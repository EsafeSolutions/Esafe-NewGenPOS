"""Idempotent schema setup; no historical accounting records are rewritten."""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def setup():
    fields = {}
    for kind in ("Quotation", "Sales Order", "Delivery Note", "Sales Invoice", "Payment Entry"):
        meta = frappe.get_meta(kind)
        additions = [
            dict(fieldname="esafepos_b2b_key", label="B2B Request Identity", fieldtype="Data", unique=1, no_copy=1),
            dict(fieldname="esafepos_b2b_hash", label="B2B Request Hash", fieldtype="Data", no_copy=1),
            dict(fieldname="esafepos_b2b_last_key", label="B2B Last Save Identity", fieldtype="Data", no_copy=1),
            dict(fieldname="esafepos_b2b_last_hash", label="B2B Last Save Hash", fieldtype="Data", no_copy=1),
            dict(fieldname="esafepos_b2b_profile", label="B2B Outlet", fieldtype="Link", options="POS Profile", search_index=1),
            dict(fieldname="esafepos_b2b_manual", label="B2B Manual Pricing", fieldtype="Long Text"),
            dict(fieldname="esafepos_b2b_approval", label="B2B Discount Approval", fieldtype="Link", options="POS Approval Request", no_copy=1),
            dict(fieldname="esafepos_b2b_approved_percent", label="B2B Approved Discount", fieldtype="Percent", no_copy=1),
        ]
        if kind == "Payment Entry":
            additions.extend([
                dict(fieldname="esafepos_b2b_session", label="B2B Collection Shift", fieldtype="Link", options="POS Register Session", search_index=1, no_copy=1),
                dict(fieldname="esafepos_b2b_settlement", label="B2B Settlement", fieldtype="Link", options="EsafePOS B2B Settlement", no_copy=1),
            ])
        fields[kind] = [dict(row, read_only=1, hidden=1) for row in additions if not meta.has_field(row["fieldname"])]
    create_custom_fields(fields, update=True)
    with open(frappe.get_app_path("esafepos", "templates", "print_formats", "b2b.html"), encoding="utf-8") as source:
        template = source.read()
    for kind in ("Quotation", "Sales Order", "Delivery Note", "Sales Invoice"):
        name = "ESAFE B2B " + kind
        if not frappe.db.exists("Print Format", name):
            frappe.get_doc({"doctype": "Print Format", "name": name, "doc_type": kind, "module": "EsafePOS",
                            "standard": "No", "custom_format": 1, "print_format_type": "Jinja", "html": template}).insert(ignore_permissions=True)


def validate_envelope(doc):
    if not doc.flags.get("b2b_operation"):
        frappe.throw("Use the ESAFE B2B workspace to change this record.", frappe.PermissionError)


def has_permission(doc, user=None, permission_type=None, **kwargs):
    from esafepos.api import permissions
    from esafepos.features import enabled
    if permission_type not in (None, "read", "print"):
        return False
    return bool(enabled("enable_regular_invoices") and permissions.can_take_customer_payments(user)
                and permissions.can_use_outlet(doc.pos_profile, user)
                and frappe.has_permission("Customer", "read", doc=doc.customer, user=user))


def query_conditions(user=None):
    from esafepos.api import permissions
    if not permissions.can_take_customer_payments(user):
        return "1=0"
    profiles = [name for name in frappe.get_all("POS Profile", pluck="name") if permissions.can_use_outlet(name, user)]
    return "pos_profile in ({0})".format(",".join(frappe.db.escape(name) for name in profiles)) if profiles else "1=0"
