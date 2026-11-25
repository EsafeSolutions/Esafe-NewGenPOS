"""Manager-operated, native cancellation and permanent deletion of POS sales."""
from __future__ import annotations

import hashlib
import json
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from esafepos.api import permissions

AUDIT = "EsafePOS Deleted Sale"
INVOICES = ("POS Invoice", "Sales Invoice")


def _identity(doctype, invoice):
    return hashlib.sha256((doctype + "\0" + invoice).encode("utf-8")).hexdigest()


def _key_hash(key):
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def assert_not_deleted_key(key, for_update=False):
    """A delayed offline upload must never recreate an intentionally deleted sale."""
    if key and frappe.db.table_exists(AUDIT) and frappe.db.get_value(
        AUDIT, {"idempotency_key_hash": _key_hash(key)}, "name", for_update=for_update
    ):
        frappe.throw(_("This sale was permanently deleted. Its old upload key cannot be used again."))


def _require_manager(doctype):
    if doctype not in INVOICES or not permissions.can_delete_sales():
        frappe.throw(_("Only a manager can permanently delete a sale."), frappe.PermissionError)
    if not frappe.has_permission(doctype, "delete"):
        frappe.throw(_("ERPNext delete permission is required for this invoice type."), frappe.PermissionError)
    if not frappe.db.table_exists(AUDIT):
        frappe.throw(_("Run the site migration to enable permanent sale deletion and its audit record."))


def _load(doctype, invoice, for_update=False):
    doc = frappe.get_doc(doctype, invoice, for_update=for_update)
    doc.check_permission("read")
    doc.check_permission("delete")
    if doc.docstatus == 1:
        doc.check_permission("cancel")
    if not doc.get("pos_profile"):
        frappe.throw(_("This is not a till sale. Manage this invoice in ERPNext."))
    permissions.assert_outlet(doc.pos_profile)
    companies = permissions.allowed_companies()
    if companies is not None and doc.company not in companies:
        frappe.throw(_("This company is not available to you."), frappe.PermissionError)
    return doc


def _already_deleted(doctype, invoice, for_update=False):
    row = frappe.db.get_value(AUDIT, _identity(doctype, invoice), ["pos_profile", "company"],
                             as_dict=True, for_update=for_update)
    if not row:
        return False
    permissions.assert_outlet(row.pos_profile)
    companies = permissions.allowed_companies()
    if companies is not None and row.company not in companies:
        frappe.throw(_("This company is not available to you."), frappe.PermissionError)
    return True


def _exists(doctype, filters, for_update=False):
    return frappe.db.table_exists(doctype) and bool(
        frappe.db.get_value(doctype, filters, "name", for_update=True) if for_update
        else frappe.db.exists(doctype, filters)
    )


