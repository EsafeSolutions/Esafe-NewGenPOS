<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<template>
  <div class="cdisplay">
    <section v-if="snap.contact?.mode === 'welcome' && !snap.items.length" class="cd-welcome">
      <div class="cd-welcome-brand">
        <img :src="snap.logo || esafeMark" alt="" />
        <p>{{ t('Welcome to') }}</p>
        <h1>{{ snap.company || 'ESAFE POS' }}</h1>
      </div>
      <DisplayContactPad :key="snap.contact.id" :busy="busy" :error="error" @submit="submitContact" @skip="skipContact" @edit="error = ''" />
    </section>
    <template v-else>
    <header class="cd-head">
      <img v-if="snap.logo" :src="snap.logo" class="cd-logo" alt="" />
      <div><h1>{{ snap.company || t('Welcome') }}</h1></div>
      <div v-if="snap.receipt" class="cd-receipt">
        <strong>{{ snap.pending ? t('Sale queued (offline)') : t('Sale completed') }}</strong>
        <div>{{ [snap.receipt, snap.date, snap.time].filter(Boolean).join(' · ') }}</div>
        <div>{{ [snap.terminal, snap.cashier].filter(Boolean).join(' · ') }}</div>
      </div>
    </header>
    <main v-if="snap.items.length" class="cd-content">
      <aside class="cd-sidebar">
        <div class="cd-greeting">
          <Icon name="person" :size="25" />
          <div><span>{{ snap.customer ? t('Welcome back') : t('Welcome') }}</span><strong v-if="snap.customer">{{ snap.customer }}</strong></div>
        </div>
        <div v-for="row in rewards" :key="row.label" class="cd-row cd-reward"><span>{{ row.label }}</span><strong>{{ row.amount }}</strong></div>
        <div v-for="(row, index) in costs" :key="'c' + index" class="cd-row"><span>{{ row.label }}</span><span>{{ row.amount }}</span></div>
        <div v-for="(row, index) in tenders" :key="'p' + index" class="cd-row"><span>{{ row.label }}</span><span>{{ row.amount }}</span></div>
        <div v-if="snap.equivalent" class="cd-equivalent muted">{{ snap.equivalent }}</div>
        <button v-if="snap.canStart" class="btn btn-outline cd-next" @click="channel?.postMessage({ kind: 'next' })">{{ t('Start next sale') }}</button>
      </aside>
      <section class="cd-cart" :aria-label="t('Items')">
        <article v-if="latest && !snap.receipt" class="cd-latest" aria-live="polite">
          <DisplayProductIcon :item="latest" />
          <div class="cd-latest-copy">
            <small>{{ t('Latest item') }}</small>
            <strong>{{ latest.name }}</strong>
            <span>{{ latest.qty }} {{ latest.uom }} × {{ latest.rate }}</span>
          </div>
          <div class="cd-latest-price">
            <del v-if="latest.gross">{{ latest.gross }}</del>
            <span v-if="latest.discount">−{{ latest.discount }}</span>
            <strong>{{ latest.amount }}</strong>
          </div>
        </article>
        <div class="cd-list-heading"><strong>{{ t('Items') }}</strong><span>{{ snap.count === 1 ? t('1 item') : t('{count} items', { count: snap.count }) }}</span></div>
        <div ref="itemList" class="cd-items">
          <article v-for="(item, index) in snap.items" :key="index" class="cd-item">
            <DisplayProductIcon :item="item" />
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
    </main>
    <p v-else class="cd-empty">{{ t('Your items will appear here') }}</p>
    <footer v-if="snap.items.length" class="cd-totals" :aria-label="t('Sale summary')">
      <div v-if="snap.subtotal"><span>{{ t('Subtotal') }}</span><strong>{{ snap.subtotal }}</strong></div>
      <div class="cd-saving"><span>{{ t('You save') }}</span><strong>{{ snap.savings || '—' }}</strong></div>
      <div class="cd-grand"><span>{{ t('Total') }}</span><strong>{{ snap.total }}</strong></div>
      <div v-if="snap.change || snap.due" class="cd-balance"><span>{{ snap.change ? t('Change') : t('Balance due') }}</span><strong>{{ snap.change || snap.due }}</strong></div>
    </footer>
    <small v-if="snap.receipt" class="cd-receipt-brand muted">{{ RECEIPT_BRAND }}</small>
    <div v-if="snap.contact" class="cd-overlay" @keydown.esc="skipContact">
      <div class="cd-dialog" role="dialog" aria-modal="true" aria-labelledby="display-contact-title">
        <DisplayContactPad :key="snap.contact.id" :busy="busy" :error="error" @submit="submitContact" @skip="skipContact" @edit="error = ''" />
      </div>
    </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { t } from '../i18n'
