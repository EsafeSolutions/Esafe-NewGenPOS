<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only -->
<template>
  <dialog ref="dialog" class="sale-thank-you" data-pos-sound="off" aria-labelledby="thank-you-title" aria-describedby="thank-you-message" @cancel.prevent="$emit('close')">
    <div class="thanks-mark"><Icon name="check" :size="36" /></div>
    <h2 id="thank-you-title">{{ t('Thank you very much for your purchase!') }}</h2>
    <p id="thank-you-message" class="thanks-message">{{ t('Come again. We wish you all the best!') }}</p>
    <div class="thanks-summary">
      <p v-if="Number(receipt.change_amount) > 0"><Icon name="cash" /> {{ t('Change handed over') }} <strong>{{ change }}</strong></p>
      <p v-if="Number(receipt.loyalty_change_points) > 0"><Icon name="star" /> {{ t('{points} points saved from your change', { points: receipt.loyalty_change_points }) }}</p>
      <p v-if="receipt.offline" class="muted small">{{ t('Saved offline, it will post to ERPNext automatically when the connection returns.') }}</p>
      <span class="muted small">{{ receipt.name }}</span>
    </div>
    <p v-if="greetingStatus === 'unavailable'" role="status" class="muted small">{{ t('Voice is unavailable on this device. The thank-you message will still appear.') }}</p>
    <div class="thanks-actions">
      <button v-if="soundPreferences.greeting && canSpeakGreeting()" type="button" class="btn btn-outline" :disabled="!soundPreferences.volume" @click="speakThankYou">{{ t('Replay greeting') }}</button>
      <button type="button" class="btn btn-primary" autofocus @click="$emit('close')">{{ t('New Sale') }}</button>
    </div>
  </dialog>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import Icon from './Icon.vue'
import { t } from '../i18n'
import { money } from '../format'
import { soundPreferences, greetingStatus, speakThankYou, stopGreeting, canSpeakGreeting } from '../posSounds'

const props = defineProps({ receipt: { type: Object, required: true } })
defineEmits(['close'])
const dialog = ref(null)
const change = computed(() => {
  const receipt = props.receipt
  const local = receipt.company_currency && receipt.currency !== receipt.company_currency && receipt.change_currency !== receipt.currency
  return money(local ? receipt.base_change_amount ?? receipt.change_amount : receipt.change_amount,
    local ? receipt.company_currency : receipt.currency)
})
onMounted(() => dialog.value.showModal())
onBeforeUnmount(() => { stopGreeting(); dialog.value?.close() })
</script>

<style scoped>
.sale-thank-you { width: min(460px, calc(100vw - 24px)); max-height: 90dvh; overflow: auto; padding: 32px; text-align: center; border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--card-bg); color: var(--text); box-shadow: var(--shadow-md); }
.sale-thank-you::backdrop { background: rgba(24, 30, 44, .55); }
.thanks-mark { display: grid; place-items: center; width: 72px; height: 72px; margin: 0 auto 20px; border-radius: 50%; background: var(--surface-2); color: var(--brand-dark); }
.sale-thank-you h2 { margin: 0; font-size: 26px; line-height: 1.25; }
.thanks-message { margin: 14px 0 24px; color: var(--text-muted); line-height: 1.6; font-size: 17px; }
.thanks-summary { padding: 18px 0; border-block: 1px solid var(--border); overflow-wrap: anywhere; }
.thanks-summary p { display: flex; justify-content: center; align-items: center; flex-wrap: wrap; gap: 8px; margin: 0 0 12px; line-height: 1.5; }
.thanks-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 24px; }
.thanks-actions .btn { flex: 1; min-height: 46px; }
@media (max-width: 460px) { .sale-thank-you { padding: 26px 20px; } .sale-thank-you h2 { font-size: 24px; } .thanks-actions { flex-direction: column; } }
</style>
