<template>
  <dialog ref="dialog" class="display-controls" aria-labelledby="display-controls-title" @close="emit('close')">
    <header class="dc-heading">
      <div><h2 id="display-controls-title"><Icon name="monitor" :size="23" /> {{ t('Customer display') }}</h2><p class="muted">{{ t('Choose what customers see on the second monitor.') }}</p></div>
      <button autofocus class="btn-icon" :aria-label="t('Close display controls')" @click="dialog.close()"><Icon name="close" /></button>
    </header>
    <div class="dc-body">
      <section class="dc-project" :aria-label="t('Second monitor')">
        <div class="dc-monitor-field"><label for="display-monitor">{{ t('Project to') }}</label><select id="display-monitor" v-model="draft.screen"><option value="">{{ t('Second monitor (automatic)') }}</option><option v-for="screen in screens" :key="screen.label" :value="screen.label">{{ screen.label }}{{ screen.current ? ' (' + t('This monitor') + ')' : '' }}</option><option v-if="draft.screen && !screens.some(row => row.label === draft.screen)" :value="draft.screen">{{ draft.screen }}</option></select></div>
        <button class="btn btn-outline" :disabled="detecting" @click="detectScreens">{{ t('Find monitors') }}</button>
        <button class="btn btn-primary" :disabled="opening" @click="project"><Icon name="monitor" /> {{ t('Open second display') }}</button>
        <p class="muted dc-wide">{{ monitorMessage || t('Allow window placement when asked. You can also move the display window to the second monitor and use its Full screen button.') }}</p>
      </section>
      <section :aria-label="t('Display content')">
        <h3>{{ t('Popup layers over adverts') }}</h3>
        <div class="dc-modes"><button v-for="mode in DISPLAY_MODES" :key="mode.value" class="btn btn-outline" :aria-pressed="draft.mode === mode.value" @click="switchMode(mode.value)"><Icon :name="mode.icon" :size="20" /> {{ t(mode.label) }}</button></div>
        <p class="muted">{{ t('Adverts stay in the background. Sales appear automatically as a popup. Bank details, counter status and QR codes open as layers above it. Adverts hides the popups until the next sale update.') }}</p>
        <p class="muted">{{ t('Opening the second display also opens a movable mini preview in the POS. Use the quick-switch bar on Sell to change layers without this editor.') }}</p>
      </section>
      <section v-if="draft.mode === 'closed'">
        <h3>{{ t('Counter closed') }}</h3>
        <label class="dc-field"><span>{{ t('Closed-counter message') }}</span><textarea v-model="draft.closedMessage" rows="3" maxlength="500" :placeholder="t('Please use the next counter. Thank you.')" /></label>
      </section>
      <section v-else-if="draft.mode === 'bank'">
        <h3>{{ t('Bank details') }}</h3>
        <p>{{ t('Shows the receiving accounts configured in Settings → General → Customer bank display for this register and currency.') }}</p>
        <p class="muted">{{ t('Add or change accounts there. Customers can choose between matching accounts on the display.') }}</p>
      </section>
      <section v-else-if="draft.mode === 'adverts'">
        <div class="dc-section-heading"><h3>{{ t('Advert playlist') }}</h3><span class="muted">{{ draft.adverts.length }}/20</span></div>
        <form class="dc-add-link" @submit.prevent="addLink"><label class="dc-field"><span>{{ t('Advert link') }}</span><input v-model="advertUrl" type="url" placeholder="https://" /></label><button class="btn btn-outline" :disabled="draft.adverts.length >= 20">{{ t('Add advert link') }}</button></form>
        <p class="muted">{{ t('Use a public YouTube video or Short, full TikTok video link, or direct HTTPS image/video link. Other social pages can be added as QR codes below.') }}</p>
        <label class="dc-upload"><Icon name="upload" /> {{ uploading ? t('Saving local files…') : t('Add local images or videos') }}<input type="file" multiple accept="image/png,image/jpeg,image/webp,image/gif,video/mp4,video/webm,video/ogg" :disabled="uploading || draft.adverts.length >= 20" @change="addFiles" /></label>
        <p class="muted">{{ t('PNG, JPEG, WebP, GIF, MP4 or WebM; up to 100 MB per file. Local files stay in this browser and play without internet.') }}</p>
        <ol v-if="draft.adverts.length" class="dc-playlist"><li v-for="(advert, index) in draft.adverts" :key="advert.id"><label class="dc-field"><span>{{ t('Advert title') }} {{ index + 1 }}</span><input v-model="advert.title" maxlength="160" /></label><small class="muted">{{ advert.localId ? t('Local file') : advert.url }}</small><div class="dc-row-actions"><button class="btn btn-outline btn-sm" :disabled="index === 0" :aria-label="t('Move advert up')" @click="moveAdvert(index, -1)">↑</button><button class="btn btn-outline btn-sm" :disabled="index === draft.adverts.length - 1" :aria-label="t('Move advert down')" @click="moveAdvert(index, 1)">↓</button><button class="btn btn-outline btn-sm" :aria-label="t('Remove advert')" @click="draft.adverts.splice(index, 1)"><Icon name="trash" /></button></div></li></ol>
        <label class="dc-field dc-short"><span>{{ t('Seconds per advert') }}</span><input type="number" min="5" max="300" v-model.number="draft.interval" /></label>
        <p class="muted">{{ t('Adverts rotate for this duration. Playback starts muted. Customers can pause the playlist. Online videos depend on the provider allowing playback.') }}</p>
      </section>
      <section v-else-if="draft.mode === 'social'">
        <div class="dc-section-heading"><h3>{{ t('Social media and other QR codes') }}</h3><button class="btn btn-outline btn-sm" :disabled="draft.social.length >= 12" @click="draft.social.push({ label: '', url: '' })"><Icon name="plus" /> {{ t('Add QR code') }}</button></div>
        <p class="muted">{{ t('Add Facebook, Instagram, TikTok, YouTube, WhatsApp, reviews, your website, or any public HTTPS link. Up to 12 QR codes.') }}</p>
        <div v-for="(social, index) in draft.social" :key="index" class="dc-social-row"><label class="dc-field"><span>{{ t('QR label') }} {{ index + 1 }}</span><input v-model="social.label" maxlength="80" :placeholder="t('Instagram')" /></label><label class="dc-field"><span>{{ t('QR link') }} {{ index + 1 }}</span><input v-model="social.url" type="url" placeholder="https://" /></label><button class="btn-icon" :aria-label="t('Remove QR code')" @click="draft.social.splice(index, 1)"><Icon name="trash" /></button></div>
      </section>
      <section v-else-if="draft.mode === 'message'" class="dc-message-editor">
        <h3>{{ t('Custom message') }}</h3>
        <label class="dc-field"><span>{{ t('Message heading') }}</span><input v-model="draft.messageTitle" maxlength="160" /></label>
        <label class="dc-field"><span>{{ t('Message text') }}</span><textarea v-model="draft.messageBody" rows="4" maxlength="1500" /></label>
      </section>
      <section class="dc-defaults"><label class="dc-field"><span>{{ t('Default content when the till opens') }}</span><select v-model="draft.defaultMode"><option v-for="mode in DISPLAY_MODES" :key="mode.value" :value="mode.value">{{ t(mode.label) }}</option></select></label><p class="muted">{{ t('Content and monitor preferences are saved for this register on this browser.') }}</p></section>
      <p v-if="error" class="error" role="alert">{{ error }}</p><p v-if="status" role="status">{{ status }}</p>
    </div>
    <footer class="dc-footer"><button class="btn btn-outline" @click="dialog.close()">{{ t('Done') }}</button><button class="btn btn-primary" :disabled="uploading" @click="save">{{ t('Save and show') }}</button></footer>
  </dialog>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { t } from '../i18n'
