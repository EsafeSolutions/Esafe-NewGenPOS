<template>
  <Teleport :to="host">
    <aside v-if="displayPreviewOpen && session.settings.enable_customer_display && !session.locked" ref="panel" class="customer-display-preview" :style="positionStyle" :aria-label="t('Customer display preview')">
      <header class="preview-handle" tabindex="0" :aria-label="t('Move customer display preview')" @pointerdown="startDrag" @pointermove="moveDrag" @pointerup="endDrag" @pointercancel="endDrag" @keydown="moveKeyboard">
        <span><Icon name="monitor" /> {{ t('Customer display') }}</span>
        <button class="btn-icon" :aria-label="collapsed ? t('Expand customer preview') : t('Minimize customer preview')" @click="collapsed = !collapsed"><Icon :name="collapsed ? 'chevron-down' : 'pause'" /></button>
        <button class="btn-icon" :aria-label="t('Close customer preview')" @click="displayPreviewOpen = false"><Icon name="close" /></button>
      </header>
      <div v-show="!collapsed" class="preview-screen" :style="{ height: `${screenHeight * scale}px` }">
        <iframe :src="previewUrl" :style="{ width: `${screenWidth}px`, height: `${screenHeight}px`, left: `${(width - screenWidth * scale) / 2}px`, transform: `scale(${scale})` }" :title="t('Customer screen mirror')" tabindex="-1" />
      </div>
      <footer v-show="!collapsed"><span class="preview-status" :class="{ connected }" />{{ connected ? t('Customer screen connected') : t('Open the customer display to connect') }}</footer>
    </aside>
  </Teleport>
</template>
<script setup>
import { computed, onMounted, onBeforeUnmount, ref, shallowRef, watch, nextTick } from 'vue'
import { t } from '../i18n'
import { useSessionStore } from '../stores/session'
import { customerDisplayUrl, displayPreviewOpen, displayMonitorState, isDisplayWindowOpen } from '../customerDisplay'
import Icon from './Icon.vue'
const session = useSessionStore()
const key = 'esafepos-display-preview-position'
const panel = ref(null), host = shallowRef(document.body), collapsed = ref(false), connected = ref(false), width = ref(360)
const position = ref(null)
try { const saved = JSON.parse(localStorage.getItem(key) || 'null'); if (Number.isFinite(saved?.x) && Number.isFinite(saved?.y)) position.value = saved } catch { /* Use the default corner. */ }
const previewUrl = customerDisplayUrl() + '&preview=1'
const screenWidth = computed(() => Math.max(320, Math.min(7680, Number(displayMonitorState.value?.width) || 1280)))
const screenHeight = computed(() => Math.max(240, Math.min(4320, Number(displayMonitorState.value?.height) || 720)))
const scale = computed(() => Math.min(width.value / screenWidth.value, 220 / screenHeight.value))
const positionStyle = computed(() => position.value ? { left: `${position.value.x}px`, top: `${position.value.y}px` } : { left: '16px', bottom: '16px' })
let drag, resize, observer, timer
function clampPosition(x, y) { return { x: Math.max(0, Math.min(innerWidth - (panel.value?.offsetWidth || 280), x)), y: Math.max(0, Math.min(innerHeight - (panel.value?.offsetHeight || 80), y)) } }
function persist() { try { localStorage.setItem(key, JSON.stringify(position.value)) } catch { /* Position can remain temporary. */ } }
function startDrag(event) {
  if (event.button !== 0 || event.target.closest('button')) return
  const rect = panel.value.getBoundingClientRect()
  drag = { x: event.clientX - rect.left, y: event.clientY - rect.top }
  event.currentTarget.setPointerCapture(event.pointerId)
  event.preventDefault()
}
function moveDrag(event) { if (drag) position.value = clampPosition(event.clientX - drag.x, event.clientY - drag.y) }
function endDrag() { if (drag) { drag = null; persist() } }
function moveKeyboard(event) {
  if (event.target !== event.currentTarget || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return
  event.preventDefault()
  const rect = panel.value.getBoundingClientRect(), step = event.shiftKey ? 40 : 10
  position.value = clampPosition(rect.left + (event.key === 'ArrowRight' ? step : event.key === 'ArrowLeft' ? -step : 0), rect.top + (event.key === 'ArrowDown' ? step : event.key === 'ArrowUp' ? -step : 0)); persist()
}
function updateHost() {
  // Keep the mini screen visible inside checkout/settings native modal layers.
  const dialogs = [...document.querySelectorAll('dialog[open]')]
  const target = dialogs.at(-1) || document.body
  if (host.value !== target && !target.closest('.customer-display-preview')) host.value = target
}
async function observePanel() {
  await nextTick(); resize?.disconnect()
  if (panel.value) {
    resize = new ResizeObserver(entries => { if (entries[0].contentRect.width > 0) width.value = entries[0].contentRect.width; if (position.value) position.value = clampPosition(position.value.x, position.value.y) })
    resize.observe(panel.value)
  }
}
function onResize() { if (position.value) { position.value = clampPosition(position.value.x, position.value.y); persist() } }
watch(panel, observePanel, { flush: 'post' })
onMounted(() => {
  observer = new MutationObserver(updateHost); observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['open'] })
  updateHost(); window.addEventListener('resize', onResize)
  connected.value = isDisplayWindowOpen()
  timer = setInterval(() => { connected.value = isDisplayWindowOpen() }, 1000)
})
onBeforeUnmount(() => { observer?.disconnect(); resize?.disconnect(); clearInterval(timer); window.removeEventListener('resize', onResize) })
</script>
<style scoped>
.customer-display-preview { position: fixed; z-index: 1200; width: min(360px, calc(100vw - 24px)); margin: 0; overflow: hidden; border: 1px solid var(--border); border-radius: var(--radius); background: var(--card-bg); color: var(--text); box-shadow: var(--shadow-md); }
.preview-handle { display: flex; align-items: center; gap: 4px; padding: 5px 8px 5px 12px; cursor: move; touch-action: none; user-select: none; }
.preview-handle > span { display: flex; align-items: center; gap: 7px; margin-inline-end: auto; font-size: 12px; font-weight: 700; }
.preview-handle button { width: 28px; height: 28px; }
.preview-handle:focus-visible { outline: 2px solid var(--brand); outline-offset: -2px; }
.preview-screen { position: relative; width: 100%; overflow: hidden; background: var(--page-bg); pointer-events: none; }
.preview-screen iframe { position: absolute; inset: 0; border: 0; transform-origin: top left; pointer-events: none; }
footer { display: flex; align-items: center; gap: 6px; padding: 7px 10px; color: var(--text-muted); font-size: 11px; }
.preview-status { width: 6px; height: 6px; border-radius: 50%; background: var(--text-muted); }
.preview-status.connected { background: var(--brand); }
@media (max-width: 600px) { .customer-display-preview { width: min(300px, calc(100vw - 24px)); } }
</style>
