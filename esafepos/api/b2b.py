"""Customer-oriented selling workspace backed by native ERPNext documents.

Only allowlisted fields cross the editor boundary. Accounting, stock, mapping,
permissions and workflow validation remain with the native document controllers.
"""
import hashlib
import importlib
import json

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate, now_datetime

from esafepos.api import permissions
from esafepos.features import enabled
from esafepos.b2b_rules import line_discount, number, progress

KINDS = {"Quotation": "enable_quotations", "Sales Order": "enable_sales_orders",
         "Delivery Note": "enable_delivery_notes", "Sales Invoice": "enable_regular_invoices"}
MAPPERS = {
    ("Quotation", "Sales Order"): ("erpnext.selling.doctype.quotation.quotation", "make_sales_order"),
    ("Sales Order", "Delivery Note"): ("erpnext.selling.doctype.sales_order.sales_order", "make_delivery_note"),
    ("Sales Order", "Sales Invoice"): ("erpnext.selling.doctype.sales_order.sales_order", "make_sales_invoice"),
    ("Delivery Note", "Sales Invoice"): ("erpnext.stock.doctype.delivery_note.delivery_note", "make_sales_invoice"),
    ("Sales Invoice", "Delivery Note"): ("erpnext.accounts.doctype.sales_invoice.sales_invoice", "make_delivery_note"),
}
HEADER_FIELDS = ("posting_date", "transaction_date", "due_date", "delivery_date", "valid_till", "po_no", "po_date",
                 "customer_address", "shipping_address_name", "contact_person", "payment_terms_template", "tc_name", "terms", "remarks")
SOURCE_FIELDS = ("sales_order", "so_detail", "against_sales_order", "prevdoc_docname", "quotation_item",
                 "delivery_note", "dn_detail", "against_sales_invoice", "si_detail")


def data(value, kind=dict):
    try:
        value = json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        frappe.throw(_("Invalid B2B request."))
    if not isinstance(value, kind):
        frappe.throw(_("Invalid B2B request."))
    return value


def context(pos_profile):
    if not enabled("enable_regular_invoices"):
        frappe.throw(_("The ESAFE B2B module is turned off in Modules & Features."), frappe.PermissionError)
    permissions.assert_outlet(pos_profile)
    profile = frappe.get_cached_doc("POS Profile", pos_profile)
    profile.check_permission("read")
    if not frappe.get_meta("Sales Invoice").has_field("esafepos_b2b_key"):
        frappe.throw(_("Run the site migration before using the ESAFE B2B module."))
    currency = frappe.get_cached_value("Company", profile.company, "default_currency")
    return profile, currency


def require_kind(doctype):
    if doctype not in KINDS or not enabled(KINDS[doctype]):
        frappe.throw(_("This B2B document type is unavailable."), frappe.PermissionError)


def customer_doc(customer, for_sale=False):
    doc = frappe.get_doc("Customer", customer)
    doc.check_permission("read")
    if for_sale and doc.get("disabled"):
        frappe.throw(_("This customer is disabled."))
    return doc


def document(pos_profile, doctype, name, action="read", lock=False):
    profile, currency = context(pos_profile)
    require_kind(doctype)
    if lock:
        frappe.db.sql("select name from `tab{0}` where name = %s for update".format(doctype), (name,))
    doc = frappe.get_doc(doctype, name)
    doc.check_permission(action)
    if doc.company != profile.company:
        frappe.throw(_("The document belongs to another company."), frappe.PermissionError)
    customer = doc.get("party_name") if doctype == "Quotation" else doc.get("customer")
    if doctype == "Quotation" and doc.get("quotation_to") != "Customer":
        frappe.throw(_("Only customer quotations are available here."))
    customer_doc(customer)
    origin = doc.get("esafepos_b2b_profile") or doc.get("pos_profile")
    if origin:
        permissions.assert_outlet(origin)
        if action != "read" and origin != pos_profile:
            frappe.throw(_("Switch to the document's outlet before changing it."))
    if action != "read" and (doc.currency != currency or cint(doc.get("is_pos")) or cint(doc.get("is_return"))):
        frappe.throw(_("Use ERPNext to change foreign-currency, POS, or return documents."))
    return doc


