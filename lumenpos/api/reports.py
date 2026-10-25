# Copyright (c) 2026 Lumen Solutions
# SPDX-License-Identifier: AGPL-3.0-only
# "LumenPOS" is a trademark of Lumen Solutions. See TRADEMARKS.md.
"""Reports in Insights (0.62.0).

Asked by the Zimbabwe shop (2026-10-15, screenshots of another POS's
dashboard) and agreed with the owner in three phases. This module is the
first: a sales and cash summary over a period, and how each cashier did.

Everything is read from the till's own documents, the way the salesperson
report reads them (lumenpos.api.salespeople): the POS Invoices, and the
Sales Invoices of an outlet that posts them directly, never a consolidated
one (it holds the same sales a second time). Amounts are in the company
currency (ERPNext's base_ fields), so a shop selling in several currencies
adds up in one. The cash counted at the close is read from the shift
(POS Register Session), each count in its own drawer's currency.

Phase 2 (products and profit): the lines sold, by item, group, brand, the item a
variant belongs to and its attributes; and what they cost. The cost follows
ERPNext's own Gross Profit report (erpnext/accounts/report/gross_profit): a
stock item's cost is what the stock ledger booked for it when the sale was
posted, here the Sales Invoice the shift's close merged the sale into (or the
outlet's own Sales Invoice); a bundle costs its components; a non-stock item
costs nothing. A sale not posted yet (its shift still open) has no ledger entry,
so its cost is estimated at the item's valuation rate in the outlet's
warehouse, as the report does when it has no entry, and is shown as estimated.
LumenPOS's own placeholder items (the gift card, the deposit) are not products
and stay out.

Who may see what: "See sales reports", "See cashier performance" and "See
profit" in Who can do what, nobody but a manager until a shop names someone,
and the whole of it can be switched off (LumenPOS Settings, Sales reports in
Insights).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from lumenpos.api import permissions
from lumenpos.api.salespeople import _outlets

MAX_DAYS = 370
SALE_DOCTYPES = ("POS Invoice", "Sales Invoice")


def enabled():
    """Sales reports in Insights: on unless a shop switched it off. A site
    updated without its migrate has no such field yet: on, as it ships."""
    try:
        value = frappe.db.get_single_value("LumenPOS Settings", "reports_in_insights")
    except Exception:
        return True
    stored = frappe.db.sql(
        "select value from tabSingles where doctype=%s and field=%s",
        ("LumenPOS Settings", "reports_in_insights"),
    )
    return bool(cint(value)) if stored else True


def can_see_sales_reports(user=None):
    return enabled() and permissions.can_see_sales_reports(user)


def can_see_cashier_report(user=None):
    return enabled() and permissions.can_see_cashier_report(user)


def can_see_profit(user=None):
    return enabled() and permissions.can_see_profit(user)


def _period(from_date, to_date):
    start = getdate(from_date or nowdate())
    end = getdate(to_date or from_date or nowdate())
    if end < start:
        start, end = end, start
    if (end - start).days > MAX_DAYS:
        frappe.throw(_("Pick a period of one year or less."))
    return start, end


def _invoices(outlets, start, end):
    """Every submitted sale and return of these outlets in the period, from
    both doctypes. `doctype` below is one of SALE_DOCTYPES, never user input."""
    if not outlets:
        return []
    rows = []
    params = {"outlets": tuple(outlets), "start": start, "end": end}
    for doctype in SALE_DOCTYPES:
        extra = " and is_pos = 1 and is_consolidated = 0" if doctype == "Sales Invoice" else ""
        found = frappe.db.sql(  # nosemgrep
            f"""
            select name, %(doctype)s as doctype, owner, pos_profile, customer, posting_date, posting_time,
                   is_return, total_qty, base_net_total, base_discount_amount,
                   base_total_taxes_and_charges, base_grand_total, base_rounded_total,
                   base_change_amount, account_for_change_amount, currency, change_amount
            from `tab{doctype}`
            where docstatus = 1{extra} and pos_profile in %(outlets)s
              and posting_date between %(start)s and %(end)s
            """,
            dict(params, doctype=doctype),
            as_dict=True,
        )
        rows.extend(found)
    return rows


def _by_doctype(invoices):
    names = {}
    for inv in invoices:
        names.setdefault(inv.doctype, []).append(inv.name)
    return names


def _line_discounts(invoices):
    """What each SALE gave off the price list on its lines, in the company
    currency: (price list rate less the rate) times the quantity, where the
    line was sold below its list price. A return gives nothing back here: its
    sale's discount was counted on the sale."""
    out = {}
    for doctype, names in _by_doctype([i for i in invoices if not cint(i.is_return)]).items():
        rows = frappe.db.sql(  # nosemgrep
            f"""
            select parent, sum((base_price_list_rate - base_rate) * qty) as discount
            from `tab{doctype} Item`
            where parent in %(names)s and base_price_list_rate > base_rate
            group by parent
            """,
            {"names": tuple(names)},
            as_dict=True,
        )
        for r in rows:
            out[r.parent] = flt(r.discount)
    return out


