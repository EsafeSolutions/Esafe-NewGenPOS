<!-- Copyright (c) 2026 Lumen Solutions
     SPDX-License-Identifier: AGPL-3.0-only
     "LumenPOS" is a trademark of Lumen Solutions. See TRADEMARKS.md. -->
<!-- Barcode and price labels (0.67.0, lumenpos.api.labels): items from a search
     or a scan, from a document that brought goods in, or from the prices changed
     since a date; the size, what prints, a preview, and the print itself. -->
<template>
  <div class="labels">
    <section class="card pick">
      <div v-if="!session.permissions.print_labels" class="muted empty">{{ t("You're not allowed to print labels.") }}</div>
      <template v-else>
        <div class="add-row">
          <div class="search-box" data-tour="labels-search">
            <Icon name="search" />
            <input
              ref="searchInput"
              v-model="query"
              :placeholder="t('Scan a barcode or search for an item…')"
              @input="debouncedSearch"
              @keydown.enter.prevent="scanOrPick"
            />
          </div>
        </div>
        <div v-if="found.length" class="found">
          <button v-for="item in found" :key="item.item_code" type="button" class="found-row" @click="addItems([{ item_code: item.item_code, qty: 1 }])">
            <bdi>{{ item.item_name }}</bdi>
            <span class="muted small" dir="ltr">{{ item.item_code }}</span>
          </button>
        </div>

        <div class="sources">
          <div class="source" data-tour="labels-document">
            <span class="src-title">{{ t('From a document') }}</span>
            <div class="src-row">
              <select v-model="docType" class="cf-in" @change="loadDocuments">
                <option v-for="d in DOCTYPES" :key="d" :value="d">{{ t(d) }}</option>
              </select>
              <input v-model="docSearch" class="cf-in grow" :placeholder="t('Number or supplier…')" @input="debouncedDocuments" />
            </div>
            <div v-if="docs.length" class="doc-list">
              <button v-for="d in docs" :key="d.name" type="button" class="found-row" @click="fromDocument(d.name)">
                <bdi dir="ltr">{{ d.name }}</bdi>
                <span class="muted small"><bdi>{{ d.party }}</bdi> · <bdi dir="ltr">{{ d.date }}</bdi><span v-if="d.draft"> · {{ t('Draft') }}</span></span>
              </button>
            </div>
          </div>
          <div class="source">
            <span class="src-title">{{ t('Prices changed since') }}</span>
            <div class="src-row">
              <input v-model="since" type="date" class="cf-in" />
              <button class="btn btn-outline" type="button" :disabled="!since || busy" @click="priceChanges">{{ t('Add') }}</button>
            </div>
          </div>
        </div>

        <div v-if="error" class="neg small err">{{ error }}</div>
        <div v-if="!rows.length" class="muted empty">{{ t('Add items to print their labels.') }}</div>
        <div v-else class="wrap">
          <table class="rt">
            <thead>
              <tr>
                <th>{{ t('Item') }}</th>
                <th class="num">{{ t('Price') }}</th>
                <th class="num">{{ t('Copies') }}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="row.item_code">
                <td>
                  <div><bdi>{{ row.item_name }}</bdi></div>
                  <div class="muted small" dir="ltr">{{ row.barcode || row.item_code }}</div>
                  <div v-if="row.unpriced" class="warn small">{{ t('No price on this outlet’s price list.') }}</div>
                  <div v-else-if="!row.barcode" class="muted small">{{ t('No barcode: the item code is printed as one.') }}</div>
                </td>
                <td class="num"><bdi>{{ money(row.price_with_tax, row.currency) }}</bdi></td>
                <td class="num">
                  <input v-model.number="row.qty" type="number" min="0" max="999" class="qty" />
                </td>
                <td><button class="btn-ghost" type="button" :title="t('Remove')" @click="remove(row)"><Icon name="close" /></button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </section>

    <section v-if="session.permissions.print_labels" class="card setup">
      <div class="setup-body">
        <label class="field" data-tour="labels-size">
          <span>{{ t('Label size') }}</span>
          <select v-model="opts.size" class="cf-in">
            <option v-for="p in PRESETS" :key="p.key" :value="p.key">{{ t(p.label) }}</option>
          </select>
        </label>
        <div v-if="size.custom" class="custom">
          <label class="field"><span>{{ t('Width, mm') }}</span><input v-model.number="opts.w" type="number" min="20" max="120" class="cf-in" /></label>
          <label class="field"><span>{{ t('Height, mm') }}</span><input v-model.number="opts.h" type="number" min="15" max="120" class="cf-in" /></label>
        </div>
        <div class="field">
          <span>{{ t('On the label') }}</span>
          <label v-for="f in fieldChoices" :key="f.key" class="check">
            <input v-model="opts.show[f.key]" type="checkbox" /> {{ t(f.label) }}
          </label>
        </div>
        <div class="muted small">{{ t('{n} labels', { n: total }) }}</div>
        <button class="btn btn-primary" type="button" data-tour="labels-print" :disabled="!total || printing" @click="print">
          <Icon name="tag" /> {{ printing ? t('Preparing…') : t('Print labels') }}
        </button>
        <p class="muted small">{{ t('Choose your label printer in the print window, with margins set to none and the scale at 100%.') }}</p>
      </div>
      <div class="preview-head muted small">{{ t('Preview') }}</div>
      <iframe class="preview" :title="t('Preview')" :srcdoc="previewHtml"></iframe>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { call } from '../api'