def _blocker(doc, for_update=False):
    if doc.docstatus not in (1, 2) or doc.get("is_return"):
        return _("Choose a submitted or cancelled sale. Return invoices are managed in ERPNext.")
    if doc.get("consolidated_invoice") or doc.get("is_consolidated") or doc.get("status") == "Consolidated":
        return _("This sale has been consolidated. Its linked accounting documents must be handled in ERPNext first.")
    if not doc.get("esafepos_session"):
        return _("This invoice has no POS shift. Manage it in ERPNext.")
    if _exists("EsafePOS Print Intent", {"reference_doctype": doc.doctype, "reference_name": doc.name,
               "state": ["not in", ["completed", "failed", "cancelled"]]}, for_update):
        return _("Finish or cancel the pending print jobs for this sale before deleting it.")
    if frappe.db.get_value("POS Register Session", doc.esafepos_session, "status") != "Open":
        return _("This shift is closing or closed. Permanent deletion cannot change its saved closing counts.")
    if doc.get("esafepos_credit_entry") or doc.get("esafepos_loyalty_change_entry"):
        return _("This sale has customer-credit or saved-change entries. Resolve those linked transactions in ERPNext first.")
    if any(str(doc.get(field) or "").strip().lower() in ("1", "yes", "true")
           for field in ("is_exchange", "custom_is_exchange")):
        return _("This sale is part of an exchange. Resolve the complete exchange in ERPNext first.")
    for doctype in INVOICES:
        if _exists(doctype, {"return_against": doc.name, "docstatus": ["!=", 2]}, for_update):
            return _("A return or draft return is linked to this sale. Resolve it before deleting the sale.")
    for doctype in ("POS Store Credit Entry", "POS Cashback Entry"):
        if _exists(doctype, {"reference_doctype": doc.doctype, "reference_invoice": doc.name}, for_update):
            return _("This sale has wallet or cashback transactions. Resolve them in ERPNext first.")
    try:
        applied = json.loads(doc.get("esafepos_promotions") or "[]")
        if not isinstance(applied, list):
            raise ValueError("Invalid promotion history")
        promo_names = [row["name"] for row in applied if isinstance(row, dict) and row.get("name")]
    except (TypeError, ValueError):
        return _("The promotion usage of this sale could not be verified. Review it in ERPNext first.")
    if promo_names and _exists("POS Coupon", {"promotion": ["in", promo_names], "used_count": [">", 0]}, for_update):
        return _("This sale includes a promotion with coupon usage. Review its redemption history in ERPNext first.")
    for doctype, field in (("POS Gift Card Entry", "invoice"), ("POS Gift Card", "issued_invoice"),
                          ("POS Layaway Payment", "invoice"), ("POS Layaway", "completed_invoice"),
                          ("POS Coupon", "used_on")):
        if _exists(doctype, {field: doc.name}, for_update):
            return _("This sale is linked to a gift card, hold or redeemed coupon. Resolve that transaction in ERPNext first.")
    if (frappe.get_meta("Journal Entry").has_field("esafepos_credit_invoice")
            and _exists("Journal Entry", {"esafepos_credit_invoice": doc.name, "docstatus": ["!=", 2]}, for_update)):
        return _("This sale has a linked customer payment or credit journal. Resolve it in ERPNext first.")
    # Native cancel handles ordinary loyalty, but all earned lots must be unused.
    lots = [row.name for row in frappe.db.get_values("Loyalty Point Entry", {"invoice": doc.name},
                                                   ["name"], as_dict=True, for_update=for_update)]
    if lots and _exists("Loyalty Point Entry", {"redeem_against": ["in", lots]}, for_update):
        return _("Points earned on this sale have been spent. Resolve those redemptions before deleting it.")
    return ""


@frappe.whitelist()
def check_sale_deletion(invoice: str, doctype: str):
    _require_manager(doctype)
    if _already_deleted(doctype, invoice):
        return {"deleted": True, "eligible": False, "invoice": invoice}
    doc = _load(doctype, invoice)
    reason = _blocker(doc)
    return {"eligible": not reason, "blocker": reason, "invoice": doc.name, "doctype": doc.doctype,
            "amount": flt(doc.rounded_total or doc.grand_total), "currency": doc.currency,
            "modified": str(doc.modified), "session": doc.esafepos_session}


def _series_snapshot(doc):
    """Native deletion rewinds the last naming number. Keep invoice numbers spent."""
    autoname = doc.meta.autoname or ""
    if not autoname or autoname.split(":", 1)[0] in ("Prompt", "field", "hash", "autoincrement"):
        return None
    pattern = doc.get("naming_series") if autoname.startswith("naming_series:") else autoname
    if not pattern or ("#" in pattern and not pattern.endswith("#")):
        frappe.throw(_("This custom invoice naming series needs manual deletion in ERPNext."))
    match = re.match(r"^(.*?)(\d+)$", doc.name)
    if not match:
        frappe.throw(_("The invoice numbering could not be verified. Manage this invoice in ERPNext."))
    rows = frappe.db.sql("select current from `tabSeries` where name=%s for update", match.group(1))
    if not rows:
        frappe.throw(_("The invoice numbering could not be verified. Manage this invoice in ERPNext."))
    return (match.group(1), cint(rows[0][0]))


