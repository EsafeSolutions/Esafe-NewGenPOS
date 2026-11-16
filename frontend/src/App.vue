<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<template>
  <!-- Customer-facing display: a chrome-free second screen, no app shell and
       no bootstrap, it exchanges cart/customer details over BroadcastChannel. -->
  <router-view v-if="isDisplay" />

  <div class="shell" v-else-if="session.loaded && !session.error" @keydown.esc="closeNavigation">
    <NavRail :mobile-open="navOpen" @navigate="closeNavigation" />
    <div v-if="navOpen" class="nav-backdrop" aria-hidden="true" @click="closeNavigation"></div>
    <div class="main">
      <header class="topbar">
        <div class="topbar-left">
          <button ref="navToggle" type="button" class="lang-pill topbar-icon nav-toggle" data-tour="nav-rail"
            aria-controls="pos-navigation" :aria-expanded="navOpen"
            :aria-label="navOpen ? t('Close menu') : t('Open menu')" @click="toggleNavigation">
            <Icon :name="navOpen ? 'close' : 'menu'" :size="20" />
          </button>
          <div class="brand-lockup">
            <span class="brand-identity">
              <PosBrandMark class="mobile-brand" />
              <span class="brand-wordmark">ESAFE ERP POS</span>
            </span>
          </div>
          <span class="brand-divider" aria-hidden="true"></span>
          <div class="topbar-title">{{ pageTitle }}</div>
          <span class="tb-pill tb-clock"><Icon name="clock" /> {{ clockText }}</span>
          <span v-if="session.registerOpen && shiftText" class="tb-pill tb-shift">
            <Icon name="check" /> {{ t('Shift Open:') }} <b>{{ shiftText }}</b>
          </span>
        </div>
        <div v-if="session.company" class="topbar-shop">
          <bdi class="shop-name" :title="session.company">{{ session.company }}</bdi>
        </div>
        <div class="topbar-right" :inert="navOpen">
          <div v-if="route.path === '/'" id="sell-header-tools" class="topbar-tools"></div>
          <button type="button" class="lang-pill topbar-icon" :title="themeAction" :aria-label="themeAction" @click="toggleTheme">
            <Icon :name="theme === 'dark' ? 'sun' : 'moon'" />
          </button>
          <!-- Help for this screen (0.58.0, Settings, General, Help for staff). -->
          <button
            v-if="help.inTill"
            class="lang-pill topbar-icon"
            data-tour="help-button"
            :title="t('Help for this screen')"
            :aria-label="t('Help for this screen')"
            @click="help.togglePanel()"
          >
            <Icon name="help" />
          </button>
          <button
            v-if="session.settings.enable_xreport && session.registerOpen"
            class="lang-pill topbar-icon"
            data-tour="xreport"
            :title="t('X-report (mid-shift read)')"
            :aria-label="t('X-report')"
            :disabled="xreportLoading"
            @click="openXReport"
          >
            <Icon name="report" />
          </button>
          <button
            v-if="session.settings.enable_till_lock"
            class="lang-pill topbar-icon"
            :title="t('Lock the till')"
            :aria-label="t('Lock the till')"
            @click="session.lockTill()"
          >
            <Icon name="shield" />
          </button>
          <!-- Two languages: one tap swaps them. More: a short list. -->
          <button
            v-if="offeredLanguages.length === 2"
            class="lang-pill topbar-icon"
            data-tour="language"
            :title="t('Language') + ' · ' + otherLanguage.name"
            :aria-label="t('Language') + ' · ' + otherLanguage.name"
            :lang="otherLanguage.code"
            @click="setLocale(otherLanguage.code)"
          >
            <Icon name="globe" />
          </button>
          <div v-else-if="offeredLanguages.length > 2" ref="langMenu" class="lang-menu" data-tour="language">
            <button
              class="lang-pill topbar-icon"
              :title="t('Language') + ' · ' + currentLanguage.name"
              :aria-label="t('Language') + ' · ' + currentLanguage.name"
              aria-haspopup="listbox"
              :aria-expanded="langOpen ? 'true' : 'false'"
              @click="langOpen = !langOpen"
            >
              <Icon name="globe" />
            </button>
            <div v-if="langOpen" class="lang-list" role="listbox" :aria-label="t('Language')">
              <button
                v-for="l in offeredLanguages"
                :key="l.code"
                class="lang-option"
                :class="{ active: l.code === locale }"
                role="option"
                :aria-selected="l.code === locale ? 'true' : 'false'"
                @click="pickLanguage(l.code)"
              >
                <bdi :lang="l.code">{{ l.name }}</bdi>
              </button>
            </div>
          </div>
          <button
            v-if="session.offline"
            class="offline-pill"
            :title="t('View queued offline sales')"
            @click="offlineLogOpen = true"
          >
            ⚠ {{ t('Offline') }}{{ session.queuedCount ? `, ${session.queuedCount}` : '' }}
          </button>
          <button
            v-else-if="session.queuedCount"
            class="offline-pill syncing"
            :title="t('View offline sales log')"
            @click="offlineLogOpen = true"
          >
            {{ t('Syncing') }} {{ session.queuedCount }}…
          </button>
          <button
            v-if="!session.reportsOnly"
            class="register-pill"
            data-tour="register-pill"
            :class="{ open: session.registerOpen }"
            :title="session.registerOpen ? t('Go to the Register page to close it') : t('Open the register')"
            @click="$router.push('/register')"
          >
            {{ session.registerOpen ? t('Register open ▸ close') : t('Register closed') }}
          </button>
          <!-- The outlet, switchable here too (a manager covering outlets of
               two companies no longer has to close a shift to change over). -->
          <!-- The reports alone (0.65.0): who, and that this screen is reports only. -->
          <span v-if="session.reportsOnly" class="topbar-user">
            <span class="user-name">{{ session.userFullname }} ·</span>
            {{ t('Reports only') }}
          </span>
          <span v-else class="topbar-user">
            <span class="user-name">{{ session.userFullname }} ·</span>
            <select
              v-if="session.availableProfiles.length > 1"
              class="outlet-switch"
              :value="session.posProfile"
              :title="t('Switch outlet')"
              @change="switchOutlet($event)"
            >
              <option v-for="p in session.availableProfiles" :key="p" :value="p">{{ session.outletLabel(p) }}</option>
            </select>
            <template v-else>{{ session.outletLabel(session.posProfile) }}</template>
          </span>
          <a href="/app" class="lang-pill topbar-icon erp-link" :title="t('Back to ERPNext')" :aria-label="t('Back to ERPNext')">
            <Icon name="logout" />
          </a>
        </div>
      </header>
      <StorageWarning v-if="!session.reportsOnly" />
      <main class="content" :inert="navOpen">
        <!-- The reports alone: no other screen mounts, not even for the moment
             before the move to Insights (the Sell screen would ask for products). -->
        <router-view v-if="!session.reportsOnly || route.path === '/insights'" :key="session.posProfile" />
        <!-- The open-register prompt only blocks the Sell screen; the nav
             rail and other tabs (Register, History, Settings) stay usable. -->
        <!-- A tour shows the Sell screen under it, so the prompt steps aside. -->
        <OpenRegisterOverlay v-if="!session.reportsOnly && !session.registerOpen && route.path === '/' && !help.tourId" />
      </main>
    </div>
    <div v-if="session.toast" class="toast" :class="{ error: session.toast.isError }">
      <!-- The store raises its own messages in English ("Back online"); a
           known one shows in the till's language, anything else as it came. -->
      {{ t(session.toast.message) }}
    </div>
    <LockOverlay v-if="session.locked" />
    <XReportModal v-if="xreportOpen && xreportSummary" :summary="xreportSummary" @close="xreportOpen = false" />
    <OfflineLogModal v-if="offlineLogOpen" @close="offlineLogOpen = false" />
    <HelpPanel />
    <HelpCard v-if="!session.locked" />
    <TourOverlay />
  </div>

  <div v-else-if="!isDisplay && session.error" class="boot-error">
    <div class="card boot-card">
      <h2>{{ t('EsafePOS could not start') }}</h2>
      <p>{{ session.error }}</p>
      <button class="btn btn-primary" @click="session.bootstrap()">{{ t('Retry') }}</button>
    </div>
  </div>

  <div v-else class="boot-loading">{{ t('Loading EsafePOS…') }}</div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { call } from './api'
