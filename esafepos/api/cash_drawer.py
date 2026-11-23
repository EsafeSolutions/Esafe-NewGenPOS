"""Authorize local printer-port pulses; never sends bytes or changes a sale."""
import json
from uuid import UUID

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime, flt
from esafepos.drawer_config import FIELD, registry, validate


def identity(workstation):
    try:
        if str(UUID(workstation)) != workstation:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        frappe.throw(_("Invalid workstation identity."))


@frappe.whitelist(methods=["POST"])
def save_setup(pos_profile, workstation, printer_id, values):
    from esafepos.api.printing_settings import _profile
    from esafepos.api import audit

    if frappe.session.user == "Guest":
        frappe.throw(_("Sign in before configuring the cash drawer."), frappe.PermissionError)
    profile = _profile(pos_profile, write=True)
    identity(workstation)
    if not profile.meta.has_field(FIELD):
        frappe.throw(_("Run the site migration before configuring the cash drawer."))
    frappe.db.sql("select name from `tabPOS Profile` where name=%s for update", profile.name)
    profile.reload()
    if not isinstance(printer_id, str) or not printer_id.strip() or len(printer_id) > 500:
        frappe.throw(_("Save an exact receipt printer before configuring the drawer."))
    try:
        settings = validate(json.loads(values) if isinstance(values, str) else values)
        entries = registry(profile)
    except ValueError as error:
        frappe.throw(_(str(error)))
    if workstation not in entries and len(entries) >= 250:
        frappe.throw(_("Review retired workstation entries before adding another drawer."))
    entries[workstation] = dict(settings, printerId=printer_id, updated_by=frappe.session.user)
    profile.set(FIELD, json.dumps(entries))
    profile.save()
    audit.log(audit.SETTINGS_CHANGE, pos_profile=pos_profile, detail="Workstation cash drawer settings updated: " + workstation)
    return dict(settings, printerId=printer_id)


def authorize(profile_name, workstation, printer_id, source, values, existing=False):
    from esafepos.api import permissions

    if frappe.session.user == "Guest":
        frappe.throw(_("Sign in before opening the cash drawer."), frappe.PermissionError)
    permissions.assert_outlet(profile_name)
    identity(workstation)
    profile = frappe.get_cached_doc("POS Profile", profile_name)
    try:
        saved = registry(profile).get(workstation) or {}
        settings = validate(values)
    except ValueError as error:
        frappe.throw(_(str(error)))
    if not saved.get("enabled") or printer_id != saved.get("printerId") or any(settings[k] != saved.get(k) for k in settings):
        frappe.throw(_("Save and enable the drawer for this workstation's exact receipt printer first."), frappe.PermissionError)
    mode = values.get("mode")
    reason = str(values.get("reason") or "").strip()
    if mode == "test":
        from esafepos.api.printing_settings import _profile
        _profile(profile_name, write=True)
        if source.doctype != "POS Profile" or source.name != profile_name:
            frappe.throw(_("A drawer setup test must reference its outlet."), frappe.PermissionError)
        reason = "Explicit workstation drawer test"
    elif mode == "manual":
        if source.doctype != "POS Register Session" or not permissions.can_cash_out():
            frappe.throw(_("Manual opening requires the existing cash-out permission."), frappe.PermissionError)
        from esafepos.api.register import _assert_owner_or_manager
        _assert_owner_or_manager(source)
        source.check_permission("write")
        if source.status != "Open" or source.pos_profile != profile_name or not reason or len(reason) > 140:
            frappe.throw(_("Use your open register and enter a reason of at most 140 characters."), frappe.PermissionError)
    elif mode == "payment":
        if not saved.get("automatic"):
            frappe.throw(_("Automatic drawer opening is disabled."), frappe.PermissionError)
        if not _cash_sale(source, profile_name, existing):
            frappe.throw(_("This is not a new eligible cash payment."), frappe.PermissionError)
        reason = "Successful cash payment"
    else:
        frappe.throw(_("Choose an explicit drawer test, manual opening or eligible cash payment."))
    linked = values.get("receiptIntent") or ""
    if mode == "payment" and profile.get("esafepos_silent_printing") and profile.get("esafepos_auto_print_receipt") and not linked:
        frappe.throw(_("This outlet requires the original automatic receipt before its drawer pulse."), frappe.PermissionError)
    if linked:
        receipt = frappe.get_doc("EsafePOS Print Intent", linked)
        if (mode != "payment" or receipt.role != "receipt" or not receipt.get("original_key") or receipt.get("reprint_of")
                or receipt.owner != frappe.session.user or receipt.workstation != workstation
                or receipt.pos_profile != profile_name or receipt.reference_name != source.name
                or receipt.reference_doctype != source.doctype or receipt.printer_id != printer_id
                or receipt.state not in ("submitted", "completed")):
            frappe.throw(_("The original receipt must reach submitted/completed on this same printer before the pulse."), frappe.PermissionError)
    return {"drawer_mode": mode, "drawer_pin": settings["pin"], "drawer_on_ms": settings["onMs"],
            "drawer_off_ms": settings["offMs"], "drawer_reason": reason, "drawer_receipt": linked or None}


def _cash_sale(sale, profile_name, existing):
    from esafepos.api.session import get_open_session

    if (sale.doctype not in ("POS Invoice", "Sales Invoice") or not frappe.has_permission(sale.doctype, "create") or sale.get("docstatus") != 1
            or not sale.meta.has_field("esafepos_queued_offline")
            or sale.get("is_return") or sale.get("return_against") or sale.get("esafepos_queued_offline")
            or sale.owner != frappe.session.user or flt(sale.get("grand_total")) <= 0
            or flt(sale.get("outstanding_amount")) > 0.005 or sale.get("esafepos_credit_entry")
            or (sale.doctype == "Sales Invoice" and not sale.get("is_pos"))):
        return False
    current = get_open_session(profile_name)
    if frappe.db.exists(sale.doctype, {"return_against": sale.name, "docstatus": 1}):
        return False
    if not current or current["name"] != sale.get("esafepos_session"):
        frappe.throw(_("The cash sale must belong to your current open register."), frappe.PermissionError)
    session = frappe.get_doc("POS Register Session", current["name"])
    session.check_permission("write")
    if session.pos_profile != profile_name or session.status != "Open":
        frappe.throw(_("The register is not open at this outlet."), frappe.PermissionError)
    if not existing:
        age = (now_datetime() - get_datetime(sale.creation)).total_seconds()
        if age < 0 or age > 300:
            return False
    cash = 0
    for row in sale.get("payments") or []:
        if row.get("mode_of_payment") == "Credit Sale":
            return False
        if frappe.get_cached_value("Mode of Payment", row.get("mode_of_payment"), "type") == "Cash":
            cash += max(0, flt(row.get("amount")))
    return cash > 0


@frappe.whitelist()
def payment_eligibility(pos_profile, doctype, name):
    from esafepos.api.esafe_printing import _source
    source = _source(pos_profile, {"doctype": doctype, "name": name}, role="drawer")
    return {"eligible": _cash_sale(source, pos_profile, existing=False)}
