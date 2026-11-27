<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<template>
  <div ref="screenRoot" class="cdisplay" :inert="isPreview || undefined">
    <CustomerDisplayContent mode="adverts" background :config="presentation" :mirror="isPreview" :visual-state="mirrorState?.playback" @visual="playback = $event" />
    <div class="cd-screen-tools"><strong>{{ snap.company || t('Welcome') }}</strong><span v-if="fullscreenError" role="status">{{ fullscreenError }}</span><button v-if="fullscreenAvailable && !isPreview" class="btn btn-outline btn-sm" @click="toggleFullscreen"><Icon name="monitor" /> {{ fullscreen ? t('Exit full screen') : t('Full screen') }}</button></div>
    <section v-if="showLive" class="cd-live-popup" role="dialog" aria-modal="false" :aria-label="t('Live sale')" @keydown.esc="dismissLive">
    <button class="btn-icon cd-live-close" :aria-label="t('Hide live sale popup')" @click="dismissLive"><Icon name="close" /></button>
    <section v-if="snap.receipt && snap.greeting" class="cd-farewell" role="status">
      <Icon name="check" :size="64" />
      <h1>{{ t('Thank you very much for your purchase!') }}</h1>
      <p>{{ t('Come again. We wish you all the best!') }}</p>
      <div v-if="snap.change" class="cd-farewell-detail">{{ t('Change handed over') }} <strong>{{ snap.change }}</strong></div>
      <div v-if="snap.savedChangePoints" class="cd-farewell-detail">{{ t('{points} points saved from your change', { points: snap.savedChangePoints }) }}</div>
      <small class="muted">{{ snap.receipt }}</small>
      <button v-if="snap.canStart" type="button" class="btn btn-outline" @click="channel?.postMessage({ kind: 'next' })">{{ t('Start next sale') }}</button>
    </section>
    <section v-else-if="snap.contact?.mode === 'welcome' && !snap.items.length" class="cd-welcome">
      <div class="cd-welcome-brand">
        <img :src="snap.logo || esafeMark" alt="" />
        <p>{{ t('Welcome to') }}</p>
        <h1>{{ snap.company || 'ESAFE POS' }}</h1>
      </div>
      <DisplayContactPad :key="snap.contact.id" :busy="busy" :error="error" @submit="submitContact" @skip="skipContact" @edit="error = ''" />
    </section>
    <template v-else>
    <header class="cd-head">
      <div><h1>{{ snap.company || t('Welcome') }}</h1></div>
      <button v-if="hasBankDetails && bankDismissed" class="btn btn-outline cd-bank-reopen" @click="bankDismissed = false"><Icon name="bank" /> {{ t('Bank transfer details') }}</button>
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
          <div>
            <span>{{ snap.customer ? t('Welcome back') : t('Welcome') }}</span>
            <strong v-if="snap.customer">{{ snap.customer }}</strong>
          </div>
        </div>
        <div v-if="rewards.length || costs.length || tenders.length || snap.paid || snap.equivalent || snap.canStart"
          class="cd-details">
          <div v-for="row in rewards" :key="row.label" class="cd-row cd-reward"><span>{{ row.label }}</span><strong>{{ row.amount }}</strong></div>
          <div v-for="(row, index) in costs" :key="'c' + index" class="cd-row"><span>{{ row.label }}</span><span>{{ row.amount }}</span></div>
          <div v-for="(row, index) in tenders" :key="'p' + index" class="cd-row"><span>{{ row.label }}</span><span>{{ row.amount }}</span></div>
          <div v-if="snap.paid" class="cd-row cd-paid"><span>{{ t('Total paid') }}</span><strong>{{ snap.paid }}</strong></div>
          <div v-if="snap.equivalent" class="cd-equivalent muted">{{ snap.equivalent }}</div>
          <button v-if="snap.canStart" class="btn btn-outline cd-next" @click="channel?.postMessage({ kind: 'next' })">{{ t('Start next sale') }}</button>
        </div>
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
    <Teleport :to="screenRoot || 'body'" :disabled="!isPreview || !screenRoot">
    <component :is="isPreview ? 'section' : 'dialog'" ref="bankDialog" class="cd-bank-dialog" :class="{ 'cd-mirror-bank': isPreview }" :hidden="isPreview && (!hasBankDetails || bankDismissed)" aria-labelledby="bank-display-title" @cancel.prevent="bankDismissed = true">
      <template v-if="hasBankDetails">
        <header class="cd-bank-title"><Icon name="bank" :size="26" /><div><h2 id="bank-display-title">{{ t('Bank transfer details') }}</h2><span>{{ t('Choose the receiving account, then confirm the recipient in your banking app.') }}</span></div><button autofocus class="btn-icon" :aria-label="t('Close bank details')" @click="bankDismissed = true"><Icon name="close" /></button></header>
        <div v-if="snap.bankAccounts.length > 1" class="cd-bank-tabs"><button v-for="(account, index) in snap.bankAccounts" :key="index" class="btn btn-outline" :aria-pressed="bankIndex === index" @click="bankIndex = index">{{ account.bank_name }} · {{ account.account_number.slice(-4) }}</button></div>
        <Transition name="bank-panel" mode="out-in"><BankTransferCard :key="bankIndex" :account="snap.bankAccounts[bankIndex] || snap.bankAccounts[0]" :amount="snap.bankAmount || snap.due" /></Transition>
      </template>
    </component>
    </Teleport>
    <div v-if="snap.contact" class="cd-overlay" @keydown.esc="skipContact">
      <div class="cd-dialog" role="dialog" aria-modal="true" aria-labelledby="display-contact-title">
        <DisplayContactPad :key="snap.contact.id" :busy="busy" :error="error" @submit="submitContact" @skip="skipContact" @edit="error = ''" />
      </div>
    </div>
    </template>
    </section>
    <section v-if="popupMode" class="cd-popup-sheet" role="dialog" aria-modal="false" :aria-label="t(popupLabel)" @keydown.esc="manualDismissed = true">
      <header class="cd-popup-heading"><span>{{ snap.company || t('Welcome') }}</span><button class="btn-icon" :aria-label="t('Close display popup')" @click="manualDismissed = true"><Icon name="close" /></button></header>
      <CustomerDisplayContent :key="popupMode" :mode="popupMode" :config="presentation" :accounts="snap.standbyBankAccounts || []" :mirror="isPreview" :visual-state="{ bankIndex: mirrorState?.popupBankIndex || 0 }" @visual="popupBankIndex = $event.bankIndex" />
    </section>
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
import BankTransferCard from '../components/BankTransferCard.vue'
import CustomerDisplayContent from '../components/CustomerDisplayContent.vue'
import { normalizePresentation, displayLayers, DISPLAY_MODES } from '../displayContent'
import esafeMark from '../assets/esafe-solutions-favicon.png'

