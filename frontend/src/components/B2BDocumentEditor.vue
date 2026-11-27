<template>
  <section class="b2b-editor" :aria-label="t(draft.doctype)">
    <header class="b2b-editor-heading">
      <div><span class="b2b-kicker">{{ t(draft.doctype) }}</span><h2>{{ draft.name || t('New draft') }}</h2></div>
      <span class="b2b-status" :class="{ complete: draft.docstatus === 1, warning: dirty }">{{ dirty ? t('Unsaved changes') : t(draft.status || 'Draft') }}</span>
      <a v-if="draft.name" class="btn btn-outline" :href="deskUrl(draft.doctype, draft.name)" target="_blank" rel="noopener">{{ t('Open in ERPNext') }}</a>
      <button class="btn btn-outline" :disabled="busy" @click="emit('close')"><Icon name="close" /> {{ t('Close') }}</button>
    </header>
    <p v-if="foreign" class="b2b-notice">{{ t('Use ERPNext to edit or settle this currency. You can view and print it here.') }}</p>
    <p v-if="error" class="b2b-error" role="alert">{{ error }}</p>
    <nav class="b2b-subtabs" role="tablist" :aria-label="t('Document sections')">
      <button v-for="tab in sections" :key="tab" role="tab" :aria-selected="section === tab" :class="{ active: section === tab }" @click="section = tab">{{ t(tab) }}</button>
    </nav>

    <div v-if="section === 'Details'" class="b2b-fields b2b-editor-body" @input="changed" @change="changed">
      <label>{{ t(draft.doctype === 'Sales Order' || draft.doctype === 'Quotation' ? 'Transaction date' : 'Posting date') }}<input v-model="draft[dateField]" type="date" :disabled="!editable" /></label>
      <label v-if="draft.doctype === 'Sales Invoice'">{{ t('Due date') }}<input v-model="draft.due_date" type="date" :disabled="!editable" /></label>
      <label v-if="draft.doctype === 'Quotation'">{{ t('Valid until') }}<input v-model="draft.valid_till" type="date" :disabled="!editable" /></label>
      <label v-if="draft.doctype === 'Sales Order' || draft.doctype === 'Delivery Note'">{{ t('Delivery date') }}<input v-model="draft.delivery_date" type="date" :disabled="!editable" /></label>
      <label>{{ t('Customer purchase order') }}<input v-model="draft.po_no" :disabled="!editable" /></label>
      <label>{{ t('Purchase order date') }}<input v-model="draft.po_date" type="date" :disabled="!editable" /></label>
      <label>{{ t('Salesperson') }}<select v-model="draft.sales_person" :disabled="!editable"><option value="">{{ t('Select salesperson') }}</option><option v-for="person in session.salesPersons" :key="person.name" :value="person.name">{{ person.sales_person_name || person.name }}</option></select></label>
      <label v-if="draft.doctype === 'Sales Invoice'" class="b2b-check"><input v-model="draft.update_stock" type="checkbox" :true-value="1" :false-value="0" :disabled="!editable || hasDelivery" />{{ t('Deliver stock with this invoice') }}</label>
      <p v-if="draft.doctype === 'Sales Invoice'" class="muted b2b-wide">{{ t(draft.update_stock ? 'Submission will move stock. Do not create another delivery for the same goods.' : 'Record delivery separately with a linked Delivery Note.') }}</p>
      <label class="b2b-wide">{{ t('Note') }}<textarea v-model="draft.remarks" rows="3" :disabled="!editable" /></label>
    </div>

    <div v-if="section === 'Items'" class="b2b-editor-body">
      <div v-if="editable" class="b2b-item-search">
        <label for="b2b-item-search">{{ t('Add items') }}</label>
        <div class="b2b-search-field"><Icon name="search" /><input id="b2b-item-search" v-model="itemQuery" autocomplete="off" :placeholder="t('Search item name or code')" @input="searchItems" /></div>
        <div v-if="itemResults.length" class="b2b-suggestions"><button v-for="item in itemResults" :key="item.name" @click="addItem(item)"><b>{{ item.item_name }}</b><small>{{ item.name }} · {{ item.stock_uom }}</small></button></div>
      </div>
      <div class="b2b-table-wrap">
        <table class="b2b-line-table"><thead><tr><th>{{ t('Item') }}</th><th>{{ t('UOM') }}</th><th>{{ t('Quantity') }}</th><th>{{ t('Warehouse') }}</th><th>{{ t('Rate') }}</th><th>{{ t('Line discount') }}</th><th class="b2b-num">{{ t('Net amount') }}</th><th v-if="editable"><span class="sr-only">{{ t('Remove') }}</span></th></tr></thead>
          <tbody><tr v-for="(line, index) in draft.items" :key="line.name || line.localKey || index">
            <td class="b2b-item-name"><b>{{ line.item_name || line.item_code }}</b><small>{{ line.item_code }}</small><template v-if="line.has_serial_no || line.serial_no"><label>{{ t('Serial numbers') }}<textarea v-model="line.serial_no" rows="2" :disabled="!editable" @input="changed" /></label></template><label v-if="line.has_batch_no || line.batch_no">{{ t('Batch') }}<input v-model="line.batch_no" :disabled="!editable" @input="changed" /></label></td>
            <td><select v-model="line.uom" :disabled="!editable" :aria-label="t('UOM')" @change="repriceLine(line)"><option v-for="unit in unitsFor(line)" :key="unit" :value="unit">{{ unit }}</option></select></td>
            <td><input v-model.number="line.qty" type="number" min="0.001" step="any" inputmode="decimal" :disabled="!editable" :aria-label="t('Quantity')" @input="repriceLine(line)" /></td>
            <td><select v-model="line.warehouse" :disabled="!editable" :aria-label="t('Warehouse')" @change="changed"><option v-for="warehouse in warehousesFor(line)" :key="warehouse" :value="warehouse">{{ warehouse }}</option></select></td>
            <td><input v-model.number="line.base_rate" type="number" min="0" step="any" inputmode="decimal" :disabled="!editable || !options.can_change_rate" :aria-label="t('Rate')" @input="line.manual_rate = true; changed()" /><small v-if="line.manual_rate">{{ t('Manual rate') }} <button type="button" class="b2b-text-button" @click="line.manual_rate = false; changed()">{{ t('Reset') }}</button></small></td>
            <td><div class="b2b-discount-input"><input v-model.number="line.discount_value" type="number" min="0" :max="line.discount_method === 'Percent' ? 100 : undefined" step="any" inputmode="decimal" :disabled="!editable || !options.can_edit_price" :aria-label="t('Line discount')" @input="changed" /><select v-model="line.discount_method" :disabled="!editable || !options.can_edit_price" :aria-label="t('Discount type')" @change="line.discount_value = 0; changed()"><option value="Percent">%</option><option value="Amount">{{ draft.currency }}</option></select></div><small>{{ t('Amount is per unit') }}</small></td>
            <td class="b2b-num"><strong>{{ money(line.amount || 0, draft.currency) }}</strong></td>
            <td v-if="editable"><button class="b2b-icon-button" :aria-label="t('Remove item')" @click="draft.items.splice(index, 1); changed()"><Icon name="trash" /></button></td>
          </tr><tr v-if="!draft.items?.length"><td colspan="8" class="b2b-empty">{{ t('Search and add items to begin.') }}</td></tr></tbody>
        </table>
      </div>
      <p class="muted small">{{ t('Rates include native ERPNext pricing rules. Manual line discounts apply to that rate. Totals are confirmed by the server.') }}</p>
      <div v-if="editable" class="b2b-inline-actions"><button class="btn btn-outline" :disabled="busy || !draft.items.length" @click="refreshPreview"><Icon name="refresh" /> {{ t('Recalculate') }}</button><span class="muted small">{{ previewing ? t('Calculating…') : previewCurrent ? t('Totals confirmed') : t('Totals need recalculation') }}</span></div>
    </div>

    <div v-if="section === 'Payments'" class="b2b-editor-body">
      <div class="b2b-account-metrics"><div><span>{{ t('Invoice total') }}</span><strong>{{ money(draft.grand_total || 0, draft.currency) }}</strong></div><div><span>{{ t('Outstanding') }}</span><strong>{{ money(draft.outstanding_amount || 0, draft.currency) }}</strong></div></div>
      <p class="muted">{{ t('Receive partial or split payments, settle selected invoices, or apply available customer advances in Payments.') }}</p>
      <button v-if="draft.docstatus === 1 && ['Sales Invoice', 'Sales Order'].includes(draft.doctype)" class="btn btn-primary" :disabled="!options.can_pay || foreign" @click="emit('pay', draft)"><Icon name="cash" /> {{ t(draft.doctype === 'Sales Order' ? 'Receive order advance' : 'Take payment') }}</button>
      <p v-else class="muted">{{ t('Submit the document before receiving a payment against it.') }}</p>
    </div>

    <div v-if="section === 'Address & Contact'" class="b2b-fields b2b-editor-body" @change="changed">
      <label>{{ t('Billing address') }}<select v-model="draft.customer_address" :disabled="!editable"><option value="">{{ t('Customer default') }}</option><option v-for="row in customerOptions.addresses || []" :key="row.name" :value="row.name">{{ row.address_title || row.name }}</option></select></label>
      <label>{{ t('Shipping address') }}<select v-model="draft.shipping_address_name" :disabled="!editable"><option value="">{{ t('Customer default') }}</option><option v-for="row in customerOptions.addresses || []" :key="row.name" :value="row.name">{{ row.address_title || row.name }}</option></select></label>
      <label>{{ t('Contact') }}<select v-model="draft.contact_person" :disabled="!editable"><option value="">{{ t('Customer default') }}</option><option v-for="row in customerOptions.contacts || []" :key="row.name" :value="row.name">{{ row.full_name || row.name }}</option></select></label>
      <p class="muted b2b-wide">{{ draft.contact_display }} {{ draft.contact_mobile }}</p>
    </div>

    <div v-if="section === 'Terms'" class="b2b-fields b2b-editor-body" @change="changed">
      <label>{{ t('Payment terms') }}<select v-model="draft.payment_terms_template" :disabled="!editable"><option value="">{{ t('Customer default') }}</option><option v-for="name in options.payment_terms || []" :key="name" :value="name">{{ name }}</option></select></label>
      <label>{{ t('Terms template') }}<select v-model="draft.tc_name" :disabled="!editable" @change="draft.terms = ''; changed()"><option value="">{{ t('None') }}</option><option v-for="name in options.terms_templates || []" :key="name" :value="name">{{ name }}</option></select></label>
      <label class="b2b-wide">{{ t('Terms') }}<textarea v-model="draft.terms" rows="8" :disabled="!editable" @input="changed" /></label>
    </div>

    <div v-if="section === 'Connections'" class="b2b-editor-body">
      <div v-for="link in draft.connections || []" :key="link.doctype + link.name" class="b2b-connection"><Icon name="folder-open" /><span>{{ t(link.doctype) }}</span><button class="b2b-text-button" @click="emit('open', link)">{{ link.name }}</button></div>
      <p v-if="!draft.connections?.length" class="muted">{{ t('This is a direct document. Linked orders, deliveries, and invoices appear here when you continue the sale.') }}</p>
      <button v-if="draft.docstatus === 1" class="btn btn-outline" @click="emit('progress', draft)">{{ t('Show sales process') }}</button>
    </div>

    <footer class="b2b-editor-footer">
      <div class="b2b-document-totals"><span>{{ t('Net') }} <b>{{ money(draft.net_total || 0, draft.currency) }}</b></span><span>{{ t('Tax') }} <b>{{ money(draft.total_taxes_and_charges || 0, draft.currency) }}</b></span><span v-if="draft.rounding_adjustment">{{ t('Rounding') }} <b>{{ money(draft.rounding_adjustment, draft.currency) }}</b></span><strong>{{ t('Total') }} {{ money(draft.payable_total ?? draft.grand_total ?? 0, draft.currency) }}</strong></div>
      <div class="b2b-inline-actions">
        <label v-if="editable && options.can_edit_price" class="b2b-approval">{{ t('Discount approval passcode') }}<input v-model="passcode" type="password" autocomplete="off" :placeholder="t('If required')" /></label>
        <button v-if="editable && approvalNeeded" class="btn btn-outline" :disabled="busy" @click="approvalOpen = true"><Icon name="shield" /> {{ t('Get discount approval') }}</button>
        <button v-if="editable" class="btn btn-primary" :disabled="busy || !draft.items.length || !dirty" @click="save"><Icon name="bookmark" /> {{ busy ? t('Saving…') : t('Save draft') }}</button>
        <button v-if="draft.name && draft.docstatus === 0 && capability.submit && !foreign" class="btn btn-primary" :disabled="busy || dirty" @click="submit"><Icon name="check" /> {{ t('Submit') }}</button>
        <button v-if="draft.name && capability.print" class="btn btn-outline" :disabled="busy || dirty || offline" @click="print"><Icon name="download" /> {{ t('Print') }}</button>
        <template v-if="draft.docstatus === 1 && !foreign && !draft.readonly"><button v-for="target in conversionTargets" :key="target" class="btn btn-outline" :disabled="busy || offline" @click="convert(target)">{{ t('Create {document}', { document: t(target) }) }}</button><button v-if="capability.cancel && capability.amend" class="btn btn-outline" :disabled="busy || offline" @click="amend">{{ t('Cancel and amend') }}</button></template>
      </div>
    </footer>
    <PasscodeModal v-if="approvalOpen" :discount-context="approvalContext" @approved="discountApproved" @close="approvalOpen = false" />
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import Icon from './Icon.vue'
import PasscodeModal from './PasscodeModal.vue'
import { call } from '../api'
import { money } from '../format'
import { t } from '../i18n'
import { newId } from '../offline'
import { useSessionStore } from '../stores/session'
import { printB2BDocument } from '../b2bPrinting'

