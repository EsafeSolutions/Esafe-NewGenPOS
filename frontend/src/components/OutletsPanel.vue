<!-- Copyright (c) 2026 Lumen Solutions
     SPDX-License-Identifier: AGPL-3.0-only
     "LumenPOS" is a trademark of Lumen Solutions. See TRADEMARKS.md. -->
<!-- The Outlets tab of Insights (0.62.0): each outlet's sales, returns,
     average sale and items sold, its shifts and their over and short, the
     stock in its warehouse with the items at or below their reorder level, and
     its best sellers (lumenpos.api.reports.outlets). Opens on every outlet of
     the company. -->
<template>
  <div class="rep">
    <div class="card rep-card">
      <div class="rep-head">
        <div>
          <div class="rep-title">{{ t('Outlets') }}</div>
          <div class="muted small">{{ t('In {currency}, tax included. Stock is what the outlet\'s warehouse holds now.', { currency: report?.currency || session.localCurrency }) }}</div>
        </div>
        <span style="flex: 1" />
        <button class="btn btn-outline" :disabled="!report?.rows?.length" @click="download">
          <Icon name="download" /> {{ t('Download CSV') }}
        </button>
      </div>

      <ReportFilters default-scope="company" @change="load" />

      <div v-if="session.offline" class="muted empty">{{ t('This report needs a connection.') }}</div>
      <div v-else-if="loading && !report" class="muted empty">{{ t('Loading…') }}</div>
      <div v-else-if="error" class="empty neg">{{ error }}</div>
      <div v-else-if="!report || !report.rows.length" class="muted empty">{{ t('No outlet to show.') }}</div>
      <div v-else class="outlets">
        <article v-for="o in report.rows" :key="o.pos_profile" class="outlet">
          <header class="o-head">
            <span class="o-name"><bdi>{{ o.pos_profile }}</bdi></span>
            <span v-if="o.open_shifts" class="tag">{{ t('{count} open', { count: o.open_shifts }) }}</span>
            <span class="muted small o-wh"><bdi>{{ o.warehouse }}</bdi></span>
          </header>
          <dl class="o-figs">
            <div><dt>{{ t('Sales') }}</dt><dd>{{ o.sales }}</dd></div>
            <div><dt>{{ t('Total with tax') }}</dt><dd><bdi>{{ m(o.total) }}</bdi></dd></div>
            <div><dt>{{ t('Average sale') }}</dt><dd><bdi>{{ m(o.average_sale) }}</bdi></dd></div>
            <div><dt>{{ t('Returns') }}</dt><dd>{{ o.returns }}</dd></div>
            <div><dt>{{ t('Items sold') }}</dt><dd>{{ qty(o.items_sold) }}</dd></div>
            <div><dt>{{ t('Shifts') }}</dt><dd>{{ o.shifts }}</dd></div>
            <div>
              <dt>{{ t('Over and short') }}</dt>
              <dd>
                <span v-if="!o.differences.length" class="muted">{{ o.shifts ? t('No count yet') : '' }}</span>
                <span v-for="d in o.differences" :key="d.currency" class="d-line" :class="diffClass(d.difference)">
                  <bdi>{{ diffText(d.difference, d.currency) }}</bdi>
                </span>
              </dd>
            </div>
            <div><dt>{{ t('Stock in the warehouse') }}</dt><dd>{{ qty(o.stock) }}</dd></div>
            <div><dt>{{ t('At or below reorder level') }}</dt><dd :class="{ short: o.low_stock }">{{ o.low_stock }}</dd></div>
          </dl>
          <div v-if="o.top.length" class="o-top">
            <div class="muted small">{{ t('Best sellers') }}</div>
            <ol>
              <li v-for="x in o.top" :key="x.key"><bdi>{{ x.label }}</bdi> <span class="muted">{{ qty(x.qty) }}</span></li>
            </ol>
          </div>
        </article>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import Icon from './Icon.vue'
import ReportFilters from './ReportFilters.vue'
import { call } from '../api'
import { t } from '../i18n'
import { money } from '../format'
import { useSessionStore } from '../stores/session'

const session = useSessionStore()
const report = ref(null)
const loading = ref(false)
const error = ref('')
let asked = null

const m = (v) => money(v || 0, report.value?.currency)
const qty = (v) => Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 3 })
const diffClass = (d) => (Math.abs(d) < 0.005 ? 'ok' : d < 0 ? 'short' : 'over')
function diffText(d, ccy) {
  if (Math.abs(d) < 0.005) return t('Exact')
  return d < 0 ? t('Short {amount}', { amount: money(-d, ccy) }) : t('Over {amount}', { amount: money(d, ccy) })
}

async function load(args) {
  if (args) asked = args
  if (session.offline || !asked) return
  loading.value = true
  error.value = ''
  try {
    report.value = await call('lumenpos.api.reports.outlets', asked)
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
  const head = [t('Outlet'), t('Sales'), t('Total with tax'), t('Average sale'), t('Returns'), t('Items sold'), t('Shifts'),
    t('Over and short'), t('Stock in the warehouse'), t('At or below reorder level')]
  const lines = [head.map(cell).join(',')]
  for (const o of r.rows) {
    const diff = o.differences.map((d) => `${d.currency} ${d.difference}`).join(' ')
    lines.push([o.pos_profile, o.sales, o.total, o.average_sale, o.returns, o.items_sold, o.shifts, diff, o.stock, o.low_stock].map(cell).join(','))
  }
  const blob = new Blob([String.fromCharCode(0xfeff) + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `outlets-${r.from_date}-${r.to_date}.csv`
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
.outlets { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; padding: 14px; }
.outlet { border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; min-width: 0; }
.o-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; margin-bottom: 8px; }
.o-name { font-weight: 700; font-size: 15px; }
.o-wh { flex-basis: 100%; }
.tag { font-size: 11px; font-weight: 600; padding: 1px 6px; border-radius: 999px; background: var(--brand-soft); color: var(--brand); }
.o-figs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 14px; margin: 0; }
.o-figs div { min-width: 0; }
.o-figs dt { font-size: 12px; color: var(--text-muted); }
.o-figs dd { margin: 2px 0 0; font-weight: 700; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.d-line { display: block; }
.o-top { margin-top: 10px; border-top: 1px solid var(--border-subtle); padding-top: 8px; }
.o-top ol { margin: 4px 0 0; padding-inline-start: 18px; font-size: 13px; }
.ok { color: var(--text-muted); }
.short { color: var(--red); }
.over { color: var(--amber); }
@media (max-width: 600px) {
  .rep-head { flex-wrap: wrap; }
  .outlets { grid-template-columns: minmax(0, 1fr); }
}
</style>
