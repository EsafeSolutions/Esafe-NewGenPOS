<template>
  <section class="items-page">
    <div v-if="!session.permissions.edit_items" class="card items-card">{{ t('You do not have access to the Items editor.') }}</div>
    <div v-else-if="session.offline" class="card items-card">{{ t('Editing items needs a connection.') }}</div>
    <template v-else>
      <div class="card items-card item-browser">
        <button v-if="options.can_create_items" type="button" class="btn btn-primary" :disabled="saving || opening" @click="startCreate">{{ t('Add item') }}</button>
        <form class="item-search" @submit.prevent="searchItems()">
          <input v-model="search" :aria-label="t('Find an item')" :placeholder="t('Item name, code or barcode')" />
          <button class="btn btn-primary" :disabled="loading">{{ t('Search') }}</button>
        </form>
        <div class="item-filters">
          <SearchSelect v-model="group" :label="t('Category')" :options="groupOptions" @change="searchItems()" />
          <SearchSelect v-model="brand" :label="t('Brand')" :options="brandOptions" @change="searchItems()" />
        </div>
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
            </span>
          </button>
          <button v-if="hasMore" class="btn btn-outline more-items" :disabled="loading || saving" @click="searchItems(true)">
            {{ loading ? t('Loading…') : t('Load more items') }}
          </button>
        </div>
      </div>
      <ItemCreateForm v-if="creating" :options="options" @busy="saving = $event" @cancel="creating = false" @created="itemCreated" />
      <div v-else-if="draft" class="card items-card edit-item">
        <form @submit.prevent="save">
        <fieldset :disabled="saving || opening">
          <header>
            <h2>{{ draft.item_name }}</h2>
            <div class="muted">{{ [draft.item_code, draft.item_group, draft.brand].filter(Boolean).join(' · ') }}</div>
          </header>
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
          <label v-if="draft.price_list">{{ t('Selling price list') }}
            <select :value="draft.price_list" @change="changePriceList">
              <option v-for="list in priceLists" :key="list.name" :value="list.name">{{ list.name }} · {{ list.currency }}</option>
            </select>
          </label>
          <section class="item-options-section">
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
          <section v-if="draft.can_edit_item" class="item-options-section">
            <div class="section-heading"><h3>{{ t('Barcodes') }}</h3>
              <button type="button" class="btn btn-outline" @click="addBarcode">{{ t('Add barcode') }}</button>
            </div>
            <div v-for="(row, index) in draft.barcodes" :key="row._key" class="barcode-row">
              <label>{{ t('Barcode') }}<input v-model.trim="row.barcode" maxlength="140" /></label>
              <label>{{ t('Barcode unit') }}<select v-model="row.uom"><option :value="draft.stock_uom">{{ draft.stock_uom }}</option>
                <option v-for="unit in draft.units.filter((entry) => entry.uom && entry.uom !== draft.stock_uom)" :key="unit.uom" :value="unit.uom">{{ unit.uom }}</option>
              </select></label>
              <button type="button" class="btn btn-outline" @click="row.barcode = generateItemBarcode()">{{ t('Generate') }}</button>
              <button type="button" class="btn btn-outline" :aria-label="t('Remove barcode')" @click="draft.barcodes.splice(index, 1)">×</button>
            </div>
          </section>
          <small v-if="!draft.can_edit_prices" class="muted">{{ t('Your account cannot edit item selling prices.') }}</small>
          <small v-else-if="!draft.price_list" class="muted">{{ t('No selling price lists are available to your account.') }}</small>
          <button v-if="draft.can_edit_item || draft.units.some((unit) => unit.editable)" class="btn btn-primary">
            {{ saving ? t('Saving…') : t('Save changes') }}
          </button>
        </fieldset>
        </form>
        <ItemWarehouseStock v-if="options.can_view_stock && !opening" :key="draft.item_code" :item-code="draft.item_code" :disabled="saving" @busy="saving = $event" @updated="refreshCatalog" />
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
import ItemWarehouseStock from '../components/ItemWarehouseStock.vue'
import { money } from '../format'
import { generateItemBarcode } from '../itemUtilities'
import { t } from '../i18n'
import { useCatalogStore } from '../stores/catalog'
import { useCartStore } from '../stores/cart'
import { useSessionStore } from '../stores/session'