def _payments(invoices, company):
    """What each payment method took over these sales, in the company currency,
    the change given taken off the method whose account gave it (the drawer),
    or off the first cash method when no method holds that account. Each method
    also lists what it took in other currencies, in their own money (`paid_in`,
    0.66.0, lumenpos.paid_in), change given in that money taken off the same way."""
    from lumenpos import currency
    from lumenpos import paid_in

    local = currency.company_currency(company)
    with_fields = paid_in.has_fields()
    result = {}
    foreign = {}
    for doctype, names in _by_doctype(invoices).items():
        extra = ", p.lumenpos_paid_currency as paid_currency, p.lumenpos_paid_amount as paid_amount" if with_fields else ""
        rows = frappe.db.sql(  # nosemgrep
            f"""
            select p.mode_of_payment, p.amount, p.base_amount, inv.currency{extra}
            from `tabSales Invoice Payment` p
            join `tab{doctype}` inv on inv.name = p.parent
            where p.parenttype = %(doctype)s and p.parent in %(names)s
            """,
            {"doctype": doctype, "names": tuple(names)},
            as_dict=True,
        )
        for r in rows:
            result[r.mode_of_payment] = flt(result.get(r.mode_of_payment)) + flt(r.base_amount)
            code, paid = paid_in.of_row(r, company, local)
            if code:
                by = foreign.setdefault(r.mode_of_payment, {})
                by[code] = flt(by.get(code)) + paid
    change = {}
    change_foreign = {}
    for inv in invoices:
        if flt(inv.base_change_amount):
            change[inv.account_for_change_amount] = flt(change.get(inv.account_for_change_amount)) + flt(inv.base_change_amount)
            sale = inv.get("currency")
            given_in = frappe.get_cached_value("Account", inv.account_for_change_amount, "account_currency") if inv.account_for_change_amount else None
            if sale and sale != local and given_in == sale and flt(inv.get("change_amount")):
                key = (inv.account_for_change_amount, sale)
                change_foreign[key] = flt(change_foreign.get(key)) + flt(inv.change_amount)
    if change:
        accounts = {}
        for mode in result:
            account = frappe.db.get_value("Mode of Payment Account", {"parent": mode, "company": company}, "default_account")
            if account:
                accounts.setdefault(account, mode)
        cash = [m for m in result if frappe.get_cached_value("Mode of Payment", m, "type") == "Cash"]

        def target_of(account):
            return accounts.get(account) or (cash[0] if cash else None)

        for account, amount in change.items():
            target = target_of(account)
            if target:
                result[target] = flt(result[target]) - amount
        for (account, code), amount in change_foreign.items():
            target = target_of(account)
            if target and code in foreign.get(target, {}):
                foreign[target][code] = flt(foreign[target][code]) - amount
    return [
        {
            "mode_of_payment": m,
            "amount": flt(a, 2),
            "paid_in": [{"currency": c, "amount": flt(v, 2)} for c, v in sorted((foreign.get(m) or {}).items()) if flt(v, 2)],
        }
        for m, a in sorted(result.items(), key=lambda kv: -kv[1])
    ]


def _sale_moment(posting_date, posting_time):
    """"YYYY-MM-DD HH:MM:SS" for a sale, which sorts as text in time order."""
    from frappe.utils import get_datetime

    try:
        return get_datetime(f"{posting_date} {posting_time or '0:00:00'}").strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return f"{posting_date} 00:00:00"


def _paid_in_totals(payments):
    """Everything taken in each other currency, over every method."""
    totals = {}
    for p in payments:
        for x in p.get("paid_in") or []:
            totals[x["currency"]] = flt(totals.get(x["currency"])) + flt(x["amount"])
    return [{"currency": c, "amount": flt(v, 2)} for c, v in sorted(totals.items()) if flt(v, 2)]


