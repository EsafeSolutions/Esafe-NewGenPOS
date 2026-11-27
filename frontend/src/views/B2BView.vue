<template>
  <section class="b2b-workspace" :data-b2b-dirty="dirty || busy ? 'true' : 'false'">
    <header class="b2b-heading"><div><h1>ESAFE B2B MODULE</h1><p>{{ t('Customer sales, from quotation to settlement.') }}</p></div><span class="b2b-company"><Icon name="company" /> {{ options?.company || session.company }}</span><button class="btn btn-outline" :disabled="loading || offline || dirty || busy" @click="refresh"><Icon name="refresh" /> {{ t('Refresh') }}</button></header>
    <div v-if="session.posProfile !== profile" class="b2b-error">{{ t('The outlet changed. Discard this workspace before loading the selected outlet.') }} <button class="btn btn-outline" @click="switchOutlet">{{ t('Discard and switch outlet') }}</button></div>
    <p v-if="offline" class="b2b-notice">{{ t('B2B needs a connection. Your current entries remain here for retry.') }}</p>
    <p v-if="error" class="b2b-error" role="alert">{{ error }}</p>
    <div v-if="!options && loading" class="b2b-empty">{{ t('Loading B2B workspace…') }}</div>
    <template v-if="options">
      <section class="b2b-customer-bar">
        <div v-if="!customer" class="b2b-customer-picker"><label for="b2b-customer">{{ t('Customer') }}</label><div class="b2b-search-field"><Icon name="search" /><input id="b2b-customer" v-model="customerQuery" autocomplete="off" :placeholder="t('Search customer name, phone or code')" @input="searchCustomers" /></div><div v-if="customerResults.length" class="b2b-suggestions"><button v-for="row in customerResults" :key="row.name" @click="selectCustomer(row)"><b>{{ row.customer_name }}</b><small>{{ row.name }} {{ row.mobile_no }}</small></button></div></div>
        <div v-else class="b2b-selected-customer"><span class="b2b-customer-avatar"><Icon name="company" :size="26" /></span><div><strong>{{ customer.customer_name || customer.name }}</strong><small>{{ customer.name }}<template v-if="customer.mobile_no"> · {{ customer.mobile_no }}</template></small></div><button class="b2b-text-button" :disabled="busy" @click="changeCustomer">{{ t('Change customer') }}</button><router-link class="btn btn-outline" :to="{path:'/customers',query:{customer:customer.name}}">{{ t('Customer account') }}</router-link><a v-if="options.can_edit_customer" class="b2b-text-button" :href="deskUrl('Customer',customer.name)" target="_blank" rel="noopener">{{ t('Edit customer') }}</a></div>
        <button v-if="!customer && options.can_create_customer" class="btn btn-outline" :disabled="offline" @click="customerModal = true"><Icon name="plus" /> {{ t('Add customer') }}</button>
      </section>
      <div v-if="customer" class="b2b-account-metrics">
        <div><span>{{ t('Outstanding') }}</span><strong>{{ account ? money(account.outstanding, options.currency) : '—' }}</strong></div>
        <div><span>{{ t('Overdue invoices') }}</span><strong :class="{ 'b2b-negative': account?.overdue > 0 }">{{ account ? money(account.overdue, options.currency) : '—' }}</strong></div>
        <div><span>{{ t('Available advances') }}</span><strong>{{ account ? money(account.advance_total, options.currency) : '—' }}</strong></div>
        <div><span>{{ t('Cheques awaiting clearance') }}</span><strong>{{ account ? money(account.pending_total, options.currency) : '—' }}</strong></div>
      </div>
      <nav ref="tabBar" class="b2b-tabs" role="tablist" :aria-label="t('B2B sections')" @keydown="tabKeys"><button v-for="tab in tabs" :key="tab.id" role="tab" :aria-selected="activeTab === tab.id" :tabindex="activeTab === tab.id ? 0 : -1" :class="{ active: activeTab === tab.id }" @click="setTab(tab.id)"><Icon :name="tab.icon" :size="18" /><span>{{ t(tab.label) }}</span></button></nav>

      <section v-if="activeTab === 'overview'" class="b2b-overview">
        <header class="b2b-section-heading"><div><h2>{{ t('Sales process') }}</h2><p class="muted">{{ processAnchor ? `${t(processAnchor.doctype)} ${processAnchor.name}` : t('Open a document to follow its connected sales process.') }}</p></div><span v-if="process" class="b2b-progress-total">{{ process.percent }}% {{ t(process.complete ? 'Complete' : 'complete') }}</span></header>
        <div class="b2b-process" :aria-label="t('Sales process progress')"><div class="b2b-process-track" :style="{ '--progress': `${process?.percent || 0}%` }" /><button v-for="(stage,index) in processStages" :key="stage.doctype" class="b2b-process-step" :class="{ complete:stage.state === 'Complete', current:['In progress','Draft'].includes(stage.state), skipped:stage.state === 'Skipped' }" @click="setTab(kindTab[stage.doctype] || 'payments')"><span class="b2b-process-icon"><Icon :name="stage.state === 'Complete' ? 'check' : stageIcons[index]" :size="23" /></span><b>{{ t(stage.doctype === 'Payment' ? 'Payment' : stage.doctype) }}</b><small>{{ t(stage.state) }}</small></button></div>
        <div v-if="process" class="b2b-process-summary"><span>{{ t('Outstanding on this sale') }} <b>{{ money(process.outstanding, options.currency) }}</b></span><span v-if="process.pending_cheques">{{ process.pending_cheques }} {{ t('cheques awaiting clearance') }}</span><span v-if="process.truncated" class="b2b-negative">{{ t('This sales chain is too large to show fully. Review its connections in ERPNext.') }}</span></div>
        <header class="b2b-section-heading"><h2>{{ process ? t('Connected documents') : t('Recent sales documents') }}</h2><button v-if="options.kinds['Sales Invoice']?.create" class="btn btn-primary" :disabled="!customer || offline" @click="newDocument('Sales Invoice')"><Icon name="plus" /> {{ t('New invoice') }}</button></header>
        <div class="b2b-table-wrap"><table><thead><tr><th>{{ t('Document') }}</th><th>{{ t('Type') }}</th><th>{{ t('Status') }}</th><th class="b2b-num">{{ t('Total') }}</th></tr></thead><tbody><tr v-for="row in process?.documents || recent" :key="row.doctype+row.name"><td><button class="b2b-text-button" @click="openDocument(row)">{{ row.name }}</button></td><td>{{ t(row.doctype) }}</td><td><span class="b2b-status">{{ t(row.status || docStatus(row.docstatus)) }}</span></td><td class="b2b-num">{{ money(row.grand_total, row.currency) }}</td></tr><tr v-if="!(process?.documents || recent).length"><td colspan="4" class="b2b-empty">{{ t(customer ? 'Create a quotation, order, delivery, or invoice for this customer.' : 'Select a customer to begin a B2B sale.') }}</td></tr></tbody></table></div>
      </section>

      <template v-if="currentKind">
        <B2BDocumentEditor v-if="editor && editor.doctype === currentKind" :document="editor" :options="options" :customer-options="customerOptions" :profile="profile" :offline="offline || session.posProfile !== profile" @saved="documentSaved" @open="openDocument" @dirty="dirty = $event" @busy="busy = $event" @close="closeEditor" @pay="takePayment" @progress="loadProgress" />
        <section v-else class="b2b-document-list">
          <header class="b2b-section-heading"><div><h2>{{ t(currentKind) }}</h2><p class="muted">{{ t('Draft, submit, print, and continue the sale.') }}</p></div><button v-if="options.kinds[currentKind]?.create" class="btn btn-primary" :disabled="!customer || offline" @click="newDocument(currentKind)"><Icon name="plus" /> {{ t('New {document}',{document:t(currentKind)}) }}</button></header>
          <div class="b2b-list-filters"><div class="b2b-search-field"><Icon name="search" /><input v-model="documentSearch" :placeholder="t('Search document or customer')" @input="searchDocuments" /></div><select v-model="documentStatus" :aria-label="t('Status')" @change="page = 0; loadDocuments()"><option value="">{{ t('All statuses') }}</option><option v-for="value in ['Draft','Submitted','Cancelled']" :key="value">{{ value }}</option></select><label>{{ t('From') }}<input v-model="documentFrom" type="date" @change="page = 0; loadDocuments()" /></label><label>{{ t('To') }}<input v-model="documentTo" type="date" @change="page = 0; loadDocuments()" /></label></div>
          <p v-if="loading" class="muted b2b-padded" role="status">{{ t('Loading documents…') }}</p>
          <div class="b2b-table-wrap"><table><thead><tr><th>{{ t('Document') }}</th><th>{{ t('Customer') }}</th><th>{{ t('Date') }}</th><th>{{ t('Status') }}</th><th class="b2b-num">{{ t('Total') }}</th><th v-if="currentKind === 'Sales Invoice'" class="b2b-num">{{ t('Outstanding') }}</th><th>{{ t('Process') }}</th></tr></thead><tbody><tr v-for="row in documents" :key="row.name"><td><button class="b2b-text-button" @click="openDocument({...row,doctype:currentKind})">{{ row.name }}</button></td><td>{{ row.customer_name }}</td><td>{{ row.posting_date || row.transaction_date }}</td><td><span class="b2b-status" :class="{complete:row.status === 'Paid',warning:row.status === 'Overdue'}">{{ t(row.status || docStatus(row.docstatus)) }}</span></td><td class="b2b-num">{{ money(row.grand_total,row.currency) }}</td><td v-if="currentKind === 'Sales Invoice'" class="b2b-num">{{ money(row.outstanding_amount,row.currency) }}</td><td><button class="b2b-text-button" @click="showProcess({...row,doctype:currentKind})">{{ t('View progress') }}</button></td></tr><tr v-if="!documents.length && !loading"><td colspan="7" class="b2b-empty">{{ t('No matching documents.') }}</td></tr></tbody></table></div>
          <div class="b2b-pagination"><button class="btn btn-outline" :disabled="page === 0 || loading" @click="page--; loadDocuments()">{{ t('Previous') }}</button><span>{{ t('Page') }} {{ page+1 }}</span><button class="btn btn-outline" :disabled="!hasMore || loading" @click="page++; loadDocuments()">{{ t('Next') }}</button></div>
        </section>
      </template>

      <section v-if="activeTab === 'payments'">
        <p v-if="!customer" class="b2b-empty">{{ t('Select a customer to view payments and settle invoices.') }}</p>
        <B2BSettlementPanel v-else-if="account" :key="customer.name" :options="options" :account="account" :customer="customer" :profile="profile" :focus="paymentFocus" :existing-receipt="existingReceipt" :offline="offline || session.posProfile !== profile" @refresh="refreshCustomer" @dirty="dirty = $event" @busy="busy = $event" />
        <p v-else class="b2b-notice">{{ t('Customer balances could not be loaded. Refresh before collecting a payment.') }}</p>
        <template v-if="customer && options.can_pay"><header class="b2b-section-heading"><h2>{{ t('Recent customer receipts') }}</h2></header><div class="b2b-table-wrap"><table><thead><tr><th>{{ t('Receipt') }}</th><th>{{ t('Date') }}</th><th>{{ t('Method') }}</th><th>{{ t('Reference') }}</th><th class="b2b-num">{{ t('Amount') }}</th><th></th></tr></thead><tbody><tr v-for="row in payments" :key="row.name"><td><a :href="deskUrl('Payment Entry',row.name)" target="_blank" rel="noopener">{{ row.name }}</a><small>{{ t(docStatus(row.docstatus)) }}</small></td><td>{{ row.posting_date }}</td><td>{{ row.mode_of_payment }}</td><td>{{ row.reference_no }}<small>{{ row.reference_date }}</small></td><td class="b2b-num">{{ money(row.paid_amount,row.paid_from_account_currency) }}</td><td><button class="b2b-text-button" @click="printDocument('Payment Entry',row.name)">{{ t('Print') }}</button></td></tr></tbody></table></div><div class="b2b-padded b2b-inline-actions"><button v-for="row in settlements" :key="row.name" class="btn btn-outline" @click="openReceipt(row.name)">{{ t('Receipt') }} {{ row.name }}</button></div></template>
      </section>

      <section v-if="activeTab === 'cheques'">
        <header class="b2b-section-heading"><div><h2>{{ t('Cheque management') }}</h2><p class="muted">{{ t('Track receipt, deposit, bank clearance, and returned cheques.') }}</p></div><select v-model="chequeStatus" :aria-label="t('Cheque status')" @change="page = 0; loadCheques()"><option value="">{{ t('All cheques') }}</option><option v-for="value in ['Due today','Upcoming','Overdue','Received','Deposited','Cleared','Bounced','Returned','Cancelled']" :key="value">{{ value }}</option></select></header>
        <div class="b2b-table-wrap"><table><thead><tr><th>{{ t('Cheque / customer') }}</th><th>{{ t('Issuing bank') }}</th><th>{{ t('Cheque date') }}</th><th>{{ t('Status') }}</th><th class="b2b-num">{{ t('Amount') }}</th><th>{{ t('Actions') }}</th></tr></thead><tbody><tr v-for="row in cheques" :key="row.name"><td><b>{{ row.reference_no }}</b><small>{{ row.customer }}</small></td><td>{{ row.bank }}</td><td>{{ row.cheque_date }}<small v-if="row.clearance_date">{{ t('Cleared') }} {{ row.clearance_date }}</small></td><td><span class="b2b-status" :class="{complete:row.status === 'Cleared',warning:row.status === 'Bounced'}">{{ t(row.status) }}</span></td><td class="b2b-num">{{ money(row.amount,row.currency) }}</td><td><div class="b2b-inline-actions"><button v-for="action in chequeActions(row.status)" :key="action" class="btn btn-outline" :disabled="offline || busy" @click="openChequeAction(row,action)">{{ t(actionLabels[action]) }}</button><a v-if="row.payment_entry" :href="deskUrl('Payment Entry',row.payment_entry)" target="_blank" rel="noopener">{{ row.payment_entry }}</a><button class="b2b-text-button" @click="openChequeAction(row,'history')">{{ t('History') }}</button></div></td></tr><tr v-if="!cheques.length"><td colspan="6" class="b2b-empty">{{ t('No matching cheques.') }}</td></tr></tbody></table></div><div class="b2b-pagination"><button class="btn btn-outline" :disabled="!page || loading" @click="page--; loadCheques()">{{ t('Previous') }}</button><span>{{ t('Page') }} {{ page+1 }}</span><button class="btn btn-outline" :disabled="!hasMore || loading" @click="page++; loadCheques()">{{ t('Next') }}</button></div>
      </section>

      <section v-if="activeTab === 'summary'">
        <header class="b2b-section-heading"><div><h2>{{ t('Customer account statement') }}</h2><p class="muted">{{ t('All permitted ERPNext ledger activity for this customer and company.') }}</p></div><button class="btn btn-primary" :disabled="!statement || offline || busy" @click="printStatement"><Icon name="download" /> {{ t('Print / PDF') }}</button></header>
        <div class="b2b-list-filters"><label>{{ t('From') }}<input v-model="statementFrom" type="date" /></label><label>{{ t('To') }}<input v-model="statementTo" type="date" /></label><button class="btn btn-outline" :disabled="!customer || loading || offline" @click="loadStatement">{{ t('Load statement') }}</button></div>
        <p v-if="!customer" class="b2b-empty">{{ t('Select a customer to view their statement.') }}</p>
        <p v-else-if="!options.can_statement" class="b2b-notice">{{ t('General Ledger read permission is required for a complete customer statement.') }}</p>
        <template v-if="statement"><div class="b2b-account-metrics"><div><span>{{ t('Opening balance') }}</span><strong>{{ money(statement.opening,statement.currency) }}</strong></div><div><span>{{ t('Debits') }}</span><strong>{{ money(statement.debit,statement.currency) }}</strong></div><div><span>{{ t('Credits') }}</span><strong>{{ money(statement.credit,statement.currency) }}</strong></div><div><span>{{ t('Closing balance') }}</span><strong>{{ money(statement.closing,statement.currency) }}</strong></div></div>
          <div class="b2b-table-wrap"><table><thead><tr><th>{{ t('Date') }}</th><th>{{ t('Document') }}</th><th class="b2b-num">{{ t('Debit') }}</th><th class="b2b-num">{{ t('Credit') }}</th><th class="b2b-num">{{ t('Balance') }}</th></tr></thead><tbody><tr v-for="(row,index) in statement.rows" :key="index"><td>{{ row.date }}</td><td><a v-if="row.can_open" :href="deskUrl(row.doctype,row.name)" target="_blank" rel="noopener">{{ row.name }}</a><span v-else>{{ row.name }}</span><small>{{ t(row.doctype) }}</small></td><td class="b2b-num">{{ money(row.debit,statement.currency) }}</td><td class="b2b-num">{{ money(row.credit,statement.currency) }}</td><td class="b2b-num">{{ money(row.balance,statement.currency) }}</td></tr><tr v-if="!statement.rows.length"><td colspan="5" class="b2b-empty">{{ t('No ledger activity in this period.') }}</td></tr></tbody></table></div>
          <div class="b2b-summary-line b2b-padded"><span>{{ t('Cheques awaiting clearance (excluded from ledger balance)') }}</span><b>{{ money(statement.pending_total,statement.currency) }}</b></div><p class="muted small b2b-padded">{{ t('Updated') }} {{ statement.refreshed_at }}</p>
        </template>
      </section>
    </template>
    <CustomerModal v-if="customerModal" select-only @selected="selectCustomer" @close="customerModal = false" />
    <div v-if="chequeDialog" class="b2b-dialog-backdrop"><section class="b2b-dialog" role="dialog" aria-modal="true" :aria-label="t(actionLabels[chequeDialog.action] || 'Cheque history')"><header class="b2b-section-heading"><h2>{{ t(actionLabels[chequeDialog.action] || 'Cheque history') }} · {{ chequeDialog.row.reference_no }}</h2><button class="b2b-icon-button" :disabled="busy" :aria-label="t('Close')" @click="chequeDialog = null"><Icon name="close" /></button></header><p v-if="chequeError" class="b2b-error" role="alert">{{ chequeError }}</p><template v-if="chequeDialog.action !== 'history'"><div class="b2b-fields"><label>{{ t('Event date') }}<input v-model="chequeEventDate" type="date" :max="options.today" /></label><label v-if="['bounce','return','cancel'].includes(chequeDialog.action)">{{ t('Reason') }}<input v-model="chequeReason" /></label></div><template v-if="chequeDialog.action === 'clear'"><p class="b2b-notice">{{ t('Review current invoice allocations. Clearance posts the payment to the bank and reduces the customer balance.') }}</p><div class="b2b-table-wrap"><table><thead><tr><th>{{ t('Invoice') }}</th><th>{{ t('Outstanding') }}</th><th>{{ t('Allocate') }}</th></tr></thead><tbody><tr v-for="row in chequeAccount?.invoices || []" :key="row.name"><td>{{ row.name }}</td><td>{{ money(row.outstanding_amount,options.currency) }}</td><td><input v-model.number="chequeAllocations[row.name]" type="number" min="0" step="0.01" :max="row.outstanding_amount" :aria-label="row.name" /></td></tr></tbody></table></div><label class="b2b-check b2b-padded"><input v-model="chequeKeepAdvance" type="checkbox" />{{ t('Keep any unallocated amount as a customer advance') }}</label></template><button class="btn btn-primary" :disabled="busy || offline" @click="transitionCheque">{{ busy ? t('Saving…') : t('Confirm {action}',{action:t(actionLabels[chequeDialog.action])}) }}</button></template><div v-else><p v-for="(event,index) in parseRows(chequeDialog.row.history)" :key="index">{{ event.date }} · {{ event.action }} · {{ event.user }}<br>{{ event.reason }}</p></div></section></div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import B2BDocumentEditor from '../components/B2BDocumentEditor.vue'
