"""Native B2B receipts, advance reconciliation, and cheque custody.

The settlement and cheque records are operational envelopes, never ledgers.
All financial effects come from submitted ERPNext Payment Entries.
"""
import json

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate, now_datetime

from esafepos.api import permissions
from esafepos.api.b2b import context, customer_doc, data, identity, lock_customer, document, audit
from esafepos.b2b_rules import allocate, number, money, cheque_transition
from esafepos.features import enabled

SETTLEMENT = "EsafePOS B2B Settlement"
CHEQUE = "EsafePOS Customer Cheque"


def _precision(currency):
    from frappe.model.meta import get_field_precision
    return get_field_precision(frappe.get_meta("Payment Entry").get_field("paid_amount"), currency=currency)


def _amount(value, currency):
    raw = number(value, "payment amount", positive=True)
    precision = _precision(currency)
    rounded = money(raw, precision)
    if raw != rounded:
        frappe.throw(_("Use at most {0} decimal places for this currency.").format(precision))
    return float(rounded)


def _pay_context(pos_profile):
    profile, currency = context(pos_profile)
    if not enabled("enable_customer_payments") or not permissions.can_take_customer_payments():
        frappe.throw(_("You cannot collect customer payments."), frappe.PermissionError)
    for action in ("read", "create", "submit"):
        if not frappe.has_permission("Payment Entry", action):
            frappe.throw(_("Payment Entry {0} permission is required.").format(action), frappe.PermissionError)
    return profile, currency


def _account(name, company, currency, account_type):
    doc = frappe.get_doc("Account", name)
    if doc.company != company or doc.is_group or doc.disabled or doc.account_currency != currency or doc.account_type != account_type:
        frappe.throw(_("Configure a compatible company-currency payment account."))
    return doc


def _mode(profile, currency, mode_name, method):
    if method not in ("Cash", "Bank Transfer", "Cheque"):
        frappe.throw(_("Choose cash, bank transfer, or cheque."))
    if mode_name not in {row.mode_of_payment for row in profile.get("payments") or []}:
        frappe.throw(_("Choose a payment method configured on this outlet."))
    mode = frappe.get_doc("Mode of Payment", mode_name)
    mode.check_permission("read")
    expected = "Cash" if method == "Cash" else "Bank"
    if not mode.enabled or mode.type != expected:
        frappe.throw(_("Choose a payment mode compatible with this tender."))
    account = frappe.db.get_value("Mode of Payment Account", {"parent": mode.name, "company": profile.company}, "default_account")
    _account(account, profile.company, currency, expected)
    return account


def _session(profile, collection_context, posting_date):
    if collection_context not in ("Till", "Back office"):
        frappe.throw(_("Choose Till or Back office collection."))
    if getdate(posting_date) > getdate(nowdate()):
        frappe.throw(_("A received payment cannot be posted in the future."))
    if collection_context == "Back office":
        return None
    if getdate(posting_date) != getdate(nowdate()):
        frappe.throw(_("Till collections must use today's date."))
    from esafepos.api.session import get_open_session
    from esafepos.api.sales import _lock_open_session
    session = get_open_session(profile.name)
    if not session:
        frappe.throw(_("Open the register before taking a till collection."))
    _lock_open_session(session["name"])
    return session["name"]


def _open_invoices(profile, customer, currency, lock=False):
    customer_doc(customer)
    rows = frappe.get_list("Sales Invoice", filters={"company": profile.company, "customer": customer,
                           "docstatus": 1, "is_pos": 0, "is_return": 0, "currency": currency, "outstanding_amount": [">", 0]},
                           fields=["name", "posting_date", "due_date", "grand_total", "outstanding_amount", "currency", "debit_to", "status", "modified"],
                           order_by="posting_date asc, name asc", limit_page_length=0)
    if lock:
        for row in sorted(rows, key=lambda value: value.name):
            frappe.db.sql("select name from `tabSales Invoice` where name = %s for update", (row.name,))
        return _open_invoices(profile, customer, currency)
    visible = []
    for row in rows:
        origin = frappe.db.get_value("Sales Invoice", row.name, "esafepos_b2b_profile")
        if not origin or permissions.can_use_outlet(origin):
            visible.append(row)
    return visible


