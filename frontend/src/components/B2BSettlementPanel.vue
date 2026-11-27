<template>
  <section class="b2b-payment-panel">
    <header class="b2b-section-heading"><div><h2>{{ t('Customer settlement') }}</h2><p class="muted">{{ t('Settle invoices, receive a deposit, or use an existing advance.') }}</p></div><button class="btn btn-outline" :disabled="busy || offline" @click="emit('refresh')"><Icon name="refresh" /> {{ t('Refresh balances') }}</button></header>
    <p v-if="!options.can_pay" class="b2b-notice">{{ t('Customer payment capability and Payment Entry permissions are required to post collections.') }}</p>
    <p v-if="error" class="b2b-error" role="alert">{{ error }}</p>
    <nav class="b2b-subtabs" :aria-label="t('Settlement type')"><button :class="{active: operation === 'receive'}" @click="operation = 'receive'">{{ t('Receive payment') }}</button><button v-if="account.can_reconcile" :class="{active: operation === 'advance'}" @click="operation = 'advance'">{{ t('Apply advance') }}</button></nav>
    <div class="b2b-payment-layout">
      <div>
        <div class="b2b-choice-row"><label><input v-model="allocationMode" type="radio" value="oldest" @change="touch" />{{ t('Oldest invoices first') }}</label><label><input v-model="allocationMode" type="radio" value="selected" @change="touch" />{{ t('Selected invoices') }}</label><label v-if="operation === 'receive'"><input v-model="allocationMode" type="radio" value="deposit" @change="touch" />{{ t('Customer deposit / advance') }}</label></div>
        <p v-if="focus?.doctype === 'Sales Order'" class="b2b-notice">{{ t('Advance for order') }} <b>{{ focus.name }}</b></p>
        <div v-if="allocationMode !== 'deposit'" class="b2b-table-wrap"><table><thead><tr><th v-if="allocationMode === 'selected'"></th><th>{{ t('Invoice') }}</th><th>{{ t('Due date') }}</th><th class="b2b-num">{{ t('Outstanding') }}</th><th>{{ t('Allocate') }}</th></tr></thead><tbody><tr v-for="row in account.invoices || []" :key="row.name"><td v-if="allocationMode === 'selected'"><input v-model="chosen" type="checkbox" :value="row.name" :aria-label="row.name" @change="touch" /></td><td><b>{{ row.name }}</b><small>{{ row.posting_date }}</small></td><td>{{ row.due_date || '—' }}</td><td class="b2b-num">{{ money(row.outstanding_amount, options.currency) }}</td><td><input v-if="allocationMode === 'selected'" v-model.number="amounts[row.name]" type="number" min="0" :max="row.outstanding_amount" step="0.01" :disabled="!chosen.includes(row.name)" :aria-label="t('Allocate to {invoice}', {invoice:row.name})" @input="touch" /><span v-else>{{ money(previewAllocations.find(item => item.name === row.name)?.amount || 0, options.currency) }}</span></td></tr><tr v-if="!account.invoices?.length"><td colspan="5" class="b2b-empty">{{ t('No open company-currency invoices.') }}</td></tr></tbody></table></div>
        <div v-else class="b2b-empty"><Icon name="bank" :size="32" /><h3>{{ t('Receive an advance') }}</h3><p>{{ t('The receipt stays available on this customer account until applied to an invoice.') }}</p></div>
        <div v-if="operation === 'advance'" class="b2b-fields b2b-padded"><label>{{ t('Available advance') }}<select v-model="advanceKey" @change="selectAdvance"><option value="">{{ t('Select advance') }}</option><option v-for="(row, index) in account.advances || []" :key="index" :value="String(index)">{{ row.name }} — {{ money(row.amount, options.currency) }}</option></select></label><label>{{ t('Amount to apply') }}<input v-model.number="advanceAmount" type="number" min="0.01" :max="advance?.amount" step="0.01" @input="touch" /></label></div>
      </div>
      <aside class="b2b-settlement-form">
        <template v-if="operation === 'receive'">
          <div class="b2b-fields"><label>{{ t('Collection context') }}<select v-model="collectionContext" @change="touch"><option value="Till">{{ t('Till collection') }}</option><option value="Back office">{{ t('Back-office collection') }}</option></select></label><label>{{ t('Receipt date') }}<input v-model="postingDate" type="date" :max="options.today" :disabled="collectionContext === 'Till'" @change="touch" /></label></div>
          <p v-if="collectionContext === 'Till' && !session.registerOpen" class="b2b-error">{{ t('Open the register to collect at the till, or choose back office.') }}</p>
          <article v-for="(row, index) in tenders" :key="row.key" class="b2b-tender">
            <header><strong>{{ t('Payment') }} {{ index + 1 }}</strong><button v-if="tenders.length > 1" class="b2b-icon-button" :aria-label="t('Remove payment')" @click="tenders.splice(index, 1); touch()"><Icon name="close" /></button></header>
            <div class="b2b-fields"><label>{{ t('Method') }}<select v-model="row.method" @change="changeMethod(row)"><option>Cash</option><option>Bank Transfer</option><option v-if="options.can_cheque">Cheque</option></select></label><label>{{ t('Amount') }}<input v-model.number="row.amount" type="number" min="0.01" step="0.01" inputmode="decimal" @input="touch" /></label><label class="b2b-wide">{{ t('Account / mode') }}<select v-model="row.mode_of_payment" @change="touch"><option v-for="mode in modesFor(row.method)" :key="mode.name" :value="mode.name">{{ mode.name }} — {{ mode.account }}</option></select></label></div>
            <div v-if="row.method !== 'Cash'" class="b2b-fields"><label>{{ t(row.method === 'Cheque' ? 'Cheque number' : 'Transfer reference') }}<input v-model="row.reference_no" @input="touch" /></label><label>{{ t(row.method === 'Cheque' ? 'Cheque date' : 'Transfer date') }}<input v-model="row.reference_date" type="date" @change="touch" /></label><label v-if="row.method === 'Cheque'" class="b2b-wide">{{ t('Issuing bank') }}<input v-model="row.bank" @input="touch" /></label></div>
            <p v-if="row.method === 'Cheque'" class="b2b-notice small">{{ t('Pending until bank clearance. This cheque does not reduce the outstanding balance yet.') }}</p>
          </article>
          <button class="btn btn-outline" :disabled="tenders.length >= 20 || busy" @click="addTender"><Icon name="plus" /> {{ t('Add split payment') }}</button>
        </template>
        <div class="b2b-payment-total"><span>{{ t(operation === 'advance' ? 'Advance to apply' : 'Total received / held') }}</span><strong>{{ money(total, options.currency) }}</strong></div>
        <div class="b2b-summary-line"><span>{{ t('Allocate to invoices') }}</span><b>{{ money(allocated, options.currency) }}</b></div>
        <div class="b2b-summary-line"><span>{{ t('Remaining as advance') }}</span><b>{{ money(excess, options.currency) }}</b></div>
        <label v-if="excess > 0 && allocationMode !== 'deposit' && operation === 'receive'" class="b2b-check b2b-padded"><input v-model="keepAdvance" type="checkbox" @change="touch" />{{ t('Keep excess as customer advance') }}</label>
        <p v-if="pending > 0" class="b2b-notice">{{ t('Awaiting cheque clearance') }}: {{ money(pending, options.currency) }}</p>
        <button class="btn btn-primary b2b-full" :disabled="!canPost" @click="post"><Icon name="check" /> {{ busy ? t('Posting…') : t(operation === 'advance' ? 'Apply advance' : 'Confirm settlement') }}</button>
      </aside>
    </div>
    <section v-if="receipt" class="b2b-receipt-section">
      <div ref="receiptElement" class="b2b-receipt"><h2>{{ t('Customer settlement receipt') }}</h2><p><b>{{ receipt.customer_name }}</b> · {{ receipt.company }} · {{ receipt.posting_date }}</p><p>{{ receipt.name }} · {{ t(receipt.collection_context) }}</p><table><thead><tr><th>{{ t('Method / reference') }}</th><th>{{ t('Status') }}</th><th class="b2b-num">{{ t('Amount') }}</th></tr></thead><tbody><tr v-for="(row, index) in receipt.rows" :key="index"><td>{{ row.mode_of_payment || row.method }}<small>{{ row.reference_no || row.source }} {{ row.reference_date }}</small><small v-for="ref in row.allocations" :key="ref.reference_name">{{ ref.reference_name }}: {{ money(ref.allocated_amount, receipt.currency) }}</small></td><td>{{ row.cheque ? t(row.status === 'Cleared' ? 'Cleared' : row.status === 'Received' || row.status === 'Deposited' ? 'Awaiting clearance' : row.status) : row.docstatus === 2 ? t('Cancelled') : t(row.method === 'Existing advance' ? 'Advance allocated' : 'Posted') }}<small>{{ row.payment || row.cheque }}</small></td><td class="b2b-num">{{ money(row.amount, receipt.currency) }}</td></tr></tbody></table><p>{{ t('Cheques awaiting clearance are excluded from settled payments.') }}</p></div>
      <button class="btn btn-outline" :disabled="busy || offline" @click="printReceipt"><Icon name="download" /> {{ t('Print receipt') }}</button>
    </section>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import Icon from './Icon.vue'