def _figures(invoices, discounts):
    """Counts and amounts of a set of invoices, sales and returns apart."""
    out = {
        "sales": 0, "returns": 0, "items_sold": 0.0, "discounts": 0.0,
        "sales_net": 0.0, "returns_net": 0.0, "net": 0.0, "tax": 0.0, "total": 0.0,
        "sales_total": 0.0, "returns_total": 0.0,
    }
    for inv in invoices:
        total = flt(inv.base_rounded_total) or flt(inv.base_grand_total)
        out["net"] += flt(inv.base_net_total)
        out["tax"] += flt(inv.base_total_taxes_and_charges)
        out["total"] += total
        out["items_sold"] += flt(inv.total_qty)
        if cint(inv.is_return):
            out["returns"] += 1
            out["returns_net"] += flt(inv.base_net_total)
            out["returns_total"] += total
        else:
            out["sales"] += 1
            out["sales_net"] += flt(inv.base_net_total)
            out["sales_total"] += total
            out["discounts"] += flt(discounts.get(inv.name)) + flt(inv.base_discount_amount)
    out["average_sale"] = out["sales_total"] / out["sales"] if out["sales"] else 0.0
    return {k: (flt(v, 2) if isinstance(v, float) else v) for k, v in out.items()}


def _shifts(outlets, start, end, opened_by=None):
    """The shifts opened in the period at these outlets, each with what its
    close counted against what was expected, per drawer and in that drawer's
    currency. An open shift has no count yet."""
    if not outlets:
        return []
    filters = {
        "pos_profile": ["in", list(outlets)],
        "opened_at": ["between", [f"{start} 00:00:00", f"{end} 23:59:59.999999"]],
    }
    if opened_by:
        filters["opened_by"] = opened_by
    sessions = frappe.get_all(
        "POS Register Session",
        filters=filters,
        fields=["name", "pos_profile", "opened_by", "opened_at", "closed_at", "status", "opening_float",
                "sales_count", "total_sales", "expected_pending", "variance_reason"],
        order_by="opened_at desc",
        limit_page_length=0,
    )
    if not sessions:
        return []
    counts = {}
    for row in frappe.get_all(
        "POS Register Payment Count",
        filters={"parenttype": "POS Register Session", "parent": ["in", [s.name for s in sessions]]},
        fields=["parent", "mode_of_payment", "currency", "expected_amount", "counted_amount", "difference"],
        order_by="idx asc",
        limit_page_length=0,
    ):
        counts.setdefault(row.parent, []).append(
            {"mode_of_payment": row.mode_of_payment, "currency": row.currency or "",
             "expected": flt(row.expected_amount, 2), "counted": flt(row.counted_amount, 2),
             "difference": flt(row.difference, 2)}
        )
    out = []
    for s in sessions:
        rows = counts.get(s.name, []) if s.status != "Open" else []
        out.append({
            "name": s.name, "pos_profile": s.pos_profile, "opened_by": s.opened_by,
            "opened_at": str(s.opened_at or ""), "closed_at": str(s.closed_at or ""), "status": s.status,
            "opening_float": flt(s.opening_float, 2), "sales_count": cint(s.sales_count),
            "pending": cint(s.expected_pending), "variance_reason": s.variance_reason or "",
            "counts": rows,
            "off": any(abs(r["difference"]) >= 0.005 for r in rows),
        })
    return out


def _differences(shifts, company_currency):
    """The counted-less-expected of these shifts, added up per currency."""
    by = {}
    for s in shifts:
        if s["pending"]:
            continue
        for r in s["counts"]:
            ccy = r["currency"] or company_currency
            by[ccy] = flt(by.get(ccy)) + r["difference"]
    return [{"currency": c, "difference": flt(v, 2)} for c, v in sorted(by.items())]


def _names(users):
    if not users:
        return {}
    return {u.name: u.full_name or u.name for u in frappe.get_all(
        "User", filters={"name": ["in", list(users)]}, fields=["name", "full_name"])}


def _context(from_date, to_date, pos_profile, company, outlet=None):
    from lumenpos import currency

    start, end = _period(from_date, to_date)
    outlets, company = _outlets(pos_profile, company, outlet)
    return start, end, outlets, company, currency.company_currency(company)