import { useSessionStore } from './stores/session'
import { useCatalogStore } from './stores/catalog'
import { useCartStore } from './stores/cart'
import { money, shiftClock, isolate } from './format'
import { displayContactRequest, displayCustomerName, displayPayment, displayReceipt, publishCart, onDisplayRequest, requestDisplayContact } from './customerDisplay'
import { connectTillContact } from './displayContact'
import { ensurePersistentStorage } from './offline'
import { t, locale, setLocale, offeredLanguages, LANGUAGES } from './i18n'
import { theme, toggleTheme } from './theme'
import PosBrandMark from './components/PosBrandMark.vue'
import Icon from './components/Icon.vue'
import NavRail from './components/NavRail.vue'
import OpenRegisterOverlay from './components/OpenRegisterOverlay.vue'
import LockOverlay from './components/LockOverlay.vue'
import XReportModal from './components/XReportModal.vue'
import OfflineLogModal from './components/OfflineLogModal.vue'
import StorageWarning from './components/StorageWarning.vue'
import HelpPanel from './components/HelpPanel.vue'
import HelpCard from './components/HelpCard.vue'
import TourOverlay from './components/TourOverlay.vue'
import { useHelpStore } from './stores/help'

const session = useSessionStore()
const help = useHelpStore()
const catalog = useCatalogStore()
const cart = useCartStore()
const themeAction = computed(() => theme.value === 'dark' ? t('Switch to light mode') : t('Switch to dark mode'))

