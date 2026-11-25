"""Operational browser sharing for open shifts; user permissions stay separate."""
import re

import frappe
from frappe import _


def multiple_computers():
    value = frappe.get_cached_doc("EsafePOS Settings").get("shift_multiple_computers")
    return True if value is None else bool(int(value))


def shared_management():
    settings = frappe.get_cached_doc("EsafePOS Settings")
    return settings.get("shift_scope") == "Per outlet" and bool(int(settings.get("shared_shift_management") or 0))


def apply_settings(doc, payload):
    """Leave new choices intact when an older settings screen saves."""
    if "shift_scope" in payload:
        selected = payload.get("shift_scope")
        if selected not in ("Per cashier", "Per outlet"):
            frappe.throw(_("Choose a valid shift sharing mode."))
        if selected != (doc.get("shift_scope") or "Per cashier") and frappe.db.exists("POS Register Session", {"status": "Open"}):
            frappe.throw(_("Close the open shifts before changing who shares a shift. Existing drawer counts must stay separate."))
        doc.shift_scope = selected
    for field in ("shift_multiple_computers", "shared_shift_management"):
        if field in payload:
            if payload[field] not in (0, 1, False, True):
                frappe.throw(_("Choose on or off for shift sharing settings."))
            doc.set(field, int(payload[field]))


def workstation(required=False):
    reader = getattr(frappe, "get_request_header", lambda name: None)
    value = str(reader("X-ESAFEPOS-Workstation") or "").strip()
    if value and re.fullmatch(r"[A-Za-z0-9-]{16,80}", value):
        return value
    if required:
        frappe.throw(_("Refresh this POS to identify this computer before using the shift."))
    return None


def tag_opening(doc):
    value = workstation(required=not multiple_computers())
    if doc.meta.has_field("workstation_id"):
        doc.workstation_id = value
    elif not multiple_computers():
        frappe.throw(_("Run the site migration to enable the shift computer restriction."))


def assert_workstation(doc):
    if multiple_computers():
        return
    current = workstation(required=True)
    if not doc.meta.has_field("workstation_id"):
        frappe.throw(_("Run the site migration to enable the shift computer restriction."))
    bound = frappe.db.get_value("POS Register Session", doc.name, "workstation_id", for_update=True)
    if bound and bound != current:
        frappe.throw(_("This shift is assigned to another computer. Ask a manager to move it from the Register page."))
    if not bound:
        frappe.db.set_value("POS Register Session", doc.name, "workstation_id", current, update_modified=False)


def allowed_here(doc):
    return multiple_computers() or not doc.get("workstation_id") or doc.get("workstation_id") == workstation()
