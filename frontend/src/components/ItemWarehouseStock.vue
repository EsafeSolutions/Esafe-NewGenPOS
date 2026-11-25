<template>
  <section class="warehouse-stock" :aria-label="t('Warehouse stock')">
    <div class="stock-heading"><div><h3>{{ t('Warehouse stock') }}</h3><p class="muted">{{ t('Quantities are in the stock unit.') }} {{ stock.stock_uom }}</p></div>
      <button type="button" class="btn btn-outline" :disabled="loading || saving || disabled || session.offline" @click="load"><Icon name="refresh" />{{ t('Refresh') }}</button></div>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="loading" role="status">{{ t('Loading…') }}</p>
    <template v-else-if="!error">
      <div class="stock-table"><table>
        <thead><tr><th>{{ t('Warehouse') }}</th><th>{{ t('On hand') }}</th><th>{{ t('Reserved') }}</th><th>{{ t('Available') }}</th></tr></thead>
        <tbody><tr v-for="row in stock.rows" :key="row.warehouse"><th scope="row">{{ row.warehouse }}</th><td>{{ row.actual_qty }}</td><td>{{ row.reserved_qty }}</td><td :class="{ empty: row.available_qty <= 0 }">{{ row.available_qty }}</td></tr></tbody>
      </table></div>
      <p v-if="!stock.rows.length" class="muted">{{ t('No accessible warehouses in this company.') }}</p>
      <p class="muted stock-hint">{{ t('Reserved includes unposted POS sales. Close affected shifts before changing stock.') }}</p>
      <div class="stock-actions" role="group" :aria-label="t('Inventory actions')">
        <button v-if="stock.can_transfer && stock.rows.length > 1" type="button" class="btn btn-outline" :aria-pressed="action === 'transfer'" :disabled="saving || uncertain" @click="action = 'transfer'"><Icon name="exchange" />{{ t('Transfer stock') }}</button>
        <button v-if="stock.can_adjust" type="button" class="btn btn-outline" :aria-pressed="action === 'adjust'" :disabled="saving || uncertain" @click="action = 'adjust'"><Icon name="detail" />{{ t('Adjust stock') }}</button>
        <button v-if="stock.can_view_movements" type="button" class="btn btn-outline" :aria-pressed="action === 'movements'" :disabled="saving || uncertain" @click="showMovements"><Icon name="clock" />{{ t('Stock movements') }}</button>
      </div>
      <p v-if="posted" class="posted" role="status">{{ t('Posted successfully') }}: <a :href="'/app/' + posted.type + '/' + encodeURIComponent(posted.name)" target="_blank" rel="noopener noreferrer">{{ posted.name }}</a></p>
      <form v-if="action === 'transfer' && stock.can_transfer" class="stock-form" @submit.prevent="transfer">
        <h4>{{ t('Transfer between warehouses') }}</h4>
        <fieldset :disabled="saving || disabled || session.offline || uncertain">
          <div class="form-pair">
            <label>{{ t('From warehouse') }}<select v-model="source" required><option v-for="row in stock.rows" :key="row.warehouse" :value="row.warehouse">{{ row.warehouse }}</option></select></label>
            <label>{{ t('To warehouse') }}<select v-model="target" required><option value="" disabled>{{ t('Choose destination') }}</option><option v-for="row in stock.rows.filter(row => row.warehouse !== source)" :key="row.warehouse" :value="row.warehouse">{{ row.warehouse }}</option></select></label>
          </div>
          <div class="transfer-quantity"><label>{{ t('Transfer quantity') }}<input v-model="transferQty" type="number" min="0.000001" step="any" required /></label><span class="muted">{{ stock.stock_uom }} · {{ t('{n} available', { n: sourceRow?.available_qty ?? 0 }) }}</span></div>
          <label v-if="stock.has_serial_no">{{ t('Serial numbers (one per line)') }}<textarea v-model="serials" rows="4" required /></label>
          <label v-if="stock.has_batch_no">{{ t('Batch number') }}<input v-model.trim="batch" maxlength="140" required /></label>
          <label>{{ t('Transfer reason') }}<input v-model.trim="transferReason" maxlength="500" required /></label>
        </fieldset>
        <p class="muted">{{ t('Posting moves stock immediately and creates an ERPNext Material Transfer.') }}</p>
        <p v-if="uncertain" class="empty" role="alert">{{ t('The server response was lost. Keep these details and retry to check the same transfer without posting it twice.') }}</p>
        <button class="btn btn-primary" :disabled="saving || disabled || session.offline || !validTransfer">{{ saving ? t('Posting…') : uncertain ? t('Check and retry transfer') : t('Post transfer') }}</button>
        <button v-if="uncertain" type="button" class="btn btn-outline" :disabled="saving || disabled" @click="clearUncertain">{{ t('Clear after checking ERPNext') }}</button>
      </form>
      <form v-if="action === 'adjust' && stock.can_adjust" class="stock-form" @submit.prevent="adjust">
        <h4>{{ t('Adjust stock') }}</h4>
        <fieldset :disabled="saving || disabled || session.offline">
          <label>{{ t('Warehouse') }}<select v-model="warehouse"><option v-for="row in stock.rows" :key="row.warehouse" :value="row.warehouse">{{ row.warehouse }}</option></select></label>
          <div class="form-pair"><label>{{ t('New on-hand quantity') }}<input v-model="qty" type="number" min="0" step="any" required /></label><label>{{ t('Valuation rate (optional)') }}<input v-model="rate" type="number" min="0.000001" step="any" /></label></div>
          <small class="muted">{{ t('Leave the rate blank to use ERPNext valuation. New stock may require a rate.') }}</small>
          <label>{{ t('Reason') }}<input v-model.trim="reason" maxlength="500" required /></label>
        </fieldset>
        <p class="muted">{{ t('This posts a Stock Reconciliation and changes stock immediately. Close shifts with unposted sales first.') }}</p>
        <button class="btn btn-primary" :disabled="saving || disabled || session.offline || qty === '' || !reason || !warehouse">{{ saving ? t('Saving…') : t('Post stock adjustment') }}</button>
      </form>
      <section v-if="action === 'movements' && stock.can_view_movements" class="stock-form">
        <h4>{{ t('Stock movements') }}</h4>
        <form class="movement-filters" @submit.prevent="loadMovements()"><label>{{ t('From date') }}<input v-model="fromDate" type="date" /></label><label>{{ t('To date') }}<input v-model="toDate" type="date" /></label><button class="btn btn-outline" :disabled="movementLoading || session.offline">{{ t('Apply') }}</button></form>
        <p v-if="movementError" role="alert">{{ movementError }}</p><p v-else-if="!movements.length && !movementLoading" class="muted">{{ t('No stock movements found for this item.') }}</p>
        <div v-if="movements.length" class="stock-table"><table class="movements-table"><thead><tr><th>{{ t('Date / reference') }}</th><th>{{ t('Warehouse') }}</th><th>{{ t('Change') }}</th><th>{{ t('Balance') }}</th></tr></thead><tbody>
          <tr v-for="row in movements" :key="row.name"><th scope="row">{{ row.posting_date }}<small>{{ row.voucher_type }} · {{ row.voucher_no }}</small></th><td>{{ row.warehouse }}</td><td :class="{ empty: row.actual_qty < 0 }">{{ row.actual_qty > 0 ? '+' : '' }}{{ row.actual_qty }}</td><td>{{ row.qty_after_transaction }}</td></tr>
        </tbody></table></div>
        <p v-if="movementLoading" role="status">{{ t('Loading…') }}</p><button v-if="moreMovements" type="button" class="btn btn-outline" :disabled="movementLoading || session.offline" @click="loadMovements(true)">{{ t('Load more movements') }}</button>
      </section>
      <p v-if="!stock.can_adjust" class="muted stock-hint">{{ t('Stock adjustment requires access and an item without serial or batch tracking.') }}</p>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { call, OfflineError } from '../api'