def identity(key, payload):
    if not isinstance(key, str) or not 16 <= len(key) <= 140:
        frappe.throw(_("A valid retry identity is required."))
    return hashlib.sha256(key.encode("utf-8")).hexdigest(), hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def previous(doctype, key, fingerprint, profile):
    name = frappe.db.get_value(doctype, {"esafepos_b2b_key": key}, "name")
    if not name:
        return None
    doc = document(profile, doctype, name)
    if doc.get("esafepos_b2b_hash") != fingerprint:
        frappe.throw(_("This retry identity was used for different data. Refresh and try again."))
    return doc


def lock_customer(customer):
    customer_doc(customer)
    frappe.db.sql("select name from `tabCustomer` where name = %s for update", (customer,))


def audit(action, doc, profile):
    from esafepos.api import audit as audit_api
    audit_api.log(action, detail="{0} {1}".format(doc.doctype, doc.name), reference_doctype=doc.doctype,
                  reference_name=doc.name, pos_profile=profile, amount=flt(doc.get("grand_total") or doc.get("amount")))


def _fields(doctype, fields):
    meta = frappe.get_meta(doctype)
    return [field for field in fields if field == "name" or meta.has_field(field)]


@frappe.whitelist()
def get_context(pos_profile):
    profile, currency = context(pos_profile)
    from esafepos.api.b2b_payments import _precision
    kinds = {}
    for kind, feature in KINDS.items():
        kinds[kind] = {action: bool(enabled(feature) and frappe.has_permission(kind, action))
                       for action in ("read", "create", "write", "submit", "cancel", "amend", "print")}
    modes = []
    for row in profile.get("payments") or []:
        mode = frappe.get_cached_doc("Mode of Payment", row.mode_of_payment)
        account = frappe.db.get_value("Mode of Payment Account", {"parent": mode.name, "company": profile.company}, "default_account")
        if mode.get("enabled") and mode.type in ("Cash", "Bank") and account:
            if frappe.get_cached_value("Account", account, "account_currency") == currency:
                modes.append({"name": mode.name, "type": mode.type, "account": account})
    can_pay = enabled("enable_customer_payments") and permissions.can_take_customer_payments() and all(
        frappe.has_permission("Payment Entry", action) for action in ("read", "create", "submit"))
    return {"company": profile.company, "currency": currency, "currency_precision": _precision(currency), "today": nowdate(), "kinds": kinds,
            "warehouse": profile.warehouse, "payment_modes": modes, "can_pay": bool(can_pay),
            "can_cheque": bool(can_pay and enabled("enable_cheque_tracking")),
            "can_statement": bool(enabled("enable_customer_balances") and frappe.has_permission("GL Entry", "read")),
            "can_edit_price": bool(permissions.can_edit_price()), "can_change_rate": bool(cint(profile.get("allow_rate_change")) and permissions.can_edit_price()),
            "can_create_customer": bool(frappe.has_permission("Customer", "create")),
            "payment_terms": frappe.get_list("Payment Terms Template", pluck="name", limit_page_length=200) if frappe.has_permission("Payment Terms Template", "read") else [],
            "terms_templates": frappe.get_list("Terms and Conditions", pluck="name", limit_page_length=200) if frappe.has_permission("Terms and Conditions", "read") else [],
            "can_edit_customer": bool(frappe.has_permission("Customer", "write")),
            "warehouses": frappe.get_list("Warehouse", filters={"company": profile.company, "is_group": 0, "disabled": 0}, pluck="name", limit_page_length=200)
            if frappe.has_permission("Warehouse", "read") else [profile.warehouse]}


