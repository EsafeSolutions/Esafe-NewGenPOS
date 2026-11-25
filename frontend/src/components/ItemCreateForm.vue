<template>
  <form class="card create-item" @submit.prevent="create">
    <h2>{{ t('Add item') }}</h2>
    <fieldset :disabled="saving">
      <ItemIdentifierField v-model="draft.item_code" :label="t('Item code')" target="item_code" required
        :exclude="[draft.barcode]" @busy="generatingCode = $event" />
      <label>{{ t('Item name') }}<input v-model.trim="draft.item_name" required maxlength="140" /></label>
      <label>{{ t('Category') }}<select v-model="draft.item_group" required><option value="" disabled>{{ t('Choose a category') }}</option><option v-for="name in options.item_groups" :key="name">{{ name }}</option></select></label>
      <label>{{ t('Stock unit') }}<select v-model="draft.stock_uom" required @change="clearUnitChoices"><option value="" disabled>{{ t('Choose a unit') }}</option><option v-for="name in options.stock_uoms" :key="name">{{ name }}</option></select></label>
      <label>{{ t('Brand') }}<select v-model="draft.brand"><option value="">{{ t('No brand') }}</option><option v-for="name in options.brands" :key="name">{{ name }}</option></select></label>
      <div class="barcode-field">
        <ItemIdentifierField v-model="draft.barcode" :label="t('Barcode (optional)')" target="barcode"
          :exclude="[draft.item_code]" @busy="generatingBarcode = $event" />
        <label v-if="draft.barcode">{{ t('Barcode unit') }}
          <select v-model="barcodeUom"><option :value="draft.stock_uom">{{ draft.stock_uom || t('Stock unit') }}</option>
            <option v-for="unit in sellingUnits" :key="unit.uom" :value="unit.uom">{{ unit.uom }}</option>
          </select>
        </label>
      </div>
      <section class="create-units">
        <div class="section-heading"><h3>{{ t('Selling prices') }}</h3><span v-if="priceList">{{ priceList }}</span></div>
        <label v-if="options.can_edit_prices && options.price_lists?.length">{{ t('Selling price list') }}
          <select v-model="priceList"><option v-for="list in options.price_lists" :key="list.name" :value="list.name">{{ list.name }} · {{ list.currency }}</option></select>
        </label>
        <label v-if="options.can_edit_prices">{{ draft.stock_uom }} {{ t('Price') }}
          <input v-model.number="stockPrice" type="number" min="0.000001" step="any" :placeholder="t('Selling price')" @input="updateAutoPrices" />
        </label>
        <div v-for="(unit, index) in sellingUnits" :key="index" class="create-unit-row">
          <label>{{ t('Selling unit') }}<select v-model="unit.uom" required @change="unitSelected(unit)">
            <option value="" disabled>{{ t('Choose a unit') }}</option>
            <option v-for="name in unitChoices(unit)" :key="name" :value="name">{{ name }}</option>
          </select></label>
          <label>{{ t('Conversion factor') }}<input v-model.number="unit.factor" type="number" min="0.000001" step="any" required @input="unitFactorChanged(unit)" /></label>
          <label v-if="options.can_edit_prices">{{ t('Unit price') }}<input v-model.number="unit.price" type="number" min="0.000001" step="any" :placeholder="t('Selling price')" @input="unit.auto_price = false; updateAutoPrices()" /></label>
          <button type="button" class="btn btn-outline" :aria-label="t('Remove selling unit')" @click="sellingUnits.splice(index, 1)">×</button>
        </div>
        <button type="button" class="btn btn-outline" :disabled="!unitChoices({ uom: '' }).length" @click="addUnit">{{ t('Add selling unit') }}</button>
        <p v-if="!options.can_edit_prices" class="muted">{{ t('You can add item units. Selling prices can be added by a user with item price access.') }}</p>
      </section>
      <p class="muted">{{ t('Creates a stock item. Add warehouse stock after saving.') }}</p>
      <button class="btn btn-primary" :disabled="generatingCode || generatingBarcode">{{ saving ? t('Saving…') : t('Create item') }}</button>
      <button type="button" class="btn btn-outline" @click="$emit('cancel')">{{ t('Cancel') }}</button>
    </fieldset>
  </form>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { call } from '../api'
