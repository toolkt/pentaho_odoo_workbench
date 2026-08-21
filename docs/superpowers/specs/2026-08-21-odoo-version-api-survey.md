# Odoo 11–19 API survey for `pentaho_reports` (2026-08-21)
Generated from a per-version read of the local source trees at `/Volumes/Workspace/Development/OdooWorkbench/odooNN/odoo`. Every claim cites `file:line` inside that tree. This is the reference the per-version glue in `vNN/pentaho_reports` is written against.

---

## Odoo 11

### Python floor

setup.py:60 `python_requires='>=3.5'` (odoo/release.py:15 `version_info = (11, 0, 0, FINAL, 0, '')`). The project venv runs Python 3.6.8 (/Volumes/Workspace/Development/OdooWorkbench/odoo11/venv/bin/python). Code must stay 3.5/3.6-compatible: no f-strings if 3.5 is a real target, no dataclasses, no `from __future__ import annotations`, no walrus.

### Report-action JS: mechanism

Legacy jQuery/underscore widget stack with the `odoo.define(name, function(require){...})` AMD-ish loader (addons/web/static/src/js/boot.js:100-135). Report actions are dispatched by `web.ActionManager.do_action` which converts `action.type` 'ir.actions.report' into the method name `ir_actions_report` and calls `this[type](action, options)` (addons/web/static/src/js/chrome/action_manager.js:685-690, 721). The core implementation of `ir_actions_report` lives in the `report.report` module via `ActionManager.include({ ir_actions_report: function (action, options) {...} })` (addons/web/static/src/js/report/qwebactionmanager.js:70-142). There is NO registry of report handlers, no action service, no `registry.category('ir.actions.report handlers')`, no OWL.

### Report-action JS: evidence

addons/web/static/src/js/chrome/action_manager.js:632 (`do_action`), :667 (`action.context = pyeval.eval('context', ncontext)`), :685 (`var type = action.type.replace(/\./g,'_')`), :688-690 (unknown type -> console.error + rejected deferred), :721 (`$.when(this[type](action, options))`); addons/web/static/src/js/report/qwebactionmanager.js:1 (`odoo.define('report.report', ...)`), :4 (`require('web.ActionManager')`), :70-71 (`ActionManager.include({ ir_actions_report: function (action, options)`), :77 (`qweb-html` branch), :88-89 (`qweb-pdf` branch, `framework.blockUI()`), :137-140 (else branch: `self.do_warn(_t('Error'), _t('Non qweb reports are not anymore supported.'), true); return;`); addons/web/views/webclient_templates.xml:235 (qwebactionmanager.js is in `web.assets_backend`). Sidebar Print menu flow: addons/web/static/src/js/chrome/sidebar.js:135-168 calls `/web/action/load` with `action_id: item.action.id` then `self.do_action(result, {on_close})`; addons/web/controllers/main.py:1203-1227 (`/web/action/load` sets `bin_size: True` in context for ir.actions.report at :1220 and returns `clean_action(action.read()[0])`). Bindings for the Print menu: odoo/models.py:1407-1425 (`fields_view_get(toolbar=True)` -> `ir.actions.actions.get_bindings`), odoo/addons/base/ir/ir_actions.py:86-113 (`get_bindings` does `action.read()[0]` WITHOUT bin_size).

### Report-action JS: how to intercept a custom report_type

What the core does with an unknown report_type: it does NOT fall through or throw — `report.report`'s `ir_actions_report` hits its final `else` and shows a warning notification 'Non qweb reports are not anymore supported.' then returns undefined (qwebactionmanager.js:137-140). Therefore the addon must `.include()` on `web.ActionManager` AFTER `report.report` has been included, i.e. it MUST `require('report.report')` so the loader orders it after the core include; otherwise the core's else-branch swallows the pentaho type before your override runs (include chain is LIFO: the last include's method runs first and decides whether to call `_super`). Exact pattern for this version (classic script, no ES module):

```js
odoo.define('pentaho_reports.report', function (require) {
'use strict';

var ActionManager = require('web.ActionManager');
var core = require('web.core');
var crash_manager = require('web.crash_manager');
var framework = require('web.framework');
var session = require('web.session');
require('report.report');   // force load order: our include must wrap the core qweb include

var _t = core._t;

ActionManager.include({
    ir_actions_report: function (action, options) {
        if (action.report_type !== 'pentaho') {
            return this._super.apply(this, arguments);
        }
        var self = this;
        action = _.clone(action);
        // action.context is already a plain evaluated object here (action_manager.js:667)
        var activeIds = action.context.active_ids || [];
        framework.blockUI();
        // action.id is present when the action came from /web/action/load (Print menu);
        // it is ABSENT when the dict was built by ir.actions.report.report_action() (ir_actions_report.py:731-739)
        var reportId = action.id;
        var def = reportId
            ? this._rpc({model: 'ir.actions.report', method: 'render_report',
                         args: [[reportId], activeIds, action.data || {}], context: action.context})
            : this._rpc({model: 'ir.actions.report', method: 'render_report_by_name',
                         args: [action.report_name, activeIds, action.data || {}], context: action.context});
        return def.then(function (result) {
            // result = whatever render_report returns, e.g. {token: ..., filename: ...}
            var ok = session.get_file({
                url: '/pentaho/download',
                data: {key: result.key},          // becomes POST form fields; csrf_token + token are added by ajax.get_file
                complete: framework.unblockUI,    // only fires when server sets the fileToken cookie or on error
                error: crash_manager.rpc_error.bind(crash_manager),
                success: function () {
                    if (options && !action.dialog) { options.on_close(); }
                },
            });
            if (!ok) {
                self.do_warn(_t('Warning'), _t('A popup window with your report was blocked.'), true);
            }
        }, function (error, event) {
            framework.unblockUI();
            // leave event un-prevented to let crash_manager show the server error,
            // or event.preventDefault() + self.do_warn(...) to handle it yourself (ajax.js:75-81)
        });
    },
});

});
```

For the 'print' path, open a new window instead of get_file: `window.open(session.url('/pentaho/print', {key: result.key}))` (session.url: addons/web/static/src/js/core/session.js:363-374) — GET avoids the CSRF check (http.py:798-800). Register the file via an XML template inheriting `web.assets_backend` (see assets). Notes: `this._rpc({model, method, args, kwargs, context})` builds `/web/dataset/call_kw/<model>/<method>` (addons/web/static/src/js/core/rpc.js:43-50) and goes through `odoo.api.call_kw` (odoo/api.py:693-699) — methods starting with `_` cannot be called remotely (odoo/models.py:107-111), so name the ORM method `render_report` (public). Also note that `report_action()` in this version pops a 'Choose Your Document Layout' wizard for the superuser when the company has no external_report_layout/logo regardless of report_type (ir_actions_report.py:706-720) — pass `config=False` or override it.

### Download helper

`session.get_file(options)` (addons/web/static/src/js/core/session.js:278-284) which delegates to `ajax.get_file` (addons/web/static/src/js/core/ajax.js:268-380). Signature/options: `{url, data, form, success, error, complete}`; returns boolean (false = popup blocked on iOS path). Mechanics: builds a hidden `<form method="POST" action=url target=iframe>` (ajax.js:336-339), appends `csrf_token` from `core.csrf_token` (ajax.js:341-344; value comes from `odoo.csrf_token`, addons/web/static/src/js/services/core.js:54), appends every `options.data` key plus a numeric `token` (ajax.js:347-352), submits (ajax.js:357-360), then polls `document.cookie` every 1s for `fileToken=<token>` to fire `success` and `complete` (ajax.js:362-378). CRITICAL: the server route MUST accept `token` (and `csrf_token` is popped by HttpRequest.dispatch, http.py:800, so accept `**kw`) and MUST `response.set_cookie('fileToken', token)` on the PDF response, exactly like `/report/download` does (addons/web/controllers/main.py:1639-1640), otherwise `complete`/unblockUI never fire. Server errors must be returned as an HTML/JSON body in the iframe — `/report/download` returns `request.make_response(html_escape(json.dumps({'code':200,'message':'Odoo Server Error','data': _serialize_exception(e)})))` (main.py:1644-1651), which ajax.get_file parses and passes to `options.error` (ajax.js:307-328). There is NO `@web/core/network/download`, no `framework.download`, no `downloadFile` in this version. For GET-based opening use `framework.redirect(url)` (misc.js:190-200 exports) or `window.open(session.url(path, params))`.

### Block UI

`var framework = require('web.framework'); framework.blockUI(); framework.unblockUI();` — defined in addons/web/static/src/js/core/misc.js:1 (`odoo.define('web.framework', ...)`), :57-64 (`blockUI` wraps `$.blockUI` + a Throbber + `o_ui_blocked` body class), :66-71 (`unblockUI`), exported at :196-200. Exactly what qwebactionmanager.js:89 and :133 use.

### Notification

Any Widget (ActionManager included) has `this.do_notify(title, message, sticky, className)` and `this.do_warn(title, message, sticky, className)` from ServicesMixin (addons/web/static/src/js/core/mixins.js:532-537), which `trigger_up('notification' | 'warning', ...)`; the web client catches these and calls `NotificationManager.notify/warn` (addons/web/static/src/js/chrome/abstract_web_client.js:48-50, :211-213; addons/web/static/src/js/widgets/notification.js:65-70, module `web.notification`). Used by the core report handler at qwebactionmanager.js:94 and :112. For modal errors: `Dialog.alert(owner, message, options)` (addons/web/static/src/js/core/dialog.js:197). Server-side RPC errors are shown automatically by `web.crash_manager` via the `rpc_error` bus event (ajax.js:75-81, abstract_web_client.js:168) unless the rejection handler calls `event.preventDefault()`. There is no `notification` service / `useService('notification')` in this version.

### ES module (`/** @odoo-module **/`) supported

False

### Assets

XML template inheriting `web.assets_backend` — there is NO `assets` manifest key in this version. Evidence: the manifest loader's default descriptor keys are `application, author, auto_install, category, depends, description, icon, installable, license, post_load, version, web, website, sequence, summary` plus `depends data demo test init_xml update_xml demo_xml` (odoo/modules/module.py:310-329); an `assets` key would be silently stored and ignored. `grep -rn "odoo-module\|'assets'" odoo/modules/module.py odoo/tools addons/web/static/src/js/boot.js` finds nothing. The bundle is the QWeb template `web.assets_backend` (addons/web/views/webclient_templates.xml:93) and addons extend it with `<template id="assets_backend" name="..." inherit_id="web.assets_backend"><xpath expr="." position="inside"><script type="text/javascript" src="/pentaho_reports/static/src/js/report.js"/></xpath></template>` (exact pattern used by addons/mail/views/mail_templates.xml:4-8), listed under the manifest `'data'` key. Bundled JS is concatenated + rjsmin-minified as plain scripts (odoo/addons/base/ir/ir_qweb/assetsbundle.py:273-276, :580-582) — no transpilation, so `/** @odoo-module **/`, `import`/`export` are syntax errors; files must use `odoo.define('module.name', function (require) {...})` (addons/web/static/src/js/boot.js:100-135). QWeb XML templates go under the manifest `'qweb'` key (addons/mail/__manifest__.py:45).

### Views: conditional attribute syntax

Must use `attrs="{'invisible': [('report_type','!=','pentaho')], 'required': [('report_type','=','pentaho')]}"` (domain syntax). Evidence: odoo/osv/orm.py:64-66 `transfer_node_to_modifiers` does `modifiers.update(safe_eval(node.get('attrs')))`; the plain `invisible="..."`/`required="..."`/`readonly="..."` attributes are evaluated ONCE server-side at view post-processing with only `{'context': ...}` in scope: `bool(safe_eval(node.get(a), {'context': context or {}}))` (orm.py:75-77). A Python-expression form like `invisible="report_type != 'pentaho'"` is REJECTED: verified with the venv — `safe_eval("report_type != 'pentaho'", {'context': {}})` raises `ValueError: <class 'NameError'>: "name 'report_type' is not defined"`, which surfaces from `ir.ui.view._check_xml` -> `postprocess_and_fields` (odoo/addons/base/ir/ir_ui_view.py:330-349, :788, :876) at module install. Base's own report form uses attrs (odoo/addons/base/ir/ir_actions.xml:65, :73). Field names used in attrs are validated against the model (`get_attrs_field_names`, ir_ui_view.py:945-1013, missing check :1085).

### Views: report form xmlid

`base.act_report_xml_view` (odoo/addons/base/ir/ir_actions.xml:50-96, model ir.actions.report). It contains `<field name="report_type"/>` at :71 inside `<group><group>` (between `<field name="name"/>` :70 and `<field name="paperformat_id" .../>` :72-73), so `<xpath expr="//field[@name='report_type']" position="after">` (or `<field name="report_type" position="after">`) is a valid anchor. Other anchors: `<notebook>` with pages `security` and `advanced` (:83-92), button box `name="button_box"` (:57). Tree view: `base.act_report_xml_view_tree` (:97-110, also has `report_type` at :106).

`report_type` field present in form: True

### Views: report search xmlid

`base.act_report_xml_search_view` (odoo/addons/base/ir/ir_actions.xml:111-126): `<search string="Report Xml">` with `<field name="name" .../>` (:116-118), `<field name="model" .../>` (:119), and a `<group expand="0" string="Group By">` containing `<filter string="Report Type" .../>` and `<filter string="Report Model" .../>` (:120-123). Filters have no `name` attribute, so anchor by `//field[@name='model']` or `//group` / `//filter[@string='Report Type']`. The act_window `base.ir_action_report` (:127-134) uses it.

### Routes: JSON route type

`type='json'`. odoo/http.py:439 (`:param type: The type of request, can be 'http' or 'json'`), :507 `assert 'type' not in routing or routing['type'] in ("http", "json")`. JsonRequest class at :538, `_request_type = "json"` at :577.

### Routes: is type='json' still accepted

'json' is the ONLY JSON type; `type='jsonrpc'` does not exist and fails the assert at odoo/http.py:507 (AssertionError at import/decoration time, i.e. module load). Request class is chosen by mimetype: `application/json` or `application/json-rpc` -> JsonRequest, else HttpRequest (http.py:1405-1412); mismatch between route type and request type raises BadRequest (http.py:316-319).

### Routes: content_disposition

`from odoo.http import content_disposition`; `def content_disposition(filename)` at odoo/http.py:1651-1655 — single positional arg, returns `"attachment; filename*=UTF-8''%s" % url_quote(ustr(filename))`. No `disposition_type` / inline parameter; for inline PDF build the header yourself (`'inline; filename*=UTF-8\'\'...'`). Usage example: addons/web/controllers/main.py:1639 `response.headers.add('Content-Disposition', content_disposition(filename))` and :1575-1576 `request.make_response(pdf, headers=[('Content-Type','application/pdf'), ('Content-Length', len(pdf))])`.

### Routes: request.make_response

`request.make_response(self, data, headers=None, cookies=None)` at odoo/http.py:837-855; `headers` is a list of `(name, value)` tuples, `cookies` a mapping applied via `response.set_cookie(k, v)`. Returns `odoo.http.Response` (werkzeug subclass) so you can also call `response.set_cookie('fileToken', token)` / `response.headers.add(...)` afterwards (main.py:1639-1640).

### Routes: JSON request shape

Yes: `JsonRequest.__init__` parses the body into `self.jsonrequest` (http.py:613) and `self.params = dict(self.jsonrequest.get('params', {}))` then pops `context` out of params into `self.context` (http.py:619-620); `dispatch` calls `self._call_function(**self.params)` (http.py:695), so every key of the JSON-RPC `params` object becomes a keyword argument of the controller method (docstring http.py:538-560: params must be an object, not an array). `request.jsonrequest` and `request.params` both exist. The return value is wrapped as `{'jsonrpc':'2.0','id':..., 'result': ...}` by `_json_response` (http.py:622-646). JSON routes are NOT CSRF-checked (CSRF only in `HttpRequest.dispatch`, http.py:798-831). For type='http' routes, query args + form fields + files are merged into `request.params` and passed as kwargs (http.py:761-766, :832); `csrf_token` is popped before the call (http.py:800) and a POST without a valid token is rejected with BadRequest unless `csrf=False` (http.py:798-829).

### ORM: create decorator

`@api.model_create_multi` does NOT exist — `grep model_create_multi odoo/api.py odoo/models.py` is empty. Available decorators in odoo/api.py: `constrains`(:138), `onchange`(:170), `depends`(:211), `returns`(:236), `model`(:311), `multi`(:332), `one`(:351), `model_cr`(:387), `model_cr_context`(:409), `noguess`(:617). `create` is single-dict: odoo/models.py:3404-3406 `@api.model @api.returns('self', lambda value: value.id) def create(self, vals)`; `write` is `@api.multi def write(self, vals)` (models.py:3050-3051). Override shape: `@api.model def create(self, vals): ... return super(IrActionsReport, self).create(vals)` and `@api.multi def write(self, vals): ... return super(...).write(vals)`. Undecorated methods go through `api.guess` (api.py:623-645) which treats record-style methods as `multi`; decorate explicitly anyway. Public ORM methods called from JS go through `call_kw` (api.py:693-699); names starting with `_` are blocked (models.py:107-111).

### ORM: selection_add / ondelete

`selection_add=[('pentaho', 'Pentaho')]` is supported (odoo/fields.py:1759-1760 docstring, :1795-1804 `_setup_attrs` merges via OrderedDict). `ondelete=` is NOT a known Selection parameter: Selection `_slots` only has `selection` (fields.py:1766-1768). Passing `ondelete={...}` does not raise — unknown kwargs are kept in `field.args` (fields.py:318-322, verified in venv: `args: {'selection_add': [...], 'ondelete': {...}}`) and end up as inert `_attrs` (fields.py:347-354) — so it is silently ignored, not enforced. Drop it for clarity. Extending field must be redeclared as `report_type = fields.Selection(selection_add=[('pentaho', 'Pentaho')])` in a model with `_inherit = 'ir.actions.report'`.

### ORM: cr.savepoint()

Yes: `cr.savepoint()` context manager exists — odoo/sql_db.py:406-418 (`@contextmanager @check def savepoint(self)`: SAVEPOINT/ROLLBACK TO/RELEASE with a uuid name). Use `with self.env.cr.savepoint(): ...`. No `flush=` parameter (no flush concept in 11).

### ORM: config['addons_path'] type

`odoo.tools.config['addons_path']` is a comma-joined STRING: odoo/tools/config.py:464 `self.options['addons_path'] = ','.join(default_addons)` and :466-468 `",".join(os.path.abspath(...) for x in self.options['addons_path'].split(','))`. The list form is `odoo.tools.config.addons_paths` (`conf.addons_paths = self.options['addons_path'].split(',')`, config.py:492) or `odoo.modules.module.ad_paths` (module.py:34). Prefer `odoo.modules.module.get_module_path('pentaho_reports')` / `get_resource_path(module, *args)` (module.py:156, :205).

### ORM: has_group

`self.env.user.has_group('base.group_system')` exists: odoo/addons/base/res/res_users.py:588-594 `@api.model def has_group(self, group_ext_id)` taking an XML-ID string (delegates to cached `_has_group`, :596-598). Also `_is_admin()`/`_is_superuser()`/`_is_public()` at :616-631. No `res.users.has_groups()` plural helper here.

### ORM: res.users.share

Yes: `share = fields.Boolean(compute='_compute_share', compute_sudo=True, string='Share User', store=True, ...)` at odoo/addons/base/res/res_users.py:215-216 (computed at :260). Also `res.groups.share` at :89.

### ORM: _() usage

`from odoo import _` (odoo/__init__.py:98 re-exports odoo.tools.translate._). `_` is `GettextAlias()` whose `__call__(self, source)` takes exactly ONE positional argument (odoo/tools/translate.py:425, :455; verified signature `(source)`). So the Odoo 19 style `_("Error %s", value)` raises TypeError here — you MUST write `_("Error %s") % value`. Nothing is deprecated or warned about `%` formatting; the translation is resolved by sniffing the caller's frame for `cr`/`context`/`lang` (translate.py:429-453). In JS use `core._t` / `core._lt` (qwebactionmanager.js:9-10).

### Report model: name

`ir.actions.report` (class IrActionsReport, `_name = 'ir.actions.report'`, `_inherit = 'ir.actions.actions'`, `_table = 'ir_act_report_xml'`, `_sequence = 'ir_actions_id_seq'`) at odoo/addons/base/ir/ir_actions_report.py:77-82. The old `ir.actions.report.xml` name is gone in 11 (only the SQL table keeps the `_xml` suffix). The separate `report` Python addon no longer exists — everything is in base; `'depends': ['base', 'web']` is enough.

### Report model: report_type values

`report_type = fields.Selection([('qweb-html', 'HTML'), ('qweb-pdf', 'PDF')], required=True, default='qweb-pdf', ...)` at ir_actions_report.py:89-92. Other fields: `name`(:84, translate), `type`(:85, default 'ir.actions.report'), `binding_type`(:86, default 'report'), `model`(:87, Char required), `report_name`(:93 required), `report_file`(:95), `groups_id`(:97), `multi`(:98), `paperformat_id`(:100), `print_report_name`(:101), `attachment_use`(:103), `attachment`(:105). ACL: odoo/addons/base/security/ir.model.access.csv:77-78 (read for all, full for group_system).

### Report model: render dispatch

`@api.multi def render(self, res_ids, data=None)` at ir_actions_report.py:691-696: `report_type = self.report_type.lower().replace('-', '_'); render_func = getattr(self, 'render_' + report_type, None); if not render_func: return None; return render_func(res_ids, data=data)`. So a pentaho report is dispatched to `render_pentaho(self, res_ids, data=None)` (PUBLIC name, no leading underscore — `_render_<type>` is NOT looked up) and the per-type methods return a `(content, format_str)` tuple: `render_qweb_pdf` returns `(pdf_content, 'pdf')` (:668-669), `render_qweb_html` returns `(html, 'html')` (:689). Callers: nothing generic in core calls `render()` for reports; `/report/<converter>/<reportname>` (addons/web/controllers/main.py:1551-1578) and `/report/download` (:1604-1651) call `render_qweb_pdf/html` directly and resolve reports through `_get_report_from_name`, which is hard-filtered to `('report_type','in',['qweb-pdf','qweb-html'])` (ir_actions_report.py:423-431) — pentaho reports are invisible to those routes and must be looked up with `search([('report_name','=',name)])`. `mail.template` attachment generation raises `UserError('Unsupported report type %s found.')` for non-qweb types (addons/mail/models/mail_template.py:510-512). `report_action(docids, data=None, config=True)` (:698-739) returns a dict WITHOUT `id` (keys: context, data, type, report_name, report_type, report_file, name) and, when `config=True` and uid is SUPERUSER with no external_report_layout/logo, returns the 'Choose Your Document Layout' wizard instead (:704-720).

### Report model: Binary attachment default

`fields.Binary` defaults to `attachment=False` (odoo/fields.py:1665-1670 `_slots = {'prefetch': False, 'context_dependent': True, 'attachment': False}`), i.e. stored in a `bytea` column (:1673-1675); set `attachment=True` explicitly to store in ir.attachment. Note `attachment` is forced False for non-stored fields (:1677-1681). Binary values are base64 strings in/out of the ORM. Trap: `ir.actions.actions.get_bindings` (ir_actions.py:94-110) does `action.read()[0]` with NO `bin_size` context for every Print-menu item on every `fields_view_get(toolbar=True)` (odoo/models.py:1407-1425), so a stored Binary on ir.actions.report ships the whole base64 .prpt to the browser each time a form/list view is loaded; only `/web/action/load` adds `bin_size: True` (addons/web/controllers/main.py:1219-1220).

### Report model: Print-menu binding

Inherited from `ir.actions.actions`: `binding_model_id = fields.Many2one('ir.model', ondelete='cascade')` and `binding_type = fields.Selection([('action','Action'),('action_form_only','Form-only'),('report','Report')], required=True, default='action')` (odoo/addons/base/ir/ir_actions.py:33-37); ir.actions.report sets `binding_type` default 'report' (ir_actions_report.py:86). The report's `model` field (Char, :87) is the target model name. Helpers `create_action()` (:119-125, writes binding_model_id from `ir.model._get(report.model)`) and `unlink_action()` (:128-133). In XML data: `<field name="model">res.partner</field>` + `<field name="binding_model_id" ref="base.model_res_partner"/>` (+ `binding_type` defaults to report). `multi=True` hides it from form-view toolbars (models.py:1409-1411). There is no `binding_view_types` field in 11.

### Tests: TransactionCase conventions

`odoo.tests.common` (re-exported by `odoo.tests`, odoo/tests/__init__.py:1-2) provides `TransactionCase` (odoo/tests/common.py:170-203): per-test `setUp` creates `self.registry`, `self.cr`, `self.uid = SUPERUSER_ID`, `self.env = api.Environment(self.cr, self.uid, {})` and registers rollback cleanup — override `setUp`, call `super(...).setUp()` first; there is NO per-class env on TransactionCase (no `setUpClass` with `cls.env`). `SingleTransactionCase` (:206-227) and `SavepointCase` (:229-246) create `cls.env` in `setUpClass` (:212-216) and SavepointCase wraps each test in a savepoint (:240-246) — that is the class-level-setup option. `BaseCase.cursor()` at :121. `@at_install(flag)` / `@post_install(flag)` decorators at :68-90 (default: run at install, not post-install). Tests only run if the module's `tests` package imports (odoo/modules/module.py:428-444) — `tests/__init__.py` must import the test modules. Tests run only when the module is installed WITH demo data: `has_demo = hasattr(package, 'demo') or ...` gates `run_unit_tests` (odoo/modules/loading.py:182, :205-211), and `config['demo']` is emptied by `--without-demo` (odoo/tools/config.py:473-474) — do NOT pass `--without-demo=all`.

### Tests: HttpCase

`HttpCase(TransactionCase)` at odoo/tests/common.py:249-306, `registry_test_mode = True`. `setUp` (:262-274) creates a pre-saved session and `self.opener = requests.Session()` with the `session_id` cookie (:273-274). `url_open(self, url, data=None, timeout=10)` (:276-281) — GET, or form-encoded POST when `data` is given; NO `json=`/`headers=`/`files=` kwargs. `authenticate(self, user, password)` (:283-304) logs the magic session in as that user (`self.authenticate('admin', 'admin')`). The HTTP server thread is started in test mode even with `--stop-after-init` (odoo/service/server.py:370-373). To POST to a `type='json'` route use the requests session directly so the mimetype is application/json (http.py:1409 picks JsonRequest by mimetype): `r = self.opener.post('http://%s:%s/pentaho/preview' % (HOST, PORT), json={'jsonrpc': '2.0', 'method': 'call', 'id': 1, 'params': {'report_id': rid}}, timeout=30); payload = r.json()['result']` (HOST/PORT from odoo.tests.common:46-47; no CSRF on json routes). For a POST to a `type='http'` route you must either send a `csrf_token` (form field, http.py:800, obtainable only with a request object) or use GET / `csrf=False`. Remember the test transaction is not committed: records created in the test are only visible to the HTTP thread because `registry.enter_test_mode()` makes the server reuse the test cursor (common.py:264-266; TestCursor in odoo/sql_db.py:436-466). Also `phantom_js` browser tests (:429) — irrelevant here.

### Tests: tagged

`odoo.tests.tagged` does NOT exist (`grep -rn tagged odoo/tests/` is empty; no `test_tags` option in odoo/tools/config.py). Use `@at_install(False)` / `@post_install(True)` from odoo.tests.common (common.py:68-90) for scheduling; `unittest` attributes otherwise. Remove every `@tagged(...)` import/decorator when porting.

### Tests: run command

`/Volumes/Workspace/Development/OdooWorkbench/odoo11/venv/bin/python /Volumes/Workspace/Development/OdooWorkbench/odoo11/odoo/odoo-bin --addons-path=/Volumes/Workspace/Development/OdooWorkbench/odoo11/odoo/addons,<path-to-custom-addons> -d <fresh_db> -i pentaho_reports --test-enable --stop-after-init --log-level=test` (optionally `--db_host/--db_user/--db_password`, `-p <port>` to avoid clashing with a running server since HttpCase binds the http port). Flags verified in odoo/tools/config.py: `-i/--init` :107, `-d/--database` :207, `-p/--http-port` :130, `--test-enable` :160-161 ("Enable YAML and unit tests"), `--test-file` :156, `--test-report-directory` :158, `--test-commit` :162, `--stop-after-init` :261, `--log-level` :184 (choices include 'test'), `--addons-path` :116-118. There is NO `--test-tags` in this version; you cannot select individual tests from the CLI except via `--test-file <path/to/test_x.py>` (config.py:156; loader at odoo/service/server.py:1027-1044). Do not add `--without-demo=all` (tests are skipped without demo, see transaction_case_setup). Re-running tests on an existing db: `-u pentaho_reports --test-enable --stop-after-init`.

### Other port tripwires

Other things a port of a custom report-type addon trips on in 11.0:

1. Python 3.5/3.6 floor (setup.py:60; venv is 3.6.8): no f-strings unless you accept 3.6+ only; `super(Class, self)` style is used throughout core; `pycompat` shims are present (odoo/tools/pycompat).
2. Report action dicts: the action reaching `ir_actions_report` in JS has `id` ONLY when loaded via `/web/action/load` (Print menu / sidebar.js:150-162). `report_action()` (ir_actions_report.py:731-739) returns no `id`, so code paths that call `report.report_action(docids)` from buttons/server actions need either an override adding `'id': self.id` or a JS fallback on `report_name`. `action.context` is already evaluated to a plain object with `active_ids`/`active_id`/`active_model` by the time your handler runs (action_manager.js:667; sidebar.js:140-149).
3. The superuser 'Choose Your Document Layout' interception in `report_action` (ir_actions_report.py:704-720) fires for any report_type unless `config=False`.
4. `_get_report_from_name` (ir_actions_report.py:423-431) filters to qweb types; `/report/pdf|html/<name>` routes (addons/web/controllers/main.py:1551-1578) and `/report/download` (:1604-1651) will never serve a pentaho report — your own `/pentaho/*` routes are mandatory, and they must replicate the `fileToken` cookie contract (main.py:1640) for `session.get_file` to unblock the UI (ajax.js:362-378), plus accept the extra `token` kwarg (and `**kw`) because get_file always posts it (ajax.js:347).
5. mail.template 'attach report' raises `UserError('Unsupported report type ...')` for non-qweb types (addons/mail/models/mail_template.py:510-512) — override `generate_email` if emailing pentaho PDFs is required.
6. `_()` takes a single argument (translate.py:425): rewrite `_("msg %s", x)` as `_("msg %s") % x` everywhere (TypeError otherwise). No `odoo.exceptions.RedirectWarning` signature changes relevant; `UserError`, `AccessError`, `ValidationError` exist (imported at ir_actions_report.py:4).
7. Field API: no `model_create_multi`; `@api.model create(self, vals)` and `@api.multi write(self, vals)`; `@api.depends/@api.constrains` as usual; `fields.Binary(attachment=False)` default; Selection `ondelete` silently ignored; no `fields.Image`; no `_rec_name`/`display_name` changes needed. `self.env.cr.savepoint()` exists (sql_db.py:406). No `flush()`/`flush_model`/`invalidate_recordset` — use `invalidate_cache()`/`clear_caches()` (common.py:188-189).
8. Views: only `attrs` domains; `invisible="expr"` is evaluated with just `context` at install (osv/orm.py:75-77) and fails with NameError for field references. View arch validity is checked by `ir.ui.view._check_xml` at load (ir_ui_view.py:330-349). The form view `base.act_report_xml_view` and search view `base.act_report_xml_search_view` both exist with `report_type` present in the form (ir_actions.xml:71).
9. HTTP: `type='json'` only (`jsonrpc` asserts at import, http.py:507); JSON params -> kwargs (http.py:619, :695); type='http' POST needs `csrf_token` unless `csrf=False` (http.py:798-829); `content_disposition(filename)` one-arg (http.py:1651); `request.make_response(data, headers=None, cookies=None)` (http.py:837). `werkzeug` is the underlying Response (`odoo.http.Response`), `request.httprequest` is the werkzeug request. `request.env`, `request.session`, `request.context` exist. `http.Controller` base class.
10. JS: classic `odoo.define` + `require('report.report')` ordering; `ActionManager.include` with `_super`; `this._rpc({model, method, args, kwargs, context})` (mixins.js:471-475, rpc.js:37-93) — note `_rpc` always injects `context` into kwargs; ORM method names must not start with `_` (models.py:107-111). `framework.blockUI/unblockUI`, `do_notify/do_warn`, `crash_manager.rpc_error`, `session.get_file`, `session.url`. No ES modules, no OWL, no services/registry, no `@web/...` imports, no `assets` manifest key — add the script through a `web.assets_backend` inheriting template in the `data` list (mail_templates.xml:4-8). jQuery Deferreds, not native Promises (`.then(success, failure)`, `.done/.fail`, `$.when`).
11. Tests: no `@tagged`; `TransactionCase`/`SavepointCase`/`HttpCase` from `odoo.tests.common`; HttpCase `url_open(url, data=None, timeout=10)` only; use `self.opener.post(..., json=...)` for JSON-RPC; tests are skipped unless demo data is loaded (loading.py:182, :205); no `--test-tags`; run with `-i <module> --test-enable --stop-after-init` (optionally `--test-file`). HttpCase relies on `registry.enter_test_mode()` so the server sees uncommitted test data (common.py:264-266).
12. Perf trap: Print-menu bindings are built with `action.read()[0]` without `bin_size` (ir_actions.py:94-110) on every `fields_view_get(toolbar=True)`, so a stored Binary template on `ir.actions.report` (the .prpt) is serialized in base64 into every form/list load of the bound model. Consider overriding `get_bindings` to add `bin_size=True` to the context, or keep the template in ir.attachment and store only a reference on the report.
13. No other addon in this tree (community or ../enterprise) overrides `ir_actions_report` in JS (grep of `ir_actions_report: function` finds only qwebactionmanager.js:71), so the include chain is just core -> yours.

---

## Odoo 12

### Python floor

setup.py:59 `python_requires='>=3.5'`. The venv actually used is Python 3.9.24 (/Volumes/Workspace/Development/OdooWorkbench/odoo12/venv/bin/python). odoo/release.py:15 `version_info = (12, 0, 0, FINAL, 0, '')`; checkout is branch 12.0 at ba1ba888 (2024-01-29), so late-12.0 backports are present (e.g. odoo/tests/common.py:263-285 addClassCleanup backport).

### Report-action JS: mechanism

Legacy odoo.define AMD-ish modules + jQuery 1.11.1 Deferreds (addons/web/static/lib/jquery/jquery.js header; no native Promises, no OWL, no registries). Report actions are handled by `ActionManager.include({...})` in module 'web.ReportActionManager' (addons/web/static/src/js/chrome/action_manager_report.js:1,33). `_handleAction` (action_manager_report.js:159-164) routes `action.type === 'ir.actions.report'` to `_executeReportAction(action, options)` (lines 102-130), which switches on `action.report_type`: 'qweb-html' -> `_executeReportClientAction`, 'qweb-pdf' -> `this.call('report','checkWkhtmltopdf')` then `_triggerDownload(action, options, 'pdf')`, 'qweb-text' -> `_triggerDownload(..., 'text')`, anything else -> `console.error("The ActionManager can't handle reports of type " + action.report_type)` and `return $.Deferred().reject()` (lines 125-129). There is NO registry.category('ir.actions.report handlers'), NO action_service.js, NO @web/core/* (addons/web/static/src has only js/, scss/, xml/, lib/; listing at addons/web/static/src/js/{chrome,core,services}).

### Report-action JS: evidence

addons/web/static/src/js/chrome/action_manager_report.js:1 (odoo.define('web.ReportActionManager')), :33 (ActionManager.include), :46-72 (_downloadReport: framework.blockUI + session.get_file POST /report/download + crash_manager.rpc_error + complete: framework.unblockUI), :82-93 (_triggerDownload, close_on_report_download handling, options.on_close()), :102-130 (_executeReportAction switch with unknown-type fallthrough to console.error + rejected Deferred), :159-164 (_handleAction override), :174-199 (_makeReportUrls). addons/web/static/src/js/chrome/action_manager.js:144 (doAction), :678-697 (base _handleAction switch, default console.error+reject), :537-543 (this._rpc({route, params}) usage inside ActionManager). addons/web/static/src/js/core/service_mixins.js:134-141 (_rpc via 'ajax' service), :198-203 (do_notify/do_warn). addons/web/static/src/js/core/rpc.js:42-43 (model+method -> /web/dataset/call_kw/<model>/<method>). addons/web/static/src/js/chrome/sidebar.js:146-167 (Print menu -> /web/action/load -> self.do_action(result)). addons/web/controllers/main.py:1242-1268 (/web/action/load reads the ir.actions.report record with bin_size=True and returns ALL fields incl. report_type). odoo/addons/base/models/ir_actions.py:90-116 (get_bindings -> action.read()[0], NO bin_size).

### Report-action JS: how to intercept a custom report_type

Include on `web.ActionManager` AFTER the core report include, override `_executeReportAction` and fall through with `this._super` for everything else. Core behaviour for an unknown report_type is NOT an exception: it logs console.error and returns a rejected $.Deferred (action_manager_report.js:125-129), so without an override a 'pentaho' report silently does nothing (the Print menu simply fails). Exact pattern:

```javascript
odoo.define('pentaho_reports.ReportActionManager', function (require) {
"use strict";

var ActionManager = require('web.ActionManager');
require('web.ReportActionManager');      // force core report include to be applied first
var core = require('web.core');
var crash_manager = require('web.crash_manager');
var framework = require('web.framework');  // defined in addons/web/static/src/js/core/misc.js:1
var session = require('web.session');

var _t = core._t;

ActionManager.include({
    /**
     * @override action_manager_report.js:102
     */
    _executeReportAction: function (action, options) {
        if (action.report_type === 'pentaho') {
            return this._executePentahoReportAction(action, options);
        }
        return this._super.apply(this, arguments);
    },

    _executePentahoReportAction: function (action, options) {
        var self = this;
        var context = action.context || {};
        var docids = context.active_ids || [];
        framework.blockUI();
        // 1) ORM call (JSON-RPC /web/dataset/call_kw/ir.actions.report/render_report)
        return this._rpc({
            model: 'ir.actions.report',
            method: 'render_report',
            // NOTE: action.id is present when coming from /web/action/load (Print menu),
            // but ABSENT when the action dict comes from report.report_action() in Python
            // (ir_actions_report.py:841-849) -> pass report_name too and resolve server-side.
            args: [action.id ? [action.id] : [], docids, action.data || {}, action.report_name],
            context: context,
        }).then(function (result) {
            // 2) file download through the http route
            var def = $.Deferred();
            var blocked = !session.get_file({
                url: '/pentaho/download',             // POSTed as multipart/form-data, csrf_token + token auto-appended (ajax.js:309-327)
                data: {data: JSON.stringify(result)},  // whatever render_report returned
                success: def.resolve.bind(def),
                error: function () {
                    crash_manager.rpc_error.apply(crash_manager, arguments);
                    def.reject();
                },
                complete: framework.unblockUI,
            });
            if (blocked) {
                self.do_warn(_t('Warning'), _t('A popup window with your report was blocked.'), true);
            }
            return def;
        }, function (error) {
            framework.unblockUI();
            return $.Deferred().reject(error);
        }).then(function () {
            self.do_notify(_t('Report'), _t('Report generated.'));
            if (action.close_on_report_download) {
                return self.doAction({type: 'ir.actions.act_window_close'}, _.pick(options, 'on_close'));
            }
            return options.on_close();
        });
    },
});

});
```

For a `/pentaho/print` variant open it with `window.open('/pentaho/print?...')` or do a second `session.get_file` to that route; `this._rpc` is available on ActionManager via ServicesMixin (service_mixins.js:134). jQuery 1.11 Deferred: use .then/.done/.fail/.always; no async/await, no native Promise chaining guarantees. Register the file in the backend bundle with an XML template inheriting web.assets_backend (see assets).

### Download helper

`session.get_file(options)` (addons/web/static/src/js/core/session.js:293-298) delegating to `ajax.get_file` (addons/web/static/src/js/core/ajax.js:309-388, exported at :554). It opens an XMLHttpRequest POST to `options.url` with a FormData built from `options.data`, always appends `token='dummy-because-api-expects-one'` and `csrf_token=core.csrf_token` (ajax.js:323-326), sets responseType='blob', and on `status===200 && mimetype !== 'text/html'` parses the Content-Disposition header and calls the `web.download` lib (addons/web/static/src/js/libs/download.js, listed at webclient_templates.xml:109) (ajax.js:333-344). A 'text/html' body is treated as an error: it tries JSON.parse of the body to get a serialized Odoo exception and calls `options.error(err)` (ajax.js:348-372). Callbacks: success, error, complete (onloadend). Returns true synchronously (the core code checks `!session.get_file(...)` for popup blocking, action_manager_report.js:50-62). Consequence for the server route: `/pentaho/download` must accept POST, must tolerate extra kwargs `token` (and csrf_token is popped by HttpRequest.dispatch before the call, http.py:810) — declare `def download(self, token=None, **kw)` — and must send a non-text/html Content-Type plus `Content-Disposition` (see addons/web/controllers/main.py:1657-1709 for the core /report/download pattern, which serialises exceptions as html_escape(json.dumps(error)) at :1702-1708 so get_file's error parser can read them). There is NO `@web/core/network/download`, no `framework.download`. To open a PDF inline (print) just `window.open(url)`; no helper exists.

### Block UI

`var framework = require('web.framework'); framework.blockUI(); ... framework.unblockUI();` — module defined in addons/web/static/src/js/core/misc.js:1 (`odoo.define('web.framework', ...)`), functions at :80-88 (blockUI: $.blockUI + Throbber spinner + body class o_ui_blocked) and :90-96 (unblockUI), exported at :210-214. Used exactly this way by the core report download at action_manager_report.js:47 and :60.

### Notification

From any Widget/ActionManager: `this.do_notify(title, message, sticky, className)` and `this.do_warn(title, message, sticky, className)` (addons/web/static/src/js/core/service_mixins.js:198-203), which call the 'notification' service `notify({type: 'warning'|undefined, title, message, sticky, className})`. Service: addons/web/static/src/js/services/notification_service.js:20-80 (`NotificationService.notify(params)` with params.title, .message, .type ('notification'|'warning'), .sticky, .className, .onClose, .buttons). Core uses `self.do_notify(_t('Report'), WKHTMLTOPDF_MESSAGES[state], true)` at action_manager_report.js:112 and `this.do_warn(_t('Warning'), message, true)` at :69. For server error dialogs use `crash_manager.rpc_error(error)` (addons/web/static/src/js/services/crash_manager.js:55, instance module 'web.crash_manager' at :249-253). No `useService('notification')`, no `env.services.notification.add`.

### ES module (`/** @odoo-module **/`) supported

False

### Assets

XML template inheriting web.assets_backend; there is NO 'assets' manifest key in Odoo 12. Evidence: `grep -n assets odoo/modules/module.py` returns nothing; the manifest defaults dict at odoo/modules/module.py:310-329 knows application/author/auto_install/category/depends/description/icon/installable/license/post_load/version/web/sequence/summary/website plus 'depends data demo test init_xml update_xml demo_xml' (:330-332), and any extra key from `ast.literal_eval` (:336) is stored but never consumed by the asset bundler (odoo/addons/base/models/assetsbundle.py JavascriptAsset :694-697 only rjsmin-minifies files that are listed in a template). Bundle template: addons/web/views/webclient_templates.xml:143 `<template id="assets_backend" name="Backend Assets (used in backend interface)">`. Canonical addon pattern (addons/account_bank_statement_import/views/account_bank_statement_import_templates.xml:3-7):
```xml
<odoo>
  <template id="assets_backend" name="pentaho_reports assets" inherit_id="web.assets_backend">
    <xpath expr="." position="inside">
      <script type="text/javascript" src="/pentaho_reports/static/src/js/report_action_manager.js"></script>
    </xpath>
  </template>