@frappe.whitelist()
def sales_summary(from_date: str | None = None, to_date: str | None = None, pos_profile: str | None = None,
                  company: str | None = None, outlet: str | None = None):
    """Sales, returns, tax, payments and the cash counted at the close, over a
    period, for one outlet or every outlet of a company. Day by day over a
    longer period, hour by hour over one day."""
    if not can_see_sales_reports():
        frappe.throw(_("You're not allowed to see the sales reports."), frappe.PermissionError)
    start, end, outlets, company, ccy = _context(from_date, to_date, pos_profile, company, outlet)
    invoices = _invoices(outlets, start, end)
    discounts = _line_discounts(invoices)

    one_day = start == end
    buckets = {}
    for inv in invoices:
        # posting_time comes back as a timedelta ("9:05:00"), so the hour is
        # what stands before the first colon.
        key = "%02d" % cint(str(inv.posting_time or "0").split(":")[0]) if one_day else str(inv.posting_date)
        buckets.setdefault(key, []).append(inv)
    series = []
    for key in sorted(buckets):
        f = _figures(buckets[key], discounts)
        series.append({"key": key, "sales": f["sales"], "returns": f["returns"], "net": f["net"],
                       "tax": f["tax"], "total": f["total"]})

    payments = _payments(invoices, company)
    shifts = _shifts(outlets, start, end)
    names = _names({s["opened_by"] for s in shifts})
    for s in shifts:
        s["opened_by_name"] = names.get(s["opened_by"], s["opened_by"])
    return {
        "from_date": str(start), "to_date": str(end), "company": company, "currency": ccy,
        "outlets": outlets, "by": "hour" if one_day else "day",
        "totals": _figures(invoices, discounts),
        "payments": payments,
        "paid_in": _paid_in_totals(payments),
        "series": series,
        "shifts": shifts,
        "differences": _differences(shifts, ccy),
    }


@frappe.whitelist()
def cashiers(from_date: str | None = None, to_date: str | None = None, pos_profile: str | None = None,
             company: str | None = None, outlet: str | None = None):
    """How each cashier did over a period: the sales and returns they rang up,
    what they gave off the list price, the price edits the audit log holds
    for them, their shifts and how far their counts were from what was
    expected."""
    if not can_see_cashier_report():
        frappe.throw(_("You're not allowed to see how each cashier did."), frappe.PermissionError)
    start, end, outlets, company, ccy = _context(from_date, to_date, pos_profile, company, outlet)
    invoices = _invoices(outlets, start, end)
    discounts = _line_discounts(invoices)
    mine = {}
    for inv in invoices:
        mine.setdefault(inv.owner, []).append(inv)

    edits = {}
    if outlets:
        for row in frappe.db.sql(
            """
            select user, count(*) as n from `tabLumenPOS Audit Log`
            where action = %(action)s and pos_profile in %(outlets)s
              and date(creation) between %(start)s and %(end)s
            group by user
            """,
            {"action": "Price edit", "outlets": tuple(outlets), "start": start, "end": end},
            as_dict=True,
        ):
            edits[row.user] = cint(row.n)

    shifts = _shifts(outlets, start, end)
    by_shift = {}
    for s in shifts:
        by_shift.setdefault(s["opened_by"], []).append(s)

    users = set(mine) | set(by_shift) | set(edits)
    names = _names(users)
    rows = []
    for user in users:
        f = _figures(mine.get(user, []), discounts)
        own = by_shift.get(user, [])
        rows.append({
            "user": user, "name": names.get(user, user),
            "sales": f["sales"], "returns": f["returns"], "items_sold": f["items_sold"],
            "net": f["net"], "total": f["total"], "average_sale": f["average_sale"],
            "returns_total": f["returns_total"], "discounts": f["discounts"],
            "price_edits": edits.get(user, 0),
            "shifts": len(own),
            "shifts_off": sum(1 for s in own if s["off"] and not s["pending"]),
            "differences": _differences(own, ccy),
        })
    rows.sort(key=lambda r: (-r["total"], r["name"]))
    return {
        "from_date": str(start), "to_date": str(end), "company": company, "currency": ccy,
        "outlets": outlets, "rows": rows,
    }


# ---------------------------------------------------------------------------
# Phase 2: products and profit
# ---------------------------------------------------------------------------


