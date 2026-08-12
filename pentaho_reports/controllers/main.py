# -*- coding: utf-8 -*-
import json
import base64
import zipfile
from odoo import http, _
from odoo.exceptions import AccessError
from odoo.http import content_disposition, request
import logging

from ..native.model import UnsupportedFeature
from ..native.renderer import NativeRenderer

_logger = logging.getLogger(__name__)


class PentahoReportController(http.Controller):

    @http.route('/pentaho/preview', type='json', auth='user')
    def preview_pentaho_report(self, prpt_b64, model=None, ids=None, variables=None, **kw):
        """Render an uploaded .prpt (not yet saved as an ir.actions.report)
        to a PDF, for the true-engine preview in the Workbench designer.

        Unlike ir.actions.report._render_pentaho, the .prpt bytes come
        straight from the request body instead of a stored report record
        (the designer previews reports before/while they are saved), so the
        execute_query closure and parameters dict are rebuilt here following
        the same shape (see models/ir_actions_report.py). ``model``/``ids``
        are the record(s) the caller is previewing against.

        Unlike /pentaho/download and /pentaho/print (which only replay bytes
        the server already rendered from a stored, access-checked
        ir.actions.report), this endpoint executes the raw SQL embedded in
        whatever .prpt bytes the caller posts. auth='user' alone would let
        any logged-in user — including a portal/customer user, since
        auth='user' is not internal-only — run arbitrary SQL against the
        database. The report designer is a staff/report-author tool, so
        report-authoring privilege (the same group that can create/edit
        ir.actions.report records) is required here.
        """
        user = request.env.user
        if user.share or not user.has_group('base.group_system'):
            raise AccessError(_(
                'Report preview requires Technical (report author) access.'))

        try:
            if not isinstance(prpt_b64, str):
                _logger.warning('Pentaho preview: prpt_b64 is not a string (%s)',
                                type(prpt_b64))
                return {'error': _('No report file was uploaded.')}
            prpt_bytes = base64.b64decode(prpt_b64)
        except Exception as e:
            _logger.warning('Pentaho preview: error decoding report content: %s', e)
            return {'error': _('The uploaded report data could not be decoded.')}

        if isinstance(ids, int):
            ids = [ids]
        ids = list(ids or [])

        def execute_query(sql, params):
            # savepoint so a bad/malicious query in the previewed report
            # cannot poison the surrounding transaction (mirrors
            # ir.actions.report._render_pentaho's execute_query)
            with request.env.cr.savepoint():
                request.env.cr.execute(sql, params)
                return request.env.cr.dictfetchall()

        parameters = {
            'ids': ids,
            'user_id': request.env.uid,
            'user_name': request.env.user.name,
            'context_lang': request.env.context.get('lang', 'en_US'),
            'context_tz': request.env.context.get('tz', 'UTC'),
        }
        if variables:
            parameters.update(variables)

        try:
            pdf = NativeRenderer(execute_query).render(prpt_bytes, parameters, 'pdf')
        except UnsupportedFeature as e:
            _logger.info('Pentaho preview: unsupported feature for model=%s ids=%s: %s',
                        model, ids, e)
            return {'error': _(
                "This report uses a feature the preview renderer does not "
                "support yet: %s") % e}
        except zipfile.BadZipFile:
            _logger.info('Pentaho preview: uploaded data is not a valid .prpt archive')
            return {'error': _('The uploaded file is not a valid .prpt archive.')}
        except KeyError as e:
            # prepare_sql() raises KeyError(name) for a ${name} the report
            # references but no parameter/variable was supplied for
            _logger.info('Pentaho preview: missing parameter %s for model=%s ids=%s',
                        e, model, ids)
            return {'error': _('The report references an unknown parameter: %s') % e}
        except Exception:
            # never leak a traceback or DB error text to the client
            _logger.exception('Pentaho preview: render failed for model=%s ids=%s',
                              model, ids)
            return {'error': _(
                'The report could not be rendered. Check the report layout '
                'and query for errors.')}

        return {'pdf_b64': base64.b64encode(pdf).decode()}

    @http.route('/pentaho/download', type='http', auth='user')
    def download_pentaho_report(self, data, token=None, **kw):
        """
        Download a Pentaho report.
        
        :param data: JSON string containing [content_base64, output_type, report_name]
        :param token: Security token
        """
        try:
            result = json.loads(data)
            
            if not isinstance(result, list) or len(result) < 3:
                _logger.error('Invalid data format received: %s', result)
                return request.not_found()
            
            content_b64 = result[0]
            output_type = result[1]
            report_name = result[2]
            
            # Decode base64 content
            try:
                if isinstance(content_b64, str):
                    content = base64.b64decode(content_b64)
                else:
                    _logger.error('Content is not a string: %s', type(content_b64))
                    return request.not_found()
            except Exception as e:
                _logger.error('Error decoding report content: %s', str(e))
                return request.not_found()
            
            # Prepare response headers
            filename = f"{report_name}.{output_type}"
            headers = [
                ('Content-Type', self._get_content_type(output_type)),
                ('Content-Length', len(content)),
                ('Content-Disposition', content_disposition(filename))
            ]
            
            # Add token cookie if provided
            cookies = {'fileToken': token} if token else {}
            
            return request.make_response(content, headers, cookies)
            
        except Exception as e:
            _logger.error('Error downloading Pentaho report: %s', str(e), exc_info=True)
            return request.not_found()
    
    @http.route('/pentaho/print', type='http', auth='user')
    def print_pentaho_report(self, data, token=None, **kw):
        """
        Print a Pentaho report directly.
        Returns the PDF content with proper headers for printing.
        """
        try:
            result = json.loads(data)
            
            if not isinstance(result, list) or len(result) < 3:
                _logger.error('Invalid data format received: %s', result)
                return request.not_found()
            
            content_b64 = result[0]
            output_type = result[1]
            report_name = result[2]
            
            if output_type != 'pdf':
                return request.not_found()
            
            # Decode base64 content
            try:
                if isinstance(content_b64, str):
                    content = base64.b64decode(content_b64)
                else:
                    _logger.error('Content is not a string: %s', type(content_b64))
                    return request.not_found()
            except Exception as e:
                _logger.error('Error decoding report content: %s', str(e))
                return request.not_found()
            
            # Return PDF with inline disposition for printing
            filename = f"{report_name}.pdf"
            headers = [
                ('Content-Type', 'application/pdf'),
                ('Content-Length', len(content)),
                ('Content-Disposition', f'inline; filename="{filename}"'),
                ('Cache-Control', 'no-cache, no-store, must-revalidate'),
                ('Pragma', 'no-cache'),
                ('Expires', '0')
            ]
            
            return request.make_response(content, headers)
            
        except Exception as e:
            _logger.error('Error printing Pentaho report: %s', str(e), exc_info=True)
            return request.not_found()
    
    def _get_content_type(self, output_type):
        """Get the appropriate content type for the output format."""
        return 'application/pdf' if output_type == 'pdf' else 'application/octet-stream'