// Switch the outlet this screen works on. The other outlet's shift stays as it
// is; a sale half rung up here is cleared first, with the cashier's say-so.
async function switchOutlet(event) {
  const name = event.target.value
  if (!name || name === session.posProfile) return
  if (cart.lines.length && !confirm(t('The sale on screen will be cleared. Switch outlet?'))) {
    event.target.value = session.posProfile
    return
  }
  cart.clear()
  displayReceipt.value = null
  await session.switchProfile(name)
  catalog.fetch()
  catalog.cacheFullCatalog()
  catalog.cacheCustomers()
}
const route = useRoute()
const router = useRouter()
const isDisplay = computed(() => route.path === '/display')
const navOpen = ref(false)
const navToggle = ref(null)

async function toggleNavigation() {
  if (navOpen.value) {
    closeNavigation()
    return
  }
  navOpen.value = true
  await nextTick()
  document.querySelector('#pos-navigation a')?.focus()
}

function closeNavigation() {
  if (!navOpen.value) return
  navOpen.value = false
  navToggle.value?.focus()
}

const mobileNavQuery = window.matchMedia('(max-width: 700px)')
function resetNavigationOnDesktop(event) {
  if (!event.matches) navOpen.value = false
}
watch(() => route.path, closeNavigation)
onMounted(() => mobileNavQuery.addEventListener('change', resetNavigationOnDesktop))
onBeforeUnmount(() => mobileNavQuery.removeEventListener('change', resetNavigationOnDesktop))

// The reports alone (0.65.0): Insights is the only screen there is.
watch(
  () => [session.reportsOnly, route.path],
  ([only, path]) => {
    if (only && path !== '/insights') router.replace('/insights')
  }
)

// The language control in the top bar.
const langOpen = ref(false)
const langMenu = ref(null)
const currentLanguage = computed(() => LANGUAGES.find((l) => l.code === locale.value) || LANGUAGES[0])
const otherLanguage = computed(
  () => offeredLanguages.value.find((l) => l.code !== locale.value) || LANGUAGES[0]
)
async function pickLanguage(code) {
  langOpen.value = false
  await setLocale(code)
}
function closeLangMenu(event) {
  if (!langOpen.value) return
  if (event.type === 'keydown' && event.key !== 'Escape') return
  if (event.type === 'pointerdown' && langMenu.value && langMenu.value.contains(event.target)) return
  langOpen.value = false
}
window.addEventListener('pointerdown', closeLangMenu)
window.addEventListener('keydown', closeLangMenu)
onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', closeLangMenu)
  window.removeEventListener('keydown', closeLangMenu)
})

// Live clock + "shift open" elapsed timer for the top bar (ticks every second).
const now = ref(Date.now())
let clockTimer = null
const pad = (n) => String(n).padStart(2, '0')
const clockText = computed(() => {
  const d = new Date(now.value)
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
})
// How long the shift has been open, as a clock (07:01:20), counted on the
// site's clock: the shift's opening time is the site's, so a device in another
// zone (or set wrong) read hours too many or too few before 0.61.1.
const shiftText = computed(() => {
  const openedAt = session.registerSession?.opened_at
  if (!openedAt) return ''
  return isolate(shiftClock(openedAt, session.siteNow(now.value)))
})
onBeforeUnmount(() => clearInterval(clockTimer))