import { connectContactChannel, onCart } from '../customerDisplay'
import { RECEIPT_BRAND } from '../receiptOptions'
import DisplayContactPad from '../components/DisplayContactPad.vue'
import DisplayProductIcon from '../components/DisplayProductIcon.vue'
import Icon from '../components/Icon.vue'
import esafeMark from '../assets/esafe-solutions-favicon.png'

const snap = ref({ items: [] })
const itemList = ref(null)
const terminalId = new URLSearchParams(location.hash.split('?')[1] || '').get('terminal')
let stop = null
let channel = null
const busy = ref(false)
const error = ref('')
const latestIndex = ref(0)
const latest = computed(() => snap.value.items[latestIndex.value])
let timeout

function clearContactResult() {
  clearTimeout(timeout)
  busy.value = false
  error.value = ''
}
function submitContact(mobile) {
  if (!snap.value.contact || !channel) return
  busy.value = true
  error.value = ''
  channel.postMessage({ kind: 'submit', id: snap.value.contact.id, mobile })
  timeout = setTimeout(() => {
    busy.value = false
    error.value = t('The till did not answer. Try again or ask the cashier.')
  }, 15000)
}
function skipContact() {
  if (!snap.value.contact) return
  channel?.postMessage({ kind: 'skip', id: snap.value.contact.id })
  snap.value = { ...snap.value, contact: null }
}

