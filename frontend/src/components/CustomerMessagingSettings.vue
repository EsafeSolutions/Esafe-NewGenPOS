<template>
  <section class="messaging-settings">
    <h2>{{ t('Customer messaging') }}</h2>
    <p class="muted">{{ t('Configure SMS, WhatsApp Business API and e-invoice sharing for POS.') }}</p>
    <p v-if="loading">{{ t('Loading…') }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <button v-if="!data && !loading" type="button" class="btn btn-outline" @click="load">{{ t('Retry') }}</button>
    <template v-if="data">
      <p v-if="!data.ready" class="notice">{{ t('Run site migration to install customer messaging settings and history.') }}</p>
      <form class="card settings-card" @submit.prevent="saveConfig">
        <label class="toggle"><input v-model="form.enabled" type="checkbox" :true-value="1" :false-value="0" /> {{ t('Enable customer messaging') }}</label>
        <div class="settings-grid">
          <label class="toggle"><input v-model="form.sms_enabled" type="checkbox" :true-value="1" :false-value="0" /> {{ t('SMS messages') }}</label>
          <label class="toggle"><input v-model="form.whatsapp_enabled" type="checkbox" :true-value="1" :false-value="0" /> {{ t('WhatsApp messages and drafts') }}</label>
          <label class="toggle"><input v-model="form.image_enabled" type="checkbox" :true-value="1" :false-value="0" /> {{ t('Receipt image sharing') }}</label>
          <label>{{ t('Default country calling code') }}<input v-model="form.country_code" inputmode="numeric" placeholder="94" required /></label>
          <label>{{ t('SMS recipient number format') }}<select v-model="form.sms_number_format" :aria-label="t('SMS recipient number format')"><option value="As entered">{{ t('As entered (0771234567)') }}</option><option value="International digits">{{ t('International digits (94771234567)') }}</option><option value="International +">{{ t('International with + (+94771234567)') }}</option></select></label>
          <label>{{ t('Open WhatsApp in') }}<select v-model="form.whatsapp_target"><option value="Popup">{{ t('Separate popup window') }}</option><option value="Tab">{{ t('New tab') }}</option></select></label>
        </div>
        <p class="muted small">{{ t('Choose the number format required by your SMS provider. The WhatsApp popup opens separately using your signed-in browser/app; you press Send there. WhatsApp API sends directly from POS.') }}</p>
        <label>{{ t('E-invoice message template') }}<textarea v-model="form.invoice_template" rows="5" maxlength="2000" required /></label>
        <label>{{ t('Customer message template') }}<textarea v-model="form.customer_template" rows="3" maxlength="2000" required /></label>
        <div class="settings-grid"><label>{{ t('Approved Meta template name') }}<input v-model="form.whatsapp_template_name" placeholder="pos_receipt" /></label><label>{{ t('Template language code') }}<input v-model="form.whatsapp_template_language" placeholder="en" /></label></div>
        <label>{{ t('Meta template body parameters, in order') }}<input v-model="form.whatsapp_template_parameters" placeholder="customer,invoice,total,link" /></label>
        <label class="toggle"><input v-model="form.whatsapp_template_image" type="checkbox" :true-value="1" :false-value="0" /> {{ t('This approved template has a receipt image header') }}</label>
        <h4>{{ t('Roles allowed to send through WhatsApp API') }}</h4><div class="role-options"><label v-for="role in data.roles" :key="role" class="toggle"><input v-model="form.whatsapp_api_roles" type="checkbox" :value="role" /> {{ role }}</label></div>
        <p class="muted small">{{ t('Create and approve this template in WhatsApp Manager. The parameter order must match its numbered body variables. Templates can be used outside the 24-hour customer service window.') }}</p>
        <p class="muted small">{{ t('Placeholders') }}: <code>{customer} {invoice} {company} {currency} {total} {date} {link} {document}</code></p>
        <button class="btn btn-primary" :disabled="saving || session.offline || !data.ready">{{ t(saving ? 'Saving…' : 'Save messaging settings') }}</button>
      </form>
      <form class="card settings-card" @submit.prevent="saveWhatsApp">
        <h3>{{ t('WhatsApp Business API integration') }}</h3>
        <p class="muted small">{{ t('Connect the Meta business phone number used by this POS site. The access token is encrypted on the server and is never returned to the browser. Leave it blank to keep the saved token.') }}</p>
        <div class="settings-grid"><label>{{ t('Business phone number ID') }}<input v-model="whatsapp.phone_number_id" inputmode="numeric" required /></label><label>{{ t('Graph API version') }}<input v-model="whatsapp.api_version" placeholder="v27.0" required /></label></div>
        <label>{{ t('Access token') }}<input v-model="token" type="password" autocomplete="new-password" :placeholder="whatsapp.token_configured ? t('Saved token kept') : t('Enter Meta access token')" :required="!whatsapp.token_configured" /></label>
        <div class="connection-actions"><button class="btn btn-primary" :disabled="savingWhatsApp || session.offline">{{ t('Save WhatsApp connection') }}</button><button type="button" class="btn btn-outline" :disabled="checkingWhatsApp || session.offline" @click="checkWhatsApp">{{ t('Check saved connection') }}</button><a class="btn btn-outline" href="https://business.facebook.com/wa/manage/home/" target="_blank" rel="noopener noreferrer">{{ t('WhatsApp Manager') }}</a></div>
        <p v-if="connection" role="status">{{ connection }}</p><p class="muted small">{{ t('Text and image messages require an open 24-hour customer service window. Approved templates use their registered wording. Message history records Meta acceptance, not delivered/read status; those require delivery webhooks.') }}</p>
      </form>
      <form v-if="data.gateway" class="card settings-card" @submit.prevent="saveGateway">
        <h3>{{ t('SMS gateway integration') }}</h3><p class="muted small">{{ t('These are ERPNext SMS Settings. Existing parameter values are kept when left blank. No message is sent when saving.') }}</p>
        <label>{{ t('SMS gateway URL') }}<input v-model="gateway.sms_gateway_url" type="url" required /></label>
        <div class="settings-grid"><label>{{ t('Message parameter') }}<input v-model="gateway.message_parameter" required /></label><label>{{ t('Recipient parameter') }}<input v-model="gateway.receiver_parameter" required /></label></div>
        <label class="toggle"><input v-model="gateway.use_post" type="checkbox" :true-value="1" :false-value="0" /> {{ t('Use POST') }}</label>
        <div v-for="(row, index) in gateway.parameters" :key="row.name || index" class="parameter-row">
          <label>{{ t('Parameter') }}<input v-model="row.parameter" required /></label>
          <label>{{ t('Value') }}<input v-model="row.value" type="password" autocomplete="new-password" :placeholder="row.has_value ? t('Stored value kept') : t('Enter value')" :required="!row.has_value" /></label>
          <label class="toggle"><input v-model="row.header" type="checkbox" :true-value="1" :false-value="0" /> {{ t('HTTP header') }}</label>
          <button type="button" class="btn btn-outline" :aria-label="t('Remove SMS parameter {number}', { number: index + 1 })" @click="gateway.parameters.splice(index, 1)">×</button>
        </div>
        <button type="button" class="btn btn-outline" @click="gateway.parameters.push({parameter:'',value:'',header:0})">{{ t('Add gateway parameter') }}</button>
        <h4>{{ t('Roles allowed to send SMS') }}</h4><p class="muted small">{{ t('System Manager can always send. Select cashier roles that may submit paid SMS messages.') }}</p>
        <div class="role-options"><label v-for="role in data.roles" :key="role" class="toggle"><input v-model="gateway.allowed_roles" type="checkbox" :value="role" /> {{ role }}</label></div>
        <button class="btn btn-primary" :disabled="savingGateway || session.offline">{{ t(savingGateway ? 'Saving…' : 'Save SMS gateway') }}</button>
      </form>
      <p v-else class="muted">{{ t('A System Manager with SMS Settings write access can configure the gateway here.') }}</p>
    </template>
  </section>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import { call } from '../api'
import { t } from '../i18n'
import { useSessionStore } from '../stores/session'
const session = useSessionStore()
const loading = ref(false), saving = ref(false), savingGateway = ref(false), error = ref(''), data = ref(null), form = ref({}), gateway = ref({})
const whatsapp = ref({}), token = ref(''), savingWhatsApp = ref(false), checkingWhatsApp = ref(false), connection = ref('')
async function load() {
  loading.value = true; error.value = ''
  try { data.value = await call('esafepos.api.messaging.get_messaging_settings'); form.value = {...data.value.config}; gateway.value = data.value.gateway || {}; whatsapp.value = data.value.whatsapp || {} }
  catch (e) { error.value = e.message } finally { loading.value = false }
}
async function saveConfig() {
  saving.value = true; error.value = ''
  try { const saved = await call('esafepos.api.messaging.save_messaging_settings', { payload: form.value }); form.value = saved.config; session.notify(t('Messaging settings saved')) }
  catch (e) { error.value = e.message } finally { saving.value = false }
}
async function saveGateway() {
  savingGateway.value = true; error.value = ''
  try { data.value = await call('esafepos.api.messaging.save_sms_gateway', {payload: gateway.value}); gateway.value = data.value.gateway; session.notify(t('SMS gateway saved')) }
  catch (e) { error.value = e.message } finally { savingGateway.value = false }
}
onMounted(load)
async function saveWhatsApp() {
  savingWhatsApp.value = true; error.value = ''
  try { await call('esafepos.api.messaging.save_whatsapp_connection', {phone_number_id:whatsapp.value.phone_number_id,api_version:whatsapp.value.api_version,access_token:token.value || null}); token.value=''; whatsapp.value.token_configured=true; session.notify(t('WhatsApp connection saved')) }
  catch(e) { error.value=e.message } finally { savingWhatsApp.value=false }
}
async function checkWhatsApp() {
  checkingWhatsApp.value=true; error.value=''; connection.value=''
  try { const result=await call('esafepos.api.messaging.check_whatsapp_connection'); connection.value=t('Connected') + ': ' + [result.name,result.phone].filter(Boolean).join(' · ') }
  catch(e) { error.value=e.message } finally { checkingWhatsApp.value=false }
}
</script>
<style scoped>
.messaging-settings { max-width: 980px; } h2 { margin-top: 0; } h3 { margin-top: 0; }
.settings-card { padding: 20px; margin: 16px 0; } label { display: grid; gap: 6px; margin: 12px 0; font-size: 13px; }
input, textarea, select { width: 100%; min-width: 0; } textarea { resize: vertical; line-height: 1.5; }
.settings-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 0 16px; }
.toggle { display: flex; align-items: center; gap: 8px; } .toggle input { width: auto; }
.small { font-size: 12px; line-height: 1.5; } code { overflow-wrap: anywhere; }
.parameter-row { display: grid; grid-template-columns: 1fr 1fr auto auto; gap: 12px; align-items: center; }
.role-options { display: flex; flex-wrap: wrap; gap: 0 18px; max-height: 220px; overflow-y: auto; margin-bottom: 12px; }
.error { color: var(--red); } .notice { padding: 12px; background: var(--surface-2); }
.connection-actions { display: flex; flex-wrap: wrap; gap: 8px; } .connection-actions a { text-decoration: none; }
@media(max-width:700px) { .settings-grid { grid-template-columns: 1fr; } .parameter-row { grid-template-columns: 1fr 1fr; } .settings-card { padding: 14px; } }
</style>
