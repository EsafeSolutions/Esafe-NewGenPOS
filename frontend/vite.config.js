// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
// "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { readFileSync } from 'node:fs'

// The Frappe package owns the release. Embed it in the client so a till that
// defers an update still reports the version of the interface it is running.
const release = readFileSync(new URL('../esafepos/__init__.py', import.meta.url), 'utf8')
  .match(/^__version__\s*=\s*["']([^"']+)["']/m)?.[1]
const frontend = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8'))
const lock = JSON.parse(readFileSync(new URL('./package-lock.json', import.meta.url), 'utf8'))
const notes = JSON.parse(readFileSync(new URL('../esafepos/release_notes.json', import.meta.url), 'utf8'))
if (!release || frontend.version !== release || lock.version !== release || lock.packages?.['']?.version !== release || notes.current_version !== release || notes.releases[0]?.version !== release) {
  throw new Error('POS release versions differ. Align esafepos/__init__.py, frontend/package.json, frontend/package-lock.json and esafepos/release_notes.json before building.')
}
const changeIds = new Set(), updateNumbers = new Set(), versions = new Set()
for (const item of notes.releases) {
  if (!Number.isInteger(item.number) || item.number < 1 || updateNumbers.has(item.number) || versions.has(item.version)) throw new Error('Every release needs a unique version and positive update number.')
  updateNumbers.add(item.number); versions.add(item.version)
  for (const change of item.changes) {
    const prefix = { feature: 'F', improvement: 'I', fix: 'X' }[change.type]
    if (!prefix || !new RegExp(`^${prefix}-[0-9]{3,}$`).test(change.id) || changeIds.has(change.id) || !change.title || !change.text) throw new Error('Every release change needs a unique typed ID, title and description.')
    changeIds.add(change.id)
  }
}

// Build straight into the Frappe app's public folder with fixed filenames so
// esafepos/www/pos.html can reference /assets/esafepos/pos/pos.js and pos.css.
export default defineConfig({
  define: { __ESAFEPOS_VERSION__: JSON.stringify(release) },
  plugins: [vue(), {
    name: 'offline-shell-assets',
    generateBundle(_options, bundle) {
      // Include lazy language chunks and imported images before calling a
      // shell install complete; a reboot must not depend on a prior visit.
      this.emitFile({ type: 'asset', fileName: 'offline-assets.json',
        source: JSON.stringify(Object.keys(bundle).filter((name) => name !== 'index.html').sort()) })
    },
  }],
  base: '/assets/esafepos/pos/',
  build: {
    outDir: '../esafepos/public/pos',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: 'pos.js',
        // A language file (locales/<code>.js) is its own chunk. The hash gives
        // it a new name whenever its text changes, so neither the browser's
        // cache of /assets nor the service worker keeps an old translation.
        chunkFileNames: 'chunk-[name]-[hash].js',
        assetFileNames: (assetInfo) =>
          assetInfo.name && assetInfo.name.endsWith('.css') ? 'pos.css' : 'asset-[name][extname]',
      },
    },
  },
  server: {
    port: 8080,
    proxy: {
      '^/(api|assets|files)': {
        target: 'http://localhost:8000', // local bench during development
        changeOrigin: true,
      },
    },
  },
})