const session = useSessionStore()
const catalog = useCatalogStore()
const cart = useCartStore()
const search = ref('')
const group = ref('')
const brand = ref('')
const options = ref({})
const selectedPriceList = ref('')
const priceLists = computed(() => options.value.price_lists || [])
const groupOptions = computed(() => [{ value: '', label: t('All categories') },
  ...(options.value.item_groups || []).map((value) => ({ value, label: value }))])
const brandOptions = computed(() => [{ value: '', label: t('All brands') },
  ...(options.value.brands || []).map((value) => ({ value, label: value }))])
const items = ref([])
const draft = ref(null)
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
    activeFilters = { search: search.value, item_group: group.value, brand: brand.value }
    hasMore.value = false
    items.value = []
  }
  loading.value = true
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
    if (id === request) session.notify(error.message, true)
  } finally {
    if (id === request) loading.value = false
  }
}

function setDraft(item) {
  draft.value = {
    ...item,
    originalName: item.item_name,
    units: item.units.map((unit, index) => ({
      ...unit, _key: `${unit.uom || 'unit'}-${index}`, auto_price: false,
      original: unit.has_explicit_price ? unit.active_price : unit.price,
    })),
    barcodes: (item.barcodes || []).map((row, index) => ({ ...row, _key: `barcode-${index}` })),
  }
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
  if (saving.value) return
  saving.value = true
  const item = draft.value
  const profile = session.posProfile
  try {
    const image = item.can_edit_item && imageFile.value ? await readImage(imageFile.value) : null
    const updated = await call('esafepos.api.items.save_item', {
      pos_profile: profile, item_code: item.item_code,
      ...(item.can_edit_item && item.item_name !== item.originalName ? { item_name: item.item_name } : {}),
      price_list: item.price_list,
      ...(item.can_edit_item && !item.has_serial_no ? { selling_units: JSON.stringify(item.units
        .filter((unit) => unit.uom && unit.uom !== item.stock_uom)
        .map(({ uom, factor }) => ({ uom, factor }))) } : {}),
      ...(item.can_edit_item ? { barcodes: JSON.stringify(item.barcodes
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
    if (listed) Object.assign(listed, { item_name: updated.item_name, image: updated.image })
    for (const line of cart.lines) {
      if (line.item_code !== updated.item_code) continue
      line.item_name = updated.item_name
      line.image = updated.image
      const unit = updated.units.find((row) => row.uom === line.selling_uom)
      if (updated.price_list === (options.value.default_price_list || session.priceList) &&
          unit?.active_price && line.price_override == null) {
        line.price = unit.active_price
        line.standard_price = unit.active_price
        line.catalog_price = unit.active_price
      }
    }
    await catalog.fetch()
    catalog.cacheFullCatalog()
    await cart.reprice()
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
    if (!selectedPriceList.value) {
      selectedPriceList.value = priceLists.value.find((list) => list.name === result.default_price_list)?.name ||
        priceLists.value[0]?.name || ''
    }
  } catch (error) {
    session.notify(error.message, true)
  }
}, { immediate: true })
onBeforeUnmount(() => {
  request++
  detailRequest++
  clearImage()
})
</script>

<style scoped>
.items-page { flex: 1; min-height: 0; width: 100%; padding: 16px; display: grid; grid-template-columns: minmax(0, .85fr) minmax(0, 1.15fr); align-items: start; gap: 16px; overflow: auto; }
.items-card { min-width: 0; padding: 16px; display: grid; gap: 12px; }
.item-browser { max-height: 100%; }
.item-search { display: flex; gap: 8px; }
.item-search input { min-width: 0; flex: 1; }
.item-filters { display: flex; flex-wrap: wrap; gap: 8px; }
.item-filters > * { flex: 1 1 155px; min-width: 0; }
.item-filters :deep(.search-select-menu) { width: max(100%, 200px); }
.item-results { overflow: auto; }
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
.barcode-row { grid-template-columns: minmax(120px, 1fr) minmax(130px, .65fr) auto auto; }
.unit-remove { align-self: end; }
@media (max-width: 720px) {
  .items-page { grid-template-columns: minmax(0, 1fr); align-content: start; }
  .item-results { max-height: 32vh; }
  .item-identity { grid-template-columns: 80px minmax(0, 1fr); }
  .image-preview { width: 80px; height: 80px; }
  .unit-price-row, .barcode-row { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
}
</style>