def _lines(outlets, start, end):
    """Every line sold or returned at these outlets in the period, LumenPOS's
    placeholder items left out, each with the invoice that posted it to the
    books: a POS Invoice's merged Sales Invoice (empty until its shift closes),
    or the outlet's own Sales Invoice. `doctype` below is one of SALE_DOCTYPES."""
    if not outlets:
        return []
    from lumenpos.api.catalog import internal_item_codes

    params = {"outlets": tuple(outlets), "start": start, "end": end,
              "skip": tuple(internal_item_codes()) or ("",)}
    rows = []
    for doctype in SALE_DOCTYPES:
        if doctype == "POS Invoice":
            posted, extra = "inv.consolidated_invoice", ""
        else:
            posted, extra = "inv.name", " and inv.is_pos = 1 and inv.is_consolidated = 0"
        rows.extend(frappe.db.sql(  # nosemgrep
            f"""
            select inv.name as invoice, {posted} as posted, inv.posting_date, inv.is_return,
                   it.item_code, it.item_name, it.item_group, it.brand, it.warehouse,
                   it.qty, it.stock_qty, it.base_net_amount
            from `tab{doctype} Item` it
            join `tab{doctype}` inv on inv.name = it.parent
            where inv.docstatus = 1{extra} and inv.pos_profile in %(outlets)s
              and inv.posting_date between %(start)s and %(end)s
              and it.item_code not in %(skip)s
            """,
            params,
            as_dict=True,
        ))
    return rows


def _item_info(codes):
    if not codes:
        return {}
    return {r.name: r for r in frappe.get_all(
        "Item", filters={"name": ["in", list(codes)]},
        fields=["name", "item_name", "is_stock_item", "variant_of", "valuation_rate"],
        limit_page_length=0)}


def _bundles(codes):
    """Each Product Bundle among these items with its components and their
    quantities per bundle."""
    out = {}
    if not codes:
        return out
    for b in frappe.get_all("Product Bundle", filters={"new_item_code": ["in", list(codes)]},
                            fields=["name", "new_item_code"], limit_page_length=0):
        out[b.new_item_code] = [
            (r.item_code, flt(r.qty)) for r in frappe.get_all(
                "Product Bundle Item", filters={"parent": b.name, "parenttype": "Product Bundle"},
                fields=["item_code", "qty"], order_by="idx asc")
        ]
    return out


def _ledger(posted):
    """What the stock ledger booked for each posted invoice and item: the
    value and the quantity that moved."""
    out = {}
    if not posted:
        return out
    for r in frappe.db.sql(
        """
        select voucher_no, item_code, sum(stock_value_difference) as value, sum(actual_qty) as qty
        from `tabStock Ledger Entry`
        where voucher_type = 'Sales Invoice' and voucher_no in %(posted)s and is_cancelled = 0
        group by voucher_no, item_code
        """,
        {"posted": tuple(posted)},
        as_dict=True,
    ):
        out[(r.voucher_no, r.item_code)] = (flt(r.value), flt(r.qty))
    return out


def _cost(lines):
    """Give each line its cost (`cost`, company currency, negative on a return)
    and whether it is estimated, as ERPNext's Gross Profit report costs an
    invoice line: from the stock ledger of the invoice that posted it, a bundle
    from its components, a non-stock item at nothing, and at the valuation rate
    where nothing is posted yet."""
    codes = {ln.item_code for ln in lines}
    bundles = _bundles(codes)
    parts = {c for b in bundles.values() for c, _q in b}
    info = _item_info(codes | parts)
    ledger = _ledger({ln.posted for ln in lines if ln.posted})
    rates = {}
    stock_codes = [c for c in (codes | parts) if cint((info.get(c) or {}).get("is_stock_item"))]
    if stock_codes:
        for b in frappe.get_all("Bin", filters={"item_code": ["in", stock_codes]},
                                fields=["item_code", "warehouse", "valuation_rate"], limit_page_length=0):
            rates[(b.item_code, b.warehouse)] = flt(b.valuation_rate)

    def unit(code, posted, warehouse):
        if posted and (posted, code) in ledger:
            value, qty = ledger[(posted, code)]
            if qty:
                return value / qty, False
        return rates.get((code, warehouse)) or flt((info.get(code) or {}).get("valuation_rate")), True

    for ln in lines:
        qty = flt(ln.stock_qty) or flt(ln.qty)
        cost, estimated = 0.0, False
        if ln.item_code in bundles:
            for code, per in bundles[ln.item_code]:
                if cint((info.get(code) or {}).get("is_stock_item")):
                    u, e = unit(code, ln.posted, ln.warehouse)
                    cost += qty * per * u
                    estimated = estimated or e
        elif cint((info.get(ln.item_code) or {}).get("is_stock_item")):
            u, estimated = unit(ln.item_code, ln.posted, ln.warehouse)
            cost = qty * u
        ln.cost = cost
        ln.estimated = estimated
    return info


