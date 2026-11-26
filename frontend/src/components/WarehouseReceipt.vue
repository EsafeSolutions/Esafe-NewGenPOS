<template>
  <form class="receipt-form" @submit.prevent="receive">
    <h4>{{ t('Add to warehouse') }}</h4>
    <p class="muted">{{ t('Receive new stock with an ERPNext Material Receipt. The quantity is added to the existing balance.') }}</p>
    <fieldset :disabled="posting || disabled || session.offline || uncertain">
      <label>{{ t('Receiving warehouse') }}<select v-model="warehouse" required><option v-for="row in stock.rows" :key="row.warehouse" :value="row.warehouse">{{ row.warehouse }}</option></select></label>
      <div class="receipt-pair"><label>{{ t('Quantity received') }}<input v-model="qty" type="number" min="0.000001" step="any" required /></label>
        <label>{{ t('Unit cost') }} <small>{{ stock.currency }} / {{ stock.stock_uom }}</small><input v-model="rate" type="number" min="0.000001" step="any" required /></label></div>
      <p v-if="Number(qty) > 0 && selected" class="receipt-preview">{{ t('Expected on hand') }}: {{ Number(selected.actual_qty) + Number(qty) }} {{ stock.stock_uom }}</p>
      <label v-if="stock.has_serial_no">{{ t('Received serial numbers (one per line)') }}<textarea v-model="serials" rows="4" required /></label>
      <label v-if="stock.has_batch_no">{{ t('Received batch number') }}<input v-model.trim="batch" maxlength="140" required /></label>
      <label>{{ t('Receipt reason / reference') }}<input v-model.trim="reason" maxlength="500" required /></label>
    </fieldset>
    <p v-if="uncertain" class="receipt-error" role="alert">{{ t('The receipt response was lost. Retry this saved request to check the posting without adding stock twice.') }}</p>
    <button class="btn btn-primary" :disabled="posting || disabled || session.offline || !valid">{{ posting ? t('Posting…') : uncertain ? t('Check and retry receipt') : t('Post Material Receipt') }}</button>
    <button v-if="uncertain" class="btn btn-outline" type="button" :disabled="posting || disabled" @click="clearRequest">{{ t('Clear after checking ERPNext') }}</button>
  </form>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { call, OfflineError } from '../api'
import { t } from '../i18n'
import { useSessionStore } from '../stores/session'
const props = defineProps({ itemCode: String, stock: Object, disabled: Boolean })
const emit = defineEmits(['busy', 'posted', 'pending'])
const session = useSessionStore()
const warehouse = ref(props.stock.rows[0]?.warehouse || ''), qty = ref(''), rate = ref(''), reason = ref(''), serials = ref(''), batch = ref('')
const posting = ref(false), uncertain = ref(false)
const key = 'esafepos:receipt:' + JSON.stringify([session.user, session.posProfile, props.itemCode])
let payload = null
try {
  const saved = JSON.parse(sessionStorage.getItem(key) || 'null')
  if (saved?.request_id && saved.item_code === props.itemCode && saved.pos_profile === session.posProfile) {
    payload = saved; uncertain.value = true; warehouse.value = saved.warehouse; qty.value = saved.qty
    rate.value = saved.valuation_rate; reason.value = saved.reason; serials.value = saved.serial_no; batch.value = saved.batch_no
  }
} catch { /* Current-screen recovery still works when storage is unavailable. */ }
watch(uncertain, value => emit('pending', value), { immediate: true })
const selected = computed(() => props.stock.rows.find(row => row.warehouse === warehouse.value))
const valid = computed(() => uncertain.value || (selected.value && Number(qty.value) > 0 && Number(rate.value) > 0 && reason.value &&
  (!props.stock.has_serial_no || serials.value.trim()) && (!props.stock.has_batch_no || batch.value)))
function clearRequest() {
  if (!window.confirm(t('Confirm in ERPNext that this Material Receipt was not posted before clearing this request.'))) return
  try { sessionStorage.removeItem(key) } catch { /* Private storage. */ }
  payload = null; uncertain.value = false
}
async function receive() {
  if (posting.value || props.disabled || session.offline || !valid.value) return
  if (!uncertain.value) {
    if (!window.confirm(t('Post this Material Receipt?') + '\n' + warehouse.value + '\n+' + qty.value + ' ' + props.stock.stock_uom + ' @ ' + rate.value + ' ' + (props.stock.currency || ''))) return
    payload = { pos_profile: session.posProfile, item_code: props.itemCode, warehouse: warehouse.value,
      qty: qty.value, valuation_rate: rate.value, reason: reason.value, serial_no: serials.value, batch_no: batch.value, request_id: globalThis.crypto.randomUUID() }
    try { sessionStorage.setItem(key, JSON.stringify(payload)) } catch { /* Private storage. */ }
  }
  posting.value = true; emit('busy', true)
  try {
    const result = await call('esafepos.api.inventory.receive_stock', payload, { timeout: 60000 })
    uncertain.value = false
    try { sessionStorage.removeItem(key) } catch { /* Private storage. */ }
    qty.value = ''; rate.value = ''; reason.value = ''; serials.value = ''; batch.value = ''
    emit('posted', result); session.notify(t('Material Receipt posted') + ': ' + result.name)
  } catch (error) {
    uncertain.value = error instanceof OfflineError || uncertain.value
    if (!uncertain.value) { try { sessionStorage.removeItem(key) } catch { /* Private storage. */ } }
    session.notify(error.message, true)
  } finally { posting.value = false; emit('busy', false) }
}
</script>

<style scoped>
.receipt-form { display: grid; gap: 16px; border-top: 1px solid var(--border); padding-top: 18px; }
h4, p { margin: 0; } h4 { font-size: 16px; } p { font-size: 12px; line-height: 1.6; }
fieldset { border: 0; padding: 0; margin: 0; display: grid; gap: 14px; min-width: 0; }
label { display: grid; gap: 7px; } small { color: var(--text-muted); } input, select, textarea { width: 100%; min-width: 0; }
.receipt-pair { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.receipt-preview { padding: 12px; background: var(--surface-2); color: var(--brand-dark); border-radius: 8px; }
.receipt-error { color: var(--red); } .receipt-form > button { justify-self: start; }
@media (max-width: 720px) { .receipt-pair { grid-template-columns: minmax(0, 1fr); } }
</style>
