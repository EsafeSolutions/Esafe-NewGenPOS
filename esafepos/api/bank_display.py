"""Manager configuration and image uploads for public bank receiving details."""
import base64
import io
import json

import frappe
from frappe import _

from esafepos.bank_display import clean_config, settings_value


def _require_write():
    if not frappe.has_permission("EsafePOS Settings", "write"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)


@frappe.whitelist()
def get_settings():
    _require_write()
    return settings_value(frappe.get_cached_doc("EsafePOS Settings"))


@frappe.whitelist(methods=["POST"])
def save_settings(config):
    _require_write()
    try:
        config = clean_config(config)
    except (ValueError, TypeError, OverflowError) as error:
        frappe.throw(_(str(error)))
    # Validate profile/method names instead of persisting misspelled routing rules.
    from esafepos.api import permissions
    for account in config["accounts"]:
        if account["pos_profile"]:
            permissions.assert_outlet(account["pos_profile"])
            if not frappe.db.exists("POS Profile", account["pos_profile"]):
                frappe.throw(_("Unknown POS Profile"))
        if account["payment_mode"] and not frappe.db.exists("Mode of Payment", account["payment_mode"]):
            frappe.throw(_("Unknown payment method"))
    doc = frappe.get_doc("EsafePOS Settings")
    if not doc.meta.has_field("bank_transfer_display"):
        frappe.throw(_("Run bench migrate before saving bank display settings."))
    doc.bank_transfer_display = json.dumps(config, ensure_ascii=False)
    doc.save()
    return settings_value(doc)


@frappe.whitelist(methods=["POST"])
def upload_image(content, kind="logo"):
    _require_write()
    if not isinstance(content, str) or len(content) > 2800000:
        frappe.throw(_("Choose an image smaller than 2 MB."))
    from PIL import Image
    from frappe.utils.file_manager import save_file
    try:
        raw = base64.b64decode(content, validate=True)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError()
        picture = Image.open(io.BytesIO(raw))
        if picture.format not in ("PNG", "JPEG", "WEBP") or picture.width * picture.height > 16000000:
            raise ValueError()
        picture.load()
        # Re-encode: strip metadata and discard any non-image payload.
        output = io.BytesIO()
        picture.convert("RGBA").save(output, format="PNG")
    except Exception:
        frappe.throw(_("Choose a valid PNG, JPEG or WebP image up to 16 megapixels."))
    filename = "bank-qr.png" if kind == "qr" else "bank-logo.png"
    file_doc = save_file(filename, output.getvalue(), "EsafePOS Settings", "EsafePOS Settings", is_private=0)
    return {"file_url": file_doc.file_url}