def _reconciliation(profile, customer):
    from erpnext.accounts.party import get_party_account
    rec = frappe.new_doc("Payment Reconciliation")
    rec.company, rec.party_type, rec.party = profile.company, "Customer", customer
    rec.receivable_payable_account = get_party_account("Customer", customer, profile.company)
    if rec.meta.has_field("default_advance_account") and frappe.get_meta("Company").has_field("default_advance_received_account"):
        rec.default_advance_account = frappe.get_cached_value("Company", profile.company, "default_advance_received_account")
    rec.invoice_limit, rec.payment_limit = 0, 0
    return rec


@frappe.whitelist()
def customer_account(pos_profile, customer):
    profile, currency = context(pos_profile)
    customer_doc(customer)
    if not enabled("enable_customer_balances"):
        frappe.throw(_("Customer balances are turned off."), frappe.PermissionError)
    from esafepos import credit_sales
    invoices = _open_invoices(profile, customer, currency)
    advances = []
    can_reconcile = frappe.has_permission("Payment Reconciliation", "write")
    if can_reconcile:
        rec = _reconciliation(profile, customer)
        rec.get_unreconciled_entries()
        for row in rec.get("payments") or []:
            if row.reference_type not in ("Payment Entry", "Journal Entry"):
                continue
            source = frappe.get_doc(row.reference_type, row.reference_name)
            if source.has_permission("read") and source.company == profile.company:
                advances.append({"doctype": row.reference_type, "name": row.reference_name,
                                 "reference_row": row.get("reference_row"), "amount": row.amount,
                                 "posting_date": row.posting_date})
    pending = frappe.get_list(CHEQUE, filters={"company": profile.company, "customer": customer,
                             "status": ["in", ["Received", "Deposited"]]}, fields=["name", "amount", "cheque_date", "status"], limit_page_length=0) if frappe.has_permission(CHEQUE, "read") else []
    return {"currency": currency, "outstanding": credit_sales.owed(customer, profile.company),
            "overdue": sum(flt(row.outstanding_amount) for row in invoices if row.due_date and getdate(row.due_date) < getdate(nowdate())),
            "invoices": invoices, "advances": advances, "advance_total": sum(flt(row["amount"]) for row in advances),
            "pending_cheques": pending, "pending_total": sum(flt(row.amount) for row in pending),
            "can_reconcile": bool(can_reconcile), "refreshed_at": str(now_datetime())}


def _post_payment(profile, currency, customer, tender, references, posting_date, settlement, session_name=None, order=None):
    from erpnext.accounts.party import get_party_account
    account = _mode(profile, currency, tender["mode_of_payment"], tender["method"])
    receivable = get_party_account("Customer", customer, profile.company)
    if references and references[0]["reference_doctype"] == "Sales Invoice":
        receivable = frappe.db.get_value("Sales Invoice", references[0]["reference_name"], "debit_to")
    _account(receivable, profile.company, currency, "Receivable")
    amount = _amount(tender["amount"], currency)
    if tender["method"] != "Cash" and (not str(tender.get("reference_no") or "").strip() or not tender.get("reference_date")):
        frappe.throw(_("Enter the transfer/cheque reference and its date."))
    if order:
        source = document(profile.name, "Sales Order", order)
        if source.docstatus != 1 or source.customer != customer:
            frappe.throw(_("Choose a submitted order belonging to this customer."))
        references = [{"reference_doctype": "Sales Order", "reference_name": order, "allocated_amount": amount}]
    for ref in references:
        if ref["reference_doctype"] == "Sales Invoice":
            source = document(profile.name, "Sales Invoice", ref["reference_name"])
            if source.customer != customer or source.debit_to != receivable:
                frappe.throw(_("The allocations use another customer or receivable account."))
            if getdate(source.posting_date) > getdate(posting_date):
                frappe.throw(_("The payment cannot predate an allocated invoice."))
    payment = frappe.get_doc({"doctype": "Payment Entry", "payment_type": "Receive", "party_type": "Customer", "party": customer,
                             "company": profile.company, "posting_date": posting_date, "mode_of_payment": tender["mode_of_payment"],
                             "paid_from": receivable, "paid_to": account, "paid_from_account_currency": currency, "paid_to_account_currency": currency,
                             "paid_amount": amount, "received_amount": amount, "source_exchange_rate": 1, "target_exchange_rate": 1,
                             "reference_no": str(tender.get("reference_no") or "").strip()[:140],
                             "reference_date": tender.get("reference_date"), "references": references,
                             "cost_center": profile.get("cost_center"), "esafepos_b2b_profile": profile.name,
                             "esafepos_b2b_settlement": settlement, "esafepos_b2b_session": session_name})
    payment.insert()
    payment.submit()
    audit("Receive B2B payment", payment, profile.name)
    return payment


