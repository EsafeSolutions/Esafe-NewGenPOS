<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<template>
  <section class="invoice-workspace">
    <header class="invoice-heading">
      <div>
        <h1>{{ t('Customer invoice') }}</h1>
        <p class="muted">{{ t('Create a regular ERPNext Sales Invoice. It can be paid later from the customer account.') }}</p>
      </div>
      <span class="invoice-company">{{ session.company }}</span>
    </header>

    <div v-if="!session.settings.enable_regular_invoices" class="card invoice-disabled">
      {{ t('Regular Sales Invoices are turned off in Modules & Features.') }}
    </div>
    <div v-else class="invoice-layout">
      <section class="card invoice-builder">
        <label class="field-label" for="invoice-customer-search">{{ t('Customer') }} *</label>
        <input id="invoice-customer-search" v-model="customerQuery" class="invoice-input" autocomplete="off"
          :placeholder="t('Search customer name, phone or code')" @input="searchCustomers" />
        <div v-if="selectedCustomer" class="selected-customer">
          <span><b>{{ selectedCustomer.customer_name }}</b><small>{{ selectedCustomer.name }}<span v-if="selectedCustomer.mobile_no"> · {{ selectedCustomer.mobile_no }}</span></small></span>
          <button class="btn btn-outline" type="button" @click="clearCustomer">{{ t('Change') }}</button>
        </div>
        <div v-else-if="customerResults.length" class="suggestions" role="listbox" :aria-label="t('Customer results')">
          <button v-for="row in customerResults" :key="row.name" type="button" class="suggestion"
            @click="selectCustomer(row)">
            <b>{{ row.customer_name }}</b><span>{{ row.name }}<template v-if="row.mobile_no"> · {{ row.mobile_no }}</template></span>
          </button>
        </div>

        <template v-if="session.settings.salesperson_mode !== 'Off' && session.salesPersons.length">
          <label class="field-label salesperson-label" for="invoice-salesperson">{{ t('Salesperson') }}<template v-if="session.settings.salesperson_mode === 'Required'"> *</template></label>
          <select id="invoice-salesperson" v-model="salesPerson" class="invoice-input">
            <option value="">{{ t('Select salesperson') }}</option>
            <option v-for="person in session.salesPersons" :key="person.name" :value="person.name">{{ person.sales_person_name || person.name }}</option>
          </select>
        </template>

        <label class="field-label item-label" for="invoice-item-search">{{ t('Add items') }}</label>
        <input id="invoice-item-search" v-model="itemQuery" class="invoice-input" autocomplete="off"
          :placeholder="t('Search item name or code')" @input="searchItems" />
        <div v-if="itemResults.length" class="suggestions item-suggestions" role="listbox" :aria-label="t('Item results')">
          <button v-for="item in itemResults" :key="item.item_code" type="button" class="suggestion item-suggestion"
            @click="addItem(item)">
            <b>{{ item.item_name }}</b><span>{{ item.item_code }} · {{ money(item.price, item.currency || session.currency) }}</span>
          </button>
        </div>

        <div class="invoice-lines-title">
          <h2>{{ t('Invoice items') }}</h2><span class="muted small">{{ invoiceLines.length }} {{ t('items') }}</span>
        </div>
        <div v-if="!invoiceLines.length" class="invoice-empty muted">{{ t('Search and add items to this invoice.') }}</div>
        <div v-else class="invoice-lines">
          <article v-for="line in invoiceLines" :key="line.item_code" class="invoice-line">
            <div class="line-description"><b>{{ line.item_name }}</b><small>{{ line.item_code }} · {{ money(line.price, line.currency || session.currency) }}</small></div>
            <div class="line-actions">
              <button type="button" class="qty-btn" :aria-label="t('Decrease quantity')" @click="adjust(line, -1)">−</button>
              <input v-model.number="line.qty" class="qty-input" type="number" min="0.001" step="0.001" inputmode="decimal" :aria-label="t('Quantity')" />
              <button type="button" class="qty-btn" :aria-label="t('Increase quantity')" @click="adjust(line, 1)">+</button>
              <button type="button" class="remove-line" :aria-label="t('Remove item')" @click="removeItem(line)">×</button>
            </div>
          </article>
        </div>
        <label class="field-label due-label" for="invoice-due-date">{{ t('Due date') }}</label>
        <input id="invoice-due-date" v-model="dueDate" class="invoice-input due-date" type="date" />
        <label class="field-label note-label" for="invoice-note">{{ t('Invoice note') }}</label>
        <textarea id="invoice-note" v-model="note" class="invoice-input invoice-note" rows="2" :placeholder="t('Optional note')" />
      </section>

      <aside class="card invoice-summary">
        <h2>{{ t('Summary') }}</h2>
        <div class="summary-row"><span>{{ t('Customer') }}</span><b>{{ selectedCustomer?.customer_name || t('Not selected') }}</b></div>
        <div class="summary-row"><span>{{ t('Items') }}</span><b>{{ invoiceLines.reduce((n, row) => n + Number(row.qty || 0), 0) }}</b></div>
        <p class="muted small">{{ t('ERPNext applies the configured taxes, terms, and final amounts when the invoice is created.') }}</p>
        <button type="button" class="btn btn-primary create-invoice" :disabled="!canCreate" @click="createInvoice">
          {{ creating ? t('Creating invoice…') : t('Create Sales Invoice') }}
        </button>
        <div class="muted small invoice-hint">{{ t('This creates a submitted receivable. Collect later payments from Customers → Customer account.') }}</div>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed, onUnmounted, ref } from 'vue'
