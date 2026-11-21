// Manual discounts follow promotions; direct item amounts are per unit in
// the sale currency. Keep in sync with esafepos/api/discounts.py.
export function discountBreakdown(lines, promo, bundles, order, factor = 1, round = (n) => Math.round((n + Number.EPSILON) * 100) / 100) {
  const positive = (n) => Number.isFinite(Number(n)) ? Math.max(0, Number(n)) : 0
  const pct = (n) => Math.min(100, positive(n))
  const whole = lines.map((l, i) => (promo.line_discounts[i] || 0) + (bundles[i] || 0))
  const eligible = lines.map((l, i) => i).filter((i) => !lines[i].bundle_key)
  const bases = lines.map((l, i) => Math.max(0, l.price * l.qty - whole[i]))
  const total = eligible.reduce((sum, i) => sum + bases[i], 0)
  const basket = Math.min(total, positive(promo.basket_discount))
  if (basket > 0 && total > 0) {
    let spread = 0
    for (const i of eligible) {
      const share = round(basket * bases[i] / total)
      whole[i] += share
      spread += share
    }
    const biggest = eligible.reduce((a, b) => bases[a] >= bases[b] ? a : b)
    whole[biggest] += round(basket - spread)
  }
  const manualPercent = lines.map(() => 0)
  const manual = lines.map((l, i) => {
    if (l.bundle_key) return 0
    const base = Math.max(0, l.price * l.qty - whole[i])
    const amount = l.manual_discount_method === 'amount'
      ? Math.min(base, positive(l.manual_discount_amount) / factor * l.qty)
      : base * pct(l.manual_discount_percent) / 100
    manualPercent[i] = base > 0 ? amount / base * 100 : 0
    return amount
  })
  // A direct bundle discount is per complete bundle, never per kg/component.
  const groups = new Map()
  lines.forEach((line, i) => {
    if (line.bundle_key) {
      if (!groups.has(line.bundle_key)) groups.set(line.bundle_key, [])
      groups.get(line.bundle_key).push(i)
    }
  })
  for (const indexes of groups.values()) {
    const first = lines[indexes[0]]
    const base = indexes.reduce((sum, i) => sum + bases[i], 0)
    const amount = first.bundle_discount_method === 'amount'
      ? Math.min(base, positive(first.bundle_discount_amount) / factor * (positive(first.bundle_qty) || 1))
      : base * pct(first.bundle_discount_percent) / 100
    for (const i of indexes) {
      manual[i] = base > 0 ? amount * bases[i] / base : 0
      manualPercent[i] = base > 0 ? amount / base * 100 : 0
    }
  }
  const orderBase = eligible.reduce((sum, i) => sum + Math.max(0, lines[i].price * lines[i].qty - whole[i] - manual[i]), 0)
  const orderTotal = order.enabled ? (order.method === 'amount'
    ? Math.min(orderBase, positive(order.amount) / factor)
    : orderBase * pct(order.percent) / 100) : 0
  const orderPercent = orderBase > 0 ? orderTotal / orderBase * 100 : 0
  const perUnit = lines.map((l, i) => {
    const base = Math.max(0, l.price * l.qty - whole[i] - manual[i])
    return (whole[i] + manual[i] + (l.bundle_key ? 0 : base * orderPercent / 100)) / (l.qty || 1)
  })
  return { whole, manual, manualPercent, orderBase, orderTotal, orderPercent, perUnit }
}
