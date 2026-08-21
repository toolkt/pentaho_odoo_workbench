# -*- coding: utf-8 -*-
{
    'name': 'Pentaho Reports',
    'version': '11.0.2.0.0',
    'category': 'Reporting',
    'summary': 'Render Pentaho .prpt reports natively inside Odoo',
    'description': """
Pentaho Reports — Native Renderer
=================================

Renders Pentaho Report Designer (.prpt) files to PDF entirely inside Odoo
with a pure-Python engine. No Java, no application server, no external
report service — it runs anywhere Odoo runs, including Odoo.sh.

Key Features
------------

1. **Report Management**
   - Upload and manage .prpt report files, or load them from a module path
   - Reports keep the .prpt file as the source of truth
   - Dynamic report generation with Odoo data

2. **Native Rendering Engine** (``native/``)
   - Pure-Python interpreter for the Pentaho Reporting Classic band model:
     page header/footer, report header/footer, one group level, detail
     bands, sub-reports, dynamic height, images, custom page sizes
   - SQL data sources run on Odoo's own database cursor
     (savepoint-isolated), so reports see the same data as the user
   - Geometry calibrated against the reference Java engine
     (see ``native/tests/``)

3. **Direct Printing Support**
   - Print PDF reports directly without downloading
   - Cross-browser (Chrome, Firefox, Edge, Safari) with automatic
     fallback to download

4. **Developer Features**
   - JavaScript action handler for seamless UI integration
   - Python API for programmatic report generation
   - Parameter passing (ids, user, language, timezone + custom variables)
   - Custom filenames with dynamic variables

Usage
-----

1. **Creating a Report**:
   - Navigate to Settings > Technical > Reports
   - Create a report with type "Pentaho Report"
   - Upload your .prpt file (or set a module path and "Load file from path")
   - Configure the model so it appears in that model's Print menu

2. **Python API**::

    report = self.env.ref('module.report_id')
    pdf_content, output_type = self.env['ir.actions.report']._render_pentaho(
        report.id, record_ids,
        {'variables': {'custom_var': 'value'}},
    )

3. **UI action**::

    return {
        'type': 'ir.actions.report',
        'report_name': 'report.technical.name',
        'report_type': 'pentaho',
        'context': {'active_ids': self.ids},
        'data': {'variables': {'filename': 'custom_name'}},
    }

Dependencies
------------

- reportlab (bundled with Odoo)
- Print.js library (included)
- Odoo modules: base, web
- Python >= 3.6 (the renderer is shared, byte-identical, with the Odoo 11-19 builds of this module)
    """,
    'author': 'Toolkit Inc.',
    'website': 'https://www.toolkt.com',
    'depends': ['base', 'web'],
    'external_dependencies': {'python': ['reportlab']},
    'data': [
        'views/assets.xml',
        'views/report_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
