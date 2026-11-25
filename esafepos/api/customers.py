# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
"""Customer lookup screen, paginated client search plus a per-customer profile
with balances, lifetime stats and (via sales.search_sales) their POS
transactions. Search filters run before pagination; account balances are grouped
in company currency and purchase activity excludes cancelled sales and returns."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, now_datetime, nowdate

CUSTOMER_FIELDS = [
    "name", "customer_name", "customer_group", "customer_type",
    "mobile_no", "email_id", "tax_id", "default_currency", "default_price_list", "creation",
]


def _require_read():
    if not frappe.has_permission("Customer", "read"):
        frappe.throw(
            _("You are not permitted to view customers."), frappe.PermissionError
        )


@frappe.whitelist()
def search_customers(search: str | None = None, customer_group: str | None = None,
                     start: int | str = 0, limit: int | str = 30, company: str | None = None,
                     still_owes: int | str = 0, activity: str | None = None, activity_date: str | None = None):
    """Combine text, group, balance and activity filters before fetching a page."""
    _require_read()
    start = max(cint(start), 0)
    limit = max(1, min(cint(limit) or 30, 100))
    still_owes = bool(cint(still_owes))
    window = _activity_window(activity, activity_date)
    purchases = bool(activity and activity.startswith("purchased_"))
    if still_owes:
        from esafepos.features import enabled

        if not enabled("enable_customer_balances"):
            frappe.throw(_("Customer balances are turned off in Modules & Features."), frappe.PermissionError)
    if still_owes or purchases:
        company = _company_for_customer_view(company)
        if not company:
            frappe.throw(_("Select a company to filter customer balances or purchases."))
        return _filtered_customers(search, customer_group, start, limit, company, still_owes, window if purchases else None,
                                   window if window and not purchases else None)
    filters = {"disabled": 0}
    if customer_group:
        filters["customer_group"] = customer_group
    if window:
        filters["creation"] = [">=", window[0]]
        filters = [["Customer", key, value[0], value[1]] if isinstance(value, list)
                   else ["Customer", key, "=", value] for key, value in filters.items()]
        filters.append(["Customer", "creation", "<", window[1]])
    or_filters = None
    search = (search or "").strip()
    if search:
        like = f"%{search}%"
        or_filters = {
            "customer_name": ["like", like],
            "name": ["like", like],
            "mobile_no": ["like", like],
            "email_id": ["like", like],
            "tax_id": ["like", like],
        }
    rows = frappe.get_list(
        "Customer",
        filters=filters,
        or_filters=or_filters,
        fields=CUSTOMER_FIELDS,
        order_by="customer_name asc, name asc",
        limit_start=start,
        limit_page_length=limit + 1,
    )
    return {"items": rows[:limit], "has_more": len(rows) > limit}


def _activity_window(activity, activity_date=None):
    if not activity:
        return None
    today = getdate(nowdate())
    if activity in ("new_today", "purchased_today"):
        return str(today), str(add_days(today, 1))
    if activity in ("new_yesterday", "purchased_yesterday"):
        return str(add_days(today, -1)), str(today)
    if activity in ("new_week", "new_month"):
        return str(add_days(today, -6 if activity == "new_week" else -29)), str(add_days(today, 1))
    if activity == "purchased_date":
        if not activity_date:
            frappe.throw(_("Choose a purchase date."))
        day = getdate(activity_date)
        return str(day), str(add_days(day, 1))
    frappe.throw(_("Choose a valid customer activity filter."))


def _filtered_customers(search, group, start, limit, company, still_owes, purchases, created):
    from frappe.model.db_query import DatabaseQuery

    # Keep Frappe's user permissions, ownership, sharing and query hooks on
    # the Customer table, including the shared-only case on older versions.
    query = DatabaseQuery("Customer")
    query.reference_doctype = "Customer"
    match = query.build_match_conditions()
    conditions = ["`tabCustomer`.disabled = 0"]
    conditions.extend("(" + clause.replace("%", "%%") + ")" for clause in query.conditions + [match] if clause)
    values = {"company": company, "start": start, "limit": limit + 1}
    if group:
        conditions.append("`tabCustomer`.customer_group = %(group)s")
        values["group"] = group
    if (search or "").strip():
        conditions.append("(" + " or ".join("`tabCustomer`.{0} like %(search)s".format(field)
                          for field in ("name", "customer_name", "mobile_no", "email_id", "tax_id")) + ")")
        values["search"] = "%" + search.strip() + "%"
    if created:
        conditions.append("`tabCustomer`.creation >= %(created_from)s and `tabCustomer`.creation < %(created_to)s")
        values.update({"created_from": created[0], "created_to": created[1]})
    if purchases:
        from esafepos.walk_in import customer_attribution_sql

        activity_queries = []
        for doctype in ("POS Invoice", "Sales Invoice"):
            join, _, matches = customer_attribution_sql(doctype)
            matches = matches.replace("%(customer)s", "`tabCustomer`.name")
            extra = " and ifnull(pi.is_consolidated, 0) = 0" if doctype == "Sales Invoice" else ""
            activity_queries.append(
                "exists (select 1 from `tab{0}` pi {1} where {2} and pi.company = %(company)s "
                "and pi.docstatus = 1 and pi.is_return = 0 and pi.posting_date >= %(purchase_from)s "
                "and pi.posting_date < %(purchase_to)s{3})".format(doctype, join, matches, extra)
            )
        conditions.append("(" + " or ".join(activity_queries) + ")")
        values.update({"purchase_from": purchases[0], "purchase_to": purchases[1]})
    balance_join, balance_field = "", ""
    if still_owes:
        # Same ledger balance as credit_sales.owed: includes POS credit
        # journals and regular invoices, nets payments/advances, ignores holds.
        balance_join = """join (
            select party, round(sum(debit) - sum(credit), 2) as outstanding
            from `tabGL Entry`
            where company = %(company)s and party_type = 'Customer' and is_cancelled = 0
            group by party having outstanding > 0.005
        ) balances on balances.party = `tabCustomer`.name"""
        balance_field = ", balances.outstanding"
    fields = ", ".join("`tabCustomer`.`{0}`".format(field) for field in CUSTOMER_FIELDS)
    rows = frappe.db.sql(
        "select {0}{1} from `tabCustomer` {2} where {3} "
        "order by `tabCustomer`.customer_name asc, `tabCustomer`.name asc limit %(limit)s offset %(start)s".format(
            fields, balance_field, balance_join, " and ".join(conditions)), values, as_dict=True,
    )
    return {"items": rows[:limit], "has_more": len(rows) > limit,
            "currency": frappe.get_cached_value("Company", company, "default_currency")}


@frappe.whitelist()
def customer_price_lists(customer: str, pos_profile: str):
    """Enabled selling lists in the currency this customer's sale will use."""
    doc, profile = _price_list_customer(customer, pos_profile)
    billing_currency = doc.get("default_currency") or frappe.get_cached_value("Price List", profile.selling_price_list, "currency")
    return frappe.get_list("Price List", filters={"enabled": 1, "selling": 1, "currency": billing_currency},
                           fields=["name", "currency"], order_by="name asc", limit_page_length=0)


