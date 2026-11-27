<template>
  <main class="display-content" :class="['display-content-' + mode, { 'is-background': background }]">
    <section v-if="mode === 'closed'" class="dc-notice">
      <Icon name="ban" :size="64" /><h1>{{ t('Counter closed') }}</h1><p>{{ config.closedMessage || t('Please use the next counter. Thank you.') }}</p>
    </section>
    <section v-else-if="mode === 'message'" class="dc-notice">
      <h1>{{ config.messageTitle || t('Welcome') }}</h1><p>{{ config.messageBody || t('Thank you for visiting us.') }}</p>
    </section>
    <section v-else-if="mode === 'bank'" class="dc-bank-content">
      <h1>{{ t('Bank transfer details') }}</h1>
      <div v-if="accounts.length > 1" class="dc-bank-options"><button v-for="(account, index) in accounts" :key="index" class="btn btn-outline" :aria-pressed="bankIndex === index" @click="bankIndex = index">{{ account.bank_name }} · {{ account.account_number.slice(-4) }}</button></div>
      <BankTransferCard v-if="accounts.length" :account="accounts[bankIndex] || accounts[0]" />
      <p v-else class="dc-empty">{{ t('Bank details are not available for this counter. Please ask the cashier.') }}</p>
    </section>
    <section v-else-if="mode === 'social'" class="dc-social-content">
      <h1>{{ t('Stay connected') }}</h1>
      <div v-if="social.length" class="dc-qr-grid"><article v-for="row in social" :key="row.url + row.label"><img v-if="row.qr" :src="row.qr" :alt="t('QR code for {label}', { label: row.label })" /><h2>{{ row.label }}</h2><span>{{ row.host }}</span></article></div>
      <p v-else class="dc-empty">{{ t('Social links will appear here once added by the cashier.') }}</p>
    </section>
    <section v-else-if="mode === 'adverts'" class="dc-advert-content" :aria-label="t('Adverts')">
      <div v-if="current" class="dc-media-frame">
        <img v-if="media?.type === 'image' && !mediaError" :src="media.source" :alt="current.title || t('Advert')" @error="mediaError = true" />
        <video v-else-if="media?.type === 'video' && !mediaError" ref="video" :key="media.source" :src="media.source" :autoplay="!paused" muted playsinline loop controls @error="mediaError = true" @loadeddata="syncVideo" />
        <iframe v-else-if="media?.type === 'embed' && !mediaError && online && !paused" :key="media.source" :src="media.source" :title="current.title || t('Advert video')" allow="autoplay; encrypted-media; fullscreen; picture-in-picture" allowfullscreen referrerpolicy="strict-origin-when-cross-origin" />
        <div v-else class="dc-empty" role="status"><Icon :name="paused ? 'pause' : 'image'" :size="48" /><p>{{ paused ? t('Adverts paused') : loading ? t('Loading advert…') : t('This advert is unavailable. Please ask the cashier.') }}</p></div>
      </div>
      <div v-else class="dc-empty dc-advert-welcome"><Icon name="store" :size="64" /><h1>{{ t('Welcome') }}</h1><p>{{ t('Thank you for visiting us.') }}</p></div>
      <div v-if="current" class="dc-playback"><div><strong>{{ current.title || t('Advert') }}</strong><span class="muted">{{ index + 1 }} / {{ config.adverts.length }}</span></div><button class="btn btn-outline" :aria-label="t('Previous advert')" :disabled="config.adverts.length < 2" @click="advance(-1)">‹</button><button class="btn btn-outline" :aria-pressed="paused" @click="paused = !paused"><Icon :name="paused ? 'chevron-right' : 'pause'" /> {{ paused ? t('Play adverts') : t('Pause adverts') }}</button><button class="btn btn-outline" :aria-label="t('Next advert')" :disabled="config.adverts.length < 2" @click="advance(1)">›</button></div>
      <div v-if="current?.url && (media?.type === 'embed' || mediaError)" class="dc-online-link"><img :src="bankQrSource({ qr_payload: current.url })" :alt="t('Open advert QR code')" /><span>{{ t('If the video cannot play, scan to open it on your phone.') }}</span></div>
    </section>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch, nextTick } from 'vue'
