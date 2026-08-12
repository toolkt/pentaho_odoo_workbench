# `pentaho_reports` — native-renderer fidelity port (2026-08-12)

**Goal:** render `.prpt` reports faithfully in the pure-Python engine (no Java) so they render on odoo.sh, using willowit's Java `Pentaho-reports-for-OpenERP` (the real Pentaho Reporting Classic engine) as the fidelity reference.

**Result — measured by actually rendering all 1,639 real reports to PDF:**

| Metric | Before | After |
|---|---:|---:|
| **RENDER-OK** (produces a `%PDF`) | 1435 / 1639 | **1582 / 1639 (~96.5%)** |
| PARSE-OK | 516 / 1639 | 1582 / 1639 |

After the port, render-OK == parse-OK (no parse-OK-but-fails-to-render files remain). The remaining ~57 (3.5%) are the genuine long tail: crosstab pivots (12), corrupt zips (6), `style-expression` *formulas*, `list-parameter` (3), stale absolute-path image resources.

> **This module is not git-tracked**, so these changes live in the working tree. Integrate by deploying the module and running `odoo -u pentaho_reports`. Then run the module tests (see bottom) and validate against a real Odoo/DB (the porting was validated with stub query rows; real report SQL exercises it fully).

---

## Changes by file (with line refs)

### `native/model.py`
- **`Style.bg_color: str | None`** (`:40`) — element background color (e.g. `"#c9c98b"`) for the new fill support.
- **`Element.barcode_type: str | None`** (`:51`) — the `simple-barcodes` `@type` (e.g. `"code128"`).
- **`Group.child: "Group | None"`** (`:74`) — makes `Group` recursive for **nested (multi-level) groups**. `None` for a leaf (single-level) group.
- **`PAGE_FORMATS` expanded 3 → 15** (`:93`) — added FOLIO (`595×935`, taken from Pentaho's own `PageSize` class, *not* iText's 612×936), LEDGER, TABLOID, LETTER/LEGAL/A4_ROTATED, LETTER/LEGAL_EXTRA, FANFOLD*, etc.
- **`PageDef.size_pt` safe fallback** (`:124`) — resolves an unknown page format via `PAGE_FORMATS.get(...)` → logs a warning → falls back to LETTER. **Never raises `KeyError`** (this was the biggest render gap: parse-OK files failing at render on unknown formats like FOLIO).