import { newId } from '../offline'
import { displayPresentation, saveDisplayPresentation, setDisplayMode, openDisplayWindow } from '../customerDisplay'
import { DISPLAY_MODES, advertSource, publicDisplayUrl, displayMedia, LOCAL_MEDIA_LIMIT, LOCAL_MEDIA_TYPES } from '../displayContent'
import Icon from './Icon.vue'
const emit = defineEmits(['close'])
const dialog = ref(null), draft = ref(JSON.parse(JSON.stringify(displayPresentation.value)))
const advertUrl = ref(''), error = ref(''), status = ref(''), uploading = ref(false), opening = ref(false)
const detecting = ref(false), screens = ref([]), monitorMessage = ref('')
let details = null
let disposed = false
let stored = draft.value.adverts.map(row => row.localId).filter(Boolean)
const staged = new Set()
function switchMode(mode) { draft.value.mode = mode; setDisplayMode(mode); status.value = ''; error.value = '' }
async function detectScreens() {
  detecting.value = true
  try {
    if (!window.getScreenDetails) throw new Error(t('Monitor selection is unavailable in this browser. Move the new display window to your second monitor.'))
    details = await window.getScreenDetails()
    screens.value = details.screens.map(screen => ({ label: screen.label, current: screen === details.currentScreen }))
    monitorMessage.value = screens.value.length > 1 ? t('Monitors found. Choose a monitor and open the display.') : t('Only one monitor was detected. Connect or extend your second monitor, then try again.')
  } catch (e) { monitorMessage.value = e.name === 'NotAllowedError' ? t('Window placement was not allowed. Move the display window to your second monitor manually.') : e.message }
  finally { detecting.value = false }
}
async function project() {
  opening.value = true; error.value = ''
  try { monitorMessage.value = await openDisplayWindow(draft.value.screen, details) ? t('Display opened on the selected monitor. Use Full screen on that display to fill the screen.') : t('Display opened. Move it to the second monitor if needed, then select Full screen.') }
  catch (e) { error.value = t(e.message) }
  finally { opening.value = false }
}
function addLink() {
  error.value = ''; status.value = ''
  if (draft.value.adverts.length >= 20) return
  const source = advertSource(advertUrl.value)
  if (!source) { error.value = t('Use a YouTube or full TikTok video link, or a direct HTTPS image/video URL.'); return }
  draft.value.adverts.push({ id: newId(), title: '', url: publicDisplayUrl(advertUrl.value) })
  advertUrl.value = ''
}
async function addFiles(event) {
  error.value = ''; status.value = ''; uploading.value = true
  try {
    for (const file of Array.from(event.target.files || [])) {
      if (draft.value.adverts.length >= 20) throw new Error(t('Keep the playlist within 20 adverts.'))
      if (!LOCAL_MEDIA_TYPES.has(file.type) || !file.size || file.size > LOCAL_MEDIA_LIMIT) throw new Error(t('Choose a supported image or video smaller than 100 MB.'))
      const id = newId()
      await displayMedia('put', id, file)
      if (disposed) { await displayMedia('delete', id); break }
      staged.add(id)
      draft.value.adverts.push({ id, localId: id, title: file.name, type: file.type.startsWith('video/') ? 'video' : 'image' })
    }
  } catch (e) { error.value = e.name === 'QuotaExceededError' ? t('This browser has no space for more local media. Remove a file or use an online link.') : e.message }
  finally { uploading.value = false; event.target.value = '' }
}
function moveAdvert(index, direction) { const [row] = draft.value.adverts.splice(index, 1); draft.value.adverts.splice(index + direction, 0, row) }
function save() {
  error.value = ''; status.value = ''
  if (draft.value.social.some(row => !row.label.trim() || !publicDisplayUrl(row.url) || new TextEncoder().encode(row.url).length > 1500)) { error.value = t('Give each QR code a label and a valid HTTPS link within 1500 bytes.'); return }
  try {
    saveDisplayPresentation(draft.value)
    const kept = draft.value.adverts.map(row => row.localId).filter(Boolean)
    for (const id of [...stored, ...staged]) if (!kept.includes(id)) displayMedia('delete', id).catch(() => {})
    stored = kept; staged.clear()
    status.value = t('Display preferences saved. The customer screen has been updated.')
  } catch { error.value = t('Could not save display preferences in this browser. Free browser storage and try again.') }
}
onMounted(() => dialog.value.showModal())
onBeforeUnmount(() => { disposed = true; for (const id of staged) displayMedia('delete', id).catch(() => {}) })
</script>

