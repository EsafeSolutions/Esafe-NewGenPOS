export const RECEIPT_BRAND = 'ESAFE ERP+POS - pos.esafe.lk | +94 7777 567 52'
const LEGACY_RECEIPT_BRAND = 'ESAFE ERP+POS - pos.esafe.lk'

export function receiptFooter(customFooter = '') {
  const text = customFooter.trim()
  const customLines = text
    ? text.split(/\r\n?|\n/).filter((line) => ![RECEIPT_BRAND, LEGACY_RECEIPT_BRAND].includes(line.trim()))
    : []
  return [...customLines, RECEIPT_BRAND].join('\n')
}

export const RECEIPT_OPTION_DEFAULTS = {
  "receipt_show_line_discount": 1,
  "receipt_show_mrp": 1,
  "receipt_show_gross_total": 1,
  "receipt_show_total_discount": 1,
  "receipt_show_savings": 1,
  "receipt_show_item_count": 1,
  "receipt_show_total_qty": 1,
  "receipt_show_loyalty": 1,
  "receipt_show_cashier": 1,
  "receipt_show_terminal": 1,
  "receipt_show_customer": 1,
  "receipt_show_datetime": 1,
  "receipt_show_header_text": 1,
  "receipt_show_phone": 1,
  "receipt_show_footer": 1,
  "receipt_show_custom_fields": 1,
  "receipt_show_taxes": 1,
  "receipt_show_change": 1
}
export function receiptOptionEnabled(settings, field) { const value=settings[field] ?? RECEIPT_OPTION_DEFAULTS[field] ?? 1; return ![0,false,"0","false","",null].includes(value) }