@frappe.whitelist()
def list_documents(pos_profile, doctype, customer=None, search="", status="", start=0, from_date=None, to_date=None):
    profile, currency = context(pos_profile)
    require_kind(doctype)
    if not frappe.has_permission(doctype, "read"):
        frappe.throw(_("You cannot read these documents."), frappe.PermissionError)
    filters = {"company": profile.company}
    date_field = "transaction_date" if doctype in ("Quotation", "Sales Order") else "posting_date"
    if customer:
        customer_doc(customer)
        filters["party_name" if doctype == "Quotation" else "customer"] = customer
    if doctype == "Quotation":
        filters["quotation_to"] = "Customer"
    if status in ("Draft", "Submitted", "Cancelled"):
        filters["docstatus"] = {"Draft": 0, "Submitted": 1, "Cancelled": 2}[status]
    elif status:
        filters["status"] = status
    if from_date and to_date:
        if getdate(from_date) > getdate(to_date):
            frappe.throw(_("The start date must not follow the end date."))
        filters[date_field] = ["between", [str(getdate(from_date)), str(getdate(to_date))]]
    elif from_date:
        filters[date_field] = [">=", str(getdate(from_date))]
    elif to_date:
        filters[date_field] = ["<=", str(getdate(to_date))]
    if doctype == "Sales Invoice":
        filters["is_pos"] = 0
    fields = _fields(doctype, ["name", "customer_name", "status", "docstatus", date_field, "grand_total", "currency", "outstanding_amount", "due_date", "per_delivered", "per_billed", "modified"])
    rows = frappe.get_list(doctype, filters=filters, or_filters={"name": ["like", "%{0}%".format(str(search)[:100])],
                           "customer_name": ["like", "%{0}%".format(str(search)[:100])]} if search else None,
                           fields=fields, order_by="modified desc, name desc", limit_start=max(0, cint(start)), limit_page_length=31)
    return {"items": rows[:30], "has_more": len(rows) > 30, "currency": currency}


def serialize(doc):
    saved = json.loads(doc.get("esafepos_b2b_manual") or "[]")
    lines = []
    for index, row in enumerate(doc.get("items") or []):
        manual = saved[index] if index < len(saved) and saved[index].get("item_code") == row.item_code else {}
        lines.append({**{key: row.get(key) for key in ("name", "item_code", "item_name", "description", "qty", "uom", "stock_uom", "warehouse", "rate", "price_list_rate", "discount_amount", "discount_percentage", "amount", "serial_no", "batch_no", "delivery_date") + SOURCE_FIELDS},
                      "base_rate": manual.get("base_rate", flt(row.rate)), "manual_rate": manual.get("manual_rate", False),
                      "native_rate": manual.get("native_rate", flt(row.rate)),
                      "discount_method": manual.get("discount_method", "Percent"), "discount_value": manual.get("discount_value", 0)})
    values = {key: doc.get(key) for key in HEADER_FIELDS + ("doctype", "name", "company", "currency", "customer", "customer_name", "party_name", "modified", "docstatus", "status", "update_stock", "selling_price_list", "grand_total", "net_total", "total_taxes_and_charges", "rounded_total", "outstanding_amount", "address_display", "shipping_address", "contact_display", "contact_mobile", "amended_from")}
    values["customer"] = doc.get("party_name") if doc.doctype == "Quotation" else doc.get("customer")
    values["items"] = lines
    values["sales_person"] = (doc.get("sales_team") or [{}])[0].get("sales_person")
    values["taxes"] = [{key: row.get(key) for key in ("description", "rate", "tax_amount", "included_in_print_rate")} for row in doc.get("taxes") or []]
    values["connections"] = [{"doctype": kind, "name": name} for kind, name in sorted(set(
        (target, row.get(field)) for row in doc.get("items") or [] for field, target in (
            ("sales_order", "Sales Order"), ("against_sales_order", "Sales Order"), ("prevdoc_docname", "Quotation"),
            ("delivery_note", "Delivery Note"), ("against_sales_invoice", "Sales Invoice")) if row.get(field)))]
    values["readonly"] = bool(cint(doc.get("is_pos")) or cint(doc.get("is_return")))
    values["approved_percent"] = flt(doc.get("esafepos_b2b_approved_percent"))
    values["rounding_adjustment"] = flt(doc.get("rounding_adjustment"))
    values["payable_total"] = flt(doc.get("rounded_total")) if not cint(doc.get("disable_rounded_total")) and doc.get("rounded_total") is not None else flt(doc.get("grand_total"))
    return values


@frappe.whitelist()
def get_document(pos_profile, doctype, name):
    return serialize(document(pos_profile, doctype, name))


