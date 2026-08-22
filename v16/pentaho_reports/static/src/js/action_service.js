/** @odoo-module **/

import { registry } from "@web/core/registry";
import { download } from "@web/core/network/download";

/**
 * Detect browser type
 */
function getBrowserInfo() {
    const userAgent = navigator.userAgent.toLowerCase();
    return {
        isFirefox: userAgent.indexOf('firefox') > -1,
        isChrome: userAgent.indexOf('chrome') > -1 && userAgent.indexOf('edg') === -1,
        isEdge: userAgent.indexOf('edg') > -1,
        isSafari: userAgent.indexOf('safari') > -1 && userAgent.indexOf('chrome') === -1
    };
}

/**
 * Print PDF using new window method (works best in Firefox)
 * This opens the PDF in a new tab/window where Firefox can properly render and print it
 */
function printPDFInNewWindow(contentB64, outputType, reportFileName) {
    return new Promise((resolve, reject) => {
        try {
            // Open the PDF in a new window using the print controller
            const printUrl = `/pentaho/print?data=${encodeURIComponent(JSON.stringify([contentB64, outputType, reportFileName]))}`;
            const printWindow = window.open(printUrl, '_blank');
            
            if (!printWindow) {
                reject(new Error('Popup blocked. Please allow popups for this site.'));
                return;
            }
            
            // Set up a timer to check when the window is closed
            const checkInterval = setInterval(() => {
                if (printWindow.closed) {
                    clearInterval(checkInterval);
                    resolve();
                }
            }, 500);
            
            // Timeout after 30 seconds
            setTimeout(() => {
                clearInterval(checkInterval);
                resolve();
            }, 30000);
            
        } catch (error) {
            reject(error);
        }
    });
}

/**
 * Print PDF using Print.js for Chrome/Edge
 */
function printWithPrintJS(contentB64, reportFileName) {
    return new Promise((resolve, reject) => {
        if (!window.printJS) {
            reject(new Error('Print.js not loaded'));
            return;
        }
        
        try {
            window.printJS({
                printable: contentB64,
                type: 'pdf',
                base64: true,
                onPrintDialogClose: () => {
                    // console.log('Print dialog closed');
                    resolve();
                },
                onError: (error) => {
                    // console.error('Print.js error:', error);
                    reject(error);
                }
            });
        } catch (error) {
            reject(error);
        }
    });
}

/**
 * Handler for Pentaho report actions.
 * This handler intercepts report actions with report_type='pentaho'
 * and processes them appropriately.
 */
async function pentahoReportHandler(action, options, env) {
    if (action.report_type === "pentaho") {
        const _t = env._t;
        const { 
            report_name, 
            context = {}, 
            data = {} 
        } = action;
        
        try {
            // Block UI while generating report
            env.services.ui.block();
            
            // Get the report record
            const reportIds = await env.services.orm.searchRead(
                "ir.actions.report",
                [["report_name", "=", report_name]],
                ["id"],
                { limit: 1 }
            );
            
            if (!reportIds || reportIds.length === 0) {
                throw new Error(`Report ${report_name} not found`);
            }
            
            const reportId = reportIds[0].id;
            
            // Prepare context for the report
            const reportContext = {
                active_ids: context.active_ids || [],
                active_model: context.active_model || null,
            };
            
            // Call render_report with proper arguments
            const result = await env.services.orm.call(
                "ir.actions.report",
                "render_report",
                [reportId, reportContext.active_ids, data]
            );
            
            if (!result) {
                throw new Error("No data returned from report");
            }
            
            // result should be [content_base64, output_type, report_name, direct_print]
            const [contentB64, outputType, reportFileName, directPrint] = result;
            
            // If custom filename was passed in data, use it
            let finalFileName = reportFileName;
            if (data && data.variables && data.variables.filename) {
                // Extract filename without extension if provided
                finalFileName = data.variables.filename.replace(/\.[^/.]+$/, "");
            }
            
            // Check if we should print directly
            if (directPrint && outputType === 'pdf') {
                const browserInfo = getBrowserInfo();
                
                try {
                    if (browserInfo.isFirefox) {
                        // For Firefox, open PDF in new window
                        await printPDFInNewWindow(contentB64, outputType, finalFileName);
                        env.services.notification.add(
                            _t("Report opened in new window for printing"),
                            { type: "info" }
                        );
                    } else {
                        // For Chrome/Edge, try Print.js first
                        try {
                            await printWithPrintJS(contentB64, finalFileName);
                            env.services.notification.add(
                                _t("Report sent to printer"),
                                { type: "success" }
                            );
                        } catch (printJsError) {
                            // Fallback to new window method
                            // console.warn('Print.js failed, using new window method:', printJsError);
                            await printPDFInNewWindow(contentB64, outputType, finalFileName);
                            env.services.notification.add(
                                _t("Report opened in new window for printing"),
                                { type: "info" }
                            );
                        }
                    }
                } catch (printError) {
                    // console.error("Error printing:", printError);
                    // Fallback to download
                    env.services.notification.add(
                        _t("Print failed. Downloading file instead."),
                        { type: "warning" }
                    );
                    await download({
                        url: "/pentaho/download",
                        data: {
                            data: JSON.stringify([contentB64, outputType, finalFileName]),
                        },
                    });
                }
            } else {
                // Standard download behavior
                await download({
                    url: "/pentaho/download",
                    data: {
                        data: JSON.stringify([contentB64, outputType, finalFileName]),
                    },
                });
            }
            
        } catch (error) {
            // console.error("Error generating Pentaho report:", error);
            env.services.notification.add(
                _t("Error generating report: ") + error.message,
                { type: "danger" }
            );
        } finally {
            // Unblock UI
            env.services.ui.unblock();
        }
        
        // Handle close on report download if specified
        if (action.close_on_report_download) {
            return env.services.action.doAction(
                { type: "ir.actions.act_window_close" },
                { onClose: options.onClose }
            );
        } else if (options.onClose) {
            options.onClose();
        }
        
        return true;
    }
    return false;
}

// Register the handler with higher priority
registry.category("ir.actions.report handlers").add("pentaho_handler", pentahoReportHandler, { sequence: 5 });