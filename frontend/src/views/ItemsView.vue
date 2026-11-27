<template>
  <section class="items-page">
    <div v-if="!session.permissions.edit_items" class="card items-card">{{ t('You do not have access to the Items editor.') }}</div>
    <div v-else-if="session.offline" class="card items-card">{{ t('Editing items needs a connection.') }}</div>
    <template v-else>
      <div class="card items-card item-browser">
        <div class="browser-heading"><h2>{{ section === 'inventory' ? t('Inventory') : t('Item catalog') }}</h2>
          <button v-if="options.can_create_items && section === 'details'" type="button" class="btn btn-primary" :disabled="saving || opening" @click="startCreate"><Icon name="plus" />{{ t('Add item') }}</button></div>
        <form class="item-search" @submit.prevent="searchItems()">
          <input v-model="search" :aria-label="t('Find an item')" :placeholder="t('Item name, code or barcode')" />
          <button class="btn btn-primary" :disabled="loading">{{ t('Search') }}</button>
        </form>
        <div class="item-filters">
          <SearchSelect v-model="group" :label="t('Category')" :options="groupOptions" @change="searchItems()" />
          <SearchSelect v-model="brand" :label="t('Brand')" :options="brandOptions" @change="searchItems()" />
        </div>
        <div class="item-filters">
          <label>{{ t('Status') }}<select v-model="status" :disabled="saving" @change="searchItems()"><option value="active">{{ t('Active items') }}</option><option value="disabled">{{ t('Disabled items') }}</option><option value="all">{{ t('All statuses') }}</option></select></label>
          <label v-if="section === 'details'">{{ t('Item type') }}<select v-model="itemType" :disabled="saving" @change="searchItems()"><option value="">{{ t('All item types') }}</option><option value="stock">{{ t('Stock items') }}</option><option value="service">{{ t('Services') }}</option><option value="template">{{ t('Templates') }}</option><option value="variant">{{ t('Variants') }}</option></select></label>
          <label v-else>{{ t('Warehouse') }}<select v-model="warehouse" :disabled="saving" @change="searchItems()"><option value="">{{ t('All warehouses') }}</option><option v-for="name in options.warehouses || []" :key="name" :value="name">{{ name }}</option></select></label>
        </div>
        <div class="result-meta"><small class="muted" role="status">{{ t('{n} items loaded', { n: items.length }) }}</small><button class="btn btn-outline" type="button" :disabled="!items.length || loading" @click="exportItems"><Icon name="download" />{{ t('Export loaded items') }}</button></div>
        <p v-if="searchError" role="alert">{{ searchError }} <button class="btn btn-outline" type="button" @click="searchItems()">{{ t('Retry') }}</button></p>
        <div class="item-results">
          <div v-if="loading && !items.length" class="muted">{{ t('Loading…') }}</div>
          <div v-else-if="!items.length" class="muted">{{ t('No products found') }}</div>
          <button v-for="item in items" :key="item.name" class="item-result"
            :class="{ selected: draft?.item_code === item.name }" :aria-pressed="draft?.item_code === item.name"
            :disabled="saving" @click="openItem(item.name, selectedPriceList)">
            <span class="item-thumbnail"><img v-if="item.image" :src="item.image" alt="" loading="lazy" /><Icon v-else name="image" /></span>
            <span>
              <strong>{{ item.item_name }}</strong>
              <small class="muted">{{ [item.name, item.stock_uom, item.item_group, item.brand].filter(Boolean).join(' · ') }}</small>
              <small v-if="section === 'inventory' && item.available_qty != null" :class="{ 'empty-stock': item.available_qty <= 0 }">{{ t('{n} available', { n: item.available_qty }) }} · {{ t('{n} on hand', { n: item.actual_qty }) }}</small>
            </span>
            <span v-if="item.disabled" class="item-badge disabled-badge">{{ t('Disabled') }}</span>
            <span v-else-if="item.has_variants" class="item-badge">{{ t('Template') }}</span>
            <span v-else-if="item.variant_of" class="item-badge">{{ t('Variant') }}</span>
          </button>
          <button v-if="hasMore" class="btn btn-outline more-items" :disabled="loading || saving" @click="searchItems(true)">
            {{ loading ? t('Loading…') : t('Load more items') }}
          </button>
        </div>
      </div>
      <ItemCreateForm v-if="creating && section === 'details'" :options="options" @busy="saving = $event" @cancel="creating = false" @created="itemCreated" />
      <div v-else-if="draft" class="card items-card edit-item">
        <div v-if="section === 'inventory'" class="inventory-item-heading"><h2>{{ draft.item_name }}</h2><p class="muted">{{ draft.item_code }} · {{ draft.stock_uom }}</p></div>
        <form v-show="section === 'details'" @submit.prevent="save">
        <fieldset :disabled="saving || opening">
          <header>
            <h2>{{ draft.item_name }}</h2>
            <div class="muted">{{ [draft.item_code, draft.item_group, draft.brand].filter(Boolean).join(' · ') }}</div>
          </header>
          <p v-if="externalChanges" class="item-notice" role="status">{{ t('ERPNext has newer values. Your unsaved edits are kept.') }} <button type="button" class="btn btn-outline" @click="reloadCurrent">{{ t('Reload current values') }}</button></p>
          <div v-if="draft.has_variants" class="item-notice">{{ t('This is an item template. Manage attribute combinations in the Variants tab; set prices and stock on each variant.') }}</div>
          <div v-if="draft.variant_of" class="item-notice">{{ t('Variant of') }}: {{ draft.variant_of }}</div>
          <div v-if="draft.disabled" class="item-notice disabled-badge" role="status">{{ t('This item is disabled. Clear Disable item and save to enable it again.') }}</div>
          <div class="item-identity">
            <div class="image-preview">
              <img v-if="imagePreview && !previewFailed" :src="imagePreview" :alt="draft.item_name"
                referrerpolicy="no-referrer" @error="previewFailed = true" />
              <Icon v-else name="image" :size="32" />
            </div>
            <div class="identity-fields">
              <label>{{ t('Item name') }}<input v-model.trim="draft.item_name" :readonly="!draft.can_edit_item" required maxlength="140" /></label>
              <div v-if="draft.can_edit_item" class="image-attachment">
                <div>{{ t('Product image') }}</div>
                <div class="image-sources" role="group" :aria-label="t('Product image source')">
                  <button type="button" class="btn btn-outline" :class="{ 'source-active': imageSource === 'device' }"
                    :aria-pressed="imageSource === 'device'" @click="selectImageSource('device')">{{ t('My device') }}</button>
                  <button type="button" class="btn btn-outline" :class="{ 'source-active': imageSource === 'link' }"
                    :aria-pressed="imageSource === 'link'" @click="selectImageSource('link')">{{ t('Link') }}</button>
                  <a class="btn btn-outline" :href="onlineImageSearch" target="_blank" rel="noopener noreferrer">
                    {{ t('Find online') }}
                  </a>
                </div>
                <button v-if="options.gemini_image_search" type="button" class="btn btn-outline"
                  :disabled="refiningSearch" @click="refineImageSearch">
                  {{ refiningSearch ? t('Asking Gemini…') : t('Refine search with Gemini') }}
                </button>
                <small v-if="refinedSearch" class="muted" role="status">
                  {{ t('Gemini search terms: {query}', { query: refinedSearch }) }}
                </small>
                <label v-if="imageSource === 'device'">
                  <input :key="draft.item_code + imageReset" type="file" :aria-label="t('Choose product image')"
                    accept="image/jpeg,image/png,image/webp" @change="chooseImage" />
                  <small class="muted">{{ t('JPEG, PNG or WebP, up to 5 MB. Product images are stored in ERPNext.') }}</small>
                </label>
                <label v-else>{{ t('Image URL') }}
                  <input v-model.trim="imageLink" type="url" inputmode="url" placeholder="https://…"
                    maxlength="2048" pattern="[hH][tT][tT][pP][sS]://.+" @change="previewLink = imageLink" />
                  <small class="muted">{{ t('Paste a direct HTTPS image link. Use an image you have permission to use.') }}</small>
                  <small v-if="imageLink && previewFailed" class="muted" role="status">{{ t('Image preview unavailable. Check that the link opens the image and is publicly accessible.') }}</small>
                </label>
                <button v-if="imageFile || imageLink" type="button" class="btn btn-outline" @click="clearImage">{{ t('Discard selected image') }}</button>
              </div>
            </div>
          </div>
          <div class="metadata-fields">
            <label>{{ t('Category') }}<select v-model="draft.item_group" :disabled="!draft.can_edit_item"><option v-for="name in options.item_groups || []" :key="name" :value="name">{{ name }}</option></select></label>
            <label>{{ t('Brand') }}<select v-model="draft.brand" :disabled="!draft.can_edit_item"><option value="">{{ t('No brand') }}</option><option v-for="name in options.brands || []" :key="name" :value="name">{{ name }}</option></select></label>
            <label class="description-field">{{ t('Description') }}<textarea v-model="draft.description" :readonly="!draft.can_edit_item" rows="3" maxlength="10000" /></label>
          </div>
          <div class="item-settings">
            <label><input v-model="draft.disabled" type="checkbox" :disabled="!draft.can_edit_item" />{{ t('Disable item') }}</label>
            <label><input v-model="draft.is_sales_item" type="checkbox" :disabled="!draft.can_edit_item" />{{ t('Available for sale') }}</label>
            <label><input v-model="draft.is_purchase_item" type="checkbox" :disabled="!draft.can_edit_item" />{{ t('Available for purchase') }}</label>
          </div>
          <small v-if="draft.has_variants" class="muted">{{ t('Template changes follow ERPNext variant-field settings. Review the status of existing variants after saving.') }}</small>
          <label v-if="draft.price_list">{{ t('Selling price list') }}
            <select :value="draft.price_list" @change="changePriceList">
              <option v-for="list in priceLists" :key="list.name" :value="list.name">{{ list.name }} · {{ list.currency }}</option>
            </select>
          </label>
          <section v-if="!draft.has_variants" class="item-options-section">
            <div class="section-heading"><h3>{{ t('Selling units and prices') }}</h3>
              <button v-if="draft.can_edit_item && !draft.has_serial_no" type="button" class="btn btn-outline" @click="addSellingUnit">{{ t('Add UOM') }}</button>
            </div>
            <div class="unit-prices">
              <div v-for="unit in draft.units" :key="unit._key || unit.uom" class="unit-price-row">
                <label>{{ t('Selling unit') }}
                  <select v-if="unit.is_new" v-model="unit.uom" @change="unitSelected(unit)">
                    <option value="" disabled>{{ t('Choose a unit') }}</option>
                    <option v-for="name in unitChoices(unit)" :key="name" :value="name">{{ name }}</option>
                  </select>
                  <input v-else :value="unit.uom" readonly />
                </label>
                <label>{{ t('Conversion factor') }}
                  <input v-model.number="unit.factor" type="number" min="0.000001" step="any" :readonly="unit.uom === draft.stock_uom || (!unit.is_new && !draft.can_edit_item)" @input="unitFactorChanged(unit)" />
                  <small class="muted">1 {{ unit.uom || t('Selling unit') }} = {{ unit.factor || 0 }} {{ draft.stock_uom }}</small>
                </label>
                <label>{{ t('Selling price') }} <small v-if="draft.currency" class="muted">({{ draft.currency }})</small>
                  <input v-if="unit.editable" v-model.number="unit.price" type="number" min="0.000001" step="any" :placeholder="t('Selling price')" @input="unit.auto_price = false; updateAutoUnitPrices()" />
                  <span v-else class="price-readonly">{{ unit.active_price != null ? money(unit.active_price, draft.currency) : t('No price') }}</span>
                  <small v-if="unit.active_price != null" class="muted">{{ unit.has_explicit_price ? t('Current price') : t('Calculated from stock-unit price') }}: {{ money(unit.active_price, draft.currency) }}</small>
                </label>
                <button v-if="unit.uom !== draft.stock_uom && draft.can_edit_item" type="button" class="btn btn-outline unit-remove" :aria-label="t('Remove selling unit')" @click="removeSellingUnit(unit)">×</button>
              </div>
            </div>
            <p v-if="!draft.can_edit_prices" class="muted">{{ t('Selling prices are read-only for your account.') }}</p>
          </section>
          <section v-if="draft.can_edit_item && !draft.has_variants" class="item-options-section">
            <div class="section-heading"><h3>{{ t('Barcodes') }}</h3>
              <button type="button" class="btn btn-outline" @click="addBarcode">{{ t('Add barcode') }}</button>
            </div>
            <div v-for="(row, index) in draft.barcodes" :key="row._key" class="barcode-row">
              <ItemIdentifierField v-model="row.barcode" :label="t('Barcode')" target="barcode" :item-code="draft.item_code"
                :exclude="[draft.item_code, ...draft.barcodes.map((entry) => entry.barcode)]" @busy="row.generating = $event" />
              <label>{{ t('Barcode unit') }}<select v-model="row.uom"><option :value="draft.stock_uom">{{ draft.stock_uom }}</option>
                <option v-for="unit in draft.units.filter((entry) => entry.uom && entry.uom !== draft.stock_uom)" :key="unit.uom" :value="unit.uom">{{ unit.uom }}</option>
              </select></label>
              <button type="button" class="btn btn-outline" :aria-label="t('Remove barcode')" @click="draft.barcodes.splice(index, 1)">×</button>
            </div>
          </section>
          <small v-if="!draft.can_edit_prices" class="muted">{{ t('Your account cannot edit item selling prices.') }}</small>
          <small v-else-if="!draft.price_list" class="muted">{{ t('No selling price lists are available to your account.') }}</small>
          <button v-if="draft.can_edit_item || draft.units.some((unit) => unit.editable)" class="btn btn-primary"
            :disabled="draft.barcodes.some((row) => row.generating)">
            {{ saving ? t('Saving…') : t('Save changes') }}
          </button>
        </fieldset>
        </form>
        <ItemWarehouseStock v-if="options.can_view_stock && draft.is_stock_item && !draft.has_variants && !opening" v-show="section === 'inventory'" :key="draft.item_code" :item-code="draft.item_code" :active="section === 'inventory'" :disabled="saving" @busy="saving = $event" @updated="stockUpdated" />
        <p v-else-if="section === 'inventory'" class="muted">{{ t('Select a stock item or an individual variant to view inventory.') }}</p>
      </div>
      <div v-else class="card items-card muted">{{ opening ? t('Loading…') : t('Select an item to manage its details.') }}</div>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { call } from '../api'
