"""Compatibility shim injected via PYTHONPATH by tools/odoo_install_test.sh for Odoo <= 12.

Odoo 12's odoo/tools/image.py calls PIL.Image.ANTIALIAS, an alias Pillow removed in 10.0;
a local venv with a newer Pillow cannot even bootstrap `base` on a fresh database. Restore
the alias when it is missing. No effect on Pillow < 10 or on anything but that name.
"""
try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow absent, Odoo will complain itself
    Image = None
if Image is not None and not hasattr(Image, "ANTIALIAS") and hasattr(Image, "LANCZOS"):
    Image.ANTIALIAS = Image.LANCZOS
