<template>
  <div class="register-details">
    <div class="register-metrics">
      <div v-for="metric in metrics" :key="metric.label" class="register-metric"><span><Icon :name="metric.icon" /> {{ t(metric.label) }}</span><strong>{{ metric.value }}</strong><small>{{ metric.hint }}</small></div>
    </div>
    <details v-if="summary.customer_cheques?.length" class="tally-guide">
      <summary><Icon name="clock" /> {{ t('Customer cheques received in this shift') }} ({{ summary.customer_cheques.length }})</summary>
      <p class="muted small">{{ t('Custody only. Pending cheques are excluded from cash and bank payment tallies; clearance is posted separately.') }}</p>
      <p v-for="row in summary.customer_cheques" :key="row.name">{{ row.reference_no }} · {{ row.cheque_date }} · {{ money(row.amount, currency) }} · {{ t(row.status) }}</p>
    </details>
    <details class="tally-guide" :open="guideOpen">
      <summary><Icon name="help" /> {{ t('How payment tallies and the cash balance work') }}</summary>
      <div class="tally-guides">
        <p><Icon name="cash" /><span><b>{{ t('Cash drawer') }}</b>{{ t('Opening float + net cash payments + cash in − cash out = expected cash. Net payments include cash sales and debt collections, less refunds and change. Saved change stays in the drawer as a recorded cash in. Count every note and coin, including the float, once.') }}</span></p>
        <p><Icon name="card" /><span><b>{{ t('Credit / debit cards') }}</b>{{ t('Compare each card method with its terminal or provider batch: captured payments less refunds. Count the gross batch before bank fees. Card receipts do not add cash to the drawer.') }}</span></p>
        <p><Icon name="bank" /><span><b>{{ t('Bank transfers') }}</b>{{ t('Match received transfers and refund debits to bank records and payment references. A transfer screenshot or QR scan alone does not prove receipt. Bank transfers do not add drawer cash.') }}</span></p>
        <p><Icon name="person" /><span><b>{{ t('Accounts and points') }}</b>{{ t('Sales on account are customer debt, not received money. Later collections enter the method used. Redeemed points pay part of a sale without adding cash; saved-change funding is already in cash in. Do not add it twice.') }}</span></p>
      </div>
      <p class="tally-key"><span>✓ {{ t('Tallied: counted equals expected') }}</span><span>− {{ t('Short: counted is lower') }}</span><span>+ {{ t('Over: counted is higher') }}</span></p>
      <p class="muted small">{{ t('Recount a difference, check payment methods, refunds and unuploaded sales, then record the reason. For a wrong payment method, use the return and corrected-sale workflow before closing.') }}</p>
    </details>
    <div class="payment-breakdown">
      <div v-for="row in summary.expected || []" :key="row.mode_of_payment" class="payment-tally">
        <div class="payment-tally-head"><span><Icon :name="paymentIcon(row)" /> {{ row.mode_of_payment }}</span><strong>{{ money(row.expected_amount, row.currency || currency) }}</strong></div>
        <p v-if="row.is_cash" class="muted small">{{ t('Float') }} {{ money(row.opening_float || 0, row.currency || currency) }} + {{ t('net payments') }} {{ money(row.net_payments ?? row.expected_amount, row.currency || currency) }} + {{ t('cash in') }} {{ money(row.cash_in || 0, row.currency || currency) }} − {{ t('cash out') }} {{ money(row.cash_out || 0, row.currency || currency) }}</p>
        <p v-else class="muted small">{{ t('Payments and collections less refunds; compare with the terminal or bank records.') }}</p>
      </div>
    </div>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import { money } from '../format'
import { t } from '../i18n'
import Icon from './Icon.vue'
const props = defineProps({ summary: { type: Object, required: true }, guideOpen: Boolean })
const currency = computed(() => props.summary.company_currency)
function paymentIcon(row) {
  if (row.is_cash) return 'cash'
  if (/card|visa|master|amex|mada/i.test(row.mode_of_payment)) return 'card'
  return row.payment_type === 'Bank' ? 'bank' : 'ticket'
}
const metrics = computed(() => {
  const s = props.summary, a = s.activity || {}, cash = value => money(value || 0, currency.value)
  return [
    { label: 'Net sales', icon: 'report', value: cash(s.total_sales), hint: t('Sales less returns, including account sales') },
    { label: 'Sales', icon: 'store', value: cash(a.sales ?? s.total_sales), hint: t('{n} sale(s)', { n: a.sale_count ?? s.sales_count }) },
    { label: 'Returns', icon: 'return', value: cash(a.returns), hint: t('{n} return(s)', { n: a.return_count || 0 }) },
    { label: 'Sales on account', icon: 'person', value: cash(s.on_account), hint: t('Net debt added; excluded from payment counts') },
    { label: 'Discounts / savings', icon: 'tag', value: cash(s.total_discounts), hint: t('Line and invoice discounts, net of returns') },
    { label: 'Customer collections', icon: 'cash', value: cash(s.customer_payments_total), hint: t('{n} collection(s), included in payments', { n: s.customer_payments?.length || 0 }) },
    { label: 'Change saved as points', icon: 'gift', value: `${a.esafepos_loyalty_change_amount || 0} ${t('points')}`, hint: cash(a.esafepos_loyalty_change_amount) + ' · ' + t('Already included in cash in') },
    { label: 'Points redeemed', icon: 'ticket', value: `${a.loyalty_points || 0} ${t('points')}`, hint: cash(a.loyalty_amount) + ' · ' + t('No drawer cash received') },
    { label: 'Purchase points earned', icon: 'gift', value: `${a.earned_points || 0} ${t('points')}`, hint: t('Purchase awards; saved change shown separately') },
  ]
})
</script>
<style scoped>
.register-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0; border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
.register-metric { min-width: 0; padding: 16px; border-bottom: 1px solid var(--border-subtle); }
.register-metric > span, .payment-tally-head > span { display: flex; align-items: center; gap: 7px; font-size: 12px; color: var(--text-muted); }
.register-metric strong { display: block; font-size: clamp(17px, 1.65vw, 23px); margin: 8px 0 4px; overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
.register-metric small { display: block; color: var(--text-muted); font-size: 11px; line-height: 1.5; }
.tally-guide { margin: 16px 0; padding: 14px; background: var(--surface-2); border-radius: var(--radius); }
.tally-guide summary { cursor: pointer; font-weight: 600; line-height: 1.5; }
.tally-guides { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-top: 18px; }
.tally-guides p { display: flex; align-items: flex-start; gap: 10px; margin: 0; font-size: 12px; line-height: 1.6; }
.tally-guides .icon { flex-shrink: 0; margin-top: 3px; color: var(--brand-dark); }
.tally-guides b { display: block; font-size: 13px; }
.tally-key { display: flex; flex-wrap: wrap; gap: 14px; font-size: 12px; margin-top: 18px; }
.payment-breakdown { display: grid; gap: 8px; }
.payment-tally { padding: 12px 0; border-bottom: 1px solid var(--border-subtle); }
.payment-tally-head { display: flex; justify-content: space-between; gap: 12px; }
.payment-tally-head > span { font-size: 14px; color: var(--text); }
.payment-tally p { margin: 6px 0 0; line-height: 1.6; }
@media (max-width: 600px) { .register-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } .tally-guides { grid-template-columns: minmax(0, 1fr); } .register-metric { padding: 12px; } }
</style>
