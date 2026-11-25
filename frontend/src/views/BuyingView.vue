<!-- Copyright (c) 2026 Esafe (PVT) LTD. SPDX-License-Identifier: AGPL-3.0-only -->
<template>
  <section class="buying-workspace">
    <header class="buying-heading">
      <div><h1>{{ t('Buying') }}</h1><p class="muted">{{ t('Receive stock, track supplier balances and make payments.') }}</p></div>
      <span class="muted">{{ options.company || session.company }}<br />{{ options.currency }}</span>
    </header>
    <p v-if="!allowed" class="card buying-message" role="alert">{{ t('Buying is disabled or your account does not have buying access.') }}</p>
    <template v-else>
      <p v-if="session.offline" class="buying-message buying-error" role="alert">{{ t('Connect to the server to use Buying. Purchases and supplier payments cannot be queued offline.') }}</p>
      <div v-if="error" class="buying-message buying-error" role="alert">{{ error }} <button type="button" class="btn btn-outline" :disabled="busy" @click="refresh">{{ t('Refresh balances') }}</button></div>
      <div v-if="uncertain" class="buying-message buying-error" role="status">{{ t('The posting response was lost. Check this request before entering another purchase or payment.') }} <button type="button" class="btn btn-primary" :disabled="busy || session.offline" @click="retryPosting">{{ t('Check posting result') }}</button></div>
      <p v-if="success" class="buying-message buying-success" role="status">{{ success }}</p>
      <div v-if="loading" class="buying-message" role="status">{{ t('Loading buying setup…') }}</div>
      <div v-else-if="ready" class="buying-layout">
        <aside class="card supplier-directory" :class="{ 'has-selection': supplier && !showSuppliers }">
          <div class="section-heading"><h2>{{ t('Suppliers') }}</h2><button v-if="options.can_create_supplier" class="btn btn-outline" type="button" :disabled="locked" @click="showNewSupplier = !showNewSupplier">{{ t('Add supplier') }}</button></div>
          <form v-if="showNewSupplier" class="supplier-create" @submit.prevent="createSupplier">
            <fieldset :disabled="locked || session.offline">
              <label>{{ t('Supplier name') }}<input v-model="newSupplier.name" required maxlength="140" autocomplete="organization" /></label>
              <label>{{ t('Supplier group') }}<select v-model="newSupplier.group" required><option value="">{{ t('Select group') }}</option><option v-for="group in options.supplier_groups" :key="group">{{ group }}</option></select></label>
              <button class="btn btn-primary" type="submit">{{ t('Save supplier') }}</button>
            </fieldset>
          </form>
          <label class="supplier-search">{{ t('Find supplier') }}<input v-model="supplierQuery" :disabled="locked" :placeholder="t('Name or code')" @input="searchSuppliers" /></label>
          <p v-if="supplierLoading" class="muted" role="status">{{ t('Searching…') }}</p>
          <div class="supplier-list" :aria-label="t('Suppliers')">
            <button v-for="row in suppliers" :key="row.name" type="button" :disabled="locked" class="supplier-row" :class="{ selected: supplier?.name === row.name }" :aria-pressed="supplier?.name === row.name" @click="selectSupplier(row)">
              <strong>{{ row.supplier_name }}</strong><small>{{ row.name }}</small><small>{{ row.supplier_group }}</small>
            </button>
            <p v-if="!supplierLoading && !suppliers.length" class="buying-empty">{{ t('No suppliers found. Add a supplier to record a purchase.') }}</p>
          </div>
          <button v-if="suppliers.length && suppliers.length % 30 === 0" class="btn btn-outline load-suppliers" :disabled="busy || supplierLoading" type="button" @click="loadMoreSuppliers">{{ t('More suppliers') }}</button>
        </aside>

        <main v-if="supplier" class="supplier-workspace">
          <header class="supplier-header">
            <div><h2>{{ supplier.supplier_name }}</h2><span class="muted">{{ supplier.name }}</span></div>
            <button type="button" class="btn btn-outline change-supplier" :disabled="locked" @click="showSuppliers = !showSuppliers">{{ t(showSuppliers ? 'Hide suppliers' : 'Change supplier') }}</button>
            <button type="button" class="btn btn-outline" :disabled="busy || accountLoading || session.offline" @click="loadAccount">{{ t('Refresh') }}</button>
          </header>
          <nav class="buying-tabs" :aria-label="t('Buying sections')">
            <button type="button" :class="{ active: tab === 'account' }" :aria-pressed="tab === 'account'" :disabled="locked" @click="tab = 'account'">{{ t('Supplier account') }}</button>
            <button v-if="options.can_create_invoice" type="button" :class="{ active: tab === 'invoice' }" :aria-pressed="tab === 'invoice'" :disabled="locked" @click="tab = 'invoice'">{{ t('New purchase invoice') }}</button>
          </nav>

          <section v-if="tab === 'account'" class="card account-panel" :aria-busy="accountLoading">
            <p v-if="accountLoading" class="buying-message" role="status">{{ t('Loading supplier account…') }}</p>
            <template v-else-if="account">
              <div class="account-overview">
                <div><span class="muted">{{ t(account.balance < 0 ? 'Supplier credit balance' : 'Supplier balance') }}</span><strong>{{ account.balance == null ? t('Ledger access required') : showMoney(Math.abs(account.balance)) }}</strong><small class="muted">{{ t('Net ledger balance for this company, including credits and advances.') }}</small></div>
                <div><span class="muted">{{ t('Selected unpaid invoices') }}</span><strong>{{ showMoney(selectedTotal) }}</strong><small class="muted">{{ t('{count} selected', { count: selectedInvoices.length }) }}</small></div>
                <button v-if="options.can_pay" class="btn btn-primary" type="button" :disabled="locked || !payableSelection.length || session.offline" @click="openPayment">{{ t('Pay supplier') }}</button>
              </div>
              <p class="muted account-note">{{ t('Invoice balances can differ from the net ledger balance when credits or advances need reconciliation in ERPNext.') }}</p>

              <form v-if="showPayment" class="payment-form" @submit.prevent="paySupplier">
                <fieldset :disabled="locked || session.offline">
                  <div class="section-heading"><h3>{{ t('Supplier payment') }}</h3><button type="button" class="btn btn-outline" @click="showPayment = false">{{ t('Cancel') }}</button></div>
                  <p class="muted">{{ t('Allocate to the selected invoices, oldest first. Partial payments are supported.') }}</p>
                  <div class="form-grid">
                    <label>{{ t('Payment method') }}<select v-model="payment.method" @change="payment.mode = ''"><option>Cash</option><option>Bank Transfer</option><option>Cheque</option></select></label>
                    <label>{{ t('Pay from') }}<select v-model="payment.mode" required><option value="">{{ t('Select payment mode') }}</option><option v-for="mode in compatibleModes" :key="mode.name" :value="mode.name">{{ mode.name }} — {{ mode.account }}</option></select></label>
                    <label>{{ t('Payment amount') }} ({{ options.currency }})<input v-model="payment.amount" inputmode="decimal" required :aria-invalid="payment.amount !== '' && !paymentValid" /></label>
                    <label>{{ t('Payment date') }}<input v-model="payment.date" type="date" required /></label>
                    <label v-if="payment.method !== 'Cash'">{{ t(payment.method === 'Cheque' ? 'Cheque number' : 'Transfer reference') }}<input v-model="payment.reference" maxlength="140" required /></label>
                    <label v-if="payment.method !== 'Cash'">{{ t(payment.method === 'Cheque' ? 'Cheque date' : 'Transfer date') }}<input v-model="payment.referenceDate" type="date" required /></label>
                  </div>
                  <p v-if="!compatibleModes.length" class="buying-error buying-message">{{ t('Configure an enabled payment mode with a company-currency Cash or Bank account in ERPNext.') }}</p>
                  <p v-if="new Set(payableSelection.map((row) => row.credit_to)).size > 1" class="buying-error">{{ t('Select invoices on the same payable account, or make separate payments.') }}</p>
                  <p v-if="payment.method === 'Cheque'" class="muted">{{ t('This records an issued cheque. Clearance is tracked through ERPNext bank reconciliation.') }}</p>
                  <p v-if="payment.method === 'Cash'" class="muted">{{ t('This pays from the company cash account. If you take money from a till drawer, also record that withdrawal using Register → Cash out.') }}</p>
                  <p class="payment-review">{{ t('Payment') }}: <b>{{ showMoney(paymentAmount) }}</b> · {{ t('Remaining on selected invoices') }}: <b>{{ showMoney(Math.max(0, selectedTotal - paymentAmount)) }}</b></p>
                  <button class="btn btn-primary" type="submit" :disabled="!paymentValid">{{ t(busy ? 'Posting…' : 'Submit supplier payment') }}</button>
                </fieldset>
              </form>

              <div class="section-heading"><h3>{{ t('Unpaid purchase invoices') }}</h3><button type="button" class="btn btn-outline" :disabled="busy || !payableInvoices.length" @click="selectAll">{{ t(selectedInvoices.length ? 'Clear selection' : 'Select all') }}</button></div>
              <div v-if="account.open_invoices.length" class="buying-table-wrap">
                <table class="buying-table"><thead><tr><th>{{ t('Pay') }}</th><th>{{ t('Invoice') }}</th><th>{{ t('Date / due date') }}</th><th class="numeric">{{ t('Total') }}</th><th class="numeric">{{ t('Outstanding') }}</th></tr></thead><tbody>
                  <tr v-for="row in account.open_invoices" :key="row.name">
                    <td><input v-model="selectedInvoices" type="checkbox" :value="row.name" :disabled="locked || showPayment || row.currency !== options.currency" :aria-label="t('Select {name}', { name: row.name })" /></td>
                    <td><button class="invoice-link" type="button" :disabled="busy" @click="viewInvoice(row.name)">{{ row.name }}</button><small>{{ row.bill_no || t('No supplier reference') }}</small></td>
                    <td>{{ row.posting_date }}<small>{{ row.due_date }}</small></td><td class="numeric">{{ money(row.grand_total, row.currency) }}</td><td class="numeric"><strong>{{ money(row.outstanding_amount, row.currency) }}</strong></td>
                  </tr>
                </tbody></table>
              </div>
              <p v-else class="buying-empty">{{ t('No unpaid purchase invoices for this supplier.') }}</p>
              <div class="section-heading history-heading"><h3>{{ t('Purchase history') }}</h3><span class="muted">{{ t('50 invoices per page') }}</span></div>
              <div v-if="account.invoices.length" class="buying-table-wrap"><table class="buying-table"><thead><tr><th>{{ t('Invoice') }}</th><th>{{ t('Date') }}</th><th>{{ t('Status') }}</th><th class="numeric">{{ t('Total') }}</th></tr></thead><tbody>
                <tr v-for="row in account.invoices" :key="row.name"><td><button class="invoice-link" type="button" @click="viewInvoice(row.name)">{{ row.name }}</button><small>{{ row.bill_no }}</small></td><td>{{ row.posting_date }}</td><td>{{ t(row.status) }}</td><td class="numeric">{{ money(row.grand_total, row.currency) }}</td></tr>
              </tbody></table></div>
              <p v-else class="buying-empty">{{ t('No purchase invoices yet.') }}</p>
              <div class="history-pagination"><button type="button" class="btn btn-outline" :disabled="busy || historyStart === 0" @click="changePage(-50)">{{ t('Previous') }}</button><button type="button" class="btn btn-outline" :disabled="busy || account.invoices.length < 50" @click="changePage(50)">{{ t('Next') }}</button></div>
              <h3 class="history-heading">{{ t('Recent supplier payments') }}</h3>
              <div v-if="account.payments.length" class="buying-table-wrap"><table class="buying-table"><thead><tr><th>{{ t('Payment') }}</th><th>{{ t('Method / reference') }}</th><th>{{ t('Date') }}</th><th class="numeric">{{ t('Amount') }}</th></tr></thead><tbody>
                <tr v-for="row in account.payments" :key="row.name"><td><a class="invoice-link" :href="documentUrl('payment-entry', row.name)" target="_blank" rel="noopener">{{ row.name }}</a><small>{{ t(row.payment_type) }}</small></td><td>{{ t(row.esafepos_supplier_payment_method || row.mode_of_payment) }}<small v-if="row.esafepos_supplier_payment_method">{{ row.mode_of_payment }}</small><small>{{ row.reference_no }} <span v-if="row.reference_date">({{ row.reference_date }})</span></small><small v-if="row.clearance_date">{{ t('Cleared') }}: {{ row.clearance_date }}</small></td><td>{{ row.posting_date }}</td><td class="numeric">{{ money(row.paid_amount, row.paid_from_account_currency) }}</td></tr>
              </tbody></table></div>
              <p v-else class="buying-empty">{{ t('No supplier payments to display.') }}</p>
            </template>
          </section>

          <form v-else class="purchase-layout" @submit.prevent="createInvoice">
            <fieldset class="card purchase-editor" :disabled="locked || session.offline">
              <h3>{{ t('Purchase invoice') }}</h3>
              <p class="muted">{{ t('Submitting receives these quantities into stock and adds the invoice to the supplier balance.') }}</p>
              <div class="form-grid">
                <label>{{ t('Supplier invoice number') }}<input v-model="draft.billNo" maxlength="140" /></label>
                <label>{{ t('Supplier invoice date') }}<input v-model="draft.billDate" type="date" /></label>
                <label>{{ t('Posting date') }}<input v-model="draft.postingDate" type="date" required /></label>
                <label>{{ t('Due date') }}<input v-model="draft.dueDate" type="date" :min="draft.postingDate" required /></label>
              </div>
              <label class="warehouse-field">{{ t('Receive into warehouse') }}<select v-model="draft.warehouse" required><option value="">{{ t('Select warehouse') }}</option><option v-for="warehouse in options.warehouses" :key="warehouse">{{ warehouse }}</option></select></label>
              <label class="item-search">{{ t('Add items') }}<input v-model="itemQuery" :placeholder="t('Search purchase item name or code')" autocomplete="off" @input="searchItems" /></label>
              <p v-if="itemLoading" class="muted" role="status">{{ t('Searching…') }}</p>
              <div v-if="itemResults.length" class="item-suggestions"><button v-for="item in itemResults" :key="item.name" type="button" @click="addItem(item)"><strong>{{ item.item_name }}</strong><small>{{ item.name }} · {{ item.stock_uom }}</small></button></div>
              <p v-else-if="itemSearched && !itemLoading" class="muted">{{ t('No matching items. Create the item under Items; use ERPNext for serial, batch or asset purchases.') }}</p>
              <div v-for="(line, index) in draft.items" :key="line.item_code" class="purchase-line">
                <div class="purchase-line-name"><strong>{{ line.item_name }}</strong><small>{{ line.item_code }} · {{ line.uom }}</small></div>
                <label>{{ t('Qty') }}<input v-model="line.qty" inputmode="decimal" required :aria-label="t('Quantity for {name}', { name: line.item_name })" /></label>
                <label>{{ t('Unit cost') }}<input v-model="line.rate" inputmode="decimal" required :aria-label="t('Unit cost for {name}', { name: line.item_name })" /></label>
                <strong class="line-amount">{{ showMoney(lineAmount(line)) }}</strong>
                <button class="remove-row" type="button" :aria-label="t('Remove {name}', { name: line.item_name })" @click="draft.items.splice(index, 1)">×</button>
              </div>
              <p v-if="!draft.items.length" class="buying-empty">{{ t('Search and add the products on the supplier invoice.') }}</p>
              <div class="section-heading costs-heading"><h3>{{ t('Additional costs') }}</h3><button type="button" class="btn btn-outline" @click="addCost">{{ t('Add cost') }}</button></div>
              <p class="muted">{{ t('Freight, handling or other supplier-billed costs increase the invoice total and are spread across stock items by value.') }}</p>
              <div v-for="(cost, index) in draft.costs" :key="cost.id" class="cost-row">
                <label>{{ t('Description') }}<input v-model="cost.description" required maxlength="140" :placeholder="t('e.g. Freight')" /></label>
                <label>{{ t('Expense account') }}<select v-model="cost.account" required><option value="">{{ t('Select account') }}</option><option v-for="accountName in options.cost_accounts" :key="accountName">{{ accountName }}</option></select></label>
                <label>{{ t('Amount') }}<input v-model="cost.amount" inputmode="decimal" required /></label>
                <button class="remove-row" type="button" :aria-label="t('Remove cost {number}', { number: index + 1 })" @click="draft.costs.splice(index, 1)">×</button>
              </div>
              <p v-if="draft.costs.length && !options.cost_accounts.length" class="buying-error">{{ t('Create a company-currency expense account for these costs in ERPNext.') }}</p>
              <p class="muted">{{ t('Costs invoiced by another supplier or received later can be allocated with an ERPNext Landed Cost Voucher.') }}</p>
            </fieldset>
            <aside class="card purchase-summary">
              <h3>{{ t('Purchase summary') }}</h3>
              <dl><div><dt>{{ t('Items') }}</dt><dd>{{ showMoney(subtotal) }}</dd></div><div><dt>{{ t('Valuation costs') }}</dt><dd>{{ showMoney(additionalTotal) }}</dd></div><div class="summary-total"><dt>{{ t('Supplier payable') }}</dt><dd>{{ showMoney(subtotal + additionalTotal) }}</dd></div></dl>
              <p class="muted">{{ t('Each item’s receipt valuation includes its share of additional costs. Warehouse valuation follows the item’s ERPNext valuation method.') }}</p>
              <div v-if="draft.costs.length && subtotal > 0" class="valuation-preview"><h4>{{ t('Estimated receipt cost per stock unit') }}</h4><div v-for="line in draft.items" :key="line.item_code"><span>{{ line.item_name }}</span><b>{{ showMoney((parseMoney(line.rate) || 0) * (1 + additionalTotal / subtotal)) }}</b></div></div>
              <p v-if="!invoiceValid && draft.items.length" class="buying-error">{{ t('Check the warehouse, dates, positive quantities, unit costs and additional cost details. Valuation costs require stock items only.') }}</p>
              <button class="btn btn-primary" type="submit" :disabled="!invoiceValid || locked || session.offline">{{ t(busy ? 'Posting…' : 'Submit purchase invoice') }}</button>
              <p class="muted">{{ t('The invoice is submitted immediately. Use Pay supplier to settle it in full or in part.') }}</p>
            </aside>
          </form>

          <section v-if="detail" ref="detailPanel" class="card invoice-detail" tabindex="-1">
            <div class="section-heading"><div><h3>{{ detail.name }}</h3><p class="muted">{{ detail.posting_date }} · {{ detail.bill_no }}</p></div><button class="btn btn-outline" type="button" @click="detail = null">{{ t('Close details') }}</button></div>
            <div class="buying-table-wrap"><table class="buying-table"><thead><tr><th>{{ t('Item') }}</th><th class="numeric">{{ t('Qty') }}</th><th class="numeric">{{ t('Unit cost') }}</th><th class="numeric">{{ t('Receipt valuation / stock unit') }}</th></tr></thead><tbody><tr v-for="(row, index) in detail.items" :key="index"><td>{{ row.item_name }}<small>{{ row.item_code }}</small></td><td class="numeric">{{ row.qty }} {{ row.uom }}</td><td class="numeric">{{ money(row.rate, detail.currency) }}</td><td class="numeric">{{ money(row.valuation_rate, detail.currency) }}</td></tr></tbody></table></div>
            <p v-for="(cost, index) in detail.costs" :key="index" class="detail-cost">{{ cost.description }} <b>{{ money(cost.amount, detail.currency) }}</b> <span class="muted">{{ t(cost.category) }}</span></p>
            <a class="invoice-link" :href="documentUrl('purchase-invoice', detail.name)" target="_blank" rel="noopener">{{ t('Open in ERPNext') }}</a>
          </section>
        </main>
        <div v-else class="card buying-empty choose-supplier">{{ t('Choose a supplier to view their balance or add a purchase invoice.') }}</div>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { call, OfflineError } from '../api'