</odoo>
```
and list that XML file in the manifest 'data' list. JS QWeb templates (if any) go in the manifest 'qweb' key (addons/web/controllers/main.py:561 manifest_glob('qweb', ...)). `/** @odoo-module **/` is not recognised anywhere: `grep -rn odoo-module addons/web odoo/addons/base` returns nothing; the loader is `odoo.define` in addons/web/static/src/js/boot.js:94. ES `import`/`export` would be served verbatim and break the bundle.

### Views: conditional attribute syntax

Odoo 12 uses `attrs="{'invisible': [('report_type','!=','pentaho')], 'required': [('report_type','=','pentaho')]}"` (domain form). Evidence: odoo/osv/orm.py:64-66 `transfer_node_to_modifiers` does `modifiers.update(safe_eval(node.get('attrs')))`; plain `invisible`/`readonly`/`required` attributes are evaluated server-side at view-load time as `bool(safe_eval(node.get(a), {'context': context}))` (orm.py:75-85) with ONLY `context` in scope, so the Odoo 17+ form `invisible="report_type != 'pentaho'"` is REJECTED: verified with the venv python — `safe_eval("report_type != 'pentaho'", {'context': {}})` raises `ValueError: <class 'NameError'>: "name 'report_type' is not defined"`, which surfaces from ir.ui.view._check_xml -> postprocess_and_fields (odoo/addons/base/models/ir_ui_view.py:338-350, :946-953) as a module-install failure. Only literal `invisible="1"`/`"0"` or context-based expressions (`invisible="context.get('x')"`) are legal in the bare attribute. The core form itself uses the attrs form for report_type-dependent visibility (odoo/addons/base/views/ir_actions_views.xml:64-65, :72-73). Form views are not RNG-validated (ir_ui_view.py:351 comment; odoo/tools/view_validation.py:63-118 python validators only); tree/search/etc. are RNG-validated (odoo/addons/base/rng/, view_validation.py:51-52).

### Views: report form xmlid

base.act_report_xml_view — odoo/addons/base/views/ir_actions_views.xml:50 `<record id="act_report_xml_view" model="ir.ui.view">`, model ir.actions.report (:52). It contains `<field name="report_type"/>` at :71 inside the first `<group><group>` (:69-74), followed by `<field name="paperformat_id" attrs="{'invisible':[('report_type','not in',['qweb-pdf'])]}"/>` (:72-73), so `<xpath expr="//field[@name='report_type']" position="after">` (or `<field name="report_type" position="after">`) anchors correctly. Other anchors: `//field[@name='report_name']` (:77), notebook pages name="security" (:82) and name='advanced' (:85), button box name="button_box" (:57). Tree view: base.act_report_xml_view_tree (:98). Window action: base.ir_action_report (:126).

`report_type` field present in form: True

### Views: report search xmlid

base.act_report_xml_search_view — odoo/addons/base/views/ir_actions_views.xml:111-124; root `<search string="Report Xml">` with `<field name="name" filter_domain=...>` (:116-118), `<field name="model" ...>` (:119), and a `<group expand="0" string="Group By">` holding filters name="report_type" (:121) and name="report_model" (:122). Search views ARE RNG-validated (odoo/addons/base/rng/search_view.rng via view_validation.py:51-52), so only elements allowed by that schema (field/filter/separator/group) may be added.

### Routes: JSON route type

'json'. odoo/http.py:516 `assert 'type' not in routing or routing['type'] in ("http", "json")` inside `def route(route=None, **kw)` (:439); docstring :449 `:param type: The type of request, can be 'http' or 'json'`. JsonRequest._request_type = "json" (:586), HttpRequest._request_type = "http" (:768). Core example: `@http.route(['/report/check_wkhtmltopdf'], type='json', auth="user")` addons/web/controllers/main.py:1711.

### Routes: is type='json' still accepted

'json' is the ONLY JSON type. `type='jsonrpc'` is rejected at import time by the AssertionError at odoo/http.py:516 (the whole controller module fails to load). No alias/deprecation machinery exists in this version.

### Routes: content_disposition

`from odoo.http import content_disposition` — defined at odoo/http.py:1655-1659: `def content_disposition(filename): filename = odoo.tools.ustr(filename); escaped = urls.url_quote(filename, safe=''); return "attachment; filename*=UTF-8''%s" % escaped`. Single positional argument, no `disposition_type=` kwarg (so `content_disposition(name, 'inline')` would TypeError). addons/web/controllers/main.py:45 imports it the same way; usage :1697 `response.headers.add('Content-Disposition', content_disposition(filename))`. Not re-exported from odoo.tools.misc.

### Routes: request.make_response

`request.make_response(self, data, headers=None, cookies=None)` — odoo/http.py:847-864; `headers` is a list of (name, value) tuples, `cookies` a mapping set via response.set_cookie(k, v). Returns odoo.http.Response. Core PDF example addons/web/controllers/main.py:1623-1625: `pdfhttpheaders = [('Content-Type', 'application/pdf'), ('Content-Length', len(pdf))]; return request.make_response(pdf, headers=pdfhttpheaders)`. Http handlers may also return a werkzeug Response/HTTPException, bytes/str (wrapped as HTML), or falsy -> 204 (http.py:749-766, :842-845, :519-540 response_wrap). `request.not_found()` exists (:885). http routes: all HTTP methods accepted unless `methods=[...]` given (:460-461); unsafe methods (POST) require `csrf_token` form field unless `csrf=False` (HttpRequest.dispatch :808-840) — note session.get_file always POSTs with csrf_token appended, so keep csrf on and accept `**kw`.

### Routes: JSON request shape

Yes: JsonRequest.__init__ parses the body (`json.loads`, http.py:616-626) into `request.jsonrequest` (:622) and sets `self.params = dict(self.jsonrequest.get('params', {}))` (:628); `context` is POPPED from params into request.context (:629), so a handler never receives a `context` kwarg. JsonRequest.dispatch calls `self._call_function(**self.params)` (:705) — every key in the JSON-RPC `params` object becomes a keyword argument of the controller method (positional JSON-RPC arrays are not supported). The return value is wrapped as `{'jsonrpc': '2.0', 'id': <request id>, 'result': <value>}` (:631-651, serialised with date_utils.json_default); exceptions become `{'error': ...}` via serialize_exception. `request.params`, `request.jsonrequest`, `request.context`, `request.env`, `request.session`, `request.httprequest` are all available. Route-level `_call_function` also rejects type mismatches: a json route hit with a plain http request raises BadRequest (http.py:323-329).

### ORM: create decorator

Yes, `@api.model_create_multi` exists: odoo/api.py:466-475 (`def model_create_multi(method)`, wrapper._api = 'model_create'); `@api.model_create_single` also exists (:447-456). Both accept a single dict or a list of dicts. BaseModel.create itself is `@api.model_create_multi def create(self, vals_list)` (odoo/models.py:3511-3513); ir.actions.actions overrides create with `@api.model_create_multi def create(self, vals_list)` (odoo/addons/base/models/ir_actions.py:48-53) and `@api.multi def write(self, vals)` (:55-60), both calling `self.clear_caches()` because get_bindings is ormcached. `@api.multi` (odoo/api.py:336) and `@api.one` (:355) still exist and `@api.multi` is the conventional decorator on write/record methods in 12 (models are auto-wrapped by `api.guess`, odoo/api.py:671-717, so omitting it is tolerated). call_kw dispatch: odoo/api.py:751-760 — `_api == 'model'` -> model call, 'model_create' -> create style, anything else -> multi (first RPC arg = ids).

### ORM: selection_add / ondelete

`selection_add=[('pentaho', 'Pentaho')]` is supported (odoo/fields.py:1974-1975 docstring; merged in Selection._setup_attrs :2009-2020 via OrderedDict(self.selection + selection_add)). `ondelete=` on Selection is NOT supported and NOT validated: the Selection _slots are only 'selection' and 'validate' (:1982-1985); any unknown kwarg goes through Field.__init__ (:359-363) into `self.args` and then `set_all_attrs` (:387-394) stores it silently in `_attrs` — no error, no warning (only RENAMED_ATTRS are warned about, :488-491). So passing `ondelete={'pentaho': 'cascade'}` is ignored silently; omit it to avoid confusion. The `ondelete` slot at :2180 belongs to Many2one only. Note Odoo 12 also lacks a selection-value cleanup on uninstall, so records with report_type='pentaho' survive module removal.

### ORM: cr.savepoint()

Yes: `cr.savepoint()` is a @contextmanager on the Cursor — odoo/sql_db.py:403-415 (`@contextmanager @check def savepoint(self)`, SAVEPOINT/ROLLBACK TO/RELEASE with uuid name). Usage `with self.env.cr.savepoint(): ...`. No `flush` parameter (Odoo 12 has no flush()). Note the test `SavepointCase` (odoo/tests/common.py:557-581) uses raw SAVEPOINT SQL, not this helper.

### ORM: config['addons_path'] type

str — comma-separated. odoo/tools/config.py:467-479: `self.options['addons_path'] = ','.join(default_addons)` / `",".join(os.path.abspath(...) for x in self.options['addons_path'].split(','))`; consumers split it: :505 `conf.addons_paths = self.options['addons_path'].split(',')`. So `odoo.tools.config['addons_path']` is a str; use `odoo.tools.config['addons_path'].split(',')`, or `odoo.modules.module.get_module_path(name)` (odoo/modules/module.py:156) / `get_resource_path(module, *args)` (:205) / `odoo.addons.__path__`.

### ORM: has_group

`self.env.user.has_group('module.xmlid')` exists: odoo/addons/base/models/res_users.py:727-731 (`@api.model def has_group(self, group_ext_id)` -> sudo(user=uid)._has_group), `_has_group` :733-749 is ormcached and asserts the xmlid is fully qualified ('module.ext_id'). Also available: `_is_system()` (:759-762, base.group_system), `_is_admin()` (:764-767, superuser or base.group_erp_manager), `_is_superuser()` (:769-772). `self.env.is_admin()/is_system()` do NOT exist on Environment in 12 — call them on the user record. `sudo(user=uid)` (odoo/models.py:4789) is the way to switch user; `with_user()` does not exist.

### ORM: res.users.share

Yes: `share = fields.Boolean(compute='_compute_share', compute_sudo=True, string='Share User', store=True, ...)` on res.users — odoo/addons/base/models/res_users.py:238-239 (res.groups also has a `share` Boolean at :104).

### ORM: _() usage

`from odoo import _` works (odoo/__init__.py:139 `from odoo.tools.translate import _`); `_` is a `GettextAlias` instance (odoo/tools/translate.py:353, instance at :459) whose `__call__(self, source)` takes EXACTLY ONE positional argument (:429) and looks the string up in ir.translation by inspecting the caller frame for lang/cr (:434-457). Consequences: the Odoo 17+ form `_("Hello %s", name)` raises TypeError (too many args); the correct 12 idiom is `_("Hello %s") % name` — it is NOT deprecated and emits no warning (no warn/deprecat hits in translate.py apart from unrelated csv/PO-file logging at :124, :605, :867). `_lt` (lazy) exists in the JS side as core._lt (action_manager_report.js:17) but there is no Python `LazyTranslate`/`_lt` convenience beyond `odoo.tools.translate._lt`? — not relied on here.

### Report model: name

ir.actions.report (class IrActionsReport, `_name = 'ir.actions.report'`, `_inherit = 'ir.actions.actions'`, `_table = 'ir_act_report_xml'`) — odoo/addons/base/models/ir_actions_report.py:80-85. `ir.actions.report.xml` no longer exists in 12 (already renamed); the XML ids of the base views still carry the old `act_report_xml_*` names (ir_actions_views.xml:50, :98, :111).

### Report model: report_type values

odoo/addons/base/models/ir_actions_report.py:93-101: `report_type = fields.Selection([('qweb-html', 'HTML'), ('qweb-pdf', 'PDF'), ('qweb-text', 'Text')], required=True, default='qweb-pdf', help=...)`. Other fields on the model: name (translate=True) :87, type default 'ir.actions.report' :88, binding_type default 'report' :89, model (Char, required) :90, model_id (computed m2o ir.model, with search) :91, report_name (Char required) :102, report_file :104, groups_id m2m :106, multi :107, paperformat_id :109, print_report_name :110, attachment_use :112, attachment (Char, python expr) :114. No `_get_readable_fields` in this version (grep empty).

### Report model: render dispatch

`@api.multi def render(self, res_ids, data=None)` at ir_actions_report.py:796-802: `report_type = self.report_type.lower().replace('-', '_'); render_func = getattr(self, 'render_' + report_type, None); if not render_func: return None; return render_func(res_ids, data=data)`. So the per-type hook is PUBLIC `render_<type>` (NOT `_render_<type>`), i.e. for report_type='pentaho' define `def render_pentaho(self, res_ids, data=None)` on ir.actions.report; convention for return is a tuple `(content, format)` — `render_qweb_pdf(self, res_ids=None, data=None)` :657-661 (@api.multi), `render_qweb_text(self, docids, data=None)` :754-760 and `render_qweb_html(self, docids, data=None)` :762-770 (both @api.model) return `(self.render_template(...), 'text'|'html')`. There is NO `_render`, `_render_<type>`, `_render_qweb_pdf` in 12. Also relevant: `report_action(self, docids, data=None, config=True)` :804-849 builds the client action dict WITHOUT an `id` key (:841-849: context, data, type, report_name, report_type, report_file, name) and, for admin users with no external_report_layout_id/logo, returns the 'Choose Your Document Layout' wizard instead (:810-824) unless `config=False` — pass config=False for non-QWeb reports. `_get_report_from_name(report_name)` :475-483 (@api.model) resolves a report by report_name. `retrieve_attachment(record)` :174-189 and `postprocess_pdf_report(record, buffer)` :191-216 implement the attachment/attachment_use behaviour for PDFs (ir.attachment keyed on datas_fname). /report/download core controller returns 204 for non-qweb types (addons/web/controllers/main.py:1700-1701).

### Report model: Binary attachment default

`fields.Binary` defaults to `attachment=False` (stored as a bytea column): odoo/fields.py:1848-1859 `_slots = {'prefetch': False, 'context_dependent': True, 'attachment': False}` and `column_type` returns ('bytea','bytea') unless attachment. The Odoo 13+ default of attachment=True does NOT apply; pass `attachment=True` explicitly if you want ir.attachment storage. bin_size context handling: :1896-1897. Gotcha: `ir.actions.actions.get_bindings()` (odoo/addons/base/models/ir_actions.py:90-116, used by fields_view_get toolbar at odoo/models.py:1488-1489) does `action.read()[0]` with NO bin_size, so a stored Binary on ir.actions.report is shipped base64-encoded in every toolbar payload; `/web/action/load` does set bin_size=True for reports (addons/web/controllers/main.py:1258-1261). Consider attachment=True and/or a non-prefetched field, or `groups`/readonly to limit exposure.

### Report model: Print-menu binding

Inherited from ir.actions.actions (odoo/addons/base/models/ir_actions.py:36-41): `binding_model_id = fields.Many2one('ir.model', ondelete='cascade', ...)` and `binding_type = fields.Selection([('action','Action'),('action_form_only','Form-only'),('report','Report')], required=True, default='action')`; ir.actions.report sets `binding_type` default 'report' (ir_actions_report.py:89). The report's target model is the Char field `model` (required, :90) with a computed/searchable `model_id` (:91, :117-121). `create_action()`/`unlink_action()` (:156-169) set/clear binding_model_id from `model`. In XML data: `<field name="binding_model_id" ref="model_xxx"/>` (module.model_<name> xmlid) and `<field name="model">res.partner</field>`. Old-style `<report .../>` shortcut tag still exists in odoo/tools/convert.py for 12 but records are fine. The form view toggles the 'Add in the Print menu' buttons on binding_model_id (ir_actions_views.xml:58-63).

### Tests: TransactionCase conventions

`from odoo.tests import common` / `from odoo.tests.common import TransactionCase, SavepointCase, HttpCase, tagged` (odoo/tests/__init__.py: `from .common import *`). TransactionCase (odoo/tests/common.py:504-534) is PER-TEST: `setUp` creates self.registry, self.cr and `self.env = api.Environment(self.cr, odoo.SUPERUSER_ID, {})` (:510-523) and rolls back after each test; it has NO class-level `cls.env` — a 19-style `setUpClass` using `cls.env` will fail with AttributeError. Use `setUp(self)` and `super(...).setUp()` (Python 3.5 floor, though py3 super() works). For class-level fixtures use `SavepointCase` (:557-581, subclass of SingleTransactionCase whose `setUpClass` creates cls.registry/cls.cr/cls.env at :543-554 and wraps each test in a SAVEPOINT :578-581). Helpers: `self.patch(obj, key, val)` (:525-529), `Form` helper exists (:1192). `addClassCleanup` is backported for py<3.8 (:265-285).

### Tests: HttpCase

`HttpCase(TransactionCase)` at odoo/tests/common.py:964-1065: `registry_test_mode = True` (the HTTP server threads reuse the test cursor via registry.enter_test_mode(self.cr), :993-997); setUp creates a session in odoo.http.root.session_store and a `self.opener = requests.Session()` with the session_id cookie (:999-1006). `self.authenticate(user, password)` (:1036-1064) logs the session in server-side (reimplements OpenERPSession.authenticate; `authenticate(None, None)` drops the session). `self.url_open(url, data=None, timeout=10)` (:1008-1013) prefixes relative URLs with `http://127.0.0.1:<http_port>` (HOST/PORT at :72-73) and does `opener.post(url, data=data)` (form-encoded) when data is given, else GET — it has NO json= kwarg, no headers kwarg. To call a type='json' route in tests use the underlying requests session directly, as the core does in addons/website/tests/test_views.py:1186-1191: `url = 'http://%s:%s/pentaho/preview' % (HOST, PORT); resp = self.opener.post(url=url, json={'params': {...}}); resp.json()['result']` (jsonrpc/id keys are optional: JsonRequest only reads .get('params') and .get('id'), http.py:628,635). JSON routes skip CSRF; a POST to a type='http' route needs `csrf_token` in the form data or `csrf=False` — GET downloads need neither. `browser_js(url_path, code, ready, login, timeout)` (:1066) runs headless Chrome tours; xmlrpc proxies are set in __init__ (:972-976). Requires the HTTP server to be running in the same process, i.e. running via odoo-bin, not plain unittest.

### Tests: tagged

`odoo.tests.tagged` exists: odoo/tests/common.py:2131-2145 `def tagged(*tags)` (prefix '-' to exclude). Default tags on every odoo.addons.* test class are {'standard', 'at_install'} plus test_module/test_class via MetaCase (:307-318). `post_install(flag)` (:108-121) is a deprecated shim over tagged. Core usage: addons/web/tests/test_js.py:12 `@odoo.tests.tagged('post_install', '-at_install')`. Tags are NOT inherited by subclasses (:2138).

### Tests: run command

`/Volumes/Workspace/Development/OdooWorkbench/odoo12/venv/bin/python odoo-bin -c <conf> -d <fresh_db> --addons-path=<odoo12/odoo/addons,../enterprise,<path containing pentaho_reports>> -i pentaho_reports --test-enable --stop-after-init` (optionally `--test-tags /pentaho_reports` or `--test-tags /pentaho_reports:TestClass.test_method`). Flags verified in odoo/tools/config.py: `-i/--init` :108, `-u/--update` :109, `-d/--database` :215, `--test-enable` :159-161, `--test-tags` :162-170 (spec `[-][tag][/module][:class][.method]`; setting it also enables tests; bare `/module` implies tag 'standard'), `--test-file` :157, `--stop-after-init` :269, `--addons-path` :117-119. at_install tests run during module install; tests tagged post_install run after all modules are loaded. HttpCase tests need the HTTP server, so do not combine with a flag that disables it (in 12 that is `--no-xmlrpc`).

### Other port tripwires

Things a port from 19 to 12 will trip on, beyond the fields above: (1) JS world is odoo.define + jQuery 1.11 Deferreds + Widget/ServicesMixin; no OWL, no registries, no @odoo-module, no hooks; the file must be registered via an XML template inheriting web.assets_backend, and your ActionManager.include must `require('web.ReportActionManager')` so your override of `_executeReportAction` layers on top of the core one (last include wins). (2) Action dicts built in Python by `report.report_action()` carry NO `id` (ir_actions_report.py:841-849) — resolve the report by `report_name` (`_get_report_from_name`) or make `render_report` tolerant of an empty ids list; and pass `config=False` to report_action or admin users without a company logo get the 'Choose Your Document Layout' wizard (:810-824). (3) `session.get_file` always POSTs multipart with `token` + `csrf_token` (ajax.js:323-326), so the `/pentaho/download` http route must accept POST + `**kw`, keep CSRF on, and must NOT answer with text/html on success (ajax.js:334) — serialize failures like addons/web/controllers/main.py:1702-1708 (`request.make_response(html_escape(json.dumps({'code':200,'message':'Odoo Server Error','data': serialize_exception(e)})))`) so the client's error parser shows a proper dialog. (4) `content_disposition()` takes one arg and always produces `attachment;` — for inline printing build the header by hand (`'inline; filename*=UTF-8\'\'%s' % url_quote(name)`), or open the URL in a new tab. (5) Python 3.5 floor (setup.py:59): no f-strings only if you care about the declared floor (the venv is 3.9, so f-strings run, but `dict` ordering / `typing` niceties should be used cautiously); no `from odoo.exceptions import ...` differences except that `UserError`/`ValidationError`/`AccessError` exist. (6) `_()` takes exactly one argument — convert every `_("...", x)` to `_("...") % x`. (7) `fields.Binary` default attachment=False (bytea column) and get_bindings ships full binaries to the toolbar; add `attachment=True` and/or `groups=` to keep the .prpt payload out of every form-view load. (8) No `ondelete` on Selection (silently ignored), no `_get_readable_fields`, no `with_user` (use `sudo(user=uid)`), no `env.is_admin()` (use `self.env.user._is_admin()`), no `flush()`/`invalidate_recordset` (use `invalidate_cache`, models.py:5219), no `_check_company`. (9) `@api.multi` on write/record methods and `@api.model` on model-level RPC targets matter for call_kw arg handling (api.py:751-760): an `@api.model` method invoked with `args: [[ids], ...]` receives the ids list as its first real argument. (10) View XML: every conditional must be `attrs=\"{...}\"`; Python-expression `invisible=` crashes at install (verified); search view additions are RNG-validated (only field/filter/group/separator). (11) Tests: TransactionCase is per-test setUp; `self.url_open` has no json=; JSON routes must be called with `self.opener.post(abs_url, json={'params': {...}})`; json `params.context` is consumed by the framework (http.py:629) and never reaches the handler. (12) Manifest: no 'assets' key (ignored silently — the JS simply never loads); 'qweb' key for JS templates; `'version'` is normalised by adapt_version to '12.0.x'. (13) json route return values are serialised with date_utils.json_default only (datetime/date/bytes are fine; anything else must be plain JSON types). (14) The web client handles unknown report types by console.error + rejected Deferred (action_manager_report.js:125-129), so a missing/failed JS include manifests as a Print menu that silently does nothing — check the browser console first.

---

## Odoo 13

### Python floor

setup.py:58 `python_requires='>=3.6'` (release: odoo/release.py:15 `version_info = (13, 0, 0, FINAL, 0, '')`). The venv at /Volumes/Workspace/Development/OdooWorkbench/odoo13/venv/bin/python was not exercised; the floor is purely from setup.py.

### Report-action JS: mechanism