import { call } from '../api'
import { money } from '../format'
import { newId } from '../offline'
import { useSessionStore } from '../stores/session'
import { printB2BReceipt } from '../b2bPrinting'
import { t } from '../i18n'

const props = defineProps({ options: Object, account: Object, customer: Object, profile: String, focus: Object, offline: Boolean, existingReceipt: Object })
const emit = defineEmits(['refresh', 'dirty', 'busy'])
const session = useSessionStore(), operation = ref('receive'), allocationMode = ref('oldest'), chosen = ref([]), amounts = ref({}), tenders = ref([])
const collectionContext = ref(session.registerOpen ? 'Till' : 'Back office'), postingDate = ref(props.options.today), keepAdvance = ref(false), error = ref(''), busy = ref(false)
const receipt = ref(props.existingReceipt || null), receiptElement = ref(null), advanceKey = ref(''), advanceAmount = ref(0)
let attempt = null
const modesFor = method => (props.options.payment_modes || []).filter(mode => mode.type === (method === 'Cash' ? 'Cash' : 'Bank'))
const preferredMode = method => modesFor(method).find(mode => (method === 'Cheque' ? /cheque|check/i : method === 'Cash' ? /cash/i : /bank|transfer/i).test(mode.name)) || modesFor(method)[0]
function addTender() { const method = modesFor('Cash').length ? 'Cash' : 'Bank Transfer'; tenders.value.push({ key: newId(), method, amount: 0, mode_of_payment: modesFor(method)[0]?.name || '', reference_no: '', reference_date: props.options.today, bank: '' }) }
addTender()
const advance = computed(() => props.account.advances?.[Number(advanceKey.value)] && advanceKey.value !== '' ? props.account.advances[Number(advanceKey.value)] : null)
const roundCurrency = value => Math.round(value * 10 ** (props.options.currency_precision ?? 2)) / 10 ** (props.options.currency_precision ?? 2)
const total = computed(() => operation.value === 'advance' ? Number(advanceAmount.value || 0) : roundCurrency(tenders.value.reduce((sum, row) => sum + Number(row.amount || 0), 0)))
const previewAllocations = computed(() => {
  if (allocationMode.value === 'deposit') return []
  let left = total.value
  return (props.account.invoices || []).filter(row => allocationMode.value === 'oldest' || chosen.value.includes(row.name)).map(row => {
    const amount = allocationMode.value === 'selected' ? Number(amounts.value[row.name] || 0) : Math.min(Number(row.outstanding_amount), Math.max(left, 0))
    left -= amount; return { name: row.name, amount }
  }).filter(row => row.amount > 0)
})
const allocated = computed(() => roundCurrency(previewAllocations.value.reduce((sum, row) => sum + row.amount, 0)))
const excess = computed(() => Math.max(0, roundCurrency(total.value - allocated.value)))
const pending = computed(() => tenders.value.filter(row => row.method === 'Cheque').reduce((sum, row) => sum + Number(row.amount || 0), 0))
const canPost = computed(() => !props.offline && !busy.value && props.options.can_pay && total.value > 0 && allocated.value <= total.value &&
  (allocationMode.value !== 'selected' || previewAllocations.value.length > 0) &&
  (operation.value === 'advance' ? advance.value && excess.value === 0 && total.value <= advance.value.amount :
    (collectionContext.value !== 'Till' || session.registerOpen) && tenders.value.every(row => row.amount > 0 && row.mode_of_payment && (row.method === 'Cash' || row.reference_no.trim() && row.reference_date) && (row.method !== 'Cheque' || row.bank.trim())) &&
    (excess.value === 0 || keepAdvance.value || allocationMode.value === 'deposit')))