def _grouped(lines, key, label, with_cost):
    """Lines added up by `key(line)`: quantity sold and returned, net sales and,
    with the cost, the gross profit and margin."""
    by = {}
    for ln in lines:
        k = key(ln)
        if k is None:
            continue
        row = by.setdefault(k, {"key": k, "label": label(ln), "sold": 0.0, "returned": 0.0, "net": 0.0, "cost": 0.0})
        qty = flt(ln.qty)
        if cint(ln.is_return):
            row["returned"] += -qty
        else:
            row["sold"] += qty
        row["net"] += flt(ln.base_net_amount)
        if with_cost:
            row["cost"] += flt(ln.cost)
    out = []
    for row in by.values():
        row["qty"] = row["sold"] - row["returned"]
        for f in ("sold", "returned", "qty"):
            row[f] = flt(row[f], 3)
        row["net"] = flt(row["net"], 2)
        if with_cost:
            row["cost"] = flt(row["cost"], 2)
            row["profit"] = flt(row["net"] - row["cost"], 2)
            row["margin"] = flt(row["profit"] / row["net"] * 100, 1) if row["net"] else None
        else:
            del row["cost"]
        out.append(row)
    out.sort(key=lambda r: (-r["net"], str(r["label"])))
    return out


@frappe.whitelist()
def products(from_date: str | None = None, to_date: str | None = None, pos_profile: str | None = None,
             company: str | None = None, outlet: str | None = None):
    """What sold over a period: by item, item group, brand, the item a variant
    belongs to, and each variant attribute's values. Net sales before tax; the
    cost, gross profit and margin too for whoever may see the profit."""
    if not can_see_sales_reports():
        frappe.throw(_("You're not allowed to see the sales reports."), frappe.PermissionError)
    start, end, outlets, company, ccy = _context(from_date, to_date, pos_profile, company, outlet)
    lines = _lines(outlets, start, end)
    with_cost = can_see_profit()
    info = _cost(lines) if with_cost else _item_info({ln.item_code for ln in lines})

    items = _grouped(lines, lambda ln: ln.item_code, lambda ln: ln.item_name or ln.item_code, with_cost)
    meta = {}
    for ln in lines:
        meta.setdefault(ln.item_code, (ln.item_group or "", ln.brand or ""))
    for row in items:
        row["item_group"], row["brand"] = meta.get(row["key"], ("", ""))

    templates_of = {c: (info.get(c) or {}).get("variant_of") for c in meta}
    names = {}
    wanted = {t for t in templates_of.values() if t}
    if wanted:
        names = {r.name: r.item_name for r in frappe.get_all("Item", filters={"name": ["in", list(wanted)]},
                                                              fields=["name", "item_name"])}
    templates = _grouped(lines, lambda ln: templates_of.get(ln.item_code) or None,
                         lambda ln: names.get(templates_of.get(ln.item_code)) or templates_of.get(ln.item_code), with_cost)

    attributes = []
    variants = [c for c, t in templates_of.items() if t]
    if variants:
        values = {}
        for r in frappe.get_all("Item Variant Attribute", filters={"parent": ["in", variants], "parenttype": "Item"},
                                fields=["parent", "attribute", "attribute_value"], limit_page_length=0):
            values.setdefault(r.attribute, {})[r.parent] = r.attribute_value
        for attribute in sorted(values):
            of = values[attribute]
            rows = _grouped(lines, lambda ln, of=of: of.get(ln.item_code), lambda ln, of=of: of.get(ln.item_code), with_cost)
            attributes.append({"attribute": attribute, "values": rows})

    return {
        "from_date": str(start), "to_date": str(end), "company": company, "currency": ccy, "outlets": outlets,
        "with_profit": with_cost,
        "items_total": len(items),
        "items": items[:200],
        "groups": _grouped(lines, lambda ln: ln.item_group or "", lambda ln: ln.item_group or "", with_cost),
        "brands": _grouped(lines, lambda ln: ln.brand or "", lambda ln: ln.brand or "", with_cost),
        "templates": templates,
        "attributes": attributes,
    }


