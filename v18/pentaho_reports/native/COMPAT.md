# Compatibility rule for `engine/native`

This package is copied verbatim into `v11/…/v19/pentaho_reports/native`. The oldest
target, Odoo 11, runs on **Python 3.6.8**, so everything here must import and run on 3.6:

- no `dataclasses`, no `from __future__ import annotations`, no `X | None`,
  no `list[str]` / `dict[str, int]` / `tuple[...]` in evaluated annotations
  (use `typing.Optional/List/Dict/Tuple`, or a `# type:` comment for locals),
- no walrus (`:=`), no positional-only parameters, no `str.removeprefix`,
  no `functools.cached_property`, no `math.prod/dist`, no `zoneinfo`.
- f-strings are fine (3.6).
- reportlab: stay on the API slice used today (`pdfgen.canvas`, `pdfbase.pdfmetrics`,
  `pdfbase.ttfonts.TTFont`, `lib.colors`, `lib.utils.ImageReader`,
  `graphics.barcode.createBarcodeDrawing`); it is exercised against reportlab 3.5 → 5.0
  by `tools/engine_matrix.sh`.

Enforced by `tools/test_matrix.sh` (compileall with each Odoo's venv + the scratch matrix).
Python 3.5 (the `odoo:11` Docker image) is deliberately **not** supported.