import { money, parseMoney } from '../format'
import { newId } from '../offline'
import { useSessionStore } from '../stores/session'
import { t } from '../i18n'

const session = useSessionStore()
const allowed = computed(() => session.settings.enable_buying && session.permissions.buying && !session.reportsOnly)
const options = ref({})
const ready = ref(false)
const loading = ref(false)
const busy = ref(false)
const uncertain = ref(null)
const locked = computed(() => busy.value || Boolean(uncertain.value))
const error = ref('')
const success = ref('')
const suppliers = ref([])
const supplier = ref(null)
const supplierQuery = ref('')
const supplierLoading = ref(false)
const showSuppliers = ref(false)
const showNewSupplier = ref(false)
const newSupplier = ref({ name: '', group: '' })
const account = ref(null)
const accountLoading = ref(false)
const historyStart = ref(0)
const selectedInvoices = ref([])
const tab = ref('account')
const detail = ref(null)
const detailPanel = ref(null)
const showPayment = ref(false)
const payment = ref({ method: 'Cash', mode: '', amount: '', date: '', reference: '', referenceDate: '' })
const draft = ref({ items: [], costs: [], warehouse: '', billNo: '', billDate: '', postingDate: '', dueDate: '' })
const itemQuery = ref('')
const itemResults = ref([])
const itemLoading = ref(false)
const itemSearched = ref(false)
let supplierTimer, itemTimer
let contextVersion = 0, accountVersion = 0, supplierVersion = 0, itemVersion = 0
const attempts = new Map()
const supplierDrafts = new Map()
const showMoney = (value) => money(value, options.value.currency || session.currency)
const documentUrl = (doctype, name) => `/app/${doctype}/${encodeURIComponent(name)}`
const positive = (value) => parseMoney(value) !== null && parseMoney(value) > 0
const lineAmount = (line) => (parseMoney(line.qty) || 0) * (parseMoney(line.rate) || 0)
const subtotal = computed(() => draft.value.items.reduce((sum, line) => sum + lineAmount(line), 0))
const additionalTotal = computed(() => draft.value.costs.reduce((sum, cost) => sum + (parseMoney(cost.amount) || 0), 0))
const invoiceValid = computed(() => Boolean(supplier.value && options.value.can_create_invoice && draft.value.items.length && draft.value.warehouse &&
  draft.value.postingDate && draft.value.dueDate >= draft.value.postingDate &&
  draft.value.items.every((line) => positive(line.qty) && positive(line.rate) && (!draft.value.costs.length || line.is_stock_item)) &&
  draft.value.costs.every((cost) => cost.description.trim() && cost.account && positive(cost.amount))))