// X-report, reachable from the top bar all shift. Fetches a fresh read-only
// session summary on demand (no register-page visit needed).
const xreportOpen = ref(false)
const xreportSummary = ref(null)
const xreportLoading = ref(false)

// Offline sales log, reachable from the offline / syncing pill and Settings.
const offlineLogOpen = ref(false)
async function openXReport() {
  if (!session.registerSession || xreportLoading.value) return
  xreportLoading.value = true
  try {
    xreportSummary.value = await call('esafepos.api.register.get_session_summary', {
      session: session.registerSession.name,
    })
    xreportOpen.value = true
  } catch (e) {
    session.notify(e.message, true)
  } finally {
    xreportLoading.value = false
  }
}

// Push a fully-formatted cart snapshot to any open customer display.
function publishDisplaySnapshot() {
  if (!session.settings?.enable_customer_display || session.locked) {
    publishCart({ items: [] })
    return
  }
  const contact = route.path === '/' ? displayContactRequest.value : null
  if (!cart.lines.length && displayReceipt.value) {
    publishCart({ logo: session.settings?.receipt_logo || '', ...displayReceipt.value, contact, canStart: route.path === '/' })
    return
  }
  const saved = cart.promoSavings + cart.bundleSavings + cart.manualDiscountTotal + cart.orderDiscountTotal
  const discounts = cart.unitDiscounts
  // A sale in another currency is shown in it, with its local value under it.
  const sale = cart.saleCurrency
  const mc = session.multiCurrency || {}
  const equivalent =
    sale.foreign && !sale.blocked && mc.outlet_rate && sale.currency !== mc.company_currency
      ? money(Math.round(cart.total * mc.outlet_rate * 100) / 100, mc.company_currency)
      : ''
  publishCart({
    company: session.company,
    logo: session.settings?.receipt_logo || '',
    customer: displayCustomerName(cart.customer?.customer_name),
    pointsBalance: cart.wallet?.loyalty_points,
    contact,
    items: cart.lines.map((l, index) => ({
      name: l.item_name,
      code: l.item_code,
      image: l.image,
      group: l.item_group,
      qty: l.qty,
      uom: l.selling_uom || l.uom,
      rate: cart.show(l.price),
      amount: cart.show((l.price - discounts[index]) * l.qty),
      gross: discounts[index] > 0 ? cart.show(l.price * l.qty) : '',
      discount: discounts[index] > 0 ? cart.show(discounts[index] * l.qty) : '',
    })),
    count: cart.lines.length,
    subtotal: cart.show(cart.subtotal),
    total: cart.show(cart.total),
    equivalent,
    savings: saved > 0.005 ? cart.show(saved) : '',
    tax: cart.taxBreakdown.exclusiveTotal ? cart.show(cart.taxBreakdown.exclusiveTotal) : '',
    service: cart.serviceCharge ? cart.show(cart.serviceCharge) : '',
    due: cart.lines.length ? cart.show(cart.total) : '',
    ...(cart.lines.length ? displayPayment.value : null),
  })
}

const pageTitle = computed(
  () =>
    ({
      '/': t('Sell'),
      '/history': t('Sales History'),
      '/customers': t('Customers'),
      '/holds': t('Holds'),
      '/register': t('Register'),
      '/insights': t('Insights'),
      '/labels': t('Labels'),
      '/items': t('Items'),
      '/count': t('Stock count'),
      '/settings': t('Settings'),
    })[route.path] || t('Sell')
)

