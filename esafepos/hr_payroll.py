"""Pure monthly HR calculations. Native HR documents remain authoritative."""
import calendar
import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def number(value):
    try:
        result = Decimal(str(value or 0))
    except InvalidOperation:
        raise ValueError("Enter a valid amount.")
    if not result.is_finite():
        raise ValueError("Enter a finite amount.")
    return result


def monthly_period(value):
    try:
        if not re.match(r"^\d{4}-\d{2}$", str(value)):
            raise ValueError()
        year, month = map(int, str(value).split("-"))
        start = date(year, month, 1)
    except (ValueError, TypeError):
        raise ValueError("Select a payroll month (YYYY-MM).")
    return start, date(year, month, calendar.monthrange(year, month)[1])


def commission_earnings(invoices, people, precision=2):
    """Use ERPNext's stored incentives, including negative returns, exactly once."""
    by, seen = {}, set()
    for invoice in invoices:
        key = (invoice["doctype"], invoice["name"])
        if key in seen or invoice.get("is_consolidated") or invoice.get("docstatus") != 1:
            continue
        seen.add(key)
        team = invoice.get("sales_team") or []
        if team and abs(sum(number(row.get("allocated_percentage")) for row in team) - 100) > Decimal("0.01"):
            raise ValueError("Sales team allocation must total 100% on {0}.".format(invoice["name"]))
        for row in team:
            incentive = number(row.get("incentives"))
            if not incentive:
                continue
            employee = people.get(row["sales_person"])
            if not employee:
                raise ValueError("Link salesperson {0} to an Employee before preparing commissions.".format(row["sales_person"]))
            entry = by.setdefault(employee, {"amount": Decimal(0), "sources": []})
            entry["amount"] += incentive
            entry["sources"].append({"doctype": invoice["doctype"], "name": invoice["name"],
                                     "modified": str(invoice.get("modified") or ""), "is_return": invoice.get("is_return", 0),
                                     "sales_person": row["sales_person"], "allocated_percentage": float(number(row.get("allocated_percentage"))),
                                     "base_net_total": float(number(invoice.get("base_net_total"))), "incentives": float(incentive)})
    for entry in by.values():
        entry["amount"] = float(entry["amount"].quantize(Decimal(10) ** -precision, rounding=ROUND_HALF_UP))
    return by
