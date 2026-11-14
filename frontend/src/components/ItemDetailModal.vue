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
        <div class="item-edit">
          <label>{{ t('Quantity') }}<span v-if="item.stock_uom || item.uom"> ({{ item.stock_uom || item.uom }})</span>
            <input v-model.number="qty" type="number" :min="quantityStep" :step="quantityStep" required :disabled="Boolean(item.has_serial_no)" />
          </label>
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
        <p v-if="item.has_serial_no" class="muted">{{ t('Quantity follows the scanned serial numbers.') }}</p>
      </div>
      <footer class="modal-footer">
        <button type="button" class="btn btn-outline" @click="$emit('close')">{{ t('Cancel') }}</button>
        <button class="btn btn-primary" type="submit">{{ line ? t('Update cart') : t('Add to cart') }}</button>
      </footer>
    </form>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import Icon from './Icon.vue'
import { plainText } from '../format'
import { t } from '../i18n'
import { useCartStore } from '../stores/cart'
import { useSessionStore } from '../stores/session'

const props = defineProps({ item: { type: Object, required: true }, line: Object })
const emit = defineEmits(['close', 'save'])
const cart = useCartStore()
const session = useSessionStore()
const canDiscount = computed(() => session.permissions?.can_edit_price !== false)
const quantityStep = computed(() => props.item.whole_qty ? 1 : 0.0001)
const qty = ref(props.line?.qty || 1)
const initialPrice = props.line?.price_override ?? cart.inSale(props.line?.price ?? props.item.price)
const price = ref(initialPrice)
const initialMethod = props.line?.manual_discount_method || 'percent'
const method = ref(initialMethod)
const initialDiscount = (initialMethod === 'amount' ? props.line?.manual_discount_amount : props.line?.manual_discount_percent) || 0
const discount = ref(initialDiscount)
const closeButton = ref(null)
const trigger = document.activeElement
onMounted(() => closeButton.value?.focus())
onBeforeUnmount(() => trigger?.focus())

function save() {
  emit('save', {
    qty: Number(qty.value),
    price: price.value !== initialPrice && session.permissions?.can_change_price ? price.value : null,
    discount: (discount.value !== initialDiscount || method.value !== initialMethod) && canDiscount.value
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
.item-edit { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.item-edit label { display: block; }
.item-edit input, .item-edit select { display: block; width: 100%; margin-top: 5px; }
</style>
