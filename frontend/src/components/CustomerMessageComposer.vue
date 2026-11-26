<template>
  <section class="message-composer card" :aria-label="t(invoice ? 'Send e-invoice' : 'Customer message')">
    <header><div><h3>{{ t(invoice ? 'Send e-invoice' : 'Customer message') }}</h3><p class="muted small">{{ t('Review the number and edit the message before sharing.') }}</p></div></header>
    <p v-if="loading" class="muted" role="status">{{ t('Preparing message…') }}</p>
    <div v-else-if="loadError" role="alert"><p>{{ loadError }}</p><button type="button" class="btn btn-outline" @click="load">{{ t('Retry') }}</button></div>
    <template v-else-if="details">
      <p v-if="!settings.enabled" class="notice">{{ t('Customer messaging is disabled in POS Settings.') }}</p>
      <p v-if="!details.options.ready" class="notice">{{ t('Run site migration to enable sending and message history.') }}</p>
      <label>{{ t('Customer mobile') }}<input v-model="mobile" type="tel" autocomplete="tel" :aria-label="t('Customer mobile')" placeholder="e.g. +94770000000" :disabled="busy" /></label>
      <label>{{ t('WhatsApp API format') }}<select v-model="deliveryType" :aria-label="t('WhatsApp API format')" :disabled="busy"><option value="Text">{{ t('Typed text and invoice link') }}</option><option v-if="invoice && imageSource && settings.image_enabled" value="Image">{{ t('Receipt image and caption') }}</option><option value="Template" :disabled="Boolean(settings.whatsapp_template_image && (!imageSource || !settings.image_enabled))">{{ t('Approved Meta template') }}</option></select></label>
      <p v-if="settings.whatsapp_template_image && !imageSource" class="muted small">{{ t('The approved template requires a receipt image. Open an invoice to use it.') }}</p>
      <label v-if="deliveryType !== 'Template'">{{ t('Message') }}<textarea v-model="message" rows="5" maxlength="4000" :aria-label="t('Message')" :disabled="busy" /></label>
      <div v-else class="template-review"><b>{{ settings.whatsapp_template_name || t('No approved template configured') }}</b><p class="muted small">{{ t('The wording comes from the approved Meta template. These values are sent in the configured order:') }}</p><div v-for="key in templateKeys" :key="key">{{ key }}: {{ details.template_values?.[key] || '—' }}</div></div>
      <label v-if="deliveryType !== 'Template'" class="window-check"><input v-model="sessionConfirmed" type="checkbox" :disabled="busy" /> {{ t('This customer messaged our WhatsApp business within the last 24 hours.') }}</label>
      <div v-if="deliveryType !== 'Template'" class="message-meta muted small"><span>{{ message.length }} {{ t('characters') }}</span><span>{{ t('SMS may use more than one paid segment.') }}</span></div>
      <label v-if="details.url" class="invoice-link">{{ t('Invoice link') }}<input :value="details.url" readonly dir="ltr" :aria-label="t('Invoice link')" @focus="$event.target.select()" /></label>
      <div class="message-actions">
        <button v-if="settings.whatsapp_enabled" type="button" class="btn btn-primary" :disabled="!canSendApi || submittedWhatsApp" @click="sendWhatsAppApi">{{ t('Send via WhatsApp API') }}</button>
        <button v-if="settings.whatsapp_enabled && deliveryType !== 'Template'" type="button" class="btn btn-outline" :disabled="!canSend" @click="openWhatsApp">{{ t(settings.whatsapp_target === 'Popup' ? 'WhatsApp popup' : 'Open WhatsApp') }}</button>
        <button v-if="settings.sms_enabled && deliveryType !== 'Template'" type="button" class="btn btn-outline" :disabled="!canSend || !details.options.can_sms || !details.options.sms_configured || message.length > 1600 || submittedSms" @click="sendSms">{{ t('Send SMS') }}</button>
        <button v-if="deliveryType !== 'Template'" type="button" class="btn btn-outline" :disabled="busy || !message.trim()" @click="copyText(message)">{{ t('Copy message') }}</button>
        <button v-if="details.url" type="button" class="btn btn-outline" :disabled="busy" @click="copyText(details.url)">{{ t('Copy link') }}</button>
        <a v-if="details.url" class="btn btn-outline" :href="details.url" target="_blank" rel="noopener noreferrer">{{ t('Preview e-invoice') }}</a>
      </div>
      <p v-if="settings.whatsapp_enabled && !details.options.whatsapp_configured" class="muted small">{{ t('Configure the WhatsApp Business API connection in POS Settings to send inside POS. The popup remains available.') }}</p>
      <p v-else-if="settings.whatsapp_enabled && !details.options.can_whatsapp_api" class="muted small">{{ t('Your role is not enabled for WhatsApp Business API sending in POS Settings.') }}</p>
      <p v-if="needsImage && !image" class="muted small">{{ t('Prepare the receipt image below before sending through WhatsApp API.') }}</p>
      <p v-if="settings.sms_enabled && !details.options.sms_configured" class="muted small">{{ t('Configure the SMS gateway in Settings → Customer messaging.') }}</p>
      <p v-else-if="settings.sms_enabled && !details.options.can_sms" class="muted small">{{ t('Your role is not enabled for SMS in the gateway settings.') }}</p>
      <p class="muted small">{{ t('The popup opens WhatsApp separately for you to review and send. API submissions are recorded below; POS does not read your WhatsApp Web chats.') }}</p>
      <p v-if="result" class="message-result" :class="{ notice: result.status === 'Outcome unknown' }" role="status">
        <b>{{ t(result.status) }}</b><span v-if="result.duplicate"> · {{ t('This request was already recorded; it was not sent again.') }}</span><br v-if="result.error" />{{ result.error }}
        <button type="button" class="btn-ghost" @click="newMessage">{{ t('Start another message') }}</button>
      </p>
      <p v-if="error" class="message-error" role="alert">{{ error }}</p>
      <section v-if="invoice && imageSource && settings.image_enabled" class="image-sharing">
        <h4>{{ t('Receipt image') }}</h4>
        <p class="muted small">{{ t('Prepare a PNG to share from your device, or download it and attach it in WhatsApp. SMS sends text and links only.') }}</p>
        <button type="button" class="btn btn-outline" :disabled="busy" @click="prepareImage">{{ t(imageBusy ? 'Preparing image…' : image ? 'Refresh receipt image' : 'Prepare receipt image') }}</button>
        <template v-if="image">
          <img :src="imageUrl" :alt="t('Receipt image preview')" />
          <div class="message-actions"><a class="btn btn-outline" :href="imageUrl" :download="image.name">{{ t('Download PNG') }}</a>
            <button v-if="canShareImage" type="button" class="btn btn-outline" @click="shareImage">{{ t('Share image…') }}</button>
            <button v-if="canCopyImage" type="button" class="btn btn-outline" @click="copyImage">{{ t('Copy image') }}</button>
          </div>
        </template>
      </section>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { call } from '../api'