const payableInvoices = computed(() => (account.value?.open_invoices || []).filter((row) => row.currency === options.value.currency))
const payableSelection = computed(() => payableInvoices.value.filter((row) => selectedInvoices.value.includes(row.name)))
const selectedTotal = computed(() => payableSelection.value.reduce((sum, row) => sum + Number(row.outstanding_amount), 0))
const paymentAmount = computed(() => parseMoney(payment.value.amount) || 0)
const compatibleModes = computed(() => (options.value.payment_modes || []).filter((mode) => mode.type === (payment.value.method === 'Cash' ? 'Cash' : 'Bank')))
const paymentValid = computed(() => options.value.can_pay && positive(payment.value.amount) && paymentAmount.value <= selectedTotal.value + 1e-9 &&
  compatibleModes.value.some((mode) => mode.name === payment.value.mode) && payment.value.date &&
  payableSelection.value.length && new Set(payableSelection.value.map((row) => row.credit_to)).size === 1 &&
  payableSelection.value.every((row) => row.posting_date <= payment.value.date) &&
  (payment.value.method === 'Cash' || (payment.value.reference.trim() && payment.value.referenceDate)))

async function api(method, args = {}) {
  return call(`esafepos.api.buying.${method}`, { pos_profile: session.posProfile, ...args }, { timeout: 60000 })
}

