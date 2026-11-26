// Structured display settings only; no arbitrary HTML, CSS or transaction changes.
export const DESIGN_RANGES = {
  "fontSize": [
    9,
    16,
    "px"
  ],
  "totalSize": [
    12,
    24,
    "px"
  ],
  "lineHeight": [
    1,
    2,
    ""
  ],
  "paddingTop": [
    0,
    10,
    "mm"
  ],
  "paddingRight": [
    0,
    10,
    "mm"
  ],
  "paddingBottom": [
    0,
    10,
    "mm"
  ],
  "paddingLeft": [
    0,
    10,
    "mm"
  ],
  "sectionGap": [
    0,
    10,
    "mm"
  ],
  "itemPadding": [
    0,
    3,
    "mm"
  ],
  "logoHeight": [
    16,
    100,
    "px"
  ],
  "barcodeHeight": [
    20,
    80,
    "px"
  ],
  "borderWidth": [
    0,
    2,
    "px"
  ]
}
export const DESIGN_ALIGNMENTS = ["headerAlign","footerAlign","itemAlign","labelAlign","valueAlign"]
export function cleanReceiptDesign(input = {}) {
  if (typeof input === 'string') input = JSON.parse(input || '{}')
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('Invalid receipt design.')
  const result = {}
  for (const [key, value] of Object.entries(input)) {
    if (DESIGN_ALIGNMENTS.includes(key)) {
      if (!['left', 'center', 'right'].includes(value)) throw new Error('Choose a valid receipt alignment.')
    } else {
      const range = DESIGN_RANGES[key]
      if (!range || typeof value !== 'number' || !Number.isFinite(value) || value < range[0] || value > range[1]) throw new Error('Receipt design value is outside its allowed range: ' + key)
    }
    result[key] = value
  }
  return result
}
export function receiptDesignStyle(input) {
  try { return Object.fromEntries(Object.entries(cleanReceiptDesign(input)).map(([key, value]) => ['--rc-' + key, String(value) + (DESIGN_RANGES[key]?.[2] || '')])) }
  catch { return {} }
}
