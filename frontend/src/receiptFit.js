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
  if (element.matches('.retail-quantity')) return element.parentElement.getBoundingClientRect().width - horizontalSpace(element.parentElement, win)
  const own = element.getBoundingClientRect().width - horizontalSpace(element, win)
  if (!element.matches('.row > :last-child, .retail-savings strong')) return own
  const parent = element.parentElement
  return Math.min(own, (parent.getBoundingClientRect().width - horizontalSpace(parent, win)) * 0.8)
}
function fitItemColumns(root, doc, win) {
  let reflowed = 0
  for (const table of root.querySelectorAll('.retail-items')) {
    const headers = [...table.querySelectorAll('thead th')], rows = [...table.querySelectorAll('.retail-item-values')]
    if (!headers.length || !rows.length) continue
    const available = table.getBoundingClientRect().width - 2
    const minimum = headers.map((header, index) => {
      const cells = index === 0 ? [...table.querySelectorAll('tbody .retail-no')] : rows.map(row => row.children[index]).filter(Boolean)
      const headerFont = Number.parseFloat(win.getComputedStyle(header).fontSize)
      const headerMinimum = textWidth(header, doc) * Math.min(1, MIN_FONT / headerFont) + horizontalSpace(header, win) + 2
      return Math.max(10, headerMinimum, ...cells.map(cell => {
        const value = cell.querySelector('.retail-quantity') || cell
        const font = Number.parseFloat(win.getComputedStyle(value).fontSize)
        return textWidth(value, doc) * Math.min(1, MIN_FONT / font) + horizontalSpace(cell, win) + 2
      }))
    })
    const sum = minimum.reduce((total, width) => total + width, 0)
    if (sum <= available) {
      const extra = headers.map((header, index) => Math.max(0, header.getBoundingClientRect().width - minimum[index]))
      const total = extra.reduce((value, width) => value + width, 0)
      headers.forEach((header, index) => header.style.setProperty('width', `${minimum[index] + (available - sum) * (total ? extra[index] / total : 1 / headers.length)}px`, 'important'))
      continue
    }
    // Readable monetary values take priority over keeping a five-column grid.
    // Retain every field, with its translated heading, inside the item row.
    table.querySelector('thead').style.display = 'none'
    for (const row of rows) {
      const cells = [...row.children], details = doc.createElement('td')
      details.colSpan = headers.length; details.className = 'receipt-item-details'
      cells.slice(1).forEach((cell, offset) => {
        const line = doc.createElement('div'), label = doc.createElement('span'), value = doc.createElement('span')
        line.className = 'receipt-item-detail'; label.textContent = headers[offset + 1].textContent
        if (!cell.matches('.retail-item-qty')) value.className = 'receipt-item-money'
        for (const node of cell.childNodes) value.appendChild(node.cloneNode(true))
        line.append(label, value); details.appendChild(line)
      })
      row.replaceChildren(details); reflowed++
    }
  }
  return reflowed
}
export function fitReceiptContent(root) {
  const doc = root.ownerDocument, win = doc.defaultView
  let adjusted = 0, unsafe = false
  const itemRowsReflowed = fitItemColumns(root, doc, win)
  for (const heading of root.querySelectorAll('.receipt-company')) {
    const previous = heading.style.whiteSpace
    heading.style.whiteSpace = 'nowrap'
    const available = heading.getBoundingClientRect().width - horizontalSpace(heading, win)
    const required = textWidth(heading, doc), current = Number.parseFloat(win.getComputedStyle(heading).fontSize)
    if (required > available + TOLERANCE) {
      const size = Math.max(12, Math.floor(current * available / required * 98) / 100)
      heading.style.fontSize = `${size}px`; adjusted++
    }
    if (textWidth(heading, doc) > available + TOLERANCE) heading.style.whiteSpace = previous
  }
  for (const label of root.querySelectorAll('.retail-meta-row > :first-child')) {
    const previous = label.style.whiteSpace
    label.style.whiteSpace = 'nowrap'
    const available = label.getBoundingClientRect().width - horizontalSpace(label, win)
    const required = textWidth(label, doc), current = Number.parseFloat(win.getComputedStyle(label).fontSize)
    if (required > available + TOLERANCE) { label.style.fontSize = `${Math.max(MIN_FONT, Math.floor(current * available / required * 98) / 100)}px`; adjusted++ }
    label.style.whiteSpace = previous
  }
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
  for (const element of root.querySelectorAll('.retail-item-values td:not(.retail-item-qty):not(.receipt-item-details), .retail-quantity, .receipt-item-money, .row > :last-child, .retail-savings strong')) {
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
  return { adjusted, itemRowsReflowed, contentWidthPx: right - left }
}
