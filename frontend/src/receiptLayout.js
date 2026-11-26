// Physical roll, Windows page and printable width are distinct measurements.
export function receiptRollWidth(source) { return source?.classList.contains('paper-58') ? 58 : 80 }
// Common thermal heads are narrower than the physical roll. Full-width
// layouts remain available as an explicit, calibrated workstation setting.
export function safeReceiptWidth(roll) { return roll === 58 ? 48 : 72 }
export function validateReceiptLayout(value = {}, roll = 80) {
  const paperWidth = value.paperWidth ?? safeReceiptWidth(roll)
  const printableWidth = value.printableWidth ?? paperWidth
  const inset = value.inset ?? 3
  if (![58, 80].includes(roll) || ![paperWidth, printableWidth, inset].every((n) => typeof n === 'number' && Number.isFinite(n))) throw new Error('Use valid receipt measurements in millimetres.')
  if (paperWidth < 10 || paperWidth > roll || printableWidth < 10 || printableWidth > paperWidth) throw new Error('Printable width must fit the Windows paper width and physical roll.')
  if (inset < 0 || inset > 10) throw new Error('Choose an inset from 0 to 10 mm.')
  if (value.margins !== undefined && (!value.margins || typeof value.margins !== 'object' || Array.isArray(value.margins))) throw new Error('Use valid receipt margins in millimetres.')
  // Older workstation records used one inset for all four sides.
  const margins = Object.fromEntries(['top', 'right', 'bottom', 'left'].map((side) => [side, value.margins?.[side] ?? inset]))
  if (!Object.values(margins).every((n) => typeof n === 'number' && Number.isFinite(n) && n >= 0 && n <= 20)) throw new Error('Use margins from 0 to 20 mm.')
  if (printableWidth - margins.left - margins.right < 10) throw new Error('Left and right margins must leave at least 10 mm for receipt content.')
  return { paperWidth, printableWidth, margins }
}
export function receiptLayoutFor(source, binding = {}) {
  const roll = receiptRollWidth(source)
  return validateReceiptLayout(binding.receiptLayout?.[roll], roll)
}
export function receiptHtmlOptions(document, copies = 1) {
  return { copies, size: { width: document.width, height: document.height }, margins: 0, orientation: 'portrait', scale: 'fit' }
}
