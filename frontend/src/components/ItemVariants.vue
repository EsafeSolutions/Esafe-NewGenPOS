<template>
  <div class="variants-page">
    <p v-if="session.offline" class="card variants-card">{{ t('Managing variants needs a connection.') }}</p>
    <template v-else>
      <aside class="card variants-card">
        <div class="section-head"><h2>{{ t('Item templates') }}</h2><button v-if="options.can_create" class="btn btn-primary" type="button" :disabled="busy" @click="creating = true"><Icon name="plus" />{{ t('New template') }}</button></div>
        <form class="template-search" @submit.prevent="searchTemplates()"><input v-model="query" :aria-label="t('Find a template')" :placeholder="t('Template name or code')" /><button class="btn btn-outline" :disabled="loading">{{ t('Search') }}</button></form>
        <p class="muted">{{ t('Use templates for products with sizes, colors or other attributes. Each combination has its own price, barcode and stock.') }}</p>
        <p v-if="error" role="alert">{{ error }} <button class="btn btn-outline" @click="initialize">{{ t('Retry') }}</button></p>
        <p v-if="loading" role="status">{{ t('Loading…') }}</p>
        <div class="template-list"><button v-for="item in templates" :key="item.name" type="button" :class="{ selected: selected?.item_code === item.name }" :aria-pressed="selected?.item_code === item.name" :disabled="busy" @click="openTemplate(item.name)"><strong>{{ item.item_name }}</strong><small class="muted">{{ item.name }} <span v-if="item.disabled">· {{ t('Disabled') }}</span></small></button></div>
        <p v-if="!loading && !templates.length" class="muted">{{ t('No templates found. Create a template to start adding variants.') }}</p>
        <button v-if="hasMore" class="btn btn-outline" :disabled="loading || busy" @click="searchTemplates(true)">{{ t('Load more templates') }}</button>
        <button v-if="options.can_create_attribute" type="button" class="btn btn-outline" :disabled="busy" @click="showAttribute = !showAttribute">{{ t('New attribute') }}</button>
        <form v-if="showAttribute" class="attribute-form" @submit.prevent="createAttribute">
          <h3>{{ t('Create attribute') }}</h3><label>{{ t('Attribute name') }}<input v-model.trim="attributeName" placeholder="Color" maxlength="140" required :disabled="busy" /></label>
          <label>{{ t('Values and abbreviations') }}<textarea v-model="attributeValues" rows="5" placeholder="Red=R&#10;Blue=B" required :disabled="busy" /></label>
          <small class="muted">{{ t('One value per line: value=abbreviation. Abbreviations are used in variant item codes.') }}</small>
          <button class="btn btn-primary" :disabled="busy">{{ t('Create attribute') }}</button>
        </form>
      </aside>
      <form v-if="creating" class="card variants-card" @submit.prevent="createTemplate">
        <div class="section-head"><h2>{{ t('New item template') }}</h2><button class="btn btn-outline" type="button" :disabled="busy" @click="creating = false">{{ t('Cancel') }}</button></div>
        <fieldset :disabled="busy"><label>{{ t('Template code') }}<input v-model.trim="templateCode" maxlength="140" required /></label><label>{{ t('Item name') }}<input v-model.trim="templateName" maxlength="140" required /></label>
          <div class="form-pair"><label>{{ t('Category') }}<select v-model="templateGroup" required><option value="" disabled>{{ t('Choose a category') }}</option><option v-for="name in editorOptions.item_groups || []" :key="name" :value="name">{{ name }}</option></select></label>
            <label>{{ t('Stock unit') }}<select v-model="templateUom" required><option value="" disabled>{{ t('Choose a unit') }}</option><option v-for="name in editorOptions.stock_uoms || []" :key="name" :value="name">{{ name }}</option></select></label></div>
          <h3>{{ t('Template attributes') }}</h3><div class="attribute-choices"><label v-for="attribute in options.attributes" :key="attribute.name"><input v-model="templateAttributes" type="checkbox" :value="attribute.name" />{{ attribute.name }}</label></div>
          <p v-if="!options.attributes.length" class="muted">{{ t('Create an attribute first, such as Color or Size.') }}</p>
          <button class="btn btn-primary" :disabled="!templateAttributes.length">{{ busy ? t('Creating…') : t('Create template') }}</button>
        </fieldset>
      </form>
      <section v-else-if="selected" class="card variants-card">
        <div class="section-head"><div><h2>{{ selected.item_name }}</h2><small class="muted">{{ selected.item_code }}</small></div><button class="btn btn-outline" type="button" :disabled="busy" @click="emit('open', selected.item_code)">{{ t('Edit template') }}</button></div>
        <p v-if="selected.disabled" class="muted">{{ t('Enable this template in Item details before creating variants.') }}</p>
        <p v-else-if="selected.variant_based_on !== 'Item Attribute'" class="muted">{{ t('Manufacturer-based variants are managed in ERPNext.') }}</p>
        <form v-else-if="options.can_create" class="new-variant" @submit.prevent="createVariant">
          <h3>{{ t('Add a variant') }}</h3><fieldset :disabled="busy"><div class="form-pair">
            <label v-for="name in selected.attributes" :key="name">{{ name }}
              <input v-if="attributeByName(name)?.numeric_values" v-model="values[name]" type="number" :min="attributeByName(name).from_range" :max="attributeByName(name).to_range" :step="attributeByName(name).increment" required />
              <select v-else v-model="values[name]" required><option value="" disabled>{{ t('Choose a value') }}</option><option v-for="value in attributeByName(name)?.values || []" :key="value" :value="value">{{ value }}</option></select>
            </label></div><button class="btn btn-primary" :disabled="!selected.attributes.length">{{ busy ? t('Creating…') : t('Create variant') }}</button></fieldset>
        </form>
        <div class="section-head"><h3>{{ t('Variants') }}</h3><button class="btn btn-outline" type="button" :disabled="busy" @click="openTemplate(selected.item_code)">{{ t('Refresh') }}</button></div>
        <p v-if="!selected.variants.length" class="muted">{{ t('No variants yet. Choose attribute values above to create the first one.') }}</p>
        <div class="variant-rows"><div v-for="item in selected.variants" :key="item.name" class="variant-row"><div><strong>{{ item.item_name }}</strong><small class="muted">{{ item.name }} · {{ item.stock_uom }}</small></div><span :class="{ 'disabled-label': item.disabled }">{{ item.disabled ? t('Disabled') : t('Active') }}</span><button class="btn btn-outline" type="button" :disabled="busy" @click="emit('open', item.name)">{{ t('Manage item') }}</button></div></div>
        <button v-if="moreVariants" class="btn btn-outline" :disabled="busy" @click="openTemplate(selected.item_code, true)">{{ t('Load more variants') }}</button>
      </section>
      <p v-else class="card variants-card muted">{{ t('Select a template to manage its variants.') }}</p>
    </template>
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { call } from '../api'
import Icon from './Icon.vue'
import { t } from '../i18n'
import { useSessionStore } from '../stores/session'
import { useCatalogStore } from '../stores/catalog'
defineProps({ editorOptions: { type: Object, default: () => ({}) } })
const emit = defineEmits(['open'])
const session = useSessionStore(), catalog = useCatalogStore()
const options = ref({ attributes: [] }), templates = ref([]), selected = ref(null), query = ref('')
const loading = ref(false), busy = ref(false), error = ref(''), hasMore = ref(false), moreVariants = ref(false), creating = ref(false)
const showAttribute = ref(false), attributeName = ref(''), attributeValues = ref('')
const templateCode = ref(''), templateName = ref(''), templateGroup = ref(''), templateUom = ref(''), templateAttributes = ref([]), values = ref({})
let request = 0, detailRequest = 0, generation = 0, activeQuery = ''
const attributeByName = name => options.value.attributes.find(attribute => attribute.name === name)
async function initialize() {
  if (session.offline || !session.permissions.edit_items) return
  const version = ++generation
  try {
    const result = await call('esafepos.api.item_variants.options', { pos_profile: session.posProfile })
    if (version !== generation) return
    options.value = result; await searchTemplates()
  } catch (err) { if (version === generation) error.value = err.message }
}
async function searchTemplates(append = false) {
  if (session.offline) return
  const id = ++request
  if (!append) { activeQuery = query.value; templates.value = []; hasMore.value = false }
  loading.value = true; error.value = ''
  try {
    const rows = await call('esafepos.api.items.search_items', { pos_profile: session.posProfile, search: activeQuery,
      item_type: 'template', status: 'all', start: append ? templates.value.length : 0, limit: 50 })
    if (id !== request) return
    templates.value = append ? [...templates.value, ...rows] : rows; hasMore.value = rows.length === 50
  } catch (err) { if (id === request) error.value = err.message }
  finally { if (id === request) loading.value = false }
}
async function openTemplate(code, append = false) {
  const id = ++detailRequest
  busy.value = true; error.value = ''
  try {
    const result = await call('esafepos.api.item_variants.template_details', { pos_profile: session.posProfile, item_code: code,
      start: append ? selected.value.variants.length : 0 })
    if (id !== detailRequest) return
    const rows = result.variants
    selected.value = append ? { ...result, variants: [...selected.value.variants, ...rows] } : result
    moreVariants.value = rows.length === 50; creating.value = false
    if (!append) values.value = Object.fromEntries(result.attributes.map(name => [name, '']))
  } catch (err) { if (id === detailRequest) error.value = err.message }
  finally { if (id === detailRequest) busy.value = false }
}
async function mutate(fn) {
  if (busy.value || session.offline) return
  busy.value = true; error.value = ''
  try { await fn() } catch (err) { error.value = err.message }
  finally { busy.value = false }
}
function createAttribute() { return mutate(async () => {
  const rows = attributeValues.value.split('\n').filter(line => line.trim()).map(line => {
    const split = line.lastIndexOf('='); return { attribute_value: split < 0 ? '' : line.slice(0, split).trim(), abbr: split < 0 ? '' : line.slice(split + 1).trim() }
  })
  await call('esafepos.api.item_variants.create_attribute', { pos_profile: session.posProfile, attribute_name: attributeName.value, values: rows })
  showAttribute.value = false; attributeName.value = ''; attributeValues.value = ''; await initialize()
  session.notify(t('Attribute created'))
}) }
function createTemplate() { return mutate(async () => {
  const result = await call('esafepos.api.item_variants.create_template', { pos_profile: session.posProfile, item_code: templateCode.value,
    item_name: templateName.value, item_group: templateGroup.value, stock_uom: templateUom.value,
    attributes: templateAttributes.value.map(attribute => ({ attribute })) })
  templateCode.value = ''; templateName.value = ''; templateAttributes.value = []
  await searchTemplates(); await openTemplate(result.item_code); session.notify(t('Template created'))
}) }
function createVariant() { return mutate(async () => {
  const result = await call('esafepos.api.item_variants.create_variant', { pos_profile: session.posProfile,
    template_code: selected.value.item_code, values: values.value }, { timeout: 60000 })
  await openTemplate(selected.value.item_code); await catalog.fetch(); catalog.cacheFullCatalog()
  session.notify(result.existing ? t('This variant already exists') : t('Variant created'))
}) }
watch(() => [session.posProfile, session.offline], () => { generation++; request++; detailRequest++; selected.value = null; templates.value = []; options.value = { attributes: [] }; initialize() }, { immediate: true })
onBeforeUnmount(() => { generation++; request++; detailRequest++ })
</script>