const snap = ref({ items: [] })
const screenRoot = ref(null)
const parameters = new URLSearchParams(location.hash.split('?')[1] || '')
const isPreview = parameters.get('preview') === '1'
const manualDismissed = ref(false), liveDismissed = ref(false), mirrorState = ref(null), playback = ref({ index: 0, paused: false }), popupBankIndex = ref(0)
const presentation = computed(() => normalizePresentation(snap.value.presentation))
const layers = computed(() => displayLayers(snap.value, liveDismissed.value))
const showLive = computed(() => layers.value.live || (hasBankDetails.value && !bankDismissed.value))
const popupMode = computed(() => manualDismissed.value || (hasBankDetails.value && !bankDismissed.value) ? '' : layers.value.popup)
const popupLabel = computed(() => DISPLAY_MODES.find(row => row.value === popupMode.value)?.label || '')
watch([() => presentation.value.requestId, () => presentation.value.mode], () => {
  manualDismissed.value = false
  liveDismissed.value = presentation.value.hideLive
  bankDismissed.value = presentation.value.mode !== 'bank'
})
function dismissLive() { liveDismissed.value = true; bankDismissed.value = true }
const fullscreenAvailable = Boolean(document.fullscreenEnabled)
const fullscreen = ref(Boolean(document.fullscreenElement)), fullscreenError = ref('')
const updateFullscreen = () => { fullscreen.value = Boolean(document.fullscreenElement) }
async function toggleFullscreen() {
  fullscreenError.value = ''
  try { if (document.fullscreenElement) await document.exitFullscreen(); else await document.documentElement.requestFullscreen() }
  catch { fullscreenError.value = t('Full screen is unavailable. Maximize the display window instead.') }
}
const itemList = ref(null)
const bankIndex = ref(0)
const bankDialog = ref(null)
const bankDismissed = ref(false)
const hasBankDetails = computed(() => Boolean(snap.value.bankAccounts?.length && !snap.value.receipt))
const bankAccountKey = computed(() => JSON.stringify((snap.value.bankAccounts || []).map(account => [account.bank_name, account.account_number, account.currency, account.pos_profile, account.payment_mode])))
watch(bankAccountKey, () => { bankIndex.value = 0 })
watch([bankAccountKey, () => snap.value.bankAmount], () => { bankDismissed.value = false })
watch([hasBankDetails, bankDismissed, bankDialog], ([hasDetails, dismissed, dialog]) => {
  if (!dialog || isPreview || dialog.tagName !== 'DIALOG') return
  if (hasDetails && !dismissed) { if (!dialog.open) dialog.showModal() }
  else if (dialog.open) dialog.close()
}, { flush: 'post' })
const terminalId = parameters.get('terminal')
let stop = null
let channel = null
const busy = ref(false)
const error = ref('')
const latestIndex = ref(0)
const latest = computed(() => snap.value.items[latestIndex.value])
let timeout
let heartbeat