import Icon from './Icon.vue'
import { t } from '../i18n'
import { useSessionStore } from '../stores/session'
const props = defineProps({ itemCode: String, disabled: Boolean })
const emit = defineEmits(['updated', 'busy'])
const session = useSessionStore()
const stock = ref({ rows: [] }), warehouse = ref(''), qty = ref(''), rate = ref(''), reason = ref('')
const source = ref(''), target = ref(''), transferQty = ref(''), transferReason = ref(''), serials = ref(''), batch = ref('')
const action = ref(''), loading = ref(false), saving = ref(false), error = ref(''), posted = ref(null), uncertain = ref(false)
let transferPayload = null, request = 0, movementRequest = 0
const recoveryKey = () => 'esafepos:transfer:' + JSON.stringify([session.user, session.posProfile, props.itemCode])
function recoverTransfer() {
  try {
    const payload = JSON.parse(sessionStorage.getItem(recoveryKey()) || 'null')
    if (!payload?.request_id || payload.item_code !== props.itemCode || payload.pos_profile !== session.posProfile) return
    transferPayload = payload; uncertain.value = true; action.value = 'transfer'
    source.value = payload.source_warehouse; target.value = payload.target_warehouse
    transferQty.value = payload.qty; transferReason.value = payload.reason; serials.value = payload.serial_no; batch.value = payload.batch_no
  } catch { /* The current screen still retains its retry identity when storage is unavailable. */ }
}
const sourceRow = computed(() => stock.value.rows.find(row => row.warehouse === source.value))
const validTransfer = computed(() => uncertain.value || (source.value && target.value && source.value !== target.value &&
  Number(transferQty.value) > 0 && Number(transferQty.value) <= Number(sourceRow.value?.available_qty) && transferReason.value &&
  (!stock.value.has_serial_no || serials.value.trim()) && (!stock.value.has_batch_no || batch.value)))