function resetDraft() {
  draft.value = { items: [], costs: [], warehouse: options.value.warehouse || options.value.warehouses?.[0] || '',
    billNo: '', billDate: '', postingDate: options.value.today || '', dueDate: options.value.today || '' }
  itemResults.value = []; itemQuery.value = ''; itemSearched.value = false
}

async function initialize() {
  const version = ++contextVersion
  ++accountVersion; ++supplierVersion; ++itemVersion
  clearTimeout(supplierTimer); clearTimeout(itemTimer)
  supplier.value = null; account.value = null; detail.value = null; options.value = {}
  ready.value = false; loading.value = false; error.value = ''; success.value = ''
  uncertain.value = null
  suppliers.value = []; supplierQuery.value = ''; selectedInvoices.value = []
  supplierDrafts.clear()
  showPayment.value = false; showNewSupplier.value = false; tab.value = 'account'; historyStart.value = 0
  resetDraft()
  if (!allowed.value || !session.posProfile || session.offline) return
  loading.value = true
  try {
    const setup = await api('options')
    if (version !== contextVersion) return
    options.value = setup; resetDraft(); ready.value = true
    await fetchSuppliers()
  } catch (e) { if (version === contextVersion) error.value = e.message }
  finally { if (version === contextVersion) loading.value = false }
}