function publishVisual() {
  if (isPreview || !snap.value.terminalId) return
  channel?.postMessage({ kind: 'display-state', state: {
    manualDismissed: manualDismissed.value, liveDismissed: liveDismissed.value,
    bankDismissed: bankDismissed.value, bankIndex: bankIndex.value, popupBankIndex: popupBankIndex.value,
    bankOpen: hasBankDetails.value && !bankDismissed.value,
    popup: popupMode.value, live: showLive.value, playback: { ...playback.value },
    width: innerWidth, height: innerHeight,
  } })
}
watch([manualDismissed, liveDismissed, bankDismissed, bankIndex, popupBankIndex, playback, showLive, popupMode], publishVisual, { deep: true, flush: 'post' })

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
  { label: t('Loyalty redeemed'), amount: snap.value.redeemed },
  { label: t('Exchange credit'), amount: snap.value.exchangeCredit },
].filter((row) => row.amount))
const rewards = computed(() => [
  { label: t('Change saved as points'), amount: snap.value.savedChangePoints || '' },
  { label: t('Points earned'), amount: snap.value.earnedPoints || '' },
  { label: t('Points balance'), amount: snap.value.pointsBalance },
  { label: t('Cashback'), amount: snap.value.cashback },
].filter((row) => row.amount != null && row.amount !== ''))

watch(() => snap.value.contact?.id, clearContactResult)
watch([latestIndex, () => snap.value.receipt], async () => {
  await nextTick()
  const list = itemList.value
  if (!list) return
  if (snap.value.receipt) {
    list.scrollTop = 0
    return
  }
  const item = list.children[latestIndex.value]
  if (!item) return
  const bottom = item.offsetTop + item.offsetHeight
  if (item.offsetTop < list.scrollTop) list.scrollTop = item.offsetTop
  else if (bottom > list.scrollTop + list.clientHeight) list.scrollTop = bottom - list.clientHeight
})

