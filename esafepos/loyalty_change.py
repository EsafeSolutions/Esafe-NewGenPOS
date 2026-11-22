# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
"""Cash change funded into ERPNext's own loyalty ledger, in the sale transaction.

The invoice keeps ERPNext's normal change accounting. A matching Journal Entry
puts the retained change back into cash and credits the program's redemption
expense account. The register records that receipt as Cash In. Points reference
the funding entry, so returning goods does not erase money the customer saved.
"""
import math

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, now_datetime


def lock_customer(customer):
    frappe.db.sql("select name from `tabCustomer` where name=%s for update", customer)


def enabled():
    return not frappe.get_meta("Accounts Settings").has_field("enable_loyalty_point_program") or bool(
        cint(frappe.db.get_single_value("Accounts Settings", "enable_loyalty_point_program"))
    )


def setup(details, company, posting_date=None):
    """Explain configuration problems without changing the site's ERPNext setup."""
    reason = None
    date = getdate(posting_date)
    if not details or not details.get("loyalty_program"):
        reason = _("Enroll this customer in an ERPNext Loyalty Program to save change.")
    elif frappe.get_cached_value("Company", company, "default_currency") != "LKR":
        reason = _("Saving change as points is available for LKR companies only.")
    elif details.get("company") != company:
        reason = _("The Loyalty Program must belong to this outlet's company.")
    elif flt(details.get("conversion_factor")) != 1:
        reason = _("Set the ERPNext Loyalty Program conversion factor to 1 for 1 LKR = 1 point.")
    elif (details.get("from_date") and getdate(details.from_date) > date) or (
        details.get("to_date") and getdate(details.to_date) < date
    ):
        reason = _("The ERPNext Loyalty Program is not active on this date.")
    elif not details.get("expense_account") or not details.get("cost_center"):
        reason = _("Set an expense account and cost center on the ERPNext Loyalty Program.")
    else:
        account = frappe.db.get_value(
            "Account", details.expense_account,
            ["company", "account_currency", "is_group", "disabled", "root_type"], as_dict=True,
        )
        center = frappe.db.get_value("Cost Center", details.cost_center, ["company", "is_group"], as_dict=True)
        if not account or account.company != company or account.account_currency != "LKR" or (
            account.is_group or account.disabled or account.root_type != "Expense"
        ):
            reason = _("Choose an enabled LKR expense ledger for this company's Loyalty Program.")
        elif not center or center.company != company or center.is_group:
            reason = _("Choose a cost center in this company's Loyalty Program.")
    if not reason and not enabled():
        reason = _("Enable Loyalty Point Program in ERPNext Accounts Settings.")
    if not reason and not frappe.get_meta("POS Invoice").has_field("esafepos_loyalty_change_amount"):
        reason = _("Run bench migrate to enable saving change as points.")
    return {"enabled": not bool(reason), "reason": reason}


def prepare(invoice, profile, payload):
    """Validate a requested whole-rupee transfer against the server's invoice."""
    raw = payload.get("loyalty_change_amount")
    if raw in (None, "", 0, "0"):
        return None
    try:
        amount = -1 if isinstance(raw, bool) else float(raw)
    except (TypeError, ValueError):
        amount = -1
    if not math.isfinite(amount) or amount <= 0 or amount != int(amount):
        frappe.throw(_("Save whole LKR amounts as loyalty points."))
    if cint(payload.get("queued_offline")) or payload.get("original_invoice") or payload.get("is_exchange"):
        frappe.throw(_("Saving change as points requires an online sale, outside an exchange."))
    from esafepos import walk_in
    if not payload.get("customer") or invoice.customer == walk_in.FALLBACK_CUSTOMER:
        frappe.throw(_("Select a loyalty customer before saving change as points."))
    if invoice.currency != "LKR" or flt(invoice.conversion_rate) != 1 or invoice.get("is_return"):
        frappe.throw(_("Save change as points on LKR sales only."))
    lock_customer(invoice.customer)
    from esafepos.erpnext_compat import loyalty_details
    details = loyalty_details(invoice.customer, profile.company)
    status = setup(details, profile.company, invoice.posting_date)
    if not status["enabled"]:
        frappe.throw(status["reason"])
    if any(p.get("mode_of_payment") == "Credit Sale" and flt(p.get("amount")) for p in payload.get("payments") or []):
        frappe.throw(_("A sale on account cannot save change as points."))
    cash = sum(flt(p.amount) for p in invoice.payments if
               frappe.get_cached_value("Mode of Payment", p.mode_of_payment, "type") == "Cash")
    total = flt(invoice.rounded_total) or flt(invoice.grand_total)
    paid = sum(flt(p.amount) for p in invoice.payments)
    change = flt(paid + flt(invoice.get("loyalty_amount")) - total, 2)
    if amount > min(change, cash) + 0.000001:
        frappe.throw(_("The points amount cannot exceed the cash change available."))
    return {"amount": int(amount), "details": details}


