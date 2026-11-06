<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<!-- The Cashiers tab of Insights (0.62.0): what each cashier rang up, the
     returns and discounts they gave, the price edits the audit log holds for
     them, and how their shifts' counts compared with what was expected. The
     server decides who may see it (lumenpos.api.reports.cashiers). -->
<template>
  <div class="rep">
    <div class="card rep-card">
      <div class="rep-head">
        <div>
          <div class="rep-title">{{ t('How each cashier did') }}</div>
          <div class="muted small">{{ t('In {currency}. A sale counts for whoever rang it up.', { currency: report?.currency || session.localCurrency }) }}</div>
        </div>
        <span style="flex: 1" />
        <button class="btn btn-outline" :disabled="!report?.rows?.length" @click="download">
          <Icon name="download" /> {{ t('Download CSV') }}
        </button>
      </div>

      <ReportFilters @change="load" />

      <div v-if="session.offline" class="muted empty">{{ t('This report needs a connection.') }}</div>
      <div v-else-if="loading && !report" class="muted empty">{{ t('Loading…') }}</div>
      <div v-else-if="error" class="empty neg">{{ error }}</div>
      <div v-else-if="!report || !report.rows.length" class="muted empty">{{ t('No cashier activity in this period.') }}</div>
      <template v-else>
        <div class="muted small range">
          <bdi>{{ report.from_date }}</bdi><span v-if="report.to_date !== report.from_date">&nbsp;{{ t('to') }}&nbsp;<bdi>{{ report.to_date }}</bdi></span>
        </div>
        <div class="wrap" data-tour="report-cashiers">
          <table class="rt">
            <thead>
              <tr>
                <th>{{ t('Cashier') }}</th>
                <th class="num">{{ t('Sales') }}</th>
                <th class="num">{{ t('Total with tax') }}</th>
                <th class="num">{{ t('Average sale') }}</th>
                <th class="num">{{ t('Returns') }}</th>
                <th class="num">{{ t('Discounts given') }}</th>
                <th class="num">{{ t('Price edits') }}</th>
                <th class="num">{{ t('Shifts') }}</th>
                <th>{{ t('Over and short') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in report.rows" :key="r.user">
                <td class="who"><bdi>{{ r.name }}</bdi></td>
                <td class="num">{{ r.sales }}</td>
                <td class="num strong"><bdi>{{ m(r.total) }}</bdi></td>
                <td class="num"><bdi>{{ m(r.average_sale) }}</bdi></td>
                <td class="num">
                  <template v-if="r.returns">{{ r.returns }} <span class="muted">(<bdi>{{ m(r.returns_total) }}</bdi>)</span></template>
                  <span v-else class="muted">0</span>
                </td>
                <td class="num"><bdi>{{ m(r.discounts) }}</bdi></td>
                <td class="num">{{ r.price_edits }}</td>
                <td class="num">
                  {{ r.shifts }}<span v-if="r.shifts_off" class="short">&nbsp;({{ t('{count} off', { count: r.shifts_off }) }})</span>
                </td>
                <td>
                  <span v-if="!r.differences.length" class="muted">{{ r.shifts ? t('No count yet') : '' }}</span>
                  <span v-for="d in r.differences" :key="d.currency" class="count-line" :class="diffClass(d.difference)">
                    <bdi>{{ diffText(d.difference, d.currency) }}</bdi>
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="muted small note">
          {{ t('Over and short adds up what each cashier counted at their closes against what their shifts expected. Price edits are the prices typed at the till, from the audit log.') }}
        </p>
      </template>
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
    report.value = await call('lumenpos.api.reports.cashiers', asked)
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
  const head = [t('Cashier'), t('Sales'), t('Total with tax'), t('Average sale'), t('Returns'), t('Returns amount'),
    t('Discounts given'), t('Price edits'), t('Shifts'), t('Over and short')]
  const lines = [head.map(cell).join(',')]
  for (const x of r.rows) {
    const diff = x.differences.map((d) => `${d.currency} ${d.difference}`).join(' ')
    lines.push([x.name, x.sales, x.total, x.average_sale, x.returns, x.returns_total, x.discounts, x.price_edits, x.shifts, diff].map(cell).join(','))
  }
  const blob = new Blob([String.fromCharCode(0xfeff) + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `cashiers-${r.from_date}-${r.to_date}.csv`
  link.click()
  setTimeout(() => URL.revokeObjectURL(link.href), 1000)
}
</script>

<style scoped>
.rep { flex: 1; display: flex; align-items: flex-start; min-height: 0; overflow: auto; }
.rep-card { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.rep-head { display: flex; align-items: center; gap: 10px; padding: 14px; border-bottom: 1px solid var(--border); }
.rep-title { font-weight: 700; font-size: 16px; }
.range { padding: 10px 14px 4px; }
.empty { padding: 26px; text-align: center; }
.neg { color: var(--red); }
.note { padding: 10px 14px 14px; }
.wrap { overflow-x: auto; }
.rt { width: 100%; border-collapse: collapse; font-size: 13px; }
.rt th { text-align: start; font-weight: 600; color: var(--text-muted); font-size: 12px; padding: 8px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; }
.rt td { padding: 9px 10px; border-bottom: 1px solid var(--border-subtle); vertical-align: top; }
.rt .num { text-align: end; white-space: nowrap; font-variant-numeric: tabular-nums; }
.rt .strong { font-weight: 700; }
.rt .who { min-width: 140px; }
.count-line { display: block; white-space: nowrap; }
.ok { color: var(--text-muted); }
.short { color: var(--red); font-weight: 600; }
.over { color: var(--amber); font-weight: 600; }
@media (max-width: 600px) {
  .rep-head { flex-wrap: wrap; }
}
</style>