const movements = ref([]), moreMovements = ref(false), movementLoading = ref(false), movementError = ref(''), fromDate = ref(''), toDate = ref('')
let movementDates = {}
async function load() {
  if (session.offline) return
  const id = ++request
  loading.value = true; error.value = ''
  try {
    const result = await call('esafepos.api.items.warehouse_stock', { pos_profile: session.posProfile, item_code: props.itemCode })
    if (id !== request) return
    stock.value = result
    if (!result.rows.some(row => row.warehouse === warehouse.value)) warehouse.value = result.rows[0]?.warehouse || ''
    if (!result.rows.some(row => row.warehouse === source.value)) source.value = warehouse.value
    if (!action.value) action.value = result.can_transfer && result.rows.length > 1 ? 'transfer' : result.can_adjust ? 'adjust' : ''
  } catch (err) { if (id === request) error.value = err.message }
  finally { if (id === request) loading.value = false }
}
async function transfer() {
  if (saving.value || props.disabled || session.offline || !validTransfer.value) return
  if (!uncertain.value) {
    if (!window.confirm(t('Post this stock transfer?') + '\n' + transferQty.value + ' ' + stock.value.stock_uom + '\n' + source.value + ' → ' + target.value)) return
    transferPayload = { pos_profile: session.posProfile, item_code: props.itemCode, source_warehouse: source.value,
      target_warehouse: target.value, qty: transferQty.value, expected_qty: sourceRow.value.actual_qty,
      reason: transferReason.value, serial_no: serials.value, batch_no: batch.value, request_id: globalThis.crypto.randomUUID() }
    try { sessionStorage.setItem(recoveryKey(), JSON.stringify(transferPayload)) } catch { /* Private window. */ }
  }
  saving.value = true; emit('busy', true)
  try {
    const result = await call('esafepos.api.items.transfer_stock', transferPayload, { timeout: 60000 })
    uncertain.value = false; posted.value = { type: 'stock-entry', name: result.name }
    try { sessionStorage.removeItem(recoveryKey()) } catch { /* Private window. */ }
    transferQty.value = ''; transferReason.value = ''; serials.value = ''; batch.value = ''
    session.notify(t('Stock transfer posted') + ': ' + result.name)
    await load(); emit('updated')
  } catch (err) {
    uncertain.value = err instanceof OfflineError || uncertain.value
    if (!uncertain.value) { try { sessionStorage.removeItem(recoveryKey()) } catch { /* Private window. */ } }
    session.notify(err.message, true)
  }
  finally { saving.value = false; emit('busy', false) }
}
function clearUncertain() {
  if (!window.confirm(t('Confirm in ERPNext that this transfer was not posted before clearing this request.'))) return
  try { sessionStorage.removeItem(recoveryKey()) } catch { /* Private window. */ }
  uncertain.value = false; transferPayload = null
}
async function adjust() {
  if (saving.value || props.disabled || session.offline) return
  const row = stock.value.rows.find(entry => entry.warehouse === warehouse.value)
  if (!row || qty.value === '' || !reason.value) return
  if (!window.confirm(t('Post this stock adjustment?') + '\n' + row.warehouse + ': ' + row.actual_qty + ' → ' + qty.value)) return
  saving.value = true; emit('busy', true)
  try {
    const result = await call('esafepos.api.items.adjust_stock', { pos_profile: session.posProfile, item_code: props.itemCode,
      warehouse: row.warehouse, qty: qty.value, expected_qty: row.actual_qty, reason: reason.value, valuation_rate: rate.value || null })
    posted.value = { type: 'stock-reconciliation', name: result.name }; qty.value = ''; rate.value = ''; reason.value = ''
    session.notify(t('Stock adjustment posted') + ': ' + result.name); await load(); emit('updated')
  } catch (err) { session.notify(err.message, true) }
  finally { saving.value = false; emit('busy', false) }
}
function showMovements() { action.value = 'movements'; loadMovements() }
async function loadMovements(append = false) {
  if (session.offline) return
  const id = ++movementRequest
  if (!append) { movements.value = []; movementDates = { from_date: fromDate.value || null, to_date: toDate.value || null } }
  movementLoading.value = true; movementError.value = ''
  try {
    const rows = await call('esafepos.api.items.stock_movements', { pos_profile: session.posProfile,
      item_code: props.itemCode, ...movementDates, start: append ? movements.value.length : 0 })
    if (id !== movementRequest) return
    movements.value = append ? [...movements.value, ...rows] : rows; moreMovements.value = rows.length === 50
  } catch (err) { if (id === movementRequest) movementError.value = err.message }
  finally { if (id === movementRequest) movementLoading.value = false }
}
watch(() => [props.itemCode, session.posProfile], () => { recoverTransfer(); load() }, { immediate: true })
watch(warehouse, () => { qty.value = ''; rate.value = ''; reason.value = '' })
watch(source, () => { if (target.value === source.value) target.value = '' })
onBeforeUnmount(() => { request++; movementRequest++ })
</script>

