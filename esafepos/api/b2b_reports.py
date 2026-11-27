"""Company-currency statements from authorized native party-ledger entries."""
import base64

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, now_datetime

from esafepos.api.b2b import context, customer_doc
from esafepos.features import enabled
from esafepos.erpnext_compat import sum_fields


def authorize(pos_profile, customer):
    profile, currency = context(pos_profile)
    doc = customer_doc(customer)
    if not enabled("enable_customer_balances") or not frappe.has_permission("GL Entry", "read"):
        frappe.throw(_("Customer statement access requires customer balances and General Ledger read permission."), frappe.PermissionError)
    return profile, currency, doc


@frappe.whitelist()
def customer_statement(pos_profile, customer, from_date=None, to_date=None):
    profile, currency, doc = authorize(pos_profile, customer)
    to_date = str(getdate(to_date or nowdate()))
    from_date = str(getdate(from_date or (to_date[:8] + "01")))
    if getdate(from_date) > getdate(to_date):
        frappe.throw(_("The statement start date must not follow its end date."))
    filters = {"company": profile.company, "party_type": "Customer", "party": customer}
    if frappe.get_meta("GL Entry").has_field("is_cancelled"):
        filters["is_cancelled"] = 0
    opening_rows = frappe.get_list("GL Entry", filters=dict(filters, posting_date=["<", from_date]),
                                  fields=sum_fields("debit", "credit"), limit_page_length=0)
    opening = sum(flt(row.get("debit")) - flt(row.get("credit")) for row in opening_rows)
    ledger = frappe.get_list("GL Entry", filters=dict(filters, posting_date=["between", [from_date, to_date]]),
                             fields=["name", "posting_date", "voucher_type", "voucher_no", "account", "debit", "credit", "remarks"],
                             order_by="posting_date asc, creation asc, name asc", limit_page_length=10001)
    if len(ledger) > 10000:
        frappe.throw(_("This statement exceeds 10,000 ledger lines. Choose a shorter date range."))
    balance, rows = opening, []
    for row in ledger:
        balance += flt(row.debit) - flt(row.credit)
        rows.append({"date": str(row.posting_date), "doctype": row.voucher_type, "name": row.voucher_no,
                     "account": row.account, "debit": flt(row.debit), "credit": flt(row.credit), "balance": flt(balance, 2),
                     "remarks": row.remarks, "can_open": bool(frappe.has_permission(row.voucher_type, "read", doc=row.voucher_no))})
    current_invoices = frappe.get_list("Sales Invoice", filters={"customer": customer, "company": profile.company,
                                      "docstatus": 1, "outstanding_amount": [">", 0]},
                                      fields=["name", "posting_date", "due_date", "currency", "outstanding_amount", "conversion_rate"],
                                      order_by="due_date asc, name asc", limit_page_length=0)
    pending = []
    if enabled("enable_cheque_tracking") and frappe.has_permission("EsafePOS Customer Cheque", "read"):
        pending = frappe.get_list("EsafePOS Customer Cheque", filters={"company": profile.company, "customer": customer,
                                  "status": ["in", ["Received", "Deposited"]]},
                                  fields=["name", "reference_no", "bank", "cheque_date", "amount", "status"], limit_page_length=0)
    # A voucher may have multiple party GL rows. Read its allocations once.
    payments, seen = [], set()
    for row in ledger:
        if row.voucher_type not in ("Payment Entry", "Journal Entry") or (row.voucher_type, row.voucher_no) in seen:
            continue
        seen.add((row.voucher_type, row.voucher_no))
        payment = frappe.get_doc(row.voucher_type, row.voucher_no)
        if payment.has_permission("read"):
            if row.voucher_type == "Payment Entry":
                payments.append({"name": payment.name, "date": str(payment.posting_date), "mode": payment.mode_of_payment,
                                 "reference": payment.reference_no, "currency": payment.paid_from_account_currency,
                                 "unallocated": flt(payment.unallocated_amount),
                                 "allocations": [{"doctype": ref.reference_doctype, "name": ref.reference_name, "amount": ref.allocated_amount}
                                                 for ref in payment.get("references") or []]})
            else:
                party_rows = [entry for entry in payment.get("accounts") or [] if entry.get("party_type") == "Customer" and entry.get("party") == customer]
                payments.append({"name": payment.name, "date": str(payment.posting_date), "mode": payment.get("mode_of_payment") or "Journal Entry",
                                 "reference": payment.get("cheque_no"), "currency": currency,
                                 "unallocated": sum(max(0, flt(entry.credit) - flt(entry.debit)) for entry in party_rows if not entry.get("reference_name")),
                                 "allocations": [{"doctype": entry.reference_type, "name": entry.reference_name, "amount": flt(entry.credit) - flt(entry.debit)}
                                                 for entry in party_rows if entry.get("reference_name")]})
    return {"customer": customer, "customer_name": doc.customer_name, "company": profile.company, "currency": currency,
            "from_date": from_date, "to_date": to_date, "opening": flt(opening, 2), "closing": flt(balance, 2), "rows": rows,
            "debit": sum(row["debit"] for row in rows), "credit": sum(row["credit"] for row in rows),
            "current_invoices": current_invoices, "payments": payments, "pending_cheques": pending,
            "pending_total": sum(flt(row.amount) for row in pending), "refreshed_at": str(now_datetime())}


@frappe.whitelist()
def statement_pdf(pos_profile, customer, from_date=None, to_date=None):
    statement = customer_statement(pos_profile, customer, from_date, to_date)
    from frappe.utils.pdf import get_pdf
    html = frappe.render_template("templates/print_formats/b2b_statement.html", {"statement": statement})
    output = get_pdf(html, {"page-size": "A4", "margin-top": "12mm", "margin-bottom": "12mm"})
    return {"format": "pdf", "data": base64.b64encode(output).decode("ascii")}
