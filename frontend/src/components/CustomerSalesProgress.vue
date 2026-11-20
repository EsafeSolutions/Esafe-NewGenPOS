<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<template>
  <section class="sales-progress card">
    <header class="sp-head">
      <div>
        <h3>{{ t('Sales Rep Progress') }}</h3>
        <p class="muted small">{{ t('ERPNext selling documents and open customer tasks.') }}</p>
      </div>
      <button class="btn btn-outline btn-sm" :disabled="loading" @click="load">{{ loading ? t('Loading.') : t('Refresh') }}</button>
    </header>
    <p v-if="session.offline" class="muted small">{{ t('Customer sales progress needs a connection to ERPNext.') }}</p>
    <p v-else-if="error" class="sp-error small">{{ error }}</p>
    <template v-else-if="data">
      <div class="sp-summary">
        <article class="sp-total"><span>{{ t('Outstanding') }}</span><strong>{{ money(data.outstanding, data.currency) }}</strong></article>
        <article class="sp-total"><span>{{ t('Goods to deliver') }}</span><strong>{{ data.goods_to_deliver.qty }} {{ t('items') }}</strong><small>{{ money(data.goods_to_deliver.value, data.currency) }}</small></article>
        <article class="sp-total"><span>{{ t('Total paid') }}</span><strong>{{ money(data.payment_totals.total, data.currency) }}</strong></article>
      </div>

      <div class="sp-flow" aria-label="Quotation to payment progress">
        <article v-for="stage in stageRows" :key="stage.key" class="sp-stage">
          <div class="sp-stage-title">{{ t(stage.label) }}</div>
          <strong>{{ stage.rows.length }}</strong>
          <span>{{ t('documents') }}</span>
          <div class="sp-stage-list">
            <a v-for="row in stage.rows.slice(0, 4)" :key="row.name" :href="`/app/${stage.route}/${encodeURIComponent(row.name)}`" target="_blank" rel="noopener">
              <span class="mono">{{ row.name }}</span>
              <span class="muted">{{ row.status || row.posting_date || row.transaction_date }}</span>
              <span class="right">{{ money(row.grand_total, row.currency || data.currency) }}</span>
            </a>
            <span v-if="!stage.rows.length" class="muted small">{{ t('None') }}</span>
          </div>
        </article>
      </div>

      <section class="sp-subsection">
        <h4>{{ t('Payments received') }}</h4>
        <div class="sp-payment-totals">
          <span>{{ t('Cash') }} <b>{{ money(data.payment_totals.cash, data.currency) }}</b></span>
          <span>{{ t('Cheque') }} <b>{{ money(data.payment_totals.cheque, data.currency) }}</b></span>
          <span>{{ t('Bank transfer') }} <b>{{ money(data.payment_totals.bank_transfer, data.currency) }}</b></span>
          <span>{{ t('Other') }} <b>{{ money(data.payment_totals.other, data.currency) }}</b></span>
        </div>
        <div v-if="data.payments.length" class="sp-table-wrap">
          <table class="sp-table">
            <thead><tr><th>{{ t('Receipt') }}</th><th>{{ t('Date') }}</th><th>{{ t('Paid by') }}</th><th>{{ t('Reference') }}</th><th>{{ t('Reference date') }}</th><th class="right">{{ t('Amount') }}</th></tr></thead>
            <tbody><tr v-for="row in data.payments" :key="row.name">
              <td class="mono">{{ row.name }}</td><td>{{ row.posting_date }}</td><td>{{ row.mode_of_payment || t('Unknown') }}</td>
              <td>{{ row.reference_no || '—' }}</td><td>{{ row.reference_date || '—' }}</td>
              <td class="right">{{ money(row.base_paid_amount || row.received_amount || row.paid_amount, row.currency || data.currency) }}</td>
            </tr></tbody>
          </table>
        </div>
        <p v-else class="muted small">{{ t('No payments found') }}</p>
      </section>

      <section class="sp-subsection">
        <h4>{{ t('Pending tasks') }} <span class="sp-count">{{ data.pending_tasks.length }}</span></h4>
        <ul v-if="data.pending_tasks.length" class="sp-tasks">
          <li v-for="task in data.pending_tasks" :key="task.name">
            <span>{{ task.description || task.name }}</span><span class="muted small">{{ task.date || t('No due date') }}</span>
            <span v-if="task.allocated_to" class="muted small">{{ task.allocated_to }}</span>
          </li>
        </ul>
        <p v-else class="muted small">{{ t('No pending tasks') }}</p>
      </section>
      <footer class="sp-foot muted small">{{ t('Updated') }} {{ data.refreshed_at }}</footer>
    </template>
    <p v-else-if="loading" class="muted small">{{ t('Loading customer sales progress.') }}</p>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { call } from '../api'
