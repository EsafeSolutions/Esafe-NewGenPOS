<template>
  <section class="warehouse-stock" :aria-label="t('Warehouse stock')">
    <div class="stock-heading">
      <h3>{{ t('Warehouse stock') }}</h3>
      <button type="button" class="btn btn-outline" :disabled="loading || saving || disabled" @click="load">{{ t('Refresh') }}</button>
    </div>
    <p class="muted">{{ t('Quantities are in the stock unit.') }} {{ stock.stock_uom }}</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-else-if="loading" role="status">{{ t('Loading…') }}</p>
    <template v-else>
      <div class="stock-table">
        <table>
          <thead><tr><th>{{ t('Warehouse') }}</th><th>{{ t('On hand') }}</th><th>{{ t('Reserved') }}</th><th>{{ t('Available') }}</th></tr></thead>
          <tbody><tr v-for="row in stock.rows" :key="row.warehouse">
            <th scope="row">{{ row.warehouse }}</th><td>{{ row.actual_qty }}</td><td>{{ row.reserved_qty }}</td><td>{{ row.available_qty }}</td>
          </tr></tbody>
        </table>
      </div>
      <p v-if="!stock.rows.length" class="muted">{{ t('No accessible warehouses in this company.') }}</p>
      <div v-if="stock.can_adjust && stock.rows.length" class="stock-adjustment">
        <h4>{{ t('Adjust stock') }}</h4>
        <label>{{ t('Warehouse') }}<select v-model="warehouse" :disabled="saving || disabled">
          <option v-for="row in stock.rows" :key="row.warehouse" :value="row.warehouse">{{ row.warehouse }}</option>
        </select></label>
        <label>{{ t('New on-hand quantity') }}<input v-model="qty" type="number" min="0" step="any" :disabled="saving || disabled" /></label>
        <label>{{ t('Valuation rate (optional)') }}<input v-model="rate" type="number" min="0.000001" step="any" :disabled="saving || disabled" /></label>
        <small class="muted">{{ t('Leave the rate blank to use ERPNext valuation. New stock may require a rate.') }}</small>
        <label>{{ t('Reason') }}<input v-model.trim="reason" maxlength="500" :disabled="saving || disabled" /></label>
        <p class="muted">{{ t('This posts a Stock Reconciliation and changes stock immediately. Close shifts with unposted sales first.') }}</p>
        <button type="button" class="btn btn-primary" :disabled="saving || disabled || qty === '' || !reason || !warehouse" @click="adjust">
          {{ saving ? t('Saving…') : t('Post stock adjustment') }}
        </button>
      </div>
      <p v-else class="muted">{{ t('Stock adjustment requires access and an item without serial or batch tracking.') }}</p>
    </template>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'
import { call } from '../api'
import { t } from '../i18n'
import { useSessionStore } from '../stores/session'

const props = defineProps({ itemCode: String, disabled: Boolean })
const emit = defineEmits(['updated', 'busy'])
const session = useSessionStore()
const stock = ref({ rows: [] })
const warehouse = ref('')
const qty = ref('')
const rate = ref('')
const reason = ref('')
const loading = ref(false)
const saving = ref(false)
const error = ref('')
let request = 0

async function load() {
  const id = ++request
  loading.value = true
  error.value = ''
  qty.value = ''
  rate.value = ''
  reason.value = ''
  try {
    const result = await call('esafepos.api.items.warehouse_stock', { pos_profile: session.posProfile, item_code: props.itemCode })
    if (id !== request) return
    stock.value = result
    if (!result.rows.some((row) => row.warehouse === warehouse.value)) warehouse.value = result.rows[0]?.warehouse || ''
  } catch (err) {
    if (id === request) error.value = err.message
  } finally {
    if (id === request) loading.value = false
  }
}

async function adjust() {
  if (saving.value || props.disabled || session.offline) return
  const row = stock.value.rows.find((entry) => entry.warehouse === warehouse.value)
  if (!row || qty.value === '' || !reason.value) return
  if (!window.confirm(t('Post this stock adjustment?') + '\n' + row.warehouse + ': ' + row.actual_qty + ' → ' + qty.value)) return
  saving.value = true
  emit('busy', true)
  try {
    const result = await call('esafepos.api.items.adjust_stock', {
      pos_profile: session.posProfile, item_code: props.itemCode, warehouse: row.warehouse,
      qty: qty.value, expected_qty: row.actual_qty, reason: reason.value, valuation_rate: rate.value || null,
    })
    session.notify(t('Stock adjustment posted') + ': ' + result.name)
    await load()
    emit('updated')
  } catch (err) {
    session.notify(err.message, true)
  } finally {
    saving.value = false
    emit('busy', false)
  }
}
watch(() => [props.itemCode, session.posProfile], load, { immediate: true })
watch(warehouse, () => { qty.value = ''; rate.value = ''; reason.value = '' })
</script>

<style scoped>
.warehouse-stock { border-top: 1px solid var(--border); padding-top: 16px; display: grid; gap: 12px; min-width: 0; }
.stock-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
h3, h4, p { margin: 0; }
.stock-table { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 10px 8px; border-bottom: 1px solid var(--border); text-align: end; }
th:first-child { text-align: start; }
.stock-adjustment, label { display: grid; gap: 8px; }
input, select { width: 100%; min-width: 0; }
</style>
