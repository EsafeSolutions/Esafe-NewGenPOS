<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<template>
  <div class="customers" :class="{ 'detail-selected': selected }">
    <!-- Left: searchable, paginated customer list -->
    <aside class="cust-list">
      <div class="list-head">
        <div class="search-box">
          <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="2"/><path d="m21 21-4.3-4.3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          <input
            :value="search"
            :placeholder="t('Search name, phone, code, email…')"
            :aria-label="t('Search customers')"
            @input="onSearch($event.target.value)"
          />
          <button v-if="search" class="btn-ghost clear" @click="onSearch('')"><Icon name="close" /></button>
        </div>
        <select v-model="group" class="group-select" :aria-label="t('Customer group')" @change="reload">
          <option value="">{{ t('All groups') }}</option>
          <option v-for="g in groups" :key="g" :value="g">{{ g }}</option>
        </select>
        <label v-if="session.settings?.enable_customer_balances" class="customer-filter">
          <span>{{ t('Account balance') }}</span>
          <select v-model="balance" :aria-label="t('Account balance')" @change="reload">
            <option value="">{{ t('All balances') }}</option>
            <option value="owes">{{ t('Still owes') }}</option>
          </select>
        </label>
        <label class="customer-filter">
          <span>{{ t('Customer activity') }}</span>
          <select v-model="activity" :aria-label="t('Customer activity')" @change="reload">
            <option value="">{{ t('All customers') }}</option>
            <option value="new_today">{{ t('New today') }}</option>
            <option value="new_yesterday">{{ t('New yesterday') }}</option>
            <option value="new_week">{{ t('New in the last 7 days') }}</option>
            <option value="new_month">{{ t('New in the last 30 days') }}</option>
            <option value="purchased_today">{{ t('Purchased today') }}</option>
            <option value="purchased_yesterday">{{ t('Purchased yesterday') }}</option>
            <option value="purchased_date">{{ t('Purchased on a date…') }}</option>
          </select>
        </label>
        <label v-if="activity === 'purchased_date'" class="customer-filter">
          <span>{{ t('Purchase date') }}</span>
          <input v-model="activityDate" type="date" :aria-label="t('Purchase date')" @change="reload" />
        </label>
        <label v-if="session.multiCompany" class="customer-filter">
          <span>{{ t('Company') }}</span>
          <select v-model="companyView" :aria-label="t('Company')" @change="changeCompany">
            <option v-for="c in session.companies" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
        <button v-if="group || balance || activity || search" class="btn-ghost reset-filters" @click="resetFilters">{{ t('Clear filters') }}</button>
        <p v-if="balance === 'owes'" class="filter-hint muted small">{{ t('Unpaid account balances in {company}.', { company: companyView || session.company }) }}</p>
      </div>
      <div class="list-body">
        <button
          v-for="c in customers"
          :key="c.name"
          class="cust-row"
          :class="{ active: selected && selected.name === c.name }"
          @click="select(c)"
        >
          <div class="cust-name">{{ c.customer_name }}</div>
          <div class="muted small">
            <span v-if="c.mobile_no">{{ c.mobile_no }}</span>
            <span v-if="c.customer_group"> · {{ c.customer_group }}</span>
          </div>
          <div v-if="balance === 'owes' && c.outstanding != null" class="customer-owed small">{{ t('Still owes') }} {{ money(c.outstanding, listCurrency) }}</div>
        </button>
        <div v-if="loadingList" class="muted center pad">{{ t('Loading…') }}</div>
        <div v-else-if="listError" class="list-error pad" role="alert">
          <p>{{ listError }}</p>
          <button class="btn btn-outline" @click="reload">{{ t('Retry') }}</button>
        </div>
        <div v-else-if="!customers.length" class="muted center pad">{{ activity === 'purchased_date' && !activityDate ? t('Choose a purchase date.') : t('No customers found') }}</div>
        <button v-if="hasMore && !loadingList" class="btn btn-outline load-more" @click="loadMore">
          {{ t('Load more') }}
        </button>
      </div>
    </aside>

    <!-- Right: selected customer's profile + transactions -->
    <section class="cust-detail">
      <button v-if="selected" type="button" class="btn btn-outline mobile-customer-back" @click="clearSelection">
        <span aria-hidden="true">←</span> {{ t('All customers') }}
      </button>
      <div v-if="!selected" class="empty-detail muted">
        <svg viewBox="0 0 24 24" width="46" height="46"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
        <p>{{ t('Select a customer to see their profile and transactions') }}</p>
      </div>
      <div v-else-if="loadingDetail" class="muted center pad">{{ t('Loading…') }}</div>
      <template v-else-if="detail">
        <header class="detail-head">
          <div>
            <h2>{{ detail.customer_name }}</h2>
            <div class="muted">{{ detail.name }}<span v-if="detail.customer_group"> · {{ detail.customer_group }}</span></div>
          </div>
        </header>

        <div class="customer-message-action"><button type="button" class="btn btn-outline" @click="messageOpen = !messageOpen">{{ t(messageOpen ? 'Close message' : 'SMS / WhatsApp') }}</button></div>
        <CustomerMessageComposer v-if="messageOpen" :customer="detail.name" :mobile-number="detail.mobile_no" />

        <div class="profile-grid">
          <div v-if="detail.mobile_no"><span class="lbl">{{ t('Phone') }}</span>{{ detail.mobile_no }}</div>
          <div v-if="detail.email_id"><span class="lbl">{{ t('Email') }}</span>{{ detail.email_id }}</div>
          <div v-if="detail.tax_id"><span class="lbl">{{ t('Tax ID') }}</span>{{ detail.tax_id }}</div>
          <div v-if="detail.customer_type"><span class="lbl">{{ t('Type') }}</span>{{ detail.customer_type }}</div>
          <div v-if="detail.billing_currency && detail.billing_currency !== detail.currency">
            <span class="lbl">{{ t('Buys in') }}</span>{{ detail.billing_currency }}
          </div>
          <div v-if="detail.member_since"><span class="lbl">{{ t('Member since') }}</span>{{ detail.member_since }}</div>
          <div v-if="detail.stats.last_purchase"><span class="lbl">{{ t('Last purchase') }}</span>{{ detail.stats.last_purchase }}</div>
        </div>

        <section class="customer-pricing card">
          <div>
            <h3>{{ t('Customer price list') }}</h3>
            <p class="muted small">{{ t('Applies when this customer is selected at the till. Items without a price use the outlet price. Delivery app prices take priority.') }}</p>
          </div>
          <div v-if="detail.can_edit_price_list" class="pricing-controls">
            <label class="customer-filter">
              <span>{{ t('Selling price list') }}</span>
              <select v-model="priceList" :aria-label="t('Selling price list')" :disabled="loadingPriceLists || savingPriceList || session.offline">
                <option value="">{{ t('Use outlet pricing') }}</option>
                <option v-if="priceList && !priceLists.some(p => p.name === priceList)" :value="priceList" disabled>{{ priceList }}</option>
                <option v-for="p in priceLists" :key="p.name" :value="p.name">{{ p.name }} ({{ p.currency }})</option>
              </select>
            </label>
            <button class="btn btn-primary" :disabled="loadingPriceLists || savingPriceList || session.offline || priceList === (detail.default_price_list || '')" @click="savePriceList">
              {{ savingPriceList ? t('Saving…') : t('Save price list') }}
            </button>
          </div>
          <p v-else class="pricing-current">{{ detail.default_price_list || t('Use outlet pricing') }}</p>
          <p v-if="priceListError" class="pricing-error small" role="alert">{{ priceListError }} <button v-if="!savingPriceList" class="btn-ghost" @click="loadPriceLists(detail)">{{ t('Retry') }}</button></p>
          <p v-if="session.offline && detail.can_edit_price_list" class="muted small">{{ t('Reconnect to change the customer price list.') }}</p>
        </section>

        <div class="stat-cards">
          <div class="stat"><div class="stat-v">{{ detail.stats.sales_count }}</div><div class="stat-l">{{ t('Sales') }}</div></div>
          <div class="stat"><div class="stat-v">{{ money(detail.stats.net_spent, detail.currency) }}</div><div class="stat-l">{{ t('Net spent') }}</div></div>
          <div class="stat"><div class="stat-v">{{ detail.stats.returns_count }}</div><div class="stat-l">{{ t('Returns') }}</div></div>
          <div class="stat"><div class="stat-v">{{ detail.wallet.loyalty_points }}</div><div class="stat-l">{{ t('Loyalty points') }}</div></div>
          <div class="stat"><div class="stat-v">{{ money(detail.wallet.store_credit) }}</div><div class="stat-l">{{ t('Store credit') }}</div></div>
        </div>

        <CustomerSalesProgress
          v-if="session.settings?.enable_customer_sales_progress"
          :customer="detail.name"
          :company="companyView || session.company"
        />

        <!-- Sales on account (0.60.0): what they owe, a payment, their limit. -->
        <CustomerCredit v-if="session.settings?.enable_customer_balances" :customer="detail.name" :company="companyView || session.company" @changed="accountChanged" />

        <div class="txn-head">
          <h3>{{ t('Transactions') }}</h3>
          <div class="txn-filters">
            <select v-model="txnType" @change="reloadTxns">
              <option value="">{{ t('All') }}</option>
              <option value="0">{{ t('Sales') }}</option>
              <option value="1">{{ t('Returns') }}</option>
            </select>
            <input type="date" v-model="dateFrom" :title="t('From')" @change="reloadTxns" />
            <input type="date" v-model="dateTo" :title="t('To')" @change="reloadTxns" />
          </div>
        </div>
        <div class="txn-table-wrap">
        <table class="txn-table">
          <thead>
            <tr>
              <th>{{ t('Invoice') }}</th>
              <th>{{ t('Date') }}</th>
              <th>{{ t('Type') }}</th>
              <th class="right">{{ t('Total') }}</th>
              <th>{{ t('Payment') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="tx in txns" :key="tx.name" class="txn-row" @click="openReceipt(tx)">
              <td>
                <button class="btn-ghost mono txn-invoice" @click.stop="openReceipt(tx)">{{ tx.name }}</button>
                <div v-if="tx.receipt_name || tx.receipt_contact" class="small muted">
                  {{ [tx.receipt_name, tx.receipt_contact].filter(Boolean).join(' · ') }}
                </div>
              </td>
              <td class="muted small">{{ shortTime(tx.posting_date + ' ' + tx.posting_time) }}</td>
              <td>
                <span v-if="tx.is_return" class="badge red">{{ t('Return') }}</span>
                <span v-else-if="tx.is_exchange" class="badge amber">{{ t('Exchange') }}</span>
                <span v-else class="badge">{{ t('Sale') }}</span>
              </td>
              <td class="right">{{ money(tx.grand_total, tx.currency) }}</td>
              <td class="muted small">{{ session.modeLabel(tx.payment_modes) }}</td>
            </tr>
          </tbody>
        </table>
        </div>
        <div v-if="loadingTxns" class="muted center pad">{{ t('Loading…') }}</div>
        <div v-else-if="!txns.length" class="muted center pad">{{ t('No transactions') }}</div>
        <button v-if="txnsMore && !loadingTxns" class="btn btn-outline load-more" @click="loadMoreTxns">
          {{ t('Load more') }}
        </button>
      </template>
    </section>

    <ReceiptModal
      v-if="receipt"
      :receipt="receipt"
      :can-refund="false"
      show-open-in-history
      reprint
      @open-in-history="openInHistory"
      @close="receipt = null"
      @updated="updateReceipt"
    />
  </div>
</template>

<script setup>
import Icon from '../components/Icon.vue'
import ReceiptModal from '../components/ReceiptModal.vue'
import CustomerCredit from '../components/CustomerCredit.vue'
import CustomerSalesProgress from '../components/CustomerSalesProgress.vue'
import CustomerMessageComposer from '../components/CustomerMessageComposer.vue'
import { useRoute, useRouter } from 'vue-router'
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { call } from '../api'
import { useSessionStore } from '../stores/session'
import { useCartStore } from '../stores/cart'
import { putCustomer } from '../offline'
import { money, shortTime } from '../format'
import { t } from '../i18n'

const LIST_LIMIT = 30
const TXN_LIMIT = 25

const session = useSessionStore()

const search = ref('')
const group = ref('')
const balance = ref('')
const activity = ref('')
const activityDate = ref('')
const listCurrency = ref(session.currency)
const listError = ref('')
const groups = ref([])
const customers = ref([])
const hasMore = ref(false)
const listStart = ref(0)
const loadingList = ref(false)
let searchTimer = null
let listRequest = 0
let detailRequest = 0
let txnRequest = 0
const priceList = ref('')
const priceLists = ref([])
const loadingPriceLists = ref(false)
const savingPriceList = ref(false)
const priceListError = ref('')
const cart = useCartStore()

const selected = ref(null)
const detail = ref(null)
const loadingDetail = ref(false)

const txns = ref([])
const txnType = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const txnsMore = ref(false)
const txnStart = ref(0)
const loadingTxns = ref(false)

const receipt = ref(null)
const messageOpen = ref(false)
const customerRoute = useRoute()
watch(() => customerRoute.query.customer, name => { if (name) select({name}) })

onMounted(async () => {
  groups.value = await call('esafepos.api.customers.customer_groups').catch(() => [])
  reload()
  if (customerRoute.query.customer) select({name:customerRoute.query.customer})
})
onBeforeUnmount(() => { clearTimeout(searchTimer); listRequest++; detailRequest++; txnRequest++ })

function onSearch(value) {
  search.value = value
  clearTimeout(searchTimer)
  searchTimer = setTimeout(reload, 300) // debounce, one query per pause, not per keystroke
}

function listFilters(start = 0) {
  return {
    search: search.value || null,
    customer_group: group.value || null,
    company: companyView.value || session.company,
    still_owes: balance.value === 'owes' ? 1 : 0,
    activity: activity.value || null,
    activity_date: activityDate.value || null,
    start,
    limit: LIST_LIMIT,
  }
}

function resetFilters() {
  search.value = ''; group.value = ''; balance.value = ''; activity.value = ''; activityDate.value = ''
  reload()
}

async function reload() {
  clearTimeout(searchTimer)
  listRequest++
  customers.value = []
  hasMore.value = false
  listError.value = ''
  listStart.value = 0
  if (activity.value === 'purchased_date' && !activityDate.value) {
    loadingList.value = false
    return
  }
  await fetchCustomers(0, listRequest)
}

async function fetchCustomers(start, request) {
  loadingList.value = true
  try {
    const res = await call('esafepos.api.customers.search_customers', listFilters(start))
    if (request !== listRequest) return
    customers.value = start ? customers.value.concat(res.items || []) : res.items || []
    listStart.value = start
    hasMore.value = Boolean(res.has_more)
    listCurrency.value = res.currency || session.currency
  } catch (e) {
    if (request === listRequest) listError.value = e.message
  } finally {
    if (request === listRequest) loadingList.value = false
  }
}

async function loadMore() {
  if (loadingList.value) return
  listError.value = ''
  await fetchCustomers(listStart.value + LIST_LIMIT, listRequest)
}

// The company whose figures the profile shows: the till's own by default.
const companyView = ref(session.company || '')

function changeCompany() {
  reload()
  if (selected.value) select(selected.value)
}

function accountChanged() {
  reloadTxns()
  if (balance.value === 'owes') reload()
}

async function select(c) {
  messageOpen.value = false
  const request = ++detailRequest
  txnRequest++
  txns.value = []
  selected.value = c
  detail.value = null
  loadingDetail.value = true
  try {
    const result = await call('esafepos.api.customers.customer_detail', {
      customer: c.name,
      company: companyView.value || session.company,
    })
    if (request !== detailRequest) return
    detail.value = result
    priceList.value = result.default_price_list || ''
    priceLists.value = []
    priceListError.value = ''
    loadPriceLists(result)
  } catch (e) {
    if (request === detailRequest) session.notify(e.message, true)
  } finally {
    if (request === detailRequest) loadingDetail.value = false
  }
  if (request === detailRequest) reloadTxns()
}

async function loadPriceLists(customer) {
  if (!customer.can_edit_price_list || session.offline) return
  const request = detailRequest
  loadingPriceLists.value = true
  priceListError.value = ''
  try {
    const rows = await call('esafepos.api.customers.customer_price_lists', { customer: customer.name, pos_profile: session.posProfile })
    if (request === detailRequest) priceLists.value = rows || []
  } catch (e) {
    if (request === detailRequest) priceListError.value = e.message
  } finally {
    if (request === detailRequest) loadingPriceLists.value = false
  }
}

async function savePriceList() {
  const customer = detail.value
  if (!customer || savingPriceList.value || session.offline) return
  const request = detailRequest
  savingPriceList.value = true
  priceListError.value = ''
  try {
    const saved = await call('esafepos.api.customers.set_customer_price_list', {
      customer: customer.name, pos_profile: session.posProfile, price_list: priceList.value || null,
    })
    const value = saved.default_price_list || null
    const row = customers.value.find(c => c.name === customer.name)
    if (row) Object.assign(row, { default_price_list: value })
    await putCustomer({ ...customer, default_currency: customer.billing_currency, default_price_list: value }).catch(() => {})
    if (cart.customer?.name === customer.name) {
      cart.customer.default_price_list = value
      await cart.reprice()
    }
    if (request === detailRequest) {
      detail.value.default_price_list = value
      priceList.value = value || ''
    }
    session.notify(t('Customer price list saved'))
  } catch (e) {
    if (request === detailRequest) priceListError.value = e.message
    else session.notify(e.message, true)
  } finally {
    savingPriceList.value = false
  }
}

function clearSelection() {
  detailRequest++
  txnRequest++
  selected.value = null
  detail.value = null
  txns.value = []
}

function txnFilters(start) {
  return {
    filters: {
      customer: selected.value.name,
      all_profiles: 1,
      pos_profile: session.posProfile,
      company: companyView.value || session.company,
      is_return: txnType.value || null,
      date_from: dateFrom.value || null,
      date_to: dateTo.value || null,
      start,
      limit: TXN_LIMIT,
    },
  }
}

async function reloadTxns() {
  if (!selected.value) return
  const request = ++txnRequest
  txnStart.value = 0
  loadingTxns.value = true
  try {
    const rows = await call('esafepos.api.sales.search_sales', txnFilters(0))
    if (request !== txnRequest) return
    txns.value = rows || []
    txnsMore.value = (rows || []).length === TXN_LIMIT
  } catch (e) {
    if (request === txnRequest) session.notify(e.message, true)
  } finally {
    if (request === txnRequest) loadingTxns.value = false
  }
}

async function loadMoreTxns() {
  if (!selected.value || loadingTxns.value) return
  const request = txnRequest
  const start = txnStart.value + TXN_LIMIT
  loadingTxns.value = true
  try {
    const rows = await call('esafepos.api.sales.search_sales', txnFilters(start))
    if (request !== txnRequest) return
    txnStart.value = start
    txns.value = txns.value.concat(rows || [])
    txnsMore.value = (rows || []).length === TXN_LIMIT
  } catch (e) {
    if (request === txnRequest) session.notify(e.message, true)
  } finally {
    if (request === txnRequest) loadingTxns.value = false
  }
}

const router = useRouter()

// Refunds happen in History (one money-flow path), jump there with this sale
// already open instead of duplicating the refund flow here.
function openInHistory() {
  const name = receipt.value?.name
  receipt.value = null
  if (name) router.push({ path: '/history', query: { invoice: name } })
}

async function openReceipt(tx) {
  try {
    receipt.value = await call('esafepos.api.sales.get_receipt', { invoice: tx.name })
  } catch (e) {
    session.notify(e.message, true)
  }
}

function updateReceipt(updated) {
  const linkChanged = updated.linked_customer && updated.linked_customer !== receipt.value?.linked_customer
  receipt.value = updated
  const row = txns.value.find((tx) => tx.name === updated.name)
  if (row) Object.assign(row, { receipt_contact: updated.receipt_contact, receipt_name: updated.receipt_name })
  if (linkChanged && selected.value) select(selected.value)
}
</script>

<style scoped>
.customers {
  flex: 1;
  display: flex;
  min-width: 0;
}
.cust-list {
  width: 320px;
  flex-shrink: 0;
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.list-head { padding: 12px; display: flex; flex-direction: column; gap: 8px; }
.search-box { position: relative; display: flex; align-items: center; }
.search-box svg { position: absolute; left: 11px; width: 16px; height: 16px; color: var(--text-muted); }
.search-box input { width: 100%; padding: 9px 32px 9px 34px; border-radius: 9px; }
.search-box .clear { position: absolute; right: 6px; padding: 3px 6px; }
.group-select { width: 100%; }
.customer-message-action { margin: 14px 0; }
.customer-filter { display: flex; flex-direction: column; gap: 5px; min-width: 0; font-size: 12px; color: var(--text-muted); }
.customer-filter select, .customer-filter input { width: 100%; min-width: 0; color: var(--text); }
.reset-filters { align-self: flex-start; font-size: 12px; padding: 3px 0; }
.filter-hint { margin: 0; line-height: 1.5; }
.customer-owed { margin-top: 5px; font-weight: 600; color: var(--red); }
.list-error { color: var(--red); padding-inline: 10px; }
.list-error p { margin-top: 0; }
.customer-pricing { margin: 0 0 18px; padding: 16px; }
.customer-pricing h3 { margin: 0 0 6px; font-size: 15px; }
.customer-pricing p { margin: 0; line-height: 1.5; }
.pricing-controls { display: flex; align-items: flex-end; gap: 10px; margin-top: 12px; }
.pricing-controls label { flex: 1; max-width: 360px; }
.pricing-controls button { flex-shrink: 0; }
.customer-pricing .pricing-current { margin-top: 10px; font-weight: 600; }
.customer-pricing .pricing-error { margin-top: 10px; color: var(--red); }
.list-body { flex: 1; overflow-y: auto; padding: 0 8px 12px; }
.cust-row {
  display: block;
  width: 100%;
  text-align: start;
  padding: 9px 10px;
  border-radius: 9px;
  border: 1px solid transparent;
}
.cust-row:hover { background: var(--hover-bg, rgba(19, 167, 149,0.06)); }
.cust-row.active { background: rgba(19, 167, 149, 0.1); border-color: var(--brand); }
.cust-name { font-weight: 600; }
.cust-detail { flex: 1; overflow-y: auto; padding: 20px 24px; min-width: 0; }
.empty-detail {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  text-align: center;
}
.detail-head h2 { margin: 0 0 2px; }
.detail-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.company-view { max-width: 240px; padding: 6px 10px; font-size: 13px; }
.profile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px 18px;
  margin: 18px 0;
}
.profile-grid .lbl { display: block; font-size: 11px; font-weight: 700; color: var(--text-muted); }
.stat-cards { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 22px; }
.stat {
  flex: 1;
  min-width: 110px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 14px;
}
.stat-v { font-size: 20px; font-weight: 800; }
.stat-l { font-size: 11.5px; color: var(--text-muted); margin-top: 2px; }
.txn-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.txn-head h3 { margin: 0; }
.txn-filters { display: flex; gap: 8px; flex-wrap: wrap; }
.txn-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
.txn-table th {
  text-align: start;
  font-size: 11.5px;
  color: var(--text-muted);
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
}
.txn-row { cursor: pointer; }
.txn-row:hover { background: var(--hover-bg, rgba(19, 167, 149,0.06)); }
.txn-row td { padding: 9px 8px; border-bottom: 1px solid var(--border-subtle); }
.txn-invoice { padding: 0; text-align: start; }
.right { text-align: end; }
.mono { font-family: ui-monospace, monospace; font-size: 12.5px; }
.small { font-size: 12px; }
.center { text-align: center; }
.pad { padding: 22px 0; }
.load-more { width: 100%; margin-top: 12px; }
.mobile-customer-back { display: none; }
.txn-table-wrap { width: 100%; overflow-x: auto; overscroll-behavior-inline: contain; }
.badge {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 9px;
  border-radius: 999px;
  background: var(--border-subtle);
  color: var(--text-muted);
}
.badge.red { background: rgba(226, 48, 48, 0.14); color: var(--red); }
.badge.amber { background: rgba(245, 166, 35, 0.18); color: #9a6a0a; }
html[data-theme='dark'] .badge.red { background: rgba(255, 120, 120, 0.2); color: #ff9b9b; }
html[data-theme='dark'] .badge.amber { background: rgba(245, 190, 90, 0.2); color: #ffd27a; }
@media (max-width: 1024px) {
  .cust-list { width: 260px; }
  .cust-detail { padding: 16px; }
  .stat { min-width: 125px; }
}
@media (max-width: 700px) {
  .customers { flex-direction: column; overflow: hidden; min-height: 0; }
  .cust-list { width: 100%; flex: 1; border-right: 0; }
  .cust-detail { display: none; flex: 1; overflow-y: auto; padding: 14px 12px 24px; }
  .customers.detail-selected .cust-list { display: none; }
  .customers.detail-selected .cust-detail { display: block; }
  .mobile-customer-back { display: inline-flex; align-items: center; gap: 6px; margin: 0 0 12px; min-height: 40px; }
  .detail-head { flex-direction: column; }
  .company-view { width: 100%; max-width: none; min-height: 40px; }
  .profile-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
  .stat-cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .stat { min-width: 0; padding: 10px; }
  .stat-v { font-size: 16px; overflow-wrap: anywhere; }
  .txn-head { align-items: flex-start; flex-direction: column; }
  .txn-filters { width: 100%; }
  .txn-filters select, .txn-filters input { min-width: 0; flex: 1 1 120px; }
  .txn-table { min-width: 600px; }
  .pricing-controls { align-items: stretch; flex-direction: column; }
  .pricing-controls label { max-width: none; }
}
</style>
