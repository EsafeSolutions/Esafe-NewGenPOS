export const RECEIPT_BRAND = 'ESAFE ERP+POS - pos.esafe.lk | +94 7777 567 52'
const LEGACY_RECEIPT_BRAND = 'ESAFE ERP+POS - pos.esafe.lk'

export function receiptFooter(customFooter = '') {
  const text = customFooter.trim()
  const customLines = text
    ? text.split(/\r\n?|\n/).filter((line) => ![RECEIPT_BRAND, LEGACY_RECEIPT_BRAND].includes(line.trim()))
    : []
  return [...customLines, RECEIPT_BRAND].join('\n')
}