@frappe.whitelist()
def customer_options(pos_profile, customer):
    context(pos_profile)
    customer_doc(customer)
    result = {}
    for kind, key, label in (("Address", "addresses", "address_title"), ("Contact", "contacts", "full_name")):
        names = frappe.get_all("Dynamic Link", filters={"link_doctype": "Customer", "link_name": customer, "parenttype": kind}, pluck="parent")
        result[key] = frappe.get_list(kind, filters={"name": ["in", names]}, fields=["name", label], limit_page_length=200) if names and frappe.has_permission(kind, "read") else []
    return result


@frappe.whitelist()
def search_items(pos_profile, search):
    context(pos_profile)
    query = str(search or "").strip()[:100]
    if not query:
        return []
    return frappe.get_list("Item", filters={"disabled": 0, "is_sales_item": 1, "has_variants": 0},
                           or_filters={"name": ["like", "%" + query + "%"], "item_name": ["like", "%" + query + "%"]},
                           fields=["name", "item_name", "stock_uom", "sales_uom", "has_serial_no", "has_batch_no"], limit_page_length=15)


@frappe.whitelist()
def item_units(pos_profile, item_code):
    context(pos_profile)
    item = frappe.get_doc("Item", item_code)
    item.check_permission("read")
    return {"units": [{"uom": row.uom, "conversion_factor": row.conversion_factor} for row in item.get("uoms") or []],
            "stock_uom": item.stock_uom, "has_serial_no": item.has_serial_no, "has_batch_no": item.has_batch_no}