import B2BSettlementPanel from '../components/B2BSettlementPanel.vue'
import CustomerModal from '../components/CustomerModal.vue'
import Icon from '../components/Icon.vue'
import { call } from '../api'
import { money } from '../format'
import { newId } from '../offline'
import { useSessionStore } from '../stores/session'
import { printB2BDocument, printB2BStatement } from '../b2bPrinting'
import { t } from '../i18n'
import '../b2b.css'

const session = useSessionStore(), route = useRoute(), router = useRouter(), profile = ref(session.posProfile)
const options = ref(null), customer = ref(null), customerQuery = ref(''), customerResults = ref([]), customerModal = ref(false), customerOptions = ref({})
const account = ref(null), editor = ref(null), dirty = ref(false), busy = ref(false), loading = ref(false), error = ref('')
const documents = ref([]), recent = ref([]), documentSearch = ref(''), documentStatus = ref(''), documentFrom = ref(''), documentTo = ref(''), page = ref(0), hasMore = ref(false)
const process = ref(null), processAnchor = ref(null), paymentFocus = ref(null), payments = ref([]), settlements = ref([]), existingReceipt = ref(null)
const cheques = ref([]), chequeStatus = ref(''), chequeDialog = ref(null), chequeAccount = ref(null), chequeEventDate = ref(''), chequeReason = ref(''), chequeAllocations = ref({}), chequeKeepAdvance = ref(false), chequeError = ref('')
const statement = ref(null), statementFrom = ref(''), statementTo = ref('')
const tabBar = ref(null)
const kindTab = { Quotation: 'quotations', 'Sales Order': 'orders', 'Delivery Note': 'deliveries', 'Sales Invoice': 'invoices' }
const stageIcons = ['report','bookmark','bike','ticket','cash']
const actionLabels = { deposit: 'Deposit cheque', clear: 'Clear cheque', bounce: 'Mark bounced', return: 'Return cheque', cancel: 'Cancel cheque' }
const allTabs = [{id:'overview',label:'Overview',icon:'grid'}, {id:'quotations',label:'Quotations',icon:'report',kind:'Quotation'}, {id:'orders',label:'Sales Orders',icon:'bookmark',kind:'Sales Order'}, {id:'deliveries',label:'Delivery Notes',icon:'bike',kind:'Delivery Note'}, {id:'invoices',label:'Invoices',icon:'ticket',kind:'Sales Invoice'}, {id:'payments',label:'Payments',icon:'cash'}, {id:'cheques',label:'Cheques',icon:'clock'}, {id:'summary',label:'Customer Summary',icon:'person'}]
const tabs = computed(() => allTabs.filter(tab => tab.kind ? options.value?.kinds[tab.kind]?.read : tab.id === 'cheques' ? options.value?.can_cheque : true))
const activeTab = computed(() => tabs.value.some(tab => tab.id === route.query.tab) ? route.query.tab : 'overview')
const currentKind = computed(() => allTabs.find(tab => tab.id === activeTab.value)?.kind)
const offline = computed(() => session.offline)
const processStages = computed(() => process.value?.stages || ['Quotation','Sales Order','Delivery Note','Sales Invoice','Payment'].map(doctype => ({doctype,state:'Not started'})))
const deskUrl = (kind,name) => `/app/${kind.toLowerCase().replaceAll(' ','-')}/${encodeURIComponent(name)}`
const docStatus = value => ({0:'Draft',1:'Submitted',2:'Cancelled'}[value] || 'Draft')
const parseRows = value => { try { return JSON.parse(value || '[]') } catch { return [] } }
const chequeActions = status => ({Received:['deposit','bounce','return','cancel'],Deposited:['clear','bounce','return'],Cleared:['bounce']}[status] || [])
let customerTimer, documentTimer, customerRequest = 0, listRequest = 0, customerLoad = 0, progressRequest = 0, paymentRequest = 0, statementRequest = 0, chequeAttempt = null

