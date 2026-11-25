"""Validate the physical denomination breakdown independently of Frappe."""
import json
import math
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP


def decimal_number(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Enter a valid cash count.")
    if not number.is_finite():
        raise ValueError("Enter a finite cash count.")
    return number


def clean_payment_counts(counted, expected):
    """A blank count is unknown, never an implicit zero or a balanced drawer."""
    if not isinstance(counted, dict):
        raise ValueError("Enter the counted amounts for each payment method.")
    required = {row["mode_of_payment"] for row in expected}
    cash = {row["mode_of_payment"] for row in expected if row.get("is_cash")}
    if required - set(counted):
        raise ValueError("Enter every counted amount. Use 0 for an empty payment total.")
    result = {}
    for mode, value in counted.items():
        if isinstance(value, bool) or value is None or value == "":
            raise ValueError("Enter every counted amount. Use 0 for an empty payment total.")
        number = decimal_number(value)
        amount = float(number)
        if not math.isfinite(amount) or (mode in cash and amount < 0):
            raise ValueError("Enter a finite counted amount; cash cannot be negative.")
        result[mode] = amount
    return result


def clean_counts(raw, counted, cash_currencies):
    """Custom denominations allow any currency; bank/card counts cannot use them.

    Values are in the drawer's own currency. Keep note and coin quantities
    separately, even where both have the same face value.
    """
    if isinstance(raw, str):
        raw = json.loads(raw or "{}")
    if not isinstance(raw or {}, dict) or len(raw or {}) > 50:
        raise ValueError("Invalid denomination breakdown.")
    result = {}
    for mode, entry in (raw or {}).items():
        if mode not in cash_currencies or entry.get("currency") != cash_currencies[mode]:
            raise ValueError("Count notes and coins in the cash drawer's currency.")
        rows = entry.get("rows")
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError("Invalid denomination breakdown.")
        total, cleaned, seen = Decimal(0), [], set()
        for row in rows:
            value = decimal_number(row.get("value"))
            qty = decimal_number(row.get("quantity"))
            kind = row.get("kind")
            key = (kind, value)
            if kind not in ("notes", "coins") or value <= 0 or value > 1000000000 or value.as_tuple().exponent < -3:
                raise ValueError("Enter a positive denomination with up to three decimal places.")
            if qty < 0 or qty > 10000000 or qty != qty.to_integral_value() or key in seen:
                raise ValueError("Enter each denomination once with a whole, non-negative quantity.")
            seen.add(key)
            total += value * qty
            cleaned.append({"kind": kind, "value": float(value), "quantity": int(qty)})
        total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if mode not in counted or total != decimal_number(counted[mode]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP):
            raise ValueError("The note and coin total must match the counted cash.")
        result[mode] = {"currency": entry["currency"], "rows": cleaned, "total": float(total)}
    return result


def allocate_count(amount, expected, allow_negative=False):
    """Allocate a shared physical count without inventing negative cash counts.

    The original invoices remain on each cashier's shift. Count allocation is
    proportional to positive expected takings, with an exact cent remainder.
    """
    amount = decimal_number(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    original = [decimal_number(value) for value in expected]
    # Store credit and refund tenders may legitimately be negative. Preserve
    # each member's signed expected balance, allocating only the difference.
    if allow_negative:
        differences = allocate_count(amount - sum(original), [abs(v) for v in original])
        return [float(value + decimal_number(delta)) for value, delta in zip(original, differences)]
    weights = [max(Decimal(0), value) for value in original]
    weight = sum(weights)
    if not weights:
        return []
    if not weight:
        return [float(amount)] + [0.0] * (len(weights) - 1)
    parts = [(amount * value / weight).quantize(Decimal("0.01"), rounding=ROUND_DOWN) for value in weights]
    # Put the rounding remainder on the largest share (never on a zero share).
    index = weights.index(max(weights))
    parts[index] += amount - sum(parts)
    return [float(value) for value in parts]
