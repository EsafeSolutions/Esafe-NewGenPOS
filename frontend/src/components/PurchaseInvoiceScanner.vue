<template>
  <section class="card invoice-scanner" :aria-label="t('Scan purchase invoice')">
    <header class="scan-header"><div><h2>{{ t(review ? 'Review detected invoice' : 'Scan a supplier invoice') }}</h2><p>{{ t('Choose a photo or PDF. Check the details, then fill a purchase draft.') }}</p></div><button type="button" class="btn btn-outline" @click="emit('close')">{{ t('Close scanner') }}</button></header>
    <ol class="scan-steps" :aria-label="t('Scanning steps')"><li :class="{ current: !review }">{{ t('1. Choose invoice') }}</li><li :class="{ current: review }">{{ t('2. Check details and products') }}</li><li>{{ t('3. Fill purchase draft') }}</li></ol>
    <p v-if="error" class="scan-error" role="alert">{{ error }}</p>
    <p v-if="loading" role="status">{{ t('Checking invoice scanning setup…') }}</p>
    <template v-else-if="!status.enabled || !status.configured">
      <div class="scan-setup"><h3>{{ t('Connect Gemini to scan invoices') }}</h3><p>{{ t(status.migrated === false ? 'Run the site migration first, then save a Gemini API key and enable invoice scanning.' : 'Save a Gemini API key and turn on invoice scanning. Manual purchase entry is always available.') }}</p><button v-if="status.can_configure && status.migrated !== false" type="button" class="btn btn-primary" @click="showConfig = !showConfig">{{ t('Set up invoice scanning') }}</button><button type="button" class="btn btn-outline" @click="loadStatus">{{ t('Check setup again') }}</button></div>
      <PurchaseOcrSettings v-if="showConfig" @saved="loadStatus" />
    </template>
    <template v-else>
      <div class="scan-upload">
        <label class="file-picker">{{ t('Invoice photo or PDF') }}<input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp,application/pdf" :disabled="scanning || disabled" @change="chooseFile" /></label>
        <div v-if="file" class="source-file"><img v-if="preview && file.type.startsWith('image/')" :src="preview" :alt="t('Selected supplier invoice')" /><div><b>{{ file.name }}</b><small>{{ (file.size / 1024).toFixed(0) }} KB</small><a :href="preview" target="_blank" rel="noopener">{{ t('Open original invoice') }}</a></div></div>
        <p>{{ t('JPG, PNG, WebP or PDF, up to 8 MB. Use a clear, complete invoice. Selecting Read invoice sends this document to Google Gemini.') }}</p>
        <button type="button" class="btn btn-primary" :disabled="!file || scanning || disabled" @click="scan">{{ t(scanning ? 'Reading invoice…' : 'Read invoice') }}</button>
        <p v-if="scanning" class="scan-progress" role="status">{{ t('Reading supplier, dates, products and totals. This can take about a minute. You can close the scanner without posting anything.') }}</p>
      </div>
      <form v-if="review" class="scan-review" @submit.prevent="apply">
        <fieldset :disabled="scanning || disabled">
          <div class="scan-heading"><h3>{{ t('Invoice details') }}</h3><span>{{ t('{count} detected rows', { count: review.items.length }) }}</span></div>
          <div v-if="review.warnings.length" class="scan-notes" role="status"><strong>{{ t('Check these details') }}</strong><ul><li v-for="(warning, index) in review.warnings" :key="index">{{ warning }}</li></ul></div>
          <div class="scan-grid">
            <div class="supplier-match">
              <label>{{ t('Supplier on invoice') }}<input :value="review.supplier_name || t('Not detected')" readonly /></label>
              <label>{{ t('Use supplier') }}<select v-model="supplierId" required><option value="">{{ t('Choose matching supplier') }}</option><option v-for="row in supplierOptions" :key="row.name" :value="row.name">{{ row.supplier_name }}</option></select></label>
              <label>{{ t('Find another supplier') }}<input v-model="supplierQuery" :placeholder="t('Search supplier name')" @input="searchSupplier" /></label>
              <button v-if="canCreateSupplier" type="button" class="scan-link" @click="emit('need-supplier', review.supplier_name)">{{ t('Add a new supplier') }}</button>
            </div>
            <div class="scan-grid scan-metadata">
              <label>{{ t('Detected invoice number') }}<input v-model="review.invoice_number" maxlength="140" /></label>
              <label>{{ t('Detected invoice date') }}<input v-model="review.invoice_date" type="date" /></label>
              <label>{{ t('Detected due date') }}<input v-model="review.due_date" type="date" /></label>
              <label>{{ t('Invoice currency') }}<select v-model="review.currency" required><option value="">{{ t('Choose currency') }}</option><option :value="currency">{{ currency }}</option><option v-if="originalCurrency && originalCurrency !== currency" :value="originalCurrency">{{ originalCurrency }}</option></select></label>
            </div>
          </div>
          <p v-if="duplicateChecking" role="status">{{ t('Checking the supplier invoice reference…') }}</p>
          <button v-if="duplicateFailed" type="button" class="btn btn-outline" @click="searchDuplicates">{{ t('Retry invoice reference check') }}</button>
          <p v-if="originalCurrency && originalCurrency !== currency" class="scan-error">{{ t('The detected invoice uses another currency. Enter this purchase through ERPNext; the simple POS form uses company currency.') }}</p>
          <div v-if="review.duplicate_invoices.length" class="scan-error"><b>{{ t('A matching invoice already exists. Review it before entering another purchase.') }}</b><a v-for="invoice in review.duplicate_invoices" :key="invoice.name" :href="`/app/purchase-invoice/${encodeURIComponent(invoice.name)}`" target="_blank" rel="noopener">{{ invoice.name }}</a></div>

          <div class="scan-heading"><h3>{{ t('Match products and check quantities') }}</h3><span>{{ t('{count} need attention', { count: unmatchedCount }) }}</span></div>
          <p class="scan-help">{{ t('Match every row to an existing product. Quantities and unit costs must be in that product’s stock unit; pack sizes are never converted automatically.') }}</p>
          <article v-for="(row, index) in review.items" :key="index" class="scan-item" :class="{ 'needs-review': !rowValid(row) }">
            <div class="detected-item"><strong>{{ index + 1 }}. {{ row.description || row.item_code || t('Unreadable product') }}</strong><small>{{ t('Printed unit') }}: {{ row.unit || t('Not detected') }}<span v-if="row.amount != null"> · {{ t('Printed line total') }}: {{ money(row.amount, review.currency || currency) }}</span></small></div>
            <div class="match-product">
              <label>{{ t('Match product {number}', { number: index + 1 }) }}<select v-model="row.selected" required @change="confirmUnit(row)"><option value="">{{ t('Choose product') }}</option><option v-for="item in row.candidates" :key="item.name" :value="item.name">{{ item.item_name }} — {{ item.name }} ({{ item.stock_uom }})</option></select></label>
              <label>{{ t('Search product {number}', { number: index + 1 }) }}<input v-model="row.query" :placeholder="t('Search to find another product')" @input="searchProduct(row, index)" /></label>
            </div>
            <div class="scan-quantities"><label>{{ t('Quantity') }}<input v-model="row.qty" inputmode="decimal" required :aria-label="t('Detected quantity {number}', { number: index + 1 })" /></label><label>{{ t('Unit cost') }}<input v-model="row.rate" inputmode="decimal" required :aria-label="t('Detected unit cost {number}', { number: index + 1 })" /></label><b>{{ money(rowTotal(row), currency) }}</b></div>
            <label v-if="selectedItem(row) && !sameUnit(row)" class="scan-checkbox unit-confirm"><input v-model="row.unitConfirmed" type="checkbox" />{{ t('I checked the quantity and cost are per {unit}, not per printed pack.', { unit: selectedItem(row).stock_uom }) }}</label>
          </article>

          <h3 class="scan-cost-title">{{ t('Detected additional costs and tax') }}</h3>
          <p v-if="review.costs.some(cost => cost.kind === 'tax') && !taxAccounts.length" class="scan-error">{{ t('A tax charge was detected. Configure a company-currency Tax account in ERPNext before importing this invoice.') }}</p>
          <p v-if="review.costs.some(cost => cost.kind === 'valuation') && !costAccounts.length" class="scan-error">{{ t('Configure a company-currency expense account for the detected valuation costs.') }}</p>
          <div v-for="(cost, index) in review.costs" :key="index" class="scan-cost">
            <label>{{ t(cost.kind === 'tax' ? 'Tax description' : 'Cost description') }}<input v-model="cost.description" required /></label>
            <label>{{ t(cost.kind === 'tax' ? 'Tax account' : 'Valuation expense account') }}<select v-model="cost.account" required><option value="">{{ t('Choose account') }}</option><option v-for="name in (cost.kind === 'tax' ? taxAccounts : costAccounts)" :key="name">{{ name }}</option></select></label>
            <label>{{ t('Detected charge {number}', { number: index + 1 }) }}<input v-model="cost.amount" inputmode="decimal" required /></label>
          </div>
          <p v-if="!review.costs.length" class="scan-help">{{ t('No additional costs were detected. You can add them in the purchase draft.') }}</p>
          <p v-if="review.discount_amount > 0" class="scan-error">{{ t('An invoice-level discount was detected. Use ERPNext for this invoice so the discount and stock valuation are allocated correctly.') }}</p>
          <div class="scan-totals"><label>{{ t('Invoice total on document') }}<input v-model="review.printedTotal" inputmode="decimal" /></label><div><span>{{ t('Total from checked rows') }}</span><strong>{{ money(estimate, currency) }}</strong></div><div :class="{ 'scan-error': !totalMatches }"><span>{{ t('Difference') }}</span><strong>{{ printedTotal == null ? t('Check original total') : money(estimate - printedTotal, currency) }}</strong></div></div>
          <p v-if="!totalMatches" class="scan-error">{{ t('The totals do not match. Check quantities, unit costs, missing rows, taxes and discounts against the original invoice.') }}</p>
          <label class="scan-checkbox scan-ack"><input v-model="reviewed" type="checkbox" />{{ t('I checked the supplier, dates, products, units and totals against the original invoice.') }}</label>
          <div class="scan-apply"><p>{{ t('This fills a draft. Review it once more before submitting the purchase invoice.') }}</p><button type="submit" class="btn btn-primary" :disabled="!canApply">{{ t('Fill purchase draft') }}</button></div>
        </fieldset>
      </form>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { call } from '../api'
