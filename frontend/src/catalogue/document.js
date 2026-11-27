// One paginated document shared by preview, browser printing and PDF export.
export const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c])
const FONT = 'Arial, Nirmala UI, Iskoola Pota, Tahoma, sans-serif'
let context
function width(text, size, bold = false) {
  context ||= document.createElement('canvas').getContext('2d')
  context.font = `${bold ? 'bold ' : ''}${size * 96 / 25.4}px ${FONT}`
  return context.measureText(text).width * 25.4 / 96
}
function lines(text, available, size, bold = false) {
  const result = []
  for (const paragraph of String(text || '').split('\n')) {
    let line = ''
    for (const word of paragraph.split(/\s+/).filter(Boolean)) {
      if (line && width(line + ' ' + word, size, bold) > available) { result.push(line); line = '' }
      if (width(word, size, bold) <= available) line += (line ? ' ' : '') + word
      else for (const char of (Intl.Segmenter ? [...new Intl.Segmenter(undefined, { granularity: 'grapheme' }).segment(word)].map(part => part.segment) : [...word])) {
        if (line && width(line + char, size, bold) > available) { result.push(line); line = '' }
        line += char
      }
    }
    result.push(line)
  }
  return result
}
const text = (x, y, value, size = 3.2, bold = false, anchor = 'start', color = '#172324') => `<text x="${x}" y="${y}" font-size="${size}" font-weight="${bold ? 700 : 400}" text-anchor="${anchor}" fill="${color}">${esc(value)}</text>`
export function groupItems(items, order = 'category-brand') {
  const first = order === 'brand-category' ? 'brand' : 'category', second = first === 'brand' ? 'category' : 'brand'
  const value = (row, field) => row[field] || (field === 'brand' ? 'Unbranded' : 'Uncategorised')
  const sorted = [...items].sort((a, b) => value(a, first).localeCompare(value(b, first)) || value(a, second).localeCompare(value(b, second)) || a.item_name.localeCompare(b.item_name) || a.item_code.localeCompare(b.item_code))
  const groups = []
  for (const item of sorted) {
    const title = value(item, first) + ' / ' + value(item, second)
    const key = JSON.stringify([value(item, first), value(item, second)])
    if (groups.at(-1)?.key !== key) groups.push({ key, title, items: [] })
    groups.at(-1).items.push(item)
  }
  return groups
}
export function cataloguePages(items, meta, options, images = {}) {
  const pageW = options.paper === 'Letter' ? 215.9 : 210, pageH = options.paper === 'Letter' ? 279.4 : 297
  const margin = 13, right = pageW - margin, bottom = pageH - 16, available = pageW - margin * 2
  let digits = 2
  try { digits = new Intl.NumberFormat('en', { style: 'currency', currency: meta.currency }).resolvedOptions().maximumFractionDigits } catch { /* ERPNext permits custom currency codes. */ }
  const money = value => `${meta.currency} ${new Intl.NumberFormat('en', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value)}`
  const pages = []; let body = '', y = 0, pageStart = 0, groupTitle = ''
  function page() {
    if (body) pages.push(body)
    body = `<rect width="${pageW}" height="${pageH}" fill="white"/>`
    y = 18
    for (const line of lines(options.title || (options.mode === 'menu' ? 'Menu' : 'Product catalogue'), available, 6, true)) { body += text(margin, y, line, 6, true); y += 7 }
    const company = lines(meta.company, available * 0.65, 3.5), outlet = lines(meta.outlet, available * 0.3, 3)
    company.forEach((line, i) => { body += text(margin, y + i * 4.5, line, 3.5) })
    outlet.forEach((line, i) => { body += text(right, y + i * 4.5, line, 3, false, 'end') })
    y += Math.max(company.length, outlet.length) * 4.5 + 2
    for (const line of lines(`${meta.price_list} · ${meta.generated_at}`, available, 2.8)) { body += text(margin, y, line, 2.8, false, 'start', '#526365'); y += 4 }
    if (meta.price_note) for (const line of lines(meta.price_note, available, 2.6)) { body += text(margin, y, line, 2.6, false, 'start', '#526365'); y += 3.5 }
    body += `<path d="M${margin} ${y}H${right}" stroke="#172324" stroke-width="0.4"/>`
    y += 7
    pageStart = y
  }
  function heading(continued = false) {
    for (const line of lines(groupTitle + (continued ? ' (continued)' : ''), available, 4.2, true)) { body += text(margin, y, line, 4.2, true); y += 5.5 }
    y += 2
  }
  page()
  for (const group of groupItems(items, options.grouping)) {
    groupTitle = group.title
    const headingHeight = lines(groupTitle, available, 4.2, true).length * 5.5 + 5
    const first = group.items[0], firstWidth = available - (options.images ? 39 : 0)
    const firstHeader = Math.max(lines(first.item_name, firstWidth - 48, 3.8, true).length * 4.6 + lines(`${first.item_code} · ${first.uom}`, firstWidth - 48, 2.6).length * 3.4 + 6, 18)
    const firstDescription = options.descriptions ? lines(first.description, firstWidth, 3.1).length : 1
    const firstOffers = options.discounts ? lines((first.offers || []).join(' · '), firstWidth, 2.8).length : 0
    const firstImage = options.images ? (options.mode === 'menu' ? 22 : 32) : 0
    const firstHeight = Math.max(firstHeader + (firstDescription + firstOffers) * 4.2 + 3, firstImage + 5) + 7
    const reserve = firstHeight <= bottom - pageStart - headingHeight ? firstHeight : Math.max(firstHeader + 8, firstImage + 4)
    if (y + headingHeight + reserve > bottom) page()
    heading()
    for (const item of group.items) {
      let pending = options.descriptions ? lines(item.description, available - (options.images ? 39 : 0), 3.1) : []
      if (!pending.length) pending = ['']
      const offers = options.discounts ? lines((item.offers || []).join(' · '), available - (options.images ? 39 : 0), 2.8) : []
      pending.push(...offers.map(value => ({ offer: value })))
      const nameWidth = available - (options.images ? 39 : 0) - 48
      const names = lines(item.item_name, nameWidth, 3.8, true)
      let continued = false
      do {
        const imageW = options.images && !continued ? (options.mode === 'menu' ? 22 : 32) : 0
        const left = margin + (options.images ? 39 : 0)
        const unit = `${item.item_code} · ${item.uom}${continued ? ' · continued' : ''}`
        const codeLines = lines(unit, nameWidth, 2.6)
        const headerHeight = Math.max(names.length * 4.6 + codeLines.length * 3.4 + 6, 18)
        const rowMinimum = Math.max(headerHeight + 8, imageW + 4)
        const wholeHeight = Math.max(headerHeight + pending.length * 4.2 + 3, imageW + 5) + 7
        const freshRoom = bottom - pageStart - (lines(groupTitle + ' (continued)', available, 4.2, true).length * 5.5 + 2)
        // A normal item stays intact. Only descriptions longer than a whole
        // fresh page are split; a one-line offer must not orphan on page two.
        if (y + rowMinimum > bottom || (!continued && wholeHeight <= freshRoom && y + wholeHeight > bottom)) { page(); heading(true) }
        const start = y
        if (imageW) {
          const url = images[item.item_code]
          if (url) body += `<image x="${margin}" y="${start}" width="${imageW}" height="${imageW}" preserveAspectRatio="xMidYMid meet" href="${esc(url)}"/>`
          else body += `<rect x="${margin}" y="${start}" width="${imageW}" height="${imageW}" fill="#f0f4f3"/>` + text(margin + imageW / 2, start + imageW / 2, 'No image', 2.5, false, 'middle', '#526365')
        }
        names.forEach((name, i) => { body += text(left, y + 4 + i * 4.6, name, 3.8, true) })
        // Long codes are wrapped too; never clip an identifier at the edge.
        codeLines.forEach((line, i) => { body += text(left, y + names.length * 4.6 + 4 + i * 3.4, line, 2.6, false, 'start', '#526365') })
        body += text(right, y + 5, item.unpriced ? 'Price on request' : money(item.price), 3.7, true, 'end')
        if (options.discounts && !item.unpriced && item.regular_price > item.price && money(item.regular_price) !== money(item.price)) {
          const original = money(item.regular_price)
          body += `<g text-decoration="line-through">${text(right, y + 10.5, original, 2.8, false, 'end', '#667575')}</g>`
          const percent = new Intl.NumberFormat('en', { maximumFractionDigits: 1 }).format((1 - item.price / item.regular_price) * 100)
          body += text(right, y + 15, Number(percent) ? `${percent}% off` : `Save ${money(item.regular_price - item.price)}`, 2.8, true, 'end', '#006b60')
        }
        y += headerHeight
        while (pending.length && y + 4.2 <= bottom - 3) {
          const line = pending.shift(), offer = typeof line === 'object'
          body += text(left, y, offer ? line.offer : line, offer ? 2.8 : 3.1, false, 'start', offer ? '#006b60' : '#34484a')
          y += 4.2
        }
        y = Math.max(y + 3, start + imageW + 5)
        body += `<path d="M${margin} ${y}H${right}" stroke="#cbd5d3" stroke-width="0.25"/>`
        y += 7
        continued = true
        if (pending.length) { page(); heading(true) }
      } while (pending.length)
    }
    y += 4
  }
  pages.push(body)
  return { width: pageW, height: pageH, pages: pages.map((content, i) => `<svg xmlns="http://www.w3.org/2000/svg" width="${pageW}mm" height="${pageH}mm" viewBox="0 0 ${pageW} ${pageH}" font-family="${FONT}">${content}<path d="M${margin} ${pageH - 12}H${right}" stroke="#cbd5d3" stroke-width="0.25"/>${text(margin, pageH - 7, `${items.length} items · Unit prices · Offers subject to conditions`, 2.5, false, 'start', '#526365')}${text(right, pageH - 7, `${i + 1} / ${pages.length}`, 2.5, false, 'end', '#526365')}</svg>`) }
}
