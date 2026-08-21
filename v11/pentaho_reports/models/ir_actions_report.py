# -*- coding: utf-8 -*-
"""Pentaho .prpt report actions, rendered in-process by the native engine."""
import base64
import logging
import os

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import config

from ..native.model import UnsupportedFeature
from ..native.renderer import NativeRenderer

_logger = logging.getLogger(__name__)

# addons_path is a comma-separated string in older configs, a list in Odoo 19
ADDONS_PATHS = config['addons_path']
if isinstance(ADDONS_PATHS, str):
    ADDONS_PATHS = ADDONS_PATHS.split(',')


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    report_type = fields.Selection(
        selection_add=[('pentaho', 'Pentaho Report')],
    )
    pentaho_file = fields.Binary(string='Pentaho Report File (.prpt)')
    pentaho_filename = fields.Char(string='Filename')
    pentaho_report_output_type = fields.Selection(
        [('pdf', 'PDF')],
        string='Output Format',
        default='pdf',
    )
    pentaho_load_file = fields.Boolean(
        string='Load file from path',
        help='Load the .prpt file from the path in Filename, resolved '
             'against the addons path.',
    )
    pentaho_direct_print = fields.Boolean(
        string='Direct Print',
        default=False,
        help='Print the report directly in the browser without downloading.',
    )

    @api.onchange('report_type')
    def onchange_report_type(self):
        if self.report_type == 'pentaho':
            self.pentaho_report_output_type = 'pdf'

    @api.model
    def create(self, vals):
        if vals.get('report_type') == 'pentaho':
            vals['type'] = 'ir.actions.report'
        record = super(IrActionsReport, self).create(vals)
        record._load_pentaho_files()
        return record

    def write(self, vals):
        if vals.get('report_type') == 'pentaho':
            vals['type'] = 'ir.actions.report'
        res = super(IrActionsReport, self).write(vals)
        if not self.env.context.get('skip_load_file'):
            self._load_pentaho_files()
        return res

    # ── .prpt storage ───────────────────────────────────────

    def _load_pentaho_files(self):
        """Pull .prpt content from the addons path where 'Load file' is set."""
        for report in self.filtered(
                lambda r: r.report_type == 'pentaho' and r.pentaho_load_file):
            if not report.pentaho_filename:
                continue
            content = self._read_file_from_addons(report.pentaho_filename)
            if content:
                report.with_context(skip_load_file=True).write({
                    'pentaho_file': content,
                    'pentaho_load_file': False,
                    'pentaho_filename': os.path.basename(report.pentaho_filename),
                })
            else:
                _logger.error('Failed to load file %s for report %s',
                              report.pentaho_filename, report.name)

    def _read_file_from_addons(self, filename):
        """Read a module-relative file from the addons path, base64-encoded."""
        for addons_path in ADDONS_PATHS:
            filepath = os.path.join(addons_path.strip(), filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'rb') as f:
                        return base64.b64encode(f.read())
                except OSError as e:
                    _logger.error('Error reading file %s: %s', filepath, e)
        _logger.warning('File %s not found in any addons path: %s',
                        filename, ADDONS_PATHS)
        return False

    def _pentaho_prpt_content(self):
        """The stored .prpt bytes, loading them from disk first if needed."""
        self.ensure_one()
        if self.pentaho_load_file and not self.pentaho_file:
            self._load_pentaho_files()
        if not self.pentaho_file:
            raise ValidationError(_(
                "No report file found for '%s'. Upload a .prpt file or check "
                "the file path.") % self.name)
        return base64.b64decode(self.pentaho_file)

    # ── rendering ───────────────────────────────────────────

    def _pentaho_parameters(self, res_ids, data):
        """Reserved parameters + the caller's variables, as the .prpt sees them."""
        variables = (data or {}).get('variables') or {}
        ids = res_ids or variables.get('ids') or self.env.context.get('active_ids') or []
        if isinstance(ids, int):
            ids = [ids]
        parameters = {
            'ids': list(ids),
            'user_id': self.env.uid,
            'user_name': self.env.user.name,
            'context_lang': self.env.context.get('lang', 'en_US'),
            'context_tz': self.env.context.get('tz', 'UTC'),
        }
        parameters.update(variables)
        return parameters

    def _render_pentaho_report(self, res_ids, data=None):
        """Render this .prpt report in-process → (report_bytes, output_type).

        The one place the native engine is invoked; both the JS entry point
        (render_report) and Odoo's generic report dispatch (_render_pentaho)
        funnel through here.
        """
        self.ensure_one()
        if self.report_type != 'pentaho':
            raise UserError(_('Report %s is not a Pentaho report') % self.report_name)

        def execute_query(sql, params):
            # savepoint so a bad query cannot poison the surrounding transaction
            with self.env.cr.savepoint():
                self.env.cr.execute(sql, params)
                return self.env.cr.dictfetchall()

        output_type = ((data or {}).get('output_type')
                       or self.pentaho_report_output_type or 'pdf')
        try:
            rendered = NativeRenderer(execute_query).render(
                self._pentaho_prpt_content(),
                self._pentaho_parameters(res_ids, data),
                output_type)
        except UnsupportedFeature as e:
            raise UserError(
                _('The Pentaho renderer cannot render this report: %s') % e)
        _logger.info('Pentaho renderer produced %d bytes (%s) for %s',
                     len(rendered), output_type, self.report_name)
        return rendered, output_type

    def render_pentaho(self, res_ids, data=None):
        """Odoo 11-13 generic dispatch: ir.actions.report.render(res_ids, data)
        calls render_<report_type>(res_ids, data) on the report record."""
        return self._render_pentaho_report(res_ids, data)

    @api.model
    def render_report(self, report_id, res_ids=None, data=None):
        """UI entry point → (content_b64, output_type, filename, direct_print).

        Called over ORM by the JS action handler with the report id, the
        active record ids, and the action's ``data`` dict.
        """
        report = self.browse(report_id).exists()
        if not report or report.report_type != 'pentaho':
            raise UserError(_('Report %s is not a Pentaho report') % report_id)
        content, output_type = report._render_pentaho_report(res_ids or [], data)

        filename = report.report_name
        custom = ((data or {}).get('variables') or {}).get('filename')
        if custom:
            # extension is re-added from output_type by the download controller
            filename = custom.rsplit('.', 1)[0] if '.' in custom else custom

        return (base64.b64encode(content).decode(), output_type,
                filename, report.pentaho_direct_print)