import { t, locale } from '../i18n'
import { money } from '../format'
import { useSessionStore } from '../stores/session'
import { PRESETS, sizeOf, pageHtml } from '../labels'
import Icon from '../components/Icon.vue'

const session = useSessionStore()
const DOCTYPES = ['Purchase Receipt', 'Stock Entry', 'Purchase Invoice']
const STORE_KEY = 'lumenpos-labels'

const rows = ref([])
const query = ref('')
const found = ref([])
const searchInput = ref(null)
const docType = ref(DOCTYPES[0])
const docSearch = ref('')
const docs = ref([])
const since = ref('')
const busy = ref(false)
const printing = ref(false)
const error = ref('')

// The device remembers its label size and fields, a convenience only.
function stored() {
  try {
    return JSON.parse(localStorage.getItem(STORE_KEY) || 'null') || {}
  } catch {
    return {}
  }
}
const saved = stored()
const opts = ref({
  size: saved.size || PRESETS[0].key,
  w: saved.w || 50,
  h: saved.h || 30,
  show: { shop: false, name: true, price: true, equivalent: false, barcode: true, code: false, ...(saved.show || {}) },
})
watch(opts, (v) => {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(v))
  } catch {
    /* private window: the defaults next time */
  }
}, { deep: true })

const hasEquivalents = computed(() => rows.value.some((r) => (r.equivalents || []).length))
const fieldChoices = computed(() => [
  { key: 'shop', label: 'Shop name' },
  { key: 'name', label: 'Item name' },
  { key: 'price', label: 'Price' },
  ...(hasEquivalents.value ? [{ key: 'equivalent', label: 'Price in other currencies' }] : []),
  { key: 'barcode', label: 'Barcode' },
  { key: 'code', label: 'Item code' },
])
const size = computed(() => sizeOf(opts.value.size, { w: opts.value.w, h: opts.value.h }))
const total = computed(() => rows.value.reduce((n, r) => n + Math.max(0, Math.floor(+r.qty || 0)), 0))

// What a label says, as text: the price in the outlet's money, the other
// currencies beside it.
function printable(list) {
  return list.map((r) => ({
    ...r,
    shop: session.company,
    price_text: money(r.price_with_tax, r.currency),
    equivalent_text: (r.equivalents || []).map((e) => money(e.amount, e.currency)).join(' · '),
  }))
}
const previewHtml = computed(() => {
  const sample = printable(rows.value.slice(0, 6).map((r) => ({ ...r, qty: 1 })))
  return pageHtml(sample, opts.value.show, size.value, { title: t('Labels'), rtl: locale.value === 'ar' || locale.value === 'fa' })
})

function merge(list) {
  for (const row of list || []) {
    const have = rows.value.find((r) => r.item_code === row.item_code)
    if (have) have.qty = (+have.qty || 0) + (+row.qty || 1)
    else rows.value.push({ ...row })
  }
}

async function run(fn) {
  error.value = ''
  busy.value = true
  try {
    await fn()
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    busy.value = false
  }
}

function addItems(list) {
  return run(async () => {
    const data = await call('lumenpos.api.labels.items', { pos_profile: session.posProfile, items: list })
    merge(data.rows)
    found.value = []
    query.value = ''
    searchInput.value?.focus()
  })
}

let searchTimer = null
function debouncedSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(search, 300)
}
async function search() {
  const q = query.value.trim()
  if (q.length < 2) {
    found.value = []
    return
  }
  try {
    const data = await call('lumenpos.api.catalog.get_items', { pos_profile: session.posProfile, search: q, limit: 12 })
    found.value = (data.items || []).map((i) => ({ item_code: i.item_code, item_name: i.item_name }))
  } catch {
    found.value = []
  }
}

// Enter: a scanned barcode adds its item at once, a typed word picks the only match.
async function scanOrPick() {
  const q = query.value.trim()
  if (!q) return
  clearTimeout(searchTimer)
  await run(async () => {
    const hit = await call('lumenpos.api.catalog.resolve_scan', { pos_profile: session.posProfile, code: q })
    if (hit && hit.found && hit.item) return addItems([{ item_code: hit.item.item_code, qty: 1 }])
    await search()
    if (found.value.length === 1) return addItems([{ item_code: found.value[0].item_code, qty: 1 }])
    if (!found.value.length) error.value = t('No item matches {query}.', { query: q })
  })
}

