<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<template>
  <div class="cdisplay">
    <header class="cd-head">
      <img v-if="snap.logo" :src="snap.logo" class="cd-logo" alt="" />
      <div class="cd-company">{{ snap.company || t('Welcome') }}</div>
      <div v-if="snap.customer" class="cd-customer">{{ snap.customer }}</div>
    </header>

    <div v-if="snap.items.length" class="cd-content">
      <div class="cd-cart">
        <div class="cd-items">
          <div v-for="(it, i) in snap.items" :key="i" class="cd-item">
            <div class="cd-item-main">
              <div class="cd-item-name">{{ it.name }}</div>
              <div class="cd-item-qty">{{ it.qty }} × {{ it.rate }}</div>
            </div>
            <div class="cd-item-amt">{{ it.amount }}</div>
          </div>
        </div>
        <div class="cd-totals">
          <div v-if="snap.savings" class="cd-row cd-save">
            <span>{{ t('You save') }}</span><span>{{ snap.savings }}</span>
          </div>
          <div class="cd-row cd-grand">
            <span>{{ t('Total') }}</span><span>{{ snap.total }}</span>
          </div>
          <div v-if="snap.equivalent" class="cd-row cd-equiv">
            <span></span><span>= {{ snap.equivalent }}</span>
          </div>
          <div class="cd-count">{{ t('{count} items', { count: snap.count }) }}</div>
        </div>
      </div>
      <section class="cd-details" aria-labelledby="customer-details-title">
        <h1 id="customer-details-title">{{ t('Your details') }}</h1>
        <p class="cd-details-intro">{{ t('Enter your name and contact number for this sale.') }}</p>
        <form @submit.prevent="submitDetails">
          <label for="display-customer-name">{{ t('Customer name') }}</label>
          <input id="display-customer-name" v-model="customerName" type="text" autocomplete="off" maxlength="140" required :disabled="busy || saved || !snap.customerEntryEnabled" />
          <label for="display-customer-phone">{{ t('Contact number') }}</label>
          <input id="display-customer-phone" v-model="mobile" type="tel" inputmode="tel" autocomplete="off" maxlength="32" required :disabled="busy || saved || !snap.customerEntryEnabled" />
          <p v-if="error" class="cd-error" role="alert">{{ error }}</p>
          <p v-if="saved" class="cd-success" role="status">{{ t('Thank you. Your details have been added to this sale.') }}</p>
          <button v-if="saved" type="button" class="btn btn-outline" :disabled="!snap.customerEntryEnabled" @click="saved = false">{{ t('Edit details') }}</button>
          <button v-else type="submit" class="btn btn-primary" :disabled="busy || !snap.customerEntryEnabled">
            {{ busy ? t('Saving…') : t('Save details') }}
          </button>
          <p v-if="!snap.customerEntryEnabled" class="cd-details-intro" role="status">{{ t('Please wait for the cashier.') }}</p>
        </form>
      </section>
    </div>

    <div v-else class="cd-welcome">
      <div class="cd-welcome-mark">{{ (snap.company || 'L').slice(0, 1) }}</div>
      <div class="cd-welcome-text">{{ t('Welcome') }}</div>
      <div class="cd-welcome-sub">{{ snap.company }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { t } from '../i18n'
import { onCart, onDisplayCustomerResult, sendDisplayCustomer } from '../customerDisplay'
import { customerEntryError } from '../displayCustomerEntry'
import { applyTheme } from '../theme'
import { newId } from '../offline'

const snap = ref({ company: '', logo: '', items: [], count: 0, total: '', equivalent: '', savings: '', customer: '' })
let stop = null
let stopResult = null
let timer = null
let requestId = ''
let terminalId = new URLSearchParams(window.location.hash.split('?')[1] || '').get('terminal') || ''
const customerName = ref('')
const mobile = ref('')
const error = ref('')
const busy = ref(false)
const saved = ref(false)

function resetDetails() {
  customerName.value = ''
  mobile.value = ''
  error.value = ''
  busy.value = false
  saved.value = false
  requestId = ''
  clearTimeout(timer)
}

function submitDetails() {
  if (busy.value || !snap.value.customerEntryEnabled) return
  error.value = customerEntryError(customerName.value, mobile.value)
  if (error.value) return
  requestId = newId()
  busy.value = true
  timer = setTimeout(() => {
    busy.value = false
    requestId = ''
    error.value = t('The cashier is not responding. Please ask for help or try again.')
  }, 20000)
  try {
    sendDisplayCustomer({ terminalId, saleId: snap.value.saleId, requestId,
      customer_name: customerName.value.trim(), mobile_no: mobile.value.trim() })
  } catch {
    clearTimeout(timer)
    busy.value = false
    error.value = t('Could not connect to the cashier. Please ask for help.')
  }
}

onMounted(() => {
  // This window stays light without changing the cashier's saved preference.
  document.documentElement.setAttribute('data-theme', 'light')
  stop = onCart((s) => {
    if (!s?.terminalId || (terminalId && s.terminalId !== terminalId)) return
    if (!terminalId && s.displayEnabled === false) return
    terminalId = s.terminalId
    if (snap.value.saleId !== s.saleId || !s.items?.length ||
      (saved.value && snap.value.customerKey !== s.customerKey)) resetDetails()
    snap.value = { items: [], count: 0, total: '', equivalent: '', savings: '', customer: '', company: '', logo: '', ...s }
  })
  stopResult = onDisplayCustomerResult((result) => {
    if (result.terminalId !== terminalId || result.saleId !== snap.value.saleId || result.requestId !== requestId) return
    clearTimeout(timer)
    busy.value = false
    saved.value = Boolean(result.ok)
    error.value = result.error || ''
  })
})
onBeforeUnmount(() => {
  stop?.()
  stopResult?.()
  clearTimeout(timer)
  applyTheme()
})
</script>

<style scoped>
.cdisplay {
  position: fixed;
  inset: 0;
  background: var(--card-bg);
  color: var(--text);
  color-scheme: light;
  display: flex;
  flex-direction: column;
  padding: 4vh 4vw;
  font-family: 'Inter', system-ui, sans-serif;
  overflow-y: auto;
}
.cd-head {
  text-align: center;
  padding-bottom: 3vh;
  border-bottom: 2px solid var(--border, rgba(255, 255, 255, 0.12));
}
.cd-logo { max-height: 12vh; max-width: 60%; object-fit: contain; margin-bottom: 2vh; }
.cd-company { font-size: 4vh; font-weight: 800; letter-spacing: -0.01em; }
.cd-customer { font-size: 2.2vh; color: var(--brand, #13a795); font-weight: 700; margin-top: 0.5vh; }
.cd-content { display: grid; grid-template-columns: minmax(0, 1fr) minmax(280px, 360px); gap: 4vw; flex: 1; min-height: 0; padding-top: 3vh; }
.cd-cart { display: flex; flex-direction: column; min-height: 0; }
.cd-details { align-self: start; padding: 24px; background: var(--surface-2); border-radius: var(--radius-lg); }
.cd-details h1 { margin: 0 0 10px; font-size: 24px; line-height: 1.3; }
.cd-details-intro { color: var(--text-muted); font-size: 15px; line-height: 1.5; margin: 0 0 24px; }
.cd-details label { display: block; font-size: 15px; font-weight: 600; margin-bottom: 8px; }
.cd-details input { width: 100%; min-height: 52px; font-size: 18px; margin-bottom: 20px; }
.cd-details .btn { width: 100%; min-height: 52px; font-size: 16px; }
.cd-details .btn-primary { background: var(--brand-dark); box-shadow: none; }
.cd-error { color: var(--red); font-size: 15px; line-height: 1.5; }
.cd-success { color: var(--brand-dark); font-size: 16px; line-height: 1.5; }
.cd-items { flex: 1; overflow-y: auto; min-height: 0; }
.cd-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 3vw;
  padding: 2vh 0;
  border-bottom: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.08));
}
.cd-item-main { min-width: 0; overflow-wrap: anywhere; }
.cd-item-name { font-size: clamp(18px, 3vh, 30px); font-weight: 700; }
.cd-item-qty { font-size: 2.2vh; color: var(--text-muted, #9aa4bf); margin-top: 0.4vh; }
.cd-item-amt { font-size: 3.2vh; font-weight: 800; white-space: nowrap; }
.cd-totals { padding-top: 2vh; border-top: 3px solid var(--brand, #13a795); }
.cd-row { display: flex; justify-content: space-between; }
.cd-save { color: var(--brand, #13a795); font-size: 2.6vh; font-weight: 700; margin-bottom: 1vh; }
.cd-grand { font-size: clamp(28px, 4vw, 52px); font-weight: 800; gap: 16px; flex-wrap: wrap; }
.cd-equiv { font-size: 2.6vh; font-weight: 700; color: var(--text-muted, #9aa4bf); }
.cd-count { text-align: right; font-size: 2vh; color: var(--text-muted, #9aa4bf); margin-top: 1vh; }
.cd-welcome { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2vh; }
.cd-welcome-mark {
  width: 16vh;
  height: 16vh;
  border-radius: 4vh;
  background: #13a795;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9vh;
  font-weight: 900;
  box-shadow: 0 1vh 4vh rgba(19, 167, 149, 0.4);
}
.cd-welcome-text { font-size: 5vh; font-weight: 800; }
.cd-welcome-sub { font-size: 2.6vh; color: var(--text-muted, #9aa4bf); }
@media (max-width: 800px) {
  .cdisplay { padding: 24px 20px; }
  .cd-content { display: flex; flex-direction: column; flex: 0 0 auto; gap: 28px; }
  .cd-cart { min-height: 260px; }
  .cd-items { flex: 0 0 auto; max-height: 36vh; }
  .cd-totals { margin-top: 24px; }
  .cd-details { width: 100%; }
  .cd-company { font-size: 28px; }
  .cd-item-amt { font-size: 22px; }
}
</style>