import Icon from '../components/Icon.vue'
import SearchSelect from '../components/SearchSelect.vue'
import ItemCreateForm from '../components/ItemCreateForm.vue'
import ItemIdentifierField from '../components/ItemIdentifierField.vue'
import ItemWarehouseStock from '../components/ItemWarehouseStock.vue'
import { money } from '../format'
import { t } from '../i18n'
import { useCatalogStore } from '../stores/catalog'
import { useCartStore } from '../stores/cart'
import { useSessionStore } from '../stores/session'

const session = useSessionStore()
const props = defineProps({ section: { type: String, default: 'details' }, itemCode: { type: String, default: '' } })
const emit = defineEmits(['options'])
const catalog = useCatalogStore()
const cart = useCartStore()
const search = ref('')
const group = ref('')
const brand = ref('')
const status = ref('active')
const itemType = ref('')
const warehouse = ref('')
const searchError = ref('')
const options = ref({})
const selectedPriceList = ref('')
const priceLists = computed(() => options.value.price_lists || [])
const groupOptions = computed(() => [{ value: '', label: t('All categories') },
  ...(options.value.item_groups || []).map((value) => ({ value, label: value }))])
const brandOptions = computed(() => [{ value: '', label: t('All brands') },
  ...(options.value.brands || []).map((value) => ({ value, label: value }))])
