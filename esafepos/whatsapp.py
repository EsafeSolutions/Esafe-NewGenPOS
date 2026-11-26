"""Meta WhatsApp Cloud API transport. Tokens stay in native Password storage."""
import base64
import hashlib
import re
import struct

import frappe
from frappe import _
from frappe.utils import cint


def credentials():
    doc = frappe.get_cached_doc("EsafePOS Settings")
    phone_id = str(doc.get("whatsapp_phone_number_id") or "").strip()
    version = str(doc.get("whatsapp_api_version") or "v27.0").strip()
    try:
        token = doc.get_password("whatsapp_access_token", raise_exception=False) if phone_id else ""
    except Exception:
        token = ""
    return phone_id, version, token or ""


def configured():
    phone_id, version, token = credentials()
    return bool(re.match(r"^[0-9]{5,30}$", phone_id) and re.match(r"^v[0-9]{1,3}\.0$", version) and token)


def _connection():
    phone_id, version, token = credentials()
    if not re.match(r"^[0-9]{5,30}$", phone_id) or not re.match(r"^v[0-9]{1,3}\.0$", version) or not token:
        frappe.throw(_("Configure the WhatsApp Business phone number ID and access token in POS Settings."))
    return "https://graph.facebook.com/{0}/{1}".format(version, phone_id), {"Authorization": "Bearer " + token}


def _png(image_data):
    if not isinstance(image_data, str) or not image_data.startswith("data:image/png;base64,") or len(image_data) > 5600000:
        frappe.throw(_("Prepare a PNG receipt image smaller than 4 MB."))
    try:
        data = base64.b64decode(image_data.split(",", 1)[1], validate=True)
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) < 33:
            raise ValueError()
        width, height = struct.unpack(">II", data[16:24])
        if len(data) > 4 * 1024 * 1024 or not width or not height or width * height > 24000000:
            raise ValueError()
    except (ValueError, TypeError, struct.error):
        frappe.throw(_("Prepare a valid PNG receipt image smaller than 4 MB."))
    return data


def prepare(context, settings, message, delivery_type="Text", image_data=None, session_confirmed=0):
    _connection()
    if delivery_type not in ("Text", "Image", "Template"):
        frappe.throw(_("Choose Text, Image or Approved template."))
    if delivery_type != "Template" and not cint(session_confirmed):
        frappe.throw(_("Confirm that this customer replied to your WhatsApp business within the last 24 hours, or use an approved template."))
    result = {"type": delivery_type, "message": message}
    identity = [delivery_type, message]
    if delivery_type == "Image" and len(message) > 1024:
        frappe.throw(_("Use at most 1024 characters for an image caption."))
    if delivery_type == "Image" or delivery_type == "Template" and cint(settings.get("whatsapp_template_image")):
        data = _png(image_data)
        result["image"] = data
        identity.append(hashlib.sha256(data).hexdigest())
    if delivery_type == "Template":
        name = settings.get("whatsapp_template_name") or ""
        language = settings.get("whatsapp_template_language") or "en"
        if not re.match(r"^[a-z0-9_]{1,512}$", name) or not re.match(r"^[a-z]{2,3}(_[A-Z]{2})?$", language):
            frappe.throw(_("Configure an approved WhatsApp template name and language in POS Settings."))
        keys = [key.strip() for key in (settings.get("whatsapp_template_parameters") or "").split(",") if key.strip()]
        allowed = {"customer", "invoice", "company", "currency", "total", "date", "link", "document"}
        if any(key not in allowed for key in keys) or len(keys) > 20:
            frappe.throw(_("Use the supported template parameter names."))
        parameters = [{"type": "text", "text": str(context["values"].get(key) or "-")} for key in keys]
        result["template"] = {"name": name, "language": {"code": language}}
        if parameters:
            result["template"]["components"] = [{"type": "body", "parameters": parameters}]
        result["display_message"] = "Template: {0} ({1})\n{2}".format(name, language, "\n".join("{0}: {1}".format(key, context["values"].get(key) or "-") for key in keys))
        identity.append([name, language, keys])
    context["delivery_identity"] = identity
    return result


def _post(url, **kwargs):
    import requests

    return requests.post(url, timeout=(5, 20), allow_redirects=False, **kwargs)


def _rejection(response):
    try:
        code = int(response.json().get("error", {}).get("code") or 0)
    except (ValueError, TypeError):
        code = 0
    if code == 131047:
        return _("The customer service window has closed. Use an approved WhatsApp template.")
    if code in (190, 10, 200):
        return _("WhatsApp rejected the credentials or permissions. Check the access token and business phone number in Settings.")
    return _("WhatsApp rejected this request (code {0}). Check the recipient, template and business account setup.").format(code or response.status_code)


def send(mobile, prepared):
    url, headers = _connection()
    payload = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": mobile.lstrip("+")}
    try:
        kind = prepared["type"]
        media_id = None
        if prepared.get("image"):
            upload = _post(url + "/media", headers=headers, data={"messaging_product": "whatsapp"}, files={"file": ("receipt.png", prepared["image"], "image/png")})
            if 400 <= upload.status_code < 500:
                return {"status": "Rejected", "error": _rejection(upload)}
            if not 200 <= upload.status_code < 300:
                raise ValueError()
            media_id = upload.json().get("id")
            if not media_id:
                raise ValueError()
        if kind == "Image":
            payload.update({"type": "image", "image": {"id": media_id, "caption": prepared["message"]}})
        elif kind == "Template":
            template = dict(prepared["template"])
            if media_id:
                template["components"] = [{"type":"header", "parameters":[{"type":"image", "image":{"id":media_id}}]}] + template.get("components", [])
            payload.update({"type": "template", "template": template})
        else:
            payload.update({"type": "text", "text": {"preview_url": True, "body": prepared["message"]}})
        response = _post(url + "/messages", headers=headers, json=payload)
        if 400 <= response.status_code < 500:
            return {"status": "Rejected", "error": _rejection(response)}
        if not 200 <= response.status_code < 300:
            raise ValueError()
        messages = response.json().get("messages") or []
        if not messages or not messages[0].get("id"):
            raise ValueError()
        return {"status": "Submitted to WhatsApp", "provider_id": str(messages[0]["id"])[:255], "error": ""}
    except Exception:
        return {"status": "Outcome unknown", "error": _("WhatsApp did not confirm the outcome. Check Meta's delivery reports before sending again.")}


def connection_status():
    import requests

    url, headers = _connection()
    try:
        response = requests.get(url, headers=headers, params={"fields": "display_phone_number,verified_name"}, timeout=(5, 15), allow_redirects=False)
        if response.status_code != 200:
            frappe.throw(_("The WhatsApp connection check failed. Check the token and phone number ID."))
        data = response.json()
        return {"connected": True, "phone": data.get("display_phone_number"), "name": data.get("verified_name")}
    except frappe.ValidationError:
        raise
    except Exception:
        frappe.throw(_("The WhatsApp connection could not be checked. No message was sent."))