def _record(kind, values):
    doc = frappe.get_doc(dict(values, doctype=kind))
    doc.flags.b2b_operation = True
    doc.insert(ignore_permissions=True)
    return doc


def _save(doc):
    doc.flags.b2b_operation = True
    doc.save(ignore_permissions=True)


def _prior(key, fingerprint, profile, customer):
    name = frappe.db.get_value(SETTLEMENT, {"request_id": key}, "name")
    if not name:
        return None
    doc = frappe.get_doc(SETTLEMENT, name)
    if doc.request_hash != fingerprint or doc.company != profile.company or doc.customer != customer or doc.pos_profile != profile.name:
        frappe.throw(_("This retry identity belongs to another settlement."))
    return doc


def _receipt(doc):
    rows = json.loads(doc.rows or "[]")
    for row in rows:
        if row.get("payment"):
            row["docstatus"] = frappe.db.get_value("Payment Entry", row["payment"], "docstatus")
        if row.get("cheque"):
            row["status"] = frappe.db.get_value(CHEQUE, row["cheque"], "status")
    return {"doctype": SETTLEMENT, "name": doc.name, "customer": doc.customer,
            "customer_name": frappe.get_cached_value("Customer", doc.customer, "customer_name"),
            "company": doc.company, "currency": doc.currency, "posting_date": str(doc.posting_date),
            "collection_context": doc.collection_context, "amount": doc.amount, "rows": rows, "pos_profile": doc.pos_profile,
            "allocations": json.loads(doc.allocations or "[]"), "refreshed_at": str(now_datetime())}


@frappe.whitelist()
def settlement_receipt(pos_profile, name):
    profile, currency = _pay_context(pos_profile)
    doc = frappe.get_doc(SETTLEMENT, name)
    if doc.company != profile.company or doc.pos_profile != pos_profile:
        frappe.throw(_("This settlement belongs to another outlet."), frappe.PermissionError)
    customer_doc(doc.customer)
    return _receipt(doc)