Legacy odoo.define() AMD modules + Widget-style `ActionManager.include({...})`. Report support is a mixin file `web.ReportActionManager` (addons/web/static/src/js/chrome/action_manager_report.js) that overrides `_handleAction` (lines 160-165) to route `action.type === 'ir.actions.report'` into `_executeReportAction(action, options)` (lines 103-131), which switches on `action.report_type` (qweb-html -> client action; qweb-pdf -> wkhtmltopdf check then `_triggerDownload`; qweb-text -> `_triggerDownload`). There is NO registry of report handlers (`registry.category('ir.actions.report handlers')` does not exist; addons/web/static/src/js/core/registry.js is a plain class used for `core.action_registry`/`core.serviceRegistry` only, see addons/web/static/src/js/services/core.js). No action_service.js, no @web/core/network/download.js, no ES modules.

### Report-action JS: evidence

addons/web/static/src/js/chrome/action_manager_report.js:1 `odoo.define('web.ReportActionManager', ...)`; :9-12 requires `web.ActionManager`, `web.core`, `web.framework`, `web.session`; :32 `ActionManager.include({`; :45-73 `_downloadReport(url)` -> `framework.blockUI()` + `session.get_file({url:'/report/download', data:{data: JSON.stringify([url,type]), context: JSON.stringify(session.user_context)}, success, error: (error)=>{ self.call('crash_manager','rpc_error',error); reject(); }, complete: framework.unblockUI})`; :83-94 `_triggerDownload` calls `options.on_close()` or doAction act_window_close when `action.close_on_report_download`; :103-131 `_executeReportAction` report_type switch; :126-130 unknown type -> `console.error("The ActionManager can't handle reports of type " + action.report_type, action); return Promise.reject();`; :160-165 `_handleAction` override. Enterprise example of the same pattern for a custom type: ../enterprise/account_reports/static/src/js/action_manager_account_report_dl.js:13-53 (`ActionManager.include` + `_handleAction` override + `session.get_file`). action_manager.js:130-170 `doAction` -> `_preprocessAction` (780-791, evaluates action.context incl. active_ids with pyUtils) -> `_handleAction`. RPC from inside ActionManager: `this._rpc({model, method, args, kwargs})` (addons/web/static/src/js/core/service_mixins.js:144-157; route built by addons/web/static/src/js/core/rpc.js:44-51 as `/web/dataset/call_kw/<model>/<method>`).

### Report-action JS: how to intercept a custom report_type

Core behaviour for an unknown report_type: `_executeReportAction` falls into its final else branch (action_manager_report.js:126-130) -> console.error + `Promise.reject()` -> the Print menu silently fails. So the addon must override `_executeReportAction` (preferred: keeps all other types intact) on `web.ActionManager`, requiring `web.ReportActionManager` only to force load order (boot.js:266-268 stores even an undefined factory result in `services`, so requiring a module that returns nothing is fine). Exact shape for this version (file e.g. static/src/js/action_manager_pentaho.js):

odoo.define('pentaho_reports.ActionManager', function (require) {
"use strict";
var ActionManager = require('web.ActionManager');
require('web.ReportActionManager');            // load-order only; module returns undefined
var core = require('web.core');
var framework = require('web.framework');
var session = require('web.session');
var _t = core._t;

ActionManager.include({
    _executeReportAction: function (action, options) {
        if (action.report_type !== 'pentaho') {
            return this._super.apply(this, arguments);
        }
        var self = this;
        var activeIds = (action.context && action.context.active_ids) || [];
        framework.blockUI();
        return this._rpc({
            model: 'ir.actions.report',
            method: 'render_report',
            args: [[action.id], activeIds, action.data || {}],
            context: action.context,
        }).then(function (result) {
            return new Promise(function (resolve, reject) {
                session.get_file({
                    url: '/pentaho/download',            // POSTed; FormData gets 'token' + 'csrf_token' appended
                    data: {
                        data: JSON.stringify(result),     // whatever render_report returned
                        context: JSON.stringify(session.user_context),
                    },
                    success: resolve,
                    error: function (error) {
                        self.call('crash_manager', 'rpc_error', error);
                        reject();
                    },
                    complete: framework.unblockUI,
                });
            });
        }, function (err) { framework.unblockUI(); return Promise.reject(err); })
        .then(function () {
            self.displayNotification({ type: 'success', title: _t('Report'), message: _t('Report generated'), sticky: false });
            if (action.close_on_report_download) {
                return self.doAction({ type: 'ir.actions.act_window_close' }, _.pick(options, 'on_close'));
            }
            return options.on_close();
        });
    },
});
});

Notes: (a) `options.on_close` is always defined (action_manager.js:135 defaults it to a noop) and must be called so the Print menu's `reload` fires (sidebar.js:162-166). (b) The action dict reaching `_executeReportAction` is the full `read()` of the ir.actions.report record loaded through `/web/action/load` (addons/web/controllers/main.py:1646-1672; note it forces `bin_size: True` for report actions at :1664-1665, so Binary fields arrive as sizes), or the dict built by `report_action()` (ir_actions_report.py:879-887, which only carries context/data/type/report_name/report_type/report_file/name -- custom fields are NOT included there). (c) Alternative: override `_handleAction` like account_reports does, but then you must also re-check `action.type === 'ir.actions.report' && action.report_type === 'pentaho'` before falling through to `_super`. (d) `session.get_file` uses XHR POST with FormData (ajax.js:244-257) and treats any `text/html` response as an error (ajax.js:268-272), so the download route must respond with a real `application/pdf` mimetype and accept POST plus a `token` kwarg.

### Download helper

`session.get_file(options)` (addons/web/static/src/js/core/session.js:261-264) -> `ajax.get_file(options)` (addons/web/static/src/js/core/ajax.js:244-331). It always does `xhr.open('POST', options.url)` with a FormData built from `options.data` (:251-256), appends `token='dummy-because-api-expects-one'` (:257) and `csrf_token` from `core.csrf_token` (:258-260), sets `responseType='blob'`, and on `status===200 && mimetype !== 'text/html'` reads `Content-Disposition` and calls the bundled `download(blob, filename, mimetype)` (:268-279). Non-2xx or text/html responses are parsed as an Odoo HTML error page and passed to `options.error(err)` (:281-306). `options.complete` is bound to `xhr.onloadend` (:316-318). Returns `true` always (:321). There is no `@web/core/network/download` and no `framework.download`; `ajax.post(controller_url, data)` (ajax.js:324+) exists for non-download POSTs.

### Block UI

`var framework = require('web.framework'); framework.blockUI(); ... framework.unblockUI();` -- addons/web/static/src/js/core/misc.js:1 `odoo.define('web.framework', ...)`, :80-88 `blockUI()` ($.blockUI + Throbber + body.o_ui_blocked), :90-96 `unblockUI()`, exported at :221-223. Used exactly this way in action_manager_report.js:47 and :61.

### Notification

Inside any Widget/ActionManager: `this.displayNotification({title, message, type: 'info'|'success'|'warning'|'danger', sticky, className})` (addons/web/static/src/js/core/service_mixins.js:246-248) which is `this.call('notification', 'notify', options)`; deprecated-but-present shortcuts `this.do_notify(title, message, sticky, className)` (type 'warning', :253-262) and `this.do_warn(title, message, sticky, className)` (type 'danger', :266-277). Service: addons/web/static/src/js/services/notification_service.js:78-86 `notify(params)` registered as `core.serviceRegistry.add('notification', NotificationService)` (:108); params documented :58-77 (title, subtitle, message, type, sticky, className, onClose, buttons). Server errors: `this.call('crash_manager', 'rpc_error', error)` (addons/web/static/src/js/services/crash_manager.js:199). No `useService('notification')` / OWL hooks in this version.

### ES module (`/** @odoo-module **/`) supported

False

### Assets

XML template inheriting `web.assets_backend` -- there is NO manifest `assets` key in 13.0. odoo/modules/module.py:333-355 `load_information_from_description_file` seeds defaults (application, author, auto_install, depends, data, demo, test, init_xml, update_xml, demo_xml, qweb is read elsewhere) and then `info.update(ast.literal_eval(...))`; a stray `'assets'` key is stored but nothing consumes it (grep for `['assets']`/`get('assets')` in odoo/modules, odoo/addons/base/models, addons/web/controllers/main.py returns nothing; there is no ir_asset model, only odoo/addons/base/models/assetsbundle.py). Pattern: a `views/assets.xml` listed in the manifest `data` key, e.g. ../enterprise/account_reports/views/assets.xml:5-12 `<template id="..._backend" inherit_id="web.assets_backend" active="True"><xpath expr="." position="inside"><script type="text/javascript" src="/account_reports/static/src/js/action_manager_account_report_dl.js"></script></xpath></template>`; the parent template is addons/web/views/webclient_templates.xml:174 `<template id="assets_backend" ...>`. QWeb XML templates go in the manifest `qweb` key (../enterprise/account_reports/__manifest__.py:26-27). JS must be `odoo.define(...)` AMD (addons/web/static/src/js/boot.js:110-150); no `/** @odoo-module **/` transpiler exists (no 'odoo-module'/'transpile' anywhere in assetsbundle.py or odoo/tools).

### Views: conditional attribute syntax

Only `attrs="{'invisible': [domain], 'required': [domain]}"` (domain syntax) plus static `invisible="1"`/`states="..."`. odoo/addons/base/models/ir_ui_view.py:61-66 `transfer_node_to_modifiers`: `if node.get('attrs'): modifiers.update(safe_eval(node.get('attrs')))`; :75-87 a bare `invisible="..."`/`readonly`/`required` attribute is evaluated ONCE server-side with `bool(safe_eval(node.get(a), {'context': context or {}}))` -- it is NOT a per-record expression. A 17+-style `invisible="report_type != 'pentaho'"` would hit safe_eval with no `report_type` name -> NameError re-raised as ValueError (odoo/tools/safe_eval.py:381-383) -> during view validation `_check_xml` (ir_ui_view.py:380-396, via postprocess_and_fields at :394-396) becomes `ValidationError('Error while validating view ...')` at module install. Core form itself uses the attrs form: ir_actions_views.xml:60-61 `attrs="{'invisible':[('report_type','not in',['qweb-pdf', 'qweb-html', 'qweb-text'])]}"`, :72-73 `attrs="{'invisible':[('report_type','not in',['qweb-pdf'])]}"`. So port as e.g. `<field name="pentaho_file" attrs="{'invisible': [('report_type','!=','pentaho')], 'required': [('report_type','=','pentaho')]}"/>`.

### Views: report form xmlid

base.act_report_xml_view -- odoo/addons/base/views/ir_actions_views.xml:51 `<record id="act_report_xml_view" model="ir.ui.view">` (model ir.actions.report, :53). It contains `<field name="report_type"/>` at :71 inside the first `<group>` (after `<field name="name"/>` :70, before `paperformat_id` :72-73), so `<xpath expr="//field[@name='report_type']" position="after">` is a valid anchor. Other anchors: `<div class="oe_button_box" name="button_box">` :58, `<notebook>` :82 with pages `name="security"` :83 and `name='advanced'` :86. Tree view: base.act_report_xml_view_tree (:97, also has report_type at :106).

`report_type` field present in form: True

### Views: report search xmlid

base.act_report_xml_search_view -- odoo/addons/base/views/ir_actions_views.xml:111-126. Contains `<field name="name" filter_domain=...>` (:115-117), `<field name="model" ...>` (:118), and a `<group expand="0" string="Group By">` (:119-122) with filters `name="report_type"` (:120) and `name="report_model"` (:121). Anchor e.g. `<xpath expr="//filter[@name='report_type']" position="after">` or `//field[@name='model']`.

### Routes: JSON route type

'json'. odoo/http.py:497 `assert 'type' not in routing or routing['type'] in ("http", "json")`; docstring :429 `:param type: The type of request, can be 'http' or 'json'`. `JsonRequest._request_type = "json"` (:575), `HttpRequest._request_type = "http"` (:735). Core examples: addons/web/controllers/main.py:1340 `@http.route([...'/web/dataset/call_kw/<path:path>'], type='json', auth="user")`, :2084 `@http.route(['/report/check_wkhtmltopdf'], type='json', auth="user")`.

### Routes: is type='json' still accepted

'json' IS the canonical and only JSON type in 13.0; `type='jsonrpc'` does not exist and would fail the assertion at odoo/http.py:497 at import time (`AssertionError`). So the port must rename any `type='jsonrpc'` back to `type='json'`.

### Routes: content_disposition

`from odoo.http import content_disposition` -- odoo/http.py:1659-1663 `def content_disposition(filename): filename = odoo.tools.ustr(filename); escaped = urls.url_quote(filename, safe=''); return "attachment; filename*=UTF-8''%s" % escaped`. Single positional arg, no `disposition_type` kwarg. Usage in core: addons/web/controllers/main.py:44 import, :2070 `response.headers.add('Content-Disposition', content_disposition(filename))`; PDF response built as `request.make_response(pdf, headers=[('Content-Type','application/pdf'),('Content-Length',len(pdf))])` (:1987-1989).

### Routes: request.make_response

odoo/http.py:814 `def make_response(self, data, headers=None, cookies=None)` -- `headers` is a list of `(name, value)` tuples, `cookies` a Mapping applied via `response.set_cookie(k, v)` (:828-832). Returns `odoo.http.Response` (werkzeug subclass). For a file: `resp = request.make_response(pdf_bytes, headers=[('Content-Type','application/pdf'), ('Content-Length', len(pdf_bytes)), ('Content-Disposition', content_disposition(fname))])`. `request.not_found(description=None)` at :852. Also `odoo.http.send_file(filepath_or_fp, mimetype=None, as_attachment=False, filename=None, mtime=None, ...)` at :1562.

### Routes: JSON request shape

Yes: the handler receives the JSON-RPC `params` object as keyword arguments. odoo/http.py:589-598: body is `json.loads`ed into `self.jsonrequest` (:591), `self.params = dict(self.jsonrequest.get('params', {}))` (:597), `context` is popped from params into `self.context` (:598); `dispatch` calls `self._call_function(**self.params)` (:669). URL converters are merged via `kwargs.update(self.endpoint_arguments)` (:320-321). `request.jsonrequest` (full envelope) and `request.params` both exist (:591, :597). Return value is wrapped by `_json_response` (:600-616) into `{'jsonrpc':'2.0','id':..., 'result': ...}` via `json.dumps(..., default=date_utils.json_default)` -- so return JSON-serialisable data only (base64-encode bytes). JSON routes have no CSRF check (JsonRequest.dispatch :651+ has none); `type='http'` routes DO check csrf_token on non-GET (:775-786, `routing.get('csrf', True)`), but `ajax.get_file` appends `csrf_token` automatically (ajax.js:258-260) so the POSTed download route passes without `csrf=False`. The http route must also tolerate the extra `token` form field sent by get_file (ajax.js:257) -- cf. core `def report_download(self, data, token, context=None)` at addons/web/controllers/main.py:2028 -- so declare `token=None, **kw`. In tests, POST JSON with `self.opener.post(url, json={'jsonrpc':'2.0','method':'call','id':None,'params': {...}})` (odoo/addons/base/tests/test_xmlrpc.py:55-66; addons/account/tests/test_portal_attachment.py:79).

### ORM: create decorator

Yes. odoo/api.py:342-352 `def model_create_multi(method)` (wrapper `_api = 'model_create'`, :335-339 `_model_create_multi` accepts a single dict or a list). The parent `ir.actions.actions.create` is already `@api.model_create_multi def create(self, vals_list)` (odoo/addons/base/models/ir_actions.py:47-52) and `write(self, vals)` :54-58 (both call `self.clear_caches()`). ir.actions.report itself defines no create/write (grep ir_actions_report.py: none), so the addon override should be `@api.model_create_multi def create(self, vals_list): recs = super().create(vals_list) ...` and `def write(self, vals)`.

### ORM: selection_add / ondelete

NOT supported (silently ignored, not rejected). odoo/fields.py:2182-2185 `Selection._slots = {'selection': None, 'validate': True}` -- no `ondelete` slot; :2203-2239 `_setup_attrs` only processes `selection` and `selection_add` (asserts list, merges with `merge_sequences`). Any extra kwarg goes through `Field.__init__` (:260-265) into `self.args` and ends up as a non-slot `_attrs` entry via `set_all_attrs` (:290-297); RENAMED_ATTRS/DEPRECATED_ATTRS (:35-36) do not list `ondelete`, so no warning either. Conclusion: `report_type = fields.Selection(selection_add=[('pentaho', 'Pentaho')])` -- drop the `ondelete=` kwarg (it would be harmless but meaningless; reviewers may object). No uninstall cleanup of the value happens automatically.

### ORM: cr.savepoint()

Yes. odoo/sql_db.py:440-457 `@contextmanager def savepoint(self, flush=True)` on Cursor: `SAVEPOINT "<uuid>"`, flushes env before/after when `flush=True`, `ROLLBACK TO SAVEPOINT` on exception. Usage: `with self.env.cr.savepoint(): ...`. Pair with `tools.mute_logger('odoo.sql_db')` in tests if you expect an SQL error.

### ORM: config['addons_path'] type

str (comma-joined). odoo/tools/config.py:479-491 normalises `self.options['addons_path']` to `','.join(...)`; the list form lives on `odoo.conf.addons_paths` = `self.options['addons_path'].split(',')` (:522). So use `odoo.tools.config['addons_path'].split(',')` or `odoo.addons.__path__` / `odoo.modules.module.get_module_path(name)` rather than treating it as a list.

### ORM: has_group

`self.env.user.has_group('module.xml_id')` -- odoo/addons/base/models/res_users.py:733-740 `@api.model def has_group(self, group_ext_id)` (delegates to ormcached `_has_group` :742-744, fully-qualified xmlid required). Also `self.env.is_admin()` / `is_system()` / `is_superuser()` used by core (ir_actions_report.py:889) and `_is_admin/_is_system/_is_superuser` on res.users (:800-810).

### ORM: res.users.share

Yes. odoo/addons/base/models/res_users.py:236-237 `share = fields.Boolean(compute='_compute_share', compute_sudo=True, string='Share User', store=True, ...)`, computed as `not user.has_group('base.group_user')` (:345-347). res.groups.share also exists (:104).

### ORM: _() usage

`from odoo import _` (odoo/__init__.py:127 `from odoo.tools.translate import _, _lt`). `_` is `GettextAlias()` (odoo/tools/translate.py:538) whose `__call__(self, source)` takes exactly ONE positional argument (:447-448) -- there is no `_('...%s', x)` / `_('...%(a)s', a=x)` form; passing extra args raises TypeError. The required form is `_('message %s') % value` (core: ir_ui_view.py:396 `_('Invalid view %s definition in %s') % (view_name, view.arch_fs)`; mail_template.py:456). Nothing deprecates/warns about `%`. `_lt` (lazy) exists at translate.py:485. JS side: `core._t` / `core._lt` from `web.core` (action_manager_report.js:15-16).

### Report model: name

ir.actions.report -- odoo/addons/base/models/ir_actions_report.py:83-89 `class IrActionsReport(models.Model): _name = 'ir.actions.report'; _inherit = 'ir.actions.actions'; _table = 'ir_act_report_xml'; _sequence = 'ir_actions_id_seq'`. (`ir.actions.report.xml` is gone; only the SQL table keeps the old name.)

### Report model: report_type values

ir_actions_report.py:97-105: `[('qweb-html','HTML'), ('qweb-pdf','PDF'), ('qweb-text','Text')]`, `required=True, default='qweb-pdf'`. Other fields: name (:91, translate), type Char default 'ir.actions.report' (:92), binding_type default 'report' (:93), model Char required (:94), model_id computed/searchable (:95), report_name Char required (:106), report_file (:108), groups_id (:110), multi (:111), paperformat_id (:113), print_report_name (:114), attachment_use (:116), attachment Char (:118).

### Report model: render dispatch

ir_actions_report.py:856-861: `def render(self, res_ids, data=None): report_type = self.report_type.lower().replace('-', '_'); render_func = getattr(self, 'render_' + report_type, None); if not render_func: return None; return render_func(res_ids, data=data)`. So the per-type method is PUBLIC, no underscore: name `render_pentaho` (from 'pentaho'), signature `def render_pentaho(self, res_ids, data=None)`, and it must return a 2-tuple `(content_bytes, format_str)` as the qweb ones do (`render_qweb_pdf` :715 returns `..., 'pdf'` at :780/:811/:813; `render_qweb_text` :815-820 returns `(text, 'text')`; `render_qweb_html` :823-830 returns `(html, 'html')`). Consumer that relies on this: addons/mail/models/mail_template.py:451-457 -- for non-qweb types it calls `report.render([res_id])` and raises `UserError('Unsupported report type %s found.')` if it returns falsy, then `result, format = res` and base64-encodes `result`; so implementing `render_pentaho` returning `(pdf_bytes, 'pdf')` makes email-template attachments work. Note the web download controller (addons/web/controllers/main.py:2027-2082) is hard-wired to qweb types (`if type in ['qweb-pdf','qweb-text']` :2039, else `return` :2072) -- a custom type needs its own route. `report_action(self, docids, data=None, config=True)` (:863-900) builds the client action dict with only context/data/type/report_name/report_type/report_file/name (:879-887) and, for admins without a document layout, redirects into `base.action_base_document_layout_configurator` with `close_on_report_download=True` (:889-897) -- pass `config=False` or set context `discard_logo_check` to avoid that for a Pentaho report. Lookup helper: `_get_report_from_name(report_name)` :489-500. Attachment helpers `retrieve_attachment(record)` :186-200 and `postprocess_pdf_report(record, buffer)` :202-226 are reusable for saving the PDF as an attachment.

### Report model: Binary attachment default

`fields.Binary` defaults to `attachment=True` (odoo/fields.py:1895-1905 `_slots = {'prefetch': False, 'depends_context': ('bin_size',), 'attachment': True}`; `column_type` is None when attachment, `bytea` otherwise :1908-1910; a non-stored Binary is forced to attachment=False :1912-1916). Attachment-backed values are read from ir.attachment rows with res_model/res_field/res_id (:2003-2016) and `bin_size` in context returns the human size instead of content (:1960-1967). Trap: `get_bindings` (ir_actions.py:87-118) does a full `action.read()[0]` WITHOUT bin_size and its result is embedded in every `load_views(toolbar=True)` payload (odoo/models.py:1570-1580), so a Binary field on ir.actions.report would ship the whole .prpt base64 with each form/list view load of the bound model; only `/web/action/load` sets `bin_size: True` (addons/web/controllers/main.py:1664-1665). Consider keeping the Binary on a separate model/attachment or overriding read/get_bindings.

### Report model: Print-menu binding

Inherited from ir.actions.actions (odoo/addons/base/models/ir_actions.py:35-40): `binding_model_id = fields.Many2one('ir.model', ondelete='cascade')`, `binding_type = fields.Selection([('action','Action'),('report','Report')], required=True, default='action')` (ir.actions.report overrides default to 'report' at ir_actions_report.py:93), `binding_view_types = fields.Char(default='list,form')`. `model` is a plain Char (model name) with computed `model_id` (:94-95). Helpers `create_action()` :159-164 sets `binding_model_id` from `model`, `unlink_action()` :166-170 clears it. In XML data: `<field name="binding_model_id" ref="module.model_xxx"/>` and `<field name="binding_type">report</field>`; there is NO `<report>` shortcut tag requirement and no `auto=False`/`menu` attributes are needed.

### Tests: TransactionCase conventions

odoo/tests/common.py: `TransactionCase(BaseCase)` :538-560 -- per-test transaction, ONLY `setUp(self)` defines `self.registry`, `self.cr`, `self.env` (:544-558); it has no setUpClass env, so class-level fixtures must go in `SavepointCase` (:595-620, subclass of `SingleTransactionCase` :571-592 whose `setUpClass(cls)` sets `cls.registry/cls.cr/cls.env` at :578-586 and each test runs inside a SAVEPOINT rolled back in cleanup :617-619). `SingleTransactionCase` also exists. Helpers: `self.ref(xid)` :343, `self.browse_ref(xid)` :354, `self.patch(obj, key, val)` :562, `self.uid` setter :337-340. `addClassCleanup` is backfilled for py<3.8 at :269. `Form` test helper at :1471. Default tags: 'standard' + module name, `at_install`/`post_install` are flags via `tagged` (:92-117).

### Tests: HttpCase

`HttpCase(TransactionCase)` odoo/tests/common.py:1208-1315: `registry_test_mode = True`; `setUp` (:1238-1251) enters registry test mode, creates a session in `odoo.http.root.session_store`, and `self.opener = requests.Session()` with the `session_id` cookie (:1249-1251). `url_open(self, url, data=None, files=None, timeout=10, headers=None)` (:1253-1258): flushes, prefixes `http://127.0.0.1:<http_port>`, POSTs when data/files given else GETs -- it has NO `json=` parameter. `authenticate(self, user, password)` (:1286-1315) logs the magic session in without a browser (`user=None` logs out). `logout()` :1282. To POST to a type='json' route use the requests session directly: `self.opener.post('http://%s:%s/pentaho/preview' % (HOST, odoo.tools.config['http_port']), json={'jsonrpc':'2.0','method':'call','id':None,'params': {...}})` (pattern from odoo/addons/base/tests/test_xmlrpc.py:55-66 and addons/account/tests/test_portal_attachment.py:79 `self.opener.post(url=remove_url, json={'params': remove_data})`); `HOST='127.0.0.1'` at :72. For the http download route, `self.url_open('/pentaho/download', data={'data': json.dumps(...), 'token': 'x', 'csrf_token': ...})` -- a POST to a csrf-protected http route needs a valid token (`request.csrf_token()`); simplest is to GET it (`self.url_open('/pentaho/download?...')`) or declare `csrf=False` on the route. `browser_js`/`start_tour` (:1316, :1372) need headless Chrome. HttpCase needs the HTTP server, which odoo.service.server starts in test mode even with `--stop-after-init` (odoo/service/server.py:464-465 `test_mode = config['test_enable'] or config['test_file']; if test_mode or (config['http_enable'] and not stop)`), and warns against `--workers` > 0 (:1240-1241).

### Tests: tagged

`from odoo.tests import tagged` (or `odoo.tests.common.tagged`) -- odoo/tests/common.py:2418-2432 `def tagged(*tags)`: adds/removes tags on the class `test_tags` set; '-' prefix removes (e.g. `@tagged('post_install', '-at_install')`). Tags are NOT inherited by subclasses (:2425). Selector syntax `[-][tag][/module][:class][.method]` in `TagsSelector` :2436-2470.

### Tests: run command

`/Volumes/Workspace/Development/OdooWorkbench/odoo13/venv/bin/python odoo-bin -c <conf> --addons-path=addons,../enterprise,<path-with-pentaho_reports> -d <fresh_db> -i pentaho_reports --test-enable --test-tags /pentaho_reports --stop-after-init --workers 0` . Flags from odoo/tools/config.py: `--test-enable` :165-167 (callback sets test_tags to '+standard' when unset, :399-401), `--test-tags` :168-175 (`[-][tag][/module][:class][.method]`, setting it enables tests; examples `:TestClass.test_func,/test_module`), `--test-file` :162-163, `--stop-after-init` :281, `--screenshots`/`--screencasts` :178-184. Odoo 13 has no `--without-demo=all` requirement for tests but you can add `--without-demo=all` if the tests don't need demo data. To rerun after install: `-u pentaho_reports --test-enable --test-tags /pentaho_reports --stop-after-init`.

### Other port tripwires

1) Everything client-side is legacy AMD (`odoo.define`, Widget/`include`, jQuery, underscore, Promise-based). No OWL action service, no registries for report handlers, no `@odoo-module`, no `useService`, no `download()` helper, no `web.assets_backend` manifest key: rewrite the JS as an `ActionManager.include` override of `_executeReportAction` and load it through a `views/assets.xml` template inheriting `web.assets_backend` (listed under the manifest `data` key). `session.get_file` always POSTs a FormData with `token` + `csrf_token` and expects a non-HTML 200 with a Content-Disposition header, so the download route must accept POST, take `token=None, **kw`, and return `application/pdf`.
2) Server-side JSON routes are `type='json'` (not 'jsonrpc'); the handler gets `params` as kwargs; `request.jsonrequest`/`request.params` exist; results are JSON-serialised (no bytes). `content_disposition(filename)` takes one argument. `make_response(data, headers=None, cookies=None)`.
3) Render dispatch is `render_<type>` WITHOUT leading underscore (`render_pentaho(self, res_ids, data=None)` returning `(bytes, 'pdf')`); the Odoo 19 `_render_pentaho` name would never be found (`render()` returns None -> mail templates raise 'Unsupported report type'). `report_action()` only forwards a fixed set of keys (no custom fields) and may redirect into the document-layout configurator for admins unless `config=False`/`discard_logo_check`.
4) `fields.Selection(selection_add=..., ondelete=...)`: `ondelete` is silently ignored in 13.0 -- remove it. Selection labels need the `(value, label)` tuple; singletons `(value,)` are only for reordering existing values.
5) Views: `attrs="{'invisible': [...], 'required': [...]}"` domain syntax only; a Python-expression `invisible="..."` is safe_eval'd at view-validation time and fails install with "Error while validating view". Anchor `position="after"` on `//field[@name='report_type']` in `base.act_report_xml_view` is valid; search view `base.act_report_xml_search_view` has `//field[@name='model']` and `//filter[@name='report_type']`.
6) `_()` takes a single string; use `_('...%s') % x` (no `_('...', x)` form in 13.0).
7) Python floor is 3.6 (setup.py:58): avoid walrus (3.8), positional-only params, `dict | dict`, f-string `=`, `functools.cached_property`, `str.removeprefix`, typing generics like `list[str]` at runtime. odoo.tools.config['addons_path'] is a comma-joined string; `odoo.conf.addons_paths` is the list.
8) Binary field on ir.actions.report defaults to attachment=True; `get_bindings()` reads full actions without bin_size into every `load_views(toolbar=True)` payload -- do not put large binaries directly on the action model, or guard with bin_size/override.
9) `ir.actions.actions.create` is already `@api.model_create_multi def create(self, vals_list)`; overriding with a single-dict `@api.model def create(self, vals)` signature would break multi-create callers. `write(self, vals)` unchanged. `cr.savepoint()` exists; exceptions UserError/ValidationError/AccessError in odoo/exceptions.py:33-116.
10) Tests: `TransactionCase` is setUp-only (use `SavepointCase` for setUpClass fixtures); `HttpCase.url_open` has no `json=` kwarg -- call `self.opener.post(..., json={...})`; `tagged` available; run with `--test-enable --test-tags /pentaho_reports --stop-after-init --workers 0`. ir.actions.report tree/form already expose report_type so a new selection value appears automatically in the filter group-by.
11) Core web `/report/download` (addons/web/controllers/main.py:2027-2082) returns None for non-qweb types, and the client's generic branch `console.error`s + rejects for unknown report_type -- so without the JS override the Print menu item for a 'pentaho' report silently does nothing.

---

## Odoo 14

### Python floor

setup.py:58 `python_requires='>=3.6'` (odoo/release.py:15 `version_info = (14, 0, 0, FINAL, 0, '')`). Checked from /Volumes/Workspace/Development/OdooWorkbench/odoo14/odoo.

### Report-action JS: mechanism

Legacy Widget-based ActionManager extended with `odoo.define` + `ActionManager.include({...})`. There is NO action service, NO `registry.category("ir.actions.report handlers")`, no `@web/core/...` modules, no `addons/web/static/src/webclient` or `core/network/download.js` directory (addons/web/static/src contains only css/ fonts/ img/ js/ scss/ xml/). Report actions are dispatched in addons/web/static/src/js/chrome/action_manager_report.js: `_handleAction` (line 160-165) routes `action.type === 'ir.actions.report'` to `_executeReportAction(action, options)` (line 103-131), which branches on `action.report_type` for 'qweb-html' / 'qweb-pdf' / 'qweb-text' and otherwise `console.error("The ActionManager can't handle reports of type " + action.report_type)` and `return Promise.reject()` (lines 126-130). No registry lookup anywhere: an unknown report_type is a hard rejection, so the addon MUST override `_executeReportAction` before the core else-branch runs.

### Report-action JS: evidence

addons/web/static/src/js/chrome/action_manager_report.js:1 (`odoo.define('web.ReportActionManager', ...)`), :9-12 (requires web.ActionManager, web.core, web.framework, web.session), :32 (`ActionManager.include({`), :45-73 (`_downloadReport` blocks UI + `session.get_file({url:'/report/download', data:{data: JSON.stringify([url, type]), context: JSON.stringify(session.user_context)}, success, error, complete: framework.unblockUI})`), :83-94 (`_triggerDownload` handles `action.close_on_report_download` and `options.on_close()`), :103-131 (`_executeReportAction` type switch + else reject), :160-165 (`_handleAction` override), :175-201 (`_makeReportUrls`). addons/web/static/src/js/chrome/action_manager.js:130-139 (`doAction` defaults `options.on_close` to a no-op so it is always callable), :659-677 (base `_handleAction` switch: act_url / act_window_close / client / server, default rejects), :781-795 (`_preprocessAction` evaluates `action.context` with pyUtils so `action.context.active_ids` is a plain array). In-tree precedent for exactly this pattern: ../enterprise/iot/static/src/js/action_manager.js:1-61 (`ActionManager.include({ _executeReportAction: function (action) { ... if (action.device_id) { return this._rpc({model:'ir.actions.report', method:'iot_render', args:[action.id, action.context.active_ids, action.data]}).then(...) } else { return this._super.apply(this, arguments); } } })`), registered through ../enterprise/iot/views/assets.xml:3-5 (`<template id="assets_backend" inherit_id="web.assets_backend"><xpath expr="script[last()]" position="after"><script type="text/javascript" src="/iot/static/src/js/action_manager.js"/>`).

### Report-action JS: how to intercept a custom report_type

