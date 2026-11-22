<!-- Copyright (c) 2026 Esafe (PVT) LTD; SPDX-License-Identifier: AGPL-3.0-only -->
<template>
  <section class="printer-settings">
    <header><h2>{{ t('Printer settings') }}</h2><p>{{ t('Choose how each outlet prints receipts and documents.') }}</p></header>
    <p v-if="session.offline" class="notice">{{ t('Connect to change printer settings.') }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
    <label class="field outlet"><span>{{ t('Outlet') }}</span><select v-model="profile" :aria-label="t('Outlet')" :disabled="loading || saving || session.offline" @change="loadProfile"><option v-for="name in profiles" :key="name" :value="name">{{ name }}</option></select></label>
    <p v-if="loading" class="notice" role="status">{{ t('Loading printer settings…') }}</p>
    <p v-else-if="!profile" class="notice">{{ t('No outlets are available for printer setup.') }}</p>
    <template v-if="loaded">
      <EsafePrinterSetup :key="profile" :profile="profile" :defaults="esafeDefaults" :can-write="canWrite" :needs-migration="esafeNeedsMigration" :offline="session.offline" @saved="esafeDefaults=$event" />
      <fieldset :disabled="!canWrite || loading || saving || session.offline">
        <section class="setup-section">
          <h3>{{ t('Server network printer') }}</h3>
          <p>{{ t('Leave the network address empty to use the Print Format or browser print window.') }}</p>
          <div class="fields"><label class="field"><span>{{ t('Printer IP address or hostname') }}</span><input v-model="form.host" maxlength="253" autocomplete="off" placeholder="192.168.1.100" /></label><label class="field port"><span>{{ t('Printer port') }}</span><input v-model="form.port" type="number" min="1" max="65535" step="1" /></label></div>
          <p class="hint">{{ t('Network receipts use ESC/POS. The printer must be reachable from the ERPNext server; a cloud server may not reach your shop network.') }}</p>
          <p v-if="needsMigration" class="error">{{ t('Run the site migration before changing printer settings.') }}</p>
        </section>
        <section class="setup-section">
          <h3>{{ t('Print Format') }}</h3><p>{{ t('Choose an ERPNext layout for PDF documents. Esafe uses the receipt output selected above. When silent printing is off, the server network printer takes priority.') }}</p>
          <label class="field format"><span>{{ t('Receipt and document format') }}</span><select v-model="form.print_format" :aria-label="t('Receipt and document format')"><option value="">{{ t('Built-in receipt') }}</option><option v-for="name in formatChoices" :key="name" :value="name">{{ name }}</option></select></label>
          <p class="hint">{{ t('Formats match the outlet’s sale document type: {doctype}.', {doctype:invoiceDoctype}) }}</p>
        </section>
      </fieldset>
      <p v-if="!canWrite" class="notice">{{ t('You need permission to edit this POS Profile to change its printer setup.') }}</p>
      <div class="actions"><button class="btn btn-primary" :disabled="!editable" @click="save">{{ saving ? t('Saving…') : t('Save printer settings') }}</button><button class="btn btn-outline" :disabled="!editable || !savedHost || dirty" @click="test">{{ t('Print test receipt') }}</button><span v-if="dirty && form.host" class="hint">{{ t('Save changes before printing a test.') }}</span></div>
    </template>
    <section class="setup-section browser-section"><h3>{{ t('Browser and label printing') }}</h3><p>{{ t('Browser printing remains an explicit option. Match the paper size, use 100% scale and turn off browser headers and footers. Esafe silent printing uses the workstation assignments above.') }}</p><button v-if="session.settings.enable_labels && session.permissions.print_labels" class="text-btn" @click="$emit('labels')">{{ t('Open labels and calibration') }}</button></section>
  </section>
</template>
<script setup>
import { computed, onActivated, onMounted, ref } from 'vue'
import EsafePrinterSetup from './EsafePrinterSetup.vue'
import { call } from '../../api'
import { t } from '../../i18n'
import { useSessionStore } from '../../stores/session'
defineEmits(['labels'])
const session=useSessionStore(),profiles=ref([]),profile=ref(''),form=ref({host:'',port:9100,print_format:''}),formats=ref([])
const loading=ref(false),saving=ref(false),loaded=ref(false),error=ref(''),notice=ref(''),canWrite=ref(false),needsMigration=ref(false),invoiceDoctype=ref(''),snapshot=ref(''),savedHost=ref('')
const esafeDefaults=ref({}),esafeNeedsMigration=ref(false)
const formatChoices=computed(() => [...new Set([...formats.value,form.value.print_format].filter(Boolean))])
const dirty=computed(() => JSON.stringify(form.value)!==snapshot.value)
const editable=computed(() => canWrite.value && loaded.value && !loading.value && !saving.value && !session.offline && !needsMigration.value)
function apply(data){form.value={host:data.host || '',port:data.port || 9100,print_format:data.print_format || ''};formats.value=data.formats || [];canWrite.value=!!data.can_write;needsMigration.value=!!data.needs_migration;esafeDefaults.value=data.esafe || {};esafeNeedsMigration.value=!!data.esafe_needs_migration;invoiceDoctype.value=data.invoice_doctype;snapshot.value=JSON.stringify(form.value);savedHost.value=form.value.host;loaded.value=true}
async function loadProfile(){
  if(!profile.value || session.offline)return
  loading.value=true;loaded.value=false;error.value='';notice.value=''
  try{apply(await call('esafepos.api.printing_settings.get_printer_settings',{pos_profile:profile.value}))}catch(e){error.value=e.message}finally{loading.value=false}
}
async function load(){
  if(session.offline)return
  loading.value=true
  try{const data=await call('esafepos.api.printing_settings.receipt_workspace');profiles.value=data.profiles || [];profile.value=profiles.value.includes(session.posProfile) ? session.posProfile : profiles.value[0] || ''}catch(e){error.value=e.message}finally{loading.value=false}
  await loadProfile()
}
async function save(){
  if(!editable.value)return
  saving.value=true;error.value='';notice.value=''
  try{const data=await call('esafepos.api.printing_settings.save_printer_settings',{pos_profile:profile.value,...form.value});apply(data);if(profile.value===session.posProfile){session.printerConfigured=!!data.host;session.printFormat=data.print_format || null}notice.value=t('Printer settings saved.')}catch(e){error.value=e.message}finally{saving.value=false}
}
async function test(){
  if(!editable.value || dirty.value || !savedHost.value)return
  saving.value=true;error.value='';notice.value=''
  try{await call('esafepos.api.printing_settings.test_printer',{pos_profile:profile.value});notice.value=t('Test receipt sent. Check the printer for completion.')}catch(e){error.value=e.message}finally{saving.value=false}
}
onMounted(load)
onActivated(()=>{if(!loaded.value && !loading.value && session.offline===false && !profiles.value.length)load()})
</script>
<style scoped>
.printer-settings{padding:22px;max-width:1080px;margin:0 auto;width:100%;box-sizing:border-box}h2{font-size:18px;margin:0}header p,.setup-section>p{font-size:13px;color:var(--text-muted);line-height:1.7;margin:7px 0 18px}h3{font-size:14px;margin:0}fieldset{border:0;padding:0;margin:0;min-width:0}.outlet{max-width:400px;margin:24px 0}.field{display:flex;flex-direction:column;gap:7px;min-width:0}.field>span{font-size:12px;color:var(--text-muted)}input,select{width:100%;box-sizing:border-box;padding:10px;border:1px solid var(--border);border-radius:var(--radius);background:var(--input-bg);color:var(--text);font:inherit;font-size:13px}.fields{display:flex;gap:16px;max-width:650px}.fields>.field{flex:1}.fields>.port{flex:0 0 140px}.format{max-width:650px}.setup-section{padding:24px 0;border-top:1px solid var(--border)}.hint{font-size:12px!important;line-height:1.7;color:var(--text-muted);margin:10px 0 0!important}.actions{display:flex;flex-wrap:wrap;gap:12px;align-items:center;padding-bottom:24px}.notice{font-size:13px;color:var(--text-muted);line-height:1.65}.error{font-size:13px;color:var(--red)}.text-btn{color:var(--brand-dark);font-size:13px;font-weight:600;padding:0}.browser-section{padding-bottom:10px}
@media(max-width:520px){.printer-settings{padding:16px 14px}.fields{flex-direction:column}.fields>.port{flex:auto}.actions .btn{width:100%}}
</style>
