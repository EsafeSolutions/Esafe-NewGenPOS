// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
// "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
// Build lumenpos/translations/<code>.csv (Frappe's own format, read on v13 to
// v16) from <work>/<code>_server_part*.json, after checking every string.
// Rows for texts Frappe or ERPNext already translate (<work>/erp_keys_<code>.json,
// from erp_keys.py) are left out: Frappe merges every app's translations and
// the app installed last wins, so such a row would rename the text across the
// whole desk. Usage: node write_csv.mjs <work> <code> [--dry]
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = fileURLToPath(new URL('../../', import.meta.url))
const APP = join(ROOT, 'lumenpos', 'translations')
const [work, lang] = process.argv.slice(2)
const dry = process.argv.includes('--dry')
if (!work || !lang) throw new Error('usage: node write_csv.mjs <work> <code>')

const rows = JSON.parse(readFileSync(join(work, 'server_strings.json'), 'utf8'))
const done = {}
for (const f of readdirSync(work).filter((n) => n.startsWith(`${lang}_server_part`) && n.endsWith('.json'))) {
  Object.assign(done, JSON.parse(readFileSync(join(work, f), 'utf8')))
}

const placeholders = (s) => (s.match(/\{[a-z_0-9]*\}|%\([a-z_]+\)s|%s|%d/gi) || []).sort().join('|')
const tags = (s) => (s.match(/<\/?[a-z][^>]*>/gi) || []).map((t) => t.toLowerCase()).sort().join('|')
// Arabic diacritics and tatweel, em and en dash, and every semicolon (Latin,
// Arabic, full width), written as escapes so this file carries none of them.
const FORBIDDEN = /[\u064B-\u0652\u0670\u0640\u2014\u2013;\u061B\uFF1B]/
const problems = []
const out = []
for (const r of rows) {
  const tr = done[r.id]
  if (typeof tr !== 'string' || !tr.trim()) {
    problems.push(`${r.id} missing`)
    continue
  }
  if (placeholders(tr) !== placeholders(r.en)) problems.push(`${r.id} placeholders ${placeholders(r.en)} -> ${placeholders(tr)}`)
  if (tags(tr) !== tags(r.en)) problems.push(`${r.id} html tags differ`)
  const bad = tr.replace(/&[a-z]+;|&#\d+;/gi, '').match(FORBIDDEN)
  if (bad) problems.push(`${r.id} forbidden character U+${bad[0].codePointAt(0).toString(16)}`)
  if (tr.includes('\n') !== r.en.includes('\n')) problems.push(`${r.id} newline differs`)
  out.push([r.en, tr.trim(), r.context])
}
const extra = Object.keys(done).filter((id) => !rows.some((r) => r.id === id))
if (extra.length) problems.push(`unknown ids: ${extra.slice(0, 5).join(', ')}`)

console.log(lang, 'strings', rows.length, 'translated', Object.keys(done).length, 'problems', problems.length)
for (const p of problems.slice(0, 40)) console.log('  ' + p)
if (problems.length || dry) process.exit(problems.length ? 1 : 0)

const erpKeys = new Set(JSON.parse(readFileSync(join(work, `erp_keys_${lang}.json`), 'utf8')))
const kept = out.filter(([en, , ctx]) => !erpKeys.has(ctx ? `${en}:${ctx}` : en))
console.log('left to ERPNext (already translated there):', out.length - kept.length)
const q = (v) => `"${String(v).replace(/"/g, '""')}"`
kept.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0))
const csv = kept.map(([en, tr, ctx]) => (ctx ? [en, tr, ctx] : [en, tr]).map(q).join(',')).join('\n') + '\n'
mkdirSync(APP, { recursive: true })
writeFileSync(join(APP, `${lang}.csv`), csv)
console.log('wrote', join(APP, `${lang}.csv`), kept.length, 'rows')
