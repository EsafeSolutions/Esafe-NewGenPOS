"""Customer messaging from POS. WhatsApp drafts are never reported as sent.

SMS uses Frappe's configured gateway and its sender-role checks. A durable,
unique request record is committed before crossing the gateway boundary so a
lost browser response cannot automatically send the same message twice.
"""
import hashlib
import json
import re
from urllib.parse import urlsplit

import frappe
from frappe import _
from frappe.utils import cint, flt

DEFAULTS = {
    "enabled": 1, "sms_enabled": 1, "whatsapp_enabled": 1, "image_enabled": 1,
    "country_code": "94", "whatsapp_target": "Popup", "sms_number_format": "As entered",
    "invoice_template": "Hello {customer},\nYour {document} {invoice} from {company}.\nTotal: {currency} {total}\n{link}\nThank you!",
    "customer_template": "Hello {customer},",
    "whatsapp_template_name": "", "whatsapp_template_language": "en", "whatsapp_template_parameters": "customer,invoice,total,link",
    "whatsapp_api_roles": ["System Manager", "EsafePOS Manager", "EsafePOS Cashier"],
    "whatsapp_template_image": 0,
}
PLACEHOLDERS = {"customer", "invoice", "company", "currency", "total", "date", "link", "document"}
LOG = "POS Customer Message"


def config():
    result = dict(DEFAULTS)
    try:
        saved = json.loads(frappe.get_cached_doc("EsafePOS Settings").get("customer_messaging_config") or "{}")
        result.update({key: saved[key] for key in DEFAULTS if key in saved})
    except (TypeError, ValueError):
        pass
    return result


def _read_access():
    if not frappe.has_permission("Customer", "read"):
        frappe.throw(_("You are not permitted to view customers."), frappe.PermissionError)


def _manager():
    if not frappe.has_permission("EsafePOS Settings", "write"):
        frappe.throw(_("You are not permitted to configure customer messaging."), frappe.PermissionError)


def _ready():
    return bool(frappe.db.table_exists(LOG) and frappe.db.has_column(LOG, "provider_id"))


def _whatsapp_allowed():
    roles = set(frappe.get_roles())
    return bool(roles & {"System Manager", "EsafePOS Manager"} or roles & set(config().get("whatsapp_api_roles") or []))


def _sms_allowed():
    module = _sms_module()
    checker = getattr(module, "check_sms_permission", None)
    if checker:
        checker()


def _sms_module():
    from frappe.core.doctype.sms_settings import sms_settings

    return sms_settings


@frappe.whitelist()
def options(pos_profile=None):
    _read_access()
    if pos_profile:
        from esafepos.api.permissions import assert_outlet

        assert_outlet(pos_profile)
    sms_allowed = True
    try:
        _sms_allowed()
    except frappe.PermissionError:
        sms_allowed = False
    from esafepos import whatsapp

    return {"config": config(), "ready": _ready(), "can_sms": sms_allowed, "whatsapp_configured": whatsapp.configured(), "can_whatsapp_api": _whatsapp_allowed(),
            "sms_configured": bool(frappe.db.get_single_value("SMS Settings", "sms_gateway_url")),
            "can_manage": bool(frappe.has_permission("EsafePOS Settings", "write"))}


def normalize_mobile(value, country_code=None):
    value = str(value or "").strip()
    if not re.match(r"^[+0-9\s()\-]+$", value):
        frappe.throw(_("Enter a valid customer mobile number."))
    value = re.sub(r"[\s()\-]", "", value)
    if value.startswith("00"):
        value = "+" + value[2:]
    if value.startswith("0") and country_code:
        value = "+" + country_code + value[1:]
    if not re.match(r"^\+?[1-9][0-9]{5,14}$", value):
        frappe.throw(_("Enter a valid mobile number including its country code."))
    return "+" + value.lstrip("+")