const items = ref([])
const draft = ref(null)
const baseline = ref(''), externalChanges = ref(false)
function fingerprint(item) {
  if (!item) return ''
  return JSON.stringify([item.item_name, item.item_group, item.brand || '', item.description || '', Boolean(item.disabled),
    Boolean(item.is_sales_item), Boolean(item.is_purchase_item), (item.units || []).map(({ uom, factor, price }) => [uom, Number(factor), Number(price)]),
    (item.barcodes || []).map(({ barcode, uom }) => [barcode, uom])])
}
const dirty = computed(() => fingerprint(draft.value) !== baseline.value || imageFile.value || imageLink.value)
const creating = ref(false)
const loading = ref(false)
const hasMore = ref(false)
const saving = ref(false)
const opening = ref(false)
const imageFile = ref(null)
const preview = ref('')
const imageReset = ref(0)
const imageSource = ref('device')
const imageLink = ref('')
const previewLink = ref('')
const previewFailed = ref(false)
const refinedSearch = ref('')
const refiningSearch = ref(false)
const onlineImageSearch = computed(() => {
  const item = draft.value
  const terms = refinedSearch.value || [item?.brand, item?.item_name, item?.barcode].filter(Boolean).join(' ')
  return 'https://www.google.com/search?' + new URLSearchParams({ tbm: 'isch', q: terms })
})
const imagePreview = computed(() => {
  if (!previewLink.value) return preview.value || draft.value?.image
  try {
    const url = new URL(previewLink.value)
    return url.protocol === 'https:' && !url.username && !url.password ? url.href : ''
  } catch {
    return ''
  }
})
watch(imagePreview, () => { previewFailed.value = false })
const pageSize = 50
let activeFilters = {}
let request = 0
let detailRequest = 0

