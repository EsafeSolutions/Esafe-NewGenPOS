// Fit checks use geometry only; no receipt text is retained in diagnostics.
const MIN_FONT = 9
const TOLERANCE = 1.5
function horizontalSpace(element, win) {
  const style = win.getComputedStyle(element)
  return ['paddingLeft', 'paddingRight', 'borderLeftWidth', 'borderRightWidth'].reduce((sum, name) => sum + (Number.parseFloat(style[name]) || 0), 0)
}
function textWidth(element, doc) {
  const range = doc.createRange()
  range.selectNodeContents(element)
  return range.getBoundingClientRect().width
}
function numericSpace(element, win) {
  const own = element.getBoundingClientRect().width - horizontalSpace(element, win)
  if (!element.matches('.row > :last-child, .retail-savings strong')) return own
  const parent = element.parentElement
  return Math.min(own, (parent.getBoundingClientRect().width - horizontalSpace(parent, win)) * 0.8)
}
export function fitReceiptContent(root) {
  const doc = root.ownerDocument, win = doc.defaultView
  let adjusted = 0, unsafe = false
  // Keep a shared amount column, with room remaining for the labels. A huge
  // amount must not expand the grid beyond the receipt's printable width.
  for (const grid of root.querySelectorAll('.tpl-table .retail-totals, .tpl-table .retail-loyalty')) {
    const cells = [...grid.querySelectorAll('.row > :last-child')]
    if (!cells.length) continue
    const available = grid.getBoundingClientRect().width - horizontalSpace(grid, win)
    const needed = Math.max(...cells.map(cell => textWidth(cell, doc) + horizontalSpace(cell, win)))
    grid.style.gridTemplateColumns = `minmax(0, 1fr) ${Math.min(needed + 1, available * 0.6)}px`
    // Keep common labels on a readable line on narrow paper, even when an
    // oversized body/total font was chosen in the advanced editor.
    for (const label of grid.querySelectorAll('.row > :first-child')) {
      const previous = label.style.whiteSpace
      label.style.whiteSpace = 'nowrap'
      const available = label.getBoundingClientRect().width - horizontalSpace(label, win)
      const required = textWidth(label, doc), current = Number.parseFloat(win.getComputedStyle(label).fontSize)
      if (required > available + TOLERANCE && current > MIN_FONT) {
        label.style.fontSize = `${Math.max(MIN_FONT, Math.floor(current * Math.max(0, available) / required * 98) / 100)}px`
        adjusted++
      }
      label.style.whiteSpace = previous
    }
  }
  // Preserve whole monetary values; reduce only overflowing numeric text,
  // never truncate it, split its digits or scale the entire receipt bitmap.
  for (const element of root.querySelectorAll('.retail-item-values td, .row > :last-child, .retail-savings strong')) {
    if (!element.textContent.trim()) continue
    for (let attempt = 0; attempt < 3; attempt++) {
      const available = numericSpace(element, win)
      const width = textWidth(element, doc)
      if (width <= available + TOLERANCE) break
      const current = Number.parseFloat(win.getComputedStyle(element).fontSize)
      const next = Math.max(MIN_FONT, Math.floor(current * Math.max(0, available) / width * 98) / 100)
      if (next >= current || current <= MIN_FONT) break
      element.style.fontSize = `${next}px`
      adjusted++
    }
    if (textWidth(element, doc) > numericSpace(element, win) + TOLERANCE) unsafe = true
  }
  const box = root.getBoundingClientRect(), style = win.getComputedStyle(root)
  const left = box.left + Number.parseFloat(style.paddingLeft), right = box.right - Number.parseFloat(style.paddingRight)
  const walker = doc.createTreeWalker(root, win.NodeFilter.SHOW_TEXT)
  let node, overflow = unsafe
  while ((node = walker.nextNode())) {
    if (!node.textContent.trim() || node.parentElement.closest('svg,style,script')) continue
    const range = doc.createRange(); range.selectNodeContents(node)
    for (const rect of range.getClientRects()) {
      if (rect.width && (rect.left < left - TOLERANCE || rect.right > right + TOLERANCE)) overflow = true
    }
  }
  for (const element of root.querySelectorAll('table, th, td, .row, .row > *, img, svg')) {
    const rect = element.getBoundingClientRect()
    if (rect.width && (rect.left < left - TOLERANCE || rect.right > right + TOLERANCE)) overflow = true
  }
  if (overflow) throw new Error('Receipt content does not fit the printable width. Reduce receipt font size or design padding, or adjust printer widths and margins in Printing → Printers. No print job was sent.')
  return { adjusted, contentWidthPx: right - left }
}
