// Physical roll, Windows page and printable width are distinct measurements.
export function receiptRollWidth(source) { return source?.classList.contains('paper-58') ? 58 : 80 }
export function validateReceiptLayout(value = {}, roll = 80) {
  const paperWidth = value.paperWidth ?? roll
  const printableWidth = value.printableWidth ?? paperWidth
  const inset = value.inset ?? 3
  if (![58, 80].includes(roll) || ![paperWidth, printableWidth, inset].every((n) => typeof n === 'number' && Number.isFinite(n))) throw new Error('Use valid receipt measurements in millimetres.')
  if (paperWidth < 10 || paperWidth > roll || printableWidth < 10 || printableWidth > paperWidth) throw new Error('Printable width must fit the Windows paper width and physical roll.')
  if (inset < 0 || inset > 10 || printableWidth - inset * 2 < 10) throw new Error('Choose an inset from 0 to 10 mm that leaves room for receipt content.')
  return { paperWidth, printableWidth, inset }
}
export function receiptLayoutFor(source, binding = {}) {
  const roll = receiptRollWidth(source)
  return validateReceiptLayout(binding.receiptLayout?.[roll], roll)
}
export function receiptHtmlOptions(document, copies = 1) {
  return { copies, size: { width: document.width, height: document.height }, margins: 0, orientation: 'portrait', scale: 'fit' }
}