Module to extend: `web.ActionManager` (class returned by `require('web.ActionManager')`), method `_executeReportAction(action, options)`; also `require('web.ReportActionManager')` so odoo.define ordering guarantees the core report include is applied BEFORE yours (addons/web/static/src/js/boot.js:143-153 + 251-275: factories run as soon as deps are in `services`, so an explicit dependency is the only hard ordering guarantee; if yours ran first, the core else-branch at action_manager_report.js:126-130 would reject without calling _super). Core behaviour for unknown type: console.error + Promise.reject (no fallthrough, no registry). The action dict reaching JS comes from /web/action/load (addons/web/controllers/main.py:1697-1722) which runs `clean_action` (main.py:326-350) and strips every field NOT in `ir.actions.report._get_readable_fields()` (odoo/addons/base/models/ir_actions_report.py:153-161 → report_name, report_type, target, context, data, close_on_report_download + base ir_actions.py:144-155 → id, name, type, display_name, help, xml_id, binding_*). So `action.id`, `action.report_type`, `action.report_name`, `action.context.active_ids`, `action.data` are available; any NEW custom field you want in the JS action dict needs an `_get_readable_fields` override. Exact shape to use (plain odoo.define, ES5/ES2015 but no import/export):

```js
odoo.define('pentaho_reports.ReportActionManager', function (require) {
"use strict";

var ActionManager = require('web.ActionManager');
require('web.ReportActionManager'); // make sure core report handling is included first
var core = require('web.core');
var framework = require('web.framework');
var session = require('web.session');

var _t = core._t;

ActionManager.include({
    /**
     * @override
     */
    _executeReportAction: function (action, options) {
        if (action.report_type !== 'pentaho') {
            return this._super.apply(this, arguments);
        }
        var self = this;
        var activeIds = (action.context && action.context.active_ids) || [];
        framework.blockUI();
        return this._rpc({
            model: 'ir.actions.report',
            method: 'render_report',          // your ORM method
            args: [[action.id], activeIds, action.data || {}],
            context: action.context,
        }).then(function (result) {
            // result is whatever render_report returns (e.g. {token: ..., filename: ...})
            return new Promise(function (resolve, reject) {
                var blocked = !session.get_file({
                    url: '/pentaho/download',  // MUST accept POST (get_file always POSTs FormData)
                    data: {
                        token: result.token,
                        context: JSON.stringify(session.user_context),
                    },
                    success: resolve,
                    error: function (error) {
                        self.call('crash_manager', 'rpc_error', error);
                        reject();
                    },
                    complete: framework.unblockUI,
                });
                if (blocked) {
                    self.displayNotification({
                        type: 'warning', title: _t('Warning'), sticky: true,
                        message: _t('A popup window with your report was blocked.'),
                    });
                }
            });
        }).then(function () {
            if (action.close_on_report_download) {
                return self.doAction({type: 'ir.actions.act_window_close'}, _.pick(options, 'on_close'));
            }
            return options.on_close();
        }).guardedCatch(function () {
            framework.unblockUI();
        });
    },
});

});
```

For the "print" variant, call `window.open('/pentaho/print?token=...')` (a GET, csrf-free) after the RPC instead of `session.get_file`. Register the file via an XML template inheriting `web.assets_backend` (see assets section).

### Download helper

`session.get_file(options)` from `require('web.session')` (addons/web/static/src/js/core/session.js:267-270 → delegates to `ajax.get_file`, addons/web/static/src/js/core/ajax.js:251-330). Behaviour: always `xhr.open('POST', options.url)` with a FormData built from `options.data` (ajax.js:259-263), appends `token='dummy-because-api-expects-one'` (line 265) and `csrf_token` (line 266-268) → so the server route must accept POST, must tolerate extra kwargs `token`/`csrf_token` (signature `def download(self, token=None, **kw)` or `csrf=False`), and is CSRF-checked by default (odoo/http.py:779-782). `xhr.responseType='blob'`; on status 200 and mimetype !== 'text/html' it parses `Content-Disposition` via `contentdisposition.parse(header).parameters.filename` and calls `download(blob, filename, mimetype)` (ajax.js:275-287), then `options.success()`. A 200 text/html or non-200 reply is treated as an error; the body is parsed for a JSON-serialized Odoo exception (ajax.js:290-314) — mimic addons/web/controllers/main.py:2127-2134 (`request.make_response(html_escape(json.dumps(error)))` wrapped in `werkzeug.exceptions.InternalServerError(response=res)`) to get proper error dialogs. `options.complete` → `xhr.onloadend` (ajax.js:324-326). Returns `true` synchronously (line 329); core checks `!session.get_file(...)` for popup-blocked legacy semantics (action_manager_report.js:50,63-71). There is no `@web/core/network/download` and no `framework.download`.

### Block UI

`var framework = require('web.framework'); framework.blockUI(); framework.unblockUI();` — defined in addons/web/static/src/js/core/misc.js:1 (`odoo.define('web.framework', ...)`), :82-97 (wrap `$.blockUI` / `$.unblockUI` with the spinner template, lines 49-53), exported at :235-236. Used exactly this way in action_manager_report.js:47 and :61.

### Notification

From any Widget/ActionManager (ServicesMixin): `this.displayNotification({type: 'info'|'success'|'warning'|'danger', title, message, subtitle, sticky, className})` → `this.call('notification', 'notify', options)` (addons/web/static/src/js/core/service_mixins.js:237-249). Legacy shortcuts still present but marked @deprecated: `this.do_notify(title, message, sticky, className)` (type 'warning', :251-263) and `this.do_warn(title, message, sticky, className)` (type 'danger', :265-278). The service itself: addons/web/static/src/js/services/notification_service.js:78-87 `notify(params)` (params documented :58-77, incl. `buttons`, `onClose`). Server errors from RPC: `this.call('crash_manager', 'rpc_error', error)` (addons/web/static/src/js/services/crash_manager.js:216). No `useService('notification')` / `env.services.notification.add` in this version.

### ES module (`/** @odoo-module **/`) supported

False

### Assets

Manifest `assets` key is NOT supported: odoo/modules/module.py:304-336 (`load_information_from_description_file`) only defaults `depends data demo test init_xml update_xml demo_xml` (line 331-333) + metadata (311-330); `grep` for `['assets']`/`get('assets')` across odoo/, addons/web/, addons/base/ finds no consumer, so an `'assets': {...}` key is silently ignored. Register JS/CSS by an XML template inheriting `web.assets_backend` (defined in addons/web/views/webclient_templates.xml:190) listed under the manifest `data` key, e.g. ../enterprise/iot/views/assets.xml:3-5: `<template id="assets_backend" inherit_id="web.assets_backend" name="..."><xpath expr="script[last()]" position="after"><script type="text/javascript" src="/pentaho_reports/static/src/js/action_manager.js"/></xpath></template>` (referenced from ../enterprise/iot/__manifest__.py:18 `'views/assets.xml'` in `data`). QWeb XML templates go under the manifest `qweb` key (addons/web/controllers/main.py:589 `manifest_glob('qweb', ...)`). ES-module syntax: no transpiler exists (no 'transpile'/'odoo-module' handling anywhere in odoo/ or addons/web python; addons/web/static/src/js/libs/popper.js:1 has a `/** @odoo-module **/` comment but it is inert — the file has no import/export). `import`/`export` statements would be a SyntaxError in the bundle. Use `odoo.define('name', function (require) {...})`.

### Views: conditional attribute syntax

Odoo 14 uses `attrs="{'invisible': [('report_type','!=','pentaho')], 'required': [('report_type','=','pentaho')]}"` domains. The plain `invisible="report_type != 'pentaho'"` python-expression form is REJECTED: odoo/addons/base/models/ir_ui_view.py:75-77 (`transfer_node_to_modifiers`) does `safe_eval(node.get('invisible'), {'context': context or {}})` for invisible/readonly/required, so only constant expressions (`1`, `0`, `context.get(...)`) are valid; a field name raises `ValueError: <class 'NameError'>: "name 'report_type' is not defined" while evaluating` (verified with the venv python: odoo/tools/safe_eval.py:346-347 wraps it), which `_check_xml` (ir_ui_view.py:387-420, via `postprocess_and_fields(validate=True)` → `_postprocess_view` → line 966) converts into `ValidationError('Error while validating view')` at module install. attrs domains are parsed with `ast.literal_eval` (ir_ui_view.py:64-66) and their field names validated by `_validate_attrs` (ir_ui_view.py:1296-1316, `_get_client_domain_variables` → `name_manager.must_have_fields`), so every field referenced in attrs (report_type) must be present in the form — it is (line 22 of the core form).

### Views: report form xmlid

`base.act_report_xml_view` — odoo/addons/base/views/ir_actions_views.xml:51-96 (`<record id="act_report_xml_view" model="ir.ui.view">`, model ir.actions.report). It contains `<field name="report_type"/>` at line 72 inside `<group><group>` (after `name`, before `paperformat_id` which has `attrs="{'invisible':[('report_type','not in',['qweb-pdf'])]}"`), so `<xpath expr="//field[@name='report_type']" position="after">` (or `<field name="report_type" position="after">`) is a valid anchor. Other anchors: `<field name="report_name"/>` (line 78), `<page name="advanced">` (line 86) with `attachment_use`/`attachment` (88-89), `<div class="oe_button_box" name="button_box">` (line 58). Note the `associated_view` button (line 65-67) hides itself for non-qweb types via attrs.

`report_type` field present in form: True

### Views: report search xmlid

`base.act_report_xml_search_view` — odoo/addons/base/views/ir_actions_views.xml:111-126 (`<search string="Report Xml">` with `<field name="name" .../>` line 116, `<field name="model" .../>` line 119, `<group expand="0" string="Group By" colspan="4">` line 120 containing `<filter name="report_type">` line 121 and `<filter name="report_model">` line 122). Tree view: `base.act_report_xml_view_tree` (line 97). Action: `base.ir_action_report` (line 127).

### Routes: JSON route type

`type='json'` — odoo/http.py:444-454 route() docstring: "The type of request, can be 'http' or 'json'". JsonRequest class odoo/http.py:565-604 (`_request_type = "json"`, line 604); request class selected by mimetype `application/json` / `application/json-rpc` (http.py:1413-1418). A mismatch between route type and request type raises BadRequest (http.py:322-327).

### Routes: is type='json' still accepted

Not applicable: there is no 'jsonrpc' route type in this version (grep 'jsonrpc' in odoo/http.py only hits docstrings/response envelope, lines 567-598, 631). `type='json'` is the one and only canonical JSON-RPC type; `type='jsonrpc'` would be stored in routing['type'] and then never match `_request_type` ('json' or 'http'), so every call would fail the check at http.py:322-327 with BadRequest.

### Routes: content_disposition

`from odoo.http import content_disposition` — odoo/http.py:1688-1692: `def content_disposition(filename): filename = odoo.tools.ustr(filename); escaped = urls.url_quote(filename, safe=''); return "attachment; filename*=UTF-8''%s" % escaped`. Single positional arg, no `disposition_type` kwarg. Used e.g. in addons/web/controllers/main.py:43 (import) and :2125 (`response.headers.add('Content-Disposition', content_disposition(filename))`).

### Routes: request.make_response

`request.make_response(data, headers=None, cookies=None)` — odoo/http.py:818-837: builds `Response(data, headers=headers)` and iterates `cookies.items()` calling `response.set_cookie(k, v)`. `headers` is a list of `(name, value)` tuples (docstring :829-830). Example PDF download pattern: addons/web/controllers/main.py:2083-2134 (`@http.route(['/report/download'], type='http', auth="user")`, `def report_download(self, data, token, context=None)`, sets `Content-Disposition` and `response.set_cookie('fileToken', token)`). Errors are serialized with `odoo.http.serialize_exception` and returned as `InternalServerError(response=request.make_response(html_escape(json.dumps(error))))` (:2127-2134) so ajax.get_file can show them.

### Routes: JSON request shape

JsonRequest.__init__ (odoo/http.py:606-627): reads the raw body, `self.jsonrequest = json.loads(request)` (:620), `self.params = dict(self.jsonrequest.get("params", {}))` (:626) and pops `context` from params into `self.context` (:627). dispatch() calls `self._call_function(**self.params)` (:697) so the handler receives the JSON-RPC `params` dict as kwargs (`def preview(self, report_id, **kw)`); `request.jsonrequest` and `request.params` are both available. The return value is wrapped by `_json_response` (:629-645) into `{'jsonrpc': '2.0', 'id': <req id>, 'result': <value>}` with mime application/json (:639). Exceptions become `{'jsonrpc':'2.0','id':..,'error':{code:200,message:'Odoo Server Error',data:serialize_exception(e)}}` (see docstring :584-601 and serialize_exception :725-732). JSON routes are NOT CSRF-checked (CSRF only in HttpRequest.dispatch, :779-782). For type='http': `HttpRequest.__init__` merges `httprequest.args` + `form` + `files` into `self.params` (:745-750), pops `session_id`, and POST/PUT/DELETE requests require a `csrf_token` param unless `csrf=False` (:779-782); `methods=` restricts verbs (route docstring :465-466, default all).

### ORM: create decorator

Yes: `@api.model_create_multi` exists — odoo/api.py:356-366 (`def model_create_multi(method)`, sets `wrapper._api = 'model_create'`); `model_create_single` also exists (:336-345). The base class already uses it: odoo/addons/base/models/ir_actions.py:46-50 `@api.model_create_multi def create(self, vals_list)` on ir.actions.actions (and :53-57 `def write(self, vals)`), so an override on ir.actions.report should be `@api.model_create_multi def create(self, vals_list): ... return super().create(vals_list)`. ir_actions_report.py itself defines no create/write (only `create_action`/`unlink_action` :176-187).

### ORM: selection_add / ondelete

Supported AND required here. odoo/fields.py:2323-2365 processes `selection_add`; `ondelete = field.args.get('ondelete') or {}` (:2332), new values default to 'set null' (:2333-2335), and because `ir.actions.report.report_type` is `required=True` (odoo/addons/base/models/ir_actions_report.py:104-107, default 'qweb-pdf') the check at fields.py:2336-2344 raises `ValueError("required selection fields must define an ondelete policy ...")` if any added value is left at 'set null'. Valid policies (:2347-2361): 'cascade', 'set default' (allowed since the field has a default), or a single-argument callable. So write: `report_type = fields.Selection(selection_add=[('pentaho', 'Pentaho')], ondelete={'pentaho': 'set default'})` (or 'cascade'). `selection_add` must be a list (:2327-2328) and the base selection must be a list (:2329-2330).

### ORM: cr.savepoint()

Yes: `with self.env.cr.savepoint(): ...` — odoo/sql_db.py:113-135 `@contextmanager @check def savepoint(self, flush=True)`: issues `SAVEPOINT "<uuid>"`, flushes the env before/after when flush=True, `ROLLBACK TO SAVEPOINT` on exception (re-raised) and `RELEASE SAVEPOINT` on success.

### ORM: config['addons_path'] type

`odoo.tools.config['addons_path']` is a STRING (comma-separated): odoo/tools/config.py:493-505 (`self.options['addons_path'] = ','.join(default_addons)` / `",".join(self._normalize(x) for x in ...split(','))`). The list form is `odoo.tools.config.addons_paths` (config.py:536 `conf.addons_paths = self.options['addons_path'].split(',')`). Use `config['addons_path'].split(',')` or `config.addons_paths`.

### ORM: has_group

`self.env.user.has_group('module.group_xmlid')` — odoo/addons/base/models/res_users.py:813-818 `def has_group(self, group_ext_id)` (delegates to ormcached `_has_group`, :820-822). Also `self.user_has_groups('base.group_system,!base.group_portal')` on any model — odoo/models.py:1364-1372 (comma-separated, `!` negation).

### ORM: res.users.share

Yes: odoo/addons/base/models/res_users.py:307-308 `share = fields.Boolean(compute='_compute_share', compute_sudo=True, string='Share User', store=True, ...)`; res.groups also has `share` (:158).

### ORM: _() usage

`from odoo import _` (odoo/__init__.py:127 `from odoo.tools.translate import _, _lt`). `_` is a `GettextAlias` instance (odoo/tools/translate.py:375, :563). Its `__call__(self, source, *args, **kwargs)` (:451-461) supports the NEW interpolation form `_('Hello %s', name)` / `_('%(x)s', x=...)` — it applies `translation % (args or kwargs)` and falls back to `source % ...` with `_logger.exception('Bad translation ...')` on failure. The OLD form `_('Hello %s') % name` still works with NO deprecation warning anywhere in translate.py (no warnings.warn / logger on `%`); core itself still uses it (translate.py:302, :722). `_lt` lazy variant also exists (:499-560).  No `odoo.tools.translate.LazyTranslate`/`_lt` module-level factory pattern beyond `_lt`.

### Report model: name

`ir.actions.report` — odoo/addons/base/models/ir_actions_report.py:88-96 (`class IrActionsReport(models.Model): _name = 'ir.actions.report'; _inherit = 'ir.actions.actions'; _table = 'ir_act_report_xml'`). `ir.actions.report.xml` does not exist in this version (only the SQL table keeps the old name).

### Report model: report_type values

odoo/addons/base/models/ir_actions_report.py:104-112: `[('qweb-html', 'HTML'), ('qweb-pdf', 'PDF'), ('qweb-text', 'Text')]`, `required=True, default='qweb-pdf'`. Other fields for context: `report_name` Char required (:113), `report_file` Char (:114-115), `groups_id` M2M (:116), `multi` Boolean (:117), `paperformat_id` (:119), `print_report_name` (:120-121), `attachment_use` (:122), `attachment` (:124).

### Report model: render dispatch

Generic dispatch is `_render(self, res_ids, data=None)` at odoo/addons/base/models/ir_actions_report.py:964-969: `report_type = self.report_type.lower().replace('-', '_'); render_func = getattr(self, '_render_' + report_type, None); if not render_func: return None; return render_func(res_ids, data=data)`. So for report_type 'pentaho' define `def _render_pentaho(self, res_ids, data=None)` returning a 2-tuple `(bytes_content, 'pdf')` — the contract shown by the siblings `_render_qweb_pdf(self, res_ids=None, data=None)` (:818), `_render_qweb_text(self, docids, data=None)` → `return ..., 'text'` (:921-927), `_render_qweb_html(self, docids, data=None)` → `return ..., 'html'` (:929-936). Callers of the generic path: addons/mail/models/mail_template.py:213-219 (`if report.report_type in ['qweb-html','qweb-pdf']: result, format = report._render_qweb_pdf([res_id]) else: res = report._render([res_id]); if not res: raise UserError(_('Unsupported report type %s found.', ...)); result, format = res`). The HTTP controllers do NOT use `_render`: addons/web/controllers/main.py:2019-2046 `report_routes` hard-codes converter html/pdf/text and raises 'Converter %s not implemented.' otherwise, and `/report/download` (:2083-2126) only handles 'qweb-pdf'/'qweb-text' and returns None for anything else — hence the need for a custom /pentaho/download route. Underscore-prefixed (`_render_*`) is the convention; public `render_*` methods do not exist. `report_action(self, docids, data=None, config=True)` (:971-1010) builds the JS action dict (no `id` key! keys: context, data, type, report_name, report_type, report_file, name, optional close_on_report_download), so if your JS relies on `action.id`, go through the Print menu / `/web/action/load` or override `report_action` to add `'id': self.id` (and add 'id' is already in `_get_readable_fields`). `_get_report_from_name(report_name)` at :511-518. `_get_readable_fields` at :153-161 controls which fields survive `clean_action`; add custom fields there if the JS needs them.

### Report model: Binary attachment default

`fields.Binary` defaults to `attachment = True` (odoo/fields.py:1976), `prefetch = False` (:1974), `_depends_context = ('bin_size',)` (:1975). So `pentaho_file = fields.Binary()` is stored as an ir.attachment unless `attachment=False` is passed. Note addons/web/controllers/main.py:1710-1712: /web/action/load sets `bin_size: True` in the context for ir.actions.report, so Binary fields read through the action loader come back as human sizes, never content.

### Report model: Print-menu binding

Inherited from ir.actions.actions (odoo/addons/base/models/ir_actions.py:34-39): `binding_model_id = fields.Many2one('ir.model', ondelete='cascade', ...)`, `binding_type = fields.Selection([('action','Action'),('report','Report')], default='action', required=True)`, `binding_view_types = fields.Char(default='list,form')`. ir.actions.report overrides `binding_type` default to 'report' (ir_actions_report.py:100) and has `model = fields.Char(required=True, string='Model Name')` (:101) plus computed `model_id` (:102). Helpers `create_action()` (:176-181 sets binding_model_id from `model`) / `unlink_action()` (:183-187). Print-menu bindings are collected by `ir.actions.actions.get_bindings(model_name)` (ir_actions.py:86-125; filters on `groups_id`), which is what `fields_view_get(toolbar=True)` uses (odoo/models.py:1634-1648). In XML data use `<field name="binding_model_id" ref="model_xxx"/>` + `<field name="binding_type">report</field>` (the `<report>` shortcut tag also still exists in this version).

### Tests: TransactionCase conventions

odoo/tests/common.py: `TransactionCase(BaseCase)` (:687-717) is per-test transaction with an instance `setUp(self)` that creates `self.cr`, `self.env` (SUPERUSER) and `self.registry`; it has NO `setUpClass` env — `cls.env` does not exist in TransactionCase in 14 (class-level data must go in `SavepointCase`). `SingleTransactionCase` (:720-742) and `SavepointCase(SingleTransactionCase)` (:745-782) define `setUpClass(cls)` with `cls.cr`/`cls.env` and per-test savepoint rollback; `HttpSavepointCase` (:1577). Convention in this version: `def setUp(self): super().setUp(); ...` for TransactionCase; `@classmethod def setUpClass(cls): super().setUpClass(); ...` for SavepointCase. `self.patch(obj, key, val)` helper (:709-713). Test files are discovered from `<module>/tests/__init__.py`, names starting with `test_` (odoo/tests/loader.py:16-46).

### Tests: HttpCase

`HttpCase(HttpCaseCommon, TransactionCase)` (odoo/tests/common.py:1571-1574). `setUp` enters registry test mode so HTTP threads share the test cursor (:1400-1406) and creates `self.opener = requests.Session()`. `self.authenticate(user, password)` (:1454-1492) creates a server session and sets the `session_id` cookie on `self.opener`; returns the session. `self.url_open(url, data=None, files=None, timeout=10, headers=None, allow_redirects=True)` (:1421-1427): flushes, prefixes relative urls with `http://<HOST>:<http_port>`, POSTs when data/files given else GETs. It has NO `json=` parameter, so to POST to a `type='json'` route in tests use the underlying requests session: `self.opener.post('http://%s:%s/pentaho/preview' % (HOST, odoo.tools.config['http_port']), json={'params': {...}})` (precedent: addons/survey/tests/common.py:167 `self.opener.post(url=url, json={'params': post_data})`; addons/account/tests/test_portal_attachment.py:100-108 asserting on `res.text`/`res.json()`), `base_url` can be read from `ir.config_parameter` `web.base.url` (survey/tests/common.py:160). JSON routes skip CSRF; for a CSRF-protected `type='http'` POST in tests either declare `csrf=False` or pass `csrf_token` like addons/account/tests/test_portal_attachment.py:44 (`'csrf_token': http.WebRequest.csrf_token(self)`). Tests also get `self.xmlrpc_*` proxies (:1389-1396) and `browser_js`/`start_tour` (:1494, :1556).

### Tests: tagged

`from odoo.tests import tagged` (odoo/tests/__init__.py:2 re-exports common.*; `def tagged(*tags)` at odoo/tests/common.py:2598-2616). All BaseCase classes default to tags `standard` + `at_install`; use `@tagged('post_install', '-at_install')` for HttpCase tests; tags are NOT inherited by subclasses (docstring :2604-2605).

### Tests: run command

`/Volumes/Workspace/Development/OdooWorkbench/odoo14/venv/bin/python /Volumes/Workspace/Development/OdooWorkbench/odoo14/odoo/odoo-bin -d <fresh_db> --addons-path=<paths incl. addons,../enterprise,<your addon dir>> -i pentaho_reports --test-enable --test-tags /pentaho_reports --stop-after-init` (optionally `--http-port` for HttpCase). Flags from odoo/tools/config.py: `-i/--init` (:108), `-u/--update` (:109), `-d/--database` (:233), `--test-enable` (:162-164, sets test_tags to '+standard' if none, :594-596), `--test-tags` spec `[-][tag][/module][:class][.method]` (:165-183, e.g. `--test-tags /pentaho_reports,:TestPentahoHttp.test_download`; setting it also enables tests), `--test-file` (:160), `--stop-after-init` (:287). Note `tools.config['test_enable']` makes `_render_qweb_pdf` fall back to HTML unless `force_report_rendering` is in context (ir_actions_report.py:829-830) — irrelevant for a custom `_render_pentaho` but worth knowing when asserting on core reports.

### Other port tripwires

Port tripwires for a custom report-type addon on 14.0 (all cited from /Volumes/Workspace/Development/OdooWorkbench/odoo14/odoo):
1. JS: no OWL action service, no registries, no `@odoo-module`/ES imports, no `@web/core/network/download`, no `useService`. Everything is `odoo.define` + `ActionManager.include` overriding `_executeReportAction` (addons/web/static/src/js/chrome/action_manager_report.js:103-131); unknown report_type = console.error + Promise.reject, never a fallthrough. Require 'web.ReportActionManager' in your define to pin ordering.
2. `session.get_file` always POSTs FormData and injects `token` + `csrf_token` fields (addons/web/static/src/js/core/ajax.js:259-268): your `/pentaho/download` route must be `type='http'`, allow POST, tolerate `token`/`csrf_token`/`context` kwargs (use `**kw`), and either keep CSRF (the token is sent) or set `csrf=False`. A 200 with mimetype text/html is treated as an error by get_file (ajax.js:277); return errors as InternalServerError wrapping `html_escape(json.dumps({'code':200,'message':'Odoo Server Error','data':serialize_exception(e)}))` like addons/web/controllers/main.py:2127-2134 so the crash manager can render them.
3. Action dict sanitation: `/web/action/load` → `clean_action` (addons/web/controllers/main.py:326-350) drops every ir.actions.report field not in `_get_readable_fields()` (odoo/addons/base/models/ir_actions_report.py:153-161) and logs a warning for non-field custom keys. `report_action()` (:971-1010) does not put `id` in the dict. Override `_get_readable_fields` (and/or `report_action`) if the JS needs more than id/report_type/report_name/context/data.
4. `report_type` is `required=True` on the base field (ir_actions_report.py:104-107), so `selection_add` MUST carry `ondelete={'pentaho': 'set default'|'cascade'|callable}` or registry load fails with ValueError (odoo/fields.py:2336-2344).
5. Views: python-expression `invisible="..."` is evaluated with safe_eval against `{'context': ...}` only (ir_ui_view.py:75-77) → ValidationError at install; use `attrs="{'invisible': [...], 'required': [...]}"` domains. Anchor: `base.act_report_xml_view` has `<field name="report_type"/>` (ir_actions_views.xml:72); search view `base.act_report_xml_search_view` (:111).
6. Controllers: route types are only 'http' and 'json' (odoo/http.py:444-454); JSON handlers get `params` as kwargs (http.py:626, :697); `request.make_response(data, headers=None, cookies=None)` (http.py:818); `content_disposition(filename)` single-arg returning `attachment; filename*=UTF-8''...` (http.py:1688-1692). `request.env`, `request.context`, `request.session.uid` all exist; `request.update_env` does not.
7. Manifest: no `assets` key (odoo/modules/module.py:304-336) — use an XML `<template inherit_id="web.assets_backend">` in `data` (pattern: ../enterprise/iot/views/assets.xml). QWeb client templates go under the `qweb` manifest key.
8. Generic render dispatch is `_render(res_ids, data)` → `getattr(self, '_render_' + report_type.replace('-', '_'))` (ir_actions_report.py:964-969) expecting `(content, extension)`; the web `/report/<converter>/...` and `/report/download` controllers hard-code qweb converters (addons/web/controllers/main.py:2034-2046, 2096-2126) and will not serve a pentaho type — keep your own routes. mail.template goes through `_render` for non-qweb types (addons/mail/models/mail_template.py:213-219), so `_render_pentaho` gives email-attachment support for free.
9. Python: `python_requires='>=3.6'` (setup.py:58) — avoid walrus, `dict | dict`, positional-only params, `str.removeprefix`, `functools.cache`. `_('%s', x)` and `_('%s') % x` both work without warnings (odoo/tools/translate.py:451-461). `config['addons_path']` is a comma-joined str (config.py:501-505); `config.addons_paths` is the list (:536). `cr.savepoint()` exists (sql_db.py:113-135). `@api.model_create_multi` exists and is already used by ir.actions.actions.create (ir_actions.py:46-50), which also calls `self.clear_caches()` in create/write — call super so bindings cache is invalidated.
10. Tests: `TransactionCase` has no class-level env (use `SavepointCase`/`HttpSavepointCase` for setUpClass data); `HttpCase.url_open` has no `json=` kwarg — POST JSON with `self.opener.post(url, json={'params': {...}})`; `authenticate(user, password)` sets the cookie on `self.opener`; tests run with `--test-enable --test-tags /pentaho_reports --stop-after-init`. `tools.config['test_enable']` makes core qweb-pdf rendering fall back to HTML unless `force_report_rendering` is in context (ir_actions_report.py:829-830).
11. Enterprise precedent worth copying verbatim for shape: ../enterprise/iot/static/src/js/action_manager.js (`_executeReportAction` override calling `this._rpc({model:'ir.actions.report', method:..., args:[action.id, action.context.active_ids, action.data]})`, then `options.on_close`, `do_notify`/`do_warn`).

---

## Odoo 15

### Python floor

setup.py:58 `python_requires='>=3.7'` (odoo/release.py:15 `version_info = (15, 0, 0, FINAL, 0, '')`)

### Report-action JS: mechanism

NEW OWL action service (ES-module, `@odoo-module`), NOT the legacy odoo.define ActionManager. `addons/web/static/src/webclient/actions/action_service.js` has `_executeReportAction(action, options)` (line 1030) which FIRST iterates `registry.category("ir.actions.report handlers").getAll()` (line 1031-1037) calling each `handler(action, options, env)` and returning the first truthy result; only then does it dispatch built-in qweb-html / qweb-pdf / qweb-text. There is no legacy `action_manager*.js` under addons/web/static/src/legacy/js/chrome (only abstract_action.js, action_mixin.js exist). The registry category name is exactly the string with a space: "ir.actions.report handlers".

### Report-action JS: evidence

addons/web/static/src/webclient/actions/action_service.js:1 (`/** @odoo-module **/`), :6 (`import { download } from "@web/core/network/download"`), :8 (`import { registry } from "@web/core/registry"`), :974-994 (`_triggerDownload`: `env.services.ui.block()` / `download({url:"/report/download", data:{...}})` / `env.services.ui.unblock()` / close_on_report_download handling), :1030-1068 (`_executeReportAction`; unknown type -> `console.error("The ActionManager can't handle reports of type ...")` at :1063-1066 — NO exception, NO notification, silent fallthrough returning undefined), :1134-1135 (`case "ir.actions.report": return _executeReportAction(action, options)`), :1403 (service dependencies: effect, localization, notification, router, rpc, ui, user), :1409 (`registry.category("services").add("action", actionService)`). In-tree exemplar of a custom handler: ../enterprise/iot/static/src/js/iot_report_action.js:24-51 (`async function iotReportActionHandler(action, options, env)` using `env.services.orm.call("ir.actions.report", "iot_render", args)`, `env.services.notification.add(...)`, `env.services.action.doAction({type:"ir.actions.act_window_close"},{onClose})`, `return true`, then `registry.category("ir.actions.report handlers").add("iot_report_action_handler", iotReportActionHandler)`; its manifest ../enterprise/iot/__manifest__.py:28-30 declares `'web.assets_backend': ['iot/static/src/**/*']`). Registry API: addons/web/static/src/core/registry.js:51 `add(key, value, { force, sequence } = {})` (default sequence 50, :60), :97 `getAll()` returns values ordered by sequence. Server side: the action dict reaching JS is filtered by `_get_readable_fields()` — odoo/addons/base/models/ir_actions.py:159-169 (base set) and odoo/addons/base/models/ir_actions_report.py:151-160 (adds report_name, report_type, target, context, data, close_on_report_download); addons/web/controllers/main.py:232-248 `clean_action` drops any real model field not in that set (custom-property keys that are NOT model fields pass through), and /web/action/load (main.py:1581-1607) reads the report with `bin_size=True` (:1598-1599).

### Report-action JS: how to intercept a custom report_type

Create `pentaho_reports/static/src/js/pentaho_report_action.js` and list it in the manifest under `'assets': {'web.assets_backend': ['pentaho_reports/static/src/js/**/*']}`. Exact shape for this version:

```js
/** @odoo-module **/
import { registry } from "@web/core/registry";
import { download } from "@web/core/network/download";

async function pentahoReportHandler(action, options, env) {
    if (action.report_type !== "pentaho") {
        return false;            // falsy -> core keeps looking / falls through to qweb handling
    }
    const orm = env.services.orm;          // env.services.orm.call(model, method, args, kwargs)
    const ctx = action.context || {};
    env.services.ui.block();               // addons/web/static/src/core/ui/ui_service.js:47-66
    try {
        const res = await orm.call("ir.actions.report", "render_report", [
            action.id, ctx.active_ids || [], action.data || {},
        ], { context: ctx });
        // download() POSTs a FormData (adds `token` + `csrf_token` automatically) and reads
        // Content-Disposition for the filename: addons/web/static/src/core/network/download.js:455-541
        await download({
            url: "/pentaho/download",
            data: { token: res.token, context: JSON.stringify(env.services.user.context) },
        });
        env.services.notification.add(env._t("Report generated"), { type: "success" });
    } catch (e) {
        env.services.notification.add(String(e.message || e), { title: env._t("Pentaho"), type: "danger", sticky: true });
        throw e;
    } finally {
        env.services.ui.unblock();
    }
    const onClose = options.onClose;
    if (action.close_on_report_download) {
        return env.services.action.doAction({ type: "ir.actions.act_window_close" }, { onClose });
    } else if (onClose) {
        onClose();
    }
    return true;                             // truthy -> _executeReportAction returns here (action_service.js:1033-1036)
}

registry.category("ir.actions.report handlers").add("pentaho_report_handler", pentahoReportHandler);
```