async function searchItems(append = false) {
  if (append && (loading.value || !hasMore.value)) return
  if (!append) {
    activeFilters = { search: search.value, item_group: group.value, brand: brand.value,
      status: status.value, item_type: props.section === 'inventory' ? 'stock' : itemType.value,
      include_stock: props.section === 'inventory' ? 1 : 0, warehouse: warehouse.value }
    hasMore.value = false
    items.value = []
  }
  loading.value = true
  searchError.value = ''
  const id = ++request
  try {
    const results = await call('esafepos.api.items.search_items', {
      pos_profile: session.posProfile, ...activeFilters,
      start: append ? items.value.length : 0, limit: pageSize,
    })
    if (id === request) {
      items.value = append ? [...items.value, ...results] : results
      hasMore.value = results.length === pageSize
    }
  } catch (error) {
    if (id === request) searchError.value = error.message
  } finally {
    if (id === request) loading.value = false
  }
}

function setDraft(item) {
  draft.value = {
    ...item,
    brand: item.brand || '', description: item.description || '',
    originalName: item.item_name,
    units: item.units.map((unit, index) => ({
      ...unit, _key: `${unit.uom || 'unit'}-${index}`, auto_price: false,
      original: unit.price,
    })),
    barcodes: (item.barcodes || []).map((row, index) => ({ ...row, _key: `barcode-${index}` })),
  }
  baseline.value = fingerprint(draft.value)
  externalChanges.value = false
}

