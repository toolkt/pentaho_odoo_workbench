# 2026-09-17 — Java-server parity (NextAsia Land) handed back to engine + v11–v19

## Where it came from

NextAsia Land (Odoo 18 on Odoo.sh) replaced `tk_pentaho_v18` (Tomcat Java server,
`nextasialand.odoo-host.com`) with this module's v18 copy. Every production Pentaho
report (17 reports, 22 records incl. no-data layouts) was rendered by **both** engines
from the **same** database and compared: page count/size, `pdftotext` word sequence,
and ink overlap (72 dpi, 2 px tolerance, both directions). Starting point: the client
copy was byte-identical to this repo's `engine/native` and `v18` glue.

Client commits: `5b157c1`, `c553909` (engine + glue), `37edf8b` (client `.prpt`
`ORDER BY` — client-side, not part of this repo).

## Engine changes (`engine/native`)

| Symptom in production | Fix |
|---|---|
| AP Voucher `KeyError: 'id'`; multi-record PRS repeats every record's lines | sub-report `<parameter-mapping>` input parameters; rows cache keyed by bundle + params |
| RFQ/PO/Canvass line items stacked on one line | dynamic `min-height="100%"` text cells give the row its height |
| "Nothing Follows", GRAND TOTAL, PRS total, Issuance "Received By" missing | `details-header`/`details-footer` parsed (unwrapped form) and emitted |
| Delivery Receipt grid + signature block missing | `watermark` band painted on every page |
| Check Voucher/Printing with no data → 0-page PDF | empty report is one blank page |
| AP Voucher "Bill Due", signature band visible | `visible="false"` elements/bands skipped (no space) |
| Serif text; host-dependent glyphs (Liberation Sans on Odoo.sh) | text styles inherit band → element; faces resolve to base-14 Helvetica/Times/Courier |
| Issuance quantity `2` vs Java `2.00` | text-fields print numbers as Java `String.valueOf` |
| AP Voucher "Bill Total" wrapped char-per-line; column captions overlapped | `inline` and `row` band layouts; `min-width` percentages resolved against the container |
| PRS department-head signature 12 pt high | unplaced sub-report uses its root style x **and** y |
| PRS CEO signature line missing | style-expression formula subset (`formula.py`) for `visible` / `border-*-style` |

New tests: `engine/native/tests/test_subreport_params_and_row_height.py` (30 tests).
`test_calibration.py`: Arial ascents are Helvetica's; the Java wrap-count test is no
longer skipped (Helvetica shares Arial's advance widths and it passes).

## Glue change (all nine folders, identical)

`_pentaho_execute_query`: report SQL on a side psycopg2 cursor of Odoo's connection
(same transaction) with `psycopg2.extensions.DECIMAL`, so NUMERIC keeps its scale
(`30.00`, not Odoo's float `30.0`); unwraps `TestCursor._cursor` (12+); falls back to
the plain cursor if no connection is reachable. Test:
`tests/test_render.py::test_report_queries_keep_numeric_scale` (all versions).
Checked first: `sql_db.Cursor._cnx`, `undecimalize`, `savepoint` exist in odoo11–19
(odoo19 annotates `self._cnx: PsycoConnection`); psycopg2 2.8.3–2.9.12.

## Evidence

Client benchmark (Odoo.sh render vs Java render, same records), after the fixes:
all 23 cases `text 1.00`; ink 0.99–1.00 except PO single (0.96/0.98), CA liquidation
(1.00/0.96), JV (1.00/0.91), AP Voucher (0.99/0.90) — 1 px table-border offsets.
Before: RFQ 0.39, PO(many) 0.24, DR 0.13, AP Voucher crash, empty reports 0 pages.

Engine suite, repo root (`python -m pytest`, reportlab 4.1.0):

    before: 116 passed
    after:  146 passed

Corpus sweep (`../sample_prpt`, 1,639 real bundles; stub rows; every `${param}` supplied):

    before: RENDER-OK 1582, PARSE-FAIL 57
    after:  RENDER-OK 1582, PARSE-FAIL 57   — 0 files changed outcome

`PATH=/Applications/Postgres.app/Contents/Versions/latest/bin:$PATH tools/test_matrix.sh`:

    drift                            PASS
    compile engine@py3.6             PASS
    compile v11 … v19                PASS (9)
    engine matrix                    PASS  (py36-rl3559, py39-rl3559, py39-rl4410,
                                            py39-rl500, py310-rl368, py312-rl410: 146 passed each)
    odoo v11 … v19 install+tests     PASS (9)  — test_render runs 8 tests (new test included)