import { t } from '../i18n'
import ItemIdentifierField from './ItemIdentifierField.vue'
import { useSessionStore } from '../stores/session'
const props = defineProps({ options: { type: Object, required: true } })
const emit = defineEmits(['created', 'cancel', 'busy'])
const session = useSessionStore()
const saving = ref(false)
const generatingCode = ref(false)
const generatingBarcode = ref(false)
const draft = reactive({ item_code: '', item_name: '', item_group: '', stock_uom: '', barcode: '', brand: '' })
const sellingUnits = ref([])
const stockPrice = ref('')
const barcodeUom = ref('')
const priceList = ref(props.options.default_price_list || props.options.price_lists?.[0]?.name || '')
function addUnit() {
  sellingUnits.value.push({ uom: '', factor: 1, price: '', auto_price: true })
}
function unitChoices(target) {
  return (props.options.uoms || props.options.stock_uoms || []).filter((name) => name !== draft.stock_uom &&
    (name === target.uom || !sellingUnits.value.some((unit) => unit !== target && unit.uom === name)))
}
function unitFactorChanged(unit) {
  if (unit.auto_price && stockPrice.value !== '' && stockPrice.value != null) {
    unit.price = Number(stockPrice.value) * (Number(unit.factor) || 0)
  }
}
function unitSelected(unit) {
  unit.factor = 1
  unit.auto_price = true
  unitFactorChanged(unit)
}
function updateAutoPrices() {
  sellingUnits.value.forEach(unitFactorChanged)
}
function clearUnitChoices() {
  sellingUnits.value = []
  stockPrice.value = ''
  barcodeUom.value = draft.stock_uom
}
async function create() {
  if (saving.value || generatingCode.value || generatingBarcode.value || session.offline) return
  saving.value = true
  emit('busy', true)
  const profile = session.posProfile
  try {
    const prices = []
    if (stockPrice.value !== '' && stockPrice.value != null) prices.push({ uom: draft.stock_uom, price: stockPrice.value })
    for (const unit of sellingUnits.value) {
      if (unit.price !== '' && unit.price != null) prices.push({ uom: unit.uom, price: unit.price })
    }
    const barcodes = draft.barcode ? [{ barcode: draft.barcode, uom: barcodeUom.value || draft.stock_uom }] : []
    const result = await call('esafepos.api.items.create_item', {
      pos_profile: profile, ...draft, price_list: priceList.value || null,
      selling_units: JSON.stringify(sellingUnits.value), prices: JSON.stringify(prices),
      barcodes: JSON.stringify(barcodes),
    })
    if (profile !== session.posProfile) return
    session.notify(t('Item created'))
    emit('created', result.item_code)
  } catch (error) {
    session.notify(error.message, true)
  } finally {
    saving.value = false
    emit('busy', false)
  }
}
</script>

<style scoped>
.create-item { padding: 16px; min-width: 0; }
h2 { margin: 0 0 16px; }
fieldset { border: 0; padding: 0; margin: 0; display: grid; gap: 14px; min-width: 0; }
label { display: grid; gap: 5px; }
input, select { width: 100%; min-width: 0; }
.barcode-field { display: grid; gap: 8px; }
.create-units { display: grid; gap: 10px; padding-top: 8px; border-top: 1px solid var(--border); }
.section-heading, .create-unit-row { display: flex; align-items: end; gap: 8px; }
.section-heading { justify-content: space-between; }
.section-heading h3 { margin: 0; }
.section-heading span { color: var(--text-muted); font-size: .85em; }
.create-unit-row > label { flex: 1; min-width: 0; }
@media (max-width: 520px) { .barcode-field, .create-unit-row { grid-template-columns: minmax(0, 1fr); display: grid; } }
</style>