def _prepare(pos_profile, payload):
    profile, currency = context(pos_profile)
    kind = payload.get("doctype")
    require_kind(kind)
    customer = customer_doc(payload.get("customer"), for_sale=True)
    rows = data(payload.get("items"), list)
    if not rows or len(rows) > 200:
        frappe.throw(_("Add between 1 and 200 invoice items."))
    if payload.get("name"):
        doc = document(pos_profile, kind, payload["name"], "write", lock=True)
        if doc.docstatus != 0:
            frappe.throw(_("Only draft documents can be edited."))
        if not payload.get("modified") or str(doc.modified) != str(payload["modified"]):
            frappe.throw(_("This draft changed elsewhere. Reopen it before saving."))
        if (doc.get("party_name") if kind == "Quotation" else doc.customer) != customer.name:
            frappe.throw(_("Create a new draft to change its customer."))
    else:
        from esafepos.erpnext_compat import new_doc
        doc = new_doc(kind)
        doc.check_permission("create")
        doc.company = profile.company
        if kind == "Quotation":
            doc.quotation_to, doc.party_name = "Customer", customer.name
        else:
            doc.customer = customer.name
        doc.currency, doc.conversion_rate = currency, 1
        price_list = customer.get("default_price_list") or profile.selling_price_list
        if frappe.get_cached_value("Price List", price_list, "currency") != currency:
            frappe.throw(_("Choose a customer/outlet price list in company currency."))
        doc.selling_price_list = price_list
        doc.set_warehouse = profile.warehouse
        if doc.meta.has_field("cost_center"):
            doc.cost_center = profile.get("cost_center")
    for field in HEADER_FIELDS:
        if field in payload and doc.meta.has_field(field):
            value = payload[field]
            if value and (field.endswith("_date") or field == "valid_till"):
                value = str(getdate(value))
            doc.set(field, value or None)
    if any(payload.get(key) for key in ("customer_address", "shipping_address_name", "contact_person")):
        linked = customer_options(pos_profile, customer.name)
        for field, group in (("customer_address", "addresses"), ("shipping_address_name", "addresses"), ("contact_person", "contacts")):
            if payload.get(field) and payload[field] not in {row.name for row in linked[group]}:
                frappe.throw(_("Choose an address/contact linked to this customer."), frappe.PermissionError)
    if kind == "Sales Order" and not doc.get("delivery_date"):
        doc.delivery_date = nowdate()
    if kind in ("Sales Invoice", "Delivery Note") and not doc.get("posting_date"):
        doc.posting_date = nowdate()
    if kind in ("Quotation", "Sales Order") and not doc.get("transaction_date"):
        doc.transaction_date = nowdate()
    if kind == "Sales Invoice":
        doc.is_pos = 0
        doc.update_stock = cint(payload.get("update_stock"))
        doc.set("payments", [])
        doc.esafepos_invoice_origin = "Customer Invoice"
        if doc.meta.has_field("pos_profile"):
            doc.pos_profile = profile.name
    doc.esafepos_b2b_profile = profile.name
    old_rows = {row.name: row for row in doc.get("items") or []}
    saved_manual = json.loads(doc.get("esafepos_b2b_manual") or "[]")
    old_manual = {row.name: saved_manual[index] for index, row in enumerate(doc.get("items") or []) if index < len(saved_manual)}
    source_prices = []
    doc.set("items", [])
    used = set()
    for raw in rows:
        if not isinstance(raw, dict):
            frappe.throw(_("Invalid item row."))
        item = frappe.get_cached_doc("Item", raw.get("item_code"))
        item.check_permission("read")
        if item.disabled or not item.is_sales_item or item.has_variants:
            frappe.throw(_("Choose an enabled selling item."))
        qty = float(number(raw.get("qty"), "quantity", positive=True))
        uom = raw.get("uom") or item.stock_uom
        conversion = 1 if uom == item.stock_uom else next((flt(unit.conversion_factor) for unit in item.get("uoms") or [] if unit.uom == uom), 0)
        if conversion <= 0:
            frappe.throw(_("Choose a configured selling UOM."))
        warehouse = raw.get("warehouse") or profile.warehouse
        if item.is_stock_item:
            wh = frappe.get_doc("Warehouse", warehouse)
            if warehouse != profile.warehouse:
                wh.check_permission("read")
            if wh.company != profile.company or wh.is_group or wh.disabled:
                frappe.throw(_("Choose an enabled warehouse in this company."))
        source = old_rows.get(raw.get("name"))
        if raw.get("name") and raw["name"] in used:
            frappe.throw(_("An item row cannot be repeated."))
        used.add(raw.get("name"))
        if source and source.item_code != item.name:
            frappe.throw(_("Remove the existing line before changing its item."))
        values = {"item_code": item.name, "qty": qty, "uom": uom, "conversion_factor": conversion,
                  "warehouse": warehouse, "delivery_date": raw.get("delivery_date") or doc.get("delivery_date") or nowdate(),
                  "serial_no": raw.get("serial_no"), "batch_no": raw.get("batch_no"), "use_serial_batch_fields": 1}
        if source:
            values.update({key: source.get(key) for key in SOURCE_FIELDS if source.get(key)})
        source_prices.append({"rate": old_manual.get(source.name, {}).get("native_rate", source.rate),
                              "price_list_rate": source.price_list_rate} if source and any(source.get(key) for key in SOURCE_FIELDS) else None)
        if doc.get("update_stock") and values.get("delivery_note"):
            frappe.throw(_("The Delivery Note already moved this stock. Turn off Update Stock."))
        doc.append("items", values)
    if doc.meta.has_field("sales_team"):
        doc.set("sales_team", [])
        if payload.get("sales_person"):
            person = frappe.get_doc("Sales Person", payload["sales_person"])
            person.check_permission("read")
            doc.append("sales_team", {"sales_person": person.name, "allocated_percentage": 100})
        elif frappe.get_cached_value("EsafePOS Settings", None, "salesperson_mode") == "Required":
            frappe.throw(_("Select a salesperson."))
    if doc.meta.has_field("payment_schedule"):
        doc.set("payment_schedule", [])
    doc.ignore_pricing_rule = 0
    doc.run_method("set_missing_values")
    # Native controllers resolve customer defaults, UOM price lists and rules.
    doc.run_method("calculate_taxes_and_totals")
    manual, approval_rows = [], []
    for row, raw, agreed in zip(doc.items, rows, source_prices):
        if agreed:
            row.rate, row.price_list_rate = agreed["rate"], agreed["price_list_rate"]
        native_rate = flt(row.rate)
        base = native_rate
        manual_rate = bool(raw.get("manual_rate"))
        if manual_rate:
            if not cint(profile.get("allow_rate_change")) or not permissions.can_edit_price():
                frappe.throw(_("You cannot change item rates at this outlet."), frappe.PermissionError)
            base = float(number(raw.get("base_rate"), "rate"))
        discount = float(number(raw.get("discount_value", 0), "discount"))
        method = raw.get("discount_method") or "Percent"
        adjusted = line_discount(base, method, discount)
        effective = max(0, (native_rate - adjusted["rate"]) / native_rate * 100) if native_rate else 0
        approval_rows.append({"manual_discount_percent": effective})
        if discount and not permissions.can_edit_price():
            frappe.throw(_("You cannot apply manual line discounts."), frappe.PermissionError)
        # Retain native automatic discount and add the authorized manual change.
        row.rate = adjusted["rate"]
        row.discount_amount = flt(row.price_list_rate) - row.rate
        row.discount_percentage = row.discount_amount / flt(row.price_list_rate) * 100 if flt(row.price_list_rate) else 0
        manual.append({"item_code": row.item_code, "base_rate": base, "manual_rate": manual_rate,
                       "native_rate": native_rate, "discount_method": method, "discount_value": discount, "effective_percent": effective})
    from esafepos.api.sales import _check_price_edit_permission, _check_discount_passcode
    approval = {"pos_profile": pos_profile, "items": approval_rows, "discount_passcode": payload.get("discount_passcode"), "discount_request": payload.get("discount_request")}
    _check_price_edit_permission(approval)
    worst = max(row["manual_discount_percent"] for row in approval_rows)
    approver = None
    if worst > flt(doc.get("esafepos_b2b_approved_percent")):
        approver = _check_discount_passcode(approval)
        limit = flt(frappe.get_cached_value("EsafePOS Settings", None, "discount_limit_percent"))
        if limit > 0 and worst > limit:
            doc.esafepos_b2b_approved_percent = worst
            doc.esafepos_b2b_approval = payload.get("discount_request")
    if approver:
        doc.remarks = (doc.get("remarks") or "") + "\n" + _("Discount approved by {0}").format(approver)
    doc.ignore_pricing_rule = 1
    doc.esafepos_b2b_manual = json.dumps(manual)
    doc.run_method("calculate_taxes_and_totals")
    if doc.currency != currency:
        frappe.throw(_("B2B transactions must use company currency."))
    return doc


