<template>
  <section class="all-registers">
    <header class="all-heading"><div><span class="eyebrow"><Icon name="store" /> {{ t('Register control') }}</span><h1>{{ t('All registers') }}</h1><p class="muted">{{ t('Review each shift, adjust drawer cash, and count payments before closing.') }}</p></div><button class="btn btn-outline" :disabled="busy || loading || session.offline" @click="refresh"><Icon name="refresh" :class="{ spinning: loading }" /> {{ t('Refresh all') }}</button></header>
    <p v-if="session.offline" class="hub-notice">{{ t('Connect to load current totals, switch registers, adjust cash or close shifts.') }}</p>
    <p v-if="error" role="alert" class="neg hub-notice">{{ error }}</p>
    <div class="hub-toolbar"><span>{{ t('{n} open register(s)', { n: registers.length }) }}</span><button v-if="session.permissions.is_manager && canClose" class="btn btn-primary" :disabled="loading || busy || !registers.length || session.offline" @click="reviewAll = !reviewAll"><Icon name="check" /> {{ reviewAll ? t('Exit closing review') : t('Review and close all registers') }}</button></div>
    <div v-if="reviewAll" class="hub-notice"><b>{{ t('Count every register separately') }}</b><p>{{ t('Stop sales on every till and upload its offline queue. Enter each payment total, review any difference, and tick Reviewed. Linked physical drawers use their combined count below. Closing all runs one shift at a time; a failed close stops the remaining shifts.') }}</p></div>
    <p v-if="loading && !registers.length" role="status">{{ t('Loading registers…') }}</p>
    <p v-if="!loading && !registers.length && !error" class="hub-notice">{{ t('No open registers are available. Open a shift from This register.') }}</p>
    <article v-for="entry in registers" :key="entry.session" class="card hub-register" :class="{ 'is-reviewed': entry.reviewed }">
      <header class="hub-register-head"><div><span class="hub-status"><Icon :name="entry.closed ? 'check' : 'store'" /> {{ entry.closed ? t('Closing') : t('Open') }}</span><h2>{{ entry.pos_profile }}</h2><p class="muted small">{{ entry.session }} · {{ entry.opened_by_name || entry.opened_by }} · {{ shortTime(entry.opened_at) }}</p></div><div class="hub-actions"><button v-if="entry.pos_profile !== session.posProfile" class="btn btn-outline" :disabled="busy || loading || session.offline" @click="switchTo(entry)"><Icon name="exchange" /> {{ t('Switch register') }}</button><button class="btn btn-outline" :aria-expanded="expanded === entry.session" :disabled="busy" @click="expanded = expanded === entry.session ? '' : entry.session"><Icon name="detail" /> {{ t('Full summary / adjust / close') }}</button></div></header>
      <p v-if="entry.error" role="alert" class="neg hub-notice">{{ entry.error }} <button class="btn btn-outline" :disabled="busy" @click="reloadEntry(entry)">{{ t('Retry summary') }}</button></p>
      <div v-if="entry.summary" class="hub-quick"><span>{{ t('Net sales') }} <b>{{ money(entry.summary.total_sales, entry.summary.company_currency) }}</b></span><span>{{ t('Returns') }} <b>{{ money(entry.summary.activity?.returns || 0, entry.summary.company_currency) }}</b></span><span>{{ t('On account') }} <b>{{ money(entry.summary.on_account || 0, entry.summary.company_currency) }}</b></span><span><Icon name="gift" /> {{ t('Points saved') }} <b>{{ entry.summary.activity?.esafepos_loyalty_change_amount || 0 }}</b></span></div>
      <Transition name="register-panel">
        <div v-if="entry.summary && (expanded === entry.session || reviewAll)" class="hub-register-body">
          <RegisterSummary :summary="entry.summary" />
          <details v-if="entry.summary.cash_movements?.length" class="hub-movements"><summary>{{ t('Cash movement log') }} ({{ entry.summary.cash_movements.length }})</summary><p v-for="(movement, index) in entry.summary.cash_movements" :key="index" class="small">{{ movement.movement_type }} · {{ money(movement.amount, movement.currency) }} · {{ movement.reason }} · {{ movement.recorded_by }} · {{ shortTime(movement.recorded_at) }}</p></details>
          <details v-if="mayManage(entry) && (session.permissions.can_cash_in !== false || session.permissions.can_cash_out !== false) && !entry.closed" class="hub-adjust"><summary><Icon name="cash" /> {{ t('Adjust drawer cash') }}</summary><p class="muted small">{{ t('Record physical money added or removed. This keeps the opening float and sales intact and records who made the adjustment.') }}</p><div class="hub-adjust-form"><select v-model="entry.movement.type" :aria-label="t('Adjustment type')"><option v-if="session.permissions.can_cash_in !== false" value="Cash In">{{ t('Cash In') }}</option><option v-if="session.permissions.can_cash_out !== false" value="Cash Out">{{ t('Cash Out') }}</option></select><select v-model="entry.movement.mode" :aria-label="t('Cash drawer')"><option v-for="row in entry.summary.expected.filter(r => r.is_cash)" :key="row.mode_of_payment" :value="row.mode_of_payment">{{ row.mode_of_payment }} · {{ row.currency }}</option></select><input v-model="entry.movement.amount" inputmode="decimal" :placeholder="t('Amount')" :aria-label="t('Adjustment amount')" /><input v-model="entry.movement.reason" :placeholder="t('Reason')" :aria-label="t('Adjustment reason')" maxlength="140" /><button class="btn btn-outline" :disabled="busy || session.offline" @click="adjust(entry)"><Icon name="plus" /> {{ t('Record adjustment') }}</button></div></details>
          <SharedDrawerPanel v-if="entry.summary.combined_drawer && !entry.closed && expanded === entry.session" :session-name="entry.session" @closed="groupClosed" />
          <p v-if="entry.summary.combined_drawer" class="hub-notice">{{ t('This shift shares a physical drawer. Open Full summary and use Close all linked shifts for one combined count.') }}</p>
          <div v-else-if="mayManage(entry) && canClose && !entry.closed" class="hub-close">
            <h3><Icon name="check" /> {{ t('Count and reconcile') }}</h3>
            <p class="muted small">{{ t('Difference = counted − expected. Enter 0 explicitly for an empty payment. Count cash including its opening float; use terminal and bank records for non-cash methods.') }}</p>
            <div v-for="row in entry.summary.expected" :key="row.mode_of_payment" class="hub-count"><label><b>{{ row.mode_of_payment }}</b><span class="muted small">{{ t('Expected') }} {{ money(row.expected_amount, row.currency) }}</span><input v-model="entry.counted[row.mode_of_payment]" inputmode="decimal" :aria-label="`${entry.session} ${t('Counted')} ${row.mode_of_payment}`" :placeholder="t('Enter counted total')" :disabled="busy" @input="entry.reviewed = false; delete entry.denominations[row.mode_of_payment]" /></label><span class="hub-difference" :class="difference(entry, row) == null ? '' : Math.abs(difference(entry, row)) < .005 ? 'tallied' : 'neg'">{{ tallyLabel(entry, row) }}</span><CashDenominationCounter v-if="row.is_cash" :currency="row.currency" v-model="entry.denominations[row.mode_of_payment]" :disabled="busy" @count="entry.counted[row.mode_of_payment] = $event; entry.reviewed = false" /></div>
            <VarianceReason v-if="hasVariance(entry) && session.settings.variance_reason_mode !== 'Off'" v-model:reason="entry.reason" v-model:action="entry.action" :required="reasonRequired(entry)" :missing="reasonRequired(entry) && !entry.reason.trim()" :reasons="session.settings.variance_reasons || []" />
            <label class="hub-note"><span class="small">{{ t('Closing note (optional)') }}</span><input v-model="entry.note" maxlength="500" :disabled="busy" /></label>
            <label class="hub-review"><input type="checkbox" v-model="entry.reviewed" :disabled="!valid(entry) || busy" /><span>{{ t('Reviewed: all sales uploaded, payments counted, and this till has stopped selling.') }}</span></label>
            <button v-if="!reviewAll" class="btn btn-danger" :disabled="busy || session.offline || !entry.reviewed || !valid(entry)" @click="closeEntries([entry])">{{ t('Close this register') }}</button>
          </div>
        </div>
      </Transition>
    </article>
    <div v-if="reviewAll && registers.length" class="hub-bulk card"><div><b>{{ t('{done} of {total} independent register(s) ready', { done: independent.filter(e => e.reviewed && valid(e)).length, total: independent.length }) }}</b><p class="muted small">{{ t('Finish linked drawers using their combined closing controls. Each successful close is saved even if a later register fails.') }}</p></div><button class="btn btn-danger" :disabled="busy || loading || session.offline || linkedOpen || !independent.length || independent.some(e => !e.reviewed || !valid(e))" @click="closeEntries(independent)">{{ busy ? t('Closing registers…') : t('Close all registers') }}</button></div>
    <p v-if="result" role="status" class="hub-notice">{{ result }}</p>
    <CashOutApproval v-if="approval" :amount="approval.amount" :currency="approval.currency" :drawer="approval.mode" :reason="approval.reason" :pos-profile="approval.entry.pos_profile" @close="approval = null" @approved="approveAdjustment" />
  </section>