@frappe.whitelist()
def profit(from_date: str | None = None, to_date: str | None = None, pos_profile: str | None = None,
           company: str | None = None, outlet: str | None = None):
    """Net sales, the cost of the goods sold, the gross profit and the margin
    over a period, day by day and by item group, with the most and the least
    profitable items. How much of the cost is estimated (shifts not closed yet)
    is said apart."""
    if not can_see_profit():
        frappe.throw(_("You're not allowed to see the profit."), frappe.PermissionError)
    start, end, outlets, company, ccy = _context(from_date, to_date, pos_profile, company, outlet)
    lines = _lines(outlets, start, end)
    _cost(lines)
    net = sum(flt(ln.base_net_amount) for ln in lines)
    cost = sum(flt(ln.cost) for ln in lines)
    estimated = sum(flt(ln.cost) for ln in lines if ln.estimated)
    totals = {
        "net": flt(net, 2), "cost": flt(cost, 2), "profit": flt(net - cost, 2),
        "margin": flt((net - cost) / net * 100, 1) if net else None,
        "estimated_cost": flt(estimated, 2),
        "estimated_lines": sum(1 for ln in lines if ln.estimated),
    }
    days = _grouped(lines, lambda ln: str(ln.posting_date), lambda ln: str(ln.posting_date), True)
    days.sort(key=lambda r: r["key"])
    items = _grouped(lines, lambda ln: ln.item_code, lambda ln: ln.item_name or ln.item_code, True)
    sold = [r for r in items if r["net"] > 0]
    return {
        "from_date": str(start), "to_date": str(end), "company": company, "currency": ccy, "outlets": outlets,
        "totals": totals,
        "days": days,
        "groups": sorted(_grouped(lines, lambda ln: ln.item_group or "", lambda ln: ln.item_group or "", True),
                         key=lambda r: -r["profit"]),
        "best": sorted(sold, key=lambda r: -r["profit"])[:10],
        "lowest_margin": sorted(sold, key=lambda r: (r["margin"] if r["margin"] is not None else 0))[:10],
    }


# ---------------------------------------------------------------------------
# Phase 3: customers and outlets
# ---------------------------------------------------------------------------


def _walk_ins(outlets):
    """The customers that stand for "no customer": each outlet's own default
    customer, and the walk-in of every other currency (lumenpos.currency names
    them "Walk-in <currency>")."""
    out = {c for c in frappe.get_all("POS Profile", filters={"name": ["in", list(outlets) or [""]]}, pluck="customer") if c}
    out |= set(frappe.get_all("Customer", filters={"customer_name": ["like", "Walk-in %"]}, pluck="name"))
    return out


@frappe.whitelist()
def customers(from_date: str | None = None, to_date: str | None = None, pos_profile: str | None = None,
              company: str | None = None, outlet: str | None = None):
    """Who bought over a period: how many named customers, how many came back,
    how many are new, the average basket and how often they buy, the best and
    the most recent ones, and what walk-in sales came to beside them."""
    if not can_see_sales_reports():
        frappe.throw(_("You're not allowed to see the sales reports."), frappe.PermissionError)
    start, end, outlets, company, ccy = _context(from_date, to_date, pos_profile, company, outlet)
    invoices = _invoices(outlets, start, end)
    walk = _walk_ins(outlets)
    named = [i for i in invoices if i.customer and i.customer not in walk]
    anon = [i for i in invoices if not i.customer or i.customer in walk]

    by = {}
    for inv in named:
        row = by.setdefault(inv.customer, {"customer": inv.customer, "sales": 0, "returns": 0, "total": 0.0, "last": ""})
        total = flt(inv.base_rounded_total) or flt(inv.base_grand_total)
        row["total"] += total
        if cint(inv.is_return):
            row["returns"] += 1
        else:
            row["sales"] += 1
        # A real date and time, written with its leading zeros: posting_time comes
        # back as a timedelta ("9:57:38"), and as text 9:57 sorted after 10:03, so
        # a customer of the morning headed the recent list all day (0.66.0).
        when = _sale_moment(inv.posting_date, inv.posting_time)
        if when > row["last"]:
            row["last"] = when
    names = {}
    created = {}
    if by:
        for c in frappe.get_all("Customer", filters={"name": ["in", list(by)]}, fields=["name", "customer_name", "creation"],
                                limit_page_length=0):
            names[c.name] = c.customer_name or c.name
            created[c.name] = getdate(c.creation)
    rows = []
    for key, row in by.items():
        row["name"] = names.get(key, key)
        row["total"] = flt(row["total"], 2)
        row["new"] = bool(created.get(key) and start <= created[key] <= end)
        rows.append(row)

    sales_named = [i for i in named if not cint(i.is_return)]
    total_named = sum(flt(i.base_rounded_total) or flt(i.base_grand_total) for i in sales_named)
    count = len(rows)
    totals = {
        "customers": count,
        "repeat": sum(1 for r in rows if r["sales"] >= 2),
        "new": sum(1 for r in rows if r["new"]),
        "average_basket": flt(total_named / len(sales_named), 2) if sales_named else 0.0,
        "frequency": flt(len(sales_named) / count, 2) if count else 0.0,
        "named_total": flt(sum(r["total"] for r in rows), 2),
        "walk_in_sales": sum(1 for i in anon if not cint(i.is_return)),
        "walk_in_total": flt(sum(flt(i.base_rounded_total) or flt(i.base_grand_total) for i in anon), 2),
    }
    totals["repeat_rate"] = flt(totals["repeat"] / count * 100, 1) if count else 0.0
    return {
        "from_date": str(start), "to_date": str(end), "company": company, "currency": ccy, "outlets": outlets,
        "totals": totals,
        "top": sorted(rows, key=lambda r: (-r["total"], r["name"]))[:20],
        "repeat": sorted([r for r in rows if r["sales"] >= 2], key=lambda r: (-r["sales"], -r["total"]))[:20],
        "recent": sorted(rows, key=lambda r: r["last"], reverse=True)[:10],
    }


