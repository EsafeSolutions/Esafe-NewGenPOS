<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<template>
  <div class="sell">
    <!-- "Per cashier" shift scope: the drawer belongs to whoever opened it. -->
    <div v-if="session.sellBlockedBy" class="shift-owner-banner">
      <Icon name="warning" />
      {{ t('This shift belongs to {name}. Close it and open your own to sell.', { name: session.sellBlockedBy }) }}
    </div>
    <!-- An exchange is open: the goods coming back are already picked, this
         cart is what the customer takes instead. Nothing has posted yet. -->
    <div v-if="cart.exchange" class="exchange-banner">
      <span>
        <Icon name="exchange" />
        {{ t('Exchange against {invoice}, worth {amount}. Add what the customer is taking instead.', {
          invoice: cart.exchange.invoice,
          amount: money(cart.exchange.value),
        }) }}
      </span>
      <button class="btn btn-ghost btn-sm" @click="cart.cancelExchange()">{{ t('Cancel exchange') }}</button>
    </div>
    <section class="catalog">
      <div class="search-row">
        <div class="search-box" data-tour="sell-search">
          <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="2"/><path d="m21 21-4.3-4.3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          <input
            ref="searchInput"
            :value="catalog.search"
            :placeholder="t('Search products or scan a barcode')"
            @input="onSearchInput($event.target.value)"
            @keydown="scanGuard.onKeydown"
            @keydown.enter="onSearchEnter"
          />
          <button v-if="catalog.search" class="btn-ghost clear" @click="catalog.clearSearch()"><Icon name="close" /></button>
        </div>
        <button
          v-if="session.settings.enable_price_checker"
          class="btn btn-outline"
          :title="t('Look up a price without selling')"
          @click="priceCheckOpen = true"
        >
          <Icon name="search" /> {{ t('Price check') }}
        </button>
        <button
          v-if="session.settings.enable_customer_display"
          class="btn btn-outline"
          :title="t('Open the customer-facing display')"
          @click="openCustomerDisplay"
        >
          <Icon name="store" /> {{ t('Display') }}
        </button>
        <button class="btn btn-outline" data-tour="sell-parked" @click="parkedOpen = true">
          {{ t('Retrieve Sale') }}
        </button>
        <button v-if="session.settings.enable_customer_display && !session.offline"
          class="btn btn-outline" :disabled="paymentOpen || cart.submitting" @click="askForContact">
          <Icon name="person" /> {{ t('Ask for contact number') }}
        </button>
      </div>

      <div class="group-bar" data-tour="sell-groups">
        <button
          v-if="session.settings.enable_quick_keys"
          class="chip chip-fav"
          :class="{ active: showFavourites }"
          @click="toggleFavourites"
        >
          <Icon name="star" /> {{ t('Favourites') }}
        </button>
        <button
          v-if="session.bundles.length"
          class="chip chip-bundle"
          :class="{ active: showBundles }"
          @click="showBundles = !showBundles; showFavourites = false"
        >
          <Icon name="gift" /> {{ t('Bundles') }}
        </button>
        <SearchSelect :label="t('Brand')" :model-value="catalog.brand" :options="brandOptions" @change="catalog.setBrand" />
        <SearchSelect :label="t('Item group')" :model-value="catalog.itemGroup" :options="groupOptions" @change="catalog.setGroup" />
        <select v-if="!showBundles && !showFavourites" class="catalog-mode" :aria-label="t('Item view')" v-model="itemMode">
          <option value="list">{{ t('List') }}</option>
          <option value="image">{{ t('Images') }}</option>
          <option value="detail">{{ t('Images and full descriptions') }}</option>
        </select>
      </div>

      <div v-if="showBundles" class="bundle-grid">
        <div v-for="bundle in session.bundles" :key="bundle.name" class="bundle-card card">
          <div class="bundle-badge"><Icon name="gift" /> {{ t('BUNDLE') }}</div>
          <div class="bundle-title">{{ bundle.title }}</div>
          <ul class="bundle-list">
            <li v-for="component in bundle.items" :key="component.item_code">
              {{ component.qty }} × {{ component.item_name }}
            </li>
          </ul>
          <div class="bundle-foot">
            <span class="bundle-price">{{ money(bundle.bundle_price) }}</span>
            <button class="btn btn-primary" @click="addBundleToCart(bundle)">{{ t('Add') }}</button>
          </div>
        </div>
        <div v-if="!session.bundles.length" class="muted">{{ t('No bundles configured') }}</div>
      </div>
      <div v-else-if="showFavourites" class="fav-grid">
        <article
          v-for="fav in favourites"
          :key="fav.item_code"
          class="fav-card card"
        >
          <button class="btn btn-ghost fav-name" @click="inspectItem(fav)">{{ fav.quick_label || fav.item_name }}</button>
          <div class="fav-price">{{ money(fav.price) }}</div>
          <div v-if="fav.is_stock_item" class="muted small">{{ t('{qty} in stock', { qty: fav.actual_qty }) }}</div>
          <button class="btn btn-outline btn-sm" @click="addToCart(fav)">{{ t('Add') }}</button>
        </article>
        <div v-if="!favourites.length" class="muted">{{ favLoading ? t('Loading…') : t('No favourites configured. Add some in Settings → Features.') }}</div>
      </div>
      <ProductGrid v-else :mode="itemMode" data-tour="sell-products" @select="addToCart" @inspect="inspectItem" />
    </section>

    <CartPanel @pay="onPay" @park="parkOpen = true" @hold="openHold" @quotation="createQuotation" @receipt="receipt = $event" />

    <PaymentOverlay v-if="paymentOpen" @close="paymentOpen = false" @done="onSaleDone" />
    <HoldModal v-if="holdOpen" @close="holdOpen = false" @done="onHeld" />
    <ParkedSalesModal v-if="parkedOpen" @close="parkedOpen = false" />
    <ReceiptModal v-if="receipt" :receipt="receipt" @close="receipt = null" @updated="receipt = $event" />
    <SerialModal
      v-if="serialItem"
      :item="serialItem"
      @close="serialItem = null; serialEdits = null"
      @add="onSerialScanned"
    />
    <PasscodeModal
      v-if="passcodeOpen"
      @close="passcodeOpen = false"
      @approved="onDiscountApproved"
    />
    <PriceCheckModal v-if="priceCheckOpen" @close="priceCheckOpen = false" />
    <ItemDetailModal v-if="detailItem" :item="detailItem" :line="detailLine"
      @close="detailItem = null" @save="saveItemDetails" />

    <div v-if="parkOpen" class="modal-backdrop" @click.self="parkOpen = false">
      <div class="modal" style="width: 420px">
        <div class="modal-header">{{ t('Park this sale') }}</div>
        <div class="modal-body">
          <input v-model="parkNote" :placeholder="t('Note (e.g. customer\'s name)')" style="width: 100%" />
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="parkOpen = false">{{ t('Cancel') }}</button>
          <button class="btn btn-primary" @click="parkSale">{{ t('Park Sale') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import Icon from '../components/Icon.vue'
import SearchSelect from '../components/SearchSelect.vue'
import { computed, ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { t } from '../i18n'
import { call } from '../api'
import { customerDisplayUrl, displayContactRequest, displayReceipt, requestDisplayContact } from '../customerDisplay'
import { money } from '../format'
import { useSessionStore } from '../stores/session'
import { scaleBarcodeOptions, useCatalogStore } from '../stores/catalog'
import { searchCatalog } from '../offline'
import { useCartStore } from '../stores/cart'
import ProductGrid from '../components/ProductGrid.vue'
import CartPanel from '../components/CartPanel.vue'
import PaymentOverlay from '../components/PaymentOverlay.vue'
import ParkedSalesModal from '../components/ParkedSalesModal.vue'
import HoldModal from '../components/HoldModal.vue'
import ReceiptModal from '../components/ReceiptModal.vue'
import SerialModal from '../components/SerialModal.vue'
import PasscodeModal from '../components/PasscodeModal.vue'
import PriceCheckModal from '../components/PriceCheckModal.vue'
import ItemDetailModal from '../components/ItemDetailModal.vue'
import { createScanGuard } from '../scanGuard'
import { parseScaleBarcode } from '../barcode'

const router = useRouter()
const session = useSessionStore()
const scanGuard = createScanGuard()
let scanTimer = null

// A barcode scanner fires characters as a fast burst. Add the item the instant
// it's scanned, without waiting for an Enter key (typed searches still need it).
function onSearchInput(value) {
  catalog.setSearch(value)
  clearTimeout(scanTimer)
  if (!value) {
    scanGuard.reset()
    return
  }
  if (value.length >= 3 && scanGuard.isScan(value)) {
    scanTimer = setTimeout(() => {
      if (catalog.search === value) onSearchEnter()
    }, 80)
  }
}
const catalog = useCatalogStore()
const cart = useCartStore()
const brandOptions = computed(() => [{ value:'', label:t('All brands') }, ...catalog.brands.map((brand) => ({ value:brand, label:brand }))])
const groupOptions = computed(() => [{ value:'', label:t('All item groups') }, ...session.itemGroups.map((group) => ({ value:group, label:group }))])

const paymentOpen = ref(false)
const parkedOpen = ref(false)
const parkOpen = ref(false)
const parkNote = ref('')
const receipt = ref(null)
const searchInput = ref(null)
const serialItem = ref(null)
const serialEdits = ref(null)
const priceCheckOpen = ref(false)
const detailItem = ref(null)
const detailLine = computed(() => cart.lines.find((line) => line.item_code === detailItem.value?.item_code && !line.bundle_key && !line.selling_uom))
const modeKey = 'esafepos-item-view'
const savedMode = localStorage.getItem(modeKey)
const itemMode = ref(['list', 'image', 'detail'].includes(savedMode) ? savedMode : 'image')
watch(itemMode, (mode) => localStorage.setItem(modeKey, mode))

const holdOpen = ref(false)
function openHold() {
  if (cart.lines.some((line) => line.selling_uom)) {
    session.notify(t('Use the stock unit for items placed on hold.'), true)
    return
  }
  holdOpen.value = true
}

// Goods put aside for a customer: the cart is cleared by the modal, the hold
// itself lives on the Holds screen from here on.
function onHeld() {
  holdOpen.value = false
  router.push('/holds')
}

onMounted(() => searchInput.value?.focus())

// Ask the server what this basket costs while the cashier is still working it,
// so pressing Pay opens a screen that already knows the payable instead of
// waiting for a round trip (about 190 ms of pure latency on a cloud site).
watch(
  () => [
    cart.lines.length,
    cart.total,
    cart.customer?.name,
    cart.orderDiscountPercent,
    cart.appType,
  ],
  () => cart.prefetchQuote()
)

function hasStock(item, totalQty) {
  // Stock guard: no overselling stock items when negative stock is disallowed
  // (serialized items are covered by per-serial validation instead)
  if (!item.has_serial_no && item.is_stock_item && !session.allowNegativeStock && !session.offline) {
    if (Math.round(totalQty * 10000) / 10000 > (item.actual_qty || 0)) {
      session.notify(t('{item}: only {qty} in stock', { item: item.item_name, qty: item.actual_qty || 0 }), true)
      return false
    }
  }
  return true
}

function cartQty(item) {
  return cart.lines.filter((line) => line.item_code === item.item_code)
    .reduce((sum, line) => sum + line.qty * (line.conversion_factor || 1), 0)
}

function addToCart(item, serial = null, qty = 1) {
  const addQty = Number(qty) || 1
  if (!hasStock(item, cartQty(item) + addQty * (item.conversion_factor || 1))) return false
  if (item.has_serial_no && !serial) {
    // Strict: a serialized item can only enter the cart with a scanned serial
    if (session.offline) {
      session.notify(t('Serialized items cannot be sold offline'), true)
      return
    }
    serialItem.value = item
    return
  }
  if (serial && cart.hasSerial(serial)) {
    session.notify(t('Serial {serial} is already in this sale', { serial }), true)
    return
  }
  return cart.addItem(item, serial, addQty)
}

function onSerialScanned(serial) {
  const item = serialItem.value
  serialItem.value = null
  if (addToCart(item, serial) && serialEdits.value) applyItemEdits(item, serialEdits.value)
  serialEdits.value = null
}

function inspectItem(item) {
  detailItem.value = item
}

function applyItemEdits(item, edits) {
  const index = cart.lines.findIndex((line) => line.item_code === item.item_code && !line.bundle_key &&
    (line.selling_uom || null) === (item.selling_uom || null))
  if (edits.price !== null) cart.setLinePrice(index, edits.price)
  if (edits.discount !== null) cart.setLineDiscount(index, edits.discount, edits.method)
}

function saveItemDetails(edits) {
  const unit = edits.unit
  const item = unit ? {
    ...detailItem.value, selling_uom: unit.uom, conversion_factor: unit.factor,
    whole_qty: unit.whole_qty, price: unit.price, standard_price: unit.price,
  } : detailItem.value
  const existing = unit ? cart.lines.find((line) => line.item_code === item.item_code && line.selling_uom === unit.uom) : detailLine.value
  if (!existing) {
    if (!addToCart(item, null, edits.qty)) {
      if (serialItem.value) {
        serialEdits.value = edits
        detailItem.value = null
      }
      return
    }
  } else if (!item.has_serial_no) {
    if (!hasStock(item, cartQty(item) + (edits.qty - existing.qty) * (existing.conversion_factor || 1))) return
    cart.setQty(cart.lines.indexOf(existing), edits.qty)
  }
  applyItemEdits(item, edits)
  detailItem.value = null
}

const showBundles = ref(false)
const showFavourites = ref(false)
const favourites = ref([])
const favLoading = ref(false)

// The favourites are read once, so their counts follow every sale and return
// the way the grid's tiles do: until 0.56.1 a favourite kept the count it was
// read with, and an item sold out and brought back stayed at 0 there.
// (An action subscription made in setup ends with this screen.)
catalog.$onAction(({ name, args }) => {
  if (!favourites.value.length) return
  if (name === 'applyStock') {
    const levels = args[0] || {}
    for (const fav of favourites.value) {
      if (fav.item_code in levels) fav.actual_qty = levels[fav.item_code]
    }
  } else if (name === 'applyStockDelta') {
    for (const line of args[0] || []) {
      const fav = favourites.value.find((f) => f.item_code === line.item_code)
      if (fav && fav.is_stock_item) fav.actual_qty = (Number(fav.actual_qty) || 0) - (Number(line.qty) || 0)
    }
  }
})

async function toggleFavourites() {
  showFavourites.value = !showFavourites.value
  showBundles.value = false
  if (showFavourites.value && !favourites.value.length) await loadFavourites()
}

function openCustomerDisplay() {
  // Same SPA, hash route, opens (or focuses) a dedicated second-screen window.
  const url = customerDisplayUrl()
  window.open(url, 'esafepos-customer-display', 'width=1024,height=720')
}

function askForContact() {
  if (!cart.lines.length) displayReceipt.value = null
  requestDisplayContact(cart.lines.length ? 'overlay' : 'welcome')
}

async function loadFavourites() {
  favLoading.value = true
  try {
    const res = await call('esafepos.api.catalog.get_quick_keys', {
      pos_profile: session.posProfile,
    })
    favourites.value = res.items || []
  } catch (e) {
    session.notify(e.message, true)
  } finally {
    favLoading.value = false
  }
}

async function addBundleToCart(bundle) {
  try {
    await cart.addBundle(bundle)
    session.notify(t('{title} added to cart', { title: bundle.title }))
  } catch (e) {
    session.notify(e.message, true)
  }
}

async function onSearchEnter() {
  clearTimeout(scanTimer)
  // Was this entry SCANNED (fast burst) or typed? Capture before resetting the
  // guard, it's needed to enforce "scan only" on a serial entered here.
  const wasScan = scanGuard.isScan(catalog.search)
  scanGuard.reset()
  const term = catalog.search.trim()
  if (!term) return
  const options = scaleBarcodeOptions(session.settings)
  const scale = options && parseScaleBarcode(term, options)
  // Scanner fast path: barcodes and serial numbers resolve server-side
  if (!session.offline) {
    try {
      const result = await call('esafepos.api.catalog.resolve_scan', {
        pos_profile: session.posProfile,
        code: term,
        customer_group: cart.customer?.customer_group || null,
        app_type: cart.appType,
      })
      if (result.found) {
        // Scan-only: a serial TYPED into the search box must not bypass the rule
        // (same guard as the serial modal). A scanned serial (burst) is allowed.
        if (result.serial && session.settings.serial_scan_only && !wasScan) {
          session.notify(t('Manual entry is off. Scan the serial with the scanner.'), true)
          catalog.clearSearch()
          return
        }
        addToCart(result.item, result.serial, result.qty || 1)
        catalog.clearSearch()
        return
      }
      // A serial the server knows but cannot sell (already sold on a sale the
      // shift close has not booked yet): say why instead of "not found".
      if (result.message) {
        session.notify(result.message, true)
        catalog.clearSearch()
        return
      }
      if (scale) return
    } catch {
      /* fall back to the grid below */
    }
  }
  const matches = await searchCatalog(term, null, 2, '', options).catch(() => [])
  if (catalog.search.trim() !== term) return
  if (matches.length === 1 || (scale && matches.length)) {
    const item = matches[0]
    const exact = item.barcode === term || item.item_code === term
    addToCart(item, null, scale && !exact ? scale.weight : 1)
    catalog.clearSearch()
  }
}

async function parkSale() {
  try {
    await cart.park(parkNote.value)
    parkOpen.value = false
    parkNote.value = ''
    session.notify(t('Sale parked'))
  } catch (e) {
    session.notify(e.message, true)
  }
}

function onSaleDone(saleReceipt) {
  paymentOpen.value = false
  receipt.value = saleReceipt
}

async function createQuotation() {
  const tab = window.open('about:blank', '_blank')
  if (!tab) {
    session.notify(t('Allow pop-ups to open the quotation.'), true)
    return
  }
  try {
    const quote = await cart.createQuotation()
    tab.location.replace(`/printview?doctype=Quotation&name=${encodeURIComponent(quote.name)}&no_letterhead=0`)
    session.notify(t('Quotation {name} created', { name: quote.name }))
  } catch (e) {
    tab.close()
    session.notify(e.message, true)
  }
}

const passcodeOpen = ref(false)

function onPay() {
  // The server refuses it too (esafepos.api.salespeople.for_sale).
  if (session.settings.salesperson_mode === 'Required' && session.salesPersons.length && !cart.salesPerson) {
    session.notify(t('Pick the salesperson first'), true)
    return
  }
  if (cart.appType && cart.activeApp?.require_order_id && !cart.orderId.trim()) {
    session.notify(t('Enter the {channel} order ID first', { channel: cart.appType }), true)
    return
  }
  if (cart.needsDiscountApproval) {
    passcodeOpen.value = true
    return
  }
  displayContactRequest.value = null
  paymentOpen.value = true
}

function onDiscountApproved(result) {
  // Either a manager passcode or an approved discount-request name clears the
  // over-limit gate; the server re-checks whichever was used.
  if (result.passcode) cart.discountPasscode = result.passcode
  if (result.request) cart.discountRequest = result.request
  passcodeOpen.value = false
  displayContactRequest.value = null
  paymentOpen.value = true
}
</script>

<style scoped>
.shift-owner-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: rgba(226, 48, 48, 0.12);
  color: #c23434;
  font-weight: 700;
  font-size: 13px;
}
.exchange-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  background: var(--brand-soft, rgba(19, 167, 149, 0.1));
  color: var(--brand);
  font-weight: 600;
  font-size: 13px;
}
.exchange-banner .btn-sm { color: inherit; text-decoration: underline; }
.sell {
  flex: 1;
  display: flex;
  min-width: 0;
}
.catalog {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px;
  min-width: 0;
}
.search-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.search-box {
  flex: 1 1 260px;
  min-width: 0;
  position: relative;
  display: flex;
  align-items: center;
}
.search-box svg {
  position: absolute;
  left: 12px;
  width: 18px;
  height: 18px;
  color: var(--text-muted);
}
.search-box input {
  width: 100%;
  padding: 12px 38px 12px 40px;
  font-size: 15px;
  border-radius: 10px;
}
.search-box .clear {
  position: absolute;
  right: 8px;
  padding: 4px 8px;
}
.group-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 12px 0 4px;
  min-height: 36px;
}
.catalog-mode { max-width: 100%; }
.group-scroll {
  display: flex;
  min-width: 0;
  gap: 8px;
  overflow-x: auto;
  flex: 1;
  padding-bottom: 2px;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
}
.group-scroll::-webkit-scrollbar { display: none; }
.chip {
  flex-shrink: 0;
  border: 1px solid var(--border);
  background: var(--card-bg);
  border-radius: 999px;
  padding: 7px 16px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  white-space: nowrap;
  transition: all 0.1s;
}
.chip:hover { border-color: var(--brand); color: var(--brand); }
.chip.active {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
}
.chip-bundle { font-weight: 700; }
.chip-fav { font-weight: 700; }
.chip-fav.active { background: var(--brand); border-color: var(--brand); color: #fff; }
@media (max-width: 1200px) {
  .search-box { flex-basis: 100%; }
  .search-row > .btn { flex: 1 1 auto; }
}
@media (max-width: 900px) {
  .sell { flex-direction: column; overflow-y: auto; }
  .catalog { flex: 0 0 auto; min-height: 320px; max-height: 65vh; max-height: 65dvh; }
}
@media (max-width: 700px) {
  .catalog { padding: 12px; }
  .group-bar { flex-wrap: wrap; }
}
.fav-grid {
  flex: 1;
  overflow-y: auto;
  margin-top: 10px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
  align-content: start;
  padding-bottom: 20px;
}
.fav-card {
  padding: 16px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: start;
  border: 1px solid var(--border);
  transition: border-color 0.1s, transform 0.05s;
}
.fav-card:hover { border-color: var(--brand); }
.fav-card:active { transform: scale(0.98); }
.fav-name { font-weight: 700; font-size: 14px; }
.fav-price { font-weight: 800; font-size: 16px; color: var(--brand-dark); }
.bundle-grid {
  flex: 1;
  overflow-y: auto;
  margin-top: 10px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 12px;
  align-content: start;
  padding-bottom: 20px;
}
.bundle-card {
  padding: 14px 16px;
  border: 1.5px solid rgba(19, 167, 149, 0.35);
  display: flex;
  flex-direction: column;
}
.bundle-badge {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: var(--brand-dark);
}
.bundle-title { font-weight: 700; font-size: 15px; margin: 4px 0 8px; }
.bundle-list {
  margin: 0 0 10px;
  padding-left: 18px;
  font-size: 12.5px;
  color: var(--text-muted);
  flex: 1;
}
.bundle-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.bundle-price { font-weight: 800; font-size: 16px; color: var(--brand-dark); }
</style>
