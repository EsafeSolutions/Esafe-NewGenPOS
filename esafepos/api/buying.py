"""Simple buying at the POS, backed by native ERPNext stock and accounting."""

import hashlib
import json
import math
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from esafepos.api import permissions
from esafepos.features import enabled


CAPABILITY = "Manage buying and suppliers"
MAX_ROWS = 200


def can_buy():
    return bool(enabled("enable_buying") and permissions.allowed(CAPABILITY)
                and frappe.has_permission("Supplier", "read")
                and frappe.has_permission("Purchase Invoice", "read"))


def _context(pos_profile):
    if not can_buy():
        frappe.throw(_("Buying is disabled or your account does not have buying access."), frappe.PermissionError)
    permissions.assert_outlet(pos_profile)
    profile = frappe.get_cached_doc("POS Profile", pos_profile)
    return profile, frappe.get_cached_value("Company", profile.company, "default_currency")


def _require(doctype, action):
    if not frappe.has_permission(doctype, action):
        frappe.throw(_("You do not have {0} permission on {1}.").format(action, doctype), frappe.PermissionError)


def _rows(value, label):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            frappe.throw(_("Invalid {0}.").format(label))
    if not isinstance(value, list) or len(value) > MAX_ROWS or any(not isinstance(row, dict) for row in value):
        frappe.throw(_("Enter at most {0} valid {1}.").format(MAX_ROWS, label))
    return value


def _number(value, label, positive=True):
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        frappe.throw(_("Enter a valid {0}.").format(label))
    if not math.isfinite(number) or number < 0 or (positive and number == 0):
        frappe.throw(_("Enter a valid {0}.").format(label))
    return number


def _date(value, label):
    try:
        return str(getdate(value))
    except (ValueError, TypeError, OverflowError):
        frappe.throw(_("Enter a valid {0}.").format(label))


def _supplier(name, lock=False):
    doc = frappe.get_doc("Supplier", name)
    doc.check_permission("read")
    if doc.disabled:
        frappe.throw(_("This supplier is disabled."))
    if lock:
        # Serializes retries and concurrent POS settlements for this supplier.
        frappe.db.sql("select name from `tabSupplier` where name = %s for update", (name,))
    return doc


def _account(name, company, currency, types=None):
    doc = frappe.get_doc("Account", name)
    doc.check_permission("read")
    if doc.company != company or doc.is_group or doc.disabled or (doc.account_currency or currency) != currency:
        frappe.throw(_("Choose an enabled {0} account in {1}.").format(currency, company))
    if types and doc.account_type not in types:
        frappe.throw(_("Choose a {0} account.").format(" / ".join(types)))
    return doc


def _payable(supplier, company, currency):
    from erpnext.accounts.party import get_party_account

    name = get_party_account("Supplier", supplier, company)
    _account(name, company, currency, ("Payable",))
    return name


def _identity(doctype, key, payload):
    key = str(key or "").strip()
    if not key or len(key) > 100:
        frappe.throw(_("A valid request ID is required. Reopen the form and try again."))
    if not frappe.get_meta(doctype).has_field("esafepos_buying_key"):
        frappe.throw(_("Run the EsafePOS site migration before using Buying."))
    identity = hashlib.sha256((frappe.session.user + ":" + doctype + ":" + key).encode()).hexdigest()
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
    return identity, fingerprint


def _previous(doctype, identity, fingerprint, company=None):
    name = frappe.db.get_value(doctype, {"esafepos_buying_key": identity}, "name")
    if not name:
        return None
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    if doc.esafepos_buying_hash != fingerprint or (company and doc.company != company):
        frappe.throw(_("This request ID was already used for different details."))
    expected = 0 if doctype == "Supplier" else 1
    if doc.docstatus != expected:
        frappe.throw(_("The earlier document is no longer active. Review it in ERPNext."))
    return doc


