# pentaho_reports — Odoo 12

Pure-Python renderer for Pentaho `.prpt` reports (no Java, no Tomcat, works on Odoo.sh).
This folder is the Odoo **12** build; sibling folders `../v11` … `../v19` are the same module
for other versions. Requires Python ≥ 3.6 (this build's floor; Odoo 12 itself allows 3.5, which the shared renderer does not support) and reportlab (bundled with Odoo).

Install: copy this folder into your addons path (or `--addons-path=/path/to/v12`), then
`odoo-bin -d <db> -i pentaho_reports`. Settings → Technical → Reports → create a report with
type *Pentaho Report* and upload the `.prpt`.

Do not edit `native/` here — it is a synced copy of `../../engine/native` (see the root README).
