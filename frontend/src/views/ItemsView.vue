<template>
  <section class="items-page">
    <div v-if="!session.permissions.edit_items" class="card items-card">{{ t('You cannot edit items and selling prices.') }}</div>
    <div v-else-if="session.offline" class="card items-card">{{ t('Editing items needs a connection.') }}</div>
    <template v-else>
      <div class="card items-card">
        <form class="item-search" @submit.prevent="searchItems">
          <input v-model="search" :aria-label="t('Find an item')" :placeholder="t('Item name, code or barcode')" />
          <button class="btn btn-primary" :disabled="loading">{{ t('Search') }}</button>
        </form>
        <div v-if="!loading && !items.length" class="muted">{{ t('No products found') }}</div>
        <button v-for="item in items" :key="item.name" class="item-result" :disabled="saving" @click="openItem(item.name)">
          <strong>{{ item.item_name }}</strong>
          <small class="muted">{{ item.name }} · {{ item.stock_uom }}</small>
        </button>
      </div>
      <form v-if="draft" class="card items-card edit-item" @submit.prevent="save">
        <div>
          <h2>{{ draft.item_code }}</h2>
          <div class="muted">{{ draft.price_list }} · {{ draft.currency }}</div>
        </div>
        <label>{{ t('Item name') }}<input v-model.trim="draft.item_name" required maxlength="140" /></label>
        <label v-for="unit in draft.units" :key="unit.uom">
          {{ unit.uom }} <span v-if="unit.uom !== draft.stock_uom" class="muted">· {{ unit.factor }} {{ draft.stock_uom }}</span>
          <input v-model.number="unit.price" type="number" min="0.000001" step="any" :placeholder="t('Selling price')" />
          <small v-if="unit.active_price != null && unit.active_price !== unit.original" class="muted">
            {{ t('Current price') }} {{ money(unit.active_price, draft.currency) }}
          </small>
        </label>
        <button class="btn btn-primary" :disabled="saving">{{ t('Save changes') }}</button>
      </form>
    </template>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'
import { call } from '../api'
import { money } from '../format'
import { t } from '../i18n'
import { useCatalogStore } from '../stores/catalog'
import { useCartStore } from '../stores/cart'
import { useSessionStore } from '../stores/session'

const session = useSessionStore()
const catalog = useCatalogStore()
const cart = useCartStore()
const search = ref('')
const items = ref([])
const draft = ref(null)
const loading = ref(false)
const saving = ref(false)
let request = 0

async function searchItems() {
  loading.value = true
  const id = ++request
  try {
    const results = await call('esafepos.api.items.search_items', { pos_profile: session.posProfile, search: search.value })
    if (id === request) items.value = results
  } catch (error) {
    if (id === request) session.notify(error.message, true)
  } finally {
    if (id === request) loading.value = false
  }
}

function setDraft(item) {
  draft.value = { ...item, units: item.units.map((unit) => ({ ...unit, original: unit.price })) }
}

async function openItem(itemCode) {
  const id = ++request
  loading.value = false
  try {
    const result = await call('esafepos.api.items.item_details', { pos_profile: session.posProfile, item_code: itemCode })
    if (id === request) setDraft(result)
  } catch (error) {
    if (id === request) session.notify(error.message, true)
  }
}

async function save() {
  if (saving.value) return
  saving.value = true
  const item = draft.value
  const profile = session.posProfile
  try {
    const updated = await call('esafepos.api.items.save_item', {
      pos_profile: profile, item_code: item.item_code, item_name: item.item_name,
      prices: item.units.filter((unit) => unit.price !== '' && unit.price != null && unit.price !== unit.original)
        .map(({ uom, price }) => ({ uom, price })),
    })
    if (session.posProfile !== profile) return
    setDraft(updated)
    const listed = items.value.find((row) => row.name === updated.item_code)
    if (listed) listed.item_name = updated.item_name
    for (const line of cart.lines) {
      if (line.item_code !== updated.item_code) continue
      line.item_name = updated.item_name
      const unit = updated.units.find((row) => row.uom === line.selling_uom)
      if (unit?.active_price && line.price_override == null) {
        line.price = unit.active_price
        line.standard_price = unit.active_price
        line.catalog_price = unit.active_price
      }
    }
    await catalog.cacheFullCatalog()
    await cart.reprice()
    session.notify(t('Item saved'))
  } catch (error) {
    session.notify(error.message, true)
  } finally {
    saving.value = false
  }
}

watch(() => [session.posProfile, session.offline, session.permissions.edit_items], ([profile, offline, allowed]) => {
  request++
  draft.value = null
  items.value = []
  loading.value = false
  if (profile && !offline && allowed) searchItems()
}, { immediate: true })
</script>

<style scoped>
.items-page { padding: 16px; display: grid; grid-template-columns: minmax(0, 1fr) minmax(280px, 1fr); align-content: start; align-items: start; gap: 16px; overflow: auto; }
.items-card { padding: 16px; display: grid; gap: 10px; }
.item-search { display: flex; gap: 8px; }
.item-search input { min-width: 0; flex: 1; }
.item-result { padding: 9px 4px; display: grid; gap: 4px; text-align: start; color: inherit; border: 0; border-bottom: 1px solid var(--border); background: transparent; }
.item-result:hover { color: var(--brand); }
.edit-item { gap: 16px; }
.edit-item h2 { margin: 0 0 4px; }
.edit-item label { display: grid; gap: 5px; }
.edit-item input { width: 100%; }
@media (max-width: 720px) {
  .items-page { grid-template-columns: minmax(0, 1fr); }
  .edit-item { grid-row: 1; }
}
</style>
