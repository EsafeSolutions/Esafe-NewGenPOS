"""Pure manual-discount arithmetic, mirrored by frontend/src/discounts.js."""
import math


def positive(value):
    try:
        number = float(value or 0)
        return max(0.0, number) if math.isfinite(number) else 0.0
    except (TypeError, ValueError):
        return 0.0


def discount_breakdown(lines, promo, bundles, order, factor=1, rounding=round):
    """Direct item discounts are per unit; all typed amounts use sale currency."""
    whole = [positive(promo["line_discounts"][i]) + float(bundles[i] or 0)
             for i in range(len(lines))]
    eligible = [i for i, line in enumerate(lines) if not line.get("bundle_key")]
    bases = [max(0.0, line["price"] * line["qty"] - whole[i])
             for i, line in enumerate(lines)]
    total = sum(bases[i] for i in eligible)
    basket = min(total, positive(promo.get("basket_discount")))
    if basket > 0 and total > 0:
        spread = 0.0
        for i in eligible:
            share = rounding(basket * bases[i] / total, 2)
            whole[i] += share
            spread += share
        biggest = max(eligible, key=lambda i: bases[i])
        whole[biggest] += rounding(basket - spread, 2)
    manual, manual_percent = [], []
    for i, line in enumerate(lines):
        base = max(0.0, line["price"] * line["qty"] - whole[i])
        if line.get("bundle_key"):
            amount = 0.0
        elif line.get("manual_discount_method") == "amount":
            amount = min(base, positive(line.get("manual_discount_amount")) / factor * line["qty"])
        else:
            amount = base * min(100.0, positive(line.get("manual_discount_percent"))) / 100.0
        manual.append(amount)
        manual_percent.append(amount / base * 100.0 if base > 0 else 0.0)
    order_base = sum(max(0.0, lines[i]["price"] * lines[i]["qty"] - whole[i] - manual[i])
                     for i in eligible)
    order_total = 0.0
    if order.get("enabled"):
        if order.get("method") == "amount":
            order_total = min(order_base, positive(order.get("amount")) / factor)
        else:
            order_total = order_base * min(100.0, positive(order.get("percent"))) / 100.0
    order_percent = order_total / order_base * 100.0 if order_base > 0 else 0.0
    per_unit = []
    for i, line in enumerate(lines):
        base = max(0.0, line["price"] * line["qty"] - whole[i] - manual[i])
        extra = 0.0 if line.get("bundle_key") else base * order_percent / 100.0
        per_unit.append((whole[i] + manual[i] + extra) / (line["qty"] or 1))
    return dict(whole=whole, manual=manual, manual_percent=manual_percent,
                order_base=order_base, order_total=order_total,
                order_percent=order_percent, per_unit=per_unit)
