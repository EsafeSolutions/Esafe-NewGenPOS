<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<template>
  <div ref="gridWrap" class="grid-wrap" @scroll.passive="loadNearEnd">
    <div v-if="!visibleItems.length && !catalog.hasMore" class="grid-empty">
      {{ catalog.loading ? t('Loading…') : catalog.items.length ? t('No products in stock') : t('No products found') }}
    </div>
    <div v-else-if="!visibleItems.length" class="grid-empty">
      {{ catalog.loading ? t('Loading…') : t('No items to show on this page. Load more items to continue.') }}
    </div>
    <div v-else class="grid" :class="mode">
      <article v-for="item in visibleItems.slice(0, rendered)" :key="item.item_code" class="tile card">
        <button type="button" class="tile-main" :class="{ 'tile-main--photo': mode === 'image' && item.image }"
          @click="$emit('inspect', item)">
          <div v-if="mode !== 'list'" class="tile-img">
            <img v-if="item.image" :src="item.image" :alt="item.item_name" loading="lazy" />
            <Icon v-else name="image" />
          </div>
          <div class="tile-copy">
            <strong>{{ item.item_name }}</strong>
            <small>{{ item.item_code }}<template v-if="item.stock_uom"> · {{ item.stock_uom }}</template></small>
            <p v-if="mode === 'detail' && item.description">{{ plainText(item.description) }}</p>
          </div>
        </button>
        <div class="tile-foot">
          <div><strong class="tile-price">{{ money(item.price) }}</strong>
            <small v-if="item.is_stock_item" class="tile-stock" :class="{ 'tile-stock--empty': item.actual_qty <= 0 }">
              {{ t('{qty} in stock', { qty: item.actual_qty }) }}
            </small>
          </div>
          <button type="button" class="btn btn-icon tile-add" :title="t('Add {item} to cart', { item: item.item_name })"
            :aria-label="t('Add {item} to cart', { item: item.item_name })" @click="$emit('select', item)">
            <Icon name="plus" />
          </button>
        </div>
      </article>
    </div>
    <button v-if="rendered < visibleItems.length || catalog.hasMore" class="btn btn-outline load-more" :disabled="catalog.loading" @click="loadMore">
      {{ catalog.loading ? t('Loading…') : t('Load more items') }}
    </button>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import Icon from './Icon.vue'
import { useCatalogStore } from '../stores/catalog'
import { useSessionStore } from '../stores/session'
import { money, plainText } from '../format'
import { t } from '../i18n'

const props = defineProps({ mode: { type: String, default: 'image' } })
defineEmits(['select', 'inspect'])
const catalog = useCatalogStore()
const session = useSessionStore()
const batch = computed(() => props.mode === 'detail' ? 12 : 60)
const rendered = ref(batch.value)
const gridWrap = ref(null)
watch(() => [props.mode, catalog.search, catalog.brand, catalog.itemGroup, session.posProfile], () => {
  rendered.value = batch.value
  if (gridWrap.value) gridWrap.value.scrollTop = 0
})

const visibleItems = computed(() => session.settings?.show_out_of_stock
  ? catalog.items
  : catalog.items.filter((item) => !item.is_stock_item || item.actual_qty > 0))

function loadMore() {
  if (rendered.value < visibleItems.value.length) rendered.value += batch.value
  else if (catalog.hasMore && !catalog.loading) {
    catalog.fetch(true).catch((error) => session.notify(error.message, true))
  }
}
function loadNearEnd(event) {
  const { scrollHeight, clientHeight, scrollTop } = event.currentTarget
  if (scrollHeight - clientHeight - scrollTop < 180) loadMore()
}
</script>

<style scoped>
.grid-wrap { flex: 1; overflow-y: auto; margin-top: 6px; }
.grid { display: grid; gap: 8px; grid-template-columns: repeat(auto-fill, minmax(min(150px, 100%), 1fr)); }
.grid.list, .grid.detail { grid-template-columns: minmax(0, 1fr); }
.tile { display: flex; flex-direction: column; min-width: 0; overflow: hidden; }
.tile-main { display: flex; flex-direction: column; flex: 1; width: 100%; min-width: 0; padding: 0; text-align: start; background: transparent; color: inherit; border: 0; }
.tile-main:hover strong { color: var(--brand-dark); }
.tile-main:focus-visible { outline: 2px solid var(--brand); outline-offset: -2px; }
.tile-img { display: grid; place-items: center; height: 84px; width: 100%; background: var(--surface-2); color: var(--text-muted); }
.tile-img img { width: 100%; height: 100%; object-fit: cover; }
.tile-copy { display: grid; gap: 3px; padding: 9px 10px; overflow-wrap: anywhere; }
.tile-copy small { display: block; color: var(--text-muted); }
.tile-main--photo { position: relative; min-height: 140px; }
.tile-main--photo .tile-img { position: absolute; inset: 0; height: auto; }
.tile-main--photo .tile-img img { position: absolute; inset: 0; }
.tile-main--photo .tile-copy {
  position: relative;
  align-self: stretch;
  margin-top: auto;
  background: var(--card-bg);
  background: color-mix(in srgb, var(--card-bg) 84%, transparent);
}
.tile-main--photo .tile-copy small { color: var(--text); }
.tile-copy p { margin: 4px 0 0; white-space: pre-wrap; line-height: 1.5; }
.tile-foot { display: flex; align-items: center; justify-content: space-between; gap: 6px; padding: 6px 8px; }
.tile-price { color: var(--catalog-price); }
.tile-stock { display: block; color: var(--catalog-stock); }
.tile-stock--empty { color: var(--catalog-stock-empty); }
.tile-add {
  color: #fff;
  background: #b5242a;
  background: color-mix(in srgb, var(--red) 73%, black);
}
.tile-add:hover { background: color-mix(in srgb, var(--red) 65%, black); }
.tile-add:focus-visible { outline: 2px solid var(--red); outline-offset: 2px; }
.list .tile, .detail .tile { flex-direction: row; }
.list .tile-foot, .detail .tile-foot { gap: 12px; }
.detail .tile-main { display: grid; grid-template-columns: minmax(60px, 23%) minmax(0, 1fr); align-items: start; }
.detail .tile-img { height: 100%; min-height: 90px; }
.detail .tile-img img { height: 90px; object-fit: contain; }
.grid-empty { padding: 60px 12px; text-align: center; color: var(--text-muted); }
.load-more { display: block; margin: 12px auto 20px; }
@media (max-width: 560px) {
  .grid.image { grid-template-columns: repeat(auto-fill, minmax(min(144px, 100%), 1fr)); }
  .detail .tile { flex-direction: column; }
  .detail .tile-foot { border-top: 1px solid var(--border); }
}
</style>