const costs = computed(() => [
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

watch(() => snap.value.contact?.id, clearContactResult)
watch(latestIndex, async () => {
  if (snap.value.receipt) return
  await nextTick()
  const list = itemList.value
  const item = list?.children[latestIndex.value]
  if (item && list.scrollHeight > list.clientHeight) list.scrollTop = item.offsetTop
})

onMounted(() => {
  document.documentElement.dataset.theme = 'light'
  channel = connectContactChannel(terminalId, (message) => {
    if (message?.kind !== 'result' || message.id !== snap.value.contact?.id) return
    clearContactResult()
    error.value = message.error
  })
  stop = onCart((snapshot) => {
    if (!terminalId || snapshot?.terminalId !== terminalId) return
    let changed = -1
    snapshot.items.forEach((item, index) => {
      const previous = snap.value.items[index]
      if (item.code !== previous?.code || item.uom !== previous?.uom || item.qty > previous?.qty) changed = index
    })
    if (changed >= 0) latestIndex.value = changed
    else if (latestIndex.value >= snapshot.items.length) latestIndex.value = Math.max(0, snapshot.items.length - 1)
    snap.value = snapshot
  })
})
onBeforeUnmount(() => {
  stop?.()
  channel?.close()
  clearTimeout(timeout)
})
</script>

<style scoped>
.cdisplay { height: 100dvh; display: flex; flex-direction: column; padding: clamp(12px, 2vw, 28px); background: #f2f6fc; color: #142e53; }
.cd-head, .cd-content, .cd-totals { width: 100%; max-width: 1440px; margin-inline: auto; }
.cd-head { min-height: 52px; display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.cd-head h1 { margin: 0; font-size: clamp(18px, 2.4vw, 28px); }
.cd-logo { width: 45px; height: 45px; object-fit: contain; }
.cd-receipt { margin-inline-start: auto; text-align: end; color: var(--text-muted); font-size: .88rem; }
.cd-receipt strong { color: var(--text); }
.cd-content { display: grid; flex: 1; min-height: 0; grid-template-columns: minmax(160px, .68fr) minmax(0, 2fr); gap: 14px; }
.cd-sidebar { overflow: auto; min-height: 0; }
.cd-greeting, .cd-row, .cd-list-heading { display: flex; align-items: center; gap: 10px; }
.cd-greeting { background: white; border-radius: 12px; padding: 14px; margin-bottom: 8px; }
.cd-greeting strong { display: block; font-size: 20px; }
.cd-row, .cd-list-heading { justify-content: space-between; padding: 7px 8px; }
.cd-row span { overflow-wrap: anywhere; }
.cd-cart { display: flex; flex-direction: column; min-height: 0; min-width: 0; }
.cd-latest { --product-art-size: clamp(56px, 9vw, 110px); display: flex; align-items: center; gap: clamp(9px, 2vw, 20px); padding: clamp(12px, 2vw, 24px); border-radius: 16px; background: #1658ba; color: white; }
.cd-latest-copy, .cd-latest-price { display: grid; gap: 4px; }
.cd-latest-copy { flex: 1; min-width: 0; }
.cd-latest-copy strong { font-size: clamp(18px, 3vw, 34px); line-height: 1.15; overflow-wrap: anywhere; }
.cd-latest-price { text-align: end; }
.cd-latest-price strong { border-radius: 8px; color: #123c7a; background: white; padding: 5px 9px; font-size: clamp(17px, 3vw, 31px); }
.cd-items { display: grid; position: relative; grid-template-columns: repeat(2, minmax(0, 1fr)); align-content: start; overflow: auto; gap: 7px; }
.cd-item { display: flex; align-items: center; gap: 8px; min-width: 0; border-radius: 10px; padding: 10px; background: white; }
.cd-item-main { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.cd-prices { display: grid; justify-items: end; text-align: end; font-size: .94em; }
.cd-totals { display: grid; grid-auto-columns: minmax(0, 1fr); grid-auto-flow: column; gap: 7px; margin-top: 12px; }
.cd-totals > div { display: grid; gap: 3px; padding: 10px 12px; background: white; border-radius: 10px; }
.cd-totals strong { font-size: clamp(18px, 3vw, 32px); overflow-wrap: anywhere; }
.cd-saving, .cd-reward { color: #21624d; font-weight: 700; }
.cd-totals .cd-saving { background: #e3f4ed; }
.cd-totals .cd-grand { background: #174f9b; color: white; }
.cd-totals .cd-balance { background: #d9eafe; }
.cd-receipt-brand { display: block; text-align: center; margin-top: 6px; }
.cd-equivalent { text-align: end; }
.cd-next { margin-top: 12px; }
.cd-empty { margin: 12vh auto; text-align: center; color: var(--text-muted); font-size: 1.25rem; }
.cd-welcome { width: min(1160px, 100%); flex: 1; min-height: 0; overflow: auto; align-self: center; display: grid; grid-template-columns: 1fr 1fr; align-content: center; }
.cd-welcome-brand { background: linear-gradient(150deg, #123e83, #176ed4); color: #fff; display: flex; flex-direction: column; justify-content: center; align-items: flex-start; padding: clamp(18px, 5vw, 62px); border-radius: 16px 0 0 16px; }
.cd-welcome-brand img { width: 65px; height: 65px; object-fit: contain; background: white; padding: 7px; border-radius: 12px; }
.cd-welcome-brand p { margin: 26px 0 0; font-size: clamp(18px, 3vw, 34px); }
.cd-welcome-brand h1 { margin: 0; font-size: clamp(27px, 5vw, 68px); line-height: 1.02; overflow-wrap: anywhere; }
.cd-welcome :deep(.contact-pad) { border-radius: 0 16px 16px 0; }
.cd-overlay { position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; padding: 10px; background: #0a234a99; }
.cd-dialog { width: min(440px, 100%); max-height: 100%; overflow: auto; border-radius: 16px; }
@media (max-width: 900px) {
  .cd-items { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 600px) {
  .cd-content { grid-template-columns: minmax(0, 1fr); grid-template-rows: auto minmax(0, 1fr); }
  .cd-sidebar { max-height: 22dvh; }
  .cd-totals { grid-auto-flow: row; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .cd-welcome { grid-template-columns: minmax(0, 1fr); align-content: start; }
  .cd-welcome-brand { border-radius: 14px 14px 0 0; }
  .cd-welcome-brand img { width: 40px; height: 40px; }
  .cd-welcome-brand p { margin-top: 10px; }
  .cd-welcome :deep(.contact-pad) { border-radius: 0 0 14px 14px; }
}
</style>
