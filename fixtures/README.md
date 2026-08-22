# Test fixtures

Real-world `.prpt` reports used by the engine tests (`engine/native/tests`). Each was
copied with `tools/scrub_fixture.py`, which replaces the JDBC connection details the
Pentaho Report Designer embeds in `datasources/sql-ds.xml` (user → `demo`, password →
empty, url → `jdbc:postgresql://localhost/demo`). The renderer never reads those
properties — it runs the report's `static-query` on Odoo's own cursor.

| File | Exercises |
|---|---|
| `delivery_receipt.prpt`, `sales_invoice.prpt` | calibration layouts: bands, sub-report, group header/footer totals |
| `ap_voucher.prpt` | sub-report query executed once |
| `BIR_2307.prpt` | background image, custom 612×920 page |
| `evergood_sale_report.prpt` | minimal two-field detail band (preview-render path) |
| `gl_listing_nested.prpt` | nested `group-body` (multi-level groups) |
| `print_supplier_check.prpt` | `date-field` with a Java `SimpleDateFormat` mask |
| `product_barcode.prpt` | `code128` barcode element |
| `partner_list.prpt` | synthetic: `evergood_sale_report` re-pointed at `res_partner` — used by the Odoo module tests in every `vNN/pentaho_reports/tests/` |

`engine/native/tests/test_fixtures_scrubbed.py` fails if any fixture carries credentials.
