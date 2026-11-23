<!-- Copyright (c) 2026 Esafe (PVT) LTD; SPDX-License-Identifier: AGPL-3.0-only -->
<template>
  <section class="esafe-setup">
    <div class="setup-heading"><div><h3>{{ t('Esafe Print Manager') }}</h3><p>{{ t('Print directly to printers installed on this workstation.') }}</p></div><span class="state">{{ t(manager.state.connection) }}</span></div>
    <p v-if="error || manager.state.error" class="error" role="alert">{{ error || manager.state.error }}</p>
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
    <div class="actions"><button class="btn btn-outline" :disabled="busy || connecting" @click="connect">{{ connecting ? t('Connecting…') : t('Connect / reconnect') }}</button><button class="btn btn-outline" :disabled="busy || manager.state.connection!=='connected'" @click="refresh">{{ t('Refresh printers') }}</button><button v-if="manager.state.connection==='connected'" class="text-btn" @click="manager.disconnect()">{{ t('Disconnect') }}</button></div>
    <details class="guide"><summary>{{ t('First connection and troubleshooting') }}</summary><ol><li>{{ t('Install and start Esafe Printer Manager for Windows.') }}</li><li>{{ t('In the manager’s native Settings, install its local certificate after reviewing the trust prompt.') }}</li><li>{{ t('Click Connect here. Allow browser local-network access if requested and approve this exact ERP website in Esafe.') }}</li><li>{{ t('Choose printers below, then approve the updated printer permissions in the native manager.') }}</li></ol><p>{{ t('Approval belongs to this website and browser profile. A new browser profile, changed site address or revoked approval needs a fresh connection.') }}</p><p>{{ t('Esafe Printer Manager 0.2.1 uses SDK 0.2.0 and protocol 1. The supplied native releases require workstation qualification. Your administrator must qualify the installer and printer drivers before production use.') }}</p></details>
    <fieldset :disabled="busy || !canWrite || needsMigration || offline">
      <label class="check"><input v-model="config.silent" type="checkbox" />{{ t('Use Esafe silent printing for this outlet') }}</label>
      <label class="check"><input v-model="config.automatic_receipt" type="checkbox" :disabled="!config.silent" />{{ t('Automatically print the receipt after a successful sale') }}</label>
      <div class="fields"><label class="field"><span>{{ t('Receipt output') }}</span><select v-model="config.receipt_output" :aria-label="t('Receipt output')"><option value="html">{{ t('Built-in receipt (HTML)') }}</option><option value="pdf">{{ t('ERPNext Print Format (PDF)') }}</option><option value="raw">{{ t('ESC/POS raw — verified printer encoding only') }}</option></select></label><label class="field copies"><span>{{ t('Copies') }}</span><input v-model.number="config.copies" type="number" min="1" max="99" step="1" /></label><label class="field"><span>{{ t('Document paper') }}</span><select v-model="config.document_paper" :aria-label="t('Document paper')"><option>A4</option><option>Letter</option></select></label></div>
      <p class="hint">{{ t('Receipt width comes from Printing → Receipt (58 mm or 80 mm). Use HTML/PDF for Sinhala, Tamil and other complex scripts. Raw printing uses printer-specific encoding and commands.') }}</p>
      <button class="btn btn-primary" :disabled="!canWrite || busy || needsMigration || offline" @click="saveDefaults">{{ t('Save silent-printing defaults') }}</button>
    </fieldset>
    <p v-if="needsMigration" class="error">{{ t('Run the site migration to add the Esafe defaults and print-intent records.') }}</p>
    <fieldset :disabled="busy || !canWrite || offline || manager.state.connection!=='connected'">
      <h4>{{ t('Printer assignments on this workstation') }}</h4><p class="hint">{{ t('These assignments belong to this ERP site, outlet and browser. Other workstations keep their own printer choices.') }}</p>
      <label v-for="role in roles" :key="role.key" class="field"><span>{{ t(role.label) }}</span><select v-model="selection[role.key]" :aria-label="t(role.label)" @change="selectRole(role.key)"><option value="">{{ t('Choose a printer') }}</option><option v-for="printer in manager.state.printers" :key="printer.id" :value="printer.id">{{ printer.name }}{{ printer.isDefault ? ' ('+t('Windows default')+')' : '' }}</option><option v-if="selection[role.key] && !manager.state.printers.some((p)=>p.id===selection[role.key])" :value="selection[role.key]">{{ t('Missing printer — select again') }}</option></select></label>
      <p v-if="legacy" class="hint">{{ t('Previous receipt printer: {name}. Select its exact installed queue and approve it before printing.',{name:legacy}) }}</p>
      <p v-if="info" class="hint">{{ info.driver }} · {{ info.port }} · {{ t('Driver status is not confirmation of paper output.') }}</p>
      <template v-if="info && selection[optionsRole]"><label class="field"><span>{{ t('Driver options for') }}</span><select v-model="optionsRole" :aria-label="t('Driver options for')" @change="inspect(selection[optionsRole])"><option value="receipt">{{ t('Receipts') }}</option><option value="document">{{ t('Invoices / A4') }}</option><option value="report">{{ t('Reports') }}</option></select></label><div v-if="optionsRole!=='receipt' || config.receipt_output!=='raw'" class="fields"><label class="field"><span>{{ t('Orientation') }}</span><select v-model="driverOptions.orientation" :aria-label="t('Orientation')"><option value="portrait">{{ t('Portrait') }}</option><option value="landscape">{{ t('Landscape') }}</option></select></label><label v-if="info.duplex" class="field"><span>{{ t('Duplex') }}</span><select v-model="driverOptions.duplex" :aria-label="t('Duplex')"><option value="none">{{ t('One side') }}</option><option value="long-edge">{{ t('Long edge') }}</option><option value="short-edge">{{ t('Short edge') }}</option></select></label><label v-if="info.color" class="check"><input v-model="driverOptions.color" type="checkbox" />{{ t('Color output') }}</label></div><p v-else class="hint">{{ t('Raw jobs use copies only. Layout, cutting and encoding are contained in the raw printer bytes.') }}</p></template>
      <div class="actions"><button class="btn btn-primary" :disabled="!canWrite || busy" @click="saveAssignment">{{ t('Approve and save workstation printers') }}</button><button class="btn btn-outline" :disabled="busy || !selection.receipt || assignmentsDirty" @click="test">{{ t('Silent test receipt') }}</button><button class="btn btn-outline" :disabled="busy || !selection.receipt || assignmentsDirty" @click="preview">{{ t('Preview test') }}</button></div>
    </fieldset>
    <CashDrawerSetup :profile="profile" :can-write="canWrite" :needs-migration="needsMigration" :offline="offline" />
    <details class="guide" @toggle="loadEnvironment"><summary>{{ t('Installed ERP and printing versions') }}</summary><p v-if="environment">Frappe {{ environment.frappe }} · ERPNext {{ environment.erpnext }} · EsafePOS {{ environment.esafepos }} · SDK {{ environment.sdk }} · Protocol {{ environment.protocol }}<br />{{ environment.installed_apps?.join(', ') }}</p><p v-else>{{ environmentError || t('Open to load version information from this ERP site.') }}</p></details>
    <img v-if="previewUrl" class="test-preview" :src="previewUrl" :alt="t('Esafe test preview')" />
  </section>