Notes: (a) the handler runs BEFORE any report_type switch, so it also sees qweb reports — guard on `action.report_type === "pentaho"`; (b) `action.id`, `action.report_name`, `action.report_type`, `action.context`, `action.data`, `action.close_on_report_download` are available; any extra ir.actions.report field the JS wants (e.g. pentaho_filename) must be added via `def _get_readable_fields(self): return super()._get_readable_fields() | {"pentaho_filename"}` in the Python model or `clean_action` strips it (main.py:238-246); (c) if no handler returns truthy for report_type 'pentaho', core only does `console.error(...)` (action_service.js:1063-1066) — nothing is shown to the user; (d) for a `/pentaho/print` variant use `env.services.rpc("/pentaho/print", params)` (rpc service returns `rpc(route, params={}, settings)`; addons/web/static/src/core/network/rpc_service.js:126-133) or `browser.open`; (e) legacy `odoo.define('...', function(require){...})` modules still load in v15 (e.g. addons/web/static/src/legacy/js/report/client_action.js:1) but cannot reach the new registry without `@web/core/registry`, so use the ES-module form.

### Download helper

`import { download } from "@web/core/network/download"` (addons/web/static/src/core/network/download.js:455 `export function download(options)`; implementation :459-541). Options: `{url, data}` -> `xhr.open("POST", options.url)` with a FormData built from `options.data` entries (:466-473), or `{form}` to post an existing form element (:462-465). It always appends `token="dummy-because-api-expects-one"` and `csrf_token=odoo.csrf_token` (:474-477), so an `auth='user' type='http'` route with default CSRF passes; the route should accept `**kw` (or it logs 'called ignoring args' per odoo/http.py:535-545). On 200 with mimetype != text/html it parses the `Content-Disposition` header for the filename (:484-494) and saves the blob; a text/html body is treated as a serialized Python error and rejected via `makeErrorFromResponse` (:500-530). Legacy equivalent still present: addons/web/static/src/legacy/js/core/session.js:252-255 `get_file(options)` -> `ajax.get_file` (addons/web/static/src/legacy/js/core/ajax.js:574), only for odoo.define code.

### Block UI

`env.services.ui.block()` / `env.services.ui.unblock()` — addons/web/static/src/core/ui/ui_service.js:38-74 (ref-counted: blockCount, warning if unblock called more than block, :53-60). Exactly how core wraps report download: action_service.js:976-985 (`env.services.ui.block(); try { await download(...) } finally { env.services.ui.unblock(); }`). In a component use `useService("ui")` from `@web/core/utils/hooks`.

### Notification

`env.services.notification.add(message, options)` — addons/web/static/src/core/notifications/notification_service.js:42-59; options typedef :18-25: `{ title?, type?: "warning"|"danger"|"success"|"info", sticky?: boolean (default false, auto-close), className?, onClose?, buttons?: [{name, icon?, primary?, onClick}] }`; returns a close function. Registered as service "notification" (:73). Translation: `env._t(...)` (action_service.js:244) or `import { _t, _lt } from "@web/core/l10n/translation"` (translation.js:16, :40).

### ES module (`/** @odoo-module **/`) supported

True

### Assets

Manifest `assets` key. odoo/addons/base/models/ir_asset.py:211-219 `_get_asset_paths` reads `manifest.get('assets', {})` and for each bundle processes the commands (plain path/glob string, or ('include'|'prepend'|'before'|'after'|'remove'|'replace', ...) tuples); `ir.asset` DB records (fields bundle/directive/path/target, ir_asset.py:80-90) are processed before (sequence < default) and after. 174 core manifests use it, e.g. addons/iap/__manifest__.py:23-29 `'assets': {'web.assets_backend': ['iap/static/src/js/**/*'], 'web.tests_assets': [...]}`; bundle names defined in addons/web/__manifest__.py:85 (`'web.assets_backend'`). The OLD XML form `<template id="..." inherit_id="web.assets_backend">` is NOT usable: no `web.assets_backend` template record exists in v15 (grep of addons/web/views shows only `<t t-call-assets="web.assets_backend">` consumers at webclient_templates.xml:206,208,227 and a `assets_backend_legacy_lazy` template at lazy_assets.xml:4), so such an inherit would fail with 'External ID not found'. `/** @odoo-module **/` files are transpiled at bundle time: odoo/tools/js_transpiler.py:576-594 (`ODOO_MODULE_RE`, `is_odoo_module`), used by odoo/addons/base/models/assetsbundle.py:820-828; import paths use `@web/...` aliases resolved from the file's location under `web/static/src`. odoo/modules/module.py has no 'assets' handling (manifest passes through as a dict).  Legacy `odoo.define` files in the same bundle are still accepted.

### Views: conditional attribute syntax

v15 uses `attrs="{'invisible': [('report_type','!=','pentaho')], 'required': [('report_type','=','pentaho')]}"` domains. Evidence: the core form itself uses `attrs="{'invisible':[('report_type','not in',['qweb-pdf'])]}"` (odoo/addons/base/views/ir_actions_views.xml:74-75); parsing at odoo/addons/base/models/ir_ui_view.py:86-88 (`transfer_node_to_modifiers`: `ast.literal_eval(node.get('attrs'))`), validation at :1615-1631 (`_validate_attrs` requires every field named in an attrs domain to be present in the view via `name_manager.must_have_fields`; `report_type` is present at line 72 of the form so it's satisfied). The v17+ form `invisible="report_type != 'pentaho'"` is NOT supported: a bare `invisible=`/`required=`/`readonly=` attribute is evaluated server-side once by `quick_eval(value_str, {'context': ...})` (ir_ui_view.py:97-100, quick_eval :44-55 -> safe_eval with only `context` in globals), so a python expression referencing `report_type` raises a NameError-style ValueError at view validation/arch rendering; only literals like 1/0/True/False (or context-only expressions) are valid there. `states=` is also still accepted (:90-95).

### Views: report form xmlid

`base.act_report_xml_view` (odoo/addons/base/views/ir_actions_views.xml:51, model ir.actions.report, loaded from odoo/addons/base/__manifest__.py:32). It contains `<field name="report_type"/>` at line 72 inside `<group><group>` (after `<field name="name"/>` :71, before `paperformat_id` :73-75), so `<xpath expr="//field[@name='report_type']" position="after">` / `<field name="report_type" position="after">` anchors work. Other anchors: `binding_model_id` invisible field :56, button_box with `create_action`/`unlink_action`/`associated_view` :58-67 (associated_view button is hidden for non-qweb types via attrs :65), pages `security` :86 and `advanced` :89. Tree view `base.act_report_xml_view_tree` :97 (also has report_type at :106).

`report_type` field present in form: True

### Views: report search xmlid

`base.act_report_xml_search_view` (odoo/addons/base/views/ir_actions_views.xml:111-126): fields `name` (:116, filter_domain includes report_type ilike) and `model` (:119); group-by filters `report_type` (:121) and `report_model` (:122) inside `<group expand="0" string="Group By">`. Window action `base.ir_action_report` :127 (uses the tree :131 and search :132 views).

### Routes: JSON route type

`type='json'`. odoo/http.py:451 (`:param type: The type of request, can be 'http' or 'json'`); JsonRequest._request_type = "json" (odoo/http.py:606); core usage e.g. addons/web/controllers/main.py:2033 `@http.route(['/report/check_wkhtmltopdf'], type='json', auth="user")` and :1583 `/web/action/load`.

### Routes: is type='json' still accepted

'json' IS the canonical and only accepted JSON type in v15; `type='jsonrpc'` does not exist. The route decorator stores the string unchecked, but at dispatch `_call_function` compares `self.endpoint.routing['type'] != self._request_type` (odoo/http.py:321-326) and raises `werkzeug.exceptions.BadRequest("Function declared as capable of handling request of type 'jsonrpc' but called with a request of type 'json'")` — so a `type='jsonrpc'` route would 400 on every call. Request class is chosen by mimetype: `application/json` / `application/json-rpc` -> JsonRequest, else HttpRequest (odoo/http.py:1427-1432). JSON routes are not CSRF-checked (CSRF check lives only in HttpRequest.dispatch, http.py:785-814).

### Routes: content_disposition

`from odoo.http import content_disposition` — odoo/http.py:1738-1742 `def content_disposition(filename)` (single positional arg; returns `"attachment; filename*=UTF-8''%s"` with RFC6266 url-quoting). Used the same way in addons/web/controllers/main.py:42. There is no `disposition_type` kwarg in v15 (always attachment).

### Routes: request.make_response

`request.make_response(data, headers=None, cookies=None)` — odoo/http.py:824-842 (`headers` is a list of (name, value) tuples, `cookies` a mapping set via `response.set_cookie(k, v)`). Core PDF pattern: addons/web/controllers/main.py:1928-1931 `request.make_response(pdf, headers=[('Content-Type','application/pdf'), ('Content-Length', len(pdf))])`; /report/download adds `('Content-Disposition', content_disposition(filename))`. Also `odoo.http.send_file(filepath_or_fp, mimetype=None, as_attachment=False, filename=None, mtime=None, ...)` exists (http.py:1641).

### Routes: JSON request shape

Yes: a type='json' handler receives `**kwargs` straight from the JSON-RPC `params` dict. odoo/http.py:626 `self.jsonrequest = json.loads(request)`, :632 `self.params = dict(self.jsonrequest.get("params", {}))`, :633 `self.context = self.params.pop('context', dict(self.session.context))` (a `context` key in params is POPPED and becomes request.context, not a kwarg), :702 `result = self._call_function(**self.params)`. `request.jsonrequest` (full envelope) and `request.params` both exist. The return value is wrapped into `{'jsonrpc':'2.0','id':..., 'result': ...}` by `_json_response` (:635-651); raising a Python exception becomes a JSON-RPC error. For type='http' routes, kwargs come from `httprequest.args` + form (:752-756) and `csrf_token` is popped before the call (:787).

### ORM: create decorator

`@api.model_create_multi` exists: odoo/api.py:421-429 (`def model_create_multi(method)`, wrapper accepts a single dict or list of dicts via `_model_create_multi` :414-418). `@api.model_create_single` also still exists (odoo/api.py:401-409). Plain `@api.model def create(self, vals)` (single dict) still works but the multi form is preferred; no warning is emitted for either in this version (the only DeprecationWarnings in api.py are Environment.manage :498 and related :714).

### ORM: selection_add / ondelete

SUPPORTED and REQUIRED here. odoo/fields.py:2436-2483: `selection_add` must be a list (:2440), `ondelete` is read from `field.args.get('ondelete') or {}` (:2445) and each new value defaults to 'set null' (:2446-2448). Because `ir.actions.report.report_type` is `required=True` (odoo/addons/base/models/ir_actions_report.py:102-106), line :2449-2457 raises `ValueError("...required selection fields must define an ondelete policy ... 'set default' (if the field has a default defined), 'cascade', or a single-argument callable")` if any added value is left at 'set null'. So the addon MUST write `report_type = fields.Selection(selection_add=[('pentaho', 'Pentaho')], ondelete={'pentaho': 'cascade'})` (or `'set default'` — valid since the base field has `default='qweb-pdf'`, check :2463-2468; or `'set qweb-pdf'`, :2469-2473; or a callable). Valid policies: 'set null', 'cascade', 'set default', 'set <value>', callable (:2460-2479).

### ORM: cr.savepoint()

Yes: `with self.env.cr.savepoint(): ...` — odoo/sql_db.py:125-143 `@contextmanager def savepoint(self, flush=True)` (creates a uuid-named SAVEPOINT, flushes before/after when flush=True, ROLLBACK TO on exception then re-raises, RELEASE otherwise). Cursor also supports `with cr:` (__enter__ :145).

### ORM: config['addons_path'] type

`odoo.tools.config['addons_path']` is a STR (comma-separated, normalized absolute paths): odoo/tools/config.py:500-512 (`self.options['addons_path'] = ",".join(self._normalize(x) for x in ...split(','))`), `__getitem__` returns `self.options[key]` (:689-690). The list form is the attribute `odoo.tools.config.addons_paths` (:543 `conf.addons_paths = self.options['addons_path'].split(',')`). Use `odoo.addons.__path__` or `odoo.modules.module.get_module_path(name)` to locate a module.

### ORM: has_group

`self.env.user.has_group('module.xml_id')` — odoo/addons/base/models/res_users.py:895-901 `def has_group(self, group_ext_id)` (callable on `env.user` or any single user; delegates to ormcached `_has_group` :903-912 which requires a fully-qualified `module.ext_id`). `self.env.is_admin()` / `is_system()` also available (used at ir_actions_report.py:1035).

### ORM: res.users.share

Yes: `res.users.share` exists — odoo/addons/base/models/res_users.py:370-371 `share = fields.Boolean(compute='_compute_share', compute_sudo=True, string='Share User', store=True, ...)`. (res.groups also has a `share` Boolean, :211.)

### ORM: _() usage

`from odoo import _` (odoo/__init__.py:149 exports `_` and `_lt`; `_ = GettextAlias()` at odoo/tools/translate.py:550). `GettextAlias.__call__(self, source, *args, **kwargs)` (translate.py:438-449) supports BOTH `_("...%s", x)` / `_("...%(name)s", name=x)` (positional XOR keyword, asserted :440) and, since it simply returns the translated string, the old `_("...%s") % x` still works with no warning or deprecation anywhere in translate.py (no 'deprecated' markers relevant to `_`). Core uses the kwargs style, e.g. ir_ui_view.py:1636-1639. `_lt` (lazy) also available for module-level strings.

### Report model: name

`ir.actions.report` (odoo/addons/base/models/ir_actions_report.py:86-92: `_name = 'ir.actions.report'`, `_inherit = 'ir.actions.actions'`, `_table = 'ir_act_report_xml'`, `_sequence = 'ir_actions_id_seq'`). `ir.actions.report.xml` does not exist in v15 (only the legacy table name survives).

### Report model: report_type values

ir_actions_report.py:102-110: `report_type = fields.Selection([('qweb-html','HTML'), ('qweb-pdf','PDF'), ('qweb-text','Text')], required=True, default='qweb-pdf', help=...)`. Other fields: name (:95, translate), type (:96), binding_type default 'report' (:98), model Char required (:99), model_id computed (:100), report_name Char required (:111), report_file Char (:112-113), groups_id M2M (:114), multi Boolean (:115), paperformat_id (:117), print_report_name (:118-119, translate), attachment_use (:120-121), attachment Char (:122-123). No `_get_readable_fields`-exposed custom fields by default (:151-160).

### Report model: render dispatch

ir_actions_report.py:999-1004: `def _render(self, res_ids, data=None): report_type = self.report_type.lower().replace('-', '_'); render_func = getattr(self, '_render_' + report_type, None); if not render_func: return None; return render_func(res_ids, data=data)`. So report_type 'pentaho' dispatches to `_render_pentaho(self, res_ids, data=None)` (underscore-prefixed; there is no public `render_<type>` dispatch in v15). Convention for the return value is a tuple `(bytes, format_str)`: `_render_qweb_pdf` returns `(pdf_content, 'pdf')` (:918, :946-947), `_render_qweb_text` returns `(..., 'text')` (:950-960), callers unpack `[0]` (addons/web/controllers/main.py:1926-1933; addons/mail/models/mail_template.py:236-238 uses `report._render_qweb_pdf([res_id])` when report_type == 'qweb-pdf' and `report._render([res_id])` otherwise, so `_render_pentaho` must return `(bytes, 'pdf')` for mail templates to attach it). Note `_render_qweb_pdf` is an instance method (:853) while `_render_qweb_text/_html` are `@api.model` (:949, :961); `_render` is called on a singleton report. `report_action(docids, data=None, config=True)` (:1006-1037) builds the client action dict including `report_type` (:1028) — and note :1034-1036 redirects admins to the external-layout configurator when `config=True` and no company layout is set. The web `/report/<converter>/<reportname>` controller (main.py:1910-1937) and `/report/download` (main.py:1973-2007) only know converters html/pdf/text and types qweb-pdf/qweb-text; an unknown converter raises HTTPException 'Converter %s not implemented.' (:1937), so pentaho needs its own routes.

### Report model: Binary attachment default

odoo/fields.py:2075-2097 `class Binary(Field)`: `prefetch = False` (:2083), `attachment = True` (:2085) — i.e. a `fields.Binary()` on ir.actions.report is stored as an ir.attachment by default (no bytea column); pass `attachment=False` for a DB column (:2089-2090 sets `attrs['attachment'] = False` only when explicitly given). Reading via /web/action/load uses `bin_size=True` (addons/web/controllers/main.py:1598-1599) so the action payload carries the size, not the blob (and the field is stripped anyway unless listed in `_get_readable_fields`).

### Report model: Print-menu binding

Inherited from ir.actions.actions (odoo/addons/base/models/ir_actions.py:35-40): `binding_model_id = fields.Many2one('ir.model', ondelete='cascade', ...)`, `binding_type = fields.Selection([('action','Action'), ('report','Report')], ...)` (report model defaults it to 'report', ir_actions_report.py:98), `binding_view_types = fields.Char(default='list,form')`. `model = fields.Char(required=True)` (:99) holds the model name string; `model_id` is computed from it (:100, :125-128). Helpers `create_action()` (:174-179, writes binding_model_id + binding_type='report') and `unlink_action()` (:181-185). Print-menu discovery: ir_actions.py:108-133 `get_bindings` query on binding_model_id/binding_type. In XML data: `<field name="binding_model_id" ref="model_..._"/>` + `<field name="binding_type">report</field>` + `<field name="model">x.y</field>`.

### Tests: TransactionCase conventions

`from odoo.tests.common import TransactionCase` (odoo/tests/common.py:803-866; also re-exported by `odoo.tests`, odoo/tests/__init__.py:2). v15 TransactionCase already runs ALL test methods in one class-level transaction with a per-test SAVEPOINT: `setUpClass` creates `cls.registry`, `cls.cr`, `cls.env` (SUPERUSER) (:822-831); `setUp` opens `SAVEPOINT test_N` and registers a ROLLBACK cleanup (:862-864), so class-wide fixtures go in `setUpClass` (call `super().setUpClass()` first) and per-test fixtures in `setUp` (call `super().setUp()`). `SavepointCase` still exists but is a deprecated alias emitting `DeprecationWarning('Deprecated class SavepointCase has been merged into TransactionCase')` on subclassing (:869-877); `HttpSavepointCase` likewise (:1792-1799). `SingleTransactionCase` also exists (:879). Helpers on BaseCase: `self.patch`, `assertRaises`, `Form` (:1884), `RecordCapturer` (:159).

### Tests: HttpCase

`from odoo.tests.common import HttpCase` (odoo/tests/common.py:1580-1790, subclass of TransactionCase with `registry_test_mode = True` :1582; `setUp` enters registry test mode :1601-1602 so HTTP worker threads share the test cursor). `self.authenticate(login, password)` (:1658-1700) creates a server session and sets `self.opener.cookies['session_id']`; `self.authenticate(None, None)` gives an anonymous session; `self.logout()` (:1654). `self.url_open(url, data=None, files=None, timeout=10, headers=None, allow_redirects=True, head=False)` (:1624-1631): relative URLs are prefixed with `http://127.0.0.1:<http_port>`; GET when no data/files, POST otherwise; there is NO `json=` kwarg. To POST to a type='json' route, mimic the in-tree tests (addons/mail/tests/test_discuss_controller.py:55-70, addons/auth_totp/tests/test_totp.py:115-129): `self.url_open('/pentaho/preview', data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'id': 0, 'params': {...}}), headers={'Content-Type': 'application/json'})` then `resp.json()['result']` / `['error']` — the application/json mimetype is what selects JsonRequest (odoo/http.py:1429). `self.opener` is a `requests.Session` subclass that flushes/clears the cursor before every request (:1547-1561), so `self.opener.post(self.base_url()+'/x', json={...})` also works. For type='http' POST routes with CSRF enabled you must send `csrf_token` (get one via `odoo.http.root`/`request.csrf_token()` in a session, or declare `csrf=False`). Also `self.xmlrpc_object` etc. (:1604-1606), `browser_js` (:1703), `start_tour` (:1767). The HTTP server must be running (do not pass `--no-http`).

### Tests: tagged

Yes: `from odoo.tests import tagged` / `from odoo.tests.common import tagged` — odoo/tests/common.py:2819-2838 `def tagged(*tags)`; all test classes default to `standard` + `at_install`; use `@tagged('post_install', '-at_install')` for tests that need the full registry (a warning is logged if a class is neither/both :2833-2836). Tags are not inherited by subclasses (:2827).

### Tests: run command

From the odoo15/odoo root, with the venv python: `/Volumes/Workspace/Development/OdooWorkbench/odoo15/venv/bin/python odoo-bin -d <fresh_db> --addons-path=addons,../enterprise,/path/to/custom_addons -i pentaho_reports --test-enable --test-tags /pentaho_reports --stop-after-init` (optionally `--log-level=test`). Flags verified in odoo/tools/config.py: `--test-enable` (:162-164), `--test-tags` (:165-183; spec format `[-][tag][/module][:class][.method]`, e.g. `--test-tags /pentaho_reports,:TestPentahoHttp.test_download`; setting it also enables tests), `--test-file` (:160-161), `--stop-after-init` (:293), `--screenshots`/`--screencasts` (:184-190). `-d`/`-i`/`-u` are the usual database/init/update options. Add `--http-port=<n>` if 8069 is busy (HttpCase reads `odoo.tools.config['http_port']`, common.py:1594, :1626).

### Other port tripwires

Porting traps specific to v15, all verified in source: (1) `report_type` is `required=True`, so `selection_add` WITHOUT an `ondelete` entry for 'pentaho' raises ValueError at registry load (odoo/fields.py:2449-2457) — use `ondelete={'pentaho': 'cascade'}` (or 'set default'). (2) Any custom ir.actions.report field the JS reads off `action` must be whitelisted in `_get_readable_fields()` (odoo/addons/base/models/ir_actions.py:159-169 + ir_actions_report.py:151-160; filtered in addons/web/controllers/main.py:232-246 `clean_action`), and Binary fields are read with `bin_size=True` in /web/action/load (main.py:1598-1599). (3) View inheritance must use `attrs="{'invisible': [...], 'required': [...]}"` domains; v17-style `invisible="expr"` is evaluated server-side with only `context` in scope (ir_ui_view.py:97-100, quick_eval :44-55) and will error. The XML form for asset bundles (`inherit_id="web.assets_backend"`) has no target record in v15 — declare `'assets': {'web.assets_backend': [...]}` in the manifest (ir_asset.py:211-219). (4) The JS must be an `/** @odoo-module **/` file registering into `registry.category("ir.actions.report handlers")` (action_service.js:1031); the handler signature is `(action, options, env)` and it must return a truthy value to stop core processing; otherwise core silently `console.error`s for unknown report types (:1063-1066) — no user-visible error. `download()` auto-adds `token` and `csrf_token` form fields (download.js:474-477) so the http route should take `**kw`; it treats a `text/html` 200 response as an error (download.js:481-486), so the PDF route must set `Content-Type: application/pdf`. (5) `type='jsonrpc'` routes 400 at dispatch (http.py:321-326) — use `type='json'`; a `context` key inside JSON params is popped into request.context and never reaches the handler (http.py:633). `content_disposition(filename)` takes one arg (http.py:1738). (6) `_render` dispatches to `_render_<type>` (underscore, ir_actions_report.py:999-1004) expecting `(bytes, fmt)`; `mail.template` calls `report._render([res_id])` for non-qweb-pdf types (addons/mail/models/mail_template.py:238), so implement `_render_pentaho(self, res_ids, data=None)` returning `(pdf_bytes, 'pdf')` to keep e-mail attachments working. `report_action()` redirects admins to the external-layout wizard when `config=True` and no layout is set (:1034-1036) — pass `config=False` for pentaho. (7) Tests: `SavepointCase` is deprecated (DeprecationWarning) — use TransactionCase with `setUpClass`; `HttpCase.url_open` has no `json=` kwarg, post `json.dumps(envelope)` with `Content-Type: application/json`. (8) `odoo.tools.config['addons_path']` is a comma-joined str (config.py:510-512); `config.addons_paths` is the list (:543). (9) `_()` supports both `%`-after and positional/keyword args, no deprecation (translate.py:438-449). (10) `cr.savepoint()` context manager, `model_create_multi`, `env.user.has_group`, `res.users.share` all exist as cited. (11) Core has `/report/download` with `auth="user"` that only understands qweb-pdf/qweb-text (main.py:1973-1988) — don't reuse it; and `/report/<converter>/...` raises 'Converter not implemented' for anything but html/pdf/text (:1937). (12) Python floor is 3.7 (setup.py:58) — avoid 3.8+ syntax (walrus, positional-only params, `dict |` needs 3.9) in the ported addon.

---

## Odoo 16

### Python floor

setup.py:64 `python_requires='>=3.7'` (odoo/release.py:15 `version_info = (16, 0, 0, FINAL, 0, '')`). The venv at odoo16/venv runs Python 3.9.24.

### Report-action JS: mechanism

New (Owl 2) action service: `addons/web/static/src/webclient/actions/action_service.js` `_executeReportAction` first iterates `registry.category("ir.actions.report handlers")` and only then hard-codes qweb-html / qweb-pdf / qweb-text. There is NO legacy ActionManager in 16 for reports: `addons/web/static/src/legacy/js/chrome/` only contains abstract_action.js and action_mixin.js (no action_manager*.js), and no file under `addons/web/static/src/legacy` references `_executeReportAction`/`ir.actions.report`. The legacy `session.get_file` (legacy/js/core/session.js:227-229 -> ajax.js:158) and `$.blockUI` defaults (legacy/js/core/misc.js:47-51) still exist but are not what the action service uses.

### Report-action JS: evidence

action_service.js:1 `/** @odoo-module **/`; :6 `import { download } from "@web/core/network/download"`; :8 `import { registry } from "@web/core/registry"`; :1077-1097 `_triggerDownload` (env.services.ui.block()/unblock() around `download({url:'/report/download', data:{data: JSON.stringify([url, action.report_type]), context: JSON.stringify(env.services.user.context)}})`, then close_on_report_download -> doAction act_window_close / options.onClose); :1131-1138 `_executeReportAction`: `const handlers = registry.category("ir.actions.report handlers").getAll(); for (const handler of handlers) { const result = await handler(action, options, env); if (result) { return result; } }`; :1139-1169 qweb-html/qweb-pdf/qweb-text branches; :1163-1168 else `console.error("The ActionManager can't handle reports of type ${action.report_type}", action)` (no throw, no download). :1241-1242 `case "ir.actions.report": return _executeReportAction(action, options)`. Registry API: core/registry.js:50 `add(key, value, { force, sequence } = {})`. Test proving the contract: addons/web/static/tests/webclient/actions/reports/report_action_tests.js:287-294 (handler returning true short-circuits; returning undefined falls through). Real-world reference in this tree: ../enterprise/iot/static/src/iot_report_action.js:23-49 (handler uses env.services.orm.call('ir.actions.report', 'iot_render', [action.id, action.context.active_ids, action.data]) then registers via `registry.category("ir.actions.report handlers").add("iot_report_action_handler", iotReportActionHandler)`).

### Report-action JS: how to intercept a custom report_type

Register an async handler `(action, options, env) => truthy|undefined` in registry category "ir.actions.report handlers"; return a truthy value to stop the default chain. With an unknown report_type the core does NOT error visibly: action_service.js:1163-1168 just `console.error`s and resolves (so without a handler a 'pentaho' report silently does nothing). IMPORTANT: the `action` dict received by the handler only contains whitelisted fields — odoo/addons/base/models/ir_actions.py:168-176 `_get_action_dict` filters `self.sudo().read()[0]` through `_get_readable_fields()`; ir_actions_report.py:158-167 whitelists report_name, report_type, target, context, data, close_on_report_download (+ base ir_actions.py:187-190: binding_model_id, binding_type, binding_view_types, display_name, help, id, name, type, xml_id). Any custom Char/Boolean field the JS needs must be added via an override `def _get_readable_fields(self): return super()._get_readable_fields() | {'your_field'}` (pattern: ../enterprise/iot/models/ir_actions_report.py:37-40). Exact file shape for pentaho_reports/static/src/pentaho_report_action.js:

/** @odoo-module **/
import { registry } from "@web/core/registry";
import { download } from "@web/core/network/download";

async function pentahoReportHandler(action, options, env) {
    if (action.report_type !== "pentaho") {
        return; // fall through to core qweb handling
    }
    const orm = env.services.orm;
    const ui = env.services.ui;
    const notification = env.services.notification;
    const activeIds = (action.context && action.context.active_ids) || [];
    ui.block();
    try {
        // any public (non-underscore) method on ir.actions.report
        const result = await orm.call("ir.actions.report", "render_report", [action.id, activeIds, action.data || {}], { context: action.context || {} });
        // POST download through a type='http' route (csrf_token is appended automatically by download())
        await download({
            url: "/pentaho/download",
            data: { token: result.token /* or whatever the route expects */, context: JSON.stringify(env.services.user.context) },
        });
        notification.add(env._t("Report generated"), { type: "success" });
    } catch (e) {
        notification.add(e.message || String(e), { title: env._t("Pentaho report failed"), type: "danger", sticky: true });
        throw e;
    } finally {
        ui.unblock();
    }
    const onClose = options.onClose;
    if (action.close_on_report_download) {
        return env.services.action.doAction({ type: "ir.actions.act_window_close" }, { onClose });
    } else if (onClose) {
        onClose();
    }
    return true; // handled
}

registry.category("ir.actions.report handlers").add("pentaho_report_handler", pentahoReportHandler);

For printing in a new tab (/pentaho/print, GET) use `window.open(url)`/`env.services.action.doAction({type:'ir.actions.act_url', url, target:'new'})` instead of download(). Put the file in the manifest under `'assets': {'web.assets_backend': ['pentaho_reports/static/src/**/*']}`.

### Download helper

`import { download } from "@web/core/network/download"` (addons/web/static/src/core/network/download.js:470-473, impl :474-499): `download({url, data})` or `download({form})`; it POSTs a FormData built from `options.data` with XMLHttpRequest, appends `token=dummy-because-api-expects-one` and `csrf_token=odoo.csrf_token` (:489-492), sets responseType blob (:512), reads the Content-Disposition filename and saves via `_download` (:513-521), and rejects with a parsed RPCError when status != 200 or the mimetype is text/html without a filename (:522-552). Companion `downloadFile(data, filename, mimetype)` (:453-456) for client-side blobs. Legacy `session.get_file` still exists (legacy/js/core/session.js:227, ajax.js:158-190) but is legacy-only and not usable from an @odoo-module without importing `web.session`. A `type='http'` download route must therefore accept POST (csrf token is sent, so default csrf=True is fine) and return `request.make_response(pdf, headers=[('Content-Type','application/pdf'), ('Content-Length', len(pdf)), ('Content-Disposition', content_disposition(filename))])` — see addons/web/controllers/report.py:42-44 and :131.

### Block UI

`env.services.ui.block()` / `env.services.ui.unblock()` (addons/web/static/src/core/ui/ui_service.js:127-188: ref-counted blockCount at :136-152, warns if unblocked more times than blocked :147; BlockUI component imported :6). Used exactly this way by core _triggerDownload (action_service.js:1079, :1087). `useService("ui")` from @web/core/utils/hooks inside components.

### Notification

`env.services.notification.add(message, { title, type: 'warning'|'danger'|'success'|'info', sticky: false, buttons: [...] })` — addons/web/static/src/core/notifications/notification_service.js:19-24 (option typedef), :41 `function add(message, options = {})`, :74 registered as service "notification". Used by action_service.js:1149-1152 and iot_report_action.js:8-13. Translation: `env._t(...)` (action_service.js:840, :1017) or `import { _t } from "@web/core/l10n/translation"` (core/l10n/translation.js:16).

### ES module (`/** @odoo-module **/`) supported

True

### Assets

Manifest `'assets'` key. odoo/modules/module.py:31 `_DEFAULT_MANIFEST` has `'assets': {}`; odoo/addons/base/models/ir_asset.py:204-207 `_fill_asset_paths` iterates `odoo.modules.module._get_manifest_cached(addon)['assets'].get(bundle, ())` for every installed addon (between low- and high-sequence ir.asset records). Example: addons/web/__manifest__.py:27 `'assets': {` ... bundles like 'web.assets_common', 'web.assets_backend'; 207 manifests in addons/ use it. Use `'assets': {'web.assets_backend': ['pentaho_reports/static/src/**/*']}`. XML `<template inherit_id="web.assets_backend">` is NOT the mechanism in 16 (assets are ir.asset records / manifest, not qweb templates). ES-module syntax `/** @odoo-module **/` is transpiled by odoo/tools/js_transpiler.py:4-5, :650-701 (`/** @odoo-module */`, `alias=`, `default=false` variants); the whole web client (action_service.js:1) uses it. Owl 2 is bundled (addons/web/static/lib/owl/owl.js, `import {...} from "@odoo/owl"` at action_service.js:18-26).

### Views: conditional attribute syntax

Odoo 16 uses `attrs="{'invisible': [('report_type','!=','pentaho')], 'required': [('report_type','=','pentaho')]}"` domains. Evidence: the base report form itself uses `attrs="{'invisible':[('report_type','not in',['qweb-pdf'])]}"` (odoo/addons/base/views/ir_actions_views.xml:73-74, :66); odoo/addons/base/models/ir_ui_view.py:82-86 `transfer_node_to_modifiers` does `ast.literal_eval(attrs)`; :1755-1771 `_validate_attrs` validates field names in attrs domains. The Odoo-17+ form `invisible="report_type != 'pentaho'"` is REJECTED: a bare `invisible=`/`required=` attribute is run through `str2bool` and, failing that, `safe_eval(val, {'context': self._context})` at view validation (ir_ui_view.py:1549-1560) and again at render (ir_ui_view.py:1127-1133 `_postprocess_context_dependent`) — only `context` is in scope, so `report_type` raises a NameError/ValueError and the view install fails. Only `invisible="1"`/`"0"` and `context.get(...)` expressions are accepted outside attrs.

### Views: report form xmlid

base.act_report_xml_view (odoo/addons/base/views/ir_actions_views.xml:51-95, model ir.actions.report). Yes, it contains `<field name="report_type"/>` at :72 inside `<group><group>` (name :71, report_type :72, paperformat_id :73-74), so `<xpath expr="//field[@name='report_type']" position="after">` or `<field name="report_type" position="after">` anchors cleanly. Other anchors: `binding_model_id` invisible field :56, notebook pages `security` (:83) and `advanced` (:86, with attachment_use/attachment :88-89).

`report_type` field present in form: True

### Views: report search xmlid

base.act_report_xml_search_view (odoo/addons/base/views/ir_actions_views.xml:111-126): `<search string="Report Xml">` with `<field name="name" .../>` (:116), `<field name="model" .../>` (:119), and a Group By `<group expand="0" string="Group By">` containing `<filter name="report_type" .../>` (:121) and `<filter name="report_model" .../>` (:122). Tree view: base.act_report_xml_view_tree (:97-109, has report_type column :106). Window action: base.ir_action_report (:127-132).

### Routes: JSON route type

'json'. odoo/http.py:2023-2024 `class JsonRPCDispatcher(Dispatcher): routing_type = 'json'`; http.py:723-724 docstring `:param str type: The type of request, either 'json' or 'http'`; http.py:748 `assert routing.get('type', 'http') in _dispatchers.keys()` where `_dispatchers` is populated from `routing_type` (http.py:1887-1895) so only 'http' and 'json' exist.

### Routes: is type='json' still accepted

'json' IS the canonical and only JSON type in 16; `type='jsonrpc'` does not exist and would fail the assertion at odoo/http.py:748 (`assert routing.get('type', 'http') in _dispatchers.keys()`) at import time. No deprecation/alias machinery is present in http.py for route types.

### Routes: content_disposition

`from odoo.http import content_disposition` — odoo/http.py:289 `def content_disposition(filename, disposition_type='attachment')`; validates disposition_type in ('attachment','inline') (:299-301) and returns `"{}; filename*=UTF-8''{}"` with url_quote (:302-305). Used by addons/web/controllers/report.py:10 and :131 `response.headers.add('Content-Disposition', content_disposition(filename))`.

### Routes: request.make_response

odoo/http.py:1670 `def make_response(self, data, headers=None, cookies=None, status=200)` — headers is a list of (name, value) tuples, cookies a Mapping applied with response.set_cookie (:1687-1691). Also :1693 `make_json_response(self, data, headers=None, cookies=None, status=200)`. Response.set_cookie signature :1216/1400 `(key, value='', max_age=None, expires=None, path='/', domain=None, secure=False, httponly=False, samesite=None, cookie_type='required')`. Typical PDF: `request.make_response(pdf, headers=[('Content-Type','application/pdf'), ('Content-Length', len(pdf)), ('Content-Disposition', content_disposition(name))])` (addons/web/controllers/report.py:42-44).

### Routes: JSON request shape

Yes: JsonRPCDispatcher.dispatch (odoo/http.py:2064-2086) does `self.jsonrequest = self.request.get_json_data()` (:2066), `self.request.params = dict(self.jsonrequest.get('params', {}), **args)` (:2075), pops 'context' from params and applies it to request.update_context (:2076-2078), then calls `endpoint(**self.request.params)` (via ir.http._dispatch when a db is present, :2080-2083); the return value is wrapped as `{'jsonrpc':'2.0','id':..., 'result': ...}` (:2114). `@route` wrapper filters unknown kwargs with a warning (http.py:757-763 via odoo/tools/func.py:66). Request is selected as JSON by mimetype (`is_compatible_with` :2032-2033, JSON_MIMETYPES). The raw body is at `request.dispatcher.jsonrequest` (:2028, :2066) — there is NO `request.jsonrequest` attribute on Request in 16 (grep `def jsonrequest` in http.py: none). CSRF is off by default for json routes and on for http routes (http.py:740-743; HttpDispatcher :1977-1988 checks `csrf_token` param for non-GET/HEAD/OPTIONS/TRACE, CSRF_FREE_METHODS :207). For http routes `request.params = dict(request.get_http_params(), **args)` (:1975).

### ORM: create decorator

Yes. odoo/api.py:434-443 `def model_create_multi(method)` (wrapper._api = 'model_create'; accepts a dict or list of dicts, :427-431). `model_create_single` also exists (api.py:413-423) but logs a WARNING `The model %s is not overriding the create method in batch` (:419). Base create is `@api.model_create_multi def create(self, vals_list)` (odoo/models.py:3923-3925); ir.actions.actions and ir.actions.act_window override it the same way (odoo/addons/base/models/ir_actions.py:48-49, :288-289) and clear caches on create/write/unlink (:49-69). So the port should use `@api.model_create_multi def create(self, vals_list)` and plain `def write(self, vals)`.

### ORM: selection_add / ondelete

Supported AND effectively required here. odoo/fields.py:2567-2572 documents `ondelete` for `selection_add`; :2647-2694 implements it: missing keys default to 'set null' (:2658-2659) BUT `if self.required and new_values and 'set null' in ondelete.values(): raise ValueError("required selection fields must define an ondelete policy ...")` (:2660-2668). `ir.actions.report.report_type` is `required=True, default='qweb-pdf'` (odoo/addons/base/models/ir_actions_report.py:109-113), therefore `report_type = fields.Selection(selection_add=[('pentaho', 'Pentaho')], ondelete={'pentaho': 'set default'})` (or 'cascade' / a callable) is mandatory; 'set default' is valid because the base field has a default (:2673-2678). Valid policies: 'set null', 'set default', 'set <value>', 'cascade', callable (:2670-2691).

### ORM: cr.savepoint()

Yes. odoo/sql_db.py:150 `def savepoint(self, flush=True) -> Savepoint` returns `_FlushingSavepoint(self)` (flush=True) or `Savepoint(self)`; `class Savepoint` :53 has `__enter__` :78 / `__exit__` :81 / `close(*, rollback=True)` :84 / `rollback()` :88. Use `with self.env.cr.savepoint(): ...`.

### ORM: config['addons_path'] type

str — a comma-separated string. odoo/tools/config.py:527 `self.options['addons_path'] = ','.join(default_addons)` and :529-532 `",".join(self._normalize(x) for x in self.options['addons_path'].split(',') if x.strip())`. The list form is `odoo.conf.addons_paths` (config.py:571 `conf.addons_paths = self.options['addons_path'].split(',')`; odoo/conf/__init__.py:19 `addons_paths = []`). So use `odoo.tools.config['addons_path'].split(',')` or `odoo.conf.addons_paths`.

### ORM: has_group

`res.users.has_group(group_ext_id)` exists: odoo/addons/base/models/res_users.py:1049-1055 (`def has_group(self, group_ext_id)`, delegates to ormcached `_has_group` :1057-1060 with the singleton's uid). Model-level `self.user_has_groups('module.group_a,!module.group_b')` at odoo/models.py:1455. `self.env.user.has_group('base.group_system')` is the idiom.

### ORM: res.users.share

Yes. odoo/addons/base/models/res_users.py:383-384 `share = fields.Boolean(compute='_compute_share', compute_sudo=True, string='Share User', store=True, ...)`, computed at :497. (res.groups also has a `share` boolean :199.)

### ORM: _() usage

`from odoo import _` (odoo/__init__.py:149 `from odoo.tools.translate import _, _lt`; odoo/tools/translate.py:626 `_ = GettextAlias()`). `GettextAlias.__call__(self, source, *args, **kwargs)` (translate.py:524-535) supports BOTH `_("x %s") % val` (plain string returned, no warning anywhere in translate.py — the only DeprecationWarnings there are for trans_load/trans_load_data :1465/:1472) and the newer `_("x %s", val)` / `_("x %(a)s", a=val)` forms, which interpolate the translated string and fall back to the source on TypeError/ValueError/KeyError with a logged exception (:529-535). Lazy `_lt` class at translate.py:556. Core itself still uses `_("...") % e` (translate.py:356) so the `%` form is fine in 16.

### Report model: name

ir.actions.report — odoo/addons/base/models/ir_actions_report.py:95-101 `class IrActionsReport(models.Model): _name = 'ir.actions.report'; _inherit = 'ir.actions.actions'; _table = 'ir_act_report_xml'`. There is no `ir.actions.report.xml` model in 16 (only the legacy table name survives).

### Report model: report_type values

ir_actions_report.py:109-117: `report_type = fields.Selection([('qweb-html', 'HTML'), ('qweb-pdf', 'PDF'), ('qweb-text', 'Text')], required=True, default='qweb-pdf', help=...)`. Other fields for reference: report_name (Char, required, :118), report_file (:119-120), groups_id (:121), multi (:122), paperformat_id (:124), print_report_name (:125-126), attachment_use (:127-128), attachment (:129-130), model (Char required, :106), model_id (computed from model, :107, :133-135), binding_type default 'report' (:105).

### Report model: render dispatch

ir_actions_report.py:1010-1017: `@api.model def _render(self, report_ref, res_ids, data=None): report = self._get_report(report_ref); report_type = report.report_type.lower().replace('-', '_'); render_func = getattr(self, '_render_' + report_type, None); if not render_func: return None; return render_func(report_ref, res_ids, data=data)`. So for report_type 'pentaho' the addon must define `def _render_pentaho(self, report_ref, res_ids, data=None)` and return a `(content_bytes, 'pdf')` tuple like the core methods (`_render_qweb_pdf(self, report_ref, res_ids=None, data=None)` :899 returns `pdf_content, 'pdf'` :967; `_render_qweb_text(self, report_ref, docids, data=None)` :969-977 returns `(..., 'text')`; `_render_qweb_html` :978-986 returns `(..., 'html')`). `report_ref` may be an id, a record, an xmlid or a report_name (`_get_report` :537-549). Note the underscore prefix: the generic entry point is `_render` (private, @api.model), not `render`; the legacy `render_<type>` public names do not exist. Mixing a public `render_report` ORM method for JS is fine (orm.call can only reach non-underscore methods, so name it without a leading underscore). Also note addons/web/controllers/report.py:86-131 `/report/download` only knows qweb-pdf/qweb-text (`if type_ in ['qweb-pdf','qweb-text'] ... else: return` :99, :133) — a custom type gets an empty response, hence the need for your own /pentaho/download route.

### Report model: Binary attachment default

fields.Binary stores in ir.attachment by default: odoo/fields.py:2275-2282 `:param bool attachment: ... (default: True)`, `attachment = True`; column_type is None when attachment=True (:2284-2286) and attachment is forced False when store=False (:2288-2292). Binary is `prefetch = False` and depends on context `bin_size` (:2280-2281). Use `fields.Binary(attachment=False)` if the .prpt must live in a bytea column. No `models.py` default override.

### Report model: Print-menu binding

Inherited from ir.actions.actions (odoo/addons/base/models/ir_actions.py:36-41): `binding_model_id = fields.Many2one('ir.model', ondelete='cascade')`, `binding_type = fields.Selection([('action','Action'),('report','Report')], required=True, default='action')` (ir.actions.report defaults it to 'report' at ir_actions_report.py:105), `binding_view_types = fields.Char(default='list,form')`. `model` is a plain Char (ir_actions_report.py:106) with a computed `model_id` (:107, :133-135). Helpers `create_action()` (:181-186 writes binding_model_id from `model`) and `unlink_action()` (:188-191). In XML data: `<field name="binding_model_id" ref="model_sale_order"/>` + `<field name="binding_type">report</field>`. The Print menu is computed by `ir.actions.actions.get_bindings` (ir_actions.py:128-147), and the action payload sent to the browser goes through the `_get_readable_fields` whitelist (:168-176).

### Tests: TransactionCase conventions

`from odoo.tests import TransactionCase` (odoo/tests/common.py:738; re-exported by odoo/tests/__init__.py `from .common import *`). Convention: shared data in `@classmethod setUpClass(cls): super().setUpClass()` (common.py:743-745 docstring; :769-789 sets cls.registry/cls.cr/cls.env as SUPERUSER), per-test `setUp(self): super().setUp()` wraps each test in a savepoint (:791-816). `SavepointCase` still importable but emits `DeprecationWarning: Deprecated class SavepointCase has been merged into TransactionCase` on subclassing (common.py:826-833); `HttpSavepointCase` likewise (:2124-2131). `SingleTransactionCase` :836. `Form` helper :2205.

### Tests: HttpCase

`from odoo.tests import HttpCase` (common.py:1802 `class HttpCase(TransactionCase)`, registry_test_mode=True :1804; setUpClass sets web.base.url and xmlrpc_url :1813-1820). `self.authenticate(user, password)` :1915-1956 creates a server session, sets `self.session` and `self.opener` (a requests.Session subclass :1765) with session_id + test-cursor cookies; pass `authenticate(None, None)` for an anonymous session. `self.url_open(url, data=None, files=None, timeout=12, headers=None, allow_redirects=True, head=False)` :1881-1888 — GET when no data, POST when data/files given; relative urls prefixed with base_url. POST JSON to a type='json' route (pattern from addons/mail_plugin/tests/common.py:49-68): `res = self.url_open('/pentaho/preview', data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': {...}}).encode(), headers={'Content-Type': 'application/json'}); res.json()['result']`. For a type='http' POST route with default csrf=True you must also send `csrf_token` (http.py:1977-1988) — generate with `odoo.http.Request.csrf_token`-equivalent or declare the route `csrf=False`; GET routes need no token (CSRF_FREE_METHODS http.py:207). `self.logout()` :1911. Note HttpCase needs the http server running (normal `odoo-bin --test-enable` does this; tests must be post_install or the module's at_install HTTP thread is used).

### Tests: tagged

`from odoo.tests import tagged` (odoo/tests/common.py:3192 `def tagged(*tags)`; e.g. addons/account_check_printing/tests/test_print_check.py:4). Default tags are 'standard' and 'at_install'; use `@tagged('post_install', '-at_install')` for HttpCase tests; the decorator warns if a class is neither/both at_install/post_install (:3211-3213).

### Tests: run command

`/Volumes/Workspace/Development/OdooWorkbench/odoo16/venv/bin/python odoo-bin -d <fresh_db> --addons-path=addons,../enterprise,<path-to-pentaho_reports-parent> -i pentaho_reports --test-enable --test-tags /pentaho_reports --stop-after-init` (optionally `--without-demo=all`). Flags verified in odoo/tools/config.py: `-i/--init` :112, `-u/--update` :113, `--without-demo` :115, `-d/--database` :253, `--test-enable` :175-177, `--test-tags` :178-197 (spec `[-][tag][/module][:class][.method][[params]]`, e.g. `--test-tags /pentaho_reports:TestPentahoController.test_preview`; tags default to 'standard', post_install tests run after all modules load), `--test-file` :173, `--stop-after-init` :307, `--screenshots` :204, `--addons-path` :121-123.

### Other port tripwires

1) The action dict the JS handler receives is whitelisted (ir_actions.py:168-190 + ir_actions_report.py:158-167); every custom ir.actions.report field the handler reads (e.g. a pentaho file flag) must be added through a `_get_readable_fields` override — otherwise it is silently absent (report_type itself is whitelisted). 2) The core `/report/download` route returns nothing for unknown report types (addons/web/controllers/report.py:99, :133) and `_render` returns None when `_render_<type>` is missing (ir_actions_report.py:1014-1016) — so mail templates / `report_action` users that call `_render` will get None unless `_render_pentaho(self, report_ref, res_ids, data=None)` returns `(bytes, 'pdf')`. `ir.actions.report.report_action(docids, data=None, config=True)` (:1019) still exists to build the client action. 3) Do not use `request.jsonrequest` (absent; use `request.dispatcher.jsonrequest`, http.py:2028/2066) or `type='jsonrpc'` (assert at http.py:748). `request.env`, `request.make_response`, `request.update_context` exist; `request.params` for http routes is built from form + query (http.py:1614-1628, :1975). 4) `fields.Selection(selection_add=...)` on `report_type` MUST carry `ondelete={'pentaho': 'set default'|'cascade'|callable}` or the registry raises ValueError (fields.py:2660-2668). 5) Views: only `attrs=` domains; bare `invisible="<py expr>"` is evaluated with just `context` in scope and fails validation (ir_ui_view.py:1549-1560, :1127-1133). `states=` still exists (:89-96). 6) In 16 there is no `@web/core/network/rpc` `rpc()` export and no `@web/core/user` — use `env.services.rpc(route, params)` (core/network/rpc_service.js:127-132), `env.services.orm.call(model, method, args, kwargs)` (core/orm_service.js:98), `env.services.user.context` (core/user_service.js:6-13) and `session` from `@web/session` (session.js:3). `env._t` is available on the env (action_service.js:840) or `import { _t } from "@web/core/l10n/translation"` (:16). 7) `env.services.action.doAction({type:'ir.actions.act_url', url, target:'new'})` is the way to open /pentaho/print in a new tab; `close_on_report_download` handling is the handler's responsibility (copy action_service.js:1090-1096). 8) Python: api.model_create_single logs a WARNING for every model using it (api.py:419) — use model_create_multi. `cr.savepoint(flush=True)` is a context manager (sql_db.py:150). `odoo.tools.config['addons_path']` is a comma string; `odoo.conf.addons_paths` is the list. `_("...") % x` is not deprecated (translate.py:524-535). 9) Tests: SavepointCase/HttpSavepointCase emit DeprecationWarning — use TransactionCase/HttpCase; HttpCase POST to csrf-protected http routes needs a csrf_token or `csrf=False`; JSON routes are csrf-free by default (http.py:740-743). 10) Owl 2 + `@odoo/owl` imports; legacy `web.*` odoo.define modules still exist under addons/web/static/src/legacy but the report action path is entirely in the new action service (no legacy action_manager in 16). 11) Python floor is 3.7 (setup.py:64); the venv is 3.9.24, so avoid 3.10+ syntax (match statements, `X | Y` type unions at runtime, etc.) in the ported addon.

