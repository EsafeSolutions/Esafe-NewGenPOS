// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
// "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
// Prepare a translation job in <work>: the till's texts (every key of the
// Arabic dictionary, the till's complete list, with its English, its Arabic as
// a hint for short labels, and the screen it is on) and the server's texts
// (<work>/esafepos_msgs.json from extract_server.py, minus Frappe's navbar
// labels), each split in parts. Usage: node prep.mjs <work> [parts]
import { mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = fileURLToPath(new URL('../../', import.meta.url))
const SRC = join(ROOT, 'frontend', 'src')
const work = process.argv[2]
const PARTS = Number(process.argv[3] || 3)
if (!work) throw new Error('usage: node prep.mjs <work> [parts]')
mkdirSync(work, { recursive: true })

const src = readFileSync(join(SRC, 'messages.js'), 'utf8')
const { messages } = await import('data:text/javascript;base64,' + Buffer.from(src).toString('base64'))
const files = []
const walk = (dir) => {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) {
      if (name !== 'locales') walk(p)
    } else if (/\.(vue|js)$/.test(name) && name !== 'messages.js') files.push(p)
  }
}
walk(SRC)
const screens = {}
const re = /\bt\(\s*(['"])((?:\\.|(?!\1).)*)\1/g
for (const f of files) {
  const text = readFileSync(f, 'utf8')
  const screen = f.split(/[\\/]/).pop().replace(/\.(vue|js)$/, '')
  for (const m of text.matchAll(re)) {
    const key = m[2].replace(/\\'/g, "'").replace(/\\"/g, '"')
    ;(screens[key] ||= new Set()).add(screen)
  }
}
const ui = Object.keys(messages.ar).map((key, i) => ({
  id: 'u' + String(i + 1).padStart(4, '0'),
  key,
  en: messages.en[key] || key,
  ar: messages.ar[key],
  screen: [...(screens[key] || [])].slice(0, 3).join(', ') || (key.includes(':') ? key.split(':')[0] + ' names' : 'shared'),
}))

const server = JSON.parse(readFileSync(join(work, 'esafepos_msgs.json'), 'utf8'))
  .filter((r) => !r.path.startsWith('Navbar'))
  .map((r, i) => ({
    id: 's' + String(i + 1).padStart(4, '0'),
    en: r.message,
    context: r.context || '',
    where: r.path.startsWith('DocType:') ? r.path : r.path.replace(/^apps\/esafepos\//, ''),
  }))

for (const [name, rows] of [['ui', ui], ['server', server]]) {
  writeFileSync(join(work, `${name}_strings.json`), JSON.stringify(rows, null, 1))
  const size = Math.ceil(rows.length / PARTS)
  for (let p = 0; p < PARTS; p++) {
    writeFileSync(join(work, `${name}_part${p + 1}.json`), JSON.stringify(rows.slice(p * size, (p + 1) * size), null, 1))
  }
  console.log(name, rows.length, 'in', PARTS, 'parts')
}