function unitChoices(target) {
  return (options.value.uoms || []).filter((name) => name !== draft.value?.stock_uom &&
    (name === target.uom || !draft.value.units.some((unit) => unit !== target && unit.uom === name)))
}

function addSellingUnit() {
  const choices = unitChoices({ uom: '' })
  if (!choices.length) return session.notify(t('No unused UOMs are available.'), true)
  draft.value.units.push({
    uom: '', factor: 1, price: '', active_price: null, has_explicit_price: false,
    editable: Boolean(draft.value.can_edit_prices), original: null, is_new: true,
    _key: `new-${Date.now()}-${Math.random()}`,
  })
}

function unitSelected(unit) {
  unit.factor = 1
  const base = draft.value.units.find((row) => row.uom === draft.value.stock_uom)
  unit.price = Number(base?.price || 0) || ''
  unit.auto_price = true
  unit.original = null
}

function unitFactorChanged(unit) {
  if (!unit.auto_price) return
  const base = draft.value.units.find((row) => row.uom === draft.value.stock_uom)
  const basePrice = Number(base?.price) || 0
  unit.price = basePrice ? basePrice * (Number(unit.factor) || 0) : ''
}

function updateAutoUnitPrices() {
  draft.value.units.forEach((unit) => {
    if (unit.is_new && unit.auto_price) unitFactorChanged(unit)
  })
}

function removeSellingUnit(unit) {
  if (draft.value.barcodes.some((row) => row.uom === unit.uom && row.barcode)) {
    session.notify(t('Move or remove this unit\'s barcode before removing the unit.'), true)
    return
  }
  draft.value.units = draft.value.units.filter((row) => row !== unit)
}

function addBarcode() {
  draft.value.barcodes.push({ barcode: '', uom: draft.value.stock_uom, _key: `barcode-${Date.now()}-${Math.random()}` })
}

function clearImage() {
  if (preview.value) URL.revokeObjectURL(preview.value)
  preview.value = ''
  imageFile.value = null
  imageLink.value = ''
  previewLink.value = ''
  imageReset.value++
}

function selectImageSource(source) {
  if (source === imageSource.value) return
  clearImage()
  imageSource.value = source
}

async function refineImageSearch() {
  const itemCode = draft.value?.item_code
  const profile = session.posProfile
  if (!itemCode || refiningSearch.value) return
  refiningSearch.value = true
  try {
    const result = await call('esafepos.api.item_image_search.refine_search', {
      pos_profile: profile, item_code: itemCode,
    })
    if (session.posProfile === profile && draft.value?.item_code === itemCode) {
      refinedSearch.value = result.query
    }
  } catch (error) {
    if (session.posProfile === profile && draft.value?.item_code === itemCode) session.notify(error.message, true)
  } finally {
    refiningSearch.value = false
  }
}

function chooseImage(event) {
  const file = event.target.files?.[0]
  if (!file) return
  if (file.size > 5 * 1024 * 1024 || !['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    session.notify(t('Choose a JPEG, PNG or WebP image up to 5 MB.'), true)
    event.target.value = ''
    return
  }
  if (preview.value) URL.revokeObjectURL(preview.value)
  imageFile.value = file
  preview.value = URL.createObjectURL(file)
}

function readImage(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1])
    reader.onerror = () => reject(new Error(t('Could not read the selected image.')))
    reader.readAsDataURL(file)
  })
}