---

## Odoo 17

### Python floor

python_requires='>=3.10' at setup.py:66 (odoo/release.py:15 version_info = (17, 0, 0, FINAL, 0, '')). The venv python is 3.10.19.

### Report-action JS: mechanism

OWL/ES-module action service with a dedicated handler registry: registry.category("ir.actions.report handlers"). No legacy odoo.define ActionManager / _executeReportAction override path exists in this version (addons/web/static/src/legacy/js contains only core/, libs/, public/; no action_manager*.js; no session.get_file anywhere under addons/web/static/src).

### Report-action JS: evidence

addons/web/static/src/webclient/actions/action_service.js:1082-1131 (_executeReportAction: line 1083 `const handlers = registry.category("ir.actions.report handlers").getAll();` lines 1084-1089 loop `const result = await handler(action, options, env); if (result) return result;`; line 1090 qweb-html branch; 1092-1121 qweb-pdf/qweb-text branch with env.services.ui.block()/unblock() at 1095/1108, downloadReport at 1101, notification at 1111, close_on_report_download at 1117-1121; 1122-1127 else-branch `console.error("The ActionManager can't handle reports of type ...")`). Dispatch from doAction: action_service.js:1203-1204 `case "ir.actions.report": return _executeReportAction(action, options);`. Service dependencies: action_service.js:1466-1477 (effect, localization, notification, router, rpc, title, ui, user, dialog). Reference in-tree implementation of the same registry: ../enterprise/iot/static/src/iot_report_action.js:100-145 (registry.category("ir.actions.report handlers").add("iot_report_action_handler", iotReportActionHandler)). Report helpers: addons/web/static/src/webclient/actions/reports/utils.js:14-33 getReportUrl, 67-91 downloadReport (uses download() from @web/core/network/download against /report/download).

### Report-action JS: how to intercept a custom report_type

Unknown report_type: the core does NOT throw; after the handler loop it falls through to `console.error("The ActionManager can't handle reports of type pentaho", action)` (action_service.js:1122-1127) and resolves undefined. So the addon must register a handler and return a truthy value. Exact pattern for this version:

/** @odoo-module **/
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { download } from "@web/core/network/download";

async function pentahoReportHandler(action, options, env) {
    if (action.report_type !== "pentaho") {
        return false;            // falsy => core continues to next handler / built-ins
    }
    const { orm, ui, notification, user } = env.services;
    const context = { ...user.context, ...(action.context || {}) };
    ui.block();                 // ui_service.js:163-170 (counted; always pair with unblock)
    try {
        // orm.call(model, method, args, kwargs) -> POST /web/dataset/call_kw/<model>/<method>  (orm_service.js:118-130)
        const result = await orm.call("ir.actions.report", "render_report",
            [action.id, context.active_ids || [], action.data || {}], { context });
        // download(): POST multipart to a type='http' route; auto-appends csrf_token and a dummy 'token' (download.js:480-511);
        // expects status 200 + a non-text/html mimetype or a Content-Disposition filename (download.js:523-547)
        await download({ url: "/pentaho/download", data: { token: result.token /* whatever your route needs */, context: JSON.stringify(context) } });
        notification.add(_t("Report generated"), { type: "success" });   // notification_service.js:47-103; options: title, type('warning'|'danger'|'success'|'info'), sticky, className, onClose, buttons
    } catch (e) {
        notification.add(e.message || _t("Report failed"), { type: "danger", sticky: true, title: _t("Report") });
        throw e;
    } finally {
        ui.unblock();
    }
    // mirror the core's close behaviour (action_service.js:1115-1121)
    const { onClose } = options;
    if (action.close_on_report_download) {
        return env.services.action.doAction({ type: "ir.actions.act_window_close" }, { onClose });
    } else if (onClose) {
        onClose();
    }
    return true;                // truthy => _executeReportAction returns here
}

registry.category("ir.actions.report handlers").add("pentaho_report_handler", pentahoReportHandler);

Manifest: 'assets': {'web.assets_backend': ['pentaho_reports/static/src/**/*']}. IMPORTANT server-side companion: the action dict that reaches JS is filtered by ir.actions.actions._get_readable_fields (odoo/addons/base/models/ir_actions.py:198-220; ir_actions_report.py:177-186 adds report_name, report_type, target, context, data, close_on_report_download). Any custom field the JS reads (e.g. pentaho file name/flags) must be added via `def _get_readable_fields(self): return super()._get_readable_fields() | {"your_field"}` exactly as enterprise iot does (../enterprise/iot/models/ir_actions_report.py:72-75). Also report_action() (ir_actions_report.py:1037-1064) only emits report_name/report_type/report_file/name/context/data — `action.id` is present when the action is loaded via /web/action/load but NOT when a server method returns self.report_action(); pass the report id through `data` or rely on report_name if the handler can be called both ways.

### Download helper

import { download } from "@web/core/network/download"; download({ url, data }) or download({ form }) (addons/web/static/src/core/network/download.js:480-511): builds a FormData from `data`, appends token='dummy-because-api-expects-one' and csrf_token=odoo.csrf_token (lines 499-502), POSTs via XMLHttpRequest with responseType blob (configureBlobDownloadXHR lines 523-577). Success requires xhr.status===200 and (mimetype !== 'text/html' || Content-Disposition filename) (line 535); filename is parsed from the Content-Disposition header (line 531-533); otherwise it parses the body as a serialized Python error (makeErrorFromResponse from @web/core/network/rpc_service) and rejects. Also exported: downloadFile(data, filename, mimetype) (download.js:463-466) for client-side blobs. No session.get_file / framework.getFile in this version. Core report download itself: reports/utils.js:67-91 downloadReport(rpc, action, type, userContext) -> download({url:'/report/download', data:{data: JSON.stringify([url, action.report_type]), context: JSON.stringify(userContext)}}). The server side of such a route must be type='http' (CSRF token is sent automatically so csrf can stay on) and should set headers [('Content-Type','application/pdf'), ('Content-Length', len(pdf)), ('Content-Disposition', content_disposition(filename))] exactly as addons/web/controllers/report.py:42-44 and 131.

### Block UI

env.services.ui.block() / env.services.ui.unblock() (addons/web/static/src/core/ui/ui_service.js:157-185). block(data) accepts optional {message}; it is reference-counted (blockCount, line 162-180) and unbalanced unblock logs a console warning (line 174). The core report flow wraps download in try/finally (action_service.js:1095-1109). The 'ui' service is a dependency of the action service (action_service.js:1473), so it is always available in `env.services` inside a handler.

### Notification

env.services.notification.add(message, options) (addons/web/static/src/core/notifications/notification_service.js:47-103, registered as service 'notification' at line 107). Options (lines 19-24): title (string), type ('warning'|'danger'|'success'|'info'), sticky (bool, default false), className, onClose(), buttons (NotificationButton[]). Returns a close function. Core usage: action_service.js:1111-1114 `env.services.notification.add(message, { sticky: true, title: _t("Report") })`. Translate with `import { _t } from "@web/core/l10n/translation"`.

### ES module (`/** @odoo-module **/`) supported

True

### Assets

Manifest 'assets' key. odoo/modules/module.py:31 (_DEFAULT_MANIFEST has 'assets': {}); odoo/addons/base/models/ir_asset.py:184-186 iterates `odoo.modules.module._get_manifest_cached(addon)['assets'].get(bundle, ())` for every installed addon; directives append/prepend/after/before/remove/replace/include at ir_asset.py:18-26. Bundle name is 'web.assets_backend' (addons/web/__manifest__.py:45). XML templates inheriting web.assets_backend are NOT the mechanism in 17 — use e.g. 'assets': {'web.assets_backend': ['pentaho_reports/static/src/**/*']}. JS files starting with /** @odoo-module **/ are transpiled to the module loader (odoo/tools/js_transpiler.py:4-5 and 664-681 ODOO_MODULE_RE/is_odoo_module; odoo/addons/base/models/assetsbundle.py:850 `self._is_transpiled = bool(is_odoo_module(...))`). The legacy `odoo.define` still exists (addons/web/static/src/module_loader.js:199) but the action service itself is only extensible through the registry, so write ES modules. The reference enterprise iot addon declares its handler the same way (../enterprise/iot/__manifest__.py:27-28).

### Views: conditional attribute syntax

Python-expression attributes only: invisible="report_type != 'pentaho'", required="report_type == 'pentaho'", readonly="...". attrs="{...}" and states="..." are HARD-REJECTED at view validation: odoo/addons/base/models/ir_ui_view.py:391-396 `if combined_arch.xpath('//*[@attrs]') or combined_arch.xpath('//*[@states]'): raise ValidationError(_('Since 17.0, the "attrs" and "states" attributes are no longer used...'))`. Core examples in the very view being inherited: odoo/addons/base/views/ir_actions_views.xml:78 `invisible="report_type not in ['qweb-pdf', 'qweb-html', 'qweb-text']"` and line 89-90 `<field name="paperformat_id" invisible="report_type != 'qweb-pdf'"/>`.

### Views: report form xmlid

base.act_report_xml_view (odoo/addons/base/views/ir_actions_views.xml:55-111, model ir.actions.report, <form string="Report">). It contains <field name="report_type"/> at line 88 inside the first <group> (siblings: name at 87, paperformat_id at 89-90) — a valid anchor for <xpath expr="//field[@name='report_type']" position="after">. Note the second group shows <field name="report_name"/> (line 95) which is required=True on the model (ir_actions_report.py:134), so a pentaho report still needs a report_name value (or the addon must set one in create()).

`report_type` field present in form: True

### Views: report search xmlid

base.act_report_xml_search_view (odoo/addons/base/views/ir_actions_views.xml:127-141, <search string="Report Xml">; fields: name (line 132), model (line 135); Group By filters report_type (137) and report_model (138)). Tree view: base.act_report_xml_view_tree (line 113-125, has report_type at 122).

### Routes: JSON route type

'json'. odoo/http.py:2023-2031 _dispatchers is keyed by Dispatcher.routing_type; only two exist: HttpDispatcher.routing_type = 'http' (line 2099) and JsonRPCDispatcher.routing_type = 'json' (line 2163). route() asserts `routing.get('type', 'http') in _dispatchers.keys()` (line 784), so type='jsonrpc' raises AssertionError at import. Docstring: http.py:756-758 "either 'json' or 'http'". grep for type='jsonrpc' across odoo/ and addons/ returns nothing.

### Routes: is type='json' still accepted

'json' IS the canonical and only JSON-RPC type in 17 (http.py:2163). There is no 'jsonrpc' alias and no deprecation of 'json'. A type='json' route requires the request mimetype to be application/json or application/json-rpc (JSON_MIMETYPES http.py:247; is_compatible_with http.py:2171-2172; otherwise BadRequest at http.py:1909-1917). CSRF is off by default for json routes and on for http routes (http.py:773-775; enforcement http.py:2117-2125 for non-GET/HEAD/OPTIONS/TRACE, CSRF_FREE_METHODS http.py:218). Core example: addons/web/controllers/report.py:146 `@http.route(['/report/check_wkhtmltopdf'], type='json', auth="user")`.

### Routes: content_disposition

from odoo.http import content_disposition; signature `content_disposition(filename, disposition_type='attachment')` (odoo/http.py:309-325). disposition_type must be 'attachment' or 'inline' else ValueError (line 319-321); returns "<type>; filename*=UTF-8''<url-quoted name>" (line 322-325). Used in addons/web/controllers/report.py:10 (import) and :131 `response.headers.add('Content-Disposition', content_disposition(filename))`. For inline print-preview use content_disposition(filename, 'inline').

### Routes: request.make_response

request.make_response(data, headers=None, cookies=None, status=200) (odoo/http.py:1808-1829): headers is a list of (name, value) tuples, cookies a Mapping applied via response.set_cookie(k, v); returns odoo.http.Response. Also request.make_json_response(data, headers=None, cookies=None, status=200) (http.py:1831-1848). Response.set_cookie(key, value='', max_age=None, expires=-1, path='/', domain=None, secure=False, httponly=False, samesite=None, cookie_type='required') at http.py:1561. PDF pattern: addons/web/controllers/report.py:42-44 `request.make_response(pdf, headers=[('Content-Type','application/pdf'), ('Content-Length', len(pdf))])`.

### Routes: JSON request shape

Yes. JsonRPCDispatcher.dispatch (odoo/http.py:2174-2220): body parsed with request.get_json_data() (json.loads of the raw body, http.py:1768-1769), then `self.request.params = dict(self.jsonrequest.get('params', {}), **args)` (line 2214) and the endpoint is called with **params; params MUST be a JSON object (by-name), arrays are unsupported (docstring 2181-2184). A special 'context' param replaces the session context and is removed before the call (docstring 2186-2188). Unknown kwargs are filtered out with a warning by route_wrapper (http.py:793-797). The raw payload is at request.dispatcher.jsonrequest (http.py:2167, 2205) — there is no request.jsonrequest attribute on Request in 17. For type='http' routes, request.params = query string + form + files merged with URL args (get_http_params http.py:1752-1766, HttpDispatcher.dispatch 2114). Return value of a json route is JSON-serialised into {'jsonrpc':'2.0','id':..,'result':..} (line 2250).

### ORM: create decorator

Yes. odoo/api.py:434-443 `def model_create_multi(method)` (sets wrapper._api = 'model_create'). @api.model_create_single also exists (api.py:413-423) but logs a warning 'The model %s is not overriding the create method in batch' at decoration time. Base class itself uses it: odoo/addons/base/models/ir_actions.py:76-81 `@api.model_create_multi def create(self, vals_list)` and write at 83-87 (both call self.env.registry.clear_cache()). So the addon should write `@api.model_create_multi def create(self, vals_list): records = super().create(vals_list); ...` and `def write(self, vals): res = super().write(vals); ...`.

### ORM: selection_add / ondelete

Supported AND REQUIRED here. odoo/fields.py:2678-2683 documents ondelete; processing at fields.py:2758-2805: new selection_add keys default to 'set null' (2768-2770) but line 2771-2779 raises ValueError "required selection fields must define an ondelete policy ..." when the base field is required and any added value resolves to 'set null'. ir.actions.report.report_type IS required=True with default='qweb-pdf' (odoo/addons/base/models/ir_actions_report.py:125-129). Therefore you must write: report_type = fields.Selection(selection_add=[('pentaho', 'Pentaho')], ondelete={'pentaho': 'set default'}) ('set default' is valid because default exists, fields.py:2785-2789; 'cascade' or a callable also accepted, 2783/2798-2800). Omitting ondelete = registry load failure.

### ORM: cr.savepoint()

Yes. odoo/sql_db.py:153-162 `def savepoint(self, flush=True) -> Savepoint` — returns a context manager (_FlushingSavepoint by default, Savepoint when flush=False); use `with self.env.cr.savepoint(): ...`.

### ORM: config['addons_path'] type

str (comma-separated). odoo/tools/config.py:527 and 529-532 always store `self.options['addons_path'] = ','.join(...)`; the list form lives in `conf.addons_paths = self.options['addons_path'].split(',')` (config.py:571). So odoo.tools.config['addons_path'] is a str; odoo.tools.config.addons_paths is a list.

### ORM: has_group

res.users.has_group(group_ext_id) exists: odoo/addons/base/models/res_users.py:1096-1103 (`@api.model def has_group(self, group_ext_id)`; uses singleton id if called on a record, else uid), delegating to ormcached _has_group at 1106-1115 which requires a fully-qualified 'module.ext_id'. Usage: self.env.user.has_group('base.group_system'). JS side: env.services.user.hasGroup(group) (addons/web/static/src/core/user_service.js:55-57, async).

### ORM: res.users.share

Yes. res_users.py:391-392 `share = fields.Boolean(compute='_compute_share', compute_sudo=True, string='Share User', store=True, help="External user with limited access...")`. (res.groups also has a share Boolean at res_users.py:199.)

### ORM: _() usage

