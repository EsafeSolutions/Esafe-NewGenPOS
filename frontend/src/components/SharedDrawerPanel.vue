<template>
  <section v-if="session.permissions.is_manager || group?.group" class="card shared-drawer">
    <div class="drawer-heading"><b>{{ t('Combined cash drawer') }}</b><button type="button" class="btn btn-outline" :disabled="busy || session.offline" @click="refresh(true)">{{ t('Refresh totals') }}</button></div>
    <p v-if="error" role="alert" class="neg">{{ error }}</p>
    <p v-if="session.offline" class="muted">{{ t('Connect to sync or close linked shifts.') }}</p>
    <template v-if="group?.group">
      <p class="muted small">{{ t('These shifts share one cash count. Cash exchanged inside the group needs no cash in/out entry. Record outside cash movements once.') }}</p>
      <ul class="drawer-members"><li v-for="member in group.members" :key="member.session">{{ member.opened_by_name || member.opened_by }} · {{ member.pos_profile }} · {{ member.session }}</li></ul>
      <p class="muted small">{{ t('Opening floats are added together. Each cashier keeps their own sales and ERPNext closing.') }}</p>
    </template>
    <template v-if="session.permissions.is_manager">
      <div class="drawer-link">
        <select v-model="target" :disabled="busy || session.offline" :aria-label="t('Shift to combine')"><option value="">{{ t('Choose another open shift') }}</option><option v-for="row in candidates" :key="row.session" :value="row.session">{{ row.opened_by_name || row.opened_by }} · {{ row.pos_profile }} · {{ row.session }}</option></select>
        <button type="button" class="btn btn-outline" :disabled="!target || busy || session.offline" @click="combine">{{ t('Combine shifts') }}</button>
      </div>
      <p v-if="!group?.group" class="muted small">{{ t('Optional: combine shifts that exchange cash. They must use the same company and cash accounts. Both opening floats will be included.') }}</p>
      <template v-if="group?.group">
        <p v-if="changed" role="status" class="neg">{{ t('The drawer changed. Refresh totals and re-check the count before closing.') }}</p>
        <div v-for="row in group.expected" :key="row.mode_of_payment" class="shared-count">
          <label><b>{{ row.mode_of_payment }}</b><span class="muted small">{{ t('Expected') }}: {{ money(row.expected_amount, row.currency) }}</span><input type="text" inputmode="decimal" :aria-label="`${t('Combined count')} ${row.mode_of_payment}`" v-model="counted[row.mode_of_payment]" :disabled="busy" @input="delete denominations[row.mode_of_payment]" /></label>
          <span class="small">{{ t('Difference') }}: {{ money(difference(row), row.currency) }}</span>
          <CashDenominationCounter v-if="row.is_cash" :currency="row.currency" v-model="denominations[row.mode_of_payment]" :disabled="busy" @count="counted[row.mode_of_payment] = $event" />
        </div>
        <VarianceReason v-if="askReason" v-model:reason="reason" v-model:action="action" :reasons="session.settings?.variance_reasons || []" :required="reasonRequired" :missing="reasonRequired && !reason.trim()" :known="true" />
        <input v-model="note" :placeholder="t('Closing note (optional)')" class="drawer-note" :disabled="busy" />
        <label class="drawer-ready"><input type="checkbox" v-model="ready" :disabled="busy" /><span>{{ t('All linked tills have uploaded offline sales and stopped selling for this count.') }}</span></label>
        <p class="muted small">{{ t('The shared count is allocated across shifts in proportion to expected takings. The physical count and allocation are saved on every linked shift.') }}</p>
        <button type="button" class="btn btn-danger" :disabled="busy || changed || !ready || !valid || session.offline || (reasonRequired && !reason.trim())" @click="closeAll">{{ busy ? t('Working…') : t('Close all linked shifts') }}</button>
      </template>
    </template>
    <p v-else-if="group?.group" class="muted">{{ t('A manager counts and closes all linked shifts together.') }}</p>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { call } from '../api'
