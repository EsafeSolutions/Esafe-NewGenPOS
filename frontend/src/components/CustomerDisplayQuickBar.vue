<template>
  <div class="display-quick-bar" role="toolbar" :aria-label="t('Customer display quick switches')">
    <span class="quick-display-label"><Icon name="monitor" /> {{ t('Customer screen') }}</span>
    <div class="quick-display-modes"><button v-for="mode in modes" :key="mode.value" class="btn btn-outline btn-sm" :aria-pressed="active === mode.value" @click="choose(mode.value)"><Icon :name="mode.icon" /> {{ t(mode.label) }}</button></div>
    <button class="btn btn-outline btn-sm" :aria-pressed="displayPreviewOpen" @click="displayPreviewOpen = !displayPreviewOpen"><Icon name="monitor" /> {{ t('Preview') }}</button>
    <button class="btn-icon" :aria-label="t('Customer display settings')" @click="emit('settings')"><Icon name="settings" /></button>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import { t } from '../i18n'
import { DISPLAY_MODES } from '../displayContent'
import { displayPresentation, displayMonitorState, displayPreviewOpen, setDisplayMode } from '../customerDisplay'
import Icon from './Icon.vue'
const emit = defineEmits(['settings'])
const modes = [DISPLAY_MODES.find(row => row.value === 'adverts'), ...DISPLAY_MODES.filter(row => row.value !== 'adverts')]
const active = computed(() => displayMonitorState.value ? displayMonitorState.value.bankOpen ? 'bank' : displayMonitorState.value.popup || (displayMonitorState.value.live ? 'live' : 'adverts') : displayPresentation.value.mode)
function choose(mode) {
  setDisplayMode(mode === active.value && !['adverts', 'live'].includes(mode) ? displayMonitorState.value?.live ? 'live' : 'adverts' : mode)
}
</script>
<style scoped>
.display-quick-bar { display: flex; align-items: center; gap: 6px; flex-shrink: 0; min-height: 44px; padding-bottom: 8px; margin-bottom: 8px; border-bottom: 1px solid var(--border); min-width: 0; }
.display-quick-bar > * { flex-shrink: 0; white-space: nowrap; }
.quick-display-label { display: flex; align-items: center; gap: 6px; color: var(--text-muted); font-size: 12px; margin-inline-end: 4px; }
.quick-display-modes { display: flex; gap: 6px; flex: 1 1 auto; min-width: 0; overflow-x: auto; }
.quick-display-modes > button { flex-shrink: 0; }
.display-quick-bar .btn { padding: 7px 9px; font-size: 12px; }
.display-quick-bar [aria-pressed=true] { color: var(--brand-dark); border-color: var(--brand); background: var(--surface-2); }
@media (max-width: 700px) { .quick-display-label { display: none; } }
</style>