import { money, parseMoney } from '../format'
import { t } from '../i18n'
import PurchaseOcrSettings from './PurchaseOcrSettings.vue'
const props = defineProps({ posProfile: String, currency: String, supplier: Object, costAccounts: { type: Array, default: () => [] }, taxAccounts: { type: Array, default: () => [] }, canCreateSupplier: Boolean, disabled: Boolean })
const emit = defineEmits(['close', 'apply', 'need-supplier'])
const status = ref({}), loading = ref(true), showConfig = ref(false), scanning = ref(false), error = ref('')
const file = ref(null), preview = ref(''), review = ref(null), reviewed = ref(false), originalCurrency = ref('')
const supplierId = ref(''), supplierQuery = ref(''), extraSuppliers = ref([]), fileInput = ref(null)
let version = 0, supplierVersion = 0, supplierTimer
const itemTimers = new Map(), itemVersions = new Map()
let duplicateVersion = 0
const duplicateChecking = ref(false), duplicateFailed = ref(false)
const supplierOptions = computed(() => [...new Map([...(props.supplier ? [props.supplier] : []), ...(review.value?.suppliers || []), ...extraSuppliers.value].map(row => [row.name, row])).values()])
const selectedItem = (row) => row.candidates.find(item => item.name === row.selected)
const normalized = (value) => String(value || '').trim().toLocaleLowerCase()
const sameUnit = (row) => Boolean(row.unit && normalized(row.unit) === normalized(selectedItem(row)?.stock_uom))
const validNumber = (value) => parseMoney(value) != null && parseMoney(value) > 0
const rowValid = (row) => selectedItem(row) && validNumber(row.qty) && validNumber(row.rate) && (sameUnit(row) || row.unitConfirmed)
const rowTotal = (row) => (parseMoney(row.qty) || 0) * (parseMoney(row.rate) || 0)
const unmatchedCount = computed(() => review.value?.items.filter(row => !rowValid(row)).length || 0)
const estimate = computed(() => review.value ? review.value.items.reduce((sum, row) => sum + rowTotal(row), 0) + review.value.costs.reduce((sum, row) => sum + (parseMoney(row.amount) || 0), 0) : 0)
const printedTotal = computed(() => parseMoney(review.value?.printedTotal))
const totalMatches = computed(() => printedTotal.value == null ? review.value?.printedTotal === '' : Math.abs(estimate.value - printedTotal.value) <= .02)
const canApply = computed(() => Boolean(review.value && reviewed.value && !duplicateChecking.value && !duplicateFailed.value && supplierOptions.value.some(row => row.name === supplierId.value) &&
  !unmatchedCount.value && review.value.currency === props.currency && (!originalCurrency.value || originalCurrency.value === props.currency) &&
  !(review.value.discount_amount > 0) && !review.value.duplicate_invoices.length && totalMatches.value &&
  review.value.costs.every(cost => cost.description.trim() && validNumber(cost.amount) && (cost.kind === 'tax' ? props.taxAccounts : props.costAccounts).includes(cost.account))))

