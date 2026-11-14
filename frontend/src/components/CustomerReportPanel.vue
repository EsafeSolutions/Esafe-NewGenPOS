<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<!-- The Customers tab of Insights (0.62.0): how many named customers bought,
     came back or are new, the average basket and how often they buy, the best,
     the regulars and the most recent, beside the walk-in sales
     (esafepos.api.reports.customers). -->
<template>
  <div class="rep">
    <div class="card rep-card">
      <div class="rep-head">
        <div>
          <div class="rep-title">{{ t('Customers') }}</div>
          <div class="muted small">{{ t('In {currency}, tax included. Walk-in sales are counted apart.', { currency: report?.currency || session.localCurrency }) }}</div>
        </div>
        <span style="flex: 1" />
        <button class="btn btn-outline" :disabled="!report?.top?.length" @click="download">
          <Icon name="download" /> {{ t('Download CSV') }}
        </button>
      </div>

      <ReportFilters @change="load" />

      <div v-if="session.offline" class="muted empty">{{ t('This report needs a connection.') }}</div>
      <div v-else-if="loading && !report" class="muted empty">{{ t('Loading…') }}</div>
      <div v-else-if="error" class="empty neg">{{ error }}</div>
      <template v-else-if="report">
        <div class="tiles">
          <div class="tile">
            <span class="tile-label">{{ t('Customers') }}</span>
            <span class="tile-value">{{ tot.customers }}</span>
          </div>
          <div class="tile">
            <span class="tile-label">{{ t('New customers') }}</span>
            <span class="tile-value">{{ tot.new }}</span>
          </div>
          <div class="tile">
            <span class="tile-label">{{ t('Came back') }}</span>
            <span class="tile-value">{{ tot.repeat }}<span class="tile-sub">&nbsp;<bdi>{{ tot.repeat_rate }}%</bdi></span></span>
          </div>
          <div class="tile">
            <span class="tile-label">{{ t('Average basket') }}</span>
            <span class="tile-value"><bdi>{{ m(tot.average_basket) }}</bdi></span>
          </div>
          <div class="tile">
            <span class="tile-label">{{ t('Sales per customer') }}</span>
            <span class="tile-value">{{ tot.frequency }}</span>
          </div>
          <div class="tile">
            <span class="tile-label">{{ t('Walk-in sales') }}</span>
            <span class="tile-value">{{ tot.walk_in_sales }}<span class="tile-sub">&nbsp;<bdi>{{ m(tot.walk_in_total) }}</bdi></span></span>
          </div>
        </div>
        <div v-if="!report.top.length" class="muted empty">{{ t('No named customer bought in this period.') }}</div>
        <template v-else>
          <section class="block">
            <h3 class="block-title">{{ t('Top customers') }}</h3>
            <CustomerRows :rows="report.top" :currency="report.currency" />
          </section>
          <div class="cols">
            <section class="block">
              <h3 class="block-title">{{ t('Regulars') }}</h3>
              <div v-if="!report.repeat.length" class="muted small pad">{{ t('Nobody bought twice in this period.') }}</div>
              <CustomerRows v-else :rows="report.repeat" :currency="report.currency" />
            </section>
            <section class="block">
              <h3 class="block-title">{{ t('Recently active') }}</h3>
              <CustomerRows :rows="report.recent" :currency="report.currency" />
            </section>
          </div>
        </template>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, h, ref } from 'vue'
import Icon from './Icon.vue'
import ReportFilters from './ReportFilters.vue'
import { call } from '../api'
import { t } from '../i18n'
import { money, shortTime } from '../format'
import { useSessionStore } from '../stores/session'

const session = useSessionStore()
const report = ref(null)
const loading = ref(false)
const error = ref('')
let asked = null

const tot = computed(() => report.value?.totals || {})
const m = (v) => money(v || 0, report.value?.currency)

// One table of customers: name (new ones marked), sales, total and last visit.
const CustomerRows = (props) =>
  h('div', { class: 'wrap' }, [
    h('table', { class: 'rt' }, [
      h('thead', [h('tr', [
        h('th', t('Customer')),
        h('th', { class: 'num' }, t('Sales')),
        h('th', { class: 'num' }, t('Total with tax')),
        h('th', t('Last visit')),
      ])]),
      h('tbody', props.rows.map((r) => h('tr', { key: r.customer }, [
        h('td', { class: 'who' }, [h('bdi', r.name), r.new ? h('span', { class: 'tag' }, t('New')) : null]),
        h('td', { class: 'num' }, String(r.sales)),
        h('td', { class: 'num strong' }, [h('bdi', money(r.total, props.currency))]),
        h('td', [h('bdi', shortTime(r.last))]),
      ]))),
    ]),
  ])
CustomerRows.props = ['rows', 'currency']

async function load(args) {
  if (args) asked = args
  if (session.offline || !asked) return
  loading.value = true
  error.value = ''
  try {
    report.value = await call('esafepos.api.reports.customers', asked)
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
  const lines = [[t('Customer'), t('Sales'), t('Returns'), t('Total with tax'), t('Last visit'), t('New')].map(cell).join(',')]
  for (const x of r.top) lines.push([x.name, x.sales, x.returns, x.total, x.last, x.new ? 1 : 0].map(cell).join(','))
  const blob = new Blob([String.fromCharCode(0xfeff) + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `customers-${r.from_date}-${r.to_date}.csv`
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
.pad { padding: 0 14px 12px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; padding: 12px 14px; }
.tile { display: flex; flex-direction: column; gap: 4px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 10px; background: transparent; min-width: 0; }
.tile-label { font-size: 12px; color: var(--text-muted); }
.tile-value { font-size: 17px; font-weight: 700; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.tile-sub { font-size: 12px; font-weight: 500; color: var(--text-muted); }
.block { min-width: 0; border-top: 1px solid var(--border); }
.block-title { margin: 0; padding: 12px 14px 6px; font-size: 14px; font-weight: 700; }
.cols { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
.cols .block + .block { border-inline-start: 1px solid var(--border); }
.rep :deep(.wrap) { overflow-x: auto; }
.rep :deep(.rt) { width: 100%; border-collapse: collapse; font-size: 13px; }
.rep :deep(.rt th) { text-align: start; font-weight: 600; color: var(--text-muted); font-size: 12px; padding: 8px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; }
.rep :deep(.rt td) { padding: 8px 10px; border-bottom: 1px solid var(--border-subtle); vertical-align: top; }
.rep :deep(.rt .num) { text-align: end; white-space: nowrap; font-variant-numeric: tabular-nums; }
.rep :deep(.rt .strong) { font-weight: 700; }
.rep :deep(.rt .who) { min-width: 150px; }
.rep :deep(.tag) { margin-inline-start: 6px; font-size: 11px; font-weight: 600; padding: 1px 6px; border-radius: 999px; background: var(--brand-soft); color: var(--brand); }
@media (max-width: 900px) {
  .cols { grid-template-columns: minmax(0, 1fr); }
  .cols .block + .block { border-inline-start: 0; border-top: 1px solid var(--border); }
}
@media (max-width: 600px) {
  .rep-head { flex-wrap: wrap; }
  .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