def _submit(doc, identity, fingerprint, profile):
    from esafepos.api.stock_app import _has_workflow

    if _has_workflow(doc.doctype):
        frappe.throw(_("This document requires an approval workflow. Create it in ERPNext."))
    doc.check_permission("create")
    doc.check_permission("submit")
    doc.esafepos_buying_key = identity
    doc.esafepos_buying_hash = fingerprint
    doc.esafepos_buying_profile = profile.name
    doc.insert()
    doc.submit()
    return doc


def _summary(doc):
    return {"name": doc.name, "doctype": doc.doctype, "docstatus": doc.docstatus,
            "grand_total": doc.get("grand_total"), "outstanding_amount": doc.get("outstanding_amount"),
            "paid_amount": doc.get("paid_amount"), "currency": doc.get("currency")}


@frappe.whitelist()
def options(pos_profile):
    profile, currency = _context(pos_profile)
    has = frappe.has_permission
    accounts = frappe.get_list("Account", filters={"company": profile.company, "is_group": 0, "disabled": 0},
                               fields=["name", "account_type", "account_currency", "root_type"], limit_page_length=0) if has("Account", "read") else []
    accounts = [row for row in accounts if (row.account_currency or currency) == currency]
    modes = []
    available_modes = frappe.get_list("Mode of Payment", filters={"enabled": 1, "type": ["in", ["Cash", "Bank"]]},
                                      fields=["name", "type"], order_by="name", limit_page_length=0) if has("Mode of Payment", "read") else []
    for mode in available_modes:
        account = frappe.db.get_value("Mode of Payment Account", {"parent": mode.name, "company": profile.company}, "default_account")
        if any(row.name == account and row.account_type == mode.type for row in accounts):
            modes.append({"name": mode.name, "type": mode.type, "account": account})
    return {"company": profile.company, "currency": currency, "today": nowdate(),
            "warehouse": profile.warehouse,
            "warehouses": frappe.get_list("Warehouse", filters={"company": profile.company, "is_group": 0, "disabled": 0},
                                           pluck="name", order_by="name", limit_page_length=0) if has("Warehouse", "read") else [],
            "cost_accounts": [row.name for row in accounts if row.root_type == "Expense" and row.account_type not in ("Cost of Goods Sold",)],
            "payment_modes": modes,
            "supplier_groups": frappe.get_list("Supplier Group", filters={"is_group": 0}, pluck="name", limit_page_length=0) if has("Supplier Group", "read") else [],
            "can_create_supplier": bool(has("Supplier", "create") and has("Supplier Group", "read")),
            "can_create_invoice": bool(has("Purchase Invoice", "create") and has("Purchase Invoice", "submit") and has("Account", "read") and has("Warehouse", "read") and has("Item", "read")),
            "can_pay": bool(has("Payment Entry", "read") and has("Payment Entry", "create") and has("Payment Entry", "submit") and has("Account", "read") and has("Mode of Payment", "read"))}


@frappe.whitelist()
def search_suppliers(pos_profile, search="", start=0):
    _context(pos_profile)
    filters = {"disabled": 0}
    query = str(search or "").strip()[:100]
    return frappe.get_list("Supplier", filters=filters,
                           or_filters={"supplier_name": ["like", "%" + query + "%"], "name": ["like", "%" + query + "%"]} if query else None,
                           fields=["name", "supplier_name", "supplier_group"], order_by="supplier_name asc, name asc",
                           limit_start=max(0, cint(start)), limit_page_length=30)


@frappe.whitelist(methods=["POST"])
def create_supplier(pos_profile, supplier_name, supplier_group, idempotency_key):
    _context(pos_profile)
    _require("Supplier", "create")
    supplier_name = str(supplier_name or "").strip()
    if not supplier_name or len(supplier_name) > 140:
        frappe.throw(_("Enter a supplier name of at most 140 characters."))
    group = frappe.get_doc("Supplier Group", supplier_group)
    group.check_permission("read")
    if group.is_group:
        frappe.throw(_("Choose a supplier group without child groups."))
    identity, fingerprint = _identity("Supplier", idempotency_key, {"name": supplier_name, "group": supplier_group})
    doc = _previous("Supplier", identity, fingerprint)
    if not doc:
        doc = frappe.get_doc({"doctype": "Supplier", "supplier_name": supplier_name, "supplier_group": supplier_group,
                              "supplier_type": "Company", "esafepos_buying_key": identity, "esafepos_buying_hash": fingerprint})
        doc.check_permission("create")
        doc.insert()
    return {"name": doc.name, "supplier_name": doc.supplier_name, "supplier_group": doc.supplier_group}