@frappe.whitelist(methods=["POST"])
def receive_settlement(pos_profile, payload, idempotency_key):
    profile, currency = _pay_context(pos_profile)
    payload = data(payload)
    customer = customer_doc(payload.get("customer")).name
    key, fingerprint = identity(idempotency_key, payload)
    # Check retry before checking the current shift: a lost acknowledgement may
    # be retried after its original shift closed. Identity is scoped above.
    prior = _prior(key, fingerprint, profile, customer)
    if prior:
        return _receipt(prior)
    posting = str(getdate(payload.get("posting_date") or nowdate()))
    collection = payload.get("collection_context") or "Till"
    session_name = _session(profile, collection, posting)
    lock_customer(customer)
    prior = _prior(key, fingerprint, profile, customer)
    if prior:
        return _receipt(prior)
    tenders = data(payload.get("tenders"), list)
    if not tenders or len(tenders) > 20:
        frappe.throw(_("Enter between 1 and 20 payment rows."))
    try:
        if any(not isinstance(row, dict) for row in tenders):
            frappe.throw(_("Enter valid payment rows."))
        for tender in tenders:
            tender["amount"] = _amount(tender.get("amount"), currency)
        total = float(sum(number(row["amount"]) for row in tenders))
        seen_cheques = set()
        for tender in tenders:
            _mode(profile, currency, tender.get("mode_of_payment"), tender.get("method"))
            if tender["method"] != "Cash":
                if not str(tender.get("reference_no") or "").strip() or not tender.get("reference_date"):
                    frappe.throw(_("Enter each transfer/cheque reference and date."))
                tender["reference_no"] = str(tender["reference_no"]).strip()[:140]
                tender["reference_date"] = str(getdate(tender["reference_date"]))
            if tender["method"] == "Cheque":
                if not enabled("enable_cheque_tracking") or not str(tender.get("bank") or "").strip():
                    frappe.throw(_("Enable cheque tracking and enter the issuing bank."))
                tender["bank"] = str(tender["bank"]).strip()[:140]
                duplicate_key = (tender["bank"].casefold(), tender["reference_no"].casefold())
                if duplicate_key in seen_cheques:
                    frappe.throw(_("Enter each cheque only once in a settlement."))
                seen_cheques.add(duplicate_key)
                if frappe.db.exists(CHEQUE, {"company": profile.company, "customer": customer, "bank": tender["bank"],
                                             "reference_no": tender["reference_no"], "status": ["in", ["Received", "Deposited", "Cleared"]]}):
                    frappe.throw(_("This customer already has an active cheque with that bank and number."))
        invoices = _open_invoices(profile, customer, currency, lock=True)
        as_advance = bool(cint(payload.get("as_advance")))
        selections = data(payload.get("allocations") or [], list)
        if as_advance and selections:
            frappe.throw(_("Choose invoice settlement or advance receipt."))
        references, advance = allocate([] if as_advance else invoices, total, selections,
                                       allow_advance=as_advance or bool(cint(payload.get("keep_advance"))), precision=_precision(currency))
        pool = [dict(next(row for row in invoices if row.name == ref["reference_name"]), outstanding_amount=ref["allocated_amount"]) for ref in references]
        doc = _record(SETTLEMENT, {"request_id": key, "request_hash": fingerprint, "company": profile.company,
                      "pos_profile": pos_profile, "customer": customer, "currency": currency, "amount": total,
                      "posting_date": posting, "collection_context": collection, "session": session_name,
                      "allocations": json.dumps(references), "rows": "[]", "recorded_by": frappe.session.user})
        receipt_rows = []
        for tender in tenders:
            refs, extra = allocate(pool, tender["amount"], allow_advance=True, precision=_precision(currency))
            for ref in refs:
                match = next(row for row in pool if row["name"] == ref["reference_name"])
                match["outstanding_amount"] = flt(match["outstanding_amount"] - ref["allocated_amount"], _precision(currency))
            row = {"method": tender["method"], "mode_of_payment": tender["mode_of_payment"], "amount": float(tender["amount"]),
                   "reference_no": tender.get("reference_no"), "reference_date": tender.get("reference_date"), "advance": extra, "allocations": refs}
            if tender["method"] == "Cheque":
                cheque = _record(CHEQUE, {"company": profile.company, "pos_profile": pos_profile, "customer": customer,
                                 "currency": currency, "amount": float(tender["amount"]), "bank": str(tender["bank"]).strip()[:140],
                                 "reference_no": str(tender["reference_no"]).strip()[:140], "cheque_date": tender["reference_date"],
                                 "received_date": posting, "status": "Received", "mode_of_payment": tender["mode_of_payment"],
                                 "allocations": json.dumps([{"name": ref["reference_name"], "amount": ref["allocated_amount"]} for ref in refs]),
                                 "keep_advance": cint(extra > 0), "is_advance": cint(as_advance), "sales_order": payload.get("sales_order") if as_advance else None,
                                 "settlement": doc.name, "session": session_name, "history": json.dumps([
                                     {"action": "receive", "date": posting, "user": frappe.session.user}])})
                row.update({"cheque": cheque.name, "status": "Received"})
            else:
                payment = _post_payment(profile, currency, customer, tender, refs, posting, doc.name, session_name,
                                        payload.get("sales_order") if as_advance else None)
                row["payment"] = payment.name
            receipt_rows.append(row)
        doc.rows = json.dumps(receipt_rows)
        _save(doc)
    except ValueError as error:
        frappe.throw(str(error))
    audit("Receive B2B settlement", doc, pos_profile)
    return _receipt(doc)


