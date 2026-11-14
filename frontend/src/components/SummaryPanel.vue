<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<!-- The Sales summary tab of Insights (0.62.0): takings, tax, returns,
     discounts and payments over a period, day by day (hour by hour for one
     day), and what each shift's close counted against what it expected. The
     server decides who may see it (esafepos.api.reports.sales_summary). -->
<template>
  <div class="rep">
    <div class="card rep-card">
      <div class="rep-head">
        <div>
          <div class="rep-title">{{ t('Sales summary') }}</div>
          <div class="muted small">{{ t('In {currency}. Net sales are before tax, the total includes it.', { currency: report?.currency || session.localCurrency }) }}</div>
        </div>
        <span style="flex: 1" />
        <button class="btn btn-outline" :disabled="!report || !hasData" @click="download">
          <Icon name="download" /> {{ t('Download CSV') }}
        </button>
      </div>

      <ReportFilters @change="load" />

      <div v-if="session.offline" class="muted empty">{{ t('This report needs a connection.') }}</div>
      <div v-else-if="loading && !report" class="muted empty">{{ t('Loading…') }}</div>
      <div v-else-if="error" class="empty neg">{{ error }}</div>
      <template v-else-if="report">
        <div class="muted small range">
          <bdi>{{ report.from_date }}</bdi><span v-if="report.to_date !== report.from_date">&nbsp;{{ t('to') }}&nbsp;<bdi>{{ report.to_date }}</bdi></span>
        </div>

        <div class="tiles" data-tour="report-tiles">
          <div class="tile">
            <span class="tile-label">{{ t('Sales') }}</span>
            <span class="tile-value">{{ tot.sales }}</span>
          </div>
          <div class="tile">
            <span class="tile-label">{{ t('Average sale') }}</span>
            <span class="tile-value"><bdi>{{ m(tot.average_sale) }}</bdi></span>
          </div>
          <div class="tile">
            <span class="tile-label">{{ t('Net sales') }}</span>
            <span class="tile-value"><bdi>{{ m(tot.net) }}</bdi></span>
          </div>
          <div class="tile">
            <span class="tile-label">{{ t('Tax') }}</span>
            <span class="tile-value"><bdi>{{ m(tot.tax) }}</bdi></span>
          </div>
          <div class="tile strong">
            <span class="tile-label">{{ t('Total with tax') }}</span>
            <span class="tile-value"><bdi>{{ m(tot.total) }}</bdi></span>
          </div>
          <div class="tile">
            <span class="tile-label">{{ t('Returns') }}</span>
            <span class="tile-value">{{ tot.returns }}<span v-if="tot.returns" class="tile-sub">&nbsp;<bdi>{{ m(tot.returns_total) }}</bdi></span></span>
          </div>
          <div class="tile">
            <span class="tile-label">{{ t('Discounts given') }}</span>
            <span class="tile-value"><bdi>{{ m(tot.discounts) }}</bdi></span>
          </div>
          <div class="tile">
            <span class="tile-label">{{ t('Items sold') }}</span>
            <span class="tile-value">{{ qty(tot.items_sold) }}</span>
          </div>
        </div>

        <div v-if="!hasData" class="muted empty">{{ t('No sales in this period.') }}</div>
        <div v-else class="cols">
          <section class="block">
            <h3 class="block-title">{{ t('Payments') }}</h3>
            <div class="wrap">
              <table class="rt">
                <thead>
                  <tr>
                    <th>{{ t('Method') }}</th>
                    <th class="num">{{ t('Amount') }}</th>
                    <th class="num">{{ t('Share') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="p in report.payments" :key="p.mode_of_payment">
                    <td><bdi>{{ session.modeLabel ? session.modeLabel(p.mode_of_payment) : p.mode_of_payment }}</bdi></td>
                    <td class="num">
                      <bdi>{{ m(p.amount) }}</bdi>
                      <!-- What it took in other money (0.66.0): the customer's own currency. -->
                      <div v-for="x in p.paid_in || []" :key="x.currency" class="paid-in"><bdi>{{ money(x.amount, x.currency) }}</bdi></div>
                    </td>
                    <td class="num">{{ share(p.amount) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p v-if="(report.paid_in || []).length" class="muted small paid-in-total">
              {{ t('Taken in other currencies') }}:
              <template v-for="(x, i) in report.paid_in" :key="x.currency"><span v-if="i">&nbsp;·&nbsp;</span><bdi>{{ money(x.amount, x.currency) }}</bdi></template>
            </p>
          </section>

          <section class="block">
            <h3 class="block-title">{{ report.by === 'hour' ? t('Hour by hour') : t('Day by day') }}</h3>
            <div class="wrap">
              <table class="rt">
                <thead>
                  <tr>
                    <th>{{ report.by === 'hour' ? t('Hour') : t('Day') }}</th>
                    <th class="num">{{ t('Sales') }}</th>
                    <th class="num">{{ t('Net sales') }}</th>
                    <th class="num">{{ t('Total with tax') }}</th>
                    <th class="bar-col"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in report.series" :key="row.key">
                    <td><bdi>{{ report.by === 'hour' ? row.key + ':00' : row.key }}</bdi></td>
                    <td class="num">{{ row.sales }}<span v-if="row.returns" class="muted">&nbsp;<bdi dir="ltr">(−{{ row.returns }})</bdi></span></td>
                    <td class="num"><bdi>{{ m(row.net) }}</bdi></td>
                    <td class="num"><bdi>{{ m(row.total) }}</bdi></td>
                    <td class="bar-col"><span class="bar" :style="{ width: bar(row.total) }"></span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <section class="block shifts-block" data-tour="report-shifts">
          <h3 class="block-title">{{ t('Shifts and cash counted') }}</h3>
          <div v-if="!report.shifts.length" class="muted small pad">{{ t('No shifts opened in this period.') }}</div>
          <template v-else>
            <div v-if="report.differences.length" class="diffs">
              <span class="muted small">{{ t('Over and short, all shifts') }}:</span>
              <span v-for="d in report.differences" :key="d.currency" class="chip" :class="diffClass(d.difference)">
                <bdi>{{ diffText(d.difference, d.currency) }}</bdi>
              </span>
            </div>
            <div class="wrap">
              <table class="rt">
                <thead>
                  <tr>
                    <th>{{ t('Shift') }}</th>
                    <th v-if="manyOutlets">{{ t('Outlet') }}</th>
                    <th>{{ t('Cashier') }}</th>
                    <th>{{ t('Opened') }}</th>
                    <th class="num">{{ t('Sales') }}</th>
                    <th>{{ t('Counted against expected') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="s in report.shifts" :key="s.name" :class="{ off: s.off && !s.pending }">
                    <td><bdi>{{ s.name }}</bdi></td>
                    <td v-if="manyOutlets"><bdi>{{ s.pos_profile }}</bdi></td>
                    <td><bdi>{{ s.opened_by_name }}</bdi></td>
                    <td><bdi>{{ when(s.opened_at) }}</bdi></td>
                    <td class="num">{{ s.sales_count }}</td>
                    <td>
                      <span v-if="s.status === 'Open'" class="muted">{{ t('Still open') }}</span>
                      <span v-else-if="s.pending" class="muted">{{ t('Figures pending') }}</span>
                      <template v-else>
                        <span v-for="c in s.counts" :key="c.mode_of_payment + c.currency" class="count-line">
                          <bdi>{{ session.modeLabel ? session.modeLabel(c.mode_of_payment) : c.mode_of_payment }}</bdi>:
                          <span :class="diffClass(c.difference)"><bdi>{{ diffText(c.difference, c.currency || report.currency) }}</bdi></span>
                        </span>
                        <span v-if="s.variance_reason" class="muted small reason">{{ s.variance_reason }}</span>
                      </template>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </section>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
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
const hasData = computed(() => Boolean(tot.value.sales || tot.value.returns))
const manyOutlets = computed(() => (report.value?.outlets || []).length > 1)
const m = (v) => money(v || 0, report.value?.currency)
const qty = (v) => Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 3 })
const paid = computed(() => (report.value?.payments || []).reduce((a, p) => a + Math.max(0, p.amount), 0))
const share = (v) => (paid.value > 0 ? Math.round((Math.max(0, v) / paid.value) * 100) + '%' : '')
const top = computed(() => Math.max(0, ...(report.value?.series || []).map((r) => r.total)))
const bar = (v) => (top.value > 0 ? Math.max(0, Math.round((v / top.value) * 100)) + '%' : '0%')
const when = (v) => {
  if (!v) return ''
  const day = String(v).slice(0, 10)
  return report.value && report.value.from_date === report.value.to_date ? shortTime(v) : `${day} ${shortTime(v)}`
}
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
    report.value = await call('esafepos.api.reports.sales_summary', asked)
  } catch (e) {
    report.value = null
    error.value = e.message || String(e)
  } finally {
    loading.value = false
  }
}

// A spreadsheet of the figures on screen. The byte order mark lets Excel read
// Arabic right.
function download() {
  const r = report.value
  const cell = (v) => {
    const text = String(v ?? '')
    return /[",\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text
  }
  const lines = []
  const row = (...cells) => lines.push(cells.map(cell).join(','))
  row(t('Sales summary'), r.from_date, r.to_date, r.currency)
  row(t('Sales'), r.totals.sales)
  row(t('Average sale'), r.totals.average_sale)
  row(t('Net sales'), r.totals.net)
  row(t('Tax'), r.totals.tax)
  row(t('Total with tax'), r.totals.total)
  row(t('Returns'), r.totals.returns, r.totals.returns_total)
  row(t('Discounts given'), r.totals.discounts)
  row(t('Items sold'), r.totals.items_sold)
  row('')
  row(t('Method'), t('Amount'), t('In its own currency'))
  for (const p of r.payments) row(p.mode_of_payment, p.amount, ...(p.paid_in || []).flatMap((x) => [x.currency, x.amount]))
  for (const x of r.paid_in || []) row(t('Taken in other currencies'), '', x.currency, x.amount)
  row('')
  row(r.by === 'hour' ? t('Hour') : t('Day'), t('Sales'), t('Returns'), t('Net sales'), t('Tax'), t('Total with tax'))
  for (const s of r.series) row(s.key, s.sales, s.returns, s.net, s.tax, s.total)
  row('')
  row(t('Shift'), t('Outlet'), t('Cashier'), t('Opened'), t('Sales'), t('Method'), t('Expected'), t('Counted'), t('Difference'))
  for (const s of r.shifts) {
    if (!s.counts.length) row(s.name, s.pos_profile, s.opened_by_name, s.opened_at, s.sales_count, s.status === 'Open' ? t('Still open') : t('Figures pending'))
    for (const c of s.counts) row(s.name, s.pos_profile, s.opened_by_name, s.opened_at, s.sales_count, c.mode_of_payment, c.expected, c.counted, c.difference)
  }
  const blob = new Blob([String.fromCharCode(0xfeff) + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `sales-summary-${r.from_date}-${r.to_date}.csv`
  link.click()
  setTimeout(() => URL.revokeObjectURL(link.href), 1000)
}
</script>

<style scoped>
/* The card keeps its own height and the tab scrolls as one (the 0.57.0 lesson
   of the salesperson table squeezed to two rows on a phone). */
.rep { flex: 1; display: flex; align-items: flex-start; min-height: 0; overflow: auto; }
.rep-card { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.rep-head { display: flex; align-items: center; gap: 10px; padding: 14px; border-bottom: 1px solid var(--border); }
.rep-title { font-weight: 700; font-size: 16px; }
.range { padding: 10px 14px 0; }
.empty { padding: 26px; text-align: center; }
/* A method's takings in other money, under its amount (0.66.0). */
.paid-in { font-size: 12px; color: var(--text-muted); font-weight: 500; }
.paid-in-total { margin: 0; padding: 8px 14px 12px; }
.neg { color: var(--red); }
.pad { padding: 0 14px 12px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; padding: 12px 14px; }
.tile { display: flex; flex-direction: column; gap: 4px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 10px; background: transparent; min-width: 0; }
.tile.strong { border-color: var(--brand); }
.tile-label { font-size: 12px; color: var(--text-muted); }
.tile-value { font-size: 17px; font-weight: 700; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.tile-sub { font-size: 12px; font-weight: 500; color: var(--text-muted); }
.cols { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr); gap: 0; border-top: 1px solid var(--border); }
.cols .block + .block { border-inline-start: 1px solid var(--border); }
.block { min-width: 0; }
.shifts-block { border-top: 1px solid var(--border); }
.block-title { margin: 0; padding: 12px 14px 6px; font-size: 14px; font-weight: 700; }
.wrap { overflow-x: auto; }
.rt { width: 100%; border-collapse: collapse; font-size: 13px; }
.rt th { text-align: start; font-weight: 600; color: var(--text-muted); font-size: 12px; padding: 8px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; }
.rt td { padding: 8px 10px; border-bottom: 1px solid var(--border-subtle); vertical-align: top; }
.rt .num { text-align: end; white-space: nowrap; font-variant-numeric: tabular-nums; }
.rt tr.off td { background: color-mix(in srgb, var(--red) 7%, transparent); }
.bar-col { width: 28%; min-width: 60px; }
.bar { display: block; height: 8px; border-radius: 4px; background: var(--brand); opacity: 0.75; margin-top: 5px; }
.diffs { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 0 14px 10px; }
.chip { font-size: 12px; font-weight: 600; padding: 3px 8px; border-radius: 999px; border: 1px solid var(--border); }
.count-line { display: inline-block; margin-inline-end: 10px; white-space: nowrap; }
.reason { display: block; margin-top: 2px; }
.ok { color: var(--text-muted); }
.short { color: var(--red); font-weight: 600; }
.over { color: var(--amber); font-weight: 600; }
@media (max-width: 760px) {
  .cols { grid-template-columns: minmax(0, 1fr); }
  .cols .block + .block { border-inline-start: 0; border-top: 1px solid var(--border); }
}
@media (max-width: 600px) {
  .rep-head { flex-wrap: wrap; }
  .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