async function openItem(itemCode, priceList, keepIdentity = false) {
  creating.value = false
  const id = ++detailRequest
  const name = keepIdentity && draft.value.item_name !== draft.value.originalName ? draft.value.item_name : null
  const metadata = keepIdentity ? Object.fromEntries(['disabled', 'item_group', 'brand', 'description', 'is_sales_item', 'is_purchase_item'].map(key => [key, draft.value[key]])) : null
  opening.value = true
  try {
    const result = await call('esafepos.api.items.item_details', {
      pos_profile: session.posProfile, item_code: itemCode, price_list: priceList || null,
    })
    if (id !== detailRequest) return
    if (!keepIdentity) {
      clearImage()
      refinedSearch.value = ''
      imageSource.value = /^https:\/\//i.test(result.image || '') ? 'link' : 'device'
    }
    setDraft(result)
    if (name !== null && result.can_edit_item) draft.value.item_name = name
    if (metadata && result.can_edit_item) Object.assign(draft.value, metadata)
    selectedPriceList.value = result.price_list
  } catch (error) {
    if (id === detailRequest) session.notify(error.message, true)
  } finally {
    if (id === detailRequest) opening.value = false
  }
}

function startCreate() {
  detailRequest++
  creating.value = true
  draft.value = null
  clearImage()
}

async function refreshCatalog() {
  try {
    await catalog.fetch()
    catalog.cacheFullCatalog()
  } catch (error) {
    session.notify(error.message, true)
  }
}

function stockUpdated(stock) {
  request++
  if (!stock?.rows || !draft.value) return
  const row = items.value.find(item => item.name === draft.value.item_code)
  if (!row) return
  const rows = stock.rows.filter(entry => !activeFilters.warehouse || entry.warehouse === activeFilters.warehouse)
  for (const key of ['actual_qty', 'reserved_qty', 'available_qty']) row[key] = rows.reduce((total, entry) => total + Number(entry[key] || 0), 0)
}

async function refreshLiveItems() {
  if (!session.permissions.edit_items || session.offline || saving.value || opening.value || loading.value) return
  const profile = session.posProfile, id = ++request
  try {
    const count = Math.max(pageSize, items.value.length), requests = []
    for (let start = 0; start < count; start += pageSize) requests.push(call('esafepos.api.items.search_items', {
      pos_profile: profile, ...activeFilters, start, limit: pageSize,
    }))
    const pages = await Promise.all(requests)
    if (id !== request || session.posProfile !== profile || saving.value) return
    items.value = pages.flat(); hasMore.value = pages[pages.length - 1].length === pageSize; searchError.value = ''
    const code = draft.value?.item_code
    if (!code || creating.value) return
    const detailId = detailRequest, originalBaseline = baseline.value
    const updated = await call('esafepos.api.items.item_details', { pos_profile: profile, item_code: code, price_list: selectedPriceList.value || null })
    if (session.posProfile !== profile || detailId !== detailRequest || code !== draft.value?.item_code || saving.value || originalBaseline !== baseline.value) return
    if (!dirty.value) setDraft(updated)
    else externalChanges.value = fingerprint(updated) !== baseline.value
  } catch (error) { if (id === request) catalog.liveError = error.message }
}

function reloadCurrent() {
  if (dirty.value && !window.confirm(t('Discard unsaved item changes and reload ERPNext values?'))) return
  openItem(draft.value.item_code, selectedPriceList.value)
}