const props = defineProps({ document: Object, options: Object, customerOptions: { type: Object, default: () => ({}) }, profile: String, offline: Boolean })
const emit = defineEmits(['saved', 'open', 'close', 'dirty', 'pay', 'progress', 'busy'])
const session = useSessionStore(), draft = ref({ items: [] }), dirty = ref(false), section = ref('Items'), busy = ref(false)
const error = ref(''), itemQuery = ref(''), itemResults = ref([]), units = ref({}), passcode = ref(''), previewing = ref(false), previewCurrent = ref(false)
const approvalOpen = ref(false), approvalRequest = ref(null)
const sections = ['Details', 'Items', 'Payments', 'Address & Contact', 'Terms', 'Connections']
let itemTimer, previewTimer, attempt = null, revision = 0, itemRevision = 0
const capability = computed(() => props.options.kinds?.[draft.value.doctype] || {})
const foreign = computed(() => draft.value.currency !== props.options.currency)
const editable = computed(() => !props.offline && !foreign.value && !draft.value.readonly && !draft.value.docstatus && Boolean(draft.value.name ? capability.value.write : capability.value.create))
const dateField = computed(() => ['Quotation', 'Sales Order'].includes(draft.value.doctype) ? 'transaction_date' : 'posting_date')
const hasDelivery = computed(() => draft.value.items.some(line => line.delivery_note))
const worstDiscount = computed(() => Math.max(0,...draft.value.items.map(line=>{const native=Number(line.native_rate??line.base_rate??0),base=Number(line.base_rate||0),discount=line.discount_method==='Amount'?Number(line.discount_value||0):base*Number(line.discount_value||0)/100;return native>0?Math.max(0,(native-(base-discount))/native*100):0})))
const approvalNeeded = computed(() => Number(session.settings.discount_limit_percent)>0 && worstDiscount.value>Number(session.settings.discount_limit_percent) && worstDiscount.value>Number(draft.value.approved_percent||0))
const approvalContext = computed(() => ({percent:worstDiscount.value,customer:draft.value.customer,customer_name:draft.value.customer_name,total:draft.value.grand_total,details:draft.value.items.map(line=>`${line.qty} × ${line.item_code}: ${line.discount_value||0} ${line.discount_method==='Amount'?draft.value.currency:'%'}`).join('\n')}))
const conversionTargets = computed(() => ({ Quotation: ['Sales Order'], 'Sales Order': ['Delivery Note', 'Sales Invoice'], 'Delivery Note': ['Sales Invoice'], 'Sales Invoice': draft.value.update_stock ? [] : ['Delivery Note'] }[draft.value.doctype] || []).filter(kind => props.options.kinds?.[kind]?.create))
const deskUrl = (kind, name) => `/app/${kind.toLowerCase().replaceAll(' ', '-')}/${encodeURIComponent(name)}`