let docTimer = null
function debouncedDocuments() {
  clearTimeout(docTimer)
  docTimer = setTimeout(loadDocuments, 300)
}
function loadDocuments() {
  return run(async () => {
    docs.value = await call('lumenpos.api.labels.documents', { pos_profile: session.posProfile, doctype: docType.value, search: docSearch.value })
  })
}
function fromDocument(name) {
  return run(async () => {
    const data = await call('lumenpos.api.labels.from_document', { pos_profile: session.posProfile, doctype: docType.value, name })
    merge(data.rows)
    if (!data.rows.length) error.value = t('{doc} has no items to label.', { doc: name })
  })
}
function priceChanges() {
  return run(async () => {
    const data = await call('lumenpos.api.labels.price_changes', { pos_profile: session.posProfile, since: since.value })
    merge(data.rows)
    if (!data.rows.length) error.value = t('No price changed since that date.')
  })
}

function remove(row) {
  rows.value = rows.value.filter((r) => r !== row)
}

// The print: a page of its own in a hidden frame, sized to the label, so the
// browser's print window sends exactly that to the printer.
async function print() {
  if (!total.value) return
  printing.value = true
  try {
    const frame = document.createElement('iframe')
    frame.setAttribute('aria-hidden', 'true')
    frame.style.cssText = 'position:fixed;width:0;height:0;border:0;right:0;bottom:0'
    frame.srcdoc = pageHtml(printable(rows.value), opts.value.show, size.value, { title: t('Labels'), rtl: locale.value === 'ar' || locale.value === 'fa' })
    document.body.appendChild(frame)
    await new Promise((resolve) => frame.addEventListener('load', resolve, { once: true }))
    frame.contentWindow.focus()
    frame.contentWindow.print()
    setTimeout(() => frame.remove(), 60000)
  } finally {
    printing.value = false
  }
}

onMounted(() => {
  if (session.permissions.print_labels) loadDocuments()
})
</script>

<style scoped>
.labels { flex: 1; min-width: 0; display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(280px, 1fr); gap: 14px; padding: 14px; overflow: auto; align-items: start }
.pick, .setup { padding: 0; overflow: hidden }
.add-row { padding: 12px 14px 0 }
.search-box { display: flex; align-items: center; gap: 6px; border: 1px solid var(--border); border-radius: 8px; padding: 0 9px; background: var(--card-bg) }
.search-box :deep(svg) { width: 16px; height: 16px; color: var(--text-muted) }
.search-box input { flex: 1; border: 0; padding: 9px 0; font: inherit; background: transparent; color: var(--text); outline: none; min-width: 0 }
.found, .doc-list { margin: 6px 14px 0; border: 1px solid var(--border); border-radius: 8px; max-height: 220px; overflow: auto }
.found-row { width: 100%; display: flex; justify-content: space-between; gap: 10px; padding: 8px 10px; background: transparent; border: 0; border-bottom: 1px solid var(--border); text-align: start; font: inherit; color: var(--text); cursor: pointer }
.found-row:last-child { border-bottom: 0 }
.found-row:hover { background: var(--surface-2) }
.sources { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 12px 14px }
.source { display: flex; flex-direction: column; gap: 6px; min-width: 0 }
.source .doc-list { margin: 0 }
.src-title { font-size: 12.5px; font-weight: 700; color: var(--text-muted) }
.src-row { display: flex; gap: 6px; min-width: 0 }
.grow { flex: 1; min-width: 0 }
.err { padding: 0 14px 8px }
.neg { color: var(--danger, #d33) }
.warn { color: var(--amber, #b26a00) }
.empty { padding: 26px; text-align: center }
.wrap { overflow-x: auto; border-top: 1px solid var(--border) }
.rt { width: 100%; border-collapse: collapse; font-size: 13.5px }
.rt th, .rt td { padding: 8px 12px; border-bottom: 1px solid var(--border); text-align: start; vertical-align: top }
.rt th { font-size: 12px; color: var(--text-muted); font-weight: 600 }
.rt .num { text-align: end; white-space: nowrap }
.qty { width: 64px; padding: 5px 6px; border: 1px solid var(--border); border-radius: 6px; background: var(--card-bg); color: var(--text); font: inherit; text-align: end }
.setup-body { display: flex; flex-direction: column; gap: 10px; padding: 14px }
.field { display: flex; flex-direction: column; gap: 5px; font-size: 13px }
.field > span { font-weight: 600; color: var(--text-muted); font-size: 12.5px }
.custom { display: grid; grid-template-columns: 1fr 1fr; gap: 8px }
.check { display: flex; align-items: center; gap: 7px; font-weight: 500 }
.preview-head { padding: 0 14px 6px }
.preview { width: 100%; height: 360px; border: 0; border-top: 1px solid var(--border); background: #f2f4f7 }
.small { font-size: 12px }
@media (max-width: 900px) {
  .labels { grid-template-columns: 1fr }
  .sources { grid-template-columns: 1fr }
}
</style>