onMounted(() => {
  document.addEventListener('fullscreenchange', updateFullscreen)
  document.documentElement.dataset.theme = 'light'
  channel = connectContactChannel(terminalId, (message) => {
    if (message?.kind === 'request-display-state') { publishVisual(); return }
    if (message?.kind === 'display-state' && isPreview) {
      mirrorState.value = message.state
      manualDismissed.value = Boolean(message.state.manualDismissed)
      liveDismissed.value = Boolean(message.state.liveDismissed)
      bankDismissed.value = Boolean(message.state.bankDismissed)
      bankIndex.value = Number(message.state.bankIndex) || 0
      return
    }
    if (message?.kind !== 'result' || message.id !== snap.value.contact?.id) return
    clearContactResult()
    error.value = message.error
  })
  stop = onCart((snapshot) => {
    if (!terminalId || snapshot?.terminalId !== terminalId) return
    if (JSON.stringify([snapshot.items, snapshot.receipt, snapshot.contact?.id]) !== JSON.stringify([snap.value.items, snap.value.receipt, snap.value.contact?.id])) liveDismissed.value = false
    let changed = -1
    snapshot.items.forEach((item, index) => {
      const previous = snap.value.items[index]
      if (item.code !== previous?.code || item.uom !== previous?.uom || item.qty > previous?.qty) changed = index
    })
    if (changed >= 0) latestIndex.value = changed
    else if (latestIndex.value >= snapshot.items.length) latestIndex.value = Math.max(0, snapshot.items.length - 1)
    snap.value = snapshot
    nextTick(publishVisual)
  })
  if (isPreview) channel?.postMessage({ kind: 'request-display-state' })
  else { channel?.postMessage({ kind: 'display-ready' }); heartbeat = setInterval(publishVisual, 1500) }
})
onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', updateFullscreen)
  stop?.()
  channel?.close()
  clearTimeout(timeout)
  clearInterval(heartbeat)
})
</script>