def _price_list_customer(customer, pos_profile):
    _require_read()
    from esafepos.api.permissions import assert_outlet

    assert_outlet(pos_profile)
    doc = frappe.get_doc("Customer", customer)
    doc.check_permission("read")
    profile = frappe.get_cached_doc("POS Profile", pos_profile)
    return doc, profile


@frappe.whitelist()
def set_customer_price_list(customer: str, pos_profile: str, price_list: str | None = None):
    """Update ERPNext's native field with normal document validation/auditing."""
    doc, profile = _price_list_customer(customer, pos_profile)
    doc.check_permission("write")
    price_list = (price_list or "").strip()
    if price_list:
        selected = frappe.get_doc("Price List", price_list)
        selected.check_permission("read")
        if not cint(selected.get("enabled")) or not cint(selected.get("selling")):
            frappe.throw(_("Choose an enabled selling price list."))
        billing_currency = doc.get("default_currency") or frappe.get_cached_value("Price List", profile.selling_price_list, "currency")
        if selected.currency != billing_currency:
            frappe.throw(_("Choose a price list in {0}, this customer's sale currency.").format(billing_currency))
    doc.default_price_list = price_list or None
    doc.save()
    frappe.clear_document_cache("Customer", customer)
    return {"customer": doc.name, "default_price_list": doc.default_price_list}


