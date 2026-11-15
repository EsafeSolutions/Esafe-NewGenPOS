export const RECEIPT_BRAND = 'ESAFE ERP+POS - pos.esafe.lk'

export function receiptFooter(customFooter = '') {
  const text = customFooter.trim()
  const customLines = text ? text.split(/\r\n?|\n/).filter((line) => line.trim() !== RECEIPT_BRAND) : []
  return [...customLines, RECEIPT_BRAND].join('\n')
}