def _context(pos_profile=None, customer=None, invoice=None):
    _read_access()
    from esafepos.api.permissions import assert_outlet, allowed_companies

    sale = None
    url = ""
    mobile = ""
    if invoice:
        from esafepos.digital_receipts import invoice_doctype, share_details

        doctype = invoice_doctype(invoice)
        if not doctype:
            frappe.throw(_("Invoice not found."))
        sale = frappe.get_doc(doctype, invoice)
        sale.check_permission("read")
        if cint(sale.docstatus) != 1:
            frappe.throw(_("Only a submitted invoice can be shared."))
        pos_profile = sale.get("pos_profile") or pos_profile
        linked = sale.get("esafepos_receipt_customer")
        invoice_customer = linked or (sale.customer if not sale.get("esafepos_walk_in_code") else None)
        if customer and customer != invoice_customer:
            frappe.throw(_("The customer does not match this receipt."), frappe.PermissionError)
        customer = invoice_customer
        details = share_details(sale)
        url, mobile = details["url"], details.get("mobile") or ""
    if not pos_profile:
        frappe.throw(_("Select a POS outlet before sending a message."))
    assert_outlet(pos_profile)
    profile = frappe.get_cached_doc("POS Profile", pos_profile)
    company = sale.company if sale else profile.company
    companies = allowed_companies()
    if companies is not None and company not in companies:
        frappe.throw(_("You cannot message for this company."), frappe.PermissionError)
    person = frappe.get_doc("Customer", customer) if customer else None
    if person:
        person.check_permission("read")
        mobile = mobile or person.get("mobile_no") or ""
    if not sale and not person:
        frappe.throw(_("Select a customer or invoice."))
    currency = (sale.get("currency") if sale else None) or frappe.get_cached_value("Company", company, "default_currency")
    values = {
        "customer": person.customer_name if person else _("Customer"), "company": company,
        "invoice": sale.name if sale else "", "currency": currency or "",
        "total": "{0:.2f}".format(flt(sale.get("rounded_total") or sale.get("grand_total"))) if sale else "",
        "date": str(sale.get("posting_date") or "") if sale else "", "link": url,
        "document": _("credit note") if sale and cint(sale.get("is_return")) else _("invoice"),
    }
    return {"sale": sale, "customer": customer, "pos_profile": pos_profile, "company": company,
            "mobile": mobile, "url": url, "values": values}


def render_message(template, values):
    return re.sub(r"\{([a-z_]+)\}", lambda match: str(values.get(match.group(1), match.group(0))), template)


@frappe.whitelist()
def compose(pos_profile=None, customer=None, invoice=None):
    context = _context(pos_profile, customer, invoice)
    settings = config()
    template = settings["invoice_template" if invoice else "customer_template"]
    return {"url": context["url"], "mobile": context["mobile"], "customer": context["customer"],
            "message": render_message(template, context["values"]), "template_values": context["values"], "options": options(context["pos_profile"])}


def _result(doc):
    return {"name": doc.name, "status": doc.status, "channel": doc.channel, "mobile": doc.mobile,
            "error": doc.get("error") or "", "provider_id": doc.get("provider_id") or "", "duplicate": False}