@frappe.whitelist()
def customer_groups():
    """Flat list of customer-group names for the screen's filter dropdown."""
    _require_read()
    return frappe.get_all(
        "Customer Group",
        filters={"is_group": 0},
        pluck="name",
        order_by="name asc",
        limit_page_length=0,
    )


@frappe.whitelist()
def customer_detail(customer: str, company: str | None = None):
    """Profile + balances + lifetime POS stats for one customer. The stats are a
    single grouped query scoped to this customer (the `customer` column is
    indexed), so it stays cheap regardless of total invoice volume. They add up
    the company-currency values: a customer may have bought in more than one
    currency (esafepos.currency)."""
    _require_read()
    if not frappe.db.exists("Customer", customer):
        frappe.throw(_("Customer {0} not found").format(customer))
    doc = frappe.get_doc("Customer", customer)
    doc.check_permission("read")

    # One company's figures, the till's own by default: adding another
    # company's sales (in its currency) made a number that meant nothing.
    company = company or frappe.defaults.get_user_default("company") or frappe.db.get_single_value(
        "Global Defaults", "default_company"
    )
    from esafepos.api.permissions import allowed_companies

    companies = allowed_companies()
    if companies is not None and company not in companies:
        frappe.throw(_("You cannot see {0}'s figures").format(company), frappe.PermissionError)
    # Both invoice kinds: an outlet may post Sales Invoices directly. Not the
    # Sales Invoice ERPNext consolidates a shift into: it carries is_pos too,
    # and its POS Invoices are already counted.
    from esafepos.walk_in import customer_attribution_sql

    has_invoice_origin = frappe.get_meta("Sales Invoice").has_field("esafepos_invoice_origin")

    stats = frappe._dict(sales_count=0, returns_count=0, total_spent=0, total_refunded=0, last_purchase=None)
    for doctype, extra in (
        ("POS Invoice", ""),
        (
            "Sales Invoice",
            (
                " and ((pi.is_pos = 1 and ifnull(pi.is_consolidated, 0) = 0) "
                "or (pi.is_pos = 0 and pi.esafepos_invoice_origin = 'Customer Invoice'))"
                if has_invoice_origin
                else " and ((pi.is_pos = 1 and ifnull(pi.is_consolidated, 0) = 0) or pi.is_pos = 0)"
            ),
        ),
    ):
        join, _, customer_matches = customer_attribution_sql(doctype)
        # doctype and extra are fixed strings, the values are bound.
        row = frappe.db.sql(  # nosemgrep
            f"""
            select
                sum(case when pi.is_return = 0 then 1 else 0 end) as sales_count,
                sum(case when pi.is_return = 1 then 1 else 0 end) as returns_count,
                sum(case when pi.is_return = 0 then pi.base_grand_total else 0 end) as total_spent,
                sum(case when pi.is_return = 1 then abs(pi.base_grand_total) else 0 end) as total_refunded,
                max(pi.posting_date) as last_purchase
            from `tab{doctype}` pi
            {join}
            where {customer_matches} and pi.company = %(company)s and pi.docstatus = 1{extra}
            """,
            {"customer": customer, "company": company},
            as_dict=True,
        )[0]
        stats.sales_count += cint(row.sales_count)
        stats.returns_count += cint(row.returns_count)
        stats.total_spent += flt(row.total_spent)
        stats.total_refunded += flt(row.total_refunded)
        if row.last_purchase and (not stats.last_purchase or row.last_purchase > stats.last_purchase):
            stats.last_purchase = row.last_purchase
    wallet = {"loyalty_points": 0, "store_credit": 0}
    try:
        from esafepos.api.loyalty import get_wallet

        if company:
            wallet = get_wallet(customer, company)
    except Exception:
        # Wallet is best-effort; the profile + stats still load without it.
        pass

    return {
        "name": doc.name,
        "customer_name": doc.customer_name,
        "customer_group": doc.customer_group,
        "customer_type": doc.get("customer_type"),
        "mobile_no": doc.get("mobile_no"),
        "email_id": doc.get("email_id"),
        "tax_id": doc.get("tax_id"),
        "territory": doc.get("territory"),
        "member_since": str(doc.creation)[:10] if doc.creation else None,
        "stats": {
            "sales_count": cint(stats.sales_count),
            "returns_count": cint(stats.returns_count),
            "total_spent": flt(stats.total_spent),
            "total_refunded": flt(stats.total_refunded),
            "net_spent": flt(stats.total_spent) - flt(stats.total_refunded),
            "last_purchase": str(stats.last_purchase) if stats.last_purchase else None,
        },
        "wallet": {
            "loyalty_points": wallet.get("loyalty_points") or 0,
            "store_credit": wallet.get("store_credit") or 0,
        },
        "company": company,
        "currency": (frappe.get_cached_value("Company", company, "default_currency") if company else None)
        or frappe.db.get_default("currency"),
        "billing_currency": doc.get("default_currency"),
        "default_price_list": doc.get("default_price_list"),
        "can_edit_price_list": bool(doc.has_permission("write") and frappe.has_permission("Price List", "read")),
    }