`from odoo import _` works (odoo/__init__.py:129 `from odoo.tools.translate import _, _lt`). _ is a GettextAlias instance (translate.py:466, 646). __call__(source, *args, **kwargs) at translate.py:542-555: if args/kwargs are given it applies `translation % (args or kwargs)` itself, so the preferred form is _('Unsupported report type %s found.', report.report_type) (core example: addons/mail/models/mail_template.py:299). `_("...") % x` still works with no warning and no deprecation in translate.py (the only warnings.warn calls there are for trans_load/trans_load_data, lines 1579/1586). Caveat: positional args and kwargs cannot be mixed (assert at line 544), and the module for lookup is inferred from the caller's file path (translate.py:557-565), so keep _() calls inside the addon's own files. _lt (lazy) also exists at translate.py:576.

### Report model: name

ir.actions.report (odoo/addons/base/models/ir_actions_report.py:110-116: _name = 'ir.actions.report', _inherit = 'ir.actions.actions', _table = 'ir_act_report_xml', _allow_sudo_commands = False). ir.actions.report.xml does not exist in this version.

### Report model: report_type values

[('qweb-html','HTML'), ('qweb-pdf','PDF'), ('qweb-text','Text')], required=True, default='qweb-pdf' (ir_actions_report.py:125-133). Other fields present: report_name Char required (134), report_file Char (135-136), groups_id M2M (137), multi Boolean (138), paperformat_id (140), print_report_name Char translate (141-142), attachment_use Boolean (143-144), attachment Char (145-146), model Char required (122), model_id computed (123), binding_type default 'report' (121).

### Report model: render dispatch

`@api.model def _render(self, report_ref, res_ids, data=None)` at ir_actions_report.py:1029-1035: `report = self._get_report(report_ref); report_type = report.report_type.lower().replace('-', '_'); render_func = getattr(self, '_render_' + report_type, None); if not render_func: return None; return render_func(report_ref, res_ids, data=data)`. So for report_type 'pentaho' the addon must define `@api.model def _render_pentaho(self, report_ref, res_ids, data=None)` (underscore prefix; the public render_<type> name is NOT used) and return a tuple (content_bytes, 'pdf') like _render_qweb_pdf (916-..., returns `pdf_content, 'pdf'`), _render_qweb_text (988-995 returns (text,'text')), _render_qweb_html (997-1003 returns (html,'html')). report_ref may be an int id, a record, an xmlid or a report_name (_get_report 565-580; _get_report_from_name 555-562). mail.template attachment generation calls `self.env['ir.actions.report']._render(report, [res_id])` for any non-qweb type and raises UserError 'Unsupported report type' if it returns None (addons/mail/models/mail_template.py:293-300) — implementing _render_pentaho makes email-template attachments work for free. Note the hyphen->underscore normalisation: a value like 'pentaho-pdf' would dispatch to _render_pentaho_pdf.

### Report model: Binary attachment default

fields.Binary(attachment=True) by default: odoo/fields.py:2339-2349 `attachment = True  # whether value is stored in attachment`; column_type is None when attachment=True, ('bytea','bytea') when attachment=False (2351-2353); prefetch=False (2347). Non-stored Binary forces attachment=False (2355-2359). So a Binary field on ir.actions.report holding the .prpt is stored as an ir.attachment row (res_model='ir.actions.report', res_field=<field name>) unless attachment=False is passed.

### Report model: Print-menu binding

On ir.actions.actions (odoo/addons/base/models/ir_actions.py:64-69): binding_model_id = Many2one('ir.model', ondelete='cascade'), binding_type = Selection([('action','Action'),('report','Report')], required=True, default='action') — ir.actions.report overrides the default to 'report' (ir_actions_report.py:121), binding_view_types = Char(default='list,form'). `model` (Char, required) is the report's target model (ir_actions_report.py:122). Helpers: create_action() (ir_actions_report.py:201-205) sets binding_model_id from self.model and binding_type='report'; unlink_action() (207-211) clears it; the form view buttons at ir_actions_views.xml:63-76 call these. In XML data: <field name="binding_model_id" ref="model_<model_with_underscores>"/> <field name="binding_type">report</field>. _get_bindings (ir_actions.py:152-180) is what fills the Print menu.

### Tests: TransactionCase conventions

odoo/tests/common.py:805-907 class TransactionCase(BaseCase): one transaction per class, each test in a savepoint; data setup belongs in `@classmethod def setUpClass(cls): super().setUpClass(); ...` (docstring 806-818; setUpClass at 837; cls.env/cls.cr/cls.registry set there). setUp at 876 is still available per-test. SingleTransactionCase at 909. SavepointCase does NOT exist in odoo/tests/common.py (only odoo/addons/base/tests/common.py:132 SavepointCaseWithUserDemo(TransactionCase)); use TransactionCase. Imports: `from odoo.tests import TransactionCase, HttpCase, tagged, Form` (odoo/tests/__init__.py:8-10 re-exports common.* and Form).

### Tests: HttpCase

class HttpCase(TransactionCase) at odoo/tests/common.py:1897; setUpClass enters registry test mode and sets web.base.url (1908-1919); setUp builds self.opener = Opener(self.cr) (requests.Session subclass, line 1854) plus xmlrpc proxies (1921-1933). self.authenticate(user, password) at 2003 (creates a server session, sets cookie on self.opener at 2038). self.url_open(url, data=None, files=None, timeout=12, headers=None, allow_redirects=True, head=False) at 1966-1973 — GET when no data/files, POST otherwise, relative URLs prefixed with base_url(). JSON route in tests: self.make_jsonrpc_request(route, params=None, headers=None) at 2209-2235 wraps {'id':0,'jsonrpc':'2.0','method':'call','params':params} with Content-Type application/json, raises JsonRpcException (class at 1891) on an error payload and returns result. For a type='http' POST route with CSRF on, include 'csrf_token': odoo.http.Request.csrf_token(self) in the form data like addons/web/tests/test_login.py:22-26 (or declare csrf=False on the route). Check a PDF download with resp.headers['Content-Type'] == 'application/pdf' and 'Content-Disposition'.

### Tests: tagged

from odoo.tests import tagged — odoo/tests/common.py:2308-2330. Default tags are 'standard' and 'at_install'; use @tagged('post_install', '-at_install') for HttpCase tests that need the full registry; mixing/neither logs a warning (2325-2327).

### Tests: run command

/Volumes/Workspace/Development/OdooWorkbench/odoo17/venv/bin/python odoo-bin -c <conf> --addons-path=<paths incl. the pentaho_reports parent> -d <fresh_db> -i pentaho_reports --test-enable --test-tags /pentaho_reports --stop-after-init   (flags: -i/--init config.py:112; --test-enable config.py:176-178; -t/--test-tags config.py:179-198 with spec format [-][tag][/module][:class][.method], e.g. --test-tags /pentaho_reports or /pentaho_reports:TestPentahoRoutes; --stop-after-init config.py:310; -d config.py:254; --test-file config.py:174-175 also exists). HttpCase tests need an HTTP port (default 8069 or --http-port) and, for post_install tags, the test runs after all modules load.

### Other port tripwires

1) Readable-fields gate: the webclient never sees custom ir.actions.report columns unless _get_readable_fields is extended (ir_actions.py:198-220, ir_actions_report.py:177-186); this is the #1 silent-failure trap when porting a handler that inspects action.<custom_field>. 2) ondelete on selection_add is mandatory because report_type is required (fields.py:2771-2779); use ondelete={'pentaho': 'set default'}. 3) The render hook name is _render_pentaho (underscore, @api.model, signature (report_ref, res_ids, data=None), return (bytes, 'pdf')) per ir_actions_report.py:1029-1035; a public render_report ORM method called from JS is fine but should delegate to _render_pentaho so mail.template attachments (mail_template.py:293-300) also work. 4) report_name is required=True on the model (ir_actions_report.py:134) and is in the base form; pentaho reports must populate it (create() override or default) — and _get_report_from_name/_get_report look records up by report_name, so keep it unique. 5) /report/download (addons/web/controllers/report.py:86-144) is qweb-only; custom types need their own type='http' routes; download() in JS auto-sends csrf_token and a dummy 'token' form field, so route signatures should accept **kwargs or explicit token=None. 6) The http route return for a PDF must be request.make_response(bytes, headers=[...]) — returning raw bytes from an http route is not a PDF response. 7) Views: attrs/states raise ValidationError at install (ir_ui_view.py:391-396); convert every attrs into invisible=/required=/readonly= python expressions. 8) Tests: no SavepointCase; HttpCase JSON POSTs via make_jsonrpc_request; http POSTs need a csrf_token unless csrf=False. 9) JS: legacy odoo.define ActionManager/session.get_file are gone; everything is @odoo-module + registry.category('ir.actions.report handlers'); handler signature is (action, options, env) and must return truthy to stop the core from logging 'The ActionManager can't handle reports of type pentaho'. 10) Python floor 3.10 (setup.py:66); odoo.tools.config['addons_path'] is a comma-joined str (config.py:527-532), list form is config.addons_paths. 11) JSON routes are type='json' (http.py:2163); 'jsonrpc' is rejected by the assert at http.py:784. 12) request.jsonrequest does not exist on Request; the payload is request.dispatcher.jsonrequest (http.py:2167/2205) and params arrive as kwargs (http.py:2214).

---

## Odoo 18

### Python floor

setup.py:68 `python_requires='>=3.10'` (odoo/release.py:16 `version_info = (18, 0, 0, FINAL, 0, '')`).

### Report-action JS: mechanism

New OWL/ES-module action service with a handler registry: `registry.category("ir.actions.report handlers")`. No legacy ActionManager / odoo.define anywhere in addons/web/static/src (grep for `odoo.define(` returns 0 files; `session.get_file` does not exist). Handlers are called by `_executeReportAction` in addons/web/static/src/webclient/actions/action_service.js BEFORE the core's report_type switch.

### Report-action JS: evidence