def _claim(context, channel, mobile, message, request_key):
    if not _ready():
        frappe.throw(_("Run site migration to enable the customer messaging module."))
    if not request_key or not re.match(r"^[a-zA-Z0-9_-]{16,140}$", request_key):
        frappe.throw(_("A valid message request key is required."))
    identity = hashlib.sha256((frappe.session.user + "|" + request_key).encode("utf-8")).hexdigest()
    sale = context["sale"]
    payload = json.dumps([channel, context["customer"], context["pos_profile"], sale.name if sale else None, mobile, context.get("request_message", message), context.get("delivery_identity")])
    fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    existing = frappe.db.get_value(LOG, {"request_key": identity}, "name", for_update=True)
    if existing:
        doc = frappe.get_doc(LOG, existing)
        if doc.payload_hash != fingerprint or doc.owner != frappe.session.user:
            frappe.throw(_("This request key belongs to a different message."))
        result = _result(doc)
        result["duplicate"] = True
        return doc, result
    frappe.db.savepoint("customer_message")
    doc = frappe.get_doc({"doctype": LOG, "request_key": identity, "payload_hash": fingerprint,
                          "channel": channel, "status": "Preparing", "customer": context["customer"],
                          "pos_profile": context["pos_profile"], "company": context["company"],
                          "invoice_type": sale.doctype if sale else None, "invoice": sale.name if sale else None,
                          "mobile": mobile, "message": message})
    try:
        doc.insert(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        frappe.db.rollback(save_point="customer_message")
        return _claim(context, channel, mobile, message, request_key)
    # This endpoint only records/sends a message; it never posts sale/accounting changes.
    frappe.db.commit()
    return doc, None


@frappe.whitelist()
def send_message(channel, mobile, message, request_key, pos_profile=None, customer=None, invoice=None,
                 delivery_type="Text", image_data=None, session_confirmed=0):
    context = _context(pos_profile, customer, invoice)
    settings = config()
    if channel not in ("SMS", "WhatsApp", "WhatsApp API"):
        frappe.throw(_("Choose SMS or WhatsApp."))
    if not cint(settings["enabled"]) or not cint(settings["sms_enabled" if channel == "SMS" else "whatsapp_enabled"]):
        frappe.throw(_("This messaging channel is disabled."), frappe.PermissionError)
    typed_mobile = str(mobile or "").strip()
    mobile = normalize_mobile(typed_mobile, settings["country_code"])
    message = (message or "").strip()
    if not message or len(message) > (1600 if channel == "SMS" else 4000):
        frappe.throw(_("Enter a message of at most {0} characters.").format(1600 if channel == "SMS" else 4000))
    if channel == "SMS":
        _sms_allowed()
        if not frappe.db.get_single_value("SMS Settings", "sms_gateway_url"):
            frappe.throw(_("Configure the SMS gateway in POS Settings, Customer messaging."))
    prepared = None
    if channel == "WhatsApp API":
        from esafepos import whatsapp

        if not _whatsapp_allowed():
            frappe.throw(_("Your role is not allowed to send through WhatsApp Business API."), frappe.PermissionError)
        if (delivery_type == "Image" or delivery_type == "Template" and cint(settings["whatsapp_template_image"])) and not cint(settings["image_enabled"]):
            frappe.throw(_("Receipt image sharing is disabled."), frappe.PermissionError)
        prepared = whatsapp.prepare(context, settings, message, delivery_type, image_data, session_confirmed)
        context["request_message"] = message
        message = prepared.get("display_message") or message
    doc, previous = _claim(context, channel, mobile, message, request_key)
    if previous:
        return previous
    status, error = "Opened in WhatsApp", ""
    provider_id = ""
    if channel == "SMS":
        try:
            destination = re.sub(r"[\s()\-]", "", typed_mobile)
            if settings["sms_number_format"] == "International digits":
                destination = mobile.lstrip("+")
            elif settings["sms_number_format"] == "International +":
                destination = mobile
            _sms_module().send_sms(receiver_list=[destination], msg=message, success_msg=False)
            status = "Submitted to gateway"
        except Exception:
            # A timeout can happen after acceptance. Never auto-resend or claim delivery.
            status = "Outcome unknown"
            frappe.clear_messages()
            error = _("The SMS gateway did not confirm the outcome. Check its delivery report before sending again.")
    if prepared:
        outcome = whatsapp.send(mobile, prepared)
        status, error, provider_id = outcome["status"], outcome.get("error") or "", outcome.get("provider_id") or ""
    frappe.db.set_value(LOG, doc.name, {"status": status, "error": error, "provider_id": provider_id})
    frappe.db.commit()
    doc.status, doc.error, doc.provider_id = status, error, provider_id
    return _result(doc)


@frappe.whitelist()
def recent_messages(pos_profile, customer=None):
    _read_access()
    from esafepos.api.permissions import assert_outlet, is_manager

    assert_outlet(pos_profile)
    if not _ready():
        return []
    filters = {"pos_profile": pos_profile}
    if customer:
        frappe.get_doc("Customer", customer).check_permission("read")
        filters["customer"] = customer
    if not is_manager():
        filters["owner"] = frappe.session.user
    return frappe.get_list(LOG, filters=filters, fields=["name", "creation", "customer", "invoice", "channel", "status", "mobile", "message", "error", "provider_id"],
                           order_by="creation desc", limit_page_length=50)


@frappe.whitelist()
def get_messaging_settings():
    _manager()
    result = {"config": config(), "ready": _ready(), "can_configure_sms": bool(frappe.has_permission("SMS Settings", "write"))}
    result["roles"] = frappe.get_all("Role", filters={"disabled": 0}, pluck="name", order_by="name asc")
    from esafepos import whatsapp

    doc = frappe.get_cached_doc("EsafePOS Settings")
    result["whatsapp"] = {"phone_number_id": doc.get("whatsapp_phone_number_id") or "", "api_version": doc.get("whatsapp_api_version") or "v27.0", "token_configured": whatsapp.configured()}
    if result["can_configure_sms"] and frappe.has_permission("SMS Settings", "read"):
        sms = frappe.get_doc("SMS Settings")
        result["gateway"] = {key: sms.get(key) for key in ("sms_gateway_url", "message_parameter", "receiver_parameter", "use_post")}
        result["gateway"]["parameters"] = [{"name": row.name, "parameter": row.parameter, "value": "", "has_value": bool(row.value), "header": cint(row.get("header"))} for row in sms.get("parameters") or []]
        result["gateway"]["allowed_roles"] = [row.role for row in sms.get("allowed_roles") or []]
    return result


@frappe.whitelist()
def save_messaging_settings(payload):
    _manager()
    payload = json.loads(payload) if isinstance(payload, str) else payload
    result = dict(DEFAULTS)
    for key in ("enabled", "sms_enabled", "whatsapp_enabled", "image_enabled", "whatsapp_template_image"):
        result[key] = 1 if cint(payload.get(key)) else 0
    code = str(payload.get("country_code") or "").strip().lstrip("+")
    if not re.match(r"^[1-9][0-9]{0,3}$", code):
        frappe.throw(_("Enter a country calling code such as 94."))
    result["country_code"] = code
    result["sms_number_format"] = payload.get("sms_number_format", DEFAULTS["sms_number_format"])
    if result["sms_number_format"] not in ("As entered", "International digits", "International +"):
        frappe.throw(_("Choose a supported SMS recipient number format."))
    roles = payload.get("whatsapp_api_roles", DEFAULTS["whatsapp_api_roles"])
    if not isinstance(roles, list) or len(roles) > 50 or any(not isinstance(role, str) or not frappe.db.exists("Role", role) for role in roles):
        frappe.throw(_("Choose valid roles for WhatsApp API sending."))
    result["whatsapp_api_roles"] = sorted(set(roles))
    for key in ("whatsapp_template_name", "whatsapp_template_language", "whatsapp_template_parameters"):
        result[key] = str(payload.get(key, DEFAULTS[key]) or "").strip()[:512]
    template_name = result["whatsapp_template_name"]
    keys = [key.strip() for key in result["whatsapp_template_parameters"].split(",") if key.strip()]
    if (template_name and not re.match(r"^[a-z0-9_]{1,512}$", template_name)) or not re.match(r"^[a-z]{2,3}(_[A-Z]{2})?$", result["whatsapp_template_language"]) or len(keys) > 20 or any(key not in PLACEHOLDERS for key in keys):
        frappe.throw(_("Enter a valid approved template name, language and supported body parameter names."))
    result["whatsapp_target"] = payload.get("whatsapp_target")
    if result["whatsapp_target"] not in ("Popup", "Tab"):
        frappe.throw(_("Choose Popup or Tab for WhatsApp."))
    for key in ("invoice_template", "customer_template"):
        value = str(payload.get(key) or "").strip()
        if not value or len(value) > 2000 or set(re.findall(r"\{([^{}]+)\}", value)) - PLACEHOLDERS:
            frappe.throw(_("Use a template of at most 2000 characters with the supported placeholders."))
        result[key] = value
    doc = frappe.get_doc("EsafePOS Settings")
    if not frappe.get_meta("EsafePOS Settings").has_field("customer_messaging_config"):
        frappe.throw(_("Run site migration before saving customer messaging settings."))
    doc.customer_messaging_config = json.dumps(result)
    doc.save()
    frappe.clear_document_cache("EsafePOS Settings", "EsafePOS Settings")
    return {"config": result}


@frappe.whitelist()
def save_whatsapp_connection(phone_number_id, api_version, access_token=None):
    _manager()
    if not re.match(r"^[0-9]{5,30}$", str(phone_number_id)) or not re.match(r"^v[0-9]{1,3}\.0$", str(api_version)):
        frappe.throw(_("Enter the WhatsApp Business phone number ID and API version, such as v27.0."))
    doc = frappe.get_doc("EsafePOS Settings")
    if not frappe.get_meta("EsafePOS Settings").has_field("whatsapp_access_token"):
        frappe.throw(_("Run site migration before configuring WhatsApp Business API."))
    doc.whatsapp_phone_number_id, doc.whatsapp_api_version = str(phone_number_id), str(api_version)
    if access_token:
        if len(access_token) > 4000 or any(character.isspace() for character in access_token):
            frappe.throw(_("Enter a valid WhatsApp access token."))
        doc.whatsapp_access_token = access_token
    doc.save()
    frappe.clear_document_cache("EsafePOS Settings", "EsafePOS Settings")
    return {"saved": True}


@frappe.whitelist()
def check_whatsapp_connection():
    _manager()
    from esafepos import whatsapp

    return whatsapp.connection_status()


@frappe.whitelist()
def save_sms_gateway(payload):
    _manager()
    doc = frappe.get_doc("SMS Settings")
    doc.check_permission("read")
    doc.check_permission("write")
    payload = json.loads(payload) if isinstance(payload, str) else payload
    url = str(payload.get("sms_gateway_url") or "").strip()
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or "\n" in url or "\r" in url:
        frappe.throw(_("Enter the SMS provider's HTTP or HTTPS gateway URL."))
    for key in ("message_parameter", "receiver_parameter"):
        value = str(payload.get(key) or "").strip()
        if not re.match(r"^[A-Za-z0-9_.-]{1,140}$", value):
            frappe.throw(_("Enter valid message and recipient parameter names."))
        doc.set(key, value)
    doc.sms_gateway_url = url
    doc.use_post = 1 if cint(payload.get("use_post")) else 0
    existing = {row.name: row for row in doc.get("parameters") or []}
    rows = payload.get("parameters") or []
    if len(rows) > 30:
        frappe.throw(_("Use at most 30 static SMS parameters."))
    doc.set("parameters", [])
    for row in rows:
        key = str(row.get("parameter") or "").strip()
        old = existing.get(row.get("name"))
        value = row.get("value") or (old.value if old else "")
        if not re.match(r"^[A-Za-z0-9_.-]{1,140}$", key) or not value or len(str(value)) > 255 or "\n" in str(value) or "\r" in str(value):
            frappe.throw(_("Enter a name and value for every static SMS parameter."))
        doc.append("parameters", {"parameter": key, "value": value, "header": 1 if cint(row.get("header")) else 0})
    if frappe.get_meta("SMS Settings").has_field("allowed_roles"):
        doc.set("allowed_roles", [])
        for role in sorted(set(payload.get("allowed_roles") or [])):
            if not frappe.db.exists("Role", role):
                frappe.throw(_("Unknown SMS sender role."))
            doc.append("allowed_roles", {"role": role})
    doc.save()
    return get_messaging_settings()
