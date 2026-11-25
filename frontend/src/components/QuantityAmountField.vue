<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only -->
<template>
  <div class="quantity-amount" :class="{ compact }">
    <label :for="id">{{ t('Amount') }} ({{ currency }})</label>
    <input
      :id="id"
      type="text"
      inputmode="decimal"
      autocomplete="off"
      :value="displayAmount"
      :disabled="!canCalculate"
      :title="hint"
      :aria-invalid="error ? true : undefined"
      :aria-describedby="`${id}-help`"
      @input="changeAmount($event.target.value)"
      @blur="finishAmount"
    />
    <p :id="`${id}-help`" class="amount-help" :class="{ 'amount-error': error, 'visually-hidden': compact && !error && !roundingNote }" :role="error ? 'alert' : undefined">
      {{ error || roundingNote || hint }}
    </p>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { t } from '../i18n'
import { money } from '../format'
import { QUANTITY_STEP, quantityAmount, quantityFromAmount } from '../quantityAmount'

const props = defineProps({
  id: { type: String, required: true },
  quantity: { type: [Number, String], default: 1 },
  unitPrice: { type: Number, required: true },
  currency: { type: String, required: true },
  unit: { type: String, default: '' },
  wholeQuantity: Boolean,
  disabled: Boolean,
  compact: Boolean,
})
const emit = defineEmits(['update:quantity', 'validity'])
const draft = ref(null)
const error = ref('')
let emittedQuantity = null
const canCalculate = computed(() => !props.disabled && Number.isFinite(props.unitPrice) && props.unitPrice > 0)
const hint = computed(() => props.disabled ? t('Confirm the current unit price first.')
  : canCalculate.value ? t('Before discounts and taxes.') : t('Set a unit price greater than zero.'))
const displayAmount = computed(() => draft.value ?? String(quantityAmount(props.quantity, props.unitPrice) ?? ''))
const roundingNote = computed(() => {
  if (draft.value == null || error.value) return ''
  const result = quantityFromAmount(draft.value, props.unitPrice, props.wholeQuantity)
  if (result.error || Math.abs(result.amount - result.requested) < 0.005) return ''
  return t('Quantity rounds to {qty} {unit}; amount is {amount}.', {
    qty: props.quantity, unit: props.unit, amount: money(result.amount, props.currency),
  })
})

watch(error, value => emit('validity', !value), { immediate: true })
watch(() => [props.quantity, props.unitPrice, props.currency, props.unit, props.wholeQuantity, props.disabled], (values, before) => {
  // Keep raw text while the cashier types ("5" must not become "5.00").
  const fromThisInput = values[0] === emittedQuantity && values.slice(1).every((value, index) => value === before[index + 1])
  emittedQuantity = null
  if (!fromThisInput) {
    draft.value = null
    error.value = ''
  }
})

function changeAmount(value) {
  draft.value = value
  const result = quantityFromAmount(value, props.unitPrice, props.wholeQuantity)
  const unit = props.unit || t('units')
  const errors = {
    price: t('Set a unit price greater than zero.'),
    amount: t('Enter an amount greater than zero.'),
    whole: t('Enter an amount for a whole number of {unit}.', { unit }),
    small: t('Amount is below the minimum quantity of {qty} {unit}.', { qty: QUANTITY_STEP, unit }),
    large: t('Enter a smaller amount.'),
  }
  error.value = result.error ? errors[result.error] : ''
  if (result.error) return
  emittedQuantity = result.quantity
  emit('update:quantity', result.quantity)
}

function finishAmount() {
  if (!error.value) draft.value = null
}
</script>

<style scoped>
.quantity-amount { min-width: 0; }
.quantity-amount label { display: block; }
.quantity-amount input { display: block; width: 100%; margin-top: 5px; }
.quantity-amount input[aria-invalid='true'] { border-color: var(--red); }
.amount-help { margin: 5px 0 0; font-size: 12px; line-height: 1.4; color: var(--text-muted); }
.amount-error { color: var(--red); }
.compact { width: 132px; max-width: 100%; }
.compact label { font-size: 11.5px; font-weight: 700; color: var(--text-muted); margin-bottom: 4px; }
.compact input { margin-top: 0; padding: 7px 8px; }
.visually-hidden { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
</style>