onMounted(async () => {
  // The display talks to its till window, with no bootstrap, catalog or shell.
  if (isDisplay.value) return

  clockTimer = setInterval(() => (now.value = Date.now()), 1000)
  // Make offline storage persistent so a queued sale can't be evicted under
  // disk pressure / LRU (fire-and-forget; grant is heuristic).
  ensurePersistentStorage()
  session.watchConnection()
  await session.bootstrap()
  if (session.loaded && !session.error && session.reportsOnly) return
  if (session.loaded && !session.error) {
    catalog.fetch()
    catalog.cacheFullCatalog() // background fill of the offline cache
    catalog.cacheCustomers() // recent-customers subset for offline select
    if (session.queuedCount && !session.offline) session.flushQueue()
    // Mirror the cart to any open customer display, and answer a display that
    // opens later and asks for the current state.
    displayCleanup.push(cart.$subscribe(() => {
      if (cart.lines.length) displayReceipt.value = null
      publishDisplaySnapshot()
    }))
    displayCleanup.push(onDisplayRequest(publishDisplaySnapshot))
    displayCleanup.push(connectTillContact(cart, session, route))
    displayCleanup.push(watch(() => [
      route.path, session.settings?.enable_customer_display, session.posProfile, session.locked,
      session.offline, cart.lines.length, cart.customer, Boolean(displayReceipt.value),
    ], () => {
      if (route.path === '/' && session.settings?.enable_customer_display && session.posProfile &&
          !session.locked && !session.offline && !cart.submitting && !cart.lines.length && !cart.customer &&
          !displayReceipt.value && !displayContactRequest.value) requestDisplayContact('welcome')
    }, { immediate: true, flush: 'post' }))
    displayCleanup.push(watch(() => [route.path, session.settings?.enable_customer_display, session.locked,
      displayPayment.value, displayReceipt.value, displayContactRequest.value], publishDisplaySnapshot))
    publishDisplaySnapshot()
    setupAutoLock()
    // Who sees the welcome, or what is new since their last visit.
    help.init()
  }
})

const displayCleanup = []
onBeforeUnmount(() => displayCleanup.forEach((stop) => stop()))

// Auto-lock the till after a configured idle period (0 = manual lock only).
let idleTimer = null
function setupAutoLock() {
  const reset = () => {
    clearTimeout(idleTimer)
    const mins = session.settings?.auto_lock_minutes || 0
    if (!session.settings?.enable_till_lock || mins <= 0 || session.locked) return
    idleTimer = setTimeout(() => session.lockTill(), mins * 60000)
  }
  for (const ev of ['mousemove', 'keydown', 'click', 'touchstart']) {
    window.addEventListener(ev, reset, { passive: true })
  }
  reset()
}
</script>

<style scoped>
.shell {
  display: flex;
  height: 100vh;
  height: 100dvh;
}
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.topbar {
  min-height: 52px;
  background: var(--topbar-bg);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  gap: 12px 20px;
  flex-shrink: 0;
}
.topbar-left {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
  gap: 12px;
  min-width: 0;
  max-width: 42%;
  flex-wrap: wrap;
}
.brand-lockup {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  max-width: 100%;
}
.brand-identity {
  display: inline-flex;
  flex: none;
  align-items: center;
  gap: 8px;
}
.brand-identity .mobile-brand { display: none; }
.brand-wordmark {
  color: #fff;
  font: 800 14px/1.2 "Plus Jakarta Sans", var(--font);
  letter-spacing: .035em;
  white-space: nowrap;
}
.topbar-shop {
  flex: 1 0 14rem;
  display: flex;
  justify-content: center;
  min-width: 0;
}
.shop-name {
  max-width: min(100%, 460px);
  padding: 7px clamp(10px, 1.2vw, 24px) 8px;
  border: 1px solid rgba(255, 255, 255, .24);
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(255, 255, 255, .18), rgba(255, 255, 255, .08));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .18), 0 6px 18px rgba(8, 51, 113, .16);
  text-align: center;
  letter-spacing: .01em;
  font-size: 18px;
  font-weight: 800;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.brand-divider { width: 1px; height: 24px; background: rgba(255, 255, 255, 0.24); flex: 0 0 auto; }