async function loadStatus() {
  loading.value = true; error.value = ''
  try { status.value = await call('esafepos.api.purchase_ocr.scan_status', { pos_profile: props.posProfile }) }
  catch (e) { error.value = e.message }
  finally { loading.value = false }
}
function chooseFile(event) {
  ++version; review.value = null; reviewed.value = false; error.value = ''
  if (preview.value) URL.revokeObjectURL(preview.value)
  preview.value = ''; file.value = null
  const selected = event.target.files?.[0]
  if (!selected) return
  if (!['image/jpeg', 'image/png', 'image/webp', 'application/pdf'].includes(selected.type) || selected.size > (status.value.max_bytes || 8388608) || !selected.size) {
    error.value = t('Choose a JPG, PNG, WebP or PDF invoice up to 8 MB.'); event.target.value = ''; return
  }
  file.value = selected; preview.value = URL.createObjectURL(selected)
}
function fileData(selected) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1])
    reader.onerror = () => reject(new Error(t('This file could not be opened. Choose it again.')))
    reader.readAsDataURL(selected)
  })
}
async function scan() {
  if (!file.value || scanning.value || props.disabled) return
  const current = ++version
  scanning.value = true; error.value = ''; review.value = null; reviewed.value = false
  try {
    const data = await fileData(file.value)
    if (current !== version) return
    const result = await call('esafepos.api.purchase_ocr.scan_invoice', { pos_profile: props.posProfile, file_data: data, mime_type: file.value.type, file_name: file.value.name }, { timeout: 90000 })
    if (current !== version) return
    originalCurrency.value = result.currency
    review.value = { ...result, duplicate_invoices: result.duplicate_invoices || [], printedTotal: result.total == null ? '' : String(result.total),
      items: result.items.map(row => ({ ...row, candidates: row.candidates || [], selected: row.matched_item || '', qty: row.quantity == null ? '' : String(row.quantity), rate: row.unit_price == null ? '' : String(row.unit_price), query: '', unitConfirmed: false })),
      costs: [...result.additional_costs.map(cost => ({ ...cost, kind: 'valuation', account: '', amount: cost.amount == null ? '' : String(cost.amount) })),
        ...(result.tax_amount > 0 ? [{ description: t('Invoice tax'), kind: 'tax', account: '', amount: String(result.tax_amount) }] : [])] }
    supplierId.value = result.matched_supplier || props.supplier?.name || ''
    if (props.supplier && result.matched_supplier && props.supplier.name !== result.matched_supplier) review.value.warnings.push(t('The scanned supplier differs from the supplier currently open. Check the supplier selection.'))
    await searchDuplicates()
  } catch (e) { if (current === version) error.value = e.message }
  finally { if (current === version) scanning.value = false }
}
function confirmUnit(row) { row.unitConfirmed = false; reviewed.value = false }
function searchProduct(row, index) {
  clearTimeout(itemTimers.get(index)); const current = (itemVersions.get(index) || 0) + 1; itemVersions.set(index, current)
  if (!row.query.trim()) return
  itemTimers.set(index, setTimeout(async () => {
    try {
      const items = await call('esafepos.api.buying.search_items', { pos_profile: props.posProfile, search: row.query })
      if (itemVersions.get(index) === current) row.candidates = [...new Map([...row.candidates.filter(item => item.name === row.selected), ...items].map(item => [item.name, item])).values()]
    } catch (e) { error.value = e.message }
  }, 220))
}
function searchSupplier() {
  clearTimeout(supplierTimer); const current = ++supplierVersion
  supplierTimer = setTimeout(async () => {
    try { const rows = await call('esafepos.api.buying.search_suppliers', { pos_profile: props.posProfile, search: supplierQuery.value }); if (current === supplierVersion) extraSuppliers.value = rows }
    catch (e) { error.value = e.message }
  }, 220)
}
async function searchDuplicates() {
  const current = ++duplicateVersion
  duplicateFailed.value = false
  if (!review.value || !supplierId.value || !review.value.invoice_number) { if (review.value) review.value.duplicate_invoices = []; duplicateChecking.value = false; return }
  duplicateChecking.value = true
  try {
    const result = await call('esafepos.api.buying.check_invoice_reference', { pos_profile: props.posProfile, supplier: supplierId.value, bill_no: review.value.invoice_number })
    if (review.value && current === duplicateVersion) review.value.duplicate_invoices = result
  } catch (e) { if (current === duplicateVersion) { error.value = e.message; duplicateFailed.value = true } }
  finally { if (current === duplicateVersion) duplicateChecking.value = false }
}
function apply() {
  if (!canApply.value) return
  emit('apply', { supplier: supplierOptions.value.find(row => row.name === supplierId.value), billNo: review.value.invoice_number,
    billDate: review.value.invoice_date, dueDate: review.value.due_date,
    items: review.value.items.map(row => ({ item_code: row.selected, item_name: selectedItem(row).item_name, uom: selectedItem(row).stock_uom, is_stock_item: selectedItem(row).is_stock_item, qty: String(parseMoney(row.qty)), rate: String(parseMoney(row.rate)) })),
    costs: review.value.costs.map(cost => ({ ...cost, amount: String(parseMoney(cost.amount)) })) })
}
watch(supplierId, () => { reviewed.value = false; searchDuplicates() })
watch(() => review.value?.invoice_number, () => { reviewed.value = false; searchDuplicates() })
watch(() => review.value && JSON.stringify({ supplier: supplierId.value, number: review.value.invoice_number, date: review.value.invoice_date,
  due: review.value.due_date, currency: review.value.currency, total: review.value.printedTotal,
  items: review.value.items.map(row => [row.selected, row.qty, row.rate, row.unitConfirmed]),
  costs: review.value.costs.map(cost => [cost.description, cost.account, cost.amount]) }), () => { reviewed.value = false })