def _fields(doctype, names):
    meta = frappe.get_meta(doctype)
    return [name for name in names if meta.has_field(name)]


def _company_for_customer_view(company):
    company = company or frappe.defaults.get_user_default("company") or frappe.db.get_single_value(
        "Global Defaults", "default_company"
    )
    from esafepos.api.permissions import allowed_companies

    companies = allowed_companies()
    if companies is not None and company not in companies:
        frappe.throw(_("You cannot see figures for {0}.").format(company), frappe.PermissionError)
    return company


@frappe.whitelist()
def customer_sales_progress(customer: str, company: str | None = None):
    """Read-only Sales Rep Mode view of this customer's ERPNext sales pipeline."""
    _require_read()
    from esafepos.features import enabled as feature_enabled

    if not feature_enabled("enable_customer_sales_progress"):
        frappe.throw(_("Customer sales progress is turned off in Modules & Features."), frappe.PermissionError)
    if not frappe.db.exists("Customer", customer):
        frappe.throw(_("Customer {0} not found.").format(customer))
    company = _company_for_customer_view(company)
    stages = {}

    def fetch_stage(doctype, filters, requested, order_by, limit=40):
        if not frappe.has_permission(doctype, "read"):
            return []
        fields = _fields(doctype, requested)
        return frappe.get_list(
            doctype,
            filters=filters,
            fields=fields,
            order_by=order_by,
            limit_page_length=limit,
        )

    quotations = fetch_stage(
        "Quotation",
        {"quotation_to": "Customer", "party_name": customer, "company": company, "docstatus": 1},
        ["name", "transaction_date", "valid_till", "status", "grand_total", "currency"],
        "transaction_date desc, modified desc",
    )
    orders = fetch_stage(
        "Sales Order",
        {"customer": customer, "company": company, "docstatus": 1},
        ["name", "transaction_date", "delivery_date", "status", "grand_total", "currency", "per_delivered", "per_billed", "total_qty"],
        "transaction_date desc, modified desc",
    )
    order_names = [row.name for row in orders]
    delivery_notes = fetch_stage(
        "Delivery Note",
        {"customer": customer, "company": company, "docstatus": 1},
        ["name", "posting_date", "status", "grand_total", "currency", "per_billed"],
        "posting_date desc, modified desc",
    )
    invoices = fetch_stage(
        "Sales Invoice",
        {"customer": customer, "company": company, "docstatus": 1},
        ["name", "posting_date", "due_date", "status", "grand_total", "outstanding_amount", "currency", "conversion_rate", "is_pos", "is_consolidated"],
        "posting_date desc, modified desc",
    )
    invoices = [row for row in invoices if not (cint(row.get("is_pos")) and cint(row.get("is_consolidated")))]

    undelivered_qty = 0.0
    undelivered_value = 0.0
    if order_names and frappe.has_permission("Sales Order", "read") and frappe.db.table_exists("Sales Order Item"):
        item_fields = _fields("Sales Order Item", ["qty", "delivered_qty", "rate", "item_code", "item_name", "parent"])
        for row in frappe.get_all(
            "Sales Order Item",
            filters={"parent": ["in", order_names], "parenttype": "Sales Order"},
            fields=item_fields,
            limit_page_length=0,
        ):
            remaining = max(flt(row.qty) - flt(row.get("delivered_qty")), 0)
            undelivered_qty += remaining
            undelivered_value += remaining * flt(row.get("rate"))

    payments = []
    if frappe.has_permission("Payment Entry", "read"):
        payments.extend(
            fetch_stage(
                "Payment Entry",
                {"payment_type": "Receive", "party_type": "Customer", "party": customer, "company": company, "docstatus": 1},
                ["name", "posting_date", "mode_of_payment", "reference_no", "reference_date", "paid_amount", "received_amount", "base_paid_amount", "currency"],
                "posting_date desc, modified desc",
                100,
            )
        )
    if frappe.has_permission("POS Invoice", "read"):
        pos_meta = frappe.get_meta("POS Invoice")
        payment_field = pos_meta.get_field("payments")
        pos_invoices = frappe.get_list(
            "POS Invoice",
            filters={"customer": customer, "company": company, "docstatus": 1},
            fields=_fields("POS Invoice", ["name", "posting_date", "currency", "conversion_rate"]),
            limit_page_length=0,
        )
        if payment_field and payment_field.options and pos_invoices:
            payment_doctype = payment_field.options
            payment_names = [row.name for row in pos_invoices]
            payment_fields = _fields(
                payment_doctype,
                ["parent", "mode_of_payment", "amount", "base_amount", "reference_no", "reference_date"],
            )
            invoice_by_name = {row.name: row for row in pos_invoices}
            for row in frappe.get_all(
                payment_doctype,
                filters={"parent": ["in", payment_names], "parenttype": "POS Invoice"},
                fields=payment_fields,
                limit_page_length=0,
            ):
                invoice = invoice_by_name.get(row.parent)
                amount = flt(row.get("base_amount") or (flt(row.get("amount")) * flt(invoice.get("conversion_rate") or 1)), 2)
                payments.append({
                    "name": row.parent,
                    "posting_date": invoice.posting_date,
                    "mode_of_payment": row.get("mode_of_payment"),
                    "reference_no": row.get("reference_no"),
                    "reference_date": row.get("reference_date"),
                    "paid_amount": amount,
                    "currency": frappe.get_cached_value("Company", company, "default_currency"),
                })
    if frappe.has_permission("Sales Invoice", "read"):
        pos_sales_invoices = [row for row in invoices if cint(row.get("is_pos"))]
        payment_field = frappe.get_meta("Sales Invoice").get_field("payments")
        if payment_field and payment_field.options and pos_sales_invoices:
            payment_doctype = payment_field.options
            invoice_names = [row.name for row in pos_sales_invoices]
            payment_fields = _fields(
                payment_doctype,
                ["parent", "mode_of_payment", "amount", "base_amount", "reference_no", "reference_date"],
            )
            invoice_by_name = {row.name: row for row in pos_sales_invoices}
            for row in frappe.get_all(
                payment_doctype,
                filters={"parent": ["in", invoice_names], "parenttype": "Sales Invoice"},
                fields=payment_fields,
                limit_page_length=0,
            ):
                invoice = invoice_by_name.get(row.parent)
                amount = flt(row.get("base_amount") or (flt(row.get("amount")) * flt(invoice.get("conversion_rate") or 1)), 2)
                payments.append({
                    "name": row.parent,
                    "posting_date": invoice.posting_date,
                    "mode_of_payment": row.get("mode_of_payment"),
                    "reference_no": row.get("reference_no"),
                    "reference_date": row.get("reference_date"),
                    "paid_amount": amount,
                    "currency": frappe.get_cached_value("Company", company, "default_currency"),
                })
    if frappe.has_permission("Journal Entry", "read") and frappe.get_meta("Journal Entry").has_field("esafepos_credit_kind"):
        journals = frappe.get_list(
            "Journal Entry",
            filters={"esafepos_credit_kind": "Payment", "esafepos_credit_customer": customer, "company": company, "docstatus": 1},
            fields=["name", "posting_date", "mode_of_payment", "cheque_no", "cheque_date"],
            order_by="posting_date desc, modified desc",
            limit_page_length=100,
        )
        for entry in journals:
            cash_rows = frappe.get_all(
                "Journal Entry Account",
                filters={"parent": entry.name, "parenttype": "Journal Entry", "party_type": ["in", ["", None]], "debit_in_account_currency": [">", 0]},
                fields=["debit_in_account_currency"],
                limit_page_length=0,
            )
            amount = flt(sum(flt(row.debit_in_account_currency) for row in cash_rows), 2)
            payments.append({
                "name": entry.name,
                "posting_date": entry.posting_date,
                "mode_of_payment": entry.mode_of_payment,
                "reference_no": entry.cheque_no,
                "reference_date": entry.cheque_date,
                "paid_amount": amount,
                "currency": frappe.get_cached_value("Company", company, "default_currency"),
            })

    payments.sort(key=lambda row: str(row.get("posting_date") or ""), reverse=True)
    payment_totals = {"cash": 0.0, "cheque": 0.0, "bank_transfer": 0.0, "other": 0.0, "total": 0.0}
    for row in payments:
        amount = flt(row.get("base_paid_amount") or row.get("received_amount") or row.get("paid_amount"), 2)
        mode = (row.get("mode_of_payment") or "").casefold()
        bucket = "cheque" if "cheque" in mode or "check" in mode else ("cash" if "cash" in mode else ("bank_transfer" if "bank" in mode or "transfer" in mode else "other"))
        payment_totals[bucket] += amount
        payment_totals["total"] += amount
    payment_totals = {key: flt(value, 2) for key, value in payment_totals.items()}

    todos = []
    if frappe.has_permission("ToDo", "read"):
        todos = fetch_stage(
            "ToDo",
            {"reference_type": "Customer", "reference_name": customer, "status": "Open"},
            ["name", "description", "date", "allocated_to", "priority", "status"],
            "date asc, modified desc",
            50,
        )

    from esafepos.credit_sales import owed

    return {
        "company": company,
        "currency": frappe.get_cached_value("Company", company, "default_currency"),
        "stages": {
            "quotations": quotations,
            "sales_orders": orders,
            "delivery_notes": delivery_notes,
            "sales_invoices": invoices,
        },
        "outstanding": flt(owed(customer, company), 2),
        "goods_to_deliver": {"qty": flt(undelivered_qty, 3), "value": flt(undelivered_value, 2)},
        "payments": payments[:100],
        "payment_totals": payment_totals,
        "pending_tasks": todos,
        "refreshed_at": str(now_datetime()),
    }
