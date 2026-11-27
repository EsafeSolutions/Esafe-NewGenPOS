"""Pure, company-currency B2B allocation and cheque rules (Python 3.7+)."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import isfinite


def number(value, label="amount", positive=False):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Enter a valid {0}.".format(label))
    if not result.is_finite() or not isfinite(float(result)) or result < 0 or (positive and result == 0):
        raise ValueError("Enter a valid {0}.".format(label))
    return result


def money(value, precision=2):
    return number(value).quantize(Decimal(10) ** -precision, rounding=ROUND_HALF_UP)


def line_discount(rate, method, value):
    """Return native per-unit discount fields; amount means per selling unit."""
    rate, value = number(rate, "rate"), number(value, "line discount")
    if method not in ("Percent", "Amount"):
        raise ValueError("Choose a percentage or amount discount.")
    if (method == "Percent" and value > 100) or (method == "Amount" and value > rate):
        raise ValueError("The line discount cannot exceed its rate.")
    discount = rate * value / 100 if method == "Percent" else value
    return {"rate": float(rate - discount), "discount_amount": float(discount),
            "discount_percentage": float(discount / rate * 100) if rate else 0.0}


def allocate(invoices, amount, selections=None, allow_advance=False, precision=2):
    """Allocate in caller's oldest-first order, with optional exact row amounts.

    A supplied selection must still be open. Pending cheques use this preview
    without reserving balances; clearance must call it again on locked rows.
    """
    amount = money(amount, precision)
    if amount <= 0:
        raise ValueError("Enter a positive payment amount.")
    selections = selections or []
    names = [row.get("name") for row in selections]
    if any(not name for name in names) or len(names) != len(set(names)):
        raise ValueError("Choose each invoice only once.")
    by_name = {row["name"]: row for row in invoices}
    if set(names) - set(by_name):
        raise ValueError("An invoice is no longer open. Refresh its balance.")
    selected = {row["name"]: row for row in selections}
    chosen = [row for row in invoices if not selections or row["name"] in selected]
    if len({(row.get("currency"), row.get("debit_to")) for row in chosen}) > 1:
        raise ValueError("Settle invoices with the same currency and receivable account together.")
    remaining, references = amount, []
    for row in chosen:
        outstanding = money(row["outstanding_amount"], precision)
        requested = selected.get(row["name"], {}).get("amount")
        take = min(outstanding, remaining) if requested in (None, "") else money(requested, precision)
        if take > outstanding or take > remaining:
            raise ValueError("The allocation exceeds the invoice balance or payment amount.")
        if take > 0:
            references.append({"reference_doctype": "Sales Invoice", "reference_name": row["name"],
                               "allocated_amount": float(take)})
            remaining -= take
    if remaining > 0 and not allow_advance:
        raise ValueError("Review the allocations or explicitly keep the excess as a customer advance.")
    return references, float(remaining)


CHEQUE_TRANSITIONS = {
    "Received": {"deposit": "Deposited", "bounce": "Bounced", "return": "Returned", "cancel": "Cancelled"},
    "Deposited": {"clear": "Cleared", "bounce": "Bounced", "return": "Returned"},
    "Cleared": {"bounce": "Bounced"},
}


def cheque_transition(state, action):
    target = CHEQUE_TRANSITIONS.get(state, {}).get(action)
    if not target:
        raise ValueError("This action is not valid for a {0} cheque. Refresh its status.".format(state.lower()))
    return target


def progress(documents, outstanding, pending_cheques=0):
    """A connected document graph, never unrelated customer stage counts."""
    grouped = {kind: [row for row in documents if row.get("doctype") == kind and row.get("docstatus") != 2]
               for kind in ("Quotation", "Sales Order", "Delivery Note", "Sales Invoice")}
    submitted = lambda kind: [row for row in grouped[kind] if row.get("docstatus") == 1]
    invoices, orders, deliveries = submitted("Sales Invoice"), submitted("Sales Order"), submitted("Delivery Note")
    stages = []
    for kind in ("Quotation", "Sales Order", "Delivery Note", "Sales Invoice"):
        rows = grouped[kind]
        state = "Complete" if submitted(kind) else ("Draft" if rows else "Not started")
        if kind in ("Quotation", "Sales Order") and not rows and (invoices or orders or deliveries):
            state = "Skipped"
        if kind == "Delivery Note":
            if orders:
                state = "Complete" if all(float(row.get("per_delivered") or 0) >= 99.999 for row in orders) else "In progress"
            elif invoices and all(row.get("update_stock") or not row.get("has_stock_items") for row in invoices):
                state = "Complete" if any(row.get("has_stock_items") for row in invoices) else "Skipped"
            elif deliveries:
                state = "Complete"
            if orders and not any(row.get("has_stock_items") for row in orders):
                state = "Skipped"
        if kind == "Sales Invoice" and (orders or deliveries):
            sources = deliveries or orders
            if not all(float(row.get("per_billed") or 0) >= 99.999 for row in sources):
                state = "In progress" if invoices else "Not started"
        stages.append({"doctype": kind, "state": state, "count": len(rows)})
    paid = bool(invoices) and float(outstanding) <= 0.00001 and not pending_cheques
    stages.append({"doctype": "Payment", "state": "Complete" if paid else ("In progress" if invoices or pending_cheques else "Not started"),
                   "count": 0})
    applicable = [row for row in stages if row["state"] != "Skipped"]
    percent = round(100 * sum(row["state"] == "Complete" for row in applicable) / len(applicable))
    return {"stages": stages, "percent": percent, "complete": percent == 100}
