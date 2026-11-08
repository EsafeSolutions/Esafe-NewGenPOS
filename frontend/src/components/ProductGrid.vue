<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<template>
  <div class="grid-wrap">
    <div v-if="catalog.loading" class="grid-empty">{{ t('Loading…') }}</div>
    <div v-else-if="!visibleItems.length" class="grid-empty">
      <!-- Found, but every one is out of stock here and the outlet hides
           those: say so, or it reads as if nothing was found at all. -->
      <template v-if="catalog.items.length">
        <div>{{ t('Products were found, but none has stock at this outlet, so they are hidden.') }}</div>
        <div class="grid-hint">{{ t('To show them anyway: Settings, General, Register and shifts, Show out-of-stock items in the grid.') }}</div>
      </template>
      <template v-else>{{ t('No products found') }}</template>
    </div>
    <div v-else class="grid">
      <button
        v-for="item in visibleItems"
        :key="item.item_code"
        class="tile card"
        @click="$emit('select', item)"
      >
        <div class="tile-img">
          <img v-if="item.image" :src="item.image" :alt="item.item_name" loading="lazy" />
          <span v-else>{{ initials(item.item_name) }}</span>
        </div>
        <span class="tile-details" role="button" tabindex="0" :aria-label="t('View details for {item}', { item: item.item_name })" :title="t('View item images and description')" @click.stop="showDetails(item)" @keydown.enter.stop.prevent="showDetails(item)" @keydown.space.stop.prevent="showDetails(item)"><Icon name="image" /></span>
        <div class="tile-name">{{ item.item_name }}</div>
        <div class="tile-foot">
          <span class="tile-price">{{ money(item.price) }}</span>
          <span class="tile-tags">
            <span v-if="item.has_serial_no" class="tile-serial" :title="t('Serialized, serial number required')">{{ t('S/N') }}</span>
            <span
              v-if="item.is_stock_item"
              class="tile-stock"
              :class="{ low: item.actual_qty <= 0 }"
            >{{ item.actual_qty }}</span>
          </span>
        </div>
      </button>
    </div>
    <div v-if="selectedItem" class="modal-backdrop" @click.self="selectedItem = null">
      <section class="modal item-details-modal" role="dialog" aria-modal="true" :aria-label="selectedItem.item_name">
        <header class="modal-header"><span>{{ selectedItem.item_name }}</span><button class="btn-ghost" :aria-label="t('Close')" @click="selectedItem = null"><Icon name="close" /></button></header>
        <div class="item-gallery">
          <img v-if="selectedItem.image" :src="selectedItem.image" :alt="selectedItem.item_name" />
          <div v-else class="item-no-image"><Icon name="image" :size="36" />{{ t('No item image') }}</div>
        </div>
        <div class="item-detail-meta">
          <strong>{{ money(selectedItem.price) }}</strong>
          <span>{{ selectedItem.item_code }}</span>
          <span v-if="selectedItem.brand">{{ selectedItem.brand }}</span>
          <span>{{ selectedItem.item_group }}</span>
        </div>
        <p class="item-description">{{ selectedItem.description || t('No description available.') }}</p>
        <footer class="modal-footer"><button class="btn btn-outline" @click="selectedItem = null">{{ t('Close') }}</button></footer>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ref } from 'vue'
import Icon from './Icon.vue'
import { useCatalogStore } from '../stores/catalog'
import { useSessionStore } from '../stores/session'
import { money } from '../format'
import { t } from '../i18n'

defineEmits(['select'])
const catalog = useCatalogStore()
const session = useSessionStore()
const selectedItem = ref(null)
function showDetails(item) { selectedItem.value = item }

// Hide out-of-stock stock items unless the outlet opts in (Settings → General).
// Non-stock items (services, gift cards) always show.
const visibleItems = computed(() => {
  const filtered = catalog.items.filter((item) => !catalog.brand || item.brand === catalog.brand)
  if (session.settings?.show_out_of_stock) return filtered
  return filtered.filter((i) => !i.is_stock_item || (i.actual_qty || 0) > 0)
})

function initials(name) {
  return (name || '?')
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase()
}
</script>

<style scoped>
.grid-wrap {
  flex: 1;
  overflow-y: auto;
  margin-top: 10px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
  padding-bottom: 20px;
}
.tile {
  display: flex;
  flex-direction: column;
  text-align: left;
  padding: 0 0 10px;
  overflow: hidden;
  border: 1px solid transparent;
  transition: border-color 0.1s, transform 0.05s;
}
.tile:hover { border-color: var(--brand-soft); }
.tile-details { position:absolute; top:7px; right:7px; z-index:1; display:grid; place-items:center; width:30px; height:30px; border:1px solid var(--border); border-radius:9px; color:var(--text); background:var(--card-bg); box-shadow:var(--shadow); cursor:pointer; }
.tile-details:hover, .tile-details:focus-visible { color:var(--brand-dark); border-color:var(--brand); outline:none; }
.tile:active { transform: scale(0.98); }
.tile-img {
  height: 92px;
  background: linear-gradient(135deg, var(--surface-2), var(--border-subtle));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-weight: 800;
  font-size: 24px;
}
.tile-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.tile-name {
  padding: 8px 10px 2px;
  font-weight: 600;
  font-size: 13px;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 36px;
}
.tile-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 10px;
}
.tile-price {
  font-weight: 700;
  font-size: 13.5px;
}
.tile-stock {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  background: var(--surface-2);
  border-radius: 999px;
  padding: 1px 8px;
}
.tile-stock.low {
  color: var(--red);
  background: rgba(226, 48, 48, 0.1);
}
.tile-tags { display: flex; gap: 4px; align-items: center; }
.tile-serial {
  font-size: 10px;
  font-weight: 800;
  color: var(--brand-soft);
  background: rgba(0, 176, 185, 0.12);
  border-radius: 999px;
  padding: 1px 7px;
  letter-spacing: 0.04em;
}
.grid-empty {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
  justify-content: center;
  height: 200px;
  padding: 0 16px;
  text-align: center;
  color: var(--text-muted);
}
.grid-hint { font-size: 12.5px; }
.item-details-modal { width:min(640px, calc(100vw - 32px)); max-height:calc(100vh - 32px); overflow-y:auto; }
.item-gallery { display:flex; justify-content:center; height:min(42vh,360px); padding:20px; background:var(--surface-2); }
.item-gallery img { max-width:100%; max-height:100%; object-fit:contain; }
.item-no-image { display:flex; flex-direction:column; align-items:center; justify-content:center; gap:12px; color:var(--text-muted); }
.item-detail-meta { display:flex; flex-wrap:wrap; gap:12px; padding:16px 20px 0; color:var(--text-muted); }
.item-detail-meta strong { color:var(--brand-dark); }
.item-description { padding:0 20px; white-space:pre-wrap; line-height:1.55; }
</style>
