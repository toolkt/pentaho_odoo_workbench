odoo.define('pentaho_reports.ActionManager', function (require) {
"use strict";

/**
 * Pentaho report actions on the legacy web client (Odoo 12-14).
 *
 * Core's ReportActionManager handles qweb-* types only and rejects anything
 * else (console.error + Promise.reject), so we layer an include on top of it
 * (the explicit require pins the load order) and take over report_type
 * 'pentaho': ORM call render_report → file download through /pentaho/download
 * (on 12-14 session.get_file POSTs a form with token + csrf_token; its
 * complete callback unblocks the UI — on 11/12 that callback is driven by
 * the fileToken cookie the route sets) or direct print.
 */
var ActionManager = require('web.ActionManager');
require('web.ReportActionManager');
var core = require('web.core');
var framework = require('web.framework');
var session = require('web.session');

var _t = core._t;

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
    return new Promise(function (resolve, reject) {
        var url = '/pentaho/print?data=' + encodeURIComponent(JSON.stringify([contentB64, outputType, fileName]));
        var win = window.open(url, '_blank');
        if (!win) {
            reject(new Error(_t('Popup blocked. Please allow popups for this site.')));
            return;
        }
        var check = setInterval(function () {
            if (win.closed) { clearInterval(check); resolve(); }
        }, 500);
        setTimeout(function () { clearInterval(check); resolve(); }, 30000);
    });
}

/** Print.js (bundled as print_min.js) for Chrome/Edge. */
function printWithPrintJS(contentB64) {
    return new Promise(function (resolve, reject) {
        if (!window.printJS) {
            reject(new Error('Print.js not loaded'));
            return;
        }
        try {
            window.printJS({
                printable: contentB64,
                type: 'pdf',
                base64: true,
                onPrintDialogClose: resolve,
                onError: reject,
            });
        } catch (e) {
            reject(e);
        }
    });
}

function downloadReport(contentB64, outputType, fileName) {
    return new Promise(function (resolve, reject) {
        var ok = session.get_file({
            url: '/pentaho/download',
            data: { data: JSON.stringify([contentB64, outputType, fileName]) },
            success: resolve,
            error: function (error) { reject(error); },
            complete: framework.unblockUI,
        });
        if (!ok) {
            reject(new Error(_t('A popup window with your report was blocked.')));
        }
    });
}

ActionManager.include({
    /**
     * @override
     */
    _executeReportAction: function (action, options) {
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
                throw new Error(_t('Report %s not found').replace('%s', action.report_name));
            }
            return self._rpc({
                model: 'ir.actions.report',
                method: 'render_report',
                args: [reports[0].id, activeIds, data],
                context: context,
            });
        }).then(function (result) {
            if (!result) {
                throw new Error(_t('No data returned from report'));
            }
            var contentB64 = result[0], outputType = result[1], fileName = result[2], directPrint = result[3];
            if (data.variables && data.variables.filename) {
                fileName = data.variables.filename.replace(/\.[^/.]+$/, '');
            }
            if (directPrint && outputType === 'pdf') {
                var browser = getBrowserInfo();
                var printing = browser.isFirefox
                    ? printPDFInNewWindow(contentB64, outputType, fileName)
                    : printWithPrintJS(contentB64).catch(function () {
                        return printPDFInNewWindow(contentB64, outputType, fileName);
                    });
                return printing.then(function () {
                    framework.unblockUI();
                    self.displayNotification({ type: 'success', title: _t('Report'), message: _t('Report sent to printer') });
                }, function () {
                    self.displayNotification({ type: 'warning', title: _t('Report'), message: _t('Print failed. Downloading file instead.') });
                    return downloadReport(contentB64, outputType, fileName);
                });
            }
            return downloadReport(contentB64, outputType, fileName);
        }).then(function () {
            if (action.close_on_report_download) {
                return self.doAction({ type: 'ir.actions.act_window_close' }, _.pick(options, 'on_close'));
            }
            if (options && options.on_close) {
                options.on_close();
            }
        }).catch(function (error) {
            framework.unblockUI();
            if (error && error.event && typeof error.event.preventDefault === 'function') {
                error.event.preventDefault();   // we show our own notification; skip the core crash dialog
            }
            self.displayNotification({ type: 'danger', title: _t('Error generating report'), message: errorMessage(error), sticky: true });
        });
    },
});

});