@frappe.whitelist()
def search_items(pos_profile, search=""):
    _context(pos_profile)
    query = str(search or "").strip()[:100]
    if not query:
        return []
    return frappe.get_list("Item", filters={"disabled": 0, "is_purchase_item": 1, "has_variants": 0,
                                            "is_fixed_asset": 0, "has_serial_no": 0, "has_batch_no": 0},
                           or_filters={"name": ["like", "%" + query + "%"], "item_name": ["like", "%" + query + "%"]},
                           fields=["name", "item_name", "stock_uom", "is_stock_item", "last_purchase_rate"],
                           order_by="item_name", limit_page_length=20)


def _invoice_rows(profile, supplier, outstanding=False, start=0):
    filters = {"company": profile.company, "supplier": supplier, "docstatus": 1}
    if outstanding:
        filters.update({"is_return": 0, "outstanding_amount": [">", 0]})
    return frappe.get_list("Purchase Invoice", filters=filters,
                           fields=["name", "posting_date", "due_date", "bill_no", "grand_total", "outstanding_amount", "currency", "credit_to", "status", "is_return"],
                           order_by="posting_date asc, name asc" if outstanding else "posting_date desc, name desc",
                           limit_start=max(0, cint(start)), limit_page_length=0 if outstanding else 50)


@frappe.whitelist()
def supplier_account(pos_profile, supplier, start=0):
    profile, currency = _context(pos_profile)
    _supplier(supplier)
    balance = None
    if frappe.has_permission("GL Entry", "read"):
        totals = frappe.get_list("GL Entry", filters={"company": profile.company, "party_type": "Supplier", "party": supplier, "is_cancelled": 0},
                                 fields=["sum(credit) as credit", "sum(debit) as debit"], limit_page_length=1)
        balance = flt(totals[0].credit) - flt(totals[0].debit) if totals else 0
    open_invoices = _invoice_rows(profile, supplier, outstanding=True)
    payments = []
    if frappe.has_permission("Payment Entry", "read"):
        payment_fields = ["name", "posting_date", "payment_type", "mode_of_payment", "paid_amount", "paid_from_account_currency", "reference_no", "reference_date", "clearance_date"]
        if frappe.get_meta("Payment Entry").has_field("esafepos_supplier_payment_method"):
            payment_fields.append("esafepos_supplier_payment_method")
        payments = frappe.get_list("Payment Entry", filters={"company": profile.company, "party_type": "Supplier", "party": supplier, "docstatus": 1},
                                    fields=payment_fields,
                                    order_by="posting_date desc, name desc", limit_page_length=50)
    return {"currency": currency, "balance": balance, "open_invoices": open_invoices,
            "invoices": _invoice_rows(profile, supplier, start=start), "payments": payments}


@frappe.whitelist()
def invoice_details(pos_profile, name):
    profile, currency = _context(pos_profile)
    doc = frappe.get_doc("Purchase Invoice", name)
    doc.check_permission("read")
    if doc.company != profile.company:
        frappe.throw(_("This invoice belongs to another company."), frappe.PermissionError)
    return {**_summary(doc), "supplier": doc.supplier, "bill_no": doc.bill_no,
            "posting_date": doc.posting_date, "update_stock": doc.update_stock,
            "items": [{"item_code": row.item_code, "item_name": row.item_name, "qty": row.qty,
                       "uom": row.uom, "rate": row.rate, "amount": row.amount, "valuation_rate": row.valuation_rate,
                       "stock_qty": row.stock_qty, "warehouse": row.warehouse} for row in doc.items],
            "costs": [{"description": row.description, "amount": row.tax_amount, "category": row.category} for row in doc.taxes]}