@frappe.whitelist()
def preview(pos_profile, payload):
    try:
        return serialize(_prepare(pos_profile, data(payload)))
    except ValueError as error:
        frappe.throw(str(error))


@frappe.whitelist(methods=["POST"])
def save_document(pos_profile, payload, idempotency_key):
    payload = data(payload)
    profile, currency = context(pos_profile)
    require_kind(payload.get("doctype"))
    lock_customer(payload.get("customer"))
    key, fingerprint = identity(idempotency_key, payload)
    if payload.get("name"):
        existing = document(pos_profile, payload["doctype"], payload["name"], "write", lock=True)
        if existing.get("esafepos_b2b_last_key") == key:
            if existing.get("esafepos_b2b_last_hash") != fingerprint:
                frappe.throw(_("This save identity was already used for different data."))
            return serialize(existing)
    if not payload.get("name"):
        prior = previous(payload["doctype"], key, fingerprint, pos_profile)
        if prior:
            return serialize(prior)
    if payload.get("discount_request"):
        frappe.db.sql("select name from `tabPOS Approval Request` where name = %s for update", (payload["discount_request"],))
    try:
        doc = _prepare(pos_profile, payload)
    except ValueError as error:
        frappe.throw(str(error))
    doc.esafepos_b2b_last_key, doc.esafepos_b2b_last_hash = key, fingerprint
    if not payload.get("name"):
        doc.esafepos_b2b_key, doc.esafepos_b2b_hash = key, fingerprint
        doc.insert()
    else:
        doc.save()
    if payload.get("discount_request") and doc.get("esafepos_b2b_approval") == payload["discount_request"]:
        from esafepos.api.approval_requests import consume
        consume(payload["discount_request"], "{0}: {1}".format(doc.doctype, doc.name))
    audit("Save B2B draft", doc, pos_profile)
    return serialize(doc)