</template>
<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import CashDrawerSetup from './CashDrawerSetup.vue'
import { call } from '../../api'
import { t } from '../../i18n'
import { useSessionStore } from '../../stores/session'
import { printManager as manager, printStatusMessage } from '../../printing/index.js'
const props=defineProps({profile:String,defaults:Object,canWrite:Boolean,needsMigration:Boolean,offline:Boolean})
const emit=defineEmits(['saved'])
const session=useSessionStore(),busy=ref(false),error=ref(''),notice=ref(''),selection=ref({receipt:'',labels:'',document:'',report:''}),saved=ref(''),legacy=ref(''),info=ref(null),previewUrl=ref('')
const config=ref({silent:false,automatic_receipt:false,receipt_output:'html',copies:1,document_paper:'A4'})
const optionsRole=ref('receipt'),environment=ref(null),environmentError=ref('')
let loadGeneration=0
const driverOptions=computed(()=>selection.value.options?.[optionsRole.value] || {})
function withOptions(value){return {...value,options:Object.fromEntries(['receipt','document','report'].map((role)=>[role,{orientation:'portrait',duplex:'none',color:false,...value.options?.[role]}]))}}
const roles=[{key:'receipt',label:'Default receipt printer'},{key:'labels',label:'Label printer'},{key:'document',label:'Invoice / A4 printer'},{key:'report',label:'Reports and payment receipts printer'}]
const connecting=computed(()=>['connecting','approving'].includes(manager.state.connection))
const assignmentsDirty=computed(()=>JSON.stringify(selection.value)!==saved.value)
async function run(fn){busy.value=true;error.value='';notice.value='';try{await fn()}catch(e){error.value=e.message}finally{busy.value=false}}
async function load(){
  const generation=++loadGeneration,profile=props.profile
  config.value={silent:false,automatic_receipt:false,receipt_output:'html',copies:1,document_paper:'A4',...props.defaults}
  const value=await manager.binding(profile)
  if(generation!==loadGeneration || profile!==props.profile)return
  selection.value=withOptions(value);saved.value=JSON.stringify(selection.value);info.value=null
  if(manager.state.connection==='connected')inspect(selection.value[optionsRole.value])
  try{legacy.value=localStorage.getItem('esafepos.qz-printer.v1') || ''}catch{}
}
function selectRole(role){if(role!=='labels')optionsRole.value=role;inspect(selection.value[optionsRole.value])}
async function loadEnvironment(event){
  if(!event.target.open || environment.value || props.offline)return
  try{environment.value=await call('esafepos.api.esafe_printing.environment')}catch(e){environmentError.value=e.message}
}
function connect(){return run(async()=>{await manager.resume();await manager.connect({explicit:true})})}
function refresh(){return run(()=>manager.refreshPrinters())}
async function inspect(id){info.value=null;if(!id)return;try{const value=await manager.capabilities(id);if(selection.value[optionsRole.value]===id)info.value=value}catch(e){error.value=e.message}}
function saveDefaults(){return run(async()=>{const value=await call('esafepos.api.printing_settings.save_esafe_defaults',{pos_profile:props.profile,values:config.value});if(props.profile===session.posProfile)session.settings.esafe_printing=value;emit('saved',value);notice.value=t('Silent-printing defaults saved.')})}
function saveAssignment(){return run(async()=>{selection.value=withOptions(await manager.saveBinding(props.profile,selection.value,()=>call('esafepos.api.printing_settings.authorize_workstation_setup',{pos_profile:props.profile})));saved.value=JSON.stringify(selection.value);notice.value=t('Workstation printer assignments saved.')})}
const testHtml='<!doctype html><html><head><meta charset="UTF-8"><style>@page{size:80mm 50mm;margin:3mm}body{font:14px Arial}</style></head><body><h2>ESAFE POS</h2><p>Esafe Print Manager test</p><p>Printer test only. No sale or cash-drawer pulse.</p></body></html>'
function test(){return run(async()=>{const result=await manager.dispatch({key:crypto.randomUUID(),profile:props.profile,role:'receipt',format:'html',data:testHtml,title:'ESAFE printer test',options:{copies:1,size:{width:80,height:50},margins:3},reference:{doctype:'POS Profile',name:props.profile},user:session.user});notice.value=t(printStatusMessage(result))})}
function preview(){return run(async()=>{const result=await manager.preview(props.profile,'receipt','html',testHtml,{size:{width:80,height:50},margins:3});previewUrl.value=`data:image/png;base64,${result.dataBase64}`})}
watch(()=>[props.profile,props.defaults],load)
onMounted(load)
</script>
<style scoped>
.esafe-setup{border-top:1px solid var(--border);padding:24px 0}.setup-heading{display:flex;align-items:start;justify-content:space-between;gap:14px}h3{font-size:16px;margin:0}h4{font-size:13px;margin:16px 0 8px}p,.hint,ol{font-size:12px;line-height:1.7;color:var(--text-muted)}.state{font-size:11px;padding:5px 9px;border:1px solid var(--border);border-radius:var(--radius)}.actions{display:flex;flex-wrap:wrap;gap:9px;margin:16px 0}.guide{font-size:12px;margin:20px 0}.guide summary{cursor:pointer;font-weight:600}fieldset{border:0;border-top:1px solid var(--border);padding:20px 0 0;margin:20px 0 0;min-width:0}.check{display:flex;gap:9px;align-items:center;font-size:13px;margin-bottom:15px}.check input{width:16px;flex:none}.fields{display:flex;gap:12px;flex-wrap:wrap}.field{display:flex;flex-direction:column;gap:6px;min-width:0;margin:14px 0;font-size:12px;flex:1}.field>span{color:var(--text-muted)}input,select{width:100%;box-sizing:border-box;padding:9px;background:var(--input-bg);color:var(--text);border:1px solid var(--border);border-radius:var(--radius);font:inherit}.copies{max-width:100px}.error{color:var(--red)}.notice{color:var(--brand-dark)}.text-btn{color:var(--brand-dark);font-size:12px}.test-preview{display:block;max-width:320px;width:100%;border:1px solid var(--border);margin-top:20px}@media(max-width:520px){.fields{flex-direction:column;gap:0}.copies{max-width:none}.actions>.btn{width:100%}.setup-heading{flex-direction:column}}
</style>
