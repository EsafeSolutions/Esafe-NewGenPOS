<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only -->
<template>
  <div class="modal-backdrop" @click.self="$emit('close')" @keydown.esc="$emit('close')">
    <form class="modal item-detail" role="dialog" aria-modal="true" :aria-label="item.item_name" @submit.prevent="save">
      <header class="modal-header">
        <span>{{ item.item_name }}</span>
        <button ref="closeButton" type="button" class="btn btn-ghost" :aria-label="t('Close')" @click="$emit('close')"><Icon name="close" /></button>
      </header>
      <div class="modal-body item-detail-body">
        <img v-if="item.image" :src="item.image" :alt="item.item_name" />
        <p class="muted">{{ [item.item_code, item.brand, item.stock_uom || item.uom].filter(Boolean).join(' · ') }}</p>
        <p class="description">{{ plainText(item.description) || t('No description available.') }}</p>
        <p v-if="loadingPrices" class="muted" role="status">{{ t('Confirming customer prices…') }}</p>
        <p v-if="priceError" class="price-error" role="alert">{{ priceError }} <button type="button" class="btn btn-outline" @click="loadPrices">{{ t('Retry') }}</button></p>
        <div class="item-edit">
          <label v-if="units.length > 1">{{ t('Selling unit') }}
            <select v-model="selectedUnit" @change="resetUnit">
              <option v-for="unit in units" :key="unit.uom" :value="unit.uom">{{ unitLabel(unit) }}</option>
            </select>
          </label>
          <label>{{ t('Quantity') }}<span v-if="selectedUnit"> ({{ selectedUnit }})</span>
            <input v-model.number="qty" type="number" :min="quantityStep" :step="quantityStep" required :disabled="Boolean(item.has_serial_no)" />
          </label>
          <QuantityAmountField v-if="!item.has_serial_no" id="item-quantity-amount"
            v-model:quantity="qty" :unit-price="amountRate" :currency="cart.saleCurrency.currency"
            :unit="selectedUnit" :whole-quantity="Boolean(option.whole_qty)" :disabled="loadingPrices || Boolean(priceError)"
            @validity="amountValid = $event" />
          <label>{{ t('Unit price') }} ({{ cart.saleCurrency.currency }})
            <input v-model.number="price" type="number" min="0" step="any" :disabled="!session.permissions?.can_change_price" />
          </label>
          <label>{{ t('Item discount method') }}
            <select v-model="method" :disabled="!canDiscount">
              <option value="percent">{{ t('Percent') }}</option>
              <option value="amount">{{ t('Discount per unit') }}</option>
            </select>
          </label>
          <label>{{ t('Discount') }} ({{ method === 'percent' ? '%' : cart.saleCurrency.currency }})
            <input v-model.number="discount" type="number" min="0" :max="method === 'percent' ? 100 : undefined" step="any" required :disabled="!canDiscount" />
          </label>
        </div>
        <p v-if="option.factor !== 1" class="muted">{{ t('Stock used: {qty} {unit}', { qty: Math.round(qty * option.factor * 10000) / 10000, unit: stockUnit }) }}</p>
        <p v-if="item.has_serial_no" class="muted">{{ t('Quantity follows the scanned serial numbers.') }}</p>
      </div>
      <footer class="modal-footer">
        <button type="button" class="btn btn-outline" @click="$emit('close')">{{ t('Cancel') }}</button>
        <button class="btn btn-primary" type="submit" :disabled="!amountValid || loadingPrices || Boolean(priceError)">{{ activeLine ? t('Update cart') : t('Add to cart') }}</button>
      </footer>
    </form>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Icon from './Icon.vue'
import QuantityAmountField from './QuantityAmountField.vue'
import { money, plainText } from '../format'
import { t } from '../i18n'
import { useCartStore } from '../stores/cart'
import { useSessionStore } from '../stores/session'
import { call } from '../api'