@frappe.whitelist(methods=["POST"])
def submit_document(pos_profile, doctype, name, modified, expected_total):
    doc = document(pos_profile, doctype, name, "submit", lock=True)
    if doc.docstatus == 1:
        return serialize(doc)
    if doc.docstatus != 0 or str(doc.modified) != str(modified):
        frappe.throw(_("This draft changed. Reopen and review it before submitting."))
    if abs(flt(doc.grand_total) - float(number(expected_total, "reviewed total"))) > 0.00001:
        frappe.throw(_("Review the updated total before submitting."))
    doc.submit()
    audit("Submit B2B document", doc, pos_profile)
    return serialize(doc)


@frappe.whitelist(methods=["POST"])
def convert_document(pos_profile, doctype, name, target, idempotency_key, quantities=None):
    source = document(pos_profile, doctype, name, lock=True)
    profile, currency = context(pos_profile)
    if source.currency != currency or cint(source.get("is_pos")) or cint(source.get("is_return")):
        frappe.throw(_("Use ERPNext to continue foreign-currency, POS, or return documents."))
    if doctype == "Sales Invoice" and target == "Delivery Note" and cint(source.get("update_stock")):
        frappe.throw(_("This invoice already moved the stock."))
    require_kind(target)
    if source.docstatus != 1 or (doctype, target) not in MAPPERS:
        frappe.throw(_("Choose a submitted document with an available next step."))
    if not frappe.has_permission(target, "create"):
        frappe.throw(_("You cannot create the next document."), frappe.PermissionError)
    selected = data(quantities, list) if quantities else []
    key, fingerprint = identity(idempotency_key, {"source": name, "kind": doctype, "target": target, "quantities": selected})
    prior = previous(target, key, fingerprint, pos_profile)
    if prior:
        return serialize(prior)
    if doctype == "Quotation" and source.get("valid_till") and getdate(source.valid_till) < getdate(nowdate()):
        frappe.throw(_("This quotation expired. Amend its validity in ERPNext before continuing."))
    module, method = MAPPERS[(doctype, target)]
    mapper = getattr(importlib.import_module(module), method, None)
    if not mapper:
        frappe.throw(_("This ERPNext version does not support that conversion. Open the source in ERPNext."))
    mapped = mapper(source.name)
    if isinstance(mapped, dict):
        mapped = frappe.get_doc(mapped)
    if selected:
        chosen = {row["name"]: float(number(row["qty"], "remaining quantity", positive=True)) for row in selected}
        if len(chosen) != len(selected):
            frappe.throw(_("Choose each source line once."))
        kept, found = [], set()
        for row in mapped.items:
            detail_field = {"Sales Order": "so_detail", "Quotation": "quotation_item", "Delivery Note": "dn_detail", "Sales Invoice": "si_detail"}[doctype]
            source_name = row.get(detail_field)
            if source_name in chosen:
                if chosen[source_name] > flt(row.qty):
                    frappe.throw(_("The selected quantity exceeds the remaining quantity."))
                row.qty = chosen[source_name]
                kept.append(row)
                found.add(source_name)
        if set(chosen) != found or not kept:
            frappe.throw(_("A selected line is no longer available. Refresh the source."))
        mapped.set("items", kept)
    if not mapped.get("items"):
        frappe.throw(_("This document has no remaining quantities for that action."))
    mapped.esafepos_b2b_key, mapped.esafepos_b2b_hash = key, fingerprint
    mapped.esafepos_b2b_profile = pos_profile
    if target == "Sales Invoice":
        mapped.is_pos = 0
        mapped.update_stock = 0
        mapped.esafepos_invoice_origin = "Customer Invoice"
        if mapped.meta.has_field("pos_profile"):
            mapped.pos_profile = pos_profile
    mapped.run_method("calculate_taxes_and_totals")
    mapped.insert()
    audit("Continue B2B sale", mapped, pos_profile)
    return serialize(mapped)


