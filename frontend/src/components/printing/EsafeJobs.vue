<template><section class="print-jobs"><header><h2>{{ t('Print jobs') }}</h2><p>{{ t('Esafe acceptance and Windows spooler status are separate from physical paper output.') }}</p></header><p v-if="error || manager.state.error" class="error" role="alert">{{ error || manager.state.error }}</p><div class="actions"><button class="btn btn-outline" :disabled="busy" @click="run(()=>manager.connect({explicit:true}))">{{ t('Connect / reconnect') }}</button><button class="btn btn-outline" :disabled="busy" @click="run(()=>manager.refreshJobs())">{{ t('Refresh job status') }}</button></div><details v-if="documents.length" class="documents"><summary>{{ t('Invoice and quotation browser fallback') }}</summary><p class="hint">{{ t('Check the original job before printing another copy.') }}</p><div v-for="doc in documents" :key="doc.key" class="actions"><button class="btn btn-outline" :disabled="busy" @click="browserDocument(doc)">{{ t('Open browser print view') }} · {{ doc.name }}</button></div></details><p v-if="!jobs.length" class="hint">{{ t('No print intents for this user and outlet on this workstation.') }}</p><article v-for="job in jobs" :key="job.key" class="job"><div class="job-heading"><strong>{{ job.reference?.name || job.title }}</strong><span>{{ t(job.state) }}</span></div><p>{{ job.role }} · {{ job.printerId }}<span v-if="job.agentJobId"> · {{ job.agentJobId }}</span></p><p v-if="job.state==='completed'" class="hint">{{ t(job.role==='drawer' ? 'Windows reported completion. Physical drawer opening has not been confirmed.' : 'Windows reported completion. Paper output has not been confirmed.') }}</p><p v-if="job.error" class="error">{{ job.error }}</p><p v-if="job.state==='unknown'" class="hint">{{ t(job.role==='drawer' ? 'Inspect the physical drawer and native queue. Nothing is replayed automatically. An identical retry keeps the original key; a new opening requires a separate deliberate action.' : 'Check the printer and refresh status. Nothing is replayed automatically. Retry uses the same bytes and key; reprint creates another copy.') }}</p><div class="actions"><button v-if="['prepared','failed','unknown'].includes(job.state) && !job.agentJobId && job.request" class="btn btn-outline" :disabled="busy" @click="run(()=>manager.retry(job.key))">{{ t('Retry identical intent') }}</button><button v-if="job.agentJobId && ['queued','preparing'].includes(job.state)" class="btn btn-outline" :disabled="busy" @click="run(()=>manager.cancel(job.key))">{{ t('Request cancellation') }}</button><button v-if="job.agentJobId && mayReprint(job)" class="btn btn-outline" :disabled="busy" @click="reprint(job)">{{ t('Reprint — new copy') }}</button></div></article></section></template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useSessionStore } from '../../stores/session'
import { t } from '../../i18n'
import { call } from '../../api'
import { printManager as manager } from '../../printing/index.js'
const session=useSessionStore(),busy=ref(false),error=ref('')
const belongsHere=(row)=>row.user===session.user && row.profile===session.posProfile
const jobs=computed(()=>manager.state.jobs.filter(belongsHere))
const documents=computed(()=>manager.state.documents.filter(belongsHere))
function mayReprint(job){return job.role!=='drawer' && (job.role!=='receipt' || session.permissions.can_reprint!==false)}
async function run(fn){if(busy.value)return;busy.value=true;error.value='';try{await fn()}catch(e){error.value=e.message}finally{busy.value=false}}
function reprint(job){if(window.confirm(t('This creates another copy. Check the printer first. Continue?')))return run(()=>manager.reprint(job.key))}
function browserDocument(doc){
  if(busy.value || !window.confirm(t('The original job may already have printed. Open a separate browser print view?')))return
  const tab=window.open('','_blank')
  if(!tab){error.value=t('Allow pop-ups to open the print view.');return}
  tab.opener=null
  return run(async()=>{
    try{const result=await call('esafepos.api.esafe_printing.document_printview',{doctype:doc.doctype,name:doc.name});tab.location.href=result.url}
    catch(e){tab.close();throw e}
  })
}
onMounted(()=>run(()=>manager.resume()))
</script>
<style scoped>
.documents{font-size:12px;margin:20px 0}.documents summary{cursor:pointer;font-weight:600}.print-jobs{padding:22px;max-width:1100px;margin:auto}h2{font-size:18px;margin:0}header p,.hint{font-size:12px;color:var(--text-muted);line-height:1.7}.actions{display:flex;flex-wrap:wrap;gap:9px;margin:16px 0}.job{padding:20px 0;border-top:1px solid var(--border);font-size:12px;overflow-wrap:anywhere}.job-heading{display:flex;justify-content:space-between;gap:15px}.job p{color:var(--text-muted);line-height:1.7}.job .error,.error{color:var(--red)}@media(max-width:520px){.print-jobs{padding:16px 14px}.actions>.btn{width:100%}}
</style>