@frappe.whitelist(methods=["POST"])
def permanently_delete_sale(invoice: str, doctype: str, reason: str, confirm_invoice: str,
                            expected_modified: str, payment_handled: int | str = 0):
    _require_manager(doctype)
    reason = (reason or "").strip()
    if confirm_invoice != invoice or len(reason) < 5 or len(reason) > 500 or cint(payment_handled) != 1:
        frappe.throw(_("Enter a deletion reason, type the exact invoice number and confirm the payment has been handled."))
    if _already_deleted(doctype, invoice):
        return {"deleted": True, "already_deleted": True, "invoice": invoice}
    doc = _load(doctype, invoice)
    if doc.get("customer") and doc.get("loyalty_program"):
        # POS loyalty redemption takes this customer lock before its drawer.
        # Use the same order so points cannot be spent during cancellation.
        frappe.db.get_value("Customer", doc.customer, "name", for_update=True)
    # Same lock order as sales and closing: drawer first, then invoice. Re-read
    # the invoice only after the lock so a close cannot retain stale totals.
    shift = doc.get("esafepos_session")
    if not shift:
        frappe.throw(_("This invoice has no POS shift. Manage it in ERPNext."))
    if frappe.db.get_value("POS Register Session", shift, "status", for_update=True) != "Open":
        frappe.throw(_("This shift is closing or closed. Permanent deletion cannot change its saved closing counts."))
    if _already_deleted(doctype, invoice, for_update=True):
        return {"deleted": True, "already_deleted": True, "invoice": invoice}
    doc = _load(doctype, invoice, for_update=True)
    if doc.get("esafepos_session") != shift or str(doc.modified) != expected_modified:
        frappe.throw(_("This sale changed. Reopen the deletion check and review it again."))
    blocker = _blocker(doc, for_update=True)
    if blocker:
        frappe.throw(blocker)
    point = "esafepos_delete_sale"
    frappe.db.savepoint(point)
    try:
        series = _series_snapshot(doc)
        if doc.docstatus == 1:
            doc.cancel()
        if _exists("Loyalty Point Entry", {"invoice": doc.name}, for_update=True):
            frappe.throw(_("ERPNext could not reverse all loyalty entries. The sale was not deleted."))
        key = (doc.get("esafepos_idempotency_key") or "").strip()
        record = frappe.get_doc({"doctype": AUDIT, "deletion_key": _identity(doctype, invoice),
            "invoice_doctype": doctype, "invoice_name": invoice, "pos_profile": doc.pos_profile,
            "company": doc.company, "register_session": shift, "currency": doc.currency,
            "amount": flt(doc.rounded_total or doc.grand_total), "reason": reason,
            "deleted_by": frappe.session.user, "deleted_at": now_datetime(),
            "idempotency_key_hash": _key_hash(key) if key else _key_hash("no-upload:" + _identity(doctype, invoice))})
        record.insert(ignore_permissions=True)
        # No force, link bypass, permission bypass or recoverable Deleted Document.
        frappe.delete_doc(doctype, invoice, delete_permanently=True, ignore_missing=False)
        if series:
            frappe.db.sql("update `tabSeries` set current=greatest(current, %s) where name=%s", (series[1], series[0]))
        # Unlike best-effort diagnostic logging, this audit must commit with the
        # deletion. A failed audit insert rolls the whole operation back.
        frappe.get_doc({"doctype": "EsafePOS Audit Log", "action": "Sale permanently deleted",
            "user": frappe.session.user, "pos_profile": doc.pos_profile, "amount": record.amount,
            "reference_doctype": doctype, "reference_name": invoice, "detail": reason}).insert(ignore_permissions=True)
    except Exception:
        frappe.db.rollback(save_point=point)
        frappe.clear_document_cache(doctype, invoice)
        raise
    return {"deleted": True, "invoice": invoice}