def book(invoice, plan):
    if not plan:
        return
    from esafepos import credit_sales
    from esafepos.api.register import _drawer_mode
    amount, details = plan["amount"], plan["details"]
    if flt(invoice.change_amount) + 0.000001 < amount:
        frappe.throw(_("ERPNext's final change is less than the amount to save as points."))
    drawer = _drawer_mode(invoice.pos_profile)
    cash_account = frappe.db.get_value(
        "Mode of Payment Account", {"parent": drawer, "company": invoice.company}, "default_account"
    ) if drawer else None
    if not cash_account or cash_account != invoice.account_for_change_amount:
        frappe.throw(_("The POS cash drawer must use ERPNext's Account for Change Amount to save points."))
    account = frappe.db.get_value("Account", cash_account, ["account_type", "account_currency"], as_dict=True)
    if not account or account.account_type != "Cash" or account.account_currency != "LKR":
        frappe.throw(_("Saving change needs an LKR cash drawer account."))
    dims = credit_sales._dimensions(invoice)
    entry = frappe.get_doc({
        "doctype": "Journal Entry", "voucher_type": "Journal Entry", "company": invoice.company,
        "posting_date": invoice.posting_date,
        "user_remark": _("Change saved as loyalty points for {0} {1}").format(invoice.doctype, invoice.name),
        "accounts": [
            dict(dims, account=cash_account, debit_in_account_currency=amount, cost_center=details.cost_center),
            dict(dims, account=details.expense_account, credit_in_account_currency=amount, cost_center=details.cost_center),
        ],
    })
    entry_name = credit_sales.post(entry)
    frappe.get_doc({
        "doctype": "Loyalty Point Entry", "company": invoice.company, "customer": invoice.customer,
        "loyalty_program": details.loyalty_program, "loyalty_program_tier": details.get("tier_name"),
        "invoice_type": "Journal Entry", "invoice": entry_name, "loyalty_points": amount,
        "purchase_amount": 0, "posting_date": invoice.posting_date,
        "expiry_date": add_days(invoice.posting_date, cint(details.expiry_duration)) if cint(details.expiry_duration) else "9999-12-31",
    }).insert(ignore_permissions=True)
    invoice.db_set({"esafepos_loyalty_change_amount": amount, "esafepos_loyalty_change_entry": entry_name})
    register = frappe.get_doc("POS Register Session", invoice.esafepos_session)
    register.append("cash_movements", {
        "movement_type": "Cash In", "mode_of_payment": drawer, "amount": amount,
        "reason": _("Change to loyalty: {0}").format(invoice.name),
        "recorded_at": now_datetime(), "recorded_by": frappe.session.user,
        "loyalty_change_entry": entry_name,
    })
    register.save(ignore_permissions=True)