import { call } from '../api'
import { nativeDocument, printStatusMessage, silentPrinting } from '../printing/index.js'
import { money } from '../format'
import { newId } from '../offline'
import { useSessionStore } from '../stores/session'
import { t } from '../i18n'

const session = useSessionStore()
const customerQuery = ref('')
const customerResults = ref([])
const selectedCustomer = ref(null)
const itemQuery = ref('')
const itemResults = ref([])
const invoiceLines = ref([])
const note = ref('')
const dueDate = ref('')
const salesPerson = ref('')
const creating = ref(false)
let customerTimer
let itemTimer
let invoiceAttempt = null

const canCreate = computed(() =>
  session.settings.enable_regular_invoices && !session.offline && !creating.value &&
  Boolean(selectedCustomer.value?.name) && invoiceLines.value.some((line) => Number(line.qty) > 0) &&
  (session.settings.salesperson_mode !== 'Required' || Boolean(salesPerson.value))
)

function searchCustomers() {
  clearTimeout(customerTimer)
  selectedCustomer.value = null
  customerTimer = setTimeout(async () => {
    const query = customerQuery.value.trim()
    if (!query) { customerResults.value = []; return }
    const rows = await call('esafepos.api.customers.search_customers', { search: query, start: 0, limit: 12 }).catch(() => ({ items: [] }))
    if (!selectedCustomer.value) customerResults.value = rows.items || []
  }, 220)
}

function selectCustomer(row) {
  selectedCustomer.value = row
  customerQuery.value = row.customer_name
  customerResults.value = []
}

function clearCustomer() {
  selectedCustomer.value = null
  customerQuery.value = ''
  customerResults.value = []
}

function searchItems() {
  clearTimeout(itemTimer)
  itemTimer = setTimeout(async () => {
    const query = itemQuery.value.trim()
    if (!query || !session.posProfile) { itemResults.value = []; return }
    const res = await call('esafepos.api.catalog.get_items', {
      pos_profile: session.posProfile,
      search: query,
      start: 0,
      limit: 12,
    }).catch(() => ({ items: [] }))
    if (itemQuery.value.trim() === query) itemResults.value = res.items || []
  }, 220)
}

function addItem(item) {
  const existing = invoiceLines.value.find((line) => line.item_code === item.item_code)
  if (existing) existing.qty = Number(existing.qty || 0) + 1
  else invoiceLines.value.push({ item_code: item.item_code, item_name: item.item_name, price: Number(item.price) || 0, qty: 1 })
  itemQuery.value = ''
  itemResults.value = []
}

function adjust(line, delta) {
  const next = Number(line.qty || 0) + delta
  if (next <= 0) removeItem(line)
  else line.qty = Number(next.toFixed(3))
}

function removeItem(line) {
  invoiceLines.value = invoiceLines.value.filter((row) => row.item_code !== line.item_code)
}

