<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only -->
<template>
  <section class="qz-card">
    <div class="qz-head">
      <div>
        <h4>{{ t('QZ Tray local printing') }}</h4>
        <p class="muted small">{{ t('Print the built-in receipt directly to a printer installed on this Windows computer.') }}</p>
      </div>
      <span class="qz-state" :class="{ connected }">{{ connected ? t('Connected') : t('Not connected') }}</span>
    </div>

    <div class="qz-controls">
      <button class="btn btn-outline" :disabled="busy" @click="refreshPrinters">
        {{ busy ? t('Connecting.') : t('Connect and find printers') }}
      </button>
      <label class="field qz-select">
        <span>{{ t('Windows printer on this computer') }}</span>
        <select v-model="selected" @change="saveSelectedQzPrinter(selected)">
          <option value="">{{ t('Choose a printer') }}</option>
          <option v-for="printer in printers" :key="printer" :value="printer">{{ printer }}</option>
        </select>
      </label>
      <button class="btn btn-primary" :disabled="busy || !selected" @click="testPrint">
        {{ t('Print test receipt') }}
      </button>
    </div>

    <p v-if="statusMessage" class="muted small qz-message">{{ statusMessage }}</p>
    <p class="muted small qz-note">
      {{ signingConfigured
        ? t('Silent printing is configured with a server-signed QZ certificate.')
        : t('QZ Tray can print after you approve its prompt. Upload trusted signing files below to remove print prompts.') }}
    </p>
    <p v-if="printFormat" class="muted small qz-note">{{ t('This outlet uses an ERPNext Print Format, which stays on the ERPNext print path. QZ Tray currently handles the built-in receipt.') }}</p>

    <div v-if="canManage" class="qz-signing">
      <label class="field">
        <span>{{ t('QZ digital certificate (.txt or .crt)') }}</span>
        <input type="file" accept=".txt,.crt,.pem,text/plain,application/x-pem-file" @change="readCertificate" />
        <small class="muted">{{ certificateName || (signingConfigured ? t('Certificate already saved') : t('No certificate saved')) }}</small>
      </label>
      <label class="field">
        <span>{{ t('Matching private key (.pem)') }}</span>
        <input type="file" accept=".pem,application/x-pem-file,text/plain" @change="readPrivateKey" />
        <small class="muted">{{ privateKeyName || (signingConfigured ? t('Private key already saved securely') : t('No private key saved')) }}</small>
      </label>
      <div class="qz-actions">
        <button class="btn btn-outline" :disabled="saving || (!certificateText && !privateKeyText)" @click="saveSigning">
          {{ saving ? t('Saving.') : t('Save QZ signing files') }}
        </button>
        <button v-if="signingConfigured" class="btn btn-ghost" :disabled="saving" @click="clearSigning">{{ t('Remove signing files') }}</button>
      </div>
      <p class="muted small qz-security">{{ t('The private key is encrypted in EsafePOS Settings and is never returned to this browser. Use your production QZ certificate for silent printing on multiple tills.') }}</p>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { call } from '../api'
import { t } from '../i18n'
import { connectQz, findQzPrinters, printQzTest, saveSelectedQzPrinter, selectedQzPrinter } from '../qzPrinting'

defineProps({ canManage: { type: Boolean, default: false }, printFormat: { type: String, default: '' } })

const connected = ref(false)
const initialPrinter = selectedQzPrinter()
const printers = ref(initialPrinter ? [initialPrinter] : [])
const selected = ref(initialPrinter)
const signingConfigured = ref(false)
const statusMessage = ref('')
const busy = ref(false)
const saving = ref(false)
const certificateText = ref('')
const privateKeyText = ref('')
const certificateName = ref('')
const privateKeyName = ref('')

onMounted(async () => {
  try {
    const status = await call('esafepos.api.qz_printing.get_signing_certificate')
    signingConfigured.value = Boolean(status?.configured)
  } catch {
    statusMessage.value = t('Run the site migration to enable QZ Tray signing.')
  }
})

async function refreshPrinters() {
  busy.value = true
  statusMessage.value = ''
  try {
    const result = await findQzPrinters()
    printers.value = result.printers || []
    connected.value = true
    if (selected.value && !printers.value.includes(selected.value)) {
      printers.value = [selected.value, ...printers.value]
    }
    statusMessage.value = result.signed
      ? t('QZ Tray connected. Signing is active.')
      : t('QZ Tray connected. Approve its prompt for each print until signing is configured.')
  } catch (error) {
    connected.value = false
    statusMessage.value = error.message || t('Could not connect to QZ Tray. Check that it is running on this computer.')
  } finally {
    busy.value = false
  }
}

async function readFile(file, assign) {
  if (!file) return
  assign(await file.text())
}

async function readCertificate(event) {
  const file = event.target.files?.[0]
  if (!file) return
  await readFile(file, (text) => { certificateText.value = text })
  certificateName.value = file.name
}

async function readPrivateKey(event) {
  const file = event.target.files?.[0]
  if (!file) return
  await readFile(file, (text) => { privateKeyText.value = text })
  privateKeyName.value = file.name
}

async function saveSigning() {
  saving.value = true
  try {
    const result = await call('esafepos.api.qz_printing.save_signing_config', {
      certificate: certificateText.value,
      private_key: privateKeyText.value,
    })
    signingConfigured.value = Boolean(result?.configured)
    certificateText.value = ''
    privateKeyText.value = ''
    certificateName.value = ''
    privateKeyName.value = ''
    statusMessage.value = t('QZ signing files saved. Reconnect QZ Tray to activate silent printing.')
  } catch (error) {
    statusMessage.value = error.message || t('Could not save the QZ signing files.')
  } finally {
    saving.value = false
  }
}

async function clearSigning() {
  saving.value = true
  try {
    await call('esafepos.api.qz_printing.save_signing_config', { clear: 1 })
    signingConfigured.value = false
    statusMessage.value = t('QZ signing files removed.')
  } catch (error) {
    statusMessage.value = error.message || t('Could not remove the QZ signing files.')
  } finally {
    saving.value = false
  }
}

async function testPrint() {
  busy.value = true
  statusMessage.value = ''
  try {
    const result = await printQzTest(selected.value)
    connected.value = true
    statusMessage.value = result.signed ? t('Test receipt sent silently.') : t('Test receipt sent. QZ Tray may ask you to approve it.')
  } catch (error) {
    statusMessage.value = error.message || t('Could not send the test receipt.')
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.qz-card { margin: 12px 0 18px; padding: 14px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface-2); display: flex; flex-direction: column; gap: 10px; }
.qz-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.qz-head h4 { margin: 0; }
.qz-head p { margin: 4px 0 0; }
.qz-state { border: 1px solid var(--border); border-radius: 999px; padding: 4px 9px; white-space: nowrap; font-size: 12px; }
.qz-state.connected { color: var(--green); border-color: var(--green); }
.qz-controls { display: grid; grid-template-columns: auto minmax(180px, 1fr) auto; align-items: end; gap: 10px; }
.qz-select { min-width: 0; }
.qz-select select { width: 100%; }
.qz-message, .qz-note, .qz-security { margin: 0; }
.qz-signing { padding-top: 10px; border-top: 1px solid var(--border); display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.qz-signing .field { min-width: 0; }
.qz-signing input[type="file"] { max-width: 100%; }
.qz-actions { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 8px; }
.qz-security { grid-column: 1 / -1; }
@media (max-width: 620px) {
  .qz-controls, .qz-signing { grid-template-columns: 1fr; }
  .qz-controls > button { width: 100%; }
  .qz-actions, .qz-security { grid-column: auto; }
}
</style>
