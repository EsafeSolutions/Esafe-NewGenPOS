// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
// "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
//
// Barcodes for printed labels (0.67.0), drawn as SVG with no library: EAN-13,
// UPC-A (an EAN-13 with a leading 0) and Code 128 (sets B and C). `encode` gives
// the bars as a string of modules ("1" a bar, "0" a space), quiet zones not
// included; `svg` draws it. Checked by frontend/barcode-check.mjs, and by
// decoding real prints in the browser test.

const EAN_L = ['0001101', '0011001', '0010011', '0111101', '0100011', '0110001', '0101111', '0111011', '0110111', '0001011']
const EAN_G = ['0100111', '0110011', '0011011', '0100001', '0011101', '0111001', '0000101', '0010001', '0001001', '0010111']
const EAN_R = ['1110010', '1100110', '1101100', '1000010', '1011100', '1001110', '1010000', '1000100', '1001000', '1110100']
// Which of L or G each of the six left digits takes, by the first digit.
const EAN_PARITY = ['LLLLLL', 'LLGLGG', 'LLGGLG', 'LLGGGL', 'LGLLGG', 'LGGLLG', 'LGGGLL', 'LGLGLG', 'LGLGGL', 'LGGLGL']

// Code 128 patterns, values 0 to 106 (106 = stop, 13 modules with its bar).
const C128 = [
  '11011001100', '11001101100', '11001100110', '10010011000', '10010001100', '10001001100', '10011001000', '10011000100',
  '10001100100', '11001001000', '11001000100', '11000100100', '10110011100', '10011011100', '10011001110', '10111001100',
  '10011101100', '10011100110', '11001110010', '11001011100', '11001001110', '11011100100', '11001110100', '11101101110',
  '11101001100', '11100101100', '11100100110', '11101100100', '11100110100', '11100110010', '11011011000', '11011000110',
  '11000110110', '10100011000', '10001011000', '10001000110', '10110001000', '10001101000', '10001100010', '11010001000',
  '11000101000', '11000100010', '10110111000', '10110001110', '10001101110', '10111011000', '10111000110', '10001110110',
  '11101110110', '11010001110', '11000101110', '11011101000', '11011100010', '11011101110', '11101011000', '11101000110',
  '11100010110', '11101101000', '11101100010', '11100011010', '11101111010', '11001000010', '11110001010', '10100110000',
  '10100001100', '10010110000', '10010000110', '10000101100', '10000100110', '10110010000', '10110000100', '10011010000',
  '10011000010', '10000110100', '10000110010', '11000010010', '11001010000', '11110111010', '11000010100', '10001111010',
  '10100111100', '10010111100', '10010011110', '10111100100', '10011110100', '10011110010', '11110100100', '11110010100',
  '11110010010', '11011011110', '11011110110', '11110110110', '10101111000', '10100011110', '10001011110', '10111101000',
  '10111100010', '11110101000', '11110100010', '10111011110', '10111101110', '11101011110', '11110101110', '11010000100',
  '11010010000', '11010011100', '1100011101011',
]
const START_B = 104
const START_C = 105
const CODE_B = 100
const CODE_C = 99

export function eanCheckDigit(twelve) {
  let sum = 0
  for (let i = 0; i < 12; i++) sum += Number(twelve[i]) * (i % 2 ? 3 : 1)
  return String((10 - (sum % 10)) % 10)
}

// The format a code is printed in: EAN-13 for 13 digits with a right check
// digit (or 12, the check digit added), UPC-A for 12 with a right check digit,
// else Code 128 for printable ASCII, else null (the label shows no bars).
export function formatOf(code) {
  const s = String(code || '').trim()
  if (/^\d{13}$/.test(s) && eanCheckDigit(s.slice(0, 12)) === s[12]) return 'EAN13'
  if (/^\d{12}$/.test(s) && eanCheckDigit('0' + s.slice(0, 11)) === s[11]) return 'UPCA'
  if (s && /^[\x20-\x7e]+$/.test(s) && s.length <= 48) return 'CODE128'
  return null
}

function ean13Modules(thirteen) {
  const parity = EAN_PARITY[Number(thirteen[0])]
  let out = '101'
  for (let i = 1; i <= 6; i++) out += (parity[i - 1] === 'L' ? EAN_L : EAN_G)[Number(thirteen[i])]
  out += '01010'
  for (let i = 7; i <= 12; i++) out += EAN_R[Number(thirteen[i])]
  return out + '101'
}

