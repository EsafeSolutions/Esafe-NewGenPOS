// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
// "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
// Build frontend/src/locales/<code>.js from <work>/<code>_ui_part*.json, after
// checking every text keeps its {placeholders} and marks and carries no dash
// or semicolon. Usage: node write_locale.mjs <work> <code> "<English name>" [--dry]
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = fileURLToPath(new URL('../../', import.meta.url))
const OUT = join(ROOT, 'frontend', 'src', 'locales')
const [work, code, englishName] = process.argv.slice(2)
const dry = process.argv.includes('--dry')
if (!work || !code || !englishName) throw new Error('usage: node write_locale.mjs <work> <code> "<English name>"')

const rows = JSON.parse(readFileSync(join(work, 'ui_strings.json'), 'utf8'))
const done = {}
for (const f of readdirSync(work).filter((n) => n.startsWith(`${code}_ui_part`) && n.endsWith('.json'))) {
  Object.assign(done, JSON.parse(readFileSync(join(work, f), 'utf8')))
}
const ph = (s) => (s.match(/\{[a-zA-Z_0-9]+\}/g) || []).sort().join('|')
// Em and en dash, and every semicolon (Latin, Arabic, full width), written as
// escapes so this file carries none of them.
const FORBIDDEN = /[\u2014\u2013;\u061B\uFF1B]/
const problems = []
const dict = {}
for (const r of rows) {
  const tr = done[r.id]
  if (typeof tr !== 'string' || !tr.trim()) {
    problems.push(`${r.id} missing (${r.key.slice(0, 50)})`)
    continue
  }
  if (ph(tr) !== ph(r.en)) problems.push(`${r.id} placeholders ${ph(r.en)} -> ${ph(tr)}`)
  if (FORBIDDEN.test(tr) && !FORBIDDEN.test(r.en)) problems.push(`${r.id} dash or semicolon`)
  if (r.en.endsWith('…') !== tr.endsWith('…')) problems.push(`${r.id} ellipsis differs`)
  if (/^\+ /.test(r.en) !== /^\+ /.test(tr)) problems.push(`${r.id} leading + differs`)
  if (/ \*$/.test(r.en) !== / \*$/.test(tr)) problems.push(`${r.id} required star differs`)
  dict[r.key] = tr
}
console.log(code, 'keys', rows.length, 'translated', Object.keys(done).length, 'problems', problems.length)
for (const p of problems.slice(0, 40)) console.log('  ' + p)
if (problems.length || dry) process.exit(problems.length ? 1 : 0)

const body = Object.entries(dict)
  .map(([k, v]) => `  ${JSON.stringify(k)}: ${JSON.stringify(v)},`)
  .join('\n')
const file = `// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
// "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
// ${englishName} for the till, keyed by the English source string like the
// Arabic in messages.js. Loaded only when a cashier picks ${englishName}
// (i18n.js). A missing key falls back to English. Built by
// scripts/i18n/write_locale.mjs, fix a text there and in its source part.
export default {
${body}
}
`
mkdirSync(OUT, { recursive: true })
writeFileSync(join(OUT, `${code}.js`), file)
console.log('wrote', join(OUT, `${code}.js`), Object.keys(dict).length, 'keys')