<style scoped>
.cd-farewell { display: flex; flex: 1; flex-direction: column; align-items: center; justify-content: center; gap: 24px; padding: clamp(24px, 5vw, 80px); text-align: center; }
.cd-farewell > .icon { color: var(--brand-dark); }
.cd-farewell h1 { max-width: 22ch; margin: 0; font-size: clamp(28px, 4.5vw, 68px); line-height: 1.15; }
.cd-farewell p { margin: 0; color: var(--text-muted); font-size: clamp(18px, 2vw, 30px); line-height: 1.5; }
.cd-farewell-detail { display: flex; flex-wrap: wrap; justify-content: center; gap: 12px; font-size: clamp(16px, 1.8vw, 24px); }
.cd-screen-tools { display: flex; align-items: center; justify-content: flex-end; gap: 12px; margin-bottom: 8px; color: var(--text); }
.cd-screen-tools > strong { margin-inline-end: auto; font-size: clamp(16px, 1.8vw, 28px); overflow-wrap: anywhere; min-width: 0; }
.cd-screen-tools > button { flex-shrink: 0; }
.cd-screen-tools > span { font-size: 12px; }
.cd-bank-dialog { width: min(840px, calc(100% - 48px)); max-width: none; max-height: calc(100dvh - 64px); margin: auto; padding: 20px; overflow: auto; border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--page-bg); color: var(--text); box-shadow: var(--shadow-md); }
.cd-bank-dialog::backdrop { background: color-mix(in srgb, var(--text) 30%, transparent); }
.cd-bank-title { display: flex; align-items: flex-start; gap: 14px; margin: 0 0 18px; }
.cd-bank-title > .icon, .cd-bank-title > button { flex-shrink: 0; }
.cd-bank-title > div { flex: 1; min-width: 0; }
.cd-bank-title h2 { font-size: 22px; margin: 0 0 4px; }
.cd-bank-title span { color: var(--text-muted); font-size: 14px; }
.cd-bank-reopen { margin-inline-start: auto; }
.cd-bank-tabs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
.cd-bank-tabs [aria-pressed=true] { border-color: var(--brand); background: var(--surface-2); }
.bank-panel-enter-active, .bank-panel-leave-active { transition: opacity .18s ease, transform .18s ease; }
.bank-panel-enter-from, .bank-panel-leave-to { opacity: 0; transform: translateY(6px); }
@media (prefers-reduced-motion: reduce) { .bank-panel-enter-active, .bank-panel-leave-active { transition: none; } }
.cdisplay { position: relative; width: 100%; height: 100dvh; overflow: hidden; background: var(--page-bg); color: var(--text); font-size: clamp(14px, .94vw, 18px); }
.cd-screen-tools { position: absolute; inset: 14px 20px auto; z-index: 40; margin: 0; pointer-events: none; }
.cd-screen-tools > strong { max-width: 70%; padding: 8px 12px; border-radius: var(--radius); background: color-mix(in srgb, var(--card-bg) 94%, transparent); }
.cd-screen-tools > button { pointer-events: auto; }
.cd-live-popup { position: absolute; z-index: 10; right: 4vw; top: 50%; transform: translateY(-50%); width: min(1080px, 78vw); height: min(760px, calc(100% - 164px)); display: flex; flex-direction: column; padding: clamp(14px, 1.8vw, 28px); background: var(--page-bg); border: 1px solid var(--border); border-radius: var(--radius-lg); box-shadow: var(--shadow-md); min-height: 0; }
.cd-live-close { position: absolute; top: 10px; right: 10px; z-index: 2; background: var(--card-bg); }
.cd-live-popup .cd-head { padding-inline-end: 30px; flex-shrink: 0; }
.cd-live-popup .cd-overlay { position: absolute; border-radius: inherit; }
.cd-popup-sheet { position: absolute; z-index: 30; top: 50%; left: 50%; transform: translate(-50%, -50%); width: min(860px, calc(100% - 96px)); max-height: calc(100% - 170px); display: flex; flex-direction: column; padding: 18px 24px 24px; background: var(--page-bg); border: 1px solid var(--border); border-radius: var(--radius-lg); box-shadow: var(--shadow-md); overflow: hidden; }
.cd-popup-heading { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding-bottom: 12px; color: var(--text-muted); }
.cd-popup-heading > button { flex-shrink: 0; }
.cd-popup-sheet :deep(.dc-notice) { min-height: 280px; }
.cd-mirror-bank { position: fixed; z-index: 60; inset: 50% auto auto 50%; transform: translate(-50%, -50%); }
.cd-head { min-height: clamp(44px, 3.5vw, 66px); display: flex; align-items: center; gap: 10px; margin-bottom: clamp(10px, .9vw, 17px); }
.cd-head h1 { margin: 0; font-size: clamp(18px, 1.85vw, 36px); overflow-wrap: anywhere; }
.cd-head > div { min-width: 0; }
.cd-receipt { margin-inline-start: auto; text-align: end; color: var(--text-muted); font-size: .88rem; overflow-wrap: anywhere; }
.cd-receipt strong { color: var(--text); }
.cd-content { display: grid; grid-template-columns: minmax(160px, 1fr) minmax(0, 2.95fr); flex: 1; min-height: 0; gap: clamp(10px, .95vw, 18px); }
.cd-sidebar {
  display: grid;
  align-content: start;
  gap: 8px;
  min-width: 0;
  min-height: 0;
  overflow: auto;
}
.cd-greeting, .cd-details { background: var(--card-bg); border-radius: var(--radius); }
.cd-greeting { padding: clamp(10px, 1.1vw, 21px); }
.cd-details { padding: 6px 10px 10px; }
.cd-greeting, .cd-row, .cd-list-heading { display: flex; align-items: center; gap: 10px; }
.cd-row { min-width: 0; padding: 6px 4px; justify-content: space-between; border-top: 1px solid var(--border-subtle); }
.cd-row > :last-child { text-align: end; }
.cd-paid { padding: 8px; border-radius: 8px; border-top: 0; background: var(--surface-2); color: var(--topbar-bg); }
.cd-greeting strong { display: block; overflow-wrap: anywhere; }
.cd-list-heading { justify-content: space-between; padding: 8px 10px; }
.cd-row > * { overflow-wrap: anywhere; }
.cd-cart { display: flex; flex-direction: column; flex: 1; min-height: 0; min-width: 0; }
.cd-latest { --product-art-size: clamp(60px, 7.2vw, 136px); display: flex; align-items: center; gap: clamp(10px, 1.35vw, 26px); padding: clamp(12px, 1.6vw, 30px); border-radius: var(--radius-lg); background: var(--pos-blue); color: white; }
.cd-latest-copy, .cd-latest-price { display: grid; gap: 4px; }
.cd-latest-copy { flex: 1; min-width: 0; }
.cd-latest-copy strong { font-size: clamp(18px, 2.25vw, 43px); line-height: 1.15; overflow-wrap: anywhere; }
.cd-latest-price { text-align: end; }
.cd-latest-price strong { border-radius: 8px; color: #123c7a; background: var(--card-bg); padding: 5px 10px; font-size: clamp(17px, 2.05vw, 39px); }
.cd-items { display: grid; position: relative; grid-template-columns: repeat(2, minmax(0, 1fr)); align-content: start; overflow: auto; gap: 8px; }
.cd-item { --product-art-size: clamp(42px, 3.15vw, 60px); display: flex; align-items: center; gap: 10px; min-width: 0; border-radius: 10px; padding: clamp(8px, .73vw, 14px) 12px; background: var(--card-bg); }
.cd-item-main { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.cd-prices { display: grid; justify-items: end; text-align: end; font-size: .94em; }
.cd-totals { display: grid; grid-auto-columns: minmax(0, 1fr); grid-auto-flow: column; gap: 8px; margin-top: clamp(8px, .8vw, 15px); }
.cd-totals > div { display: grid; gap: 4px; padding: clamp(8px, .8vw, 15px); background: var(--card-bg); border-radius: 12px; }
.cd-totals strong { font-size: clamp(18px, 2.14vw, 41px); overflow-wrap: anywhere; }
.cd-saving, .cd-reward { color: #21624d; font-weight: 700; }
.cd-totals .cd-saving { background: #e3f4ed; }
.cd-totals .cd-grand { background: #174f9b; color: white; }
.cd-totals .cd-balance { background: #d9eafe; }
.cd-receipt-brand { display: block; text-align: center; margin-top: 6px; }
.cd-equivalent { text-align: end; }
.cd-next { width: 100%; margin-top: 8px; }
.cd-empty { margin: 12vh auto; text-align: center; color: var(--text-muted); font-size: 1.25rem; }
.cd-welcome { width: min(1160px, 100%); flex: 1; min-height: 0; overflow: auto; align-self: center; display: grid; grid-template-columns: 1fr 1fr; align-content: center; }
.cd-welcome-brand { background: var(--topbar-bg); color: #fff; display: flex; flex-direction: column; justify-content: center; align-items: flex-start; padding: clamp(18px, 5vw, 62px); border-radius: 16px 0 0 16px; }
.cd-welcome-brand img { width: 65px; height: 65px; object-fit: contain; background: white; padding: 7px; border-radius: 12px; }
.cd-welcome-brand p { margin: 26px 0 0; font-size: clamp(18px, 3vw, 34px); }
.cd-welcome-brand h1 { margin: 0; font-size: clamp(27px, 5vw, 68px); line-height: 1.02; overflow-wrap: anywhere; }
.cd-welcome :deep(.contact-pad) { border-radius: 0 16px 16px 0; }
.cd-overlay { position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; padding: 10px; background: color-mix(in srgb, var(--topbar-bg) 60%, transparent); }
.cd-dialog { width: min(440px, 100%); max-height: 100%; overflow: auto; border-radius: 16px; }
@media (max-width: 900px) {
  .cd-items { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 600px) {
  .cd-screen-tools { inset: 10px 12px auto; gap: 6px; }
  .cd-screen-tools > strong { font-size: 14px; padding: 8px; }
  .cd-live-popup { left: 12px; right: 12px; width: auto; height: calc(100% - 176px); padding: 12px; }
  .cd-popup-sheet { width: calc(100% - 28px); max-height: calc(100% - 170px); padding: 12px; }
  .cd-bank-dialog { width: calc(100% - 24px); max-height: calc(100dvh - 40px); padding: 12px; }
  .cd-bank-title { gap: 8px; }
  .cd-bank-title h2 { font-size: 18px; }
  .cd-bank-title span { font-size: 12px; }
  .cd-content { grid-template-columns: minmax(0, 1fr); grid-template-rows: auto minmax(0, 1fr); gap: 8px; }
  .cd-sidebar { max-height: 22dvh; }
  .cd-latest { display: grid; grid-template-columns: auto minmax(0, 1fr); }
  .cd-latest-price { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; grid-column: 1 / -1; }
  .cd-totals { grid-auto-flow: row; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .cd-welcome { grid-template-columns: minmax(0, 1fr); align-content: start; }
  .cd-welcome-brand { border-radius: 14px 14px 0 0; }
  .cd-welcome-brand img { width: 40px; height: 40px; }
  .cd-welcome-brand p { margin-top: 10px; }
  .cd-welcome :deep(.contact-pad) { border-radius: 0 0 14px 14px; }
}
</style>