// Code 128 values for a text: set C over even runs of 4 or more digits (or a
// whole all-digit text of even length), set B elsewhere.
function code128Values(text) {
  const values = []
  let set = null
  let i = 0
  const digitRun = (from) => {
    let j = from
    while (j < text.length && text[j] >= '0' && text[j] <= '9') j++
    return j - from
  }
  while (i < text.length) {
    const run = digitRun(i)
    const useC = run >= 4 || (run === text.length && run >= 2 && run % 2 === 0)
    if (useC) {
      const pairs = Math.floor(run / 2)
      if (set !== 'C') {
        values.push(set === null ? START_C : CODE_C)
        set = 'C'
      }
      for (let p = 0; p < pairs; p++) {
        values.push(Number(text.slice(i, i + 2)))
        i += 2
      }
      continue
    }
    if (set !== 'B') {
      values.push(set === null ? START_B : CODE_B)
      set = 'B'
    }
    values.push(text.charCodeAt(i) - 32)
    i++
  }
  let sum = values[0]
  for (let k = 1; k < values.length; k++) sum += values[k] * k
  values.push(sum % 103)
  values.push(106)
  return values
}

export function encode(code) {
  const s = String(code || '').trim()
  const format = formatOf(s)
  if (format === 'EAN13') return { format, modules: ean13Modules(s), text: s }
  if (format === 'UPCA') return { format, modules: ean13Modules('0' + s), text: s }
  if (format === 'CODE128') return { format, modules: code128Values(s).map((v) => C128[v]).join(''), text: s }
  return { format: null, modules: '', text: s }
}

// The bars as SVG, `height` in the SVG's own units, `module` the width of one
// module. Quiet zones of 10 modules each side. The digits under the bars are the
// label's business (they need its font), so they are not drawn here.
export function svg(code, { height = 40, module = 1, color = '#000' } = {}) {
  const { modules } = encode(code)
  if (!modules) return ''
  const quiet = 10
  const width = (modules.length + 2 * quiet) * module
  let rects = ''
  let x = 0
  while (x < modules.length) {
    if (modules[x] === '1') {
      let w = 1
      while (modules[x + w] === '1') w++
      rects += `<rect x="${(quiet + x) * module}" y="0" width="${w * module}" height="${height}"/>`
      x += w
    } else {
      x++
    }
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" shape-rendering="crispEdges"><g fill="${color}">${rects}</g></svg>`
}

// GS1 in-store / variable-measure prefixes (EAN-13 20-29, 02)
export const DEFAULT_SCALE_PREFIXES = ['20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '02']

// Parse weight-embedded scale barcodes (EAN-13 / UPC-A).
// Returns { isScaleBarcode: true, prefix, plu, weight, candidates, checkDigit } or null.
export function parseScaleBarcode(code, { prefixes = DEFAULT_SCALE_PREFIXES, pluLen = 5, decimals = 3 } = {}) {
  let raw = String(code || '').trim()
  if (!raw || !/^\d+$/.test(raw)) return null

  // 12-digit UPC-A: if starting with '2', normalize to 13 digits with leading '0'
  if (raw.length === 12) {
    if (raw.startsWith('2')) raw = '0' + raw
    else return null
  }

  if (raw.length !== 13) return null

  const allowed = new Set(
    (Array.isArray(prefixes) ? prefixes : String(prefixes).split(','))
      .map((p) => String(p).trim())
      .filter(Boolean)
  )

  const prefix = raw.slice(0, 2)
  if (!allowed.has(prefix)) return null

  const pLen = pluLen === 4 ? 4 : 5
  const dec = decimals == null || decimals < 0 ? 3 : Number(decimals)

  const plu = raw.slice(2, 2 + pLen)
  const rawWeight = raw.slice(2 + pLen, 12)
  const checkDigit = raw[12]

  const weightInt = Number(rawWeight)
  if (!weightInt || weightInt <= 0 || !Number.isFinite(weightInt)) return null

  const weight = Math.round((weightInt / (10 ** dec)) * 10000) / 10000

  const candidates = []
  const addCand = (val) => {
    const s = String(val || '').trim()
    if (s && !candidates.includes(s)) candidates.push(s)
  }

  addCand(prefix + plu)
  addCand(plu)
  const stripped = plu.replace(/^0+/, '')
  if (stripped) addCand(stripped)

  if (pLen === 5) {
    const plu4 = raw.slice(2, 6)
    addCand(prefix + plu4)
    addCand(plu4)
    const stripped4 = plu4.replace(/^0+/, '')
    if (stripped4) addCand(stripped4)
    addCand(`${prefix}${plu}000000`)
  }

  return {
    isScaleBarcode: true,
    prefix,
    plu,
    weight,
    candidates,
    checkDigit,
  }
}

