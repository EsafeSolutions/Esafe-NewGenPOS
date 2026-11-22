<!-- Copyright (c) 2026 Esafe (PVT) LTD; SPDX-License-Identifier: AGPL-3.0-only -->
<template>
  <section class="printing-workspace">
    <header class="printing-header">
      <div><h1>{{ t('Printing') }}</h1><p>{{ t('Labels, receipt design and printer settings.') }}</p></div>
      <nav v-if="sections.length" class="printing-tabs" role="tablist" :aria-label="t('Printing sections')">
        <button v-for="item in sections" :id="`printing-tab-${item.key}`" :key="item.key" role="tab"
          :aria-selected="activeSection===item.key" aria-controls="printing-panel" :tabindex="activeSection===item.key ? 0 : -1"
          :class="{active:activeSection===item.key}" @click="selectSection(item.key)" @keydown="tabKey($event,item.key)">
          <Icon :name="item.icon" />{{ t(item.label) }}
        </button>
      </nav>
    </header>
    <div v-if="!sections.length" class="printing-empty">{{ t('You do not have access to printing settings or labels.') }}</div>
    <div v-else id="printing-panel" class="printing-panel" role="tabpanel" :aria-labelledby="`printing-tab-${activeSection}`">
      <KeepAlive><component :is="activeComponent" :key="activeSection" @labels="selectSection('labels')" /></KeepAlive>
    </div>
  </section>
</template>
<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSessionStore } from '../stores/session'
import { t } from '../i18n'
import Icon from '../components/Icon.vue'
import LabelsView from './LabelsView.vue'
import ReceiptSettings from '../components/printing/ReceiptSettings.vue'
import PrinterSettings from '../components/printing/PrinterSettings.vue'
import EsafeJobs from '../components/printing/EsafeJobs.vue'

const session=useSessionStore(),route=useRoute(),router=useRouter()
const sections=computed(() => [
  ...(!session.reportsOnly && session.settings.enable_labels && session.permissions.print_labels ? [{key:'labels',label:'Labels',icon:'tag'}] : []),
  ...(session.permissions.settings ? [{key:'receipt',label:'Receipt',icon:'image'},{key:'printers',label:'Printers',icon:'printer'}] : []),
  ...(session.settings.esafe_printing?.silent ? [{key:'jobs',label:'Print jobs',icon:'list'}] : []),
])
const activeSection=computed(() => sections.value.some((s) => s.key===route.query.section) ? route.query.section : sections.value[0]?.key)
const activeComponent=computed(() => ({labels:LabelsView,receipt:ReceiptSettings,printers:PrinterSettings,jobs:EsafeJobs})[activeSection.value])
function selectSection(section){if(sections.value.some((s) => s.key===section))router.replace({path:'/printing',query:{section}})}
function tabKey(event,key){
  if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return
  event.preventDefault()
  const items=sections.value,index=items.findIndex((s) => s.key===key),rtl=document.documentElement.dir==='rtl'
  const delta=(event.key==='ArrowRight' ? 1 : -1)*(rtl ? -1 : 1)
  const next=event.key==='Home' ? 0 : event.key==='End' ? items.length-1 : (index+delta+items.length)%items.length
  selectSection(items[next].key)
  event.currentTarget.parentElement.querySelectorAll('[role=tab]')[next].focus()
}
</script>
<style scoped>
.printing-workspace{display:flex;flex-direction:column;flex:1;min-width:0;min-height:0;overflow:hidden}.printing-header{padding:20px 22px 0;border-bottom:1px solid var(--border);background:var(--card-bg)}h1{font-size:23px;letter-spacing:-.5px;margin:0}.printing-header p{font-size:13px;color:var(--text-muted);margin:6px 0 18px}.printing-tabs{display:flex;gap:26px}.printing-tabs button{display:flex;align-items:center;gap:8px;border-bottom:2px solid transparent;padding:10px 2px 13px;font-size:13px;color:var(--text-muted)}.printing-tabs button.active{color:var(--brand-dark);border-color:var(--brand);font-weight:600}.printing-tabs svg{width:17px;height:17px}.printing-panel{flex:1;min-height:0;overflow:auto;min-width:0}.printing-empty{padding:28px;color:var(--text-muted);font-size:13px}button:focus-visible{outline:2px solid var(--brand);outline-offset:3px}
@media(max-width:520px){.printing-header{padding:16px 14px 0}.printing-header p{font-size:12px}.printing-tabs{gap:22px}.printing-tabs button{font-size:12px}h1{font-size:22px}}
</style>