import { t } from '../i18n'
import { advertSource, displayMedia, LOCAL_MEDIA_TYPES } from '../displayContent'
import { bankQrSource } from '../bankDisplay'
import BankTransferCard from './BankTransferCard.vue'
import Icon from './Icon.vue'
const props = defineProps({ mode: String, config: { type: Object, required: true }, accounts: { type: Array, default: () => [] }, background: Boolean, mirror: Boolean, visualState: { type: Object, default: null } })
const emit = defineEmits(['visual'])
const bankIndex = ref(0), index = ref(0), paused = ref(false), media = ref(null), mediaError = ref(false), loading = ref(false), video = ref(null)
const online = ref(navigator.onLine)
const connectivity = () => { online.value = navigator.onLine }
window.addEventListener('online', connectivity); window.addEventListener('offline', connectivity)
const social = computed(() => props.config.social.map(row => ({ ...row, host: new URL(row.url).hostname, qr: bankQrSource({ qr_payload: row.url }) })))
const current = computed(() => props.config.adverts[index.value] || props.config.adverts[0])
watch(() => JSON.stringify(props.accounts), () => { bankIndex.value = 0 })
watch(() => JSON.stringify(props.config.adverts), () => { index.value = 0; paused.value = false })
watch(() => props.visualState, state => {
  if (!props.mirror || !state) return
  index.value = Math.max(0, Math.min(props.config.adverts.length - 1, Number(state.index) || 0))
  paused.value = Boolean(state.paused)
  bankIndex.value = Math.max(0, Number(state.bankIndex) || 0)
}, { deep: true, immediate: true })
watch([index, paused, bankIndex], () => {
  if (!props.mirror) emit('visual', { index: index.value, paused: paused.value, bankIndex: bankIndex.value })
}, { immediate: true, flush: 'post' })
watch(() => JSON.stringify(current.value), async (_, previous, onCleanup) => {
  let cancelled = false, objectUrl = ''
  onCleanup(() => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl) })
  media.value = null; mediaError.value = false; loading.value = true
  try {
    const advert = current.value
    if (!advert) return
    if (!advert.localId) { media.value = advertSource(advert.url); return }
    const file = await displayMedia('get', advert.localId)
    if (cancelled) return
    if (!file || !LOCAL_MEDIA_TYPES.has(file.type)) throw new Error('Missing media')
    objectUrl = URL.createObjectURL(file)
    media.value = { type: file.type.startsWith('video/') ? 'video' : 'image', source: objectUrl }
  } catch { if (!cancelled) mediaError.value = true }
  finally { if (!cancelled) loading.value = false }
}, { immediate: true })
let timer
function advance(direction = 1) { index.value = (index.value + direction + props.config.adverts.length) % (props.config.adverts.length || 1) }
async function syncVideo() {
  await nextTick()
  if (!video.value) return
  if (paused.value) video.value.pause()
  else video.value.play().catch(() => {})
}
watch([paused, () => props.config.interval, () => props.mode, index], () => {
  clearInterval(timer)
  if (!props.mirror && !paused.value && props.mode === 'adverts') timer = setInterval(() => advance(), props.config.interval * 1000)
  syncVideo()
}, { immediate: true })
onBeforeUnmount(() => { clearInterval(timer); window.removeEventListener('online', connectivity); window.removeEventListener('offline', connectivity) })
</script>

