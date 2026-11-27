<template>
  <section class="stock-manager">
    <header class="manager-toolbar">
    <h1>{{ t('Items & stock') }}</h1>
    <div class="manager-tabs" role="tablist" :aria-label="t('Items and stock tools')" @keydown="navigateTabs">
      <button v-for="tab in tabs" :id="'manager-tab-' + tab.id" :key="tab.id" type="button" role="tab"
        :aria-selected="section === tab.id" :aria-controls="'manager-panel-' + tab.id" :tabindex="section === tab.id ? 0 : -1"
        :class="{ selected: section === tab.id }" @click="select(tab.id)"><Icon :name="tab.icon" />{{ t(tab.label) }}</button>
    </div>
    <div class="manager-sync" role="status"><span class="sync-state" :class="{ 'sync-error': session.offline || catalog.liveError }" :title="session.offline ? t('Offline: live sync paused') : catalog.liveError || t('Live price and stock sync enabled')">{{ session.offline ? t('Offline') : catalog.liveError ? t('Sync paused') : t('Live sync') }}</span><small v-if="catalog.liveLastSync && !session.offline">{{ new Date(catalog.liveLastSync).toLocaleTimeString() }}</small><button type="button" class="btn btn-outline" :aria-label="t('Sync now')" :title="t('Sync now')" :disabled="session.offline" @click="catalog.signalChange()"><Icon name="refresh" /><span>{{ t('Sync now') }}</span></button></div>
    </header>
    <p v-if="!tabs.length" class="card manager-empty">{{ t('You do not have access to item or stock tools.') }}</p>
    <template v-else>
      <div v-if="session.permissions.edit_items" v-show="section === 'details' || section === 'inventory'"
        :id="'manager-panel-' + (section === 'inventory' ? 'inventory' : 'details')" class="manager-panel" role="tabpanel"
        :aria-labelledby="'manager-tab-' + (section === 'inventory' ? 'inventory' : 'details')">
        <ItemsView :section="itemsSection" :item-code="String(route.query.item || '')" @options="editorOptions = $event" />
      </div>
      <div v-if="visited.has('variants') && session.permissions.edit_items" v-show="section === 'variants'"
        id="manager-panel-variants" class="manager-panel" role="tabpanel" aria-labelledby="manager-tab-variants">
        <ItemVariants :editor-options="editorOptions" @open="openItem" />
      </div>
      <div v-if="visited.has('count') && session.permissions.stock_count" v-show="section === 'count'"
        id="manager-panel-count" class="manager-panel" role="tabpanel" aria-labelledby="manager-tab-count">
        <StockCountView />
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Icon from '../components/Icon.vue'
import ItemVariants from '../components/ItemVariants.vue'
import ItemsView from './ItemsView.vue'
import StockCountView from './StockCountView.vue'
import { useSessionStore } from '../stores/session'
import { useCatalogStore } from '../stores/catalog'
import { t } from '../i18n'

const session = useSessionStore()
const catalog = useCatalogStore()
const route = useRoute()
const router = useRouter()
const editorOptions = ref({})
const visited = ref(new Set())
const itemsSection = ref('details')
const tabs = computed(() => [
  ...(session.permissions.edit_items ? [{ id: 'details', label: 'Item details', icon: 'detail' }] : []),
  ...(session.permissions.edit_items && editorOptions.value.can_view_stock ? [{ id: 'inventory', label: 'Inventory & transfers', icon: 'exchange' }] : []),
  ...(session.permissions.edit_items ? [{ id: 'variants', label: 'Variants', icon: 'grid' }] : []),
  ...(session.permissions.stock_count ? [{ id: 'count', label: 'Stock count', icon: 'barcode' }] : []),
])
const section = computed(() => tabs.value.some(tab => tab.id === route.query.section) ? route.query.section : tabs.value[0]?.id)
watch(section, value => { if (value) visited.value.add(value); if (['details', 'inventory'].includes(value)) itemsSection.value = value }, { immediate: true })
function select(value) { return router.replace({ path: '/items', query: { ...route.query, section: value } }) }
function openItem(item) { router.replace({ path: '/items', query: { section: 'details', item } }) }
async function navigateTabs(event) {
  if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return
  event.preventDefault()
  const index = tabs.value.findIndex(tab => tab.id === section.value)
  const direction = document.dir === 'rtl' ? -1 : 1
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.value.length - 1 :
    (index + (event.key === 'ArrowRight' ? direction : -direction) + tabs.value.length) % tabs.value.length
  await select(tabs.value[next].id)
  await nextTick()
  document.getElementById('manager-tab-' + tabs.value[next].id)?.focus()
}
</script>

<style scoped>
.stock-manager { display: flex; flex-direction: column; flex: 1; min-height: 0; min-width: 0; width: 100%; }
.manager-toolbar { display: flex; align-items: center; gap: 16px; height: 48px; min-height: 48px; padding: 0 16px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
h1 { font-size: 15px; letter-spacing: -.3px; margin: 0; white-space: nowrap; }
p { margin: 0; }
.manager-sync { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--brand-dark); flex-shrink: 0; white-space: nowrap; }
.manager-sync .btn { padding: 6px 10px; font-size: 12px; } .sync-error { color: var(--red); }
.manager-tabs { display: flex; gap: 4px; min-width: 0; flex: 1; height: 100%; overflow-x: auto; }
.manager-tabs button { display: flex; align-items: center; justify-content: center; gap: 7px; white-space: nowrap; padding: 0 11px; border-bottom: 2px solid transparent; color: var(--text-muted); font-weight: 600; font-size: 12px; flex-shrink: 0; }
.manager-tabs button.selected { border-bottom-color: var(--brand); color: var(--brand-dark); }
.manager-tabs button:focus-visible { outline: 2px solid var(--brand); outline-offset: -3px; }
.manager-panel { display: flex; flex: 1; min-height: 0; min-width: 0; }
.manager-empty { margin: 16px; padding: 24px; }
@media (max-width: 1100px) { .manager-toolbar { gap: 8px; } h1, .manager-sync small { display: none; } }
@media (max-width: 720px) { .manager-toolbar { height: 44px; min-height: 44px; padding: 0 8px; gap: 6px; } .manager-tabs { gap: 0; } .manager-tabs button { padding: 0 9px; } .manager-sync .sync-state, .manager-sync button > span:not(.icon) { display: none; } .manager-sync button { min-width: 34px; min-height: 34px; padding: 6px; } }
</style>