@frappe.whitelist(methods=["POST"])
def cancel_and_amend(pos_profile, doctype, name, modified, idempotency_key):
    doc = document(pos_profile, doctype, name, "cancel", lock=True)
    doc.check_permission("amend")
    key, fingerprint = identity(idempotency_key, {"kind": doctype, "source": name, "modified": modified})
    prior = previous(doctype, key, fingerprint, pos_profile)
    if prior:
        return serialize(prior)
    if doc.docstatus != 1 or str(doc.modified) != str(modified):
        frappe.throw(_("Refresh this submitted document before amending it."))
    # Native cancellation rejects linked payments, deliveries, frozen periods,
    # and workflows. Never cascade-cancel someone else's accounting documents.
    doc.cancel()
    amended = frappe.copy_doc(doc)
    amended.docstatus, amended.amended_from = 0, doc.name
    amended.esafepos_b2b_key, amended.esafepos_b2b_hash = key, fingerprint
    amended.esafepos_b2b_profile = pos_profile
    if doctype == "Sales Invoice":
        amended.esafepos_invoice_origin = "Customer Invoice"
    amended.insert()
    audit("Amend B2B document", amended, pos_profile)
    return serialize(amended)


@frappe.whitelist()
def sales_progress(pos_profile, doctype, name):
    """Traverse native item links in both directions, scoped at every document."""
    root = document(pos_profile, doctype, name)
    found, queue, restricted = {}, [(doctype, name)], False
    relations = [("Sales Order", "prevdoc_docname", "Quotation"),
                 ("Delivery Note", "against_sales_order", "Sales Order"),
                 ("Delivery Note", "against_sales_invoice", "Sales Invoice"),
                 ("Sales Invoice", "sales_order", "Sales Order"),
                 ("Sales Invoice", "delivery_note", "Delivery Note")]
    while queue and len(found) < 200:
        kind, docname = queue.pop(0)
        if (kind, docname) in found:
            continue
        try:
            doc = document(pos_profile, kind, docname)
        except frappe.PermissionError:
            restricted = True
            continue
        found[(kind, docname)] = doc
        for child_kind, field, parent_kind in relations:
            if kind == child_kind:
                queue.extend((parent_kind, row.get(field)) for row in doc.items if row.get(field))
            if kind == parent_kind and enabled(KINDS[child_kind]) and frappe.has_permission(child_kind, "read"):
                child_table = frappe.get_meta(child_kind).get_field("items").options
                if not frappe.get_meta(child_table).has_field(field):
                    continue
                parents = frappe.get_all(child_table, filters={field: docname, "parenttype": child_kind}, pluck="parent", limit_page_length=201)
                if parents:
                    visible = frappe.get_list(child_kind, filters={"name": ["in", parents], "company": root.company}, pluck="name", limit_page_length=201)
                    queue.extend((child_kind, item) for item in visible)
    rows = []
    for doc in found.values():
        row = {key: doc.get(key) for key in ("doctype", "name", "docstatus", "status", "grand_total", "currency", "per_delivered", "per_billed", "update_stock", "outstanding_amount")}
        row["has_stock_items"] = any(frappe.get_cached_value("Item", item.item_code, "is_stock_item") for item in doc.items)
        rows.append(row)
    outstanding = sum(max(0, flt(doc.outstanding_amount)) for doc in found.values() if doc.doctype == "Sales Invoice" and doc.docstatus == 1)
    pending = 0
    invoice_names = {doc.name for doc in found.values() if doc.doctype == "Sales Invoice"}
    if enabled("enable_cheque_tracking") and invoice_names:
        cheques = frappe.get_list("EsafePOS Customer Cheque", filters={"company": root.company, "customer": root.get("customer") or root.get("party_name"),
                                  "status": ["in", ["Received", "Deposited"]]}, fields=["allocations"], limit_page_length=0)
        pending = sum(any(row.get("name") in invoice_names for row in json.loads(cheque.allocations or "[]")) for cheque in cheques)
    result = progress(rows, outstanding, pending)
    result.update({"documents": rows, "outstanding": outstanding, "pending_cheques": pending,
                   "truncated": bool(queue), "restricted": restricted, "refreshed_at": str(now_datetime())})
    if queue or restricted:
        result["complete"], result["percent"] = False, min(result["percent"], 99)
    return result