@frappe.whitelist(methods=["POST"])
def create_invoice(pos_profile, supplier, items, warehouse, idempotency_key, costs=None,
                   bill_no=None, bill_date=None, posting_date=None, due_date=None):
    profile, currency = _context(pos_profile)
    _require("Purchase Invoice", "create")
    _require("Purchase Invoice", "submit")
    items = _rows(items, "items")
    costs = _rows(costs or [], "additional costs")
    identity, fingerprint = _identity("Purchase Invoice", idempotency_key,
        {"profile": pos_profile, "supplier": supplier, "items": items, "costs": costs, "warehouse": warehouse,
         "bill_no": bill_no, "bill_date": bill_date, "posting_date": posting_date, "due_date": due_date})
    _supplier(supplier, lock=True)
    prior = _previous("Purchase Invoice", identity, fingerprint, profile.company)
    if prior:
        return _summary(prior)
    if not items:
        frappe.throw(_("Add at least one item."))
    posting = _date(posting_date or nowdate(), "posting date")
    due = _date(due_date or posting, "due date")
    if due < posting:
        frappe.throw(_("Due date cannot be before the posting date."))
    wh = frappe.get_doc("Warehouse", warehouse)
    wh.check_permission("read")
    if wh.company != profile.company or wh.is_group or wh.disabled:
        frappe.throw(_("Choose an enabled warehouse in this company."))
    rows = []
    for row in items:
        item = frappe.get_doc("Item", row.get("item_code"))
        item.check_permission("read")
        if item.disabled or not item.is_purchase_item or item.has_variants or item.is_fixed_asset or item.has_serial_no or item.has_batch_no:
            frappe.throw(_("Use ERPNext for disabled, template, asset, serial or batch tracked items."))
        if costs and not item.is_stock_item:
            frappe.throw(_("Valuation costs require stock items on every invoice line."))
        rows.append({"item_code": item.name, "qty": _number(row.get("qty"), "quantity"),
                     "rate": _number(row.get("rate"), "purchase rate"), "uom": item.stock_uom,
                     "conversion_factor": 1, "warehouse": warehouse, "cost_center": profile.cost_center})
    taxes = []
    for row in costs:
        account = _account(row.get("account"), profile.company, currency)
        if account.root_type != "Expense":
            frappe.throw(_("Select an expense account for additional valuation costs."))
        description = str(row.get("description") or "").strip()
        if not description or len(description) > 140:
            frappe.throw(_("Enter a cost description of at most 140 characters."))
        taxes.append({"charge_type": "Actual", "account_head": account.name,
                      "description": description, "tax_amount": _number(row.get("amount"), "additional cost"),
                      "category": "Valuation and Total", "add_deduct_tax": "Add", "cost_center": profile.cost_center})
    doc = frappe.get_doc({"doctype": "Purchase Invoice", "supplier": supplier, "company": profile.company,
                          "currency": currency, "conversion_rate": 1, "party_account_currency": currency,
                          "credit_to": _payable(supplier, profile.company, currency),
                          "posting_date": posting, "due_date": due, "bill_no": str(bill_no or "").strip()[:140],
                          "bill_date": _date(bill_date, "supplier invoice date") if bill_date else None,
                          "update_stock": 1, "set_warehouse": warehouse, "cost_center": profile.cost_center,
                          "is_paid": 0, "ignore_pricing_rule": 1, "disable_rounded_total": 1,
                          "items": rows, "taxes": taxes})
    doc.run_method("set_missing_values")
    # Supplier defaults must not silently add a second tax template or change
    # the payable currency in this deliberately company-currency workflow.
    doc.set("taxes", taxes)
    doc.currency = currency
    doc.conversion_rate = 1
    return _summary(_submit(doc, identity, fingerprint, profile))


