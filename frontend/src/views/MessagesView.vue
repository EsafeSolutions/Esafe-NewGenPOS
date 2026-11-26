<template>
  <div class="messages-page">
    <header class="messages-header"><div><h2>{{ t('Customer messaging') }}</h2><p class="muted">{{ t('Send SMS or WhatsApp Business API messages. Open a receipt to share its e-invoice or image.') }}</p></div>
      <router-link v-if="session.permissions.settings" to="/settings?section=messaging" class="btn btn-outline">{{ t('Messaging settings') }}</router-link></header>
    <div class="messages-layout">
      <section class="card customer-picker"><h3>{{ t('Find a customer') }}</h3>
        <label>{{ t('Search customers') }}<input v-model="search" :aria-label="t('Search customers')" :placeholder="t('Name, phone, code, email…')" @input="queueSearch" /></label>
        <p v-if="searching" class="muted">{{ t('Searching…') }}</p><p v-if="searchError" class="error" role="alert">{{ searchError }}</p>
        <button v-for="person in customers" :key="person.name" type="button" class="customer-option" :class="{ selected: customer?.name === person.name }" @click="customer = person"><b>{{ person.customer_name }}</b><span class="muted">{{ person.mobile_no || person.name }}</span></button>
        <router-link v-if="customer" :to="{path:'/customers',query:{customer:customer.name}}" class="btn btn-outline profile-link">{{ t('Open customer profile') }}</router-link>
      </section>
      <CustomerMessageComposer v-if="customer" :customer="customer.name" :mobile-number="customer.mobile_no" @recorded="loadHistory" />
      <div v-else class="card message-empty muted">{{ t('Select a customer to prepare a message.') }}</div>
    </div>
    <section class="card message-history"><div class="history-header"><h3>{{ t('Recent messages from this outlet') }}</h3><button type="button" class="btn btn-outline" @click="loadHistory">{{ t('Refresh') }}</button></div>
      <p class="muted small">{{ t('WhatsApp API records Meta acceptance; the popup records an opened draft. SMS records gateway submission. Delivery/read status is not tracked. Cashiers see their own records.') }}</p>
      <p v-if="historyError" class="error" role="alert">{{ historyError }}</p>
      <div class="history-scroll"><table v-if="history.length"><thead><tr><th>{{ t('Time') }}</th><th>{{ t('Customer') }}</th><th>{{ t('Channel') }}</th><th>{{ t('Status') }}</th><th>{{ t('Message') }}</th></tr></thead>
        <tbody><tr v-for="row in history" :key="row.name"><td>{{ shortTime(row.creation) }}</td><td>{{ row.customer || row.mobile }}<br /><span class="muted">{{ row.mobile }}</span></td><td>{{ row.channel }}</td><td>{{ t(row.status) }}<p v-if="row.error">{{ row.error }}</p></td><td class="message-body">{{ row.message }}<router-link v-if="row.invoice" :to="{path:'/history',query:{invoice:row.invoice}}">{{ t('Open invoice') }}</router-link></td></tr></tbody></table><p v-else class="muted">{{ t('No message records yet.') }}</p></div>
    </section>
  </div>
</template>
<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { call } from '../api'
import { t } from '../i18n'
import { shortTime } from '../format'
import { useSessionStore } from '../stores/session'
import CustomerMessageComposer from '../components/CustomerMessageComposer.vue'
const session = useSessionStore()
const customer = ref(null), customers = ref([]), search = ref(''), searching = ref(false), searchError = ref(''), history = ref([]), historyError = ref('')
let timer, request = 0, historyRequest = 0
function queueSearch() { clearTimeout(timer); timer = setTimeout(findCustomers, 250) }
async function findCustomers() {
  const current = ++request; searching.value = true; searchError.value = ''
  try { const data = await call('esafepos.api.customers.search_customers', {search:search.value,limit:15}); if(current === request) customers.value = data.items || [] }
  catch(e) { if(current === request) searchError.value = e.message } finally { if(current === request) searching.value = false }
}
async function loadHistory() {
  const current = ++historyRequest; historyError.value = ''
  try { const data = await call('esafepos.api.messaging.recent_messages', {pos_profile: session.posProfile}); if(current === historyRequest) history.value = data || [] }
  catch(e) { if(current === historyRequest) historyError.value = e.message }
}
onMounted(() => { findCustomers(); loadHistory() })
watch(() => session.posProfile, () => { history.value = []; loadHistory() })
onBeforeUnmount(() => { clearTimeout(timer); request++; historyRequest++ })
</script>
<style scoped>
.messages-page { flex: 1; min-width: 0; overflow: auto; padding: 22px; } .messages-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 14px; } h2 { margin: 0; } h3 { margin: 0 0 12px; }
.messages-header p { line-height: 1.5; } .messages-header a { text-decoration: none; flex-shrink: 0; } .messages-layout { display: grid; grid-template-columns: 290px minmax(0,1fr); gap: 18px; align-items: start; }
.customer-picker, .message-empty, .message-history { padding: 18px; } label { display: grid; gap: 6px; font-size: 12px; } input { width: 100%; min-width: 0; }
.customer-option { display: grid; gap: 4px; width: 100%; text-align: start; padding: 12px 8px; border-bottom: 1px solid var(--border); } .customer-option:hover, .customer-option.selected { background: var(--surface-2); } .customer-option span { font-size: 12px; }
.profile-link { margin-top: 12px; text-decoration: none; } .message-empty { min-height: 220px; display: grid; place-items: center; } .message-history { margin-top: 20px; } .history-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.small { font-size: 12px; line-height: 1.5; } .history-scroll { overflow-x: auto; } table { border-collapse: collapse; width: 100%; min-width: 700px; font-size: 12px; }
th, td { text-align: start; padding: 10px; border-bottom: 1px solid var(--border); vertical-align: top; } .message-body { white-space: pre-wrap; overflow-wrap: anywhere; max-width: 380px; } .message-body a { display: block; margin-top: 8px; } .error { color: var(--red); }
@media(max-width:800px) { .messages-page { padding: 12px; } .messages-layout { grid-template-columns: 1fr; } .messages-header { flex-direction: column; } .customer-picker { max-height: 290px; overflow: auto; } }
</style>