import { useSessionStore } from '../stores/session'
import { money, parseMoney } from '../format'
import { t } from '../i18n'
import CashDenominationCounter from './CashDenominationCounter.vue'
import VarianceReason from './VarianceReason.vue'
const props = defineProps({ sessionName: { type: String, required: true } })
const emit = defineEmits(['changed', 'closed'])
const session = useSessionStore()
const group = ref(null), candidates = ref([]), target = ref(''), error = ref(''), busy = ref(false), changed = ref(false)
const counted = ref({}), denominations = ref({}), note = ref(''), reason = ref(''), action = ref(''), ready = ref(false)
let timer, loading = false
const valid = computed(() => group.value?.expected.every(row => {
  const n = parseMoney(counted.value[row.mode_of_payment])
  return n != null && Number.isFinite(n) && (!row.is_cash || n >= 0)
}))
function difference(row) { const n = parseMoney(counted.value[row.mode_of_payment]); return n == null ? 0 : n - row.expected_amount }
const askReason = computed(() => session.settings?.variance_reason_mode !== 'Off' && group.value?.expected.some(r => Math.abs(difference(r)) > 0.005))
const reasonRequired = computed(() => session.settings?.variance_reason_mode === 'Required' && group.value?.expected.some(r => {
  const rate = r.currency === group.value.company_currency ? 1 : group.value.rates?.[r.currency] || 1
  return Math.abs(difference(r) * rate) > (Number(session.settings?.variance_reason_threshold) || 0) + 0.005
}))
async function refresh(explicit = false) {
  if (session.offline || busy.value || loading) return
  loading = true
  try {
    const next = await call('esafepos.api.shared_drawer.summary', { session: props.sessionName })
    if (!next.all_open) { emit('closed'); return }
    if (group.value?.group && next.version !== group.value.version && !explicit) { changed.value = true; ready.value = false }
    else { group.value = next; if (explicit) { changed.value = false; ready.value = false } }
    emit('changed', next.group)
    if (session.permissions.is_manager && (explicit || !candidates.value.length)) candidates.value = await call('esafepos.api.shared_drawer.candidates', { session: props.sessionName })
    error.value = ''
  } catch (e) { error.value = e.message }
  finally { loading = false }
}
async function combine() {
  if (!confirm(t('Combine these open shifts into one cash drawer? Count both opening floats together. A manager will close all linked shifts together.'))) return
  busy.value = true
  try {
    group.value = await call('esafepos.api.shared_drawer.combine', { session: props.sessionName, target: target.value })
    target.value = ''; counted.value = {}; denominations.value = {}; ready.value = false
    emit('changed', group.value.group)
  } catch (e) { error.value = e.message }
  finally { busy.value = false }
  await refresh(true)
}
async function closeAll() {
  await session.refreshQueueCount()
  if ((session.queuedCount || 0) > (session.refusedCount || 0)) { error.value = t('Upload offline sales before closing.'); return }
  if (!confirm(t('Close all linked shifts? No more sales can be added to any of them.'))) return
  busy.value = true
  try {
    await call('esafepos.api.shared_drawer.close', { session: props.sessionName, counted: Object.fromEntries(group.value.expected.map(r => [r.mode_of_payment, parseMoney(counted.value[r.mode_of_payment])])), version: group.value.version, denomination_counts: denominations.value, closing_note: note.value || null, variance_reason: reason.value || null, variance_action: action.value || null })
    session.notify(t('Linked shifts closed. ERPNext closings continue in the background.'))
    emit('closed')
  } catch (e) { error.value = e.message }
  finally { busy.value = false }
}
onMounted(() => { refresh(true); timer = setInterval(() => refresh(), 10000) })
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.shared-drawer { padding: 16px; border: 1px solid var(--border); border-radius: var(--radius); margin: 12px 0; }
.drawer-heading, .drawer-link { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.drawer-heading { justify-content: space-between; }
.drawer-link select { flex: 1; min-width: 0; width: 100%; }
.drawer-members { padding-inline-start: 20px; line-height: 1.7; overflow-wrap: anywhere; }
.shared-count { margin: 16px 0; padding-top: 12px; border-top: 1px solid var(--border); }
.shared-count > label { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.shared-count input { width: 130px; margin-inline-start: auto; }
.drawer-note { width: 100%; margin-top: 12px; }
.drawer-ready { display: flex; gap: 10px; align-items: flex-start; margin: 16px 0; }
.drawer-ready input { margin-top: 4px; }
</style>
