<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<!-- The Products tab of Insights (0.62.0): what sold over a period, by item,
     item group, brand, the item a variant belongs to, and each variant
     attribute. The cost, gross profit and margin come only to whoever may see
     the profit (esafepos.api.reports.products decides). -->
<template>
  <div class="rep">
    <div class="card rep-card">
      <div class="rep-head">
        <div>
          <div class="rep-title">{{ t('Products') }}</div>
          <div class="muted small">{{ t('In {currency}. Net sales are before tax, returns taken off.', { currency: report?.currency || session.localCurrency }) }}</div>
        </div>
        <span style="flex: 1" />
        <button class="btn btn-outline" :disabled="!rows.length" @click="download">
          <Icon name="download" /> {{ t('Download CSV') }}
        </button>
      </div>

      <ReportFilters @change="load" />

      <div v-if="session.offline" class="muted empty">{{ t('This report needs a connection.') }}</div>
      <div v-else-if="loading && !report" class="muted empty">{{ t('Loading…') }}</div>
      <div v-else-if="error" class="empty neg">{{ error }}</div>
      <template v-else-if="report">
        <div class="views">
          <div class="seg">
            <button v-for="v in views" :key="v.key" type="button" class="seg-btn" :class="{ on: view === v.key }" @click="view = v.key">
              {{ t(v.label) }}
            </button>
          </div>
        </div>
        <div v-if="!report.items.length" class="muted empty">{{ t('No sales in this period.') }}</div>
        <template v-else-if="view === 'attribute'">
          <section v-for="a in report.attributes" :key="a.attribute" class="block">
            <h3 class="block-title"><bdi>{{ a.attribute }}</bdi></h3>
            <ProductRows :rows="a.values" :head="t('Value')" :with-profit="report.with_profit" :currency="report.currency" />
          </section>
        </template>
        <ProductRows v-else :rows="rows" :head="headLabel" :with-profit="report.with_profit" :currency="report.currency" :detail="view === 'item'" />
        <p v-if="view === 'item' && report.items_total > report.items.length" class="muted small note">
          {{ t('The {shown} best selling of {count} items.', { shown: report.items.length, count: report.items_total }) }}
        </p>
        <p v-if="report.with_profit" class="muted small note">
          {{ t('Cost is what ERPNext booked for the goods when the sale was posted, a bundle through its components. Until a shift closes it is estimated at the valuation rate.') }}
        </p>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import Icon from './Icon.vue'
import ReportFilters from './ReportFilters.vue'
import ProductRows from './ProductRows.vue'
import { call } from '../api'
import { t } from '../i18n'
import { useSessionStore } from '../stores/session'

const session = useSessionStore()
const report = ref(null)
const loading = ref(false)
const error = ref('')
const view = ref('item')
let asked = null

const views = computed(() => [
  { key: 'item', label: 'By item' },
  { key: 'group', label: 'By item group' },
  { key: 'brand', label: 'By brand' },
  report.value?.templates?.length && { key: 'template', label: 'By product with variants' },
  report.value?.attributes?.length && { key: 'attribute', label: 'By attribute' },
].filter(Boolean))
const rows = computed(() => {
  const r = report.value
  if (!r) return []
  return { item: r.items, group: r.groups, brand: r.brands, template: r.templates, attribute: [] }[view.value] || []
})
const headLabel = computed(() => ({ item: t('Item'), group: t('Item group'), brand: t('Brand'), template: t('Product') }[view.value] || ''))

async function load(args) {
  if (args) asked = args
  if (session.offline || !asked) return
  loading.value = true
  error.value = ''
  try {
    report.value = await call('esafepos.api.reports.products', asked)
    if (!views.value.some((v) => v.key === view.value)) view.value = 'item'
  } catch (e) {
    report.value = null
    error.value = e.message || String(e)
  } finally {
    loading.value = false
  }
}

function download() {
  const r = report.value
  const cell = (v) => {
    const text = String(v ?? '')
    return /[",\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text
  }
  const head = [headLabel.value || t('Value'), t('Sold'), t('Returned'), t('Net quantity'), t('Net sales')]
  if (r.with_profit) head.push(t('Cost'), t('Gross profit'), t('Gross margin'))
  const lines = [head.map(cell).join(',')]
  const list = view.value === 'attribute' ? r.attributes.flatMap((a) => a.values.map((v) => ({ ...v, label: `${a.attribute}: ${v.label}` }))) : rows.value
  for (const x of list) {
    const row = [x.label || '', x.sold, x.returned, x.qty, x.net]
    if (r.with_profit) row.push(x.cost, x.profit, x.margin ?? '')
    lines.push(row.map(cell).join(','))
  }
  const blob = new Blob([String.fromCharCode(0xfeff) + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `products-${view.value}-${r.from_date}-${r.to_date}.csv`
  link.click()
  setTimeout(() => URL.revokeObjectURL(link.href), 1000)
}
</script>

<style scoped>
.rep { flex: 1; display: flex; align-items: flex-start; min-height: 0; overflow: auto; }
.rep-card { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.rep-head { display: flex; align-items: center; gap: 10px; padding: 14px; border-bottom: 1px solid var(--border); }
.rep-title { font-weight: 700; font-size: 16px; }
.empty { padding: 26px; text-align: center; }
.neg { color: var(--red); }
.note { padding: 10px 14px 0; }
.note:last-child { padding-bottom: 14px; }
.views { padding: 12px 14px 4px; }
.seg { display: inline-flex; flex-wrap: wrap; border: 1px solid var(--border); border-radius: 9px; overflow: hidden; }
.seg-btn { background: transparent; border: 0; padding: 7px 12px; font: inherit; font-size: 13px; color: var(--text); cursor: pointer; }
.seg-btn + .seg-btn { border-inline-start: 1px solid var(--border); }
.seg-btn.on { background: var(--brand); color: #fff; }
.block { min-width: 0; border-top: 1px solid var(--border); }
.block-title { margin: 0; padding: 12px 14px 6px; font-size: 14px; font-weight: 700; }
@media (max-width: 600px) {
  .rep-head { flex-wrap: wrap; }
}
</style>