watch(() => props.document, value => {
  revision++; clearTimeout(previewTimer)
  draft.value = JSON.parse(JSON.stringify(value)); dirty.value = !value.name; previewCurrent.value = Boolean(value.name)
  passcode.value = ''; approvalRequest.value = null; approvalOpen.value = false
  error.value = ''; emit('dirty', dirty.value); loadUnits()
}, { immediate: true })
watch(busy, value => emit('busy', value))

function unitsFor(line) { return [...new Set([line.uom, ...(units.value[line.item_code]?.units || []).map(unit => unit.uom)].filter(Boolean))] }
function warehousesFor(line) { return [...new Set([line.warehouse, ...(props.options.warehouses || [])].filter(Boolean))] }
async function loadUnits() {
  await Promise.allSettled([...new Set(draft.value.items.map(line => line.item_code))].map(async code => {
    if (!units.value[code]) units.value[code] = await call('esafepos.api.b2b.item_units', { pos_profile: props.profile, item_code: code })
    for (const line of draft.value.items.filter(row => row.item_code === code)) Object.assign(line, { has_serial_no: units.value[code].has_serial_no, has_batch_no: units.value[code].has_batch_no })
  }))
}
function payload() {
  const value = draft.value
  return { ...Object.fromEntries(['doctype', 'name', 'modified', 'customer', 'posting_date', 'transaction_date', 'due_date', 'delivery_date', 'valid_till', 'po_no', 'po_date', 'sales_person', 'update_stock', 'customer_address', 'shipping_address_name', 'contact_person', 'payment_terms_template', 'tc_name', 'terms', 'remarks'].map(key => [key, value[key] ?? null])),
    items: value.items.map(line => Object.fromEntries(['name', 'item_code', 'qty', 'uom', 'warehouse', 'base_rate', 'manual_rate', 'discount_method', 'discount_value', 'serial_no', 'batch_no', 'delivery_date'].map(key => [key, line[key] ?? null]))), discount_passcode: passcode.value || null, discount_request: approvalRequest.value }
}
function changed() {
  dirty.value = true; previewCurrent.value = false; emit('dirty', true); revision++
  clearTimeout(previewTimer)
  if (draft.value.items.length) previewTimer = setTimeout(refreshPreview, 500)
}
function repriceLine(line) { if (!line.manual_rate) line.base_rate = null; changed() }
async function refreshPreview() {
  if (busy.value || !editable.value || !draft.value.items.length) return
  const version = ++revision; previewing.value = true
  try {
    const result = await call('esafepos.api.b2b.preview', { pos_profile: props.profile, payload: payload() })
    if (version !== revision) return
    for (const key of ['grand_total', 'payable_total', 'rounding_adjustment', 'net_total', 'total_taxes_and_charges', 'taxes', 'currency', 'address_display', 'contact_display', 'contact_mobile', 'terms']) draft.value[key] = result[key]
    for (let i = 0; i < result.items.length; i++) for (const key of ['base_rate', 'native_rate', 'rate', 'amount', 'price_list_rate', 'discount_amount', 'discount_percentage']) draft.value.items[i][key] = result.items[i][key]
    previewCurrent.value = true; error.value = ''
  } catch (err) { if (version === revision) error.value = err.message } finally { if (version === revision) previewing.value = false }
}
function searchItems() {
  clearTimeout(itemTimer); const request = ++itemRevision
  itemTimer = setTimeout(async () => {
    try { const rows = await call('esafepos.api.b2b.search_items', { pos_profile: props.profile, search: itemQuery.value }); if (request === itemRevision) itemResults.value = rows }
    catch (err) { error.value = err.message }
  }, 220)
}
async function addItem(item) {
  draft.value.items.push({ localKey: newId(), item_code: item.name, item_name: item.item_name, qty: 1, uom: item.sales_uom || item.stock_uom, warehouse: props.options.warehouse, base_rate: null, discount_method: 'Percent', discount_value: 0, has_serial_no: item.has_serial_no, has_batch_no: item.has_batch_no })
  itemQuery.value = ''; itemResults.value = []; changed(); await loadUnits()
}
async function perform(action) {
  busy.value = true; revision++; clearTimeout(previewTimer); error.value = ''
  try { await action() } catch (err) { error.value = err.message; session.notify(err.message, true) } finally { busy.value = false; previewing.value = false }
}
async function save() {
  await perform(async () => {
    const value = payload(), signature = JSON.stringify(value)
    if (!attempt || attempt.signature !== signature) attempt = { signature, key: newId() }
    const result = await call('esafepos.api.b2b.save_document', { pos_profile: props.profile, payload: value, idempotency_key: attempt.key }, { timeout: 60000 })
    attempt = null; passcode.value = ''; approvalRequest.value = null; dirty.value = false; emit('dirty', false); emit('saved', result)
    session.notify(t('Draft {name} saved', { name: result.name }))
  })
}
async function submit() {
  if (dirty.value) return
  await perform(async () => {
    const result = await call('esafepos.api.b2b.submit_document', { pos_profile: props.profile, doctype: draft.value.doctype, name: draft.value.name, modified: draft.value.modified, expected_total: draft.value.grand_total }, { timeout: 60000 })
    emit('saved', result); emit('progress', result); session.notify(t('Document submitted'))
  })
}
async function print() { await perform(() => printB2BDocument(draft.value.doctype, draft.value.name)) }
function discountApproved(approval){passcode.value=approval.passcode||'';approvalRequest.value=approval.request||null;approvalOpen.value=false;changed()}
async function convert(target) {
  await perform(async () => {
    const signature = JSON.stringify({ doctype: draft.value.doctype, name: draft.value.name, target })
    if (!attempt || attempt.signature !== signature) attempt = { signature, key: newId() }
    const result = await call('esafepos.api.b2b.convert_document', { pos_profile: props.profile, doctype: draft.value.doctype, name: draft.value.name, target, idempotency_key: attempt.key }, { timeout: 60000 })
    attempt = null; emit('open', result); session.notify(t('Draft {name} created', { name: result.name }))
  })
}
async function amend() {
  if (!window.confirm(t('Cancel this document and create an amended draft? Linked documents and accounting rules may prevent cancellation.'))) return
  await perform(async () => {
    const signature = `amend:${draft.value.name}:${draft.value.modified}`
    if (!attempt || attempt.signature !== signature) attempt = { signature, key: newId() }
    const result = await call('esafepos.api.b2b.cancel_and_amend', { pos_profile: props.profile, doctype: draft.value.doctype, name: draft.value.name, modified: draft.value.modified, idempotency_key: attempt.key }, { timeout: 60000 })
    attempt = null; emit('open', result)
  })
}
onBeforeUnmount(() => { revision++; itemRevision++; clearTimeout(itemTimer); clearTimeout(previewTimer) })
</script>