function exportItems() {
  const columns = ['name', 'item_name', 'item_group', 'brand', 'stock_uom', 'disabled', 'variant_of',
    ...(props.section === 'inventory' ? ['actual_qty', 'reserved_qty', 'available_qty'] : [])]
  const cell = value => '"' + String(value ?? '').replace(/^[=+@\-\t\r]/, "'$&").replaceAll('"', '""') + '"'
  const csv = [columns, ...items.value.map(item => columns.map(key => item[key]))].map(row => row.map(cell).join(',')).join('\r\n')
  const url = URL.createObjectURL(new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a'); link.href = url; link.download = 'items-stock.csv'; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

async function itemCreated(itemCode) {
  creating.value = false
  searchItems()
  await openItem(itemCode, selectedPriceList.value)
  await refreshCatalog()
}

function changePriceList(event) {
  const choice = event.target.value
  event.target.value = draft.value.price_list
  if (draft.value.units.some((unit) => unit.price !== unit.original) &&
      !window.confirm(t('Discard unsaved prices and switch price list?'))) return
  if (draft.value.units.some((unit) => unit.is_new) &&
      !window.confirm(t('Discard unsaved selling units and switch price list?'))) return
  openItem(draft.value.item_code, choice, true)
}

async function save() {
  if (saving.value || draft.value?.barcodes.some((row) => row.generating)) return
  request++; detailRequest++
  saving.value = true
  const item = draft.value
  const profile = session.posProfile
  try {
    const image = item.can_edit_item && imageFile.value ? await readImage(imageFile.value) : null
    const updated = await call('esafepos.api.items.save_item', {
      pos_profile: profile, item_code: item.item_code,
      include_catalog: 1,
      ...(item.can_edit_item && item.item_name !== item.originalName ? { item_name: item.item_name } : {}),
      ...(item.can_edit_item ? { disabled: item.disabled ? 1 : 0, item_group: item.item_group, brand: item.brand,
        description: item.description, is_sales_item: item.is_sales_item ? 1 : 0, is_purchase_item: item.is_purchase_item ? 1 : 0 } : {}),
      price_list: item.price_list,
      ...(item.can_edit_item && !item.has_serial_no && !item.has_variants ? { selling_units: JSON.stringify(item.units
        .filter((unit) => unit.uom && unit.uom !== item.stock_uom)
        .map(({ uom, factor }) => ({ uom, factor }))) } : {}),
      ...(item.can_edit_item && !item.has_variants ? { barcodes: JSON.stringify(item.barcodes
        .filter((row) => row.barcode?.trim())
        .map(({ barcode, uom }) => ({ barcode: barcode.trim(), uom }))) } : {}),
      ...(image ? { image_content: image } : {}),
      ...(item.can_edit_item && imageLink.value ? { image_url: imageLink.value } : {}),
      prices: item.units.filter((unit) => unit.editable && unit.price !== '' && unit.price != null &&
        Number(unit.price) > 0 && Number(unit.price) !== Number(unit.original))
        .map(({ uom, price }) => ({ uom, price })),
    })
    if (session.posProfile !== profile) return
    clearImage()
    setDraft(updated)
    const listed = items.value.find((row) => row.name === updated.item_code)
    if (listed) Object.assign(listed, { item_name: updated.item_name, image: updated.image, disabled: updated.disabled, item_group: updated.item_group, brand: updated.brand })
    for (const line of cart.lines) {
      if (line.item_code !== updated.item_code) continue
      line.item_name = updated.item_name
      line.image = updated.image
      const unit = updated.units.find((row) => row.uom === (line.selling_uom || line.uom || updated.stock_uom))
      if (updated.price_list === (options.value.default_price_list || session.priceList) &&
          unit?.active_price && line.price_override == null && !cart.customer && !cart.appType) {
        line.price = unit.active_price
        line.standard_price = unit.active_price
        line.catalog_price = unit.active_price
      }
    }
    if (updated.catalog) catalog.applyLiveUpdate(updated.catalog, { upsert: true })
    catalog.signalChange()
    cart.reprice().catch(() => {})
    session.notify(t('Item saved'))
  } catch (error) {
    session.notify(error.message, true)
  } finally {
    saving.value = false
  }
}

watch(() => [session.posProfile, session.offline, session.permissions.edit_items], async ([profile, offline, allowed]) => {
  detailRequest++
  request++
  draft.value = null
  creating.value = false
  refinedSearch.value = ''
  opening.value = false
  clearImage()
  items.value = []
  hasMore.value = false
  loading.value = false
  options.value = {}
  selectedPriceList.value = ''
  if (!profile || offline || !allowed) return
  searchItems()
  try {
    const result = await call('esafepos.api.items.editor_options', { pos_profile: profile })
    if (session.posProfile !== profile || session.offline) return
    options.value = result
    emit('options', result)
    if (!selectedPriceList.value) {
      selectedPriceList.value = priceLists.value.find((list) => list.name === result.default_price_list)?.name ||
        priceLists.value[0]?.name || ''
    }
    if (props.itemCode) openItem(props.itemCode, selectedPriceList.value)
  } catch (error) {
    session.notify(error.message, true)
  }
}, { immediate: true })
watch(() => props.itemCode, code => { if (code && !session.offline && session.permissions.edit_items) openItem(code, selectedPriceList.value) })
watch(() => props.section, () => { if (!session.offline && session.permissions.edit_items) searchItems() })
watch(() => catalog.liveRevision, refreshLiveItems)
onBeforeUnmount(() => {
  request++
  detailRequest++
  clearImage()
})
</script>

<style scoped>
.items-page { flex: 1; min-height: 0; height: 100%; width: 100%; padding: 12px; display: grid; grid-template-columns: minmax(0, .85fr) minmax(0, 1.15fr); grid-template-rows: minmax(0, 1fr); align-items: stretch; gap: 12px; overflow: hidden; }
.items-card { min-width: 0; padding: 16px; display: grid; gap: 12px; }
.browser-heading, .result-meta { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
.browser-heading h2 { margin: 0; font-size: 17px; }
.result-meta .btn { padding: 7px 9px; font-size: 12px; }
.item-filters label { display: grid; gap: 5px; font-size: 12px; color: var(--text-muted); }
.item-filters select { width: 100%; }
.item-result > span:nth-child(2) { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.item-badge { font-size: 11px; border: 1px solid var(--border); padding: 4px 7px; border-radius: 6px; color: var(--text-muted); }
.disabled-badge, .empty-stock { color: var(--red); }
.item-notice { padding: 12px; background: var(--surface-2); border-radius: 8px; line-height: 1.6; }
.metadata-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.description-field { grid-column: 1 / -1; }
.description-field textarea { width: 100%; resize: vertical; }
.item-settings { display: flex; flex-wrap: wrap; gap: 16px; }
.edit-item .item-settings label { display: flex; align-items: center; gap: 8px; }
.edit-item .item-settings input { width: 17px; height: 17px; accent-color: var(--brand); }
.inventory-item-heading p { margin: 0; }
.item-browser { display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.edit-item, .items-page :deep(.create-item) { min-height: 0; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; align-content: start; }
.items-page > .items-card:not(.item-browser):not(.edit-item) { align-self: start; }
.item-search { display: flex; gap: 8px; }
.item-search input { min-width: 0; flex: 1; }
.item-filters { display: flex; flex-wrap: wrap; gap: 8px; }
.item-filters > * { flex: 1 1 155px; min-width: 0; }
.item-filters :deep(.search-select-menu) { width: max(100%, 200px); }
.item-results { flex: 1; min-height: 0; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
.item-results, .edit-item, .item-browser, .items-page :deep(.create-item) { scrollbar-width: thin; scrollbar-color: var(--text-muted) var(--surface-2); }
.item-result { width: 100%; padding: 9px 8px; display: flex; align-items: center; gap: 10px; text-align: start; color: inherit; border: 0; border-bottom: 1px solid var(--border); background: transparent; }
.item-result:hover, .item-result.selected { color: var(--brand-dark); background: var(--surface-2); }
.item-result small { display: block; margin-top: 4px; }
.item-thumbnail, .image-preview { display: grid; place-items: center; flex: none; overflow: hidden; border-radius: 8px; color: var(--text-muted); background: var(--surface-2); }
.item-thumbnail { width: 40px; height: 40px; }
.item-thumbnail img, .image-preview img { width: 100%; height: 100%; object-fit: contain; }
.more-items { margin: 12px 0 0; width: 100%; }
.edit-item fieldset { display: grid; gap: 16px; min-width: 0; border: 0; padding: 0; margin: 0; }
.edit-item h2 { margin: 0 0 4px; }
.edit-item label { display: grid; gap: 5px; }
.edit-item input, .edit-item select { width: 100%; min-width: 0; }
.item-identity { display: grid; grid-template-columns: 112px minmax(0, 1fr); gap: 14px; }
.image-preview { width: 112px; height: 112px; }
.identity-fields { display: grid; gap: 10px; justify-items: start; }
.identity-fields label { width: 100%; }
.image-attachment { display: grid; gap: 8px; width: 100%; justify-items: start; min-width: 0; }
.image-sources { display: flex; flex-wrap: wrap; gap: 6px; }
.image-sources a { text-decoration: none; }
.source-active { border-color: var(--brand); background: var(--surface-2); color: var(--brand-dark); }
.unit-prices { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(150px, 100%), 1fr)); gap: 12px; }
.item-options-section { display: grid; gap: 10px; padding-top: 14px; border-top: 1px solid var(--border); min-width: 0; }
.item-options-section h3 { margin: 0; font-size: 1rem; }
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.unit-prices { grid-template-columns: minmax(0, 1fr); }
.unit-price-row, .barcode-row { display: grid; grid-template-columns: minmax(100px, .8fr) minmax(130px, .8fr) minmax(150px, 1fr) auto; align-items: end; gap: 8px; padding: 10px 0; border-bottom: 1px solid var(--border); }
.unit-price-row label, .barcode-row label { min-width: 0; }
.unit-price-row small, .barcode-row small { display: block; }
.price-readonly { padding: 9px 0; display: block; }
.barcode-row { grid-template-columns: minmax(0, 1fr) auto; }
.barcode-row > .identifier-field { grid-column: 1 / -1; }
.unit-remove { align-self: end; }
@media (max-width: 720px) {
  .items-page { grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(190px, 40%) minmax(0, 1fr); padding: 8px; gap: 8px; }
  .item-browser { display: block; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
  .item-browser > * + * { margin-top: 10px; }
  .item-results { max-height: none; overflow: visible; }
  .item-identity { grid-template-columns: 80px minmax(0, 1fr); }
  .image-preview { width: 80px; height: 80px; }
  .unit-price-row, .barcode-row { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
}
</style>
