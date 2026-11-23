<template>
  <details class="cash-counter" :open="open" @toggle="open = $event.target.open">
    <summary>{{ t('Note and coin counter') }} · {{ currency }}</summary>
    <div class="counter-body">
      <p class="muted small">{{ known ? t('Enter quantities. The total fills the counted cash automatically.') : t('Add the notes and coins used in this currency, then enter quantities.') }}</p>
      <div v-for="kind in ['notes', 'coins']" :key="kind" class="denomination-section">
        <b>{{ kind === 'notes' ? t('Notes') : t('Coins') }}</b>
        <div class="denomination-grid">
          <label v-for="row in rows.filter(r => r.kind === kind)" :key="`${kind}-${row.value}`" class="denomination-row">
            <span>{{ row.value.toLocaleString(undefined, { maximumFractionDigits: 3 }) }}</span>
            <span aria-hidden="true">×</span>
            <input type="number" min="0" max="10000000" step="1" inputmode="numeric" :aria-label="`${currency} ${row.value} ${kind}`" v-model="row.quantity" @input="update" :disabled="disabled" />
          </label>
        </div>
      </div>
      <form class="custom-denomination" @submit.prevent="add">
        <select v-model="customKind" :aria-label="t('Denomination type')" :disabled="disabled"><option value="notes">{{ t('Note') }}</option><option value="coins">{{ t('Coin') }}</option></select>
        <input v-model="customValue" type="number" min="0.001" step="0.001" :aria-label="t('Denomination value')" :placeholder="t('Value')" :disabled="disabled" />
        <button class="btn btn-outline" type="submit" :disabled="disabled || !(Number(customValue) > 0)">{{ t('Add denomination') }}</button>
      </form>
      <p v-if="invalid" role="alert" class="neg">{{ t('Use whole, non-negative quantities.') }}</p>
      <div class="counter-total"><span>{{ t('Counted cash') }}</span><strong>{{ money(total, currency) }}</strong><button type="button" class="btn btn-outline" @click="clear" :disabled="disabled">{{ t('Clear count') }}</button></div>
    </div>
  </details>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import presets from '../../../esafepos/cash_denominations.json'
import { money } from '../format'
import { t } from '../i18n'
const props = defineProps({ currency: { type: String, required: true }, disabled: Boolean, modelValue: Object })
const emit = defineEmits(['update:modelValue', 'count'])
const rows = ref([]), open = ref(false), customKind = ref('notes'), customValue = ref('')
const known = computed(() => Boolean(presets[props.currency]))
watch(() => props.currency, () => {
  rows.value = ['notes', 'coins'].flatMap(kind => (presets[props.currency]?.[kind] || []).map(value => ({ kind, value, quantity: '' })))
  if (props.modelValue?.currency === props.currency) rows.value = props.modelValue.rows.map(r => ({ ...r }))
}, { immediate: true })
watch(() => props.modelValue, value => {
  if (!value) rows.value.forEach(r => { r.quantity = '' })
})
const invalid = computed(() => rows.value.some(r => !Number.isInteger(Number(r.quantity)) || Number(r.quantity) < 0 || Number(r.quantity) > 10000000))
const total = computed(() => Math.round(rows.value.reduce((n, r) => n + r.value * (Number(r.quantity) || 0), 0) * 100) / 100)
function update() {
  const value = { currency: props.currency, rows: rows.value.map(r => ({ ...r, quantity: Number(r.quantity) || 0 })) }
  emit('update:modelValue', value)
  if (invalid.value) { emit('count', null); return }
  emit('count', total.value)
}
function clear() { rows.value.forEach(r => { r.quantity = '' }); update() }
function add() {
  const value = Number(customValue.value)
  if (!Number.isFinite(value) || value <= 0 || value > 1000000000 || Math.abs(value * 1000 - Math.round(value * 1000)) > 0.00001) return
  if (!rows.value.some(r => r.kind === customKind.value && r.value === value)) rows.value.push({ kind: customKind.value, value, quantity: '' })
  customValue.value = ''
}
</script>

<style scoped>
.cash-counter { margin-top: 14px; border: 1px solid var(--border); border-radius: var(--radius); }
summary { cursor: pointer; padding: 12px; font-weight: 600; }
.counter-body { padding: 0 12px 12px; }
.denomination-section { margin-top: 12px; }
.denomination-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px 18px; margin-top: 8px; }
.denomination-row { display: grid; grid-template-columns: 1fr auto 74px; gap: 8px; align-items: center; font-variant-numeric: tabular-nums; }
.denomination-row input { width: 100%; min-width: 0; text-align: right; }
.custom-denomination, .counter-total { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 16px; }
.custom-denomination input { width: 95px; }
.counter-total strong { margin-inline-start: auto; font-variant-numeric: tabular-nums; }
</style>