<style scoped>
.warehouse-stock { display: grid; gap: 16px; min-width: 0; }
.stock-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
h3, h4, p { margin: 0; } h3, h4 { font-size: 16px; } .stock-heading p { margin-top: 6px; font-size: 12px; }
.stock-table { overflow-x: auto; } table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; font-size: 13px; }
th, td { padding: 13px 8px; border-bottom: 1px solid var(--border); text-align: end; } th:first-child { text-align: start; } thead { color: var(--text-muted); background: var(--surface-2); }
tbody th { font-weight: 500; } .empty { color: var(--red); }
.stock-form, label, fieldset { display: grid; gap: 8px; } fieldset { margin: 0; padding: 0; border: 0; gap: 14px; min-width: 0; }
.stock-form { gap: 16px; padding-top: 18px; border-top: 1px solid var(--border); } .stock-form > .btn { justify-self: start; }
input, select, textarea { width: 100%; min-width: 0; } textarea { resize: vertical; }
.form-pair { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.transfer-quantity { display: flex; align-items: end; flex-wrap: wrap; gap: 12px; } .transfer-quantity label { width: 160px; } .transfer-quantity > span { padding-bottom: 11px; }
.stock-actions { display: flex; flex-wrap: wrap; gap: 8px; } .stock-actions [aria-pressed='true'] { color: var(--brand-dark); border-color: var(--brand); background: var(--surface-2); }
.stock-hint, .stock-form > p { font-size: 12px; line-height: 1.6; } .posted { color: var(--brand-dark); overflow-wrap: anywhere; }
.movement-filters { display: flex; align-items: end; flex-wrap: wrap; gap: 8px; } .movement-filters label { flex: 1; min-width: 120px; }
.movements-table { min-width: 470px; } .movements-table small { display: block; color: var(--text-muted); font-size: 11px; margin-top: 5px; }
@media (max-width: 720px) { .form-pair { grid-template-columns: minmax(0, 1fr); } }
</style>