async function fetchSuppliers(append = false) {
  const version = ++supplierVersion, context = contextVersion
  supplierLoading.value = true
  try {
    const rows = await api('search_suppliers', { search: supplierQuery.value, start: append ? suppliers.value.length : 0 })
    if (version === supplierVersion && context === contextVersion) suppliers.value = append ? [...suppliers.value, ...rows] : rows
  } catch (e) { if (version === supplierVersion && context === contextVersion) error.value = e.message }
  finally { if (version === supplierVersion) supplierLoading.value = false }
}
function searchSuppliers() { ++supplierVersion; clearTimeout(supplierTimer); supplierTimer = setTimeout(() => fetchSuppliers(), 220) }
function loadMoreSuppliers() { fetchSuppliers(true) }
function selectSupplier(row) {
  if (supplier.value?.name === row.name) { showSuppliers.value = false; return }
  if (supplier.value) supplierDrafts.set(supplier.value.name, JSON.parse(JSON.stringify(draft.value)))
  if (supplierDrafts.has(row.name)) draft.value = supplierDrafts.get(row.name)
  else resetDraft()
  supplier.value = row; showSuppliers.value = false; showNewSupplier.value = false
  account.value = null; detail.value = null; showPayment.value = false; selectedInvoices.value = []; historyStart.value = 0
  error.value = ''; success.value = ''; loadAccount()
}
async function loadAccount() {
  if (!supplier.value || session.offline) return
  const version = ++accountVersion, context = contextVersion
  accountLoading.value = true; error.value = ''
  try {
    const result = await api('supplier_account', { supplier: supplier.value.name, start: historyStart.value })
    if (version !== accountVersion || context !== contextVersion) return
    account.value = result
    selectedInvoices.value = selectedInvoices.value.filter((name) => result.open_invoices.some((row) => row.name === name))
  } catch (e) { if (version === accountVersion && context === contextVersion) { account.value = null; error.value = e.message } }
  finally { if (version === accountVersion) accountLoading.value = false }
}
function refresh() { if (!ready.value) initialize(); else loadAccount() }
function changePage(delta) { historyStart.value = Math.max(0, historyStart.value + delta); loadAccount() }
function selectAll() { if (!showPayment.value) selectedInvoices.value = selectedInvoices.value.length ? [] : payableInvoices.value.map((row) => row.name) }
function openPayment() {
  payment.value = { method: 'Cash', mode: options.value.payment_modes.find((mode) => mode.type === 'Cash')?.name || '',
    amount: String(selectedTotal.value), date: options.value.today, reference: '', referenceDate: options.value.today }
  showPayment.value = true
}