<style scoped>
.variants-page { flex: 1; min-height: 0; min-width: 0; overflow: auto; padding: 16px; display: grid; grid-template-columns: minmax(0, .85fr) minmax(0, 1.15fr); gap: 16px; align-items: start; }
.variants-card { padding: 18px; display: grid; gap: 16px; min-width: 0; } h2, h3, p { margin: 0; } h2 { font-size: 17px; } h3 { font-size: 15px; } p { line-height: 1.6; }
.section-head { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
.template-search { display: flex; gap: 8px; } .template-search input { min-width: 0; flex: 1; }
.template-list { display: grid; max-height: 50vh; overflow: auto; } .template-list button { text-align: start; padding: 14px 10px; border-bottom: 1px solid var(--border); }
.template-list .selected { background: var(--surface-2); color: var(--brand-dark); } small { display: block; margin-top: 5px; }
label, fieldset, .new-variant, .attribute-form { display: grid; gap: 8px; min-width: 0; } fieldset { border: 0; padding: 0; margin: 0; gap: 16px; } input, select, textarea { width: 100%; min-width: 0; } textarea { resize: vertical; }
.form-pair { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; } .attribute-choices { display: flex; gap: 16px; flex-wrap: wrap; } .attribute-choices label { display: flex; align-items: center; } .attribute-choices input { width: 17px; height: 17px; accent-color: var(--brand); }
.attribute-form, .new-variant { border-top: 1px solid var(--border); padding-top: 16px; gap: 14px; }
.variant-row { display: flex; align-items: center; gap: 12px; padding: 14px 0; border-bottom: 1px solid var(--border); } .variant-row > div { min-width: 0; overflow-wrap: anywhere; flex: 1; } .variant-row > span { font-size: 12px; color: var(--brand-dark); } .variant-row > span.disabled-label { color: var(--red); }
@media (max-width: 720px) { .variants-page { grid-template-columns: minmax(0, 1fr); align-content: start; } .form-pair { grid-template-columns: minmax(0, 1fr); } .variant-row { flex-wrap: wrap; } }
</style>