watch(() => props.supplier, value => { if (value && review.value) supplierId.value = value.name })
onMounted(loadStatus)
onUnmounted(() => { ++version; ++supplierVersion; clearTimeout(supplierTimer); itemTimers.forEach(clearTimeout); itemVersions.clear(); if (preview.value) URL.revokeObjectURL(preview.value) })
</script>

<style scoped>
.invoice-scanner { padding: 22px; min-width: 0; }
.scan-header, .scan-heading, .scan-apply { display: flex; justify-content: space-between; align-items: center; gap: 14px; }
.scan-header h2 { font-size: 19px; margin: 0; } h3 { font-size: 15px; margin: 0; }
.invoice-scanner p { color: var(--text-muted); font-size: 12px; line-height: 1.6; }
.scan-steps { display: flex; gap: 24px; list-style: none; margin: 20px 0; padding: 14px 0; border-block: 1px solid var(--border); font-size: 12px; color: var(--text-muted); }
.scan-steps .current { color: var(--brand-dark); font-weight: 700; }
.scan-upload { max-width: 650px; }
.invoice-scanner label { display: grid; gap: 7px; font-size: 12px; font-weight: 600; min-width: 0; }
.invoice-scanner input:not([type='checkbox']), .invoice-scanner select { width: 100%; min-width: 0; min-height: 43px; padding: 10px; font: inherit; color: var(--text); background: var(--input-bg); border: 1px solid var(--border); border-radius: 8px; box-sizing: border-box; }
.invoice-scanner input:focus-visible, .invoice-scanner select:focus-visible, .invoice-scanner button:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.invoice-scanner fieldset { margin: 0; padding: 0; border: 0; min-width: 0; }
.source-file { display: flex; align-items: center; gap: 16px; padding: 15px 0; }
.source-file img { width: 74px; height: 90px; object-fit: contain; background: var(--surface-2); border: 1px solid var(--border); }
.source-file > div { display: grid; gap: 5px; font-size: 12px; min-width: 0; overflow-wrap: anywhere; }
.source-file a, .scan-error a, .scan-link { color: var(--brand-dark); font-size: 12px; text-underline-offset: 3px; }
.scan-error a { display: block; padding-top: 6px; }
.scan-link { border: 0; background: transparent; text-decoration: underline; text-align: start; padding: 0; cursor: pointer; }
.scan-setup { padding: 20px 0; }.scan-setup button { margin-inline-end: 10px; margin-bottom: 10px; }
.scan-review { border-top: 1px solid var(--border); margin-top: 24px; padding-top: 24px; }
.scan-heading { margin: 18px 0; }.scan-heading span { font-size: 12px; color: var(--text-muted); }
.scan-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }.supplier-match { display: grid; gap: 12px; }
.scan-metadata { align-content: start; }
.scan-notes, .scan-error { padding: 12px 14px; border-inline-start: 3px solid var(--amber); background: var(--surface-2); margin: 14px 0; font-size: 12px; line-height: 1.6; }
.invoice-scanner .scan-error { color: var(--red); border-color: var(--red); }.scan-notes ul { margin: 6px 0 0; padding-inline-start: 20px; }
.scan-item { display: grid; grid-template-columns: minmax(180px, 1fr) minmax(230px, 1.3fr) 260px; gap: 18px; padding: 18px 0; border-bottom: 1px solid var(--border); }
.scan-item.needs-review { border-inline-start: 3px solid var(--amber); padding-inline-start: 12px; }
.detected-item { display: grid; gap: 8px; align-content: center; font-size: 13px; overflow-wrap: anywhere; }.detected-item small { font-size: 11px; color: var(--text-muted); line-height: 1.6; }
.match-product { display: grid; gap: 8px; }.scan-quantities { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; align-content: start; }.scan-quantities b { grid-column: 1 / -1; font-size: 13px; text-align: end; }
.invoice-scanner .scan-checkbox { display: flex; align-items: flex-start; gap: 10px; font-weight: 500; line-height: 1.6; }.scan-checkbox input { flex: none; width: 18px; height: 18px; accent-color: var(--brand-dark); margin-top: 1px; }
.unit-confirm { grid-column: 1 / -1; color: var(--text); }.scan-cost-title { margin-top: 24px; }.scan-cost { display: grid; grid-template-columns: 1fr 1.2fr 160px; gap: 16px; margin-top: 16px; }
.scan-totals { display: grid; grid-template-columns: 1fr 1fr 1fr; align-items: center; gap: 24px; padding: 20px; margin: 26px 0; background: var(--surface-2); border-radius: 10px; }
.scan-totals > div { display: grid; gap: 10px; font-size: 12px; }.scan-totals strong { font-size: 20px; }.scan-totals .scan-error { margin: 0; border: 0; padding: 0; }
.scan-apply { margin-top: 20px; }.scan-apply button { flex: none; min-height: 46px; }.scan-progress { font-weight: 600; }
@media (max-width: 1100px) { .scan-item { grid-template-columns: 1fr 1fr; }.scan-quantities { grid-column: 2; }.detected-item { grid-row: 1 / 3; }.unit-confirm { grid-row: auto; } }
@media (max-width: 700px) { .invoice-scanner { padding: 14px; }.scan-header, .scan-apply { align-items: flex-start; flex-direction: column; }.scan-steps { gap: 10px; font-size: 11px; }.scan-grid, .scan-item, .scan-cost, .scan-totals { grid-template-columns: minmax(0, 1fr); }.scan-item > *, .scan-quantities, .detected-item { grid-column: 1; grid-row: auto; }.scan-totals { gap: 18px; padding: 14px; }.scan-totals strong { font-size: 18px; }.scan-apply button { width: 100%; } }
</style>