</template>
<script setup>
import { computed, ref, onMounted, watch } from 'vue'
import { call } from '../api'
import { useSessionStore } from '../stores/session'
import { useCartStore } from '../stores/cart'
import { useCatalogStore } from '../stores/catalog'
import { displayReceipt } from '../customerDisplay'
import { money, parseMoney, shortTime } from '../format'
import { invalidCountModes } from '../shiftHelp'
import { t } from '../i18n'
import Icon from './Icon.vue'
import RegisterSummary from './RegisterSummary.vue'
import CashDenominationCounter from './CashDenominationCounter.vue'
import VarianceReason from './VarianceReason.vue'
import SharedDrawerPanel from './SharedDrawerPanel.vue'
import CashOutApproval from './CashOutApproval.vue'
const emit = defineEmits(['changed', 'switched', 'busy'])
const session = useSessionStore(), cart = useCartStore(), catalog = useCatalogStore()
const registers = ref([]), loading = ref(false), busy = ref(false), error = ref(''), result = ref(''), expanded = ref(''), reviewAll = ref(false), approval = ref(null)
watch(busy, value => emit('busy', value), { flush: 'sync' })
const canClose = computed(() => session.permissions.close_register !== false)
const independent = computed(() => registers.value.filter(e => !e.closed && !e.summary?.combined_drawer))
const linkedOpen = computed(() => registers.value.some(e => !e.closed && e.summary?.combined_drawer))
const mayManage = entry => session.permissions.is_manager || entry.opened_by === session.user
async function reloadEntry(entry, preserve = false) {
  entry.error = ''; entry.reviewed = false
  try {
    entry.summary = await call('esafepos.api.register.get_session_summary', { session: entry.session })
    if (entry.summary.status && entry.summary.status !== 'Open') entry.closed = true
    if (!preserve) { entry.counted = {}; entry.denominations = {} }
    entry.movement.mode ||= entry.summary.expected.find(r => r.is_cash)?.mode_of_payment || ''
  } catch (e) { entry.summary = null; entry.error = e.message }
}
async function refresh() {
  if (loading.value || busy.value || session.offline) return
  loading.value = true; error.value = ''
  try {
    const rows = await call('esafepos.api.register.all_registers')
    registers.value = rows.map(row => ({ ...row, summary: null, counted: {}, denominations: {}, reason: '', action: '', note: '', reviewed: false, closed: false, error: '', movement: { type: session.permissions.can_cash_in === false ? 'Cash Out' : 'Cash In', amount: '', reason: '', mode: '' } }))
    for (let i = 0; i < registers.value.length; i += 4) await Promise.all(registers.value.slice(i, i + 4).map(entry => reloadEntry(entry)))
  } catch (e) { registers.value = []; error.value = e.message }
  finally { loading.value = false }
}
function difference(entry, row) { const count = parseMoney(entry.counted[row.mode_of_payment]); return count == null ? null : count - row.expected_amount }
function tallyLabel(entry, row) {
  const delta = difference(entry, row)
  if (delta == null) return t('Awaiting count')
  if (Math.abs(delta) < .005) return '✓ ' + t('Tallied')
  return (delta < 0 ? '− ' + t('Short') : '+ ' + t('Over')) + ' · ' + money(Math.abs(delta), row.currency)
}
function hasVariance(entry) { return (entry.summary?.expected || []).some(row => difference(entry, row) != null && Math.abs(difference(entry, row)) >= .005) }
function reasonRequired(entry) {
  if (session.settings.variance_reason_mode !== 'Required') return false
  const s = entry.summary
  return (s.expected || []).some(row => {
    const delta = difference(entry, row)
    const rate = row.currency && row.currency !== s.company_currency ? s.rates?.[row.currency] : 1
    return Math.abs(delta || 0) * (rate || 1) > (Number(session.settings.variance_reason_threshold) || 0) + .005
  })
}
function valid(entry) {
  return !!entry.summary && !entry.error && !invalidCountModes(entry.summary.expected || [], entry.counted).length &&
    (!reasonRequired(entry) || entry.reason.trim()) && !Object.values(entry.denominations).some(group => group.rows.some(row => !Number.isInteger(Number(row.quantity)) || Number(row.quantity) < 0 || Number(row.quantity) > 10000000))
}
async function switchTo(entry) {
  if (cart.lines.length && !confirm(t('The sale on screen will be cleared. Switch outlet?'))) return
  busy.value = true
  try { cart.clear(); displayReceipt.value = null; await session.switchProfile(entry.pos_profile); await catalog.fetch(); catalog.cacheFullCatalog(); catalog.cacheCustomers(); emit('switched') }
  catch (e) { error.value = e.message }
  finally { busy.value = false }
}
async function adjust(entry) {
  const amount = parseMoney(entry.movement.amount)
  if (!(amount > 0) || !entry.movement.mode || !entry.movement.reason.trim()) { entry.error = t('Choose a cash drawer, enter an amount above zero and write a reason.'); return }
  if (entry.movement.type === 'Cash Out') {
    busy.value = true
    try {
      const check = await call('esafepos.api.register.cash_out_check', { session: entry.session, amount, mode_of_payment: entry.movement.mode })
      if (check.needed) { approval.value = { entry, amount, currency: entry.summary.expected.find(r => r.mode_of_payment === entry.movement.mode)?.currency, mode: entry.movement.mode, reason: entry.movement.reason }; return }
    } catch (e) { entry.error = e.message; return }
    finally { busy.value = false }
  }
  await postAdjustment(entry, amount)
}
async function postAdjustment(entry, amount, credentials = {}) {
  busy.value = true; entry.error = ''
  try { await call('esafepos.api.register.add_cash_movement', { session: entry.session, movement_type: entry.movement.type, amount, reason: entry.movement.reason, mode_of_payment: entry.movement.mode, ...credentials }); entry.movement.amount = ''; entry.movement.reason = ''; await reloadEntry(entry); emit('changed') }
  catch (e) { entry.error = e.message }
  finally { busy.value = false }
}
async function approveAdjustment(credentials) { const request = approval.value; approval.value = null; if (request) await postAdjustment(request.entry, request.amount, { approval_passcode: credentials.passcode || null, approval_request: credentials.request || null }) }
async function closeEntries(entries) {
  if (busy.value || session.offline || entries.some(e => !e.reviewed || !valid(e))) return
  const targets = [...entries]
  if (!confirm(t('Close {n} register(s)? No more sales can be added to these shifts.', { n: targets.length }))) return
  busy.value = true; error.value = ''; result.value = ''; let done = 0, changedActive = false
  try {
    for (const entry of targets) {
      // Preserve counts, but compare every expected amount as well as invoice
      // counts before sending the server's final under-lock close checks.
      const fresh = await call('esafepos.api.register.get_session_summary', { session: entry.session })
      const samePayments = fresh.expected.length === entry.summary.expected.length && fresh.expected.every(row => entry.summary.expected.some(previous => previous.mode_of_payment === row.mode_of_payment && previous.currency === row.currency && Math.abs(previous.expected_amount - row.expected_amount) < .005))
      if (fresh.status !== 'Open' || fresh.combined_drawer || !samePayments || fresh.sales_count !== entry.summary.sales_count || (fresh.customer_payments?.length || 0) !== (entry.summary.customer_payments?.length || 0)) {
        entry.summary = fresh; entry.reviewed = false; expanded.value = entry.session
        throw new Error(t('Register {name} changed. Recheck the payments and review it again.', { name: entry.pos_profile }))
      }
      await call('esafepos.api.register.close_register', { session: entry.session, counted: Object.fromEntries(entry.summary.expected.map(row => [row.mode_of_payment, parseMoney(entry.counted[row.mode_of_payment])])), denomination_counts: entry.denominations, closing_note: entry.note || null, variance_reason: entry.reason || null, variance_action: entry.action || null, expected_tallies: Object.fromEntries(fresh.expected.map(row => [row.mode_of_payment, { amount: row.expected_amount, currency: row.currency }])), expected_invoice_count: fresh.sales_count, expected_payment_count: fresh.customer_payments?.length || 0 })
      entry.closed = true; done++
      if (session.registerSession?.name === entry.session) { session.registerSession = null; changedActive = true }
    }
    result.value = t('{n} register(s) sent for closing. Review Previous sessions for consolidation or errors.', { n: done })
  } catch (e) { error.value = t('{n} register(s) sent for closing before stopping. ', { n: done }) + e.message }
  finally {
    if (changedActive) {
      try { await session.bootstrap(session.posProfile) }
      catch (e) { error.value = [error.value, t('Refresh the current till to load its closing status.'), e.message].filter(Boolean).join(' ') }
    }
    busy.value = false; emit('changed')
  }
}
async function groupClosed() { await session.bootstrap(session.posProfile); await refresh(); emit('changed') }
onMounted(refresh)
</script>
<style scoped>
.all-registers { display: grid; gap: 16px; }
.all-heading, .hub-toolbar, .hub-register-head, .hub-bulk { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.all-heading h1 { margin: 8px 0; font-size: 30px; letter-spacing: -.03em; }
.all-heading p { margin: 0; line-height: 1.6; font-size: 13px; }
.eyebrow { display: flex; align-items: center; gap: 6px; color: var(--brand-dark); font-size: 12px; font-weight: 700; }
.hub-toolbar { font-size: 13px; padding: 8px 0; }
.hub-register { overflow: hidden; }
.hub-register-head { padding: 18px; }
.hub-register-head h2 { margin: 8px 0 4px; font-size: 21px; overflow-wrap: anywhere; }
.hub-register-head p { margin: 0; }
.hub-status { display: inline-flex; align-items: center; gap: 6px; font-size: 11px; color: var(--brand-dark); }
.hub-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.hub-quick { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-top: 1px solid var(--border-subtle); background: var(--surface-2); }
.hub-quick > span { padding: 12px 18px; font-size: 11px; color: var(--text-muted); }
.hub-quick b { display: block; margin-top: 5px; font-size: 16px; color: var(--text); overflow-wrap: anywhere; }
.hub-register-body { padding: 18px; border-top: 1px solid var(--border); }
.hub-notice { padding: 16px; border-inline-start: 3px solid var(--brand); background: var(--surface-2); border-radius: var(--radius); font-size: 13px; line-height: 1.6; }
.hub-notice p { margin: 6px 0 0; }
.hub-adjust, .hub-movements { padding: 16px 0; border-bottom: 1px solid var(--border); }
summary { cursor: pointer; font-weight: 600; }
.hub-adjust-form { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 12px; }
.hub-adjust-form input, .hub-adjust-form select { width: 100%; min-width: 0; }
.hub-close h3 { display: flex; gap: 8px; align-items: center; margin: 22px 0 6px; }
.hub-close > p { line-height: 1.6; }
.hub-count { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 12px; padding: 14px 0; border-bottom: 1px solid var(--border-subtle); }
.hub-count label { display: grid; gap: 6px; }
.hub-count input { max-width: 260px; width: 100%; }
.hub-count :deep(.cash-counter) { grid-column: 1 / -1; margin: 0; }
.hub-difference { font-size: 13px; font-weight: 600; text-align: end; }
.tallied { color: var(--brand-dark); }
.hub-note { display: grid; gap: 6px; margin: 16px 0; }
.hub-review { display: flex; align-items: flex-start; gap: 10px; margin: 18px 0; font-size: 13px; line-height: 1.5; }
.hub-review input { margin-top: 3px; }
.hub-bulk { padding: 18px; }
.hub-bulk p { margin-bottom: 0; line-height: 1.6; }
.is-reviewed { border-color: var(--brand); }
.all-registers button { transition: transform .16s ease, background .16s ease; }
.all-registers button:hover:not(:disabled) { transform: translateY(-1px); }
.all-registers button:active:not(:disabled) { transform: translateY(1px); }
.register-panel-enter-active, .register-panel-leave-active { transition: opacity .18s ease, transform .18s ease; }
.register-panel-enter-from, .register-panel-leave-to { opacity: 0; transform: translateY(5px); }
.spinning { animation: register-spin .8s linear infinite; }
@keyframes register-spin { to { transform: rotate(360deg); } }
@media (max-width: 700px) { .all-heading, .hub-toolbar, .hub-register-head, .hub-bulk { align-items: stretch; flex-direction: column; } .hub-quick { grid-template-columns: repeat(2, minmax(0, 1fr)); } .hub-actions .btn { flex: 1; } .hub-register-head, .hub-register-body { padding: 14px; } }
@media (max-width: 420px) { .hub-adjust-form { grid-template-columns: minmax(0, 1fr); } .hub-count { grid-template-columns: minmax(0, 1fr); } .hub-difference { text-align: start; } }
@media (prefers-reduced-motion: reduce) { .all-registers button, .register-panel-enter-active, .register-panel-leave-active { transition: none; transform: none !important; } .spinning { animation: none; } }
</style>