import { money } from '../format'
import { useSessionStore } from '../stores/session'
import { t } from '../i18n'

const props = defineProps({ customer: { type: String, required: true }, company: { type: String, default: null } })
const session = useSessionStore()
const data = ref(null)
const loading = ref(false)
const error = ref('')

const stageRows = computed(() => [
  { key: 'quotations', label: 'Quotations', route: 'quotation', rows: data.value?.stages?.quotations || [] },
  { key: 'sales_orders', label: 'Sales Orders', route: 'sales-order', rows: data.value?.stages?.sales_orders || [] },
  { key: 'delivery_notes', label: 'Delivery Notes', route: 'delivery-note', rows: data.value?.stages?.delivery_notes || [] },
  { key: 'sales_invoices', label: 'Sales Invoices', route: 'sales-invoice', rows: data.value?.stages?.sales_invoices || [] },
])

async function load() {
  if (!props.customer || session.offline) return
  loading.value = true
  error.value = ''
  try {
    data.value = await call('esafepos.api.customers.customer_sales_progress', {
      customer: props.customer,
      company: props.company || session.company,
    })
  } catch (e) {
    error.value = e.message || t('Could not load customer sales progress.')
  } finally {
    loading.value = false
  }
}

watch(() => [props.customer, props.company], load, { immediate: true })
</script>

<style scoped>
.sales-progress { margin: 14px 0; padding: 14px; display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.sp-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.sp-head h3, .sp-subsection h4 { margin: 0; }
.sp-head p { margin: 4px 0 0; }
.sp-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; }
.sp-total { min-width: 0; display: flex; flex-direction: column; gap: 4px; background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius); padding: 10px; }
.sp-total > span, .sp-total small { color: var(--text-muted); font-size: 12px; }
.sp-total strong { overflow-wrap: anywhere; font-size: 16px; }
.sp-flow { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.sp-stage { min-width: 0; border: 1px solid var(--border); border-radius: var(--radius); padding: 10px; }
.sp-stage-title { font-size: 13px; font-weight: 700; }
.sp-stage > strong { font-size: 21px; margin-inline-end: 5px; }
.sp-stage > span { color: var(--text-muted); font-size: 11px; }
.sp-stage-list { display: flex; flex-direction: column; gap: 4px; margin-top: 8px; max-height: 140px; overflow: auto; }
.sp-stage-list a { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px 8px; text-decoration: none; font-size: 11.5px; }
.sp-stage-list a .right { grid-column: 1 / -1; text-align: end; }
.sp-subsection { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.sp-payment-totals { display: flex; gap: 8px; flex-wrap: wrap; }
.sp-payment-totals span { display: flex; gap: 6px; align-items: center; border: 1px solid var(--border); border-radius: 999px; padding: 6px 10px; font-size: 12px; }
.sp-table-wrap { max-width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }
.sp-table { width: 100%; min-width: 680px; border-collapse: collapse; font-size: 12px; }
.sp-table th, .sp-table td { text-align: start; padding: 8px 6px; border-bottom: 1px solid var(--border); white-space: nowrap; }
.sp-table .right { text-align: end; }
.sp-tasks { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.sp-tasks li { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 10px; padding: 8px; background: var(--surface-2); border-radius: var(--radius); }
.sp-count { border-radius: 99px; padding: 2px 8px; background: var(--surface-2); font-size: 12px; }
.sp-foot { text-align: end; }
.sp-error { color: var(--red); margin: 0; }
.mono { font-family: var(--mono); }
@media (max-width: 900px) { .sp-flow { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 560px) {
  .sales-progress { padding: 12px; }
  .sp-summary { grid-template-columns: 1fr; }
  .sp-flow { grid-template-columns: 1fr; }
  .sp-stage-list { max-height: 116px; }
  .sp-tasks li { grid-template-columns: 1fr auto; }
  .sp-tasks li span:first-child { grid-column: 1 / -1; }
}
</style>