import { newId } from '../offline'
import { useSessionStore } from '../stores/session'
import { t } from '../i18n'
import { receiptImage, whatsappUrl } from '../customerMessaging'

const props = defineProps({ invoice: String, customer: String, mobileNumber: String, imageSource: Function })
const emit = defineEmits(['recorded'])
const session = useSessionStore()
const details = ref(null), loading = ref(false), loadError = ref(''), mobile = ref(''), message = ref(''), error = ref('')
const sending = ref(false), result = ref(null), imageBusy = ref(false), image = ref(null), imageUrl = ref('')
const deliveryType = ref('Text'), sessionConfirmed = ref(false)
const settings = computed(() => details.value?.options?.config || {})
const busy = computed(() => sending.value || imageBusy.value)
const canSend = computed(() => Boolean(settings.value.enabled && details.value?.options?.ready && !session.offline && !busy.value && mobile.value.trim() && message.value.trim()))
const templateKeys = computed(() => String(settings.value.whatsapp_template_parameters || '').split(',').map(key => key.trim()).filter(Boolean))
const needsImage = computed(() => deliveryType.value === 'Image' || deliveryType.value === 'Template' && Boolean(settings.value.whatsapp_template_image))
const canSendApi = computed(() => canSend.value && details.value.options.whatsapp_configured && details.value.options.can_whatsapp_api &&
  (deliveryType.value === 'Template' ? Boolean(settings.value.whatsapp_template_name) : sessionConfirmed.value) &&
  (!needsImage.value || image.value) && (deliveryType.value !== 'Image' || message.value.length <= 1024))
const canShareImage = computed(() => Boolean(image.value && navigator.canShare?.({ files: [image.value] })))
const canCopyImage = Boolean(navigator.clipboard?.write && window.ClipboardItem)
const submittedSms = computed(() => result.value?.channel === 'SMS' && ['Submitted to gateway', 'Outcome unknown', 'Preparing'].includes(result.value.status))
const submittedWhatsApp = computed(() => result.value?.channel === 'WhatsApp API' && ['Submitted to WhatsApp', 'Outcome unknown', 'Preparing'].includes(result.value.status))
let generation = 0, requests = new Map()
const contextArgs = () => ({ pos_profile: session.posProfile, invoice: props.invoice || null, customer: props.customer || null })

watch(() => [props.invoice, props.customer, props.mobileNumber, session.posProfile], load, { immediate: true })
watch([mobile, message, deliveryType], () => { result.value = null; error.value = '' })
function discardImage() { if (imageUrl.value) URL.revokeObjectURL(imageUrl.value); image.value = null; imageUrl.value = '' }
onBeforeUnmount(() => { generation++; discardImage() })

