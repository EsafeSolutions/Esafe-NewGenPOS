"""Shared ERPNext billing customer for anonymous sales without an outlet default."""

import re
import secrets

import frappe
from frappe import _
from frappe.utils import cint

FALLBACK_CUSTOMER = "ESAFE POS Walk-in"


def enabled():
    return bool(cint(frappe.db.get_single_value("EsafePOS Settings", "enable_walk_in_codes")))


def default_customer(profile):
    if profile.customer:
        return profile.customer
    if enabled():
        return frappe.db.get_value("Customer", {"name": FALLBACK_CUSTOMER, "disabled": 0})
    return None


def billing_customer(profile, selected_customer):
    customer = selected_customer or default_customer(profile)
    if customer:
        return customer
    if enabled():
        frappe.throw(_("The automatic walk-in customer is unavailable. Ask a manager to enable it in ERPNext or save General Settings again."))
    frappe.throw(_("Select a customer (or set a default customer on the POS Profile)"))


def assign_receipt_code(invoice, selected_customer):
    if selected_customer and selected_customer != FALLBACK_CUSTOMER:
        return
    if invoice.meta.has_field("esafepos_walk_in_code") and enabled():
        invoice.esafepos_walk_in_code = "W-" + secrets.token_hex(8).upper()


def contact_number(value):
    raw = (value or "").strip()
    number = re.sub(r"[ ()-]", "", raw)
    return number if len(raw) <= 32 and re.fullmatch(r"\+?[0-9]{7,15}", number) else ""


def receipt_customer_name(invoice):
    return (
        invoice.get("esafepos_walk_in_phone")
        or (invoice.get("esafepos_walk_in_name") if invoice.get("esafepos_walk_in_code") else None)
        or invoice.get("esafepos_walk_in_code")
        or invoice.get("customer_name")
        or ""
    )


def ensure_customer():
    """Provision a fixed internal customer during setup, outside checkout."""
    if frappe.db.exists("Customer", FALLBACK_CUSTOMER):
        return

    from esafepos.api.catalog import _customer_group
    from esafepos.internal_accounts import fill_required_custom_fields

    selling = frappe.get_cached_doc("Selling Settings")
    territory = selling.territory or frappe.db.get_value("Territory", {"is_group": 0}, "name", order_by="lft asc")
    customer = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": FALLBACK_CUSTOMER,
        "customer_type": "Individual",
        "customer_group": _customer_group("Individual", selling.customer_group),
        "territory": territory,
    })
    fill_required_custom_fields(customer, FALLBACK_CUSTOMER)
    # This is an internal billing record with fixed identity and no contact.
    frappe.db.savepoint("esafepos_walk_in_customer")
    try:
        customer.insert(ignore_permissions=True, set_name=FALLBACK_CUSTOMER)
    except frappe.DuplicateEntryError:
        frappe.db.rollback(save_point="esafepos_walk_in_customer")
        if not frappe.db.get_value("Customer", FALLBACK_CUSTOMER, "name", for_update=True):
            raise
        return
    # ERPNext can enrol a new Customer through a group's automatic loyalty program.
    if customer.loyalty_program:
        customer.db_set({"loyalty_program": None, "loyalty_program_tier": None})
