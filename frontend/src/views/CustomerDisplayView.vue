<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<template>
  <div class="cdisplay">
    <header class="cd-head">
      <img v-if="snap.logo" :src="snap.logo" class="cd-logo" alt="" />
      <div><h1>{{ snap.company || t('Welcome') }}</h1><p v-if="snap.customer">{{ snap.customer }}</p></div>
      <div v-if="snap.receipt" class="cd-receipt">
        <strong>{{ snap.pending ? t('Sale queued (offline)') : t('Sale completed') }}</strong>
        <div>{{ [snap.receipt, snap.date, snap.time].filter(Boolean).join(' · ') }}</div>
        <div>{{ [snap.terminal, snap.cashier].filter(Boolean).join(' · ') }}</div>
      </div>
    </header>
    <main v-if="snap.items.length" class="cd-content">
      <section class="cd-cart" :aria-label="t('Items')">
        <div class="cd-list-heading"><strong>{{ t('Items') }}</strong><span>{{ snap.count === 1 ? t('1 item') : t('{count} items', { count: snap.count }) }}</span></div>
        <div ref="itemList" class="cd-items">
          <article v-for="(item, index) in snap.items" :key="index" class="cd-item">
            <div v-if="item.image" class="cd-image"><img :src="item.image" alt="" loading="lazy" /></div>
            <div class="cd-item-main">
              <strong>{{ item.name }}</strong>
              <div class="muted">{{ item.qty }} {{ item.uom }} × {{ item.rate }}</div>
              <small v-if="item.code && item.code !== item.name" class="muted">{{ item.code }}</small>
            </div>
            <div class="cd-prices">
              <del v-if="item.gross" class="muted">{{ item.gross }}</del>
              <strong>{{ item.amount }}</strong>
              <span v-if="item.discount" class="cd-saving">−{{ item.discount }}</span>
            </div>
          </article>
        </div>
      </section>
      <section class="cd-totals" :aria-label="t('Sale summary')">
        <div v-if="snap.savings" class="cd-row cd-saving"><span>{{ t('You save') }}</span><strong>{{ snap.savings }}</strong></div>
        <div v-for="(row, index) in costs" :key="index" class="cd-row"><span>{{ row.label }}</span><span>{{ row.amount }}</span></div>
        <div class="cd-row cd-grand"><span>{{ t('Total') }}</span><strong>{{ snap.total }}</strong></div>
        <div v-if="snap.equivalent" class="cd-equivalent muted">{{ snap.equivalent }}</div>
        <div v-for="(row, index) in tenders" :key="index" class="cd-row"><span>{{ row.label }}</span><span>{{ row.amount }}</span></div>
        <div v-if="snap.due || snap.change" class="cd-row cd-balance">
          <span>{{ snap.change ? t('Change') : t('Balance due') }}</span><strong>{{ snap.change || snap.due }}</strong>
        </div>
        <div v-for="row in rewards" :key="row.label" class="cd-row cd-reward"><span>{{ row.label }}</span><strong>{{ row.amount }}</strong></div>
      </section>
    </main>
    <p v-else class="cd-empty">{{ t('Your items will appear here') }}</p>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { t } from '../i18n'
import { onCart } from '../customerDisplay'

const snap = ref({ items: [] })
const itemList = ref(null)
const terminalId = new URLSearchParams(location.hash.split('?')[1] || '').get('terminal')
let stop = null

const costs = computed(() => [
  { label: t('Subtotal'), amount: snap.value.subtotal },
  ...(snap.value.taxes?.length ? snap.value.taxes : [{ label: t('Tax'), amount: snap.value.tax }]),
  { label: t('Service charge'), amount: snap.value.service },
  { label: t('Rounding'), amount: snap.value.rounding },
].filter((row) => row.amount))
const tenders = computed(() => [
  ...(snap.value.payments || []),
  { label: t('Paid'), amount: snap.value.paid },
  { label: t('Loyalty redeemed'), amount: snap.value.redeemed },
  { label: t('Exchange credit'), amount: snap.value.exchangeCredit },
].filter((row) => row.amount))
const rewards = computed(() => [
  { label: t('Points earned'), amount: snap.value.earnedPoints || '' },
  { label: t('Points balance'), amount: snap.value.pointsBalance },
  { label: t('Cashback'), amount: snap.value.cashback },
].filter((row) => row.amount != null && row.amount !== ''))

watch(() => snap.value.items.length, async (count, previous) => {
  if (count <= previous || snap.value.receipt) return
  await nextTick()
  if (itemList.value) itemList.value.scrollTop = itemList.value.scrollHeight
})

onMounted(() => {
  document.documentElement.dataset.theme = 'light'
  stop = onCart((snapshot) => {
    if (terminalId && snapshot?.terminalId === terminalId) snap.value = snapshot
  })
})
onBeforeUnmount(() => stop?.())
</script>

<style scoped>
.cdisplay { min-height: 100dvh; padding: clamp(16px, 4vw, 48px); background: var(--surface-2); color: var(--text); }
.cd-head, .cd-content { max-width: 1240px; margin-inline: auto; }
.cd-head { min-height: 76px; display: flex; align-items: center; gap: 16px; margin-bottom: 24px; }
.cd-head h1, .cd-head p { margin: 0; }
.cd-head h1 { font-size: clamp(22px, 4vw, 36px); }
.cd-head p { color: var(--text-muted); }
.cd-logo { width: 60px; max-height: 60px; object-fit: contain; }
.cd-receipt { margin-inline-start: auto; text-align: end; color: var(--text-muted); font-size: 0.9em; }
.cd-receipt strong { color: var(--text); }
.cd-content { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(260px, 1fr); gap: 20px; align-items: start; }
.cd-cart, .cd-totals { background: var(--card-bg); border: 1px solid var(--border); border-radius: 14px; }
.cd-list-heading, .cd-item, .cd-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.cd-list-heading { padding: 14px 18px; border-bottom: 1px solid var(--border); }
.cd-items { max-height: max(260px, calc(100dvh - 215px)); overflow: auto; }
.cd-item { padding: 14px 18px; border-bottom: 1px solid var(--border); }
.cd-item:last-child { border-bottom: 0; }
.cd-item-main { flex: 1; overflow-wrap: anywhere; }
.cd-image img { display: block; width: 52px; height: 52px; border-radius: 8px; object-fit: contain; background: var(--surface-2); }
.cd-prices { display: grid; justify-items: end; white-space: nowrap; }
.cd-totals { padding: 14px; display: grid; gap: 9px; }
.cd-row { padding: 3px 4px; }
.cd-saving, .cd-reward { color: var(--promo); font-weight: 700; }
.cd-row.cd-saving { padding: 10px; background: var(--surface-2); border-radius: 8px; }
.cd-grand { padding-block: 12px; border-block: 1px solid var(--border); font-size: clamp(20px, 3vw, 30px); }
.cd-equivalent { text-align: end; }
.cd-balance { font-size: 1.2em; padding-top: 8px; border-top: 1px solid var(--border); }
.cd-empty { margin: 12vh auto; text-align: center; color: var(--text-muted); font-size: 1.25rem; }
@media (max-width: 670px) {
  .cd-head { flex-wrap: wrap; }
  .cd-content { grid-template-columns: minmax(0, 1fr); }
  .cd-items { max-height: 45dvh; }
}
</style>