function canLeave() { return !busy.value && (!dirty.value || window.confirm(t('Discard unsaved B2B entries? Saved drafts remain available.'))) }
function setTab(tab) { if (tab === activeTab.value || !canLeave()) return; dirty.value = false; editor.value = null; router.replace({query:{...route.query,tab}}) }
function tabKeys(event) { if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return; const buttons = [...event.currentTarget.querySelectorAll('[role=tab]')]; const index = buttons.indexOf(event.target); const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length-1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length)%buttons.length; event.preventDefault(); buttons[next].click(); buttons[next].focus() }
function searchCustomers() { clearTimeout(customerTimer); const request = ++customerRequest; customerTimer = setTimeout(async () => { try { const result = await call('esafepos.api.customers.search_customers',{search:customerQuery.value,start:0,limit:12}); if(request === customerRequest) customerResults.value = result.items || [] } catch(err){error.value=err.message} },220) }
async function selectCustomer(row) {
  if (!canLeave()) return
  dirty.value = false; editor.value = null; process.value = null; processAnchor.value = null; paymentFocus.value = null; existingReceipt.value = null
  customer.value = row; customerQuery.value = ''; customerResults.value = []; customerModal.value = false; statement.value = null; account.value = null; customerOptions.value = {}
  paymentRequest++;statementRequest++;payments.value=[];settlements.value=[]
  await refreshCustomer(); await loadActive()
}
function changeCustomer() { if (!canLeave()) return; customerLoad++; dirty.value=false; customer.value=null; account.value=null; editor.value=null; process.value=null; processAnchor.value=null; paymentFocus.value=null; statement.value=null; loadActive() }
async function initialize() {
  loading.value=true; error.value=''
  try {
    options.value=await call('esafepos.api.b2b.get_context',{pos_profile:profile.value})
    statementTo.value=options.value.today; statementFrom.value=options.value.today.slice(0,8)+'01'
    if (route.query.customer && !customer.value) await selectCustomer({name:route.query.customer})
    else await loadActive()
  } catch(err){error.value=err.message} finally{loading.value=false}
}
async function refreshCustomer() {
  if(!customer.value || offline.value) return
  const request=++customerLoad, name=customer.value.name
  const results=await Promise.allSettled([
    call('esafepos.api.customers.customer_detail',{customer:name,company:options.value.company}),
    call('esafepos.api.b2b.customer_options',{pos_profile:profile.value,customer:name}),
    session.settings.enable_customer_balances ? call('esafepos.api.b2b_payments.customer_account',{pos_profile:profile.value,customer:name}) : Promise.resolve(null),
  ])
  if(request!==customerLoad) return
  if(results[0].status==='fulfilled') customer.value={...customer.value,...results[0].value}; else error.value=results[0].reason.message
  if(results[1].status==='fulfilled') customerOptions.value=results[1].value; else error.value=results[1].reason.message
  if(results[2].status==='fulfilled') account.value=results[2].value; else { account.value=null; error.value=results[2].reason.message }
  if(activeTab.value==='payments') await loadPayments()
  if(processAnchor.value) await loadProgress(processAnchor.value)
}
async function loadActive() {
  if(!options.value || offline.value) return
  if(currentKind.value) await loadDocuments()
  else if(activeTab.value==='overview') await loadRecent()
  else if(activeTab.value==='payments' && customer.value && options.value.can_pay) await loadPayments()
  else if(activeTab.value==='cheques') await loadCheques()
  else if(activeTab.value==='summary' && customer.value && options.value.can_statement) await loadStatement()
}
async function loadDocuments() {
  const kind=currentKind.value; if(!kind) return
  const request=++listRequest; loading.value=true; error.value=''
  try { const result=await call('esafepos.api.b2b.list_documents',{pos_profile:profile.value,doctype:kind,customer:customer.value?.name||null,search:documentSearch.value,status:documentStatus.value,start:page.value*30,from_date:documentFrom.value||null,to_date:documentTo.value||null}); if(request===listRequest){documents.value=result.items;hasMore.value=result.has_more} }
  catch(err){if(request===listRequest)error.value=err.message} finally{if(request===listRequest)loading.value=false}
}
function searchDocuments(){clearTimeout(documentTimer);documentTimer=setTimeout(()=>{page.value=0;loadDocuments()},220)}
async function loadRecent() { const request=++listRequest; const kinds=Object.keys(kindTab).filter(kind=>options.value.kinds[kind]?.read); const results=await Promise.allSettled(kinds.map(doctype=>call('esafepos.api.b2b.list_documents',{pos_profile:profile.value,doctype,customer:customer.value?.name||null}))); if(request!==listRequest)return; recent.value=results.flatMap((result,index)=>result.status==='fulfilled'?result.value.items.slice(0,5).map(row=>({...row,doctype:kinds[index]})):[]).sort((a,b)=>String(b.modified).localeCompare(String(a.modified))).slice(0,20); for(const result of results)if(result.status==='rejected')error.value=result.reason.message }
async function newDocument(kind) { if(!customer.value||!canLeave())return; dirty.value=false; await router.replace({query:{...route.query,tab:kindTab[kind]}});editor.value={doctype:kind,customer:customer.value.name,customer_name:customer.value.customer_name,currency:options.value.currency,docstatus:0,items:[],posting_date:options.value.today,transaction_date:options.value.today,delivery_date:options.value.today,update_stock:0};dirty.value=true }
async function openDocument(row) {
  if(!row.items && !canLeave())return
  error.value=''
  try {
    const doc=row.items?row:await call('esafepos.api.b2b.get_document',{pos_profile:profile.value,doctype:row.doctype,name:row.name})
    if(customer.value?.name!==doc.customer){customer.value={name:doc.customer,customer_name:doc.customer_name};await refreshCustomer()}
    dirty.value=false;await router.replace({query:{...route.query,tab:kindTab[doc.doctype]}});editor.value=doc
    if(doc.docstatus===1)loadProgress(doc)
  }catch(err){error.value=err.message}
}
async function documentSaved(doc){editor.value=doc;dirty.value=false;await refreshCustomer()}
function closeEditor(){if(!canLeave())return;dirty.value=false;editor.value=null;loadDocuments()}
async function loadProgress(row){const request=++progressRequest;try{const result=await call('esafepos.api.b2b.sales_progress',{pos_profile:profile.value,doctype:row.doctype,name:row.name});if(request===progressRequest){process.value=result;processAnchor.value={doctype:row.doctype,name:row.name}}}catch(err){if(request===progressRequest)error.value=err.message}}
async function showProcess(row){if(!canLeave())return;await loadProgress(row);setTab('overview')}
async function takePayment(doc){paymentFocus.value=doc;dirty.value=false;editor.value=null;await router.replace({query:{...route.query,tab:'payments'}});await refreshCustomer()}
async function loadPayments(){if(!customer.value||!options.value.can_pay)return;const request=++paymentRequest,name=customer.value.name;try{const result=await call('esafepos.api.b2b_payments.list_payments',{pos_profile:profile.value,customer:name});if(request===paymentRequest&&customer.value?.name===name){payments.value=result.items;settlements.value=result.settlements}}catch(err){if(request===paymentRequest)error.value=err.message}}
async function openReceipt(name){if(!canLeave())return;try{existingReceipt.value=await call('esafepos.api.b2b_payments.settlement_receipt',{pos_profile:profile.value,name})}catch(err){error.value=err.message}}
async function loadCheques(){const request=++listRequest;loading.value=true;try{const result=await call('esafepos.api.b2b_payments.list_cheques',{pos_profile:profile.value,customer:customer.value?.name||null,status:chequeStatus.value,start:page.value*30});if(request===listRequest){cheques.value=result.items;hasMore.value=result.has_more}}catch(err){if(request===listRequest)error.value=err.message}finally{if(request===listRequest)loading.value=false}}
async function openChequeAction(row,action){
  chequeError.value='';chequeReason.value='';chequeEventDate.value=options.value.today
  chequeAllocations.value=Object.fromEntries(parseRows(row.allocations).map(ref=>[ref.name,ref.amount]));chequeKeepAdvance.value=Boolean(row.keep_advance)
  chequeAccount.value=null;chequeDialog.value={row,action}
  if(action==='clear'){
    try{
      chequeAccount.value=await call('esafepos.api.b2b_payments.customer_account',{pos_profile:profile.value,customer:row.customer})
      chequeAllocations.value=Object.fromEntries(chequeAccount.value.invoices.map(invoice=>[invoice.name,Math.min(Number(chequeAllocations.value[invoice.name]||0),Number(invoice.outstanding_amount))]))
    }catch(err){chequeError.value=err.message}
  }
}
async function transitionCheque(){
  busy.value=true
  try {
    const args={pos_profile:profile.value,name:chequeDialog.value.row.name,modified:chequeDialog.value.row.modified,action:chequeDialog.value.action,event_date:chequeEventDate.value,reason:chequeReason.value,allocations:Object.entries(chequeAllocations.value).filter(([name,amount])=>Number(amount)>0).map(([name,amount])=>({name,amount:Number(amount)})),keep_advance:chequeKeepAdvance.value?1:0}
    const signature=JSON.stringify(args)
    if(!chequeAttempt||chequeAttempt.signature!==signature)chequeAttempt={signature,key:newId()}
    await call('esafepos.api.b2b_payments.transition_cheque',{...args,idempotency_key:chequeAttempt.key},{timeout:60000})
    chequeAttempt=null;chequeDialog.value=null;await loadCheques();await refreshCustomer();session.notify(t('Cheque updated'))
  }catch(err){chequeError.value=err.message}finally{busy.value=false}
}
async function loadStatement(){if(!customer.value||!options.value.can_statement)return;const request=++statementRequest,name=customer.value.name;loading.value=true;statement.value=null;try{const result=await call('esafepos.api.b2b_reports.customer_statement',{pos_profile:profile.value,customer:name,from_date:statementFrom.value,to_date:statementTo.value});if(request===statementRequest&&customer.value?.name===name)statement.value=result}catch(err){if(request===statementRequest)error.value=err.message}finally{if(request===statementRequest)loading.value=false}}
async function printStatement(){busy.value=true;try{await printB2BStatement({pos_profile:profile.value,customer:statement.value.customer,from_date:statement.value.from_date,to_date:statement.value.to_date})}catch(err){error.value=err.message}finally{busy.value=false}}
async function printDocument(kind,name){try{await printB2BDocument(kind,name)}catch(err){error.value=err.message}}
async function refresh(){if(dirty.value||busy.value)return;error.value='';if(customer.value)await refreshCustomer();await loadActive()}
async function switchOutlet(){if(!canLeave())return;customerLoad++;listRequest++;profile.value=session.posProfile;dirty.value=false;editor.value=null;customer.value=null;account.value=null;options.value=null;process.value=null;processAnchor.value=null;await initialize()}
function beforeUnload(event){if(dirty.value||busy.value){event.preventDefault();event.returnValue=''}}
watch(activeTab,()=>{page.value=0;listRequest++;loading.value=false;loadActive()})
function scrollActiveTab(){const nav=tabBar.value,current=nav?.querySelector('[aria-selected="true"]');if(current&&nav.scrollWidth>nav.clientWidth)current.scrollIntoView({block:'nearest',inline:'center',behavior:'instant'})}
watch([activeTab,options],async()=>{await nextTick();scrollActiveTab()})
watch(()=>session.posProfile,()=>{if(!dirty.value&&!busy.value)switchOutlet()})
watch(()=>session.offline,value=>{if(!value&&!dirty.value)refresh()})
onBeforeRouteLeave(()=>canLeave())
onBeforeRouteUpdate(()=>!dirty.value||canLeave())
onMounted(()=>{window.addEventListener('beforeunload',beforeUnload);window.addEventListener('resize',scrollActiveTab);initialize()})
onBeforeUnmount(()=>{customerRequest++;customerLoad++;listRequest++;progressRequest++;paymentRequest++;statementRequest++;clearTimeout(customerTimer);clearTimeout(documentTimer);window.removeEventListener('beforeunload',beforeUnload);window.removeEventListener('resize',scrollActiveTab)})
</script>