@frappe.whitelist(methods=["POST"])
def apply_advance(pos_profile, customer, payment_doctype, payment, allocations, idempotency_key, reference_row=None):
    profile, currency = _pay_context(pos_profile)
    if not frappe.has_permission("Payment Reconciliation", "write"):
        frappe.throw(_("Payment Reconciliation permission is required."), frappe.PermissionError)
    if payment_doctype not in ("Payment Entry", "Journal Entry"):
        frappe.throw(_("Choose an available customer advance."))
    selections = data(allocations, list)
    payload = {"customer": customer, "payment_doctype": payment_doctype, "payment": payment,
               "allocations": selections, "reference_row": reference_row}
    key, fingerprint = identity(idempotency_key, payload)
    lock_customer(customer)
    prior = _prior(key, fingerprint, profile, customer)
    if prior:
        return _receipt(prior)
    source = frappe.get_doc(payment_doctype, payment)
    source.check_permission("write")
    if source.company != profile.company or source.docstatus != 1:
        frappe.throw(_("Choose a submitted advance in this company."))
    _open_invoices(profile, customer, currency, lock=True)
    rec = _reconciliation(profile, customer)
    rec.get_unreconciled_entries()
    available = next((row for row in rec.get("payments") or [] if row.reference_type == payment_doctype and row.reference_name == payment
                      and (not reference_row or row.get("reference_row") == reference_row)), None)
    if not available:
        frappe.throw(_("This advance is no longer available. Refresh the account."))
    try:
        total = sum(_amount(row.get("amount"), currency) for row in selections)
        if total <= 0 or total > flt(available.amount):
            frappe.throw(_("The allocation exceeds the available advance."))
        invoices = _open_invoices(profile, customer, currency)
        refs, extra = allocate(invoices, total, selections, precision=_precision(currency))
    except ValueError as error:
        frappe.throw(str(error))
    native_invoices = []
    for ref in refs:
        row = next((entry for entry in rec.get("invoices") or [] if entry.invoice_type == "Sales Invoice" and entry.invoice_number == ref["reference_name"]), None)
        if not row:
            frappe.throw(_("An invoice is no longer available for reconciliation."))
        native_invoices.append(dict(row.as_dict(), outstanding_amount=ref["allocated_amount"]))
    rec.allocate_entries({"invoices": native_invoices, "payments": [dict(available.as_dict(), amount=total)]})
    rec.reconcile()
    doc = _record(SETTLEMENT, {"request_id": key, "request_hash": fingerprint, "company": profile.company,
                  "pos_profile": pos_profile, "customer": customer, "currency": currency, "amount": total,
                  "posting_date": nowdate(), "collection_context": "Advance allocation", "recorded_by": frappe.session.user,
                  "allocations": json.dumps(refs), "rows": json.dumps([{"method": "Existing advance", "amount": total,
                      "source_doctype": payment_doctype, "source": payment, "allocations": refs}])})
    audit("Allocate B2B advance", doc, pos_profile)
    return _receipt(doc)