def _allocate(invoices, selected, amount, currency):
    chosen = set(selected)
    by_name = {row.name: row for row in invoices}
    if not chosen or chosen - set(by_name):
        frappe.throw(_("Select unpaid invoices and refresh their balances."))
    rows = [row for row in invoices if row.name in chosen]
    if any(row.currency != currency for row in rows) or len({row.credit_to for row in rows}) != 1:
        frappe.throw(_("Pay invoices in the company currency on the same payable account."))
    available = sum(Decimal(str(row.outstanding_amount)) for row in rows)
    remaining = Decimal(str(amount))
    if remaining > available:
        frappe.throw(_("The payment exceeds the selected invoices' outstanding balance. Refresh and try again."))
    references = []
    for row in rows:
        take = min(Decimal(str(row.outstanding_amount)), remaining)
        if take > 0:
            references.append({"reference_doctype": "Purchase Invoice", "reference_name": row.name, "allocated_amount": float(take)})
            remaining -= take
    return rows[0].credit_to, references


@frappe.whitelist(methods=["POST"])
def pay_supplier(pos_profile, supplier, invoices, amount, payment_method, mode_of_payment,
                 idempotency_key, reference_no=None, reference_date=None, posting_date=None):
    profile, currency = _context(pos_profile)
    for action in ("read", "create", "submit"):
        _require("Payment Entry", action)
    selected = _rows(invoices, "invoice selections")
    names = [row.get("name") for row in selected]
    if any(not isinstance(name, str) or not name for name in names) or len(set(names)) != len(names):
        frappe.throw(_("Choose each invoice only once."))
    amount = _number(amount, "payment amount")
    identity, fingerprint = _identity("Payment Entry", idempotency_key,
        {"profile": pos_profile, "supplier": supplier, "invoices": names, "amount": amount,
         "method": payment_method, "mode": mode_of_payment, "reference": reference_no,
         "reference_date": reference_date, "posting_date": posting_date})
    _supplier(supplier, lock=True)
    prior = _previous("Payment Entry", identity, fingerprint, profile.company)
    if prior:
        return _summary(prior)
    if payment_method not in ("Cash", "Bank Transfer", "Cheque"):
        frappe.throw(_("Choose cash, bank transfer or cheque."))
    mode = frappe.get_doc("Mode of Payment", mode_of_payment)
    mode.check_permission("read")
    expected_type = "Cash" if payment_method == "Cash" else "Bank"
    if not mode.enabled or mode.type != expected_type:
        frappe.throw(_("Select a compatible enabled payment mode."))
    paid_from = frappe.db.get_value("Mode of Payment Account", {"parent": mode.name, "company": profile.company}, "default_account")
    _account(paid_from, profile.company, currency, (expected_type,))
    if payment_method != "Cash" and (not str(reference_no or "").strip() or not reference_date):
        frappe.throw(_("Enter the cheque or transfer reference and its date."))
    posting = _date(posting_date or nowdate(), "payment date")
    # Native ERPNext may also settle these invoices. Lock their current rows,
    # then read fresh outstanding amounts before building the references.
    for name in sorted(names):
        frappe.db.sql("select name from `tabPurchase Invoice` where name = %s for update", (name,))
    open_rows = _invoice_rows(profile, supplier, outstanding=True)
    paid_to, references = _allocate(open_rows, names, amount, currency)
    _account(paid_to, profile.company, currency, ("Payable",))
    for row in references:
        invoice = frappe.get_doc("Purchase Invoice", row["reference_name"])
        invoice.check_permission("read")
        if str(invoice.posting_date) > posting:
            frappe.throw(_("The payment date cannot be before an allocated invoice."))
    doc = frappe.get_doc({"doctype": "Payment Entry", "payment_type": "Pay", "party_type": "Supplier", "party": supplier,
                          "company": profile.company, "posting_date": posting, "mode_of_payment": mode.name,
                          "paid_from": paid_from, "paid_to": paid_to, "paid_from_account_currency": currency,
                          "paid_to_account_currency": currency, "paid_amount": amount, "received_amount": amount,
                          "source_exchange_rate": 1, "target_exchange_rate": 1,
                          "reference_no": str(reference_no or "").strip()[:140],
                          "reference_date": _date(reference_date, "reference date") if reference_date else None,
                          "cost_center": profile.cost_center, "references": references,
                          "esafepos_supplier_payment_method": payment_method})
    return _summary(_submit(doc, identity, fingerprint, profile))