### `native/bundle.py` (parser)
- **`ELEMENT_KINDS`** gained `date-field`, `vertical-line`, `rectangle`, `simple-barcodes`, `simple-barcode` (`:26–39`).
- **`_is_ignorable_child`** (`:55`) + `_IGNORED_CHILDREN` (`:48`) — **skips Pentaho dynamic `*-expression`/`output-parameter` children** (conditional-formatting formulas) wherever they appear, instead of raising. ⚠️ *Fidelity caveat:* the element still renders, but with its **static** design-time styles (the dynamic formula is not evaluated).
- **`_to_float` tolerates trailing `%`** (`:73`) — percent spatial values (`min-width="100%"`, `x="20%"`) no longer crash; parsed as the numeric part (approximation; a bare `"%"` returns the default).
- **`_parse_group` is now recursive** (`:166`) and handles **`group-body`** (`:192`): a `group-body` wraps one nested `<group>` → parsed into `group.child`. A malformed `group-body` with no nested `<group>` now **raises `UnsupportedFeature`** (`:216`) rather than silently dropping the group's data rows.
- **`barcode_type` captured** for the barcode kinds (`:252`).
- **`background-color`/`bg-color` parsed** into `Style.bg_color` (from `border-styles`/`common-styles`/`content-styles`).
- **Nested sub-report `href` fix** (`:298`) — the href is **root-relative** (not prefix-relative); a `namelist()` pre-check skips a genuinely-missing nested part gracefully (logs + `subreport = None`) instead of a broad `except KeyError` that masked unrelated errors. Verified correct against sibling and depth-3 subreports across the corpus.
- **`has_data_bound_elements`** walks the nested `.child` chain (so nested reports aren't mis-detected as empty).

### `native/formats.py` (formatting)
- **`java_dateformat_to_strftime`** (`:108`) + `_DATE_TOKEN_MAP` (`:86`) — translates a Java `SimpleDateFormat` pattern to `strftime`, by exact `(char, run-length)` lookup (collision-proof: `MM`≠`mm`, `HH`≠`hh`). Unrecognized/quoted-literal patterns → **ISO fallback** (never a wrong char).
- **`format_value` honors the date mask** (`:139`) — `date-field` values now render in their intended format (was always ISO). `format_number` (number-field) is unchanged.

### `native/painter.py` (drawing)
- **`parse_color`** (`:25`) — `#rrggbb`/`#rgb`/named → RGB; fails closed (returns `None`) on anything malformed (never raises).
- **`fill_background`** (`:196`) — fills an element's box with `bg_color` (bottom-left origin, `stroke=0/fill=1`), skipping degenerate boxes.
- **`draw_vline`** (`:234`) — vertical line (mirror of `draw_hline`).
- **`draw_rect`** (`:240`) — rectangle outline (reuses `draw_borders` when bordered; `draw_shape=False` → skip).
- **`draw_barcode`** (`:284`) + `_BARCODE_SYMBOLOGIES` (`:278`) — renders via reportlab `createBarcodeDrawing` (`code128`→`Code128`, default `Code128`); skips empty values and **catches an unencodable value** so a bad barcode never crashes the whole report.

### `native/renderer.py` (render pipeline)
- **`fill_background(box, el.style)` called before all kind-specific drawing** (`:234`, `:253`) — so colored separator bars / cell backgrounds render behind content (additive; no geometry change).
- **Recursive grouping**: `_emit_group` (`:95`), `_partition_rows` (`:114`), `_leaf_group` (`:21`) replace the single-level loop. Emits each level's header/footer on that level's key change; single-level (leaf) behavior is byte-identical to before. `_emit_report` (`:79`) drives it; no-rows emits the *leaf* group's `no_data`. Sub-report emit/measure descend to leaf details.
- **Dispatch for the new element kinds** (`:258` vertical-line, `:261` rectangle, `:272` simple-barcode(s)) — each returns before the text branch; none added to the dynamic-height set.

### `controllers/main.py` (preview endpoint — from the desktop designer's "Preview PDF")
- **`POST /pentaho/preview`** (`:18`, `type='json'`, `auth='user'`) — decodes an uploaded `.prpt` (base64), runs its SQL on the request cursor, returns `{pdf_b64}` (or `{error}`; never a traceback). Mirrors `_render_pentaho`'s `NativeRenderer(execute_query).render(...)` with parameterized (non-interpolated) SQL.
- **Access gate** (`:41`) — rejects `user.share or not user.has_group('base.group_system')` via `AccessError`, so only Technical/report-author users can render an uploaded `.prpt` (closes an arbitrary-SQL exposure to portal users). *Requires the desktop designer's Odoo login to have `base.group_system`.*

### `native/tests/`
- `test_bundle.py` — **38 tests** (many new: expression-skip, `%` spatial, sibling/nested sub-reports, vertical-line/rectangle, `background-color` fill content-stream check, nested-group emission order, leaf-group no-regression, page-format fallback, barcodes, group-body raise).
- `test_date_field.py` — renders a real `.prpt` and extracts text to prove the date mask reaches the glyphs.
- `test_formats.py` — `format_value`/`java_dateformat_to_strftime` cases.
- `test_preview_render.py` — render-core (uploaded bytes → PDF) via a stub `execute_query`.
- `tests/test_preview_controller.py` — the HttpCase authz test (needs a live Odoo).

---

## How to run the tests
The module's `__init__.py` imports `odoo`, so run pytest from **inside `native/tests/`** (not the addon root), in a venv with `reportlab pypdf pytest`:
```bash
python3.12 -m venv /tmp/prptvenv && . /tmp/prptvenv/bin/activate && pip install reportlab pypdf pytest
cd native/tests && python -m pytest .
```
(Pre-existing failures reference a `piaggio_reports/` fixture directory that isn't in this checkout — environmental, unrelated to the port.)

## Fidelity caveats
- **Dynamic style/attribute expressions are skipped** → conditional formatting (e.g. "red if negative") renders as its static style. Full Pentaho formula evaluation is a separate, large effort — not done.
- Rectangle fill is a solid color (no gradients); barcodes are `code128`.
- Percent (`%`) spatial values are approximated as raw points.

## Remaining ~57 reports (not ported)
crosstab pivots (12), corrupt zips (6), `style-expression`-as-section formulas, `list-parameter` (3), stale absolute-path image resources — low value / genuinely unrenderable.
