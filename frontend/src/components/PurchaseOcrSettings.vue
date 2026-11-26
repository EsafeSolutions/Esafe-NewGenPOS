<template>
  <form class="ocr-settings" @submit.prevent="save">
    <p class="muted">{{ t('Read supplier invoices from photos and PDFs, then check the detected items before filling a purchase draft. The selected document is sent to Google Gemini.') }}</p>
    <fieldset :disabled="busy || !loaded">
      <label class="ocr-toggle"><input v-model="enabled" type="checkbox" />{{ t('Enable purchase invoice scanning') }}</label>
      <label>{{ t('Gemini API key') }}<input v-model.trim="key" type="password" autocomplete="new-password" maxlength="256" :placeholder="configured ? t('Key saved. Leave blank to keep it.') : t('Paste your Gemini API key')" /></label>
      <label>{{ t('Gemini model') }}<input v-model.trim="model" required maxlength="90" placeholder="gemini-3.5-flash-lite" /></label>
      <label v-if="configured" class="ocr-toggle"><input v-model="clearKey" type="checkbox" />{{ t('Remove the saved key') }}</label>
      <p class="muted">{{ t('The key is stored as an encrypted server password and is never returned to the browser. Scanning is separate from product image search. Google API charges and quota apply.') }}</p>
      <button type="submit" class="btn btn-primary">{{ t(busy ? 'Saving…' : 'Save invoice scanning settings') }}</button>
    </fieldset>
    <p v-if="message" :role="failed ? 'alert' : 'status'">{{ message }}</p>
    <button v-if="!loaded && !busy" type="button" class="btn btn-outline" @click="load">{{ t('Retry settings') }}</button>
  </form>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { call } from '../api'
import { t } from '../i18n'
const emit = defineEmits(['saved'])
const enabled = ref(false), configured = ref(false), key = ref(''), model = ref('gemini-3.5-flash-lite'), clearKey = ref(false)
const loaded = ref(false), busy = ref(false), message = ref(''), failed = ref(false)
function apply(config) { enabled.value = config.enabled; configured.value = config.configured; model.value = config.model }
async function load() {
  busy.value = true; message.value = ''; failed.value = false
  try { apply(await call('esafepos.api.purchase_ocr.get_config')); loaded.value = true }
  catch (e) { message.value = e.message; failed.value = true }
  finally { busy.value = false }
}
async function save() {
  if (busy.value || !loaded.value) return
  busy.value = true; message.value = ''; failed.value = false
  try {
    apply(await call('esafepos.api.purchase_ocr.save_config', { enabled: enabled.value, api_key: key.value, model: model.value, clear_key: clearKey.value }))
    key.value = ''; clearKey.value = false; message.value = t('Invoice scanning settings saved.'); emit('saved')
  } catch (e) { message.value = e.message; failed.value = true }
  finally { busy.value = false }
}
onMounted(load)
</script>

<style scoped>
.ocr-settings { max-width: 680px; }
.ocr-settings fieldset { border: 0; margin: 0; padding: 0; display: grid; gap: 16px; }
.ocr-settings label { display: grid; gap: 7px; font-size: 13px; font-weight: 600; }
.ocr-settings .ocr-toggle { display: flex; gap: 10px; align-items: center; }
.ocr-settings input:not([type='checkbox']) { width: 100%; min-height: 44px; color: var(--text); background: var(--input-bg); border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; box-sizing: border-box; font: inherit; }
.ocr-settings p { font-size: 13px; line-height: 1.6; }
.ocr-settings button { justify-self: start; }
</style>