watch(() => props.account.invoices, rows => { for (const row of rows || []) if (amounts.value[row.name] === undefined) amounts.value[row.name] = Number(row.outstanding_amount) }, { immediate: true })
watch(() => props.focus, focus => {
  if (!focus) return
  if (focus.doctype === 'Sales Order') allocationMode.value = 'deposit'
  else { allocationMode.value = 'selected'; chosen.value = [focus.name]; amounts.value[focus.name] = focus.outstanding_amount }
  tenders.value[0].amount = focus.outstanding_amount || focus.grand_total || 0
}, { immediate: true })
watch(() => props.existingReceipt, value => { receipt.value = value })
watch(busy, value => emit('busy', value))
function touch() { emit('dirty', true); error.value = '' }
function changeMethod(row) { row.mode_of_payment = preferredMode(row.method)?.name || ''; touch() }
function selectAdvance() { advanceAmount.value = advance.value?.amount || 0; if (allocationMode.value === 'deposit') allocationMode.value = 'oldest'; touch() }
async function post() {
  if (!canPost.value) return
  busy.value = true; error.value = ''
  try {
    let method, args
    if (operation.value === 'advance') {
      method = 'esafepos.api.b2b_payments.apply_advance'
      args = { pos_profile: props.profile, customer: props.customer.name, payment_doctype: advance.value.doctype, payment: advance.value.name,
        reference_row: advance.value.reference_row, allocations: previewAllocations.value }
    } else {
      method = 'esafepos.api.b2b_payments.receive_settlement'
      args = { pos_profile: props.profile, payload: { customer: props.customer.name, collection_context: collectionContext.value, posting_date: collectionContext.value === 'Till' ? props.options.today : postingDate.value,
        allocations: allocationMode.value === 'selected' ? previewAllocations.value : [], tenders: tenders.value.map(({ key, ...row }) => row),
        as_advance: allocationMode.value === 'deposit' ? 1 : 0, keep_advance: keepAdvance.value ? 1 : 0,
        sales_order: props.focus?.doctype === 'Sales Order' && allocationMode.value === 'deposit' ? props.focus.name : null } }
    }
    const signature = JSON.stringify({ method, args }); if (!attempt || attempt.signature !== signature) attempt = { signature, key: newId() }
    receipt.value = await call(method, { ...args, idempotency_key: attempt.key }, { timeout: 60000 })
    attempt = null; tenders.value = []; addTender(); advanceAmount.value = 0; emit('dirty', false); emit('refresh'); session.notify(t('Customer settlement recorded'))
  } catch (err) { error.value = err.message; session.notify(err.message, true) } finally { busy.value = false }
}
async function printReceipt() { try { busy.value = true; await printB2BReceipt(receiptElement.value, { doctype: receipt.value.doctype, name: receipt.value.name }) } catch (err) { error.value = err.message } finally { busy.value = false } }
onBeforeUnmount(() => emit('busy', false))
</script>
