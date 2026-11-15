<template>
  <form class="contact-pad" @submit.prevent="submit">
    <header>
      <Icon name="person" :size="29" />
      <h2 id="display-contact-title">{{ t('Membership') }}</h2>
      <p>{{ t('Enter your number to find your account or add it to this receipt.') }}</p>
    </header>
    <input v-model="mobile" type="tel" inputmode="none" autocomplete="off"
      :aria-label="t('Contact number')" :placeholder="t('Contact number')" :disabled="busy" />
    <div class="keypad">
      <button v-for="digit in digits" :key="digit" type="button" :disabled="busy" @click="press(digit)">
        {{ digit }}
      </button>
      <button type="button" :disabled="busy" :aria-label="t('Delete last digit')" @click="mobile = mobile.slice(0, -1)">⌫</button>
    </div>
    <p v-if="error" class="contact-error" role="alert">{{ error }}</p>
    <div class="pad-actions">
      <button type="button" class="btn btn-outline" @click="$emit('skip')">{{ t('Skip') }}</button>
      <button class="btn btn-primary" :disabled="busy || !valid">{{ busy ? t('Looking up…') : t('Continue') }}</button>
    </div>
  </form>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import Icon from './Icon.vue'
import { t } from '../i18n'

const props = defineProps({ busy: Boolean, error: String })
const emit = defineEmits(['submit', 'skip', 'edit'])
const mobile = ref('')
const digits = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '+', '0']
const valid = computed(() => /^\+?[0-9]{7,15}$/.test(mobile.value))
watch(mobile, (value) => {
  const cleaned = value.replace(/[^+0-9]/g, '').replace(/(?!^)\+/g, '').slice(0, 16)
  if (cleaned !== value) mobile.value = cleaned
  emit('edit')
})
function press(digit) {
  if (mobile.value.length < 16 && (digit !== '+' || !mobile.value)) mobile.value += digit
}
function submit() {
  if (valid.value && !props.busy) emit('submit', mobile.value)
}
</script>

<style scoped>
.contact-pad { background: var(--card-bg); display: grid; gap: 12px; padding: clamp(12px, 2vw, 24px); }
header { background: #dff3ff; border-radius: 12px; color: #133d72; padding: 12px; text-align: center; }
header h2, header p { margin: 3px 0; }
.contact-pad input { width: 100%; text-align: center; font-size: clamp(20px, 4vw, 30px); letter-spacing: .1em; min-height: 50px; }
.keypad { display: grid; grid-template-columns: repeat(3, 1fr); gap: 7px; }
.keypad button { min-height: clamp(44px, 7vh, 64px); font-size: 23px; font-weight: 650; background: var(--surface-2); color: var(--text); border: 1px solid var(--border); border-radius: 9px; }
.keypad button:active { background: var(--border); }
.pad-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
.pad-actions button { min-height: 46px; }
.contact-error { color: var(--red); margin: 0; text-align: center; }
</style>
