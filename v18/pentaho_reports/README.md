# pentaho_reports — Odoo 18

Pure-Python renderer for Pentaho `.prpt` reports (no Java, no Tomcat, works on Odoo.sh).
This folder is the Odoo **18** build; sibling folders `../v11` … `../v19` are the same module
for other versions. Requires Python ≥ 3.10 (Odoo 18's own floor) and reportlab (bundled with Odoo).

Install: copy this folder into your addons path (or `--addons-path=/path/to/v18`), then
`odoo-bin -d <db> -i pentaho_reports`. Settings → Technical → Reports → create a report with
type *Pentaho Report* and upload the `.prpt`.

Do not edit `native/` here — it is a synced copy of `../../engine/native` (see the root README).
