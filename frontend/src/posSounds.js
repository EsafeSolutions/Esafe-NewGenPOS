// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
// Sounds belong to this browser, so each till can choose its own volume.
import { reactive, readonly, ref } from 'vue'

const KEY = 'esafepos-sounds'
const defaults = { clicks: true, greeting: true, volume: 0.6 }
let saved = {}
try { saved = JSON.parse(localStorage.getItem(KEY) || '{}') || {} } catch { /* Use defaults. */ }
const preferences = reactive({
  clicks: typeof saved.clicks === 'boolean' ? saved.clicks : defaults.clicks,
  greeting: typeof saved.greeting === 'boolean' ? saved.greeting : defaults.greeting,
  volume: typeof saved.volume === 'number' && Number.isFinite(saved.volume)
    ? Math.max(0, Math.min(1, saved.volume)) : defaults.volume,
})
export const soundPreferences = readonly(preferences)
export const greetingStatus = ref('idle')
export const THANK_YOU_MESSAGE = 'Thank you very much for your purchase. Come again. We wish you all the best!'
export const canSpeakGreeting = () => typeof window !== 'undefined' &&
  Boolean(window.speechSynthesis && window.SpeechSynthesisUtterance)

let audio = null
let audioRequest = 0
let lastClick = -Infinity
let utterance = null

export function setSoundPreference(key, value) {
  if (key === 'volume') {
    const volume = Number(value)
    if (!Number.isFinite(volume)) return
    preferences.volume = Math.max(0, Math.min(1, volume))
  } else if (key === 'clicks' || key === 'greeting') preferences[key] = Boolean(value)
  else return
  if (!preferences.greeting || preferences.volume === 0) stopGreeting()
  try { localStorage.setItem(KEY, JSON.stringify(preferences)) } catch { /* Keep the tab preference. */ }
}

function playNotes(notes) {
  if (!preferences.clicks || !preferences.volume) return
  try {
    const Audio = window.AudioContext || window.webkitAudioContext
    if (!Audio) return
    if (!audio || audio.state === 'closed') audio = new Audio()
    const context = audio, request = ++audioRequest, requestedAt = Date.now()
    const play = () => {
      if (request !== audioRequest || context.state !== 'running' ||
          !preferences.clicks || !preferences.volume || Date.now() - requestedAt > 250) return
      try {
        const start = context.currentTime
        for (const [frequency, offset, duration, level] of notes) {
          const tone = context.createOscillator(), gain = context.createGain()
          tone.type = 'sine'
          tone.frequency.value = frequency
          gain.gain.setValueAtTime(0, start + offset)
          gain.gain.linearRampToValueAtTime(level * preferences.volume, start + offset + 0.008)
          gain.gain.exponentialRampToValueAtTime(0.0001, start + offset + duration)
          tone.connect(gain)
          gain.connect(context.destination)
          tone.onended = () => { tone.disconnect(); gain.disconnect() }
          tone.start(start + offset)
          tone.stop(start + offset + duration + 0.01)
        }
      } catch { /* An unavailable audio device must not interrupt the sale. */ }
    }
    // Unlock during the gesture; discard stale taps if the browser resumes late.
    if (context.state !== 'running') context.resume().then(play).catch(() => {})
    else play()
  } catch { /* Audio must never interrupt ordering or payment. */ }
}

export function playOrderSound() {
  const now = Date.now()
  if (now - lastClick < 65) return
  lastClick = now
  playNotes([[880, 0, 0.065, 0.09], [1320, 0.018, 0.075, 0.045]])
}

export function playOrderingClick(event) {
  const target = event.target?.closest?.('button, [role="button"], input[type="checkbox"]')
  if (!target || target.disabled || target.getAttribute('aria-disabled') === 'true' ||
      target.closest('[data-pos-sound="off"]')) return
  playOrderSound()
}

export function stopGreeting() {
  if (utterance) {
    utterance.onend = null
    utterance.onerror = null
    utterance = null
    try { window.speechSynthesis.cancel() } catch { /* Unsupported device. */ }
  }
  greetingStatus.value = 'idle'
}

export function speakThankYou() {
  stopGreeting()
  if (!preferences.greeting || !preferences.volume) return
  if (!canSpeakGreeting()) { greetingStatus.value = 'unavailable'; return }
  try {
    const synth = window.speechSynthesis
    const message = new window.SpeechSynthesisUtterance(THANK_YOU_MESSAGE)
    const english = synth.getVoices().filter(voice => /^en(?:[-_]|$)/i.test(voice.lang))
    const voice = english.find(voice => voice.localService) || english[0]
    if (voice) message.voice = voice
    message.lang = voice?.lang || 'en-GB'
    message.rate = 0.92
    message.pitch = 1
    message.volume = preferences.volume
    utterance = message // Keep it alive until the browser finishes speaking.
    greetingStatus.value = 'speaking'
    message.onend = () => { if (utterance === message) { utterance = null; greetingStatus.value = 'done' } }
    message.onerror = () => { if (utterance === message) { utterance = null; greetingStatus.value = 'unavailable' } }
    synth.speak(message)
  } catch { utterance = null; greetingStatus.value = 'unavailable' }
}

export function playSaleGreeting() {
  playNotes([[659.25, 0, 0.18, 0.1], [830.61, 0.1, 0.2, 0.09], [987.77, 0.2, 0.3, 0.08]])
  // Called directly by the handover button, while browser audio is allowed.
  speakThankYou()
}
