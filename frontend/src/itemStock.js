// Company-wide display quantities remain separate from register sale stock.
export function showsTotalStock(item, session) {
  return Boolean(session.settings?.enable_item_stock_totals && item.total_stock_qty != null &&
    item.total_stock_scope?.[0] === session.user && item.total_stock_scope?.[1] === session.posProfile &&
    item.total_stock_scope?.[2] === session.company)
}

export function displayedStock(item, session) {
  return showsTotalStock(item, session) ? item.total_stock_qty : item.actual_qty
}

export function applyStockLevel(item, quantity) {
  const next = Number(quantity) || 0
  if (item.total_stock_qty != null && item.total_stock_includes_register) {
    item.total_stock_qty = Number((Number(item.total_stock_qty) + next - (Number(item.actual_qty) || 0)).toFixed(9))
  }
  item.actual_qty = next
}