@frappe.whitelist()
def list_payments(pos_profile, customer, start=0):
    profile, currency = _pay_context(pos_profile)
    customer_doc(customer)
    rows = frappe.get_list("Payment Entry", filters={"company": profile.company, "party_type": "Customer", "party": customer},
                           fields=["name", "posting_date", "docstatus", "status", "mode_of_payment", "paid_amount", "paid_from_account_currency", "reference_no", "reference_date", "unallocated_amount"],
                           order_by="posting_date desc, modified desc", limit_start=max(0, cint(start)), limit_page_length=31)
    receipts = frappe.get_list(SETTLEMENT, filters={"company": profile.company, "pos_profile": pos_profile, "customer": customer},
                               fields=["name", "posting_date", "amount", "collection_context"], order_by="creation desc", limit_page_length=20)
    return {"items": rows[:30], "has_more": len(rows) > 30, "settlements": receipts}


@frappe.whitelist()
def list_cheques(pos_profile, customer=None, status="", start=0):
    profile, currency = _pay_context(pos_profile)
    if not enabled("enable_cheque_tracking"):
        frappe.throw(_("Cheque tracking is turned off."), frappe.PermissionError)
    filters = {"company": profile.company, "pos_profile": pos_profile}
    if customer:
        customer_doc(customer)
        filters["customer"] = customer
    if status in ("Received", "Deposited", "Cleared", "Bounced", "Returned", "Cancelled"):
        filters["status"] = status
    elif status in ("Due today", "Upcoming", "Overdue"):
        filters["status"] = ["in", ["Received", "Deposited"]]
        filters["cheque_date"] = [{"Due today": "=", "Upcoming": ">", "Overdue": "<"}[status], nowdate()]
    rows = frappe.get_list(CHEQUE, filters=filters, fields=["name", "customer", "reference_no", "bank", "cheque_date", "received_date", "deposit_date", "clearance_date", "amount", "currency", "status", "payment_entry", "modified", "allocations", "history", "keep_advance"],
                           order_by="cheque_date asc, name asc", limit_start=max(0, cint(start)), limit_page_length=31)
    return {"items": rows[:30], "has_more": len(rows) > 30}


