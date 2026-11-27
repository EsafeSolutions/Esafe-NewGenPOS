<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only -->
<template>
  <dialog ref="dialog" class="pos-sound-dialog" data-pos-sound="off" aria-labelledby="sound-title" @cancel.prevent="$emit('close')">
    <header class="modal-header">
      <h2 id="sound-title">{{ t('POS sounds') }}</h2>
      <button type="button" class="btn-ghost" :aria-label="t('Close sound settings')" @click="$emit('close')"><Icon name="close" /></button>
    </header>
    <div class="modal-body sound-options">
      <p class="muted">{{ t('Sound preferences for this browser.') }}</p>
      <label class="sound-choice">
        <input type="checkbox" :checked="soundPreferences.clicks" @change="setSoundPreference('clicks', $event.target.checked)" />
        <span>{{ t('Ordering click sounds') }}</span>
      </label>
      <label class="sound-choice">
        <input type="checkbox" :checked="soundPreferences.greeting" @change="setSoundPreference('greeting', $event.target.checked)" />
        <span>{{ t('Spoken thank-you greeting') }}</span>
      </label>
      <label class="sound-volume">
        <span>{{ t('Volume') }} <strong>{{ Math.round(soundPreferences.volume * 100) }}%</strong></span>
        <input type="range" min="0" max="1" step="0.05" :value="soundPreferences.volume" @input="setSoundPreference('volume', $event.target.value)" />
      </label>
      <p class="muted small">{{ t('The greeting plays after you confirm the change or points and hand over the receipt. It uses an available English voice.') }}</p>
      <p v-if="!canSpeakGreeting() || greetingStatus === 'unavailable'" role="status" class="muted small">{{ t('Voice is unavailable on this device. The thank-you message will still appear.') }}</p>
      <div class="sound-tests">
        <button type="button" class="btn btn-outline" :disabled="!soundPreferences.clicks || !soundPreferences.volume" @click="playOrderSound">{{ t('Test click sound') }}</button>
        <button type="button" class="btn btn-outline" :disabled="!soundPreferences.greeting || !soundPreferences.volume || !canSpeakGreeting()" @click="speakThankYou">{{ t('Test greeting') }}</button>
      </div>
    </div>
    <footer class="modal-footer"><button type="button" class="btn btn-primary" @click="$emit('close')">{{ t('Done') }}</button></footer>
  </dialog>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'
import Icon from './Icon.vue'
import { t } from '../i18n'
import { soundPreferences, setSoundPreference, playOrderSound, speakThankYou, stopGreeting, canSpeakGreeting, greetingStatus } from '../posSounds'

defineEmits(['close'])
const dialog = ref(null)
onMounted(() => dialog.value.showModal())
onBeforeUnmount(() => { stopGreeting(); dialog.value?.close() })
</script>

<style scoped>
.pos-sound-dialog { padding: 0; border: 1px solid var(--border); border-radius: var(--radius-lg); width: min(480px, calc(100vw - 24px)); max-height: 90dvh; overflow: auto; background: var(--card-bg); color: var(--text); box-shadow: var(--shadow-md); }
.pos-sound-dialog::backdrop { background: rgba(24, 30, 44, .55); }
.modal-header h2 { margin: 0; font-size: 18px; }
.sound-options { display: grid; gap: 20px; }
.sound-options p { margin: 0; line-height: 1.5; }
.sound-choice { display: flex; align-items: center; gap: 12px; cursor: pointer; }
.sound-choice input { width: 22px; height: 22px; accent-color: var(--brand); }
.sound-volume { display: grid; gap: 12px; }
.sound-volume span { display: flex; justify-content: space-between; }
.sound-volume input { width: 100%; accent-color: var(--brand); }
.sound-tests { display: flex; flex-wrap: wrap; gap: 10px; }
@media (max-width: 460px) { .sound-tests .btn { width: 100%; } }
</style>
