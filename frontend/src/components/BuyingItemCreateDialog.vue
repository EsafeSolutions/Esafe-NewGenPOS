<!-- Copyright (c) 2026 Esafe (PVT) LTD. SPDX-License-Identifier: AGPL-3.0-only -->
<template>
  <dialog ref="dialog" class="modal emergency-item-dialog" :aria-label="t('Emergency item entry')" @cancel.prevent="close">
    <form @submit.prevent="create">
      <header class="modal-header"><h2>{{ t('Emergency item entry') }}</h2><button class="btn btn-ghost" type="button" :disabled="saving" :aria-label="t('Close')" @click="close">×</button></header>
      <div class="modal-body">
        <fieldset :disabled="saving || session.offline || uncertain">
          <p class="muted intro">{{ t('Create a missing product and add it to this purchase draft. Stock is received when you submit the invoice.') }}</p>
          <label>{{ t('Item name') }}<input v-model.trim="draft.item_name" autofocus required maxlength="140" /></label>
          <ItemIdentifierField v-model="draft.item_code" :label="t('Item code')" target="item_code" required :exclude="[draft.barcode]" @busy="generatingCode = $event" />
          <div class="entry-grid">
            <label>{{ t('Category') }}<select v-model="draft.item_group" required><option value="" disabled>{{ t('Choose a category') }}</option><option v-for="name in options.item_groups" :key="name">{{ name }}</option></select></label>
            <label>{{ t('Stock unit') }}<select v-model="draft.stock_uom" required><option value="" disabled>{{ t('Choose a unit') }}</option><option v-for="name in options.stock_uoms" :key="name">{{ name }}</option></select></label>
            <label>{{ t('Quantity') }}<input v-model="quantity" inputmode="decimal" required :aria-invalid="!validQuantity" /></label>
            <label>{{ t('Unit cost') }} ({{ currency }})<input v-model="cost" inputmode="decimal" required :aria-invalid="cost !== '' && !validCost" /></label>
          </div>
          <p class="muted unit-note">{{ t('Enter quantity and cost per stock unit on the supplier invoice.') }}</p>
          <label>{{ t('Standard selling price') }} ({{ options.selling_price_list?.currency || currency }})<input v-model="sellingPrice" inputmode="decimal" :placeholder="t('Optional')" :disabled="!canSetSellingPrice" :aria-invalid="!validSellingPrice" /></label>
          <p class="muted unit-note">{{ canSetSellingPrice
            ? t('Saved to {list} per stock unit ({unit}). Leave blank to set the price later.', { list: options.selling_price_list.name, unit: draft.stock_uom || t('choose a unit') })
            : t(options.can_edit_prices ? 'Configure an enabled, accessible selling price list on this outlet to set a selling price.' : 'Item price editing access is required to set a selling price.') }}</p>
          <label>{{ t('Barcode (optional)') }}<input v-model.trim="draft.barcode" maxlength="140" /></label>
          <p v-if="!options.item_groups?.length || !options.stock_uoms?.length" class="entry-error">{{ t('Ask an administrator to configure an accessible item category and stock unit.') }}</p>
          <p class="muted unit-note">{{ t('The item and any selling price are saved immediately, even if you later discard the purchase draft.') }}</p>
        </fieldset>
        <div v-if="error || session.offline" ref="feedback" class="entry-feedback" role="alert">
          <p class="entry-error">{{ session.offline ? t('Connect to the server to create an item.') : error }}</p>
          <button v-if="uncertain" class="btn btn-outline" type="button" :disabled="session.offline" @click="$emit('find', draft.item_code)">{{ t('Find saved item') }}</button>
        </div>
      </div>
      <footer class="modal-footer"><button class="btn btn-outline" type="button" :disabled="saving" @click="close">{{ t('Cancel') }}</button><button class="btn btn-primary" type="submit" :disabled="!valid || saving || session.offline || uncertain || generatingCode">{{ t(saving ? 'Saving…' : 'Create and add item') }}</button></footer>
    </form>
  </dialog>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { call, OfflineError } from '../api'
import { parseMoney } from '../format'
import { t } from '../i18n'
import { useSessionStore } from '../stores/session'
import ItemIdentifierField from './ItemIdentifierField.vue'