def complete_redemption(invoice):
    """Older ERPNext releases skip points earned on another document type.

    Complete only their missing deduction from funded Journal Entry lots. The
    normal ERPNext ledger remains authoritative, including expiry and refunds.
    The customer row is locked before invoice submission by the sales API.
    """
    requested = cint(invoice.get("loyalty_points")) if invoice.get("redeem_loyalty_points") else 0
    if not requested:
        return
    spent = -sum(cint(row.loyalty_points) for row in frappe.get_all(
        "Loyalty Point Entry", filters={"invoice_type": invoice.doctype, "invoice": invoice.name,
                                       "loyalty_points": ["<", 0]}, fields=["loyalty_points"],
    ))
    left = requested - spent
    if left < 0:
        frappe.throw(_("ERPNext deducted more loyalty points than requested. The sale was not completed."))
    if not left:
        return
    lots = frappe.get_all("Loyalty Point Entry", filters={
        "customer": invoice.customer, "company": invoice.company, "loyalty_program": invoice.loyalty_program,
        "invoice_type": "Journal Entry", "loyalty_points": [">", 0],
        "posting_date": ["<=", invoice.posting_date], "expiry_date": [">=", invoice.posting_date],
    }, fields=["name", "loyalty_points", "expiry_date", "loyalty_program_tier"], order_by="expiry_date asc, creation asc")
    for lot in lots:
        used = sum(cint(r.loyalty_points) for r in frappe.get_all(
            "Loyalty Point Entry", filters={"redeem_against": lot.name}, fields=["loyalty_points"],
        ))
        take = min(left, max(0, cint(lot.loyalty_points) + used))
        if take:
            frappe.get_doc({
                "doctype": "Loyalty Point Entry", "company": invoice.company, "customer": invoice.customer,
                "loyalty_program": invoice.loyalty_program, "loyalty_program_tier": lot.loyalty_program_tier,
                "invoice_type": invoice.doctype, "invoice": invoice.name, "redeem_against": lot.name,
                "loyalty_points": -take, "purchase_amount": 0, "posting_date": invoice.posting_date,
                "expiry_date": lot.expiry_date,
            }).insert(ignore_permissions=True)
            left -= take
        if not left:
            return
    frappe.throw(_("ERPNext could not deduct the requested loyalty points. The sale was not completed."))


def cancel_invoice(doc, method=None):
    entry = doc.get("esafepos_loyalty_change_entry")
    if not entry or doc.get("is_return"):
        return
    lock_customer(doc.customer)
    frappe.db.sql("select name from `tabPOS Register Session` where name=%s for update", doc.esafepos_session)
    if frappe.db.get_value("POS Register Session", doc.esafepos_session, "status") != "Open":
        frappe.throw(_("Reopen the register before cancelling a sale with change saved as points."))
    lots = frappe.get_all("Loyalty Point Entry", filters={"invoice_type": "Journal Entry", "invoice": entry}, pluck="name")
    for name in lots:
        if frappe.db.exists("Loyalty Point Entry", {"redeem_against": name}):
            frappe.throw(_("Cancel the sales that spent this saved change before cancelling its original sale."))
    for name in lots:
        frappe.delete_doc("Loyalty Point Entry", name, ignore_permissions=True)
    # Release the submitted invoice's backlink before cancelling the funding.
    doc.db_set("esafepos_loyalty_change_entry", None)
    journal = frappe.get_doc("Journal Entry", entry)
    journal.flags.ignore_permissions = True
    was = frappe.flags.ignore_account_permission
    frappe.flags.ignore_account_permission = True
    try:
        journal.cancel()
    finally:
        frappe.flags.ignore_account_permission = was
    register = frappe.get_doc("POS Register Session", doc.esafepos_session)
    register.set("cash_movements", [r for r in register.cash_movements if r.get("loyalty_change_entry") != entry])
    register.save(ignore_permissions=True)
    doc.db_set("esafepos_loyalty_change_amount", 0)


def guard_funding_cancel(doc, method=None):
    for doctype in ("POS Invoice", "Sales Invoice"):
        if frappe.get_meta(doctype).has_field("esafepos_loyalty_change_entry") and frappe.db.exists(
            doctype, {"esafepos_loyalty_change_entry": doc.name, "docstatus": 1}
        ):
            frappe.throw(_("Cancel the original POS sale to reverse its saved change and points together."))
