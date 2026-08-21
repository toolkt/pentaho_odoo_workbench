odoo.define('pentaho_reports.ActionManager', function (require) {
"use strict";

/**
 * Pentaho report actions on the legacy web client (Odoo 11).
 *
 * Core's ReportActionManager handles qweb-* types only and rejects anything
 * else, so we layer an include on top of it (the explicit require pins the
 * load order) and take over report_type 'pentaho': ORM call render_report →
 * file download through /pentaho/download (session.get_file POSTs a form
 * with token + csrf_token and polls for the fileToken cookie the route sets;
 * its complete callback unblocks the UI) or direct print.
 *
 * Everything is jQuery 1.11 Deferreds ($.Deferred / .then(ok, fail)):
 * native Promises would not chain through _rpc's deferreds.
 */
var ActionManager = require('web.ActionManager');
require('report.report');  // core qweb handling; our include must layer on top of it
var core = require('web.core');
var framework = require('web.framework');
var session = require('web.session');

var _t = core._t;

function rejected(message) {
    return $.Deferred().reject(new Error(message)).promise();
}

function getBrowserInfo() {
    var ua = navigator.userAgent.toLowerCase();
    return {
        isFirefox: ua.indexOf('firefox') > -1,
        isChrome: ua.indexOf('chrome') > -1 && ua.indexOf('edg') === -1,
        isEdge: ua.indexOf('edg') > -1,
        isSafari: ua.indexOf('safari') > -1 && ua.indexOf('chrome') === -1,
    };
}

/**
 * Human-readable text from the three error shapes we can receive:
 *  - our own `Error` (message is a string),
 *  - a `_rpc` rejection `{message: <odoo error>, event}` (text at message.data.message),
 *  - a `session.get_file` error: the parsed Odoo exception `{message, data: {message, ...}}`.
 */
function errorMessage(error) {
    var payload = (error && error.message && typeof error.message === 'object') ? error.message : error;
    if (payload && payload.data && payload.data.message) {
        return payload.data.message;
    }
    if (payload && typeof payload.message === 'string') {
        return payload.message;
    }
    return _t('Unknown error');
}

/** Open the PDF in a new tab through /pentaho/print (Firefox prints from there). */
function printPDFInNewWindow(contentB64, outputType, fileName) {
    var def = $.Deferred();
    var url = '/pentaho/print?data=' + encodeURIComponent(JSON.stringify([contentB64, outputType, fileName]));
    var win = window.open(url, '_blank');
    if (!win) {
        return rejected(_t('Popup blocked. Please allow popups for this site.'));
    }
    var check = setInterval(function () {
        if (win.closed) { clearInterval(check); def.resolve(); }
    }, 500);
    setTimeout(function () { clearInterval(check); def.resolve(); }, 30000);
    return def.promise();
}

/** Print.js (bundled as print_min.js) for Chrome/Edge. */
function printWithPrintJS(contentB64) {
    var def = $.Deferred();
    if (!window.printJS) {
        return rejected('Print.js not loaded');
    }
    try {
        window.printJS({
            printable: contentB64,
            type: 'pdf',
            base64: true,
            onPrintDialogClose: function () { def.resolve(); },
            onError: function (error) { def.reject(error); },
        });
    } catch (e) {
        def.reject(e);
    }
    return def.promise();
}

function downloadReport(contentB64, outputType, fileName) {
    var def = $.Deferred();
    var ok = session.get_file({
        url: '/pentaho/download',
        data: { data: JSON.stringify([contentB64, outputType, fileName]) },
        success: function () { def.resolve(); },
        error: function (error) { def.reject(error); },
        complete: framework.unblockUI,
    });
    if (!ok) {
        return rejected(_t('A popup window with your report was blocked.'));
    }
    return def.promise();
}

ActionManager.include({
    /**
     * @override
     */
    ir_actions_report: function (action, options) {
        if (action.report_type !== 'pentaho') {
            return this._super.apply(this, arguments);
        }
        return this._executePentahoReportAction(action, options);
    },

    _executePentahoReportAction: function (action, options) {
        var self = this;
        var context = action.context || {};
        var data = action.data || {};
        var activeIds = context.active_ids || [];

        framework.blockUI();
        return this._rpc({
            model: 'ir.actions.report',
            method: 'search_read',
            args: [[['report_name', '=', action.report_name]], ['id']],
            kwargs: { limit: 1 },
        }).then(function (reports) {
            if (!reports.length) {
                return rejected(_t('Report %s not found').replace('%s', action.report_name));
            }
            return self._rpc({
                model: 'ir.actions.report',
                method: 'render_report',
                args: [reports[0].id, activeIds, data],
                context: context,
            });
        }).then(function (result) {
            if (!result) {
                return rejected(_t('No data returned from report'));
            }
            var contentB64 = result[0], outputType = result[1], fileName = result[2], directPrint = result[3];
            if (data.variables && data.variables.filename) {
                fileName = data.variables.filename.replace(/\.[^/.]+$/, '');
            }
            if (directPrint && outputType === 'pdf') {
                var browser = getBrowserInfo();
                var printing = browser.isFirefox
                    ? printPDFInNewWindow(contentB64, outputType, fileName)
                    : printWithPrintJS(contentB64).then(null, function () {
                        return printPDFInNewWindow(contentB64, outputType, fileName);
                    });
                return printing.then(function () {
                    framework.unblockUI();
                    self.do_notify(_t('Report'), _t('Report sent to printer'));
                }, function () {
                    self.do_warn(_t('Report'), _t('Print failed. Downloading file instead.'));
                    return downloadReport(contentB64, outputType, fileName);
                });
            }
            return downloadReport(contentB64, outputType, fileName);
        }).then(function () {
            if (action.close_on_report_download) {
                return self.do_action({ type: 'ir.actions.act_window_close' }, _.pick(options, 'on_close'));
            }
            if (options && options.on_close) {
                options.on_close();
            }
        }, function (error, event) {
            framework.unblockUI();
            if (event && typeof event.preventDefault === 'function') {
                event.preventDefault();   // we show our own notification; skip the core crash dialog
            }
            self.do_warn(_t('Error generating report'), errorMessage(error), true);
            return $.Deferred().reject(error).promise();
        });
    },
});

});