const props = defineProps({ options: { type: Object, required: true }, initialName: { type: String, default: '' }, currency: { type: String, required: true } })
const emit = defineEmits(['created', 'close', 'find'])
const session = useSessionStore()
const dialog = ref(null)
const feedback = ref(null)
const saving = ref(false)
const generatingCode = ref(false)
const error = ref('')
const uncertain = ref(false)
const draft = reactive({ item_name: props.initialName.slice(0, 140), item_code: '', item_group: '', stock_uom: '', barcode: '' })
const quantity = ref('1')
const cost = ref('')
const sellingPrice = ref('')
const canSetSellingPrice = computed(() => props.options.can_edit_prices && Boolean(props.options.selling_price_list?.name))
const validSellingPrice = computed(() => sellingPrice.value.trim() === '' || (canSetSellingPrice.value && parseMoney(sellingPrice.value) > 0))
watch([draft, quantity, cost, sellingPrice], () => { if (!uncertain.value) error.value = '' }, { deep: true })
const validQuantity = computed(() => parseMoney(quantity.value) > 0)
const validCost = computed(() => parseMoney(cost.value) > 0)
const valid = computed(() => draft.item_name && draft.item_code.trim() && props.options.item_groups?.includes(draft.item_group) &&
  props.options.stock_uoms?.includes(draft.stock_uom) && validQuantity.value && validCost.value && validSellingPrice.value)
let active = true
onMounted(() => dialog.value.showModal())
onBeforeUnmount(() => { active = false; dialog.value?.close() })
function close() { if (!saving.value) emit('close') }

async function create() {
  if (!valid.value || saving.value || generatingCode.value || session.offline || uncertain.value) return
  const profile = session.posProfile
  saving.value = true; error.value = ''
  try {
    const price = parseMoney(sellingPrice.value)
    const result = await call('esafepos.api.items.create_item', { pos_profile: profile, ...draft,
      ...(canSetSellingPrice.value && price > 0 ? { price_list: props.options.selling_price_list.name,
        prices: JSON.stringify([{ uom: draft.stock_uom, price }]) } : {}),
    })
    if (!active || profile !== session.posProfile) return
    emit('created', { item: { name: result.item_code, item_name: draft.item_name, stock_uom: draft.stock_uom, is_stock_item: 1 },
      qty: parseMoney(quantity.value), rate: parseMoney(cost.value) })
  } catch (failure) {
    if (!active || profile !== session.posProfile) return
    uncertain.value = failure instanceof OfflineError
    error.value = uncertain.value
      ? t('The response was lost. Search for item code {code} before trying again; it may already be saved.', { code: draft.item_code })
      : failure.message
    await nextTick()
    feedback.value?.scrollIntoView({ block: 'nearest' })
  } finally { saving.value = false }
}
</script>

<style scoped>
.emergency-item-dialog { padding: 0; border: 1px solid var(--border); color: var(--text); max-height: 92dvh; }
.emergency-item-dialog:not([open]) { display: none; }
.emergency-item-dialog::backdrop { background: rgba(24, 30, 44, 0.55); }
form { display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.modal-body { min-height: 0; }
.modal-header, .modal-footer { flex-shrink: 0; }
h2 { margin: 0; font-size: 18px; }
fieldset { border: 0; padding: 0; margin: 0; min-width: 0; display: grid; gap: 14px; }
label { display: grid; gap: 6px; min-width: 0; font-size: 12px; font-weight: 600; }
input, select { width: 100%; min-width: 0; min-height: 42px; }
.entry-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.intro, .unit-note, .entry-feedback { margin: 0; font-size: 12px; line-height: 1.6; }
.entry-error { color: var(--red); margin: 0; }
.entry-feedback { padding-top: 12px; }
.entry-feedback .btn { margin-top: 8px; }
.modal-footer { flex-wrap: wrap; }
@media (max-width: 520px) {
  .modal-header, .modal-body, .modal-footer { padding: 14px; }
  .entry-grid { grid-template-columns: minmax(0, 1fr); gap: 12px; }
  .modal-footer .btn-primary { flex: 1; }
}
</style>
