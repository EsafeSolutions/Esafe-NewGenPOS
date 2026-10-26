// Copyright (c) 2026 Lumen Solutions
// SPDX-License-Identifier: AGPL-3.0-only
// "LumenPOS" is a trademark of Lumen Solutions. See TRADEMARKS.md.
//
// Printed labels (0.67.0): the sizes a shop picks from and the page the browser
// prints, sized in millimetres so a label printer or an A4 sheet gets exactly
// what was chosen. The same page feeds the preview.
import { svg } from './barcode'

// A roll prints one label per page; a sheet places columns x rows on A4 with
// the gaps that make the label edges meet the sheet's die-cut.
export const PRESETS = [
  { key: '50x25', label: 'Label roll 50 x 25 mm', w: 50, h: 25 },
  { key: '40x30', label: 'Label roll 40 x 30 mm', w: 40, h: 30 },
  { key: '58x40', label: 'Label roll 58 x 40 mm', w: 58, h: 40 },
  { key: '38x25', label: 'Label roll 38 x 25 mm', w: 38, h: 25 },
  { key: 'a4-3x8', label: 'A4 sheet, 3 x 8 labels', w: 70, h: 37, cols: 3, rows: 8 },
  { key: 'a4-4x10', label: 'A4 sheet, 4 x 10 labels', w: 52.5, h: 29.7, cols: 4, rows: 10 },
  { key: 'custom', label: 'Custom size', w: 50, h: 30, custom: true },
]

export const FIELDS = ['shop', 'name', 'price', 'equivalent', 'barcode', 'code']

const esc = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])

// The size in use: a preset, or the custom one (kept within what any printer takes).
export function sizeOf(key, custom = {}) {
  const preset = PRESETS.find((p) => p.key === key) || PRESETS[0]
  if (!preset.custom) return preset
  const clamp = (v, lo, hi, d) => (Number.isFinite(+v) && +v > 0 ? Math.min(hi, Math.max(lo, +v)) : d)
  return { ...preset, w: clamp(custom.w, 20, 120, 50), h: clamp(custom.h, 15, 120, 30), cols: 0, rows: 0 }
}

// One label's HTML. `row` comes from lumenpos.api.labels (item_name, barcode,
// item_code, price text...), `show` says which fields print.
export function labelHtml(row, show, size) {
  const code = row.barcode || row.item_code
  const bars = show.barcode ? svg(code, { height: 40 }) : ''
  const nameSize = Math.max(2.2, Math.min(4, size.h * 0.11))
  const priceSize = Math.max(3, Math.min(8, size.h * 0.2))
  return `<div class="lbl">
${show.shop && row.shop ? `<div class="shop" dir="auto">${esc(row.shop)}</div>` : ''}
${show.name ? `<div class="name" dir="auto" style="font-size:${nameSize}mm">${esc(row.item_name)}</div>` : ''}
${show.price ? `<div class="price" dir="ltr" style="font-size:${priceSize}mm">${esc(row.price_text)}</div>` : ''}
${show.equivalent && row.equivalent_text ? `<div class="eq" dir="ltr">${esc(row.equivalent_text)}</div>` : ''}
${bars ? `<div class="bars">${bars}</div><div class="digits" dir="ltr">${esc(code)}</div>` : ''}
${show.code && !(bars && code === row.item_code) ? `<div class="code" dir="ltr">${esc(row.item_code)}</div>` : ''}
</div>`
}

// The whole page: every label as many times as asked, on rolls one per page,
// on sheets in a grid. `rows` carry `qty`.
export function pageHtml(rows, show, size, { title = 'Labels', rtl = false } = {}) {
  const labels = []
  for (const row of rows) for (let i = 0; i < Math.max(0, Math.floor(+row.qty || 0)); i++) labels.push(labelHtml(row, show, size))
  const sheet = size.cols > 0
  const page = sheet ? '@page { size: A4; margin: 0 }' : `@page { size: ${size.w}mm ${size.h}mm; margin: 0 }`
  // A4 is 210 x 297: the grid is centred, the margins are what is left over.
  const mx = sheet ? Math.max(0, (210 - size.cols * size.w) / 2) : 0
  const my = sheet ? Math.max(0, (297 - size.rows * size.h) / 2) : 0
  const body = sheet
    ? chunk(labels, size.cols * size.rows).map((part) => `<div class="sheet">${part.join('')}</div>`).join('')
    : labels.map((l) => `<div class="roll">${l}</div>`).join('')
  return `<!doctype html><html dir="${rtl ? 'rtl' : 'ltr'}"><head><meta charset="utf-8"><title>${esc(title)}</title><style>
${page}
* { box-sizing: border-box; margin: 0; padding: 0 }
html, body { background: #fff; color: #000; font-family: Arial, 'Segoe UI', Tahoma, 'Noto Sans Arabic', sans-serif }
.roll { width: ${size.w}mm; height: ${size.h}mm; overflow: hidden; page-break-after: always; break-after: page }
.sheet { width: 210mm; height: 297mm; padding: ${my}mm ${mx}mm; display: grid; grid-template-columns: repeat(${size.cols || 1}, ${size.w}mm); grid-auto-rows: ${size.h}mm; page-break-after: always; break-after: page; overflow: hidden }
.lbl { width: ${size.w}mm; height: ${size.h}mm; padding: 1.2mm 1.6mm; display: flex; flex-direction: column; align-items: center; justify-content: space-between; text-align: center; overflow: hidden }
.shop { font-size: 2mm; line-height: 1.1; opacity: .8; max-width: 100%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis }
.name { font-weight: 600; line-height: 1.15; max-width: 100%; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical }
.price { font-weight: 800; line-height: 1.05 }
.eq { font-size: 2.3mm; line-height: 1.1 }
.bars { width: 100%; flex: 1 1 auto; min-height: 5mm; max-height: ${Math.max(6, size.h * 0.38)}mm; display: flex }
.bars svg { width: 100%; height: 100% }
.digits, .code { font-size: 2.1mm; line-height: 1.1; letter-spacing: .2mm }
@media screen { body { background: #f2f4f7 } .roll, .sheet { background: #fff; margin: 6px auto; box-shadow: 0 1px 4px rgba(0,0,0,.18) } }
</style></head><body>${body}</body></html>`
}

function chunk(list, n) {
  const out = []
  for (let i = 0; i < list.length; i += n) out.push(list.slice(i, i + n))
  return out
}