async function mutate(kind, method, payload, onSuccess) {
  if (busy.value || session.offline) return
  const context = contextVersion
  const fullPayload = { pos_profile: session.posProfile, ...payload }
  const signature = `${kind}:${JSON.stringify(fullPayload)}`
  if (!attempts.has(signature)) attempts.set(signature, newId())
  busy.value = true; error.value = ''; success.value = ''
  try {
    const result = await api(method, { ...payload, idempotency_key: attempts.get(signature) })
    if (context !== contextVersion) return
    attempts.delete(signature)
    await onSuccess(result)
  } catch (e) {
    if (context === contextVersion) {
      error.value = e.message
      if (e instanceof OfflineError) uncertain.value = { kind, method, payload, onSuccess }
    }
  }
  finally { busy.value = false }
}
async function retryPosting() {
  if (!uncertain.value || busy.value || session.offline) return
  const request = uncertain.value
  uncertain.value = null
  await mutate(request.kind, request.method, request.payload, request.onSuccess)
}
async function createSupplier() {
  await mutate('supplier', 'create_supplier', { supplier_name: newSupplier.value.name, supplier_group: newSupplier.value.group }, async (row) => {
    newSupplier.value = { name: '', group: '' }; selectSupplier(row); await fetchSuppliers()
    success.value = t('Supplier {name} created.', { name: row.supplier_name })
  })
}
async function createInvoice() {
  if (!invoiceValid.value) return
  await mutate('invoice', 'create_invoice', { supplier: supplier.value.name, warehouse: draft.value.warehouse,
    bill_no: draft.value.billNo, bill_date: draft.value.billDate || null, posting_date: draft.value.postingDate, due_date: draft.value.dueDate,
    items: draft.value.items.map((line) => ({ item_code: line.item_code, qty: parseMoney(line.qty), rate: parseMoney(line.rate) })),
    costs: draft.value.costs.map((cost) => ({ description: cost.description, account: cost.account, amount: parseMoney(cost.amount) })) }, async (result) => {
    resetDraft(); tab.value = 'account'; historyStart.value = 0; await loadAccount()
    selectedInvoices.value = [result.name]
    success.value = t('Purchase invoice {name} submitted. Stock and supplier balance updated.', { name: result.name })
  })
}
async function paySupplier() {
  if (!paymentValid.value) return
  await mutate('payment', 'pay_supplier', { supplier: supplier.value.name, invoices: selectedInvoices.value.map((name) => ({ name })),
    amount: paymentAmount.value, payment_method: payment.value.method, mode_of_payment: payment.value.mode, posting_date: payment.value.date,
    reference_no: payment.value.reference || null, reference_date: payment.value.method === 'Cash' ? null : payment.value.referenceDate }, async (result) => {
    showPayment.value = false; selectedInvoices.value = []; await loadAccount()
    success.value = t('Supplier payment {name} submitted.', { name: result.name })
  })
}
function searchItems() {
  const version = ++itemVersion, context = contextVersion
  clearTimeout(itemTimer); itemResults.value = []; itemSearched.value = false
  if (!itemQuery.value.trim()) { itemLoading.value = false; return }
  itemLoading.value = true
  itemTimer = setTimeout(async () => {
    try {
      const rows = await api('search_items', { search: itemQuery.value })
      if (version === itemVersion && context === contextVersion) { itemResults.value = rows; itemSearched.value = true }
    } catch (e) { if (version === itemVersion && context === contextVersion) error.value = e.message }
    finally { if (version === itemVersion) itemLoading.value = false }
  }, 220)
}
function addItem(item) {
  const line = draft.value.items.find((row) => row.item_code === item.name)
  if (line) line.qty = String((parseMoney(line.qty) || 0) + 1)
  else draft.value.items.push({ item_code: item.name, item_name: item.item_name, uom: item.stock_uom,
    is_stock_item: item.is_stock_item, qty: '1', rate: item.last_purchase_rate > 0 ? String(item.last_purchase_rate) : '' })
  ++itemVersion; clearTimeout(itemTimer); itemQuery.value = ''; itemResults.value = []; itemSearched.value = false; itemLoading.value = false
}
function addCost() { draft.value.costs.push({ id: newId(), description: '', account: options.value.cost_accounts?.[0] || '', amount: '' }) }
async function viewInvoice(name) {
  const context = contextVersion, selectedSupplier = supplier.value?.name
  try {
    const result = await api('invoice_details', { name })
    if (context === contextVersion && selectedSupplier === supplier.value?.name) { detail.value = result; await nextTick(); detailPanel.value?.focus() }
  } catch (e) { if (context === contextVersion) error.value = e.message }
}
watch(() => [session.posProfile, allowed.value], initialize, { immediate: true })
watch(() => session.offline, (offline) => { if (!offline) { if (!ready.value) initialize(); else loadAccount() } })
onUnmounted(() => { ++contextVersion; clearTimeout(supplierTimer); clearTimeout(itemTimer) })
</script>