<style scoped>
.display-controls { width: min(880px, calc(100% - 32px)); max-width: none; max-height: calc(100dvh - 32px); padding: 0; margin: auto; border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--card-bg); color: var(--text); box-shadow: var(--shadow-md); }
.display-controls::backdrop { background: color-mix(in srgb, var(--text) 35%, transparent); }
.dc-heading, .dc-footer { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; padding: 20px 24px; }
.dc-heading { border-bottom: 1px solid var(--border); }
.dc-heading h2 { display: flex; align-items: center; gap: 10px; margin: 0; font-size: 22px; }
.dc-heading p { margin: 6px 0 0; }
.dc-body { padding: 0 24px; }
.dc-body section { padding: 20px 0; border-bottom: 1px solid var(--border); }
.dc-body h3 { font-size: 16px; margin: 0 0 14px; }
.dc-body p { font-size: 13px; line-height: 1.6; margin: 10px 0 0; }
.dc-project { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 12px; align-items: end; }
.dc-wide { grid-column: 1 / -1; }
.dc-monitor-field, .dc-field { display: grid; gap: 7px; font-size: 13px; min-width: 0; }
.dc-field input, .dc-field textarea, .dc-field select, .dc-monitor-field select { width: 100%; min-width: 0; }
.dc-modes { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.dc-modes button { justify-content: flex-start; min-height: 52px; }
.dc-modes [aria-pressed=true] { color: var(--brand-dark); border-color: var(--brand); background: var(--surface-2); }
.dc-check { display: flex; align-items: flex-start; gap: 9px; margin-top: 16px; font-size: 13px; line-height: 1.5; }
.dc-check input { margin-top: 3px; flex-shrink: 0; }
.dc-add-link { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: end; gap: 12px; }
.dc-upload { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; font-size: 14px; margin-top: 18px; }
.dc-upload input { max-width: 100%; }
.dc-playlist { padding: 0; list-style: none; }
.dc-playlist li { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px 14px; padding: 14px 0; border-bottom: 1px solid var(--border); }
.dc-playlist small { grid-column: 1; overflow-wrap: anywhere; }
.dc-row-actions { display: flex; gap: 6px; grid-column: 2; grid-row: 1 / 3; align-items: center; }
.dc-short { max-width: 220px; }
.dc-section-heading { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-bottom: 14px; }
.dc-section-heading h3 { margin: 0; }
.dc-social-row { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 2fr) auto; gap: 12px; align-items: end; margin: 16px 0; }
.dc-message-editor .dc-field + .dc-field { margin-top: 16px; }
.dc-footer { position: sticky; bottom: 0; background: var(--card-bg); border-top: 1px solid var(--border); align-items: center; }
@media (max-width: 600px) { .dc-heading, .dc-footer { padding: 16px; } .dc-body { padding: 0 16px; } .dc-project { grid-template-columns: minmax(0, 1fr); } .dc-modes { grid-template-columns: repeat(2, minmax(0, 1fr)); } .dc-social-row { grid-template-columns: minmax(0, 1fr) auto; } .dc-social-row .dc-field:nth-child(2) { grid-column: 1; } .dc-social-row > button { grid-column: 2; grid-row: 1 / 3; } .dc-add-link { grid-template-columns: minmax(0, 1fr); } .dc-playlist li { grid-template-columns: minmax(0, 1fr); } .dc-row-actions { grid-column: 1; grid-row: auto; } }
</style>