async function createInvoice() {
  if (!canCreate.value) return
  const native = silentPrinting(session)
  const tab = native ? null : window.open('about:blank', '_blank')
  if (!native && !tab) {
    session.notify(t('Allow pop-ups to open the invoice.'), true)
    return
  }
  creating.value = true
  try {
    const payload = {
      pos_profile: session.posProfile,
      customer: selectedCustomer.value.name,
      items: invoiceLines.value.map((line) => ({ item_code: line.item_code, qty: Number(line.qty) })),
      note: note.value.trim() || null,
      due_date: dueDate.value || null,
      sales_person: salesPerson.value || null,
    }
    const signature = JSON.stringify(payload)
    if (!invoiceAttempt || invoiceAttempt.signature !== signature) {
      invoiceAttempt = { signature, key: newId() }
    }
    const invoice = await call('esafepos.api.sales.create_customer_invoice', {
      payload: { ...payload, idempotency_key: invoiceAttempt.key },
    })
    invoiceAttempt = null
    if (native) {
      try { session.notify(t(printStatusMessage(await nativeDocument('Sales Invoice', invoice.name)))) }
      catch (error) { session.notify(t('Invoice saved. Printing needs attention: {error}', { error: error.message }), true) }
    } else tab.location.replace(`/printview?doctype=Sales%20Invoice&name=${encodeURIComponent(invoice.name)}&no_letterhead=0`)
    session.notify(t('Sales Invoice {name} created', { name: invoice.name }))
    invoiceLines.value = []
    note.value = ''
    dueDate.value = ''
    salesPerson.value = ''
    clearCustomer()
  } catch (e) {
    tab?.close()
    session.notify(e.message, true)
  } finally {
    creating.value = false
  }
}

onUnmounted(() => { clearTimeout(customerTimer); clearTimeout(itemTimer) })
</script>

<style scoped>
.invoice-workspace { display: flex; flex-direction: column; gap: 16px; min-height: 100%; padding: 18px; }
.invoice-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.invoice-heading h1 { margin: 0; font-size: 23px; }
.invoice-heading p { margin: 5px 0 0; }
.invoice-company { color: var(--text-muted); font-size: 13px; }
.invoice-layout { display: grid; grid-template-columns: minmax(0, 1.7fr) minmax(245px, .8fr); gap: 16px; align-items: start; }
.invoice-builder, .invoice-summary { padding: 18px; }
.invoice-input { width: 100%; min-height: 44px; padding: 10px 12px; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 9px; font: inherit; }
.field-label { display: block; margin: 0 0 6px; font-weight: 700; font-size: 13px; }
.item-label, .note-label, .salesperson-label, .due-label { margin-top: 18px; }
.suggestions { display: grid; max-height: 250px; overflow-y: auto; margin-top: 6px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); }
.suggestion { display: flex; min-height: 48px; flex-direction: column; justify-content: center; gap: 3px; padding: 8px 12px; text-align: left; color: var(--text); background: transparent; border: 0; border-bottom: 1px solid var(--border); cursor: pointer; }
.suggestion:last-child { border-bottom: 0; }
.suggestion span, .line-description small, .selected-customer small { color: var(--text-muted); font-size: 12px; }
.selected-customer { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 8px; padding: 12px; border-radius: 10px; background: var(--surface-muted, var(--bg)); }
.selected-customer span, .line-description { display: grid; gap: 4px; min-width: 0; }
.selected-customer .btn { min-height: 40px; }
.invoice-lines-title { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 20px; }
.invoice-lines-title h2, .invoice-summary h2 { margin: 0 0 10px; font-size: 16px; }
.invoice-empty { padding: 18px 10px; text-align: center; border: 1px dashed var(--border); border-radius: 10px; }
.invoice-lines { display: grid; gap: 8px; }
.invoice-line { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px; border: 1px solid var(--border); border-radius: 10px; }
.line-description { overflow-wrap: anywhere; }
.line-actions { display: flex; align-items: center; gap: 5px; flex: 0 0 auto; }
.qty-btn, .remove-line { width: 40px; height: 40px; border: 1px solid var(--border); border-radius: 9px; color: var(--text); background: var(--surface); font-size: 20px; cursor: pointer; }
.qty-input { width: 65px; height: 40px; text-align: center; color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: 9px; font: inherit; }
.remove-line { color: var(--danger, #c44); }
.invoice-note { resize: vertical; }
.due-date { max-width: 260px; }
.invoice-summary { position: sticky; top: 12px; }
.summary-row { display: flex; justify-content: space-between; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--border); }
.summary-row b { text-align: right; overflow-wrap: anywhere; }
.create-invoice { width: 100%; min-height: 48px; margin-top: 12px; }
.invoice-hint { margin-top: 10px; line-height: 1.45; }
.invoice-disabled { padding: 18px; }
@media (max-width: 900px) { .invoice-layout { grid-template-columns: minmax(0, 1fr) minmax(220px, .7fr); } }
@media (max-width: 700px) {
  .invoice-workspace { padding: 12px; gap: 12px; }
  .invoice-layout { grid-template-columns: minmax(0, 1fr); }
  .invoice-summary { position: static; }
  .invoice-builder, .invoice-summary { padding: 14px; }
  .invoice-line { align-items: flex-start; flex-direction: column; }
  .line-actions { width: 100%; }
  .qty-input { flex: 1; }
  .invoice-heading h1 { font-size: 20px; }
}
</style>
