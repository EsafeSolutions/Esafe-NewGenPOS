<template>
  <div ref="root" class="customer-display-menu">
    <button ref="trigger" type="button" class="btn btn-icon display-menu-trigger" :title="t('Customer display')" :aria-label="t('Display')" :aria-expanded="open" aria-controls="customer-display-icon-menu" @click="toggle()" @keydown="triggerKey"><Icon name="monitor" :size="18" /></button>
    <Teleport to="body">
      <div v-if="open" id="customer-display-icon-menu" ref="menu" class="display-icon-menu" role="toolbar" :aria-label="t('Customer display quick switches')" :style="placement" @keydown="menuKey">
        <button v-for="(mode, index) in modes" :key="mode.value" type="button" class="btn-icon" :aria-label="t(mode.label)" :title="t(mode.label)" :aria-pressed="active === mode.value" :tabindex="focused === index ? 0 : -1" @focus="focused = index" @click="choose(mode.value)"><Icon :name="mode.icon" :size="20" /></button>
        <button type="button" class="btn-icon" :aria-label="t('Preview')" :title="t('Preview')" :aria-pressed="displayPreviewOpen" :tabindex="focused === 6 ? 0 : -1" @focus="focused = 6" @click="togglePreview"><Icon name="eye" :size="20" /></button>
        <button type="button" class="btn-icon" :aria-label="t('Open second display')" :title="t('Open second display')" :disabled="opening" :tabindex="focused === 7 ? 0 : -1" @focus="focused = 7" @click="project"><Icon name="monitor" :size="20" /></button>
        <button type="button" class="btn-icon" :aria-label="t('Customer display settings')" :title="t('Customer display settings')" :tabindex="focused === 8 ? 0 : -1" @focus="focused = 8" @click="settings"><Icon name="settings" :size="20" /></button>
      </div>
    </Teleport>
  </div>
</template>
<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { t } from '../i18n'
import { DISPLAY_MODES } from '../displayContent'
import { displayPresentation, displayMonitorState, displayPreviewOpen, setDisplayMode, openDisplayWindow } from '../customerDisplay'
import { useSessionStore } from '../stores/session'
import Icon from './Icon.vue'
const emit = defineEmits(['settings'])
const session = useSessionStore()
const root = ref(null), trigger = ref(null), menu = ref(null), open = ref(false), focused = ref(0), opening = ref(false), placement = ref({})
const modes = [DISPLAY_MODES.find(row => row.value === 'adverts'), ...DISPLAY_MODES.filter(row => row.value !== 'adverts')]
const active = computed(() => displayMonitorState.value ? displayMonitorState.value.bankOpen ? 'bank' : displayMonitorState.value.popup || (displayMonitorState.value.live ? 'live' : 'adverts') : displayPresentation.value.mode)
function choose(mode) {
  setDisplayMode(mode === active.value && !['adverts', 'live'].includes(mode) ? displayMonitorState.value?.live ? 'live' : 'adverts' : mode)
  close(true)
}
function positionMenu() {
  if (!menu.value || !trigger.value) return
  const anchor = trigger.value.getBoundingClientRect(), box = menu.value.getBoundingClientRect()
  placement.value = { left: `${Math.max(8, Math.min(innerWidth - box.width - 8, anchor.right - box.width))}px`, top: `${Math.max(8, Math.min(innerHeight - box.height - 8, anchor.bottom + 6))}px` }
}
async function toggle(last = false) {
  if (open.value) { close(true); return }
  open.value = true; focused.value = last ? 8 : 0
  await nextTick(); positionMenu(); menu.value?.querySelectorAll('button')[focused.value]?.focus()
}
function close(restore = false) { open.value = false; if (restore) trigger.value?.focus() }
function triggerKey(event) {
  if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return
  event.preventDefault(); if (!open.value) toggle(event.key === 'ArrowUp')
}
function menuKey(event) {
  if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(true); return }
  const steps = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: 3, ArrowUp: -3 }
  if (!(event.key in steps) && !['Home', 'End'].includes(event.key)) return
  event.preventDefault()
  const buttons = [...menu.value.querySelectorAll('button:not(:disabled)')], current = buttons.indexOf(document.activeElement)
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (current + steps[event.key] + buttons.length) % buttons.length
  buttons[next]?.focus()
}
function outside(event) { if (open.value && !root.value?.contains(event.target) && !menu.value?.contains(event.target)) close() }
function togglePreview() { displayPreviewOpen.value = !displayPreviewOpen.value; close(true) }
function settings() { close(true); emit('settings') }
async function project() {
  close(true); opening.value = true
  try {
    const placed = await openDisplayWindow(displayPresentation.value.screen)
    if (!placed) session.notify(t('Display opened. Move it to the second monitor if needed, then select Full screen.'))
  } catch (error) { session.notify(t(error.message), true) }
  finally { opening.value = false }
}
onMounted(() => { document.addEventListener('pointerdown', outside); document.addEventListener('focusin', outside); window.addEventListener('resize', positionMenu); window.addEventListener('scroll', positionMenu, true) })
onBeforeUnmount(() => { document.removeEventListener('pointerdown', outside); document.removeEventListener('focusin', outside); window.removeEventListener('resize', positionMenu); window.removeEventListener('scroll', positionMenu, true) })
</script>
<style scoped>
.customer-display-menu { display: inline-flex; align-items: center; }
.display-menu-trigger { display: inline-grid; place-items: center; width: var(--header-tool-size, 32px); height: var(--header-tool-size, 32px); padding: 0; border-radius: 8px; background: rgba(255, 255, 255, .14); color: inherit; }
.display-menu-trigger:hover, .display-menu-trigger[aria-expanded=true] { background: rgba(255, 255, 255, .24); }
.display-menu-trigger:focus-visible { outline: 2px solid var(--brand-soft); outline-offset: 2px; }
.display-icon-menu { position: fixed; z-index: 80; display: grid; grid-template-columns: repeat(3, 36px); gap: 6px; padding: 8px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--card-bg); color: var(--text); box-shadow: var(--shadow-md); }
.display-icon-menu > button { width: 36px; height: 36px; padding: 0; border: 1px solid transparent; border-radius: 7px; }
.display-icon-menu > button:hover { background: var(--surface-2); }
.display-icon-menu [aria-pressed=true] { color: var(--brand-dark); border-color: var(--brand); background: var(--surface-2); }
.display-icon-menu > button:focus-visible { outline: 2px solid var(--brand); outline-offset: 1px; }
</style>