action_service.js:1293-1341 (`async function _executeReportAction(action, options)`; line 1294 `const handlers = registry.category("ir.actions.report handlers").getAll();`; 1295-1305 loop `const result = await handler(action, options, env); if (result) { ... return result; }`; 1307 `if (action.report_type === "qweb-html")`, 1309 `else if ("qweb-pdf" || "qweb-text")`, 1337-1340 `else { console.error(`The ActionManager can't handle reports of type ${action.report_type}`, action); }`); 1420-1421 dispatch `case "ir.actions.report": return _executeReportAction(action, options)`. Handler type signature declared at addons/web/static/src/@types/registries/registries.d.ts:81 `IrActionsReportHandlers = (action, options, env) => (void | boolean | Promise<void|boolean>)` and :102. Reference implementation in this exact version: ../enterprise/iot/static/src/iot_report_action.js:163-165 `registry.category("ir.actions.report handlers").add("iot_report_action_handler", iotReportActionHandler)` which uses `env.services.ui.block()/unblock()` (153,156), `env.services.orm` (141), `options.onClose?.()` (158) and `return true` (159) / `return false` to fall through (149). Registry add signature: addons/web/static/src/core/registry.js:95 `add(key, value, { force, sequence } = {})` (default sequence 50, line 109).

### Report-action JS: how to intercept a custom report_type

Core behaviour for unknown report_type: NOT an error/exception — after all handlers return falsy, `_executeReportAction` falls to the `else` branch and only does `console.error(...)` (action_service.js:1337-1340); nothing is downloaded and onClose is not called. So the addon MUST register a handler that returns a truthy value. Also note: when the handler returns truthy, core itself handles `action.close_on_report_download` → `doAction({type:'ir.actions.act_window_close'}, {onClose})` else calls `options.onClose()` (1297-1303), so the handler should NOT call onClose again. Exact pattern for Odoo 18 (file e.g. pentaho_reports/static/src/js/pentaho_report_action.js, listed in the manifest's `'assets': {'web.assets_backend': [...]}`):

```js
/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { download } from "@web/core/network/download";
import { user } from "@web/core/user";

async function pentahoReportHandler(action, options, env) {
    if (action.report_type !== "pentaho") {
        return false; // fall through to other handlers / core
    }
    const context = { ...user.context, ...(action.context || {}) };
    env.services.ui.block();
    try {
        // ORM call: env.services.orm.call(model, method, args, kwargs) -> /web/dataset/call_kw
        const result = await env.services.orm.call(
            "ir.actions.report", "render_report",
            [[action.id], context.active_ids || [], action.data || {}],
            { context }
        );
        // download via type='http' controller: POSTs FormData (+ csrf_token) with XHR, saves the blob
        await download({
            url: "/pentaho/download",
            data: { token: result.token, context: JSON.stringify(context) },
        });
        env.services.notification.add(_t("Report generated"), { type: "success" });
    } catch (e) {
        env.services.notification.add(e.message || String(e), { type: "danger", sticky: true, title: _t("Pentaho") });
        throw e;
    } finally {
        env.services.ui.unblock();
    }
    return true; // tells _executeReportAction the action is handled (it then handles close_on_report_download/onClose)
}

registry.category("ir.actions.report handlers").add("pentaho_report_handler", pentahoReportHandler);
```

For the /pentaho/print variant (open inline PDF in a new tab) use `window.open(url)`/`browser.open` instead of `download()`; `browser` is exported from `@web/core/browser/browser` (imported at action_service.js:2). `action.id`, `report_type`, `report_name`, `report_file`, `context`, `data`, `close_on_report_download` reach the JS (ir_actions_report.py:204-214 `_get_readable_fields`); any custom Python field (e.g. pentaho template path) is stripped by `clean_action` (addons/web/controllers/utils.py:23-46) and `_get_action_dict` (ir_actions.py:229-238) unless the addon also overrides `_get_readable_fields` on ir.actions.report to add it (or passes it in `context`/`data`).

### Download helper

`import { download } from "@web/core/network/download";` — addons/web/static/src/core/network/download.js:479 `export function download(options)`; implementation 483-511: opens an XHR `POST options.url` (or `options.form`), builds FormData from `options.data` entries, appends `token="dummy-because-api-expects-one"` (497) and `csrf_token` from `odoo.csrf_token` (499-501), then `configureBlobDownloadXHR` (522-576) reads `Content-Disposition` (529-531) to name the saved blob, and on non-200 / text/html-without-filename parses the body as a serialized Python error (`makeErrorFromResponse`, 553-568) and rejects (so `content_disposition()` with a filename on the server side is what makes the browser save the file). Also exported: `downloadFile(data, filename, mimetype)` at :462 for client-side blobs. Core's own report download uses it: addons/web/static/src/webclient/actions/reports/utils.js:65-86 `downloadReport(rpc, action, type, userContext)` → `download({url: "/report/download", data: {data: JSON.stringify([url, action.report_type]), context: JSON.stringify(userContext)}})`. `getReportUrl(action, type, userContext)` at utils.js:12. `session.get_file` does NOT exist in this version (grep returns nothing under addons/web/static/src).

### Block UI

`env.services.ui.block()` / `env.services.ui.unblock()` — addons/web/static/src/core/ui/ui_service.js:161-170 `function block(data)` (optional `{message, delay}` forwarded to the BlockUI main component), 172-182 `unblock()` (warns if called more than block), `isBlocked` getter 210. Core uses it exactly this way around the report download at action_service.js:1312-1321 (`env.services.ui.block(); try {...} finally { env.services.ui.unblock(); }`).

### Notification

`env.services.notification.add(message, options)` — addons/web/static/src/core/notifications/notification_service.js:46 `function add(message, options = {})`; options typedef at 16-24: `title`, `autocloseDelay` (default 4000), `type` in "warning"|"danger"|"success"|"info", `sticky`, `className`, `onClose`, `buttons` ([{name, icon, primary, onClick}], 10-14). Registered as service "notification" at :108. Core example: action_service.js:1326-1329 `env.services.notification.add(message, { sticky: true, title: _t("Report") })`. `_t` from `@web/core/l10n/translation` (translation.js:36 `export function _t(term, ...values)`).

### ES module (`/** @odoo-module **/`) supported

True

### Assets

Manifest `'assets'` key (XML `<template inherit_id="web.assets_backend">` is NOT how bundles are built in 18). odoo/modules/module.py:46 `_DEFAULT_MANIFEST` contains `'assets': {}`; odoo/addons/base/models/ir_asset.py:186 `for command in odoo.modules.module._get_manifest_cached(addon)['assets'].get(bundle, ())` is where bundle contents come from; `web.assets_backend` is defined in addons/web/__manifest__.py:45 (`'web.assets_backend': [`). ES-module syntax: odoo/tools/js_transpiler.py:664-672 `ODOO_MODULE_RE` matches `/** @odoo-module **/` (with optional `ignore`, `alias=`, `default=`); :675-687 `is_odoo_module(url, content)` — any file under `/{addon}/static/src` or `/{addon}/static/tests` is transpiled EVEN WITHOUT the header (686-687), the header only matters elsewhere or to opt out with `@odoo-module ignore`. Transpilation is wired in odoo/addons/base/models/assetsbundle.py:811-821 (`is_transpiled` → `transpile_javascript`). So the addon manifest needs: `'assets': {'web.assets_backend': ['pentaho_reports/static/src/js/**/*']}` and the JS can keep `/** @odoo-module **/` + `import ... from "@web/..."`.

### Views: conditional attribute syntax

Python-expression attributes only: `invisible="report_type != 'pentaho'"`, `required="report_type == 'pentaho'"`, `readonly="..."`, `column_invisible="..."` (VIEW_MODIFIERS at odoo/addons/base/models/ir_ui_view.py:34). `attrs="{...}"` and `states="..."` are REJECTED at view validation: ir_ui_view.py:384-390 `if combined_arch.xpath('//*[@attrs]') or combined_arch.xpath('//*[@states]'): ... raise ValidationError('Since 17.0, the "attrs" and "states" attributes are no longer used.\nView: %(name)s in %(file)s')`. The core report form itself uses the new form, e.g. ir_actions_views.xml:63 `invisible="binding_model_id"`, :77 `invisible="report_type not in ['qweb-pdf', 'qweb-html', 'qweb-text']"`, :90 `invisible="report_type != 'qweb-pdf'"`. Also: list views are `<list>` not `<tree>` — ir.ui.view `type` Selection has only 'list' (ir_ui_view.py:153), type is derived from the arch root tag (ir_ui_view.py:504), and there is no 'tree' string anywhere in odoo/*.py; core's own tree view is `<list string="Report xml">` (ir_actions_views.xml:116). Any inherited list-view xpath must target `//list`.

### Views: report form xmlid

`base.act_report_xml_view` — odoo/addons/base/views/ir_actions_views.xml:55 `<record id="act_report_xml_view" model="ir.ui.view">`, model ir.actions.report (:57). It contains `<field name="report_type"/>` at :88 (inside `<group><group>` after `<field name="name"/>` :87), so `<xpath expr="//field[@name='report_type']" position="after">` is a valid anchor. Other anchors: `paperformat_id` (:89), `model`/`report_name`/`print_report_name` (:93-95), notebook pages `security` (:99) and `advanced` (:102) with `attachment_use`/`attachment` (:104-105), button box `name="button_box"` (:61). List view `base.act_report_xml_view_tree` (:112, root `<list>` :116, contains `report_type` :121).

`report_type` field present in form: True

### Views: report search xmlid

`base.act_report_xml_search_view` — ir_actions_views.xml:126 `<record id="act_report_xml_search_view" model="ir.ui.view">`; arch :130-140: `<search string="Report Xml">` with `<field name="name" filter_domain=... string="Report"/>` (:131-133), `<field name="model" filter_domain="[('model','=', self)]" string="Model"/>` (:134), and `<group expand="0" string="Group By" colspan="4">` with filters `name="report_type"` (:136) and `name="report_model"` (:137). Anchor e.g. `//field[@name='model']` position="after" or `//filter[@name='report_type']`.

### Routes: JSON route type

'json'. odoo/http.py:2327-2328 `class JsonRPCDispatcher(Dispatcher): routing_type = 'json'`; :2263-2264 `class HttpDispatcher: routing_type = 'http'`; the route decorator asserts `routing.get('type', 'http') in _dispatchers.keys()` (:739) and `_dispatchers` is populated by `Dispatcher.__init_subclass__` (:2185-2193) so only 'http' and 'json' exist. Docstring :701-703 `:param str type: The type of request, either 'json' or 'http'`. The 19-style `type='jsonrpc'` does not exist: grep for `type='jsonrpc'`/`type="jsonrpc"` over odoo/ and addons/ returns nothing, and passing it would fail the assert at http.py:739.

### Routes: is type='json' still accepted

'json' IS the canonical (and only) JSON-RPC type in 18 — see http.py:2328 `routing_type = 'json'` and the docstring at :701-703. 'jsonrpc' is NOT accepted (assert at http.py:739 against `_dispatchers.keys()` = {'http','json'}). So the port must rename `type='jsonrpc'` → `type='json'` on /pentaho/preview. Core example: addons/web/controllers/report.py:153 `@http.route(['/report/check_wkhtmltopdf'], type='json', auth='user', readonly=True)`.

### Routes: content_disposition

`from odoo.http import content_disposition` — odoo/http.py:315 `def content_disposition(filename, disposition_type='attachment')`; validates `disposition_type in ('attachment', 'inline')` (:325-327, ValueError otherwise) and returns `"{}; filename*=UTF-8''{}".format(disposition_type, url_quote(filename, ...))` (:328-331). So `content_disposition('x.pdf', 'inline')` works for the /pentaho/print inline case. Core usage: addons/web/controllers/report.py:10 import and :138 `response.headers.add('Content-Disposition', content_disposition(filename))`; PDF headers pattern :43-44 `pdfhttpheaders = [('Content-Type', 'application/pdf'), ('Content-Length', len(pdf))]; return request.make_response(pdf, headers=pdfhttpheaders)`.

### Routes: request.make_response

odoo/http.py:1893 `def make_response(self, data, headers=None, cookies=None, status=200)` — headers is a list of `(name, value)` tuples, cookies a Mapping applied via `response.set_cookie(k, v)` (:1910-1913). Also :1916 `def make_json_response(self, data, headers=None, cookies=None, status=200)` (json.dumps + Content-Type application/json; charset=utf-8). A type='http' route's return value is wrapped by `Response.load(result)` (http.py:755-757).

### Routes: JSON request shape

Yes: a type='json' endpoint receives the JSON-RPC `params` object as keyword arguments. http.py:2339-2383 `JsonRPCDispatcher.dispatch`: body parsed by `self.request.get_json_data()` (:2370; = `json.loads(self.httprequest.get_data(as_text=True))` :1853-1854), `self.request_id = self.jsonrequest.get('id')` (:2371), then `self.request.params = dict(self.jsonrequest.get('params', {}), **args)` (:2379) and `request.registry['ir.http']._dispatch(endpoint)` / `endpoint(**self.request.params)` (:2381-2384); params must be a JSON object, not an array (:2348-2350); a special `context` param replaces the session context and is removed (:2352-2354). `request.dispatcher.jsonrequest` holds the raw envelope (:2332); `request.params` is the merged dict (there is no `request.jsonrequest` attribute on the request itself — http.py:1647 comment `#self.params = {}  # set by the Dispatcher`). The route is only matched when the request mimetype is JSON (`is_compatible_with` :2335-2337, else BadRequest at :2020-2028). The return value is wrapped as `{'jsonrpc': '2.0', 'id': ..., 'result': ...}` by `_response` (:2414-2415). CSRF is off by default for 'json' routes and on for 'http' routes (docstring :723-725) — which is why `download()` appends `csrf_token` (download.js:499-501); `auth='user'` default handling and `readonly=` route flag exist (:726-729, :890-900). Unknown kwargs are filtered with a warning (`route_wrapper` :748-752).

### ORM: create decorator

Yes. odoo/api.py:501 `def model_create_multi(method: T) -> T` (wrapper `_api = 'model_create'`, :509-511); `model_create_single` also still exists at :477. Base ir.actions.actions already uses it: odoo/addons/base/models/ir_actions.py:104-109 `@api.model_create_multi def create(self, vals_list): res = super(IrActions, self).create(vals_list); self.env.registry.clear_cache(); return res` and `write` at :111-115. So the addon's override should be `@api.model_create_multi def create(self, vals_list)` + plain `def write(self, vals)`. Also available: `@api.readonly` (api.py:436-446) and `@api.private` (:448).

### ORM: selection_add / ondelete

SUPPORTED and effectively REQUIRED here. odoo/fields.py:2832 `class Selection`, docstring :2840-2856 (`selection_add`, `ondelete` dict). Processing in `_setup_attrs` :2930-2980: each new key defaults to `'set null'` (:2941-2943) BUT `if self.required and new_values and 'set null' in ondelete.values(): raise ValueError("... required selection fields must define an ondelete policy ... 'set default' (if the field has a default defined), 'cascade', or a single-argument callable ...")` (:2944-2951). `ir.actions.report.report_type` is `required=True, default='qweb-pdf'` (ir_actions_report.py:151-155), so `fields.Selection(selection_add=[('pentaho', 'Pentaho')], ondelete={'pentaho': 'set default'})` (valid because a default exists, :2957-2962) or `'cascade'` or a callable is mandatory; omitting `ondelete` raises at registry load. Valid policies: 'set null', 'cascade', 'set default', 'set <value>', callable (:2954-2974).

### ORM: cr.savepoint()

Yes. odoo/sql_db.py:182 `def savepoint(self, flush=True) -> Savepoint:` — "context manager entering in a new savepoint" (class `Savepoint` at :79; `_FlushingSavepoint` when flush=True, :188-190). Usage `with self.env.cr.savepoint(): ...`.

### ORM: config['addons_path'] type

str — a comma-separated string. odoo/tools/config.py:547 `self.options['addons_path'] = ','.join(default_addons)` / :549-552 `",".join(self._normalize(x) for x in self.options['addons_path'].split(',') if x.strip())`; consumers split it: :591 `conf.addons_paths = self.options['addons_path'].split(',')`. So `odoo.tools.config['addons_path'].split(',')` is correct; iterating it directly yields characters. Prefer `odoo.tools.misc.file_path('pentaho_reports/...')` (odoo/tools/misc.py:187 `def file_path(file_path, filter_ext=('',), env=None)`) or `odoo.addons.__path__` for locating files.

### ORM: has_group

`user.has_group(group_ext_id: str) -> bool` on res.users: odoo/addons/base/models/res_users.py:1200-1217 — `self.ensure_one()`; raises AccessError unless `self.env.su or self == self.env.user or self.env.user._has_group('base.group_user')` (:1209-1212); `_has_group` (:1219-1230) is the unrestricted internal variant; `has_groups(group_spec)` comma/!-spec at :1168. There is NO `user_has_groups` on models in 18 (grep over odoo/models.py and odoo/api.py returns nothing) — use `self.env.user.has_group('base.group_system')` / `self.env.user._has_group(...)`, or `self.env.is_admin()` (used at ir_actions_report.py:1164).

### ORM: res.users.share

Yes. odoo/addons/base/models/res_users.py:390-391 `share = fields.Boolean(compute='_compute_share', compute_sudo=True, string='Share User', store=True, ...)`; `_compute_share` :535-539 (True for users not in base.group_user). `request.env.user.share` is valid.

### ORM: _() usage

`from odoo import _` works (odoo/__init__.py:73 `from odoo.tools.translate import _, _lt`); `_` is `get_text_alias` (odoo/tools/translate.py:731) with signature `get_text_alias(source: str, *args, **kwargs)` (:628-632, `assert not (args and kwargs)`), formatting done inside `get_translation` via `translation % args` (:469, :492) with a logged exception fallback on bad format (:493-497). Lazy `_lt` = `LazyGettext` (:732) and `LazyTranslate(__name__)` (:709-728). Env-bound form `self.env._("hello %s", "test")` exists (odoo/api.py:788-796). The old `_("...%s") % x` style is NOT warned or deprecated in this tree (no warnings.warn around it; e.g. translate.py:376 itself does `_("Error while parsing view:\n\n%s") % e`), but the preferred form is `_("...%s", x)` / `_("...%(name)s", name=x)` so the args are part of the translation call.

### Report model: name

`ir.actions.report` — odoo/addons/base/models/ir_actions_report.py:138-144 `class IrActionsReport(models.Model): _name = 'ir.actions.report'; _inherit = 'ir.actions.actions'; _table = 'ir_act_report_xml'; _order = 'name, id'; _allow_sudo_commands = False`. (`ir.actions.report.xml` does not exist; only the SQL table keeps the old name.)

### Report model: report_type values

ir_actions_report.py:151-159: `report_type = fields.Selection([('qweb-html', 'HTML'), ('qweb-pdf', 'PDF'), ('qweb-text', 'Text')], required=True, default='qweb-pdf', help=...)`. Other fields in 18: `type` Char default 'ir.actions.report' (:146), `binding_type` default 'report' (:147), `model` Char required (:148), `model_id` computed/searchable (:149), `report_name` Char required (:160), `report_file` Char (:161-162), `groups_id` M2M res.groups (:163), `multi` Boolean (:164), `paperformat_id` (:166), `print_report_name` translate=True (:167-168), `attachment_use` Boolean (:169-170), `attachment` Char (:171-172), `domain` Char (:173).

### Report model: render dispatch

ir_actions_report.py:1128-1135: `@api.model def _render(self, report_ref, res_ids, data=None): report = self._get_report(report_ref); report_type = report.report_type.lower().replace('-', '_'); render_func = getattr(self, '_render_' + report_type, None); if not render_func: return None; return render_func(report_ref, res_ids, data=data)`. So for report_type 'pentaho' the addon must define `@api.model def _render_pentaho(self, report_ref, res_ids, data=None)` (underscore-prefixed) returning a 2-tuple `(content_bytes, format_str)` — e.g. `(pdf_bytes, 'pdf')`, matching `_render_qweb_text` :1088-1095 (`return self._render_template(...), 'text'`) and `_render_qweb_pdf` :1017 (`return ..., 'pdf'` :1015). Consumers: addons/mail/models/mail_template.py:320-327 — for non-qweb types it calls `self.env['ir.actions.report']._render(report, [res_id])`, raises UserError 'Unsupported report type' if None, and unpacks `report_content, report_format = render_res` (so mail-template attachments of a pentaho report work once `_render_pentaho` exists). `report_ref` may be an id/xmlid/record/report_name (`_get_report` :649). `report_action(docids, data=None, config=True)` (:1137-1170) builds the client action dict with keys context/data/type/report_name/report_type/report_file/name (:1156-1164) and may wrap it in the document-layout configurator for admins (`_action_configure_external_report_layout` :1172, sets `close_on_report_download=True` :1175) — an addon may want to pass `config=False` or override to skip that for pentaho. The web `/report/download` controller (addons/web/controllers/report.py:92-151) only handles 'qweb-pdf'/'qweb-text' and `return`s None for others (:140-141); it never calls `_render`, which is why a dedicated /pentaho/download route is needed.

### Report model: Binary attachment default

`fields.Binary` stores in ir.attachment by default: odoo/fields.py:2512-2522 `class Binary(Field)`: `:param bool attachment: whether the field should be stored as ir_attachment or in a column of the model's table (default: True)`; `attachment = True` (:2522); `column_type` is None when attachment (:2524-2526) — i.e. no bytea column unless `attachment=False`. `prefetch = False` (:2520) and depends on context `bin_size` (:2521); `store=False` forces attachment=False (:2528-2532). Note ir.actions.report has `_allow_sudo_commands = False` (:144), irrelevant to Binary but relevant if x2many commands are written via sudo.

### Report model: Print-menu binding

Binding to a model's Print menu is via fields inherited from ir.actions.actions (odoo/addons/base/models/ir_actions.py:68-73): `binding_model_id = fields.Many2one('ir.model', ondelete='cascade', ...)`, `binding_type = fields.Selection([('action','Action'),('report','Report')], required=True, default='action')` (ir.actions.report overrides default to 'report' at ir_actions_report.py:147), `binding_view_types = fields.Char(default='list,form')`. Helpers `create_action()` (ir_actions_report.py:228-233 → `report.write({'binding_model_id': model.id, 'binding_type': 'report'})`) and `unlink_action()` (:235-238). The `model` Char (:148) is the target model name; `model_id` is computed from it (:175-178). In XML data: `<field name="binding_model_id" ref="model_xxx"/>` + `<field name="binding_type">report</field>` (+ `model`, `report_type`, `report_name`, `name`). Bindings are cached: base create/write call `self.env.registry.clear_cache()` (ir_actions.py:104-115).

### Tests: TransactionCase conventions

`odoo.tests.common.TransactionCase` (odoo/tests/common.py:931) — single transaction per class, each test in a savepoint; docstring :936-939 says shared data setup belongs in `@classmethod setUpClass(cls)` with `super().setUpClass()` (:963-964) — `cls.env`, `cls.registry`, `cls.cr` are class attributes (:946-948); `setUp(self)` (:1076) also works per-test. `SavepointCase` does NOT exist (grep over odoo/tests/*.py returns nothing) — TransactionCase is the savepoint-per-test class. Also available: `SingleTransactionCase` (:1163), `BaseCase` (:298), `Form` (odoo/tests/__init__.py:10). All exported via `from odoo.tests import TransactionCase, HttpCase, tagged` (odoo/tests/__init__.py:9 `from .common import *`).

### Tests: HttpCase

`odoo.tests.common.HttpCase(TransactionCase)` at odoo/tests/common.py:2144. `self.authenticate(user, password, *, browser=None, session_extra=None)` (:2262) creates a server session and resets `self.opener` (a requests.Session, `Opener` :2101) with `cookies['session_id'] = session.sid` (:2318-2319) so subsequent calls are authenticated; `self.url_open(url, data=None, files=None, timeout=12, headers=None, allow_redirects=True, head=False)` (:2225-2232) — relative `/path` is prefixed with `self.base_url()`, GET when no data, POST when `data` or `files` given. To POST to a type='json' route use `self.make_jsonrpc_request(route, params=None, headers=None)` (:2497-2525) which sends `{'id':0,'jsonrpc':'2.0','method':'call','params':params}` with `Content-Type: application/json` and returns the `result` key (raises `JsonRpcException` :2138 on `error`); or manually `self.url_open('/pentaho/preview', data=json.dumps({'jsonrpc':'2.0','method':'call','params':{...},'id':1}), headers={'Content-Type': 'application/json'})`. For the type='http' PDF routes: `resp = self.url_open('/pentaho/download', data={...})` then assert `resp.headers['Content-Type']` / `Content-Disposition` / `resp.content[:4] == b'%PDF'`. Note http routes are CSRF-protected by default (http.py:723-725) — in tests either pass `csrf=False` on the route, use GET, or obtain a token; `make_jsonrpc_request` avoids this since json routes have no CSRF.

### Tests: tagged

`from odoo.tests import tagged` — odoo/tests/common.py:2602 `def tagged(*tags)`; tags default to {'standard','at_install'}; `'-'` prefix removes a tag; warns if not exactly one of at_install/post_install (:2618-2622). Typical: `@tagged('post_install', '-at_install')` for HttpCase tests.

### Tests: run command

`/Volumes/Workspace/Development/OdooWorkbench/odoo18/venv/bin/python /Volumes/Workspace/Development/OdooWorkbench/odoo18/odoo/odoo-bin -d <fresh_db> --addons-path=<path/to/addons>,<.../odoo18/odoo/addons> -i pentaho_reports --test-enable --test-tags /pentaho_reports --stop-after-init` (optionally `--without-demo=all`, `--log-level=test`). Flags verified in odoo/tools/config.py: `-i/--init` :111, `-u/--update` :112, `--without-demo` :114, `--test-file` :171, `--test-enable` :173 (callback sets test_tags to '+standard' if unset, :689-691), `-t/--test-tags` :176 with spec format `[-][tag][/module][:class][.method][[params]]` (:178-189), `--stop-after-init` :311, `--addons-path` :121, `--dev` :305. Tests run after module install (at_install) and again after loading (post_install) per :191-195.

### Other port tripwires

Things the 19→18 port will trip on, all verified in this tree:
1. Route type: `type='jsonrpc'` does not exist — only 'http' and 'json' (http.py:739, 2264, 2328). Rename to `type='json'`. Keep `auth='user'`; `readonly=True` is accepted on routes (http.py:726-729).
2. Selection extension: `ondelete=` is mandatory for `report_type` because the base field is required (fields.py:2944-2951); use `ondelete={'pentaho': 'set default'}` (default 'qweb-pdf' exists) or 'cascade'.
3. Render hook name: `_render` dispatches to `_render_<type>` with leading underscore (ir_actions_report.py:1132) and calls it as `render_func(report_ref, res_ids, data=data)`; return `(bytes, 'pdf')`. Also the core `/report/download` silently returns None for non-qweb types (addons/web/controllers/report.py:140-141) — the addon's own routes are required, and the JS handler must return truthy or the core only `console.error`s (action_service.js:1337-1340).
4. Action dict hygiene: custom ir.actions.report fields are stripped from the action sent to the client unless added via an override of `_get_readable_fields` (ir_actions_report.py:204-214, ir_actions.py:229-250, web/controllers/utils.py:23-46, which also logs a warning for non-field custom keys). Prefer passing extra info through `context`/`data`, or fetch it in the handler with `env.services.orm.call`.
5. `report_action()` wraps in the document-layout configurator for admins when no external layout is configured (ir_actions_report.py:1164-1165, 1172-1175) and sets `close_on_report_download`; the JS handler must not call `options.onClose` itself because `_executeReportAction` does it when the handler returns truthy (action_service.js:1297-1303).
6. JS imports for 18: `@web/core/registry`, `@web/core/network/download` (`download`), `@web/core/network/rpc` (`rpc(url, params, settings)` :65), `@web/core/user` (`user.context`), `@web/core/l10n/translation` (`_t`), `@web/core/browser/browser`; services: `env.services.orm.call(model, method, args, kwargs)` (orm_service.js:115-127; it merges `user.context`), `env.services.ui.block/unblock`, `env.services.notification.add(msg, {type, sticky, title})`, `env.services.action.doAction`. `/** @odoo-module **/` header is fine but optional under static/src (js_transpiler.py:686-687). No `odoo.define`, no `web.core`, no `session.get_file`, no `framework.blockUI`.
7. Views: `attrs`/`states` raise ValidationError (ir_ui_view.py:384-390); use `invisible="report_type != 'pentaho'"`, `required="report_type == 'pentaho'"`. `<tree>` is not a valid root tag — use `<list>` (ir_ui_view.py:153, 504; core uses `<list>` at ir_actions_views.xml:116). Anchors: `base.act_report_xml_view` has `<field name="report_type"/>` at ir_actions_views.xml:88; `base.act_report_xml_search_view` at :126 with `<field name="model">` :134 and `<filter name="report_type">` :136.
8. ORM/utilities: `@api.model_create_multi` create (api.py:501; base ir.actions.actions already uses it and clears registry cache, ir_actions.py:104-115 — call super). `cr.savepoint()` exists (sql_db.py:182). `config['addons_path']` is a comma string (config.py:547-552); use `odoo.tools.misc.file_path` (misc.py:187). `user_has_groups` does not exist — use `self.env.user.has_group('base.group_system')` (res_users.py:1200). `res.users.share` exists (res_users.py:390). `self.env._()` exists (api.py:788). `fields.Binary` defaults to attachment storage (fields.py:2522) — pass `attachment=False` if the .prpt must live in a bytea column.
9. `content_disposition(filename, disposition_type='attachment')` supports 'inline' for the /pentaho/print route (http.py:315-331). `request.make_response(data, headers=None, cookies=None, status=200)` (http.py:1893); `make_json_response` also available (:1916). 'http' routes are CSRF-protected by default (http.py:723-725); the JS `download()` helper sends `csrf_token` automatically (download.js:499-501), and parses `Content-Disposition` for the filename (download.js:529-531), so the server MUST set it for the save dialog to name the file.
10. Tests: `from odoo.tests import TransactionCase, HttpCase, tagged`; no SavepointCase; `HttpCase.make_jsonrpc_request` exists (common.py:2497) for the json route; `authenticate('admin','admin')` then `url_open`. Run with `-i pentaho_reports --test-enable --test-tags /pentaho_reports --stop-after-init` (config.py:111, 173, 176, 311).
11. Python floor is 3.10 (setup.py:68) — `match` statements and `X | None` unions are fine; 3.12-only syntax (PEP 695 generics, f-string nesting quirks) is not.

---

## Odoo 19

### Python floor

python_requires='>=3.10' — setup.py:70 builds it from MIN_PY_VERSION; odoo/release.py:39 `MIN_PY_VERSION = (3, 10)`; odoo/release.py:15 `version_info = (19, 0, 0, FINAL, 0, '')`.

### Report-action JS: mechanism

New OWL action service with a handler registry: `registry.category("ir.actions.report handlers")`. There is NO legacy ActionManager / odoo.define module for reports (odoo.define still exists as a loader shim at addons/web/static/src/module_loader.js:242 but nothing report-related is defined through it). The dispatcher is `_executeReportAction(action, options)` in addons/web/static/src/webclient/actions/action_service.js:1347-1395, reached from the `case "ir.actions.report"` branch of doAction at action_service.js:1470-1471.

### Report-action JS: evidence

addons/web/static/src/webclient/actions/action_service.js:1348 `const handlers = registry.category("ir.actions.report handlers").getAll();` — :1349-1359 loops `for (const handler of handlers) { const result = await handler(action, options, env); if (result) { ... close_on_report_download -> doAction act_window_close; else onClose(); return result; } }` — :1361 `if (action.report_type === "qweb-html")` -> _executeReportClientAction — :1363-1389 qweb-pdf/qweb-text -> env.services.ui.block(); downloadReport(rpc, action, type, ctx); env.services.ui.unblock(); notification on wkhtmltopdf message — :1390-1394 `else { console.error(`The ActionManager can't handle reports of type ${action.report_type}`, action); }`. Helpers: addons/web/static/src/webclient/actions/reports/utils.js:12 getReportUrl, :65 downloadReport. Reference implementation of a third-party handler: ../enterprise/iot/static/src/iot_report_action.js:81-109 (`async function iotReportActionHandler(action, options, env) {...}` then `registry.category("ir.actions.report handlers").add("iot_report_action_handler", iotReportActionHandler)`).

### Report-action JS: how to intercept a custom report_type

Register a function in the `ir.actions.report handlers` registry; it receives `(action, options, env)`, must return a truthy value to stop core processing (falsy = fall through to the core qweb handling). For an UNKNOWN report_type the core does NOT throw: it only `console.error`s 'The ActionManager can't handle reports of type pentaho' (action_service.js:1390-1394) and resolves undefined — so without a handler the Print menu silently does nothing. Exact shape for this version (file e.g. pentaho_reports/static/src/pentaho_report_handler.js, declared in the manifest under 'assets': {'web.assets_backend': ['pentaho_reports/static/src/**/*']}):

```js
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { download } from "@web/core/network/download";
import { user } from "@web/core/user";

async function pentahoReportHandler(action, options, env) {
    if (action.report_type !== "pentaho") {
        return false; // let the core handle qweb-* reports
    }
    const { orm, ui, notification } = env.services;
    const context = { ...user.context, ...(action.context || {}) };
    const activeIds = (context.active_ids || []).filter((id) => typeof id === "number");
    ui.block();
    try {
        // ORM call: public method on ir.actions.report (must not start with '_' nor be @api.private)
        const result = await orm.call("ir.actions.report", "render_report", [action.id, activeIds, action.data || {}], { context });
        // or a JSON-RPC controller: await rpc("/pentaho/preview", { report_id: action.id, ids: activeIds });
        await download({
            url: "/pentaho/download",               // type='http' route, POST, csrf_token appended automatically
            data: { token: result.token, context: JSON.stringify(context) },
        });
        notification.add(_t("Report generated"), { type: "success" });
    } catch (error) {
        notification.add(error.message || String(error), { type: "danger", title: _t("Pentaho report"), sticky: true });
        throw error;
    } finally {
        ui.unblock();
    }
    options.onClose?.();   // core also does this when you return truthy (action_service.js:1352-1357)
    return true;           // truthy => core stops; falsy => core falls through to qweb handling
}

registry.category("ir.actions.report handlers").add("pentaho_report_handler", pentahoReportHandler);
```

Fields available on `action` in the handler: only those returned by `ir.actions.report._get_readable_fields()` (odoo/addons/base/models/ir_actions_report.py:212-222: report_name, report_type, target, context, data, close_on_report_download, domain + base set at odoo/addons/base/models/ir_actions.py:245-256: id, name, type, display_name, help, xml_id, path, binding_*). Any custom pentaho_* column you want in the JS action dict must be added by overriding `_get_readable_fields` — addons/web/controllers/utils.py:23-46 `clean_action` strips everything else (and /web/action/load at addons/web/controllers/action.py:45-46 sets bin_size=True for report actions). Methods invoked via orm.call must be public and not @api.private (odoo/service/model.py:50-71).

### Download helper

`import { download } from "@web/core/network/download"` — addons/web/static/src/core/network/download.js:479-509: `download({ url, data })` POSTs a FormData built from `data` (plus `token` and `csrf_token` from odoo.csrf_token, :498-501) via XHR with responseType blob, reads the `Content-Disposition` filename (:529-531) and saves the blob (:534-536); non-200 / text/html responses are decoded as a serialized Odoo error and rejected with makeErrorFromResponse (:540-567); 502 -> ConnectionLostError. Also `download({ form })` for an existing <form>. Sibling `downloadFile(data, filename, mimetype)` (:462-465) saves in-memory data. For printing in a new tab nothing special exists: use `browser.open(url)` from `@web/core/browser/browser` or `window.open` against your own `type='http'` GET route that returns `content_disposition(filename, 'inline')`. The core's own report path is downloadReport() at addons/web/static/src/webclient/actions/reports/utils.js:65-86 which POSTs to /report/download — that controller returns None for non-qweb types (addons/web/controllers/report.py:107-136, `else: return`), so it cannot be reused for 'pentaho'. session.get_file does NOT exist in this version.

### Block UI

`env.services.ui.block()` / `env.services.ui.unblock()` (ref-counted) — addons/web/static/src/core/ui/ui_service.js:169-191; `ui.isBlocked` getter :219-221; block accepts optional `{ message, delay }` (:170-179). Core uses it exactly this way around report downloads at action_service.js:1365-1372. No blockUI/unblockUI framework functions exist.

### Notification

`env.services.notification.add(message, options)` — addons/web/static/src/core/notifications/notification_service.js:43-55; options (typedef :13-20): title, type ('warning'|'danger'|'success'|'info'), sticky (default false), autocloseDelay (default 4000), className, onClose, buttons [{name, icon, primary, onClick}]. Returns a close function. In components: `useService("notification")`. Core example for reports at action_service.js:1374-1379.

### ES module (`/** @odoo-module **/`) supported

True

### Assets

Manifest `'assets'` key ONLY. odoo/modules/module.py:64 has `'assets': {}` in _DEFAULT_MANIFEST; odoo/addons/base/models/ir_asset.py:190-193 builds bundles from `Manifest.for_addon(addon)['assets'].get(bundle, ())` for every installed addon. No `web.assets_backend` ir.ui.view/template record exists anywhere in addons/web (grep for id="assets_backend" / id="assets_common" in addons/web/**/*.xml returns nothing; web/__manifest__.py:49 defines 'web.assets_backend' as a manifest bundle), so an XML `<template inherit_id="web.assets_backend">` would fail with a missing-external-id error at install. Example: ../enterprise/iot/__manifest__.py:28-30. Files under `<addon>/static/src` are transpiled as ES modules automatically — odoo/tools/js_transpiler.py:715-727 `is_odoo_module()` returns True for any url starting with `/<addon>/static/src` or `/<addon>/static/tests` regardless of the `/** @odoo-module **/` comment; the comment is only needed (and still honoured, with optional `alias=`/`default=`/`ignore`) for files outside those folders (ODOO_MODULE_RE :702-710). Transpilation hook: odoo/addons/base/models/assetsbundle.py:815-827.

### Views: conditional attribute syntax

Python-expression attributes only: `invisible="report_type != 'pentaho'"`, `required="report_type == 'pentaho'"`, `readonly="..."`, `column_invisible="..."` (VIEW_MODIFIERS at odoo/addons/base/models/ir_ui_view.py:34). The old `attrs="{...}"` / `states="..."` forms are REJECTED at view validation: ir_ui_view.py:492-497 raises ValidationError 'Since 17.0, the "attrs" and "states" attributes are no longer used.' Expressions are validated server-side (`_validate_attributes` :2145-2153 -> `_validate_expression` :2370) and every field referenced in them must be present in the view (`_postprocess_attributes` :1625-1630 -> name_manager.must_have_fields); `report_type` is already in the form so it can be referenced freely. Core example in the same form: `invisible="report_type != 'qweb-pdf'"` at odoo/addons/base/views/ir_actions_views.xml:89.

### Views: report form xmlid

base.act_report_xml_view — odoo/addons/base/views/ir_actions_views.xml:55-111 (model ir.actions.report, `<form string="Report">`). It contains `<field name="report_type"/>` at line 87 (inside the first `<group>` of `<group>` at :84-90), so `<xpath expr="//field[@name='report_type']" position="after">` (or `<field name="report_type" position="after">`) anchors correctly. Other anchors: notebook with pages name="security" (:97) and name='advanced' (:100); button_box div name="button_box" (:61). List view: base.act_report_xml_view_tree (:112-124, tag is `<list>` not `<tree>`, has report_type at :121).

`report_type` field present in form: True

### Views: report search xmlid

base.act_report_xml_search_view — odoo/addons/base/views/ir_actions_views.xml:126-140; contains `<field name="name" .../>` (:130), `<field name="model" .../>` (:134) and a `<group colspan="4">` with filters name="report_type" (:136) and name="report_model" (:137) to anchor on.

### Routes: JSON route type

'jsonrpc' — odoo/http.py:740-742 docstring `:param str type: The type of request, either 'jsonrpc' or 'http'`; JsonRPCDispatcher.routing_type = 'jsonrpc' at odoo/http.py:2512-2514. Core usage: addons/web/controllers/action.py:22 `@route('/web/action/load', type='jsonrpc', auth='user', readonly=True)`; addons/web/controllers/report.py:153. A third dispatcher 'json2' (plain JSON body, non-JSON-RPC envelope, returns raw JSON or a Response) also exists at http.py:2596-2657.

### Routes: is type='json' still accepted

Yes, as a deprecated alias: odoo/http.py:783-789 — `if routing.get('type') == 'json': warnings.warn("Since 19.0, @route(type='json') is a deprecated alias to @route(type='jsonrpc')", DeprecationWarning, stacklevel=3); routing['type'] = 'jsonrpc'`. Then :790-791 asserts the type is one of the registered dispatchers ('http', 'jsonrpc', 'json2'). Use type='jsonrpc' to avoid the warning.

### Routes: content_disposition

`from odoo.http import content_disposition` — odoo/http.py:350-365: `def content_disposition(filename, disposition_type='attachment')`; disposition_type must be 'attachment' or 'inline' (ValueError otherwise, :359-361); returns `"{type}; filename*=UTF-8''{url_quote(filename)}"` per RFC6266. Core usage: addons/web/controllers/report.py:136 `response.headers.add('Content-Disposition', content_disposition(filename))`. Note the JS download helper parses that header to pick the filename (download.js:529-531).

### Routes: request.make_response

`request.make_response(self, data, headers=None, cookies=None, status=200)` — odoo/http.py:2021-2042; headers is a list of (name, value) tuples, cookies a Mapping applied via response.set_cookie(k, v). Companion `request.make_json_response(data, headers=None, cookies=None, status=200)` at :2044-2060. PDF pattern from core: addons/web/controllers/report.py:43-44 `request.make_response(pdf, headers=[('Content-Type', 'application/pdf'), ('Content-Length', len(pdf))])`. type='http' POST routes enforce CSRF by default (HttpDispatcher.dispatch http.py:2461-2471: token popped from params, BadRequest 'Session expired (invalid CSRF token)' if invalid) — `download()` from JS appends csrf_token automatically; GET is exempt (SAFE_HTTP_METHODS). For the form-POST `token` param the JS always sends `token=dummy-because-api-expects-one` (download.js:498), so accept a `token=None` kwarg or `**kw`.

### Routes: JSON request shape

Yes: JsonRPCDispatcher.dispatch (odoo/http.py:2555-2567) does `self.request.params = dict(self.jsonrequest.get('params', {}), **args)` (args = URL path params) and then `ir.http._dispatch(endpoint)` -> `endpoint(**request.params)` (odoo/addons/base/models/ir_http.py:349-355). So `@http.route('/pentaho/preview', type='jsonrpc', auth='user') def preview(self, report_id, ids=None, data=None, **kw)` receives the JSON-RPC `params` object as kwargs; a `context` key in params replaces the session context and is removed before the call (:2537-2539 doc). The return value is wrapped as `{'jsonrpc': '2.0', 'id': ..., 'result': <value>}` (:2603-2610); exceptions become `{'error': {code, message, data: serialize_exception(exc)}}` (:2581-2601). `request.jsonrequest` NO LONGER EXISTS on Request (http.py:1773 comment only sets params); the raw body is `request.dispatcher.jsonrequest` (:2518/2556) or `request.get_json_data()` (:1981-1982). Request type is inferred from Content-Type: a JSON-RPC route hit without `application/json`/`application/json-rpc` mimetype (JsonRPCDispatcher.mimetypes :2514, is_compatible_with :2521-2523) gets HTTP 415 UnsupportedMediaType from `_set_request_dispatcher` (:2165-2182); http routes accept anything (HttpDispatcher.is_compatible_with returns True :2446-2448).

### ORM: create decorator

Yes. `odoo.api.model_create_multi` is re-exported at odoo/api/__init__.py:5-18 (odoo/api.py is now a package; implementation in odoo/orm/decorators.py:353-370: wraps a single dict into a list and sets `_api_model = True`). `@api.model` applied to a method literally named `create` is auto-upgraded to model_create_multi (decorators.py:316-317). `model_create_single` does NOT exist (verified: `'model_create_single' in dir(odoo.api)` is False). Core pattern for the same model family: odoo/addons/base/models/ir_actions.py:109-119 `@api.model_create_multi def create(self, vals_list): res = super().create(vals_list); self.env.registry.clear_cache(); return res` and `def write(self, vals): res = super().write(vals); ...`. Note the parent ir.actions.actions create/write already clear the registry cache.

### ORM: selection_add / ondelete

Supported AND REQUIRED here. odoo/orm/fields_selection.py:120-170: `selection_add` extends the parent list; `ondelete` is a dict {new_value: policy} with policies 'set null' (default), 'cascade', 'set default', 'set <value>' or a callable (:39-57, :144-165). Because `ir.actions.report.report_type` is `required=True` (odoo/addons/base/models/ir_actions_report.py:170-174), fields_selection.py:134-141 raises ValueError("required selection fields must define an ondelete policy that implements the proper cleanup ... 'set default' (if the field has a default defined), 'cascade', or a single-argument callable") if any added value resolves to 'set null'. So you must write e.g. `report_type = fields.Selection(selection_add=[('pentaho', 'Pentaho')], ondelete={'pentaho': 'cascade'})` (or 'set default' — the base field has default='qweb-pdf').

### ORM: cr.savepoint()

Yes: `with self.env.cr.savepoint():` — odoo/sql_db.py:217-226 `def savepoint(self, flush: bool = True) -> Savepoint` on BaseCursor returns a context-manager Savepoint (class at :87-; rolled back on exception, released on success; `flush=False` skips the pre/post flush hooks).

### ORM: config['addons_path'] type

list. odoo/tools/config.py:243 `--addons-path` has type='addons_path', my_default=[] and `_check_addons_path` (:785-797) returns a list of normalized existing directories; the option's formatter is `_format_list` (:72). Verified at runtime with the venv: `type(odoo.tools.config['addons_path'])` is `<class 'list'>`. Code that did `config['addons_path'].split(',')` must iterate the list instead.

### ORM: has_group

`self.env.user.has_group('module.xml_id')` — odoo/addons/base/models/res_users.py:1065-1082 (`@api.readonly def has_group(self, group_ext_id: str) -> bool`, ensure_one, AccessError if called on a user other than the current one by a non-internal user; `base.group_no_one` only true in debug). `has_groups('a,b,!c')` comma spec at :1033-1063; private `_has_group` at :1085. Prefer `self.env.user.has_group(...)` rather than the legacy `self.env['res.users'].has_group(...)` model-level call (the method now calls ensure_one). Also available: `_is_internal/_is_public/_is_system/_is_admin` (:1165-1181).

### ORM: res.users.share

Yes: `share = fields.Boolean(compute='_compute_share', compute_sudo=True, string='Share User', store=True, ...)` at odoo/addons/base/models/res_users.py:234.

### ORM: _() usage

`from odoo import _` still works (odoo/init.py:38-42 sets odoo._ and odoo._lt from odoo.tools.translate; `_ = get_text_alias` at odoo/tools/translate.py:677, `_lt = LazyGettext` :678). Signature is `_(source: str, /, *args, **kwargs)` (translate.py:574-578): pass format args INTO the call — `_('Report %s not found', name)` or `_('%(a)s / %(b)s', a=x, b=y)`; args and kwargs may not be mixed (assert :575). Formatting is applied in get_translation (:414-452) with `translation % args`. The old `_('...') % x` is not warned at runtime (it's plain str %), but the repo lint checker odoo/addons/test_lint/tests/_odoo_checker_gettext.py flags it (E8502 'gettext-variable', E8505 multiple unnamed placeholders, E8506 %r, E8507 UserError/ValidationError/AccessError with a non-gettext static string). Also available: `self.env._(...)` (odoo/orm/environments.py:315) which uses the env's language, and `LazyTranslate(__name__)` for module-level strings (translate.py:656-674).

### Report model: name

ir.actions.report (`_name = 'ir.actions.report'`, `_table = 'ir_act_report_xml'`, `_inherit = ['ir.actions.actions']`, `_allow_sudo_commands = False`) — odoo/addons/base/models/ir_actions_report.py:155-161. `ir.actions.report.xml` does not exist (only the table name keeps the old suffix).

### Report model: report_type values

[('qweb-html', 'HTML'), ('qweb-pdf', 'PDF'), ('qweb-text', 'Text')], required=True, default='qweb-pdf' — odoo/addons/base/models/ir_actions_report.py:170-178. Other fields on the model (:163-191): type, binding_type(default 'report'), model (Char, required), model_id (computed M2o), report_name (Char required, 'Template Name'), report_file (Char, not required), group_ids (M2m res.groups — not `groups_id`), multi, paperformat_id, print_report_name (translate=True), attachment_use, attachment, domain.

### Report model: render dispatch

`@api.model def _render(self, report_ref, res_ids, data=None)` at odoo/addons/base/models/ir_actions_report.py:1144-1150: `report = self._get_report(report_ref); report_type = report.report_type.lower().replace('-', '_'); render_func = getattr(self, '_render_' + report_type, None); if not render_func: return None; return render_func(report_ref, res_ids, data=data)`. So for report_type 'pentaho' define `@api.model def _render_pentaho(self, report_ref, res_ids, data=None)` (underscore prefix, positional (report_ref, res_ids), keyword data) returning a 2-tuple `(content_bytes, 'pdf')` like `_render_qweb_pdf` (:1033, returns `pdf_content, 'pdf'` :1101), `_render_qweb_text` (:1103-1110, returns `(str, 'text')`) and `_render_qweb_html` (:1112-1119, returns `(str, 'html')`). There is no public `render_*` dispatch. mail.template relies on this: addons/mail/models/mail_template.py:368-374 calls `_render_qweb_pdf` for qweb types and `self.env['ir.actions.report']._render(report, [res_id])` for any other type, raising UserError 'Unsupported report type' if it returns falsy and unpacking `report_content, report_format = render_res` — so implementing `_render_pentaho` makes the report usable as an email attachment. `report_ref` may be an id, xml id, report_name or record (`_get_report`). `report_action(docids, data=None, config=True)` at :1152-1185 builds the action dict sent to the client (:1172-1180, includes report_type/report_name/report_file/context/data).

### Report model: Binary attachment default

fields.Binary stores in ir.attachment by default: odoo/orm/fields_binary.py:30-40 `attachment = True`, `prefetch = False`, `_depends_context = ('bin_size',)`; `column_type` is None when attachment=True (:42-44) and `store=False` forces attachment=False (:46-50). Pass `attachment=False` to get a bytea column. Remember /web/action/load sets bin_size=True for report actions (addons/web/controllers/action.py:45-46), so a Binary included in the action dict would arrive as a size string, not content.

### Report model: Print-menu binding

On ir.actions.actions (odoo/addons/base/models/ir_actions.py:73-78): `binding_model_id = fields.Many2one('ir.model', ondelete='cascade')`, `binding_type = fields.Selection([('action','Action'),('report','Report')], required=True, default='action')` (ir.actions.report overrides default to 'report' at ir_actions_report.py:164), `binding_view_types = fields.Char(default='list,form')`. In XML use `<field name="binding_model_id" ref="model_<model_underscored>"/>` plus `<field name="model">the.model</field>` (Char, required). Helper methods `create_action()` / `unlink_action()` at ir_actions_report.py:243-254 set/clear binding_model_id; the Print menu is built from `ir.actions.actions.get_bindings(model_name)` (:155-215) keyed by binding_type. `groups_id` was renamed to `group_ids` on ir.actions.report (:181) — XML/data referencing `groups_id` will fail.

### Tests: TransactionCase conventions

`odoo.tests.common.TransactionCase` (odoo/tests/common.py:1020-1199): one transaction per class, each test method inside a savepoint; docstring (:1026-1029) says shared data belongs in `@classmethod setUpClass(cls)` (call `super().setUpClass()`; `cls.env` is available). `setUp(self)` still works for per-test setup (:1121). `SavepointCase` does NOT exist (grep in odoo/tests/*.py returns nothing) — use TransactionCase. `SingleTransactionCase` exists (:1201). `odoo.tests.common.new_test_user(env, login, groups=..., context=...)` is available (used at addons/web/tests/test_login.py:12-13). `odoo.tests` re-exports everything from common plus `Form` (odoo/tests/__init__.py:8-10).

### Tests: HttpCase

`odoo.tests.common.HttpCase(TransactionCase)` at odoo/tests/common.py:2212; `registry_test_mode = True`; setUpClass sets web.base.url (:2222-2232). `self.authenticate(user, password, *, browser=None, session_extra=None)` (:2374) creates a session and sets the cookie on `self.opener`; `self.logout(keep_db=True)` (:2370). `self.url_open(url, data=None, files=None, timeout=12, headers=None, json=None, params=None, allow_redirects=True, cookies=None, method=None)` (:2338-2344): relative URLs are prefixed with base_url(); POST is inferred when data/files/json given. For a JSON-RPC route use `self.make_jsonrpc_request(route, params=None, headers=None, cookies=None, timeout=12)` (:2624-2645) which POSTs `{'id':0,'jsonrpc':'2.0','method':'call','params':...}` with json= (so Content-Type application/json), raises requests.HTTPError on bad status and `JsonRpcException` on a JSON-RPC error, and returns `result`. Equivalent manual form: `self.url_open('/pentaho/preview', json={'jsonrpc': '2.0', 'method': 'call', 'params': {...}, 'id': 1})` — sending with data= (form-encoded) would get a 415 because the dispatcher is chosen by Content-Type (odoo/http.py:2165-2182). For a POST to a `type='http'` route include the CSRF token: `self.url_open('/pentaho/download', data={..., 'csrf_token': odoo.http.Request.csrf_token(self)})` exactly as addons/web/tests/test_pivot_export.py:30-36 does; then `response.raise_for_status()` and inspect `response.headers['Content-Disposition']` / `response.content`. GET requests need no token.

### Tests: tagged

`from odoo.tests import tagged` (or odoo.tests.common.tagged) — odoo/tests/common.py:2728-2750; classes default to {'standard','at_install'}; e.g. `@tagged('post_install', '-at_install')`. A class that is neither at_install nor post_install triggers a warning (:2745-2748).

### Tests: run command

`./odoo-bin -d <fresh_db> --addons-path=addons,../enterprise,/path/to/custom -i pentaho_reports --test-enable --test-tags /pentaho_reports --stop-after-init` (add `--without-demo` if you don't want demo data; it is now the default per odoo/tools/config.py:235-236, pass `--without-demo=False`/`--with-demo` to load demo). Flags verified in odoo/tools/config.py: `-i/--init` :227, `-u/--update` :229, `--test-enable` :285-286 ('Implies --stop-after-init'), `-t/--test-tags` :287-307 (spec `[-][tag][/module][:class][.method][[params]]`, e.g. `--test-tags /pentaho_reports:TestPentahoHttp.test_download`; setting test-tags alone enables tests), `--test-file <path.py>` :283 (converted to a tag, :704-713), `--stop-after-init` :431, `-d` :369. Tests run twice (after install = at_install tags, at end of loading = post_install tags) (:302-307). HttpCase tests need the HTTP server, which odoo-bin starts in this mode.

### Other port tripwires

1) Custom ir.actions.report columns are invisible to the JS handler unless you override `_get_readable_fields` (odoo/addons/base/models/ir_actions_report.py:212-222; stripped by addons/web/controllers/utils.py:23-46 which also logs a warning about 'custom properties'). 2) `ir.actions.report.groups_id` is now `group_ids` (:181). 3) The stock `/report/download` controller returns None (empty 200) for non-qweb types (addons/web/controllers/report.py:107-137) and `/report/pdf|html|text/<name>` call `_render_qweb_*` directly (:38-48) — your own `/pentaho/download` & `/pentaho/print` routes are mandatory. 4) `_render_pentaho` must return a `(bytes, 'pdf')` tuple so `_render()` (:1144-1150) and mail.template (addons/mail/models/mail_template.py:368-374) work. 5) The `report_file` field is not required (:180), `report_name` is (:179) — a Pentaho report still needs a unique report_name since `_get_report_from_name` is used by core routes. 6) The http layer picks the dispatcher from the request Content-Type and returns 415 on mismatch (odoo/http.py:2165-2182); `request.jsonrequest` is gone (use `request.get_json_data()` :1981 or `request.dispatcher.jsonrequest`). `readonly=True` on routes is available (http.py:768-770) and `@api.readonly` exists for model methods (odoo/orm/decorators.py:341-350) — do not mark render_report readonly if it writes attachments. 7) The list view tag is `<list>` (ir_actions_views.xml:116) — an inherited list/tree view using `<tree>` xpaths will not match. 8) `odoo.api` is a package (odoo/api/__init__.py) and fields live in odoo/orm/*; `from odoo import api, fields, models, _` still works. 9) `self.env.user.has_group` now requires a single user (ensure_one, res_users.py:1073). 10) Binary fields default to attachment storage and `/web/action/load` uses bin_size=True for report actions. 11) Views: `<field ... groups=...>` and `invisible=` python expressions only; `attrs`/`states` raise at install (ir_ui_view.py:492-497). 12) JS: no `web.core`, `web.session`, `session.get_file`, `framework.blockUI`, `crash_manager`; imports are `@web/core/registry`, `@web/core/network/rpc` (`rpc(url, params, settings)` rpc.js:93), `@web/core/network/download`, `@web/core/l10n/translation` (`_t`), `@web/core/user` (`user.context`), `@web/core/browser/browser`; ORM via `env.services.orm.call(model, method, args, kwargs)` (addons/web/static/src/core/orm_service.js:126-141). Test bundles: `web.assets_unit_tests` (hoot) / `web.assets_tests` (tours) per ../enterprise/iot/__manifest__.py:32-40. 13) `--without-demo` is now the default (config.py:235-236), so tests relying on demo data must be run with demo enabled explicitly. 14) Chrome-based `browser_js`/`start_tour` helpers exist on HttpCase (:2466, :2571) if you want to assert the handler end-to-end.
