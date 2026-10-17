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

Who may see what: "See sales reports" and "See cashier performance" in Who can
do what, nobody but a manager until a shop names someone, and the whole of it
can be switched off (LumenPOS Settings, Sales reports in Insights).
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
            select name, %(doctype)s as doctype, owner, pos_profile, posting_date, posting_time,
                   is_return, total_qty, base_net_total, base_discount_amount,
                   base_total_taxes_and_charges, base_grand_total, base_rounded_total,
                   base_change_amount, account_for_change_amount
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
    or off the first cash method when no method holds that account."""
    result = {}
    for doctype, names in _by_doctype(invoices).items():
        rows = frappe.db.sql(  # nosemgrep
            """
            select mode_of_payment, sum(base_amount) as amount
            from `tabSales Invoice Payment`
            where parenttype = %(doctype)s and parent in %(names)s
            group by mode_of_payment
            """,
            {"doctype": doctype, "names": tuple(names)},
            as_dict=True,
        )
        for r in rows:
            result[r.mode_of_payment] = flt(result.get(r.mode_of_payment)) + flt(r.amount)
    change = {}
    for inv in invoices:
        if flt(inv.base_change_amount):
            change[inv.account_for_change_amount] = flt(change.get(inv.account_for_change_amount)) + flt(inv.base_change_amount)
    if change:
        accounts = {}
        for mode in result:
            account = frappe.db.get_value("Mode of Payment Account", {"parent": mode, "company": company}, "default_account")
            if account:
                accounts.setdefault(account, mode)
        cash = [m for m in result if frappe.get_cached_value("Mode of Payment", m, "type") == "Cash"]
        for account, amount in change.items():
            target = accounts.get(account) or (cash[0] if cash else None)
            if target:
                result[target] = flt(result[target]) - amount
    return [{"mode_of_payment": m, "amount": flt(a, 2)} for m, a in sorted(result.items(), key=lambda kv: -kv[1])]


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


def _context(from_date, to_date, pos_profile, company):
    from lumenpos import currency

    start, end = _period(from_date, to_date)
    outlets, company = _outlets(pos_profile, company)
    return start, end, outlets, company, currency.company_currency(company)


@frappe.whitelist()
def sales_summary(from_date: str | None = None, to_date: str | None = None, pos_profile: str | None = None,
                  company: str | None = None):
    """Sales, returns, tax, payments and the cash counted at the close, over a
    period, for one outlet or every outlet of a company. Day by day over a
    longer period, hour by hour over one day."""
    if not can_see_sales_reports():
        frappe.throw(_("You're not allowed to see the sales reports."), frappe.PermissionError)
    start, end, outlets, company, ccy = _context(from_date, to_date, pos_profile, company)
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

    shifts = _shifts(outlets, start, end)
    names = _names({s["opened_by"] for s in shifts})
    for s in shifts:
        s["opened_by_name"] = names.get(s["opened_by"], s["opened_by"])
    return {
        "from_date": str(start), "to_date": str(end), "company": company, "currency": ccy,
        "outlets": outlets, "by": "hour" if one_day else "day",
        "totals": _figures(invoices, discounts),
        "payments": _payments(invoices, company),
        "series": series,
        "shifts": shifts,
        "differences": _differences(shifts, ccy),
    }


@frappe.whitelist()
def cashiers(from_date: str | None = None, to_date: str | None = None, pos_profile: str | None = None,
             company: str | None = None):
    """How each cashier did over a period: the sales and returns they rang up,
    what they gave off the list price, the price edits the audit log holds
    for them, their shifts and how far their counts were from what was
    expected."""
    if not can_see_cashier_report():
        frappe.throw(_("You're not allowed to see how each cashier did."), frappe.PermissionError)
    start, end, outlets, company, ccy = _context(from_date, to_date, pos_profile, company)
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