@frappe.whitelist()
def outlets(from_date: str | None = None, to_date: str | None = None, pos_profile: str | None = None,
            company: str | None = None, outlet: str | None = None):
    """Each outlet over a period (lumenpos.outlets, 0.64.0: the registers that
    sell from one warehouse, or carry one outlet name, are one outlet): its
    sales, returns, average sale and items sold, its shifts and their over and
    short, the stock in its warehouses and how many items there are at or below
    their reorder level, its best selling items, and each of its registers with
    its own sales and shifts."""
    if not can_see_sales_reports():
        frappe.throw(_("You're not allowed to see the sales reports."), frappe.PermissionError)
    start, end, chosen, company, ccy = _context(from_date, to_date, pos_profile, company, outlet)
    from lumenpos import outlets as outlet_groups

    invoices = _invoices(chosen, start, end)
    lines = _lines(chosen, start, end)
    shifts = _shifts(chosen, start, end)
    discounts = _line_discounts(invoices)
    out = []
    for group in outlet_groups.for_registers(chosen):
        registers = [r for r in group["registers"] if r in chosen]
        mine = [i for i in invoices if i.pos_profile in registers]
        f = _figures(mine, discounts)
        stock = 0.0
        low = 0
        for warehouse in group["warehouses"]:
            stock += flt(frappe.db.sql(
                "select coalesce(sum(actual_qty), 0) from `tabBin` where warehouse = %s", (warehouse,))[0][0])
            low += cint(frappe.db.sql(
                """
                select count(*) from `tabItem Reorder` r
                join `tabBin` b on b.item_code = r.parent and b.warehouse = r.warehouse
                where r.parenttype = 'Item' and r.warehouse = %s and b.actual_qty <= r.warehouse_reorder_level
                """,
                (warehouse,),
            )[0][0])
        own = [s for s in shifts if s["pos_profile"] in registers]
        names = {i.name for i in mine}
        top = _grouped([ln for ln in lines if ln.invoice in names], lambda ln: ln.item_code,
                       lambda ln: ln.item_name or ln.item_code, False)[:5]
        tills = []
        for register in registers:
            theirs = [i for i in mine if i.pos_profile == register]
            g = _figures(theirs, discounts)
            shifts_here = [s for s in own if s["pos_profile"] == register]
            tills.append({
                "pos_profile": register, "sales": g["sales"], "returns": g["returns"], "total": g["total"],
                "shifts": len(shifts_here), "open_shifts": sum(1 for s in shifts_here if s["status"] == "Open"),
                "differences": _differences(shifts_here, ccy),
            })
        tills.sort(key=lambda r: (-r["total"], r["pos_profile"]))
        out.append({
            "outlet": group["outlet"], "name": group["name"], "warehouses": group["warehouses"],
            "pos_profile": registers[0] if len(registers) == 1 else None,
            "warehouse": ", ".join(group["warehouses"]),
            "sales": f["sales"], "returns": f["returns"], "net": f["net"], "total": f["total"],
            "average_sale": f["average_sale"], "items_sold": f["items_sold"], "discounts": f["discounts"],
            "shifts": len(own), "open_shifts": sum(1 for s in own if s["status"] == "Open"),
            "differences": _differences(own, ccy),
            "stock": flt(stock, 3), "low_stock": low, "top": top, "registers": tills,
        })
    out.sort(key=lambda r: (-r["total"], r["name"]))
    return {
        "from_date": str(start), "to_date": str(end), "company": company, "currency": ccy, "outlets": chosen,
        "rows": out,
    }
