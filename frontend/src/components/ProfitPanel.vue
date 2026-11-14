<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<!-- The Profit tab of Insights (0.62.0): net sales, the cost of the goods,
     the gross profit and the margin over a period, day by day and by item
     group, with the most and the least profitable items. For whoever may see
     the profit (esafepos.api.reports.profit decides). -->
<template>
  <div class="rep">
    <div class="card rep-card">
      <div class="rep-head">
        <div>
          <div class="rep-title">{{ t('Profit') }}</div>
          <div class="muted small">{{ t('In {currency}. Net sales are before tax, the cost is what the goods cost.', { currency: report?.currency || session.localCurrency }) }}</div>
        </div>
        <span style="flex: 1" />
        <button class="btn btn-outline" :disabled="!report?.days?.length" @click="download">
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
            <span class="tile-label">{{ t('Net sales') }}</span>
            <span class="tile-value"><bdi>{{ m(tot.net) }}</bdi></span>
          </div>
          <div class="tile">
            <span class="tile-label">{{ t('Cost of goods') }}</span>
            <span class="tile-value"><bdi>{{ m(tot.cost) }}</bdi></span>
          </div>
          <div class="tile strong">
            <span class="tile-label">{{ t('Gross profit') }}</span>
            <span class="tile-value" :class="{ loss: tot.profit < 0 }"><bdi>{{ m(tot.profit) }}</bdi></span>
          </div>
          <div class="tile">
            <span class="tile-label">{{ t('Gross margin') }}</span>
            <span class="tile-value" :class="{ loss: tot.margin !== null && tot.margin < 0 }"><bdi>{{ pct(tot.margin) }}</bdi></span>
          </div>
        </div>
        <p v-if="tot.estimated_lines" class="muted small note estimate">
          {{ t('{amount} of the cost is estimated, for {count} lines of shifts not closed yet, at the valuation rate. It becomes what ERPNext books once those shifts close.', { amount: m(tot.estimated_cost), count: tot.estimated_lines }) }}
        </p>
        <div v-if="!report.days.length" class="muted empty">{{ t('No sales in this period.') }}</div>
        <template v-else>
          <section class="block">
            <h3 class="block-title">{{ t('Day by day') }}</h3>
            <div class="wrap">
              <table class="rt">
                <thead>
                  <tr>
                    <th>{{ t('Day') }}</th>
                    <th class="num">{{ t('Net sales') }}</th>
                    <th class="num">{{ t('Cost') }}</th>
                    <th class="num">{{ t('Gross profit') }}</th>
                    <th class="num">{{ t('Gross margin') }}</th>
                    <th class="bar-col"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="d in report.days" :key="d.key">
                    <td><bdi>{{ d.key }}</bdi></td>
                    <td class="num"><bdi>{{ m(d.net) }}</bdi></td>
                    <td class="num"><bdi>{{ m(d.cost) }}</bdi></td>
                    <td class="num strong" :class="{ loss: d.profit < 0 }"><bdi>{{ m(d.profit) }}</bdi></td>
                    <td class="num"><bdi>{{ pct(d.margin) }}</bdi></td>
                    <td class="bar-col"><span class="bar" :style="{ width: bar(d.profit) }"></span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
          <section class="block">
            <h3 class="block-title">{{ t('By item group') }}</h3>
            <ProductRows :rows="report.groups" :head="t('Item group')" :with-profit="true" :currency="report.currency" />
          </section>
          <div class="cols">
            <section class="block">
              <h3 class="block-title">{{ t('Most profitable items') }}</h3>
              <ProductRows :rows="report.best" :head="t('Item')" :with-profit="true" :currency="report.currency" />
            </section>
            <section class="block">
              <h3 class="block-title">{{ t('Lowest margin') }}</h3>
              <ProductRows :rows="report.lowest_margin" :head="t('Item')" :with-profit="true" :currency="report.currency" />
            </section>
          </div>
          <p class="muted small note">
            {{ t('Cost is what ERPNext booked for the goods when the sale was posted, a bundle through its components. Until a shift closes it is estimated at the valuation rate.') }}
          </p>
        </template>
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
import { money } from '../format'
import { useSessionStore } from '../stores/session'

const session = useSessionStore()
const report = ref(null)
const loading = ref(false)
const error = ref('')
let asked = null

const tot = computed(() => report.value?.totals || {})
const m = (v) => money(v || 0, report.value?.currency)
const pct = (v) => (v === null || v === undefined ? '' : v + '%')
const top = computed(() => Math.max(0, ...(report.value?.days || []).map((d) => d.profit)))
const bar = (v) => (top.value > 0 ? Math.max(0, Math.round((v / top.value) * 100)) + '%' : '0%')

async function load(args) {
  if (args) asked = args
  if (session.offline || !asked) return
  loading.value = true
  error.value = ''
  try {
    report.value = await call('esafepos.api.reports.profit', asked)
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
  const lines = []
  const row = (...cells) => lines.push(cells.map(cell).join(','))
  row(t('Profit'), r.from_date, r.to_date, r.currency)
  row(t('Net sales'), r.totals.net)
  row(t('Cost of goods'), r.totals.cost)
  row(t('Gross profit'), r.totals.profit)
  row(t('Gross margin'), r.totals.margin ?? '')
  row('')
  row(t('Day'), t('Net sales'), t('Cost'), t('Gross profit'), t('Gross margin'))
  for (const d of r.days) row(d.key, d.net, d.cost, d.profit, d.margin ?? '')
  row('')
  row(t('Item group'), t('Net sales'), t('Cost'), t('Gross profit'), t('Gross margin'))
  for (const g of r.groups) row(g.label, g.net, g.cost, g.profit, g.margin ?? '')
  const blob = new Blob([String.fromCharCode(0xfeff) + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `profit-${r.from_date}-${r.to_date}.csv`
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
.note { padding: 10px 14px 14px; }
.estimate { padding-top: 0; color: var(--amber); }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; padding: 12px 14px; }
.tile { display: flex; flex-direction: column; gap: 4px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 10px; background: transparent; min-width: 0; }
.tile.strong { border-color: var(--brand); }
.tile-label { font-size: 12px; color: var(--text-muted); }
.tile-value { font-size: 17px; font-weight: 700; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.block { min-width: 0; border-top: 1px solid var(--border); }
.block-title { margin: 0; padding: 12px 14px 6px; font-size: 14px; font-weight: 700; }
.cols { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
.cols .block + .block { border-inline-start: 1px solid var(--border); }
.wrap { overflow-x: auto; }
.rt { width: 100%; border-collapse: collapse; font-size: 13px; }
.rt th { text-align: start; font-weight: 600; color: var(--text-muted); font-size: 12px; padding: 8px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; }
.rt td { padding: 8px 10px; border-bottom: 1px solid var(--border-subtle); vertical-align: top; }
.rt .num { text-align: end; white-space: nowrap; font-variant-numeric: tabular-nums; }
.rt .strong { font-weight: 700; }
.bar-col { width: 24%; min-width: 60px; }
.bar { display: block; height: 8px; border-radius: 4px; background: var(--brand); opacity: 0.75; margin-top: 5px; }
.loss { color: var(--red); }
@media (max-width: 900px) {
  .cols { grid-template-columns: minmax(0, 1fr); }
  .cols .block + .block { border-inline-start: 0; border-top: 1px solid var(--border); }
}
@media (max-width: 600px) {
  .rep-head { flex-wrap: wrap; }
  .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