@frappe.whitelist(methods=["POST"])
def transition_cheque(pos_profile, name, action, modified, event_date=None, reason=None, allocations=None, keep_advance=None, idempotency_key=None):
    profile, currency = _pay_context(pos_profile)
    if not enabled("enable_cheque_tracking"):
        frappe.throw(_("Cheque tracking is turned off."), frappe.PermissionError)
    frappe.db.sql("select name from `tabEsafePOS Customer Cheque` where name = %s for update", (name,))
    doc = frappe.get_doc(CHEQUE, name)
    if doc.company != profile.company or doc.pos_profile != pos_profile:
        frappe.throw(_("This cheque belongs to another outlet."), frappe.PermissionError)
    customer_doc(doc.customer)
    history = json.loads(doc.history or "[]")
    retry_key, retry_hash = identity(idempotency_key, {"action": action, "event_date": event_date, "reason": reason,
                                    "allocations": allocations, "keep_advance": keep_advance}) if idempotency_key else (None, None)
    if retry_key:
        previous = next((event for event in history if event.get("request_id") == retry_key), None)
        if previous:
            if previous.get("request_hash") != retry_hash:
                frappe.throw(_("This cheque action identity was used for different data."))
            return {"name": doc.name, "status": doc.status, "modified": str(doc.modified), "payment_entry": doc.get("payment_entry")}
    if str(doc.modified) != str(modified):
        frappe.throw(_("The cheque changed. Refresh and review its status."))
    try:
        target = cheque_transition(doc.status, action)
    except ValueError as error:
        frappe.throw(str(error))
    event_date = str(getdate(event_date or nowdate()))
    if getdate(event_date) < getdate(doc.received_date) or getdate(event_date) > getdate(nowdate()):
        frappe.throw(_("Choose an event date between receipt and today."))
    if any(doc.get(field) and getdate(event_date) < getdate(doc.get(field)) for field in ("deposit_date", "clearance_date")):
        frappe.throw(_("The cheque action cannot predate its deposit or clearance."))
    if action in ("bounce", "return", "cancel") and not str(reason or "").strip():
        frappe.throw(_("Enter a reason for this cheque action."))
    if action == "deposit":
        doc.deposit_date = event_date
    if action == "clear":
        if getdate(event_date) < getdate(doc.deposit_date) or getdate(event_date) < getdate(doc.cheque_date):
            frappe.throw(_("Clearance cannot predate the deposit or cheque date."))
        lock_customer(doc.customer)
        invoices = _open_invoices(profile, doc.customer, currency, lock=True)
        selected = data(allocations, list) if allocations is not None else json.loads(doc.allocations or "[]")
        allow_excess = cint(keep_advance) if keep_advance is not None else cint(doc.keep_advance)
        if allocations is not None and not selected and not allow_excess:
            frappe.throw(_("Select invoice allocations or explicitly keep the cheque as an advance."))
        candidates = [] if not selected and (allocations is not None or doc.get("is_advance")) else invoices
        try:
            references, extra = allocate(candidates, doc.amount, selected, allow_advance=bool(allow_excess), precision=_precision(currency))
        except ValueError as error:
            frappe.throw(str(error))
        tender = {"method": "Cheque", "mode_of_payment": doc.mode_of_payment, "amount": doc.amount,
                  "reference_no": doc.reference_no, "reference_date": str(doc.cheque_date)}
        payment = _post_payment(profile, currency, doc.customer, tender, references, event_date, doc.settlement,
                                order=doc.get("sales_order") if not selected else None)
        # Native bank-clearance tool owns this allow-on-submit field. The
        # adapter is shared with ERPNext's own reconciliation UI, not raw SQL.
        from esafepos.erpnext_compat import set_payment_clearance
        set_payment_clearance(payment.name, event_date)
        doc.payment_entry, doc.clearance_date = payment.name, event_date
        doc.allocations = json.dumps([{"name": row["reference_name"], "amount": row["allocated_amount"]} for row in references])
    if action == "bounce" and doc.status == "Cleared":
        payment = frappe.get_doc("Payment Entry", doc.payment_entry)
        payment.check_permission("cancel")
        payment.flags.b2b_cheque_bounce = True
        payment.cancel()
        doc.reversal_reference = payment.name
    history.append({"action": action, "from": doc.status, "to": target, "date": event_date,
                    "request_id": retry_key, "request_hash": retry_hash,
                    "reason": str(reason or "").strip()[:1000], "user": frappe.session.user, "at": str(now_datetime())})
    doc.status, doc.history = target, json.dumps(history)
    _save(doc)
    audit("B2B cheque " + action, doc, pos_profile)
    return {"name": doc.name, "status": doc.status, "modified": str(doc.modified), "payment_entry": doc.get("payment_entry")}


def guard_collection_cancel(doc, method=None):
    """A native correction cannot silently change a closed shift's receipts."""
    if doc.get("esafepos_b2b_session"):
        from esafepos.api.sales import _lock_open_session
        _lock_open_session(doc.esafepos_b2b_session)


def payment_cancelled(doc, method=None):
    if doc.flags.get("b2b_cheque_bounce") or not frappe.db.exists("DocType", CHEQUE):
        return
    for name in frappe.get_all(CHEQUE, filters={"payment_entry": doc.name, "status": "Cleared"}, pluck="name"):
        cheque = frappe.get_doc(CHEQUE, name)
        history = json.loads(cheque.history or "[]")
        history.append({"action": "payment_cancelled", "from": cheque.status, "to": "Cancelled", "date": nowdate(),
                        "at": str(now_datetime()), "user": frappe.session.user, "reason": "Linked payment cancelled in ERPNext"})
        cheque.status, cheque.history = "Cancelled", json.dumps(history)
        _save(cheque)