<style scoped>
.buying-workspace { padding: 20px; min-height: 100%; display: flex; flex-direction: column; gap: 16px; }
.buying-heading, .supplier-header, .section-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.buying-heading h1 { font-size: 24px; margin: 0; }
.buying-heading p { margin: 5px 0 0; }
.buying-heading > span { text-align: end; font-size: 12px; line-height: 1.7; }
h2, h3, h4 { margin: 0; } h2 { font-size: 18px; } h3 { font-size: 15px; } h4 { font-size: 12px; }
.buying-layout { display: grid; grid-template-columns: 250px minmax(0, 1fr); gap: 18px; align-items: start; }
.supplier-directory { padding: 14px; position: sticky; top: 12px; }
.supplier-directory h2 { font-size: 15px; }
.supplier-directory .btn { font-size: 12px; padding: 7px 9px; }
.supplier-workspace { min-width: 0; }
.supplier-header { min-height: 50px; }
.supplier-header > div { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.supplier-header span { font-size: 12px; display: block; margin-top: 4px; }
.change-supplier { display: none; }
label { display: flex; flex-direction: column; gap: 6px; font-size: 12px; font-weight: 600; min-width: 0; }
input:not([type='checkbox']), select { width: 100%; min-height: 42px; border: 1px solid var(--border); border-radius: 8px; background: var(--input-bg); color: var(--text); padding: 9px 10px; font: inherit; font-size: 13px; box-sizing: border-box; min-width: 0; }
input[type='checkbox'] { width: 19px; height: 19px; accent-color: var(--brand-dark); }
input:focus-visible, select:focus-visible, button:focus-visible, a:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
button:disabled { opacity: .55; cursor: default; }
fieldset { border: 0; padding: 0; margin: 0; min-width: 0; }
.supplier-search { margin-top: 16px; }
.supplier-list { margin-top: 12px; max-height: 64vh; overflow: auto; }
.supplier-row { display: grid; gap: 4px; width: 100%; text-align: start; padding: 13px 10px; border: 1px solid transparent; border-bottom-color: var(--border-subtle); color: var(--text); background: transparent; border-radius: 8px; cursor: pointer; overflow-wrap: anywhere; }
.supplier-row.selected { background: var(--surface-2); border-color: var(--border); }
small, .muted { color: var(--text-muted); }
.supplier-row small { font-size: 11px; }
.supplier-create { margin-top: 14px; padding-bottom: 14px; border-bottom: 1px solid var(--border); }
.supplier-create fieldset { display: grid; gap: 10px; }
.load-suppliers { width: 100%; margin-top: 10px; }
.buying-tabs { display: flex; gap: 18px; margin: 14px 0; border-bottom: 1px solid var(--border); }
.buying-tabs button { border: 0; border-bottom: 2px solid transparent; padding: 10px 0; background: transparent; font: inherit; font-size: 13px; color: var(--text-muted); cursor: pointer; }
.buying-tabs .active { border-bottom-color: var(--brand); color: var(--brand-dark); font-weight: 700; }
.account-panel { padding: 20px; }
.account-overview { display: flex; align-items: center; gap: 32px; flex-wrap: wrap; }
.account-overview > div { flex: 1; min-width: 180px; display: grid; gap: 6px; }
.account-overview strong { font-size: 26px; font-weight: 700; letter-spacing: -.5px; font-variant-numeric: tabular-nums; }
.account-overview small { max-width: 300px; line-height: 1.5; }
.account-overview span { font-size: 12px; }
.account-note { font-size: 12px; line-height: 1.6; margin: 18px 0 24px; }
.buying-table-wrap { width: 100%; overflow: auto; margin-top: 12px; }
.buying-table { width: 100%; border-collapse: collapse; white-space: nowrap; font-size: 12px; }
.buying-table th { text-align: start; color: var(--text-muted); font-size: 11px; font-weight: 600; background: var(--surface-2); }
.buying-table th, .buying-table td { padding: 12px 10px; border-bottom: 1px solid var(--border-subtle); }
.buying-table small { display: block; margin-top: 4px; font-size: 11px; }
.buying-table .numeric { text-align: end; font-variant-numeric: tabular-nums; }
.invoice-link { border: 0; background: none; color: var(--brand-dark); padding: 0; font: inherit; font-weight: 600; cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
.history-heading { margin-top: 30px; }
.history-heading > span { font-size: 11px; }
.history-pagination { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
.buying-empty { padding: 24px 12px; color: var(--text-muted); text-align: center; line-height: 1.6; font-size: 13px; }
.choose-supplier { padding: 80px 20px; }
.buying-message { padding: 14px 16px; margin: 0; font-size: 13px; line-height: 1.6; }
.buying-message .btn { margin-inline-start: 10px; }
.buying-error { color: var(--red); }
.buying-message.buying-error { border-inline-start: 3px solid var(--red); background: var(--card-bg); }
.buying-success { border-inline-start: 3px solid var(--brand); background: var(--card-bg); }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.payment-form { padding: 18px; margin-bottom: 26px; background: var(--surface-2); border: 1px solid var(--border); border-radius: 10px; }
.payment-form p, .purchase-editor > p, .purchase-summary > p { font-size: 12px; line-height: 1.6; }
.payment-review { margin: 20px 0; }
.purchase-layout { display: grid; grid-template-columns: minmax(0, 1fr) 270px; gap: 16px; align-items: start; }
.purchase-editor, .purchase-summary { padding: 18px; }
.purchase-editor > .form-grid { margin-top: 20px; }
.warehouse-field, .item-search { margin-top: 16px; }
.item-suggestions { display: grid; max-height: 280px; overflow-y: auto; margin-top: 6px; border: 1px solid var(--border); border-radius: 8px; }
.item-suggestions button { display: grid; gap: 4px; text-align: start; background: var(--card-bg); color: var(--text); border: 0; border-bottom: 1px solid var(--border-subtle); padding: 12px; cursor: pointer; }
.purchase-line { display: grid; grid-template-columns: minmax(0, 1fr) 65px 100px 90px 26px; gap: 10px; align-items: end; padding: 14px 0; border-bottom: 1px solid var(--border); }
.purchase-line-name { align-self: center; display: grid; gap: 5px; font-size: 13px; overflow-wrap: anywhere; }
.purchase-line-name small { font-size: 11px; }
.line-amount { font-size: 12px; align-self: center; text-align: end; padding-top: 16px; overflow-wrap: anywhere; }
.remove-row { height: 42px; background: none; border: 0; color: var(--red); font-size: 24px; cursor: pointer; padding: 0; }
.costs-heading { margin-top: 28px; }
.cost-row { display: grid; grid-template-columns: minmax(100px, 1fr) minmax(120px, 1.4fr) 95px 26px; gap: 10px; align-items: end; margin: 16px 0; }
.purchase-summary { position: sticky; top: 12px; }
.purchase-summary dl { margin: 18px 0; font-size: 13px; }
.purchase-summary dl > div { display: flex; justify-content: space-between; gap: 10px; padding: 12px 0; border-bottom: 1px solid var(--border); }
.purchase-summary dd { margin: 0; font-weight: 600; text-align: end; }
.summary-total { font-weight: 700; }
.purchase-summary > button { width: 100%; margin-top: 16px; min-height: 46px; }
.valuation-preview { padding-top: 12px; margin-top: 18px; border-top: 1px solid var(--border); }
.valuation-preview > div { display: flex; justify-content: space-between; gap: 8px; font-size: 11px; padding-top: 12px; }
.valuation-preview span { overflow-wrap: anywhere; }
.valuation-preview b { white-space: nowrap; }
.invoice-detail { padding: 20px; margin-top: 18px; }
.invoice-detail .section-heading p { font-size: 12px; margin-bottom: 0; }
.detail-cost { display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; }
@media (max-width: 1250px) { .purchase-layout { grid-template-columns: minmax(0, 1fr); } .purchase-summary { position: static; } }
@media (max-width: 1000px) { .buying-layout { grid-template-columns: 210px minmax(0, 1fr); gap: 12px; } .account-overview { gap: 18px; } .purchase-line { grid-template-columns: minmax(0, 1fr) 65px 95px 26px; } .line-amount { grid-column: 1 / 4; text-align: start; padding: 0; } .purchase-line .remove-row { grid-column: 4; grid-row: 1 / 3; align-self: center; } .cost-row { grid-template-columns: 1fr 1fr 26px; } .cost-row > label:nth-child(3) { grid-column: 1 / 3; } .cost-row > button { grid-column: 3; grid-row: 1 / 3; align-self: center; } }
@media (max-width: 700px) { .buying-workspace { padding: 12px; gap: 12px; } .buying-heading h1 { font-size: 21px; } .buying-heading p { font-size: 12px; max-width: 250px; } .buying-layout { grid-template-columns: minmax(0, 1fr); } .supplier-directory { position: static; } .supplier-directory.has-selection { display: none; } .supplier-list { max-height: 300px; } .change-supplier { display: inline-flex; } .supplier-header { flex-wrap: wrap; } .supplier-header > div { flex-basis: 100%; } .account-panel, .purchase-editor, .purchase-summary, .invoice-detail { padding: 14px; } .account-overview > div { min-width: 140px; } .account-overview strong { font-size: 23px; } .account-overview > button { width: 100%; } .form-grid { gap: 12px; } .buying-tabs { gap: 16px; } .buying-tabs button { font-size: 12px; } .purchase-line { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) 30px; gap: 12px; } .purchase-line-name { grid-column: 1 / 3; } .purchase-line label { grid-row: 2; } .purchase-line .remove-row { grid-column: 3; grid-row: 1 / 4; } .line-amount { grid-column: 1 / 3; } .cost-row { grid-template-columns: minmax(0, 1fr) 30px; } .cost-row > label, .cost-row > label:nth-child(3) { grid-column: 1; } .cost-row > button { grid-column: 2; grid-row: 1 / 4; } .buying-message .btn { margin: 10px 0 0; } .payment-form { padding: 12px; } }
</style>
