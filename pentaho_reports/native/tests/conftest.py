import sys
from pathlib import Path

# Make the `native` package importable without going through the Odoo addon
# __init__ (which imports odoo). pentaho_reports/ dir onto sys.path.
MODULE_DIR = Path(__file__).resolve().parents[2]
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

PIAGGIO_DIR = MODULE_DIR.parent

DELIVERY_RECEIPT_PRPT = PIAGGIO_DIR / "piaggio_reports" / "delivery_receipt" / "delivery_receipt.prpt"
SALES_INVOICE_PRPT = PIAGGIO_DIR / "piaggio_reports" / "sales_invoice" / "sales_invoice.prpt"
AP_VOUCHER_PRPT = PIAGGIO_DIR / "piaggio_reports" / "ap_voucher" / "ap_voucher.prpt"
BIR_2307_PRPT = PIAGGIO_DIR / "piaggio_reports" / "bir_2307" / "BIR_2307.prpt"

# real-world multi-level (nested group-body) sample, e.g. a GL listing
# grouped by account then sub-account — lives in the (git-tracked, always
# present) sample_prpt/ corpus, unlike the piaggio_reports/ fixtures above.
SAMPLE_PRPT_DIR = PIAGGIO_DIR / "sample_prpt"
GL_LISTING_NESTED_PRPT = SAMPLE_PRPT_DIR / "amici_v11__gl_listing_hardcode_sample.prpt"

# real-world code128 <sbarcodes:simple-barcodes> sample (product barcode
# label sheet) — used to prove the barcode element renders end-to-end.
BARCODE_PRPT = SAMPLE_PRPT_DIR / "frpic_v16__product_barcode.prpt"