const props = defineProps({ item: { type: Object, required: true }, line: Object })
const emit = defineEmits(['close', 'save'])
const cart = useCartStore()
const session = useSessionStore()
const canDiscount = computed(() => session.permissions?.can_edit_price !== false)
const stockUnit = props.item.stock_uom || props.item.uom || ''
const prices = ref(null)
const loadingPrices = ref(false)
const priceError = ref('')
let priceRequest = 0
const units = computed(() => [
  { uom: stockUnit, factor: 1, price: prices.value?.prices?.[props.item.item_code] ?? props.item.price, whole_qty: props.item.whole_qty },
  ...(!session.offline && !cart.saleCurrency.foreign && !cart.appType ? (props.item.selling_units || []).map(unit => ({
    ...unit, price: prices.value?.selling_units?.[props.item.item_code]?.[unit.uom] ?? unit.price,
  })) : []),
])
const selectedUnit = ref(stockUnit)
const option = computed(() => units.value.find((unit) => unit.uom === selectedUnit.value) || units.value[0])
function unitLabel(unit) {
  const pack = unit.factor !== 1 ? ` (${unit.factor} ${stockUnit})` : ''
  return `${unit.uom}${pack} · ${money(cart.inSale(unit.price), cart.saleCurrency.currency)}`
}
const activeLine = computed(() => selectedUnit.value === stockUnit ? props.line :
  cart.lines.find((line) => !line.bundle_key && line.item_code === props.item.item_code && line.selling_uom === selectedUnit.value))
const quantityStep = computed(() => option.value.whole_qty ? 1 : 0.0001)
const sourcePrice = computed(() => activeLine.value?.price_override != null || !prices.value
  ? activeLine.value?.price ?? option.value.price : option.value.price)
const initialPrice = computed(() => activeLine.value?.price_override ?? cart.inSale(sourcePrice.value))
const initialMethod = computed(() => activeLine.value?.manual_discount_method || 'percent')
const initialDiscount = computed(() => (initialMethod.value === 'amount'
  ? activeLine.value?.manual_discount_amount : activeLine.value?.manual_discount_percent) || 0)
const qty = ref(1)
const price = ref(0)
const method = ref('percent')
const discount = ref(0)
const amountValid = ref(true)
const amountRate = computed(() => price.value === initialPrice.value
  ? Number(sourcePrice.value) * (cart.saleCurrency.blocked ? 1 : cart.saleCurrency.factor || 1)
  : Number(price.value))
function resetUnit() {
  qty.value = activeLine.value?.qty || 1
  price.value = initialPrice.value
  method.value = initialMethod.value
  discount.value = initialDiscount.value
}
resetUnit()
watch(initialPrice, (value, previous) => {
  if (price.value === previous) price.value = value
})
watch(() => [session.posProfile, session.offline, cart.customer?.name, cart.customer?.customer_group, cart.appType], loadPrices, { immediate: true })

async function loadPrices() {
  const request = ++priceRequest
  prices.value = null
  priceError.value = ''
  loadingPrices.value = false
  if (session.offline || (!cart.customer && !cart.appType)) return
  loadingPrices.value = true
  try {
    const result = await call('esafepos.api.catalog.get_prices', {
      pos_profile: session.posProfile, item_codes: [props.item.item_code],
      customer: cart.customer?.name || null, customer_group: cart.customer?.customer_group || null,
      app_type: cart.appType,
    })
    if (request === priceRequest) prices.value = result
  } catch (error) {
    if (request === priceRequest) priceError.value = error.message
  } finally {
    if (request === priceRequest) loadingPrices.value = false
  }
}
const closeButton = ref(null)
const trigger = document.activeElement
onMounted(() => closeButton.value?.focus())
onBeforeUnmount(() => { priceRequest++; trigger?.focus() })

function save() {
  if (!amountValid.value || loadingPrices.value || priceError.value) return
  emit('save', {
    qty: Number(qty.value),
    basePrice: Number(sourcePrice.value),
    standardPrice: prices.value?.standard_prices?.[props.item.item_code] ?? props.item.standard_price ?? props.item.price,
    ...(option.value.factor !== 1 || selectedUnit.value !== stockUnit ? { unit: option.value } : {}),
    price: price.value !== initialPrice.value && session.permissions?.can_change_price ? price.value : null,
    discount: (discount.value !== initialDiscount.value || method.value !== initialMethod.value) && canDiscount.value
      ? discount.value : null,
    method: method.value,
  })
}
</script>

<style scoped>
.item-detail { width: min(620px, calc(100vw - 24px)); max-height: calc(100dvh - 24px); display: flex; flex-direction: column; }
.item-detail-body { overflow-y: auto; }
.item-detail-body img { display: block; width: 100%; height: min(32vh, 280px); object-fit: contain; background: var(--surface-2); border-radius: 8px; }
.description { white-space: pre-wrap; line-height: 1.55; overflow-wrap: anywhere; }
.price-error { color: var(--red); line-height: 1.5; }
.item-edit { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.item-edit label { display: block; }
.item-edit input, .item-edit select { display: block; width: 100%; margin-top: 5px; }
</style>