<style scoped>
.display-content { flex: 1; min-height: 0; overflow: auto; color: var(--text); }
.dc-notice { min-height: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 40px 10px; text-align: center; }
.dc-notice > .icon { color: var(--brand); margin-bottom: 24px; }
.dc-notice h1 { margin: 0; font-size: clamp(32px, 4vw, 64px); line-height: 1.12; overflow-wrap: anywhere; }
.dc-notice p { margin: 24px 0 0; max-width: 950px; font-size: clamp(18px, 2vw, 28px); line-height: 1.5; white-space: pre-wrap; overflow-wrap: anywhere; }
.dc-bank-content { max-width: 1100px; margin: auto; padding-bottom: 24px; }
.dc-bank-content h1, .dc-social-content h1 { font-size: clamp(26px, 3vw, 46px); margin: 12px 0 24px; }
.dc-bank-options { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 18px; }
.dc-bank-options [aria-pressed=true] { border-color: var(--brand); background: var(--surface-2); }
.dc-qr-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: clamp(16px, 2vw, 32px); padding-bottom: 24px; }
.dc-qr-grid article { display: flex; flex-direction: column; align-items: center; text-align: center; padding: 24px; background: var(--card-bg); border: 1px solid var(--border); border-radius: var(--radius); min-width: 0; }
.dc-qr-grid img { width: min(100%, 260px); height: auto; image-rendering: pixelated; background: white; }
.dc-qr-grid h2 { margin: 16px 0 6px; font-size: 24px; overflow-wrap: anywhere; }
.dc-qr-grid span { color: var(--text-muted); font-size: 14px; overflow-wrap: anywhere; }
.dc-advert-content { display: flex; flex-direction: column; min-height: 100%; gap: 12px; }
.dc-media-frame { position: relative; display: flex; align-items: center; justify-content: center; flex: 1; min-height: 240px; height: max(240px, calc(100dvh - 270px)); background: var(--card-bg); border-radius: var(--radius); overflow: hidden; }
.dc-media-frame > img, .dc-media-frame > video, .dc-media-frame > iframe { position: absolute; inset: 0; width: 100%; height: 100%; }
.dc-media-frame > img, .dc-media-frame > video { object-fit: contain; }
.dc-media-frame > iframe { border: 0; }
.dc-playback { display: flex; align-items: center; justify-content: flex-end; gap: 10px; flex-wrap: wrap; }
.dc-playback > div { display: grid; flex: 1; gap: 4px; min-width: 0; overflow-wrap: anywhere; }
.dc-playback span { font-size: 14px; }
.dc-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; font-size: clamp(18px, 2vw, 30px); padding: 30px; line-height: 1.5; }
.dc-online-link { display: flex; align-items: center; gap: 12px; font-size: 13px; color: var(--text-muted); }
.dc-online-link img { width: 68px; height: 68px; flex-shrink: 0; }
.dc-advert-welcome { min-height: 100%; gap: 16px; }
.dc-advert-welcome h1, .dc-advert-welcome p { margin: 0; }
.is-background { position: absolute; inset: 0; overflow: hidden; background: var(--page-bg); }
.is-background .dc-advert-content { position: absolute; inset: 0; min-height: 0; }
.is-background .dc-media-frame { position: absolute; inset: 0; height: 100%; min-height: 0; border-radius: 0; background: var(--page-bg); }
.is-background .dc-media-frame > img, .is-background .dc-media-frame > video { object-fit: cover; }
.is-background .dc-playback { position: absolute; inset: auto 16px 16px; padding: 10px 14px; border-radius: var(--radius); background: color-mix(in srgb, var(--card-bg) 94%, transparent); color: var(--text); }
.is-background .dc-online-link { position: absolute; bottom: 90px; left: 16px; max-width: 340px; padding: 8px; border-radius: var(--radius); background: var(--card-bg); }
.is-background .dc-online-link img { width: 48px; height: 48px; }
@media (max-width: 600px) { .dc-qr-grid { grid-template-columns: minmax(0, 1fr); } .dc-media-frame { height: 42dvh; flex: none; } .dc-playback > div { flex-basis: 100%; } }
</style>