.topbar-title {
  font-size: 17px;
  font-weight: 700;
  white-space: nowrap;
}
.tb-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  font-weight: 700;
  padding: 4px 11px;
  border-radius: 999px;
  white-space: nowrap;
}
.tb-clock { background: rgba(7, 57, 59, .42); color: #b8f0e8; }
.tb-shift { background: rgba(7, 57, 59, .42); color: #b3f0cb; }
.tb-shift b { color: #fff; font-weight: 800; }
.topbar-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}
.topbar-tools { display: flex; align-items: center; gap: 6px; }
.topbar-tools:empty { display: none; }
.lang-pill.topbar-icon { display: inline-grid; place-items: center; width: 36px; min-height: 36px; padding: 0; }
.erp-link { text-decoration: none; }
.topbar-icon:focus-visible { outline: 2px solid var(--brand-soft); outline-offset: 2px; }
.lang-pill.nav-toggle, .nav-backdrop { display: none; }
.topbar-user {
  font-size: 12.5px;
  color: var(--on-pos-blue-muted);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.lang-pill,
.register-pill,
.offline-pill { white-space: nowrap; }
/* Below 1400px the user's name makes room: the outlet stays. */
@media (max-width: 1400px) {
  .topbar-user .user-name { display: none; }
}
.outlet-switch {
  font-size: 12.5px;
  padding: 3px 8px;
  border-radius: 8px;
  background: transparent;
  color: inherit;
  border: 1px solid rgba(255, 255, 255, 0.25);
  max-width: 260px;
}
.outlet-switch option { color: var(--text); background: var(--card-bg); }
.register-pill {
  font-size: 11.5px;
  font-weight: 700;
  padding: 3px 11px;
  border-radius: 999px;
  background: rgba(60, 19, 47, .42);
  color: #ffd4d4;
  cursor: pointer;
}
.register-pill:hover { filter: brightness(1.2); }
.register-pill.open {
  background: rgba(7, 57, 59, .42);
  color: #afe9e1;
}
.lang-pill {
  font-size: 11.5px;
  font-weight: 700;
  padding: 3px 11px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.16);
  color: #fff;
  cursor: pointer;
}
.lang-pill:hover { background: rgba(255, 255, 255, 0.26); }
.lang-menu { position: relative; }
.lang-list {
  position: absolute;
  top: calc(100% + 8px);
  inset-inline-end: 0;
  z-index: 60;
  min-width: 170px;
  max-height: 70vh;
  overflow-y: auto;
  padding: 6px;
  border-radius: 12px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.22);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.lang-option {
  text-align: start;
  font-size: 14px;
  font-weight: 600;
  padding: 8px 12px;
  border-radius: 8px;
  color: var(--text);
  background: transparent;
  cursor: pointer;
}
.lang-option:hover { background: var(--surface-2); }
.lang-option.active { background: var(--brand); color: #fff; }
.offline-pill {
  font-size: 11.5px;
  font-weight: 700;
  padding: 3px 11px;
  border-radius: 999px;
  background: rgba(52, 38, 10, .42);
  color: #ffd591;
  cursor: pointer;
}
.offline-pill.syncing {
  background: rgba(7, 57, 59, .42);
  color: #8fe3e8;
}
@media (max-width: 1200px) {
  .topbar { flex-wrap: wrap; }
  .topbar-left { flex-shrink: 1; max-width: 70%; }
  .topbar-shop { flex: 1 1 0; }
  .topbar-right { flex-basis: 100%; }
}
@media (max-width: 700px) {
  .shell { position: relative; }
  .nav-backdrop {
    display: block;
    position: absolute;
    inset: 0;
    z-index: 41;
    background: rgba(0, 0, 0, .42);
  }
  .lang-pill.nav-toggle {
    display: inline-grid;
    flex: none;
    position: relative;
    z-index: 42;
  }
  .topbar { padding: 8px 10px; gap: 8px; }
  .topbar-left { gap: 8px; }
  .brand-identity { gap: 6px; }
  .brand-identity .mobile-brand { display: grid; }
  .brand-wordmark { font-size: 12px; }
  .brand-divider { display: none; }
  .topbar-title { font-size: 15px; }
  .shop-name {
    padding: 5px 12px 6px;
    font-size: 16px;
  }
  .tb-clock, .tb-shift { display: none; }
  .topbar-right { position: relative; justify-content: flex-start; }
  .lang-menu { position: static; }
  .lang-list { inset-inline-start: 0; inset-inline-end: auto; max-width: 100%; }
  .outlet-switch { max-width: 150px; }
}
.content {
  flex: 1;
  min-height: 0;
  display: flex;
  position: relative; /* scopes the open-register overlay to this area */
}
.boot-loading,
.boot-error {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 16px;
}
.boot-card {
  padding: 36px;
  max-width: 460px;
  text-align: center;
}
.boot-card h2 { margin-top: 0; }
.boot-card p { color: var(--text-muted); }
</style>