async function load() {
  const current = ++generation
  loading.value = true; imageBusy.value = false; loadError.value = ''; result.value = null; deliveryType.value = 'Text'; sessionConfirmed.value = false; discardImage(); requests = new Map()
  try {
    const response = await call('esafepos.api.messaging.compose', contextArgs())
    if (current !== generation) return
    details.value = response
    mobile.value = response.mobile || props.mobileNumber || ''
    message.value = response.message || ''
  } catch (e) { if (current === generation) loadError.value = e.message }
  finally { if (current === generation) loading.value = false }
}

function newMessage() { requests = new Map(); result.value = null; error.value = '' }
function requestKey(channel) {
  const signature = JSON.stringify([channel, mobile.value, message.value, contextArgs(), channel === 'WhatsApp API' ? [deliveryType.value, needsImage.value ? image.value?.lastModified : null] : null])
  if (!requests.has(signature)) requests.set(signature, newId())
  return requests.get(signature)
}
async function record(channel) {
  const current = generation
  const args = { ...contextArgs(), channel, mobile: mobile.value, message: message.value, request_key: requestKey(channel),
    delivery_type: deliveryType.value, session_confirmed: sessionConfirmed.value ? 1 : 0 }
  if (channel === 'WhatsApp API' && needsImage.value) {
    const file = image.value
    args.image_data = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(file) })
  }
  const response = await call('esafepos.api.messaging.send_message', args)
  if (current === generation) { result.value = response; emit('recorded', response) }
  return response
}
async function openWhatsApp() {
  error.value = ''
  let popup
  try {
    const url = whatsappUrl(mobile.value, message.value, settings.value.country_code)
    popup = window.open('about:blank', '_blank', settings.value.whatsapp_target === 'Popup' ? 'popup,width=1050,height=780,resizable=yes,scrollbars=yes' : '')
    if (!popup) throw new Error(t('Allow pop-ups to open WhatsApp.'))
    popup.opener = null
    sending.value = true
    await record('WhatsApp')
    popup.location.replace(url)
  } catch (e) { popup?.close(); error.value = e.message }
  finally { sending.value = false }
}
async function sendSms() {
  sending.value = true; error.value = ''
  try { await record('SMS') } catch (e) { error.value = e.message }
  finally { sending.value = false }
}
async function sendWhatsAppApi() {
  sending.value = true; error.value = ''
  try { await record('WhatsApp API') } catch (e) { error.value = e.message }
  finally { sending.value = false }
}
async function copyText(value) {
  try { await navigator.clipboard.writeText(value); session.notify(t('Copied')) }
  catch { error.value = t('Copy was blocked. Select the message or link and copy it manually.') }
}
async function prepareImage() {
  imageBusy.value = true; error.value = ''
  const current = generation
  try {
    const file = await receiptImage(props.imageSource(), props.invoice)
    if (current === generation) { discardImage(); image.value = file; imageUrl.value = URL.createObjectURL(file) }
  } catch (e) { if (current === generation) error.value = e.message }
  finally { if (current === generation) imageBusy.value = false }
}
async function shareImage() {
  try { await navigator.share({ files: [image.value], title: props.invoice }) }
  catch (e) { if (e.name !== 'AbortError') error.value = t('Image sharing is unavailable here. Download the PNG and attach it in WhatsApp.') }
}
async function copyImage() {
  try { await navigator.clipboard.write([new ClipboardItem({ 'image/png': image.value })]); session.notify(t('Receipt image copied')) }
  catch { error.value = t('Image copying is unavailable here. Download the PNG instead.') }
}
</script>

<style scoped>
.message-composer { padding: 16px; min-width: 0; }
header { display: flex; justify-content: space-between; gap: 10px; }
h3 { font-size: 15px; margin: 0 0 4px; } h4 { margin: 0 0 6px; }
p { line-height: 1.5; margin: 6px 0 12px; } .small { font-size: 12px; }
label { display: grid; gap: 6px; margin-top: 12px; font-size: 12px; color: var(--text-muted); }
input, textarea { width: 100%; min-width: 0; color: var(--text); } textarea { resize: vertical; line-height: 1.5; }
select { width: 100%; min-width: 0; } .window-check { display: flex; align-items: flex-start; gap: 8px; line-height: 1.5; } .window-check input { width: auto; margin-top: 2px; }
.template-review { margin-top: 12px; padding: 10px; background: var(--surface-2); font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
.message-meta { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 5px; margin-top: 5px; }
.message-actions { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.message-actions .btn { font-size: 12px; text-decoration: none; justify-content: center; }
.notice, .message-result { padding: 10px; background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; }
.message-error { color: var(--red); }
.image-sharing { border-top: 1px solid var(--border); padding-top: 14px; margin-top: 14px; }
.image-sharing img { display: block; max-width: 100%; max-height: 320px; object-fit: contain; object-position: top; margin-top: 12px; background: white; }
@media (max-width: 500px) { .message-actions .btn { flex: 1 1 120px; } }
</style>
