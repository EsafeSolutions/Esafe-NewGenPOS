<template>
  <section class="bank-transfer-card" :aria-label="t('Bank transfer details')">
    <div class="bank-heading">
      <img v-if="account.logo && !logoFailed" :src="account.logo" :style="{ width: `${account.logo_size || 72}px`, height: `${account.logo_size || 72}px` }" :alt="account.bank_name" @error="logoFailed = true" />
      <Icon v-else name="bank" :size="36" />
      <div><small>{{ t('Pay by bank transfer') }}</small><h2>{{ account.bank_name }}</h2></div>
    </div>
    <p v-if="amount" class="bank-amount"><span>{{ t('Amount to send') }}</span><strong>{{ amount }}</strong></p>
    <div class="bank-instructions">
      <dl>
        <div><dt>{{ t('Account holder') }}</dt><dd>{{ account.holder }}</dd></div>
        <div><dt>{{ t('Account number') }}</dt><dd class="bank-number">{{ account.account_number }}</dd></div>
        <div v-if="account.branch"><dt>{{ t('Branch') }}</dt><dd>{{ account.branch }}</dd></div>
        <div v-if="account.swift"><dt>{{ t('SWIFT / bank code') }}</dt><dd>{{ account.swift }}</dd></div>
        <div v-if="account.currency"><dt>{{ t('Account currency') }}</dt><dd>{{ account.currency }}</dd></div>
      </dl>
      <div v-if="qr && !qrFailed" class="bank-qr"><img :src="qr" :style="{ width: `${account.qr_size || 240}px` }" :alt="t('Bank payment QR code')" @error="qrFailed = true" /><span>{{ t('Scan with your banking app') }}</span></div>
      <p v-else-if="qrFailed" role="status">{{ t('QR image unavailable. Use the account details.') }}</p>
    </div>
    <p v-if="account.instructions" class="bank-note">{{ account.instructions }}</p>
    <div class="bank-steps"><span><b>1</b> {{ t('Check the recipient') }}</span><span><b>2</b> {{ t('Send the transfer') }}</span><span><b>3</b> {{ t('Show confirmation to the cashier') }}</span></div>
    <small>{{ t('A QR scan does not confirm payment. The cashier verifies receipt before completing the sale.') }}</small>
  </section>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { bankQrSource } from '../bankDisplay'
import { t } from '../i18n'
import Icon from './Icon.vue'
const props = defineProps({ account: { type: Object, required: true }, amount: { type: String, default: '' } })
const qr = computed(() => bankQrSource(props.account))
const logoFailed = ref(false), qrFailed = ref(false)
watch(() => props.account, () => { logoFailed.value = false; qrFailed.value = false }, { deep: true })
</script>
<style scoped>
.bank-transfer-card { padding: clamp(16px, 2vw, 30px); border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--card-bg); color: var(--text); min-width: 0; }
.bank-heading { display: flex; align-items: center; gap: 16px; color: var(--brand-dark); }
.bank-heading img { object-fit: contain; max-width: 35%; }
.bank-heading h2 { margin: 4px 0 0; font-size: clamp(20px, 2vw, 32px); overflow-wrap: anywhere; }
.bank-instructions { display: flex; align-items: center; justify-content: space-between; gap: 24px; margin: 20px 0; }
dl { flex: 1; min-width: 0; margin: 0; display: grid; gap: 14px; }
dt, .bank-qr span { font-size: 13px; color: var(--text-muted); }
dd { margin: 4px 0 0; font-weight: 700; font-size: 1.1em; overflow-wrap: anywhere; }
.bank-number { font-size: clamp(22px, 2.3vw, 36px); letter-spacing: .04em; font-variant-numeric: tabular-nums; }
.bank-qr { display: grid; justify-items: center; gap: 8px; flex-shrink: 0; max-width: 48%; }
.bank-qr img { max-width: 100%; height: auto; background: white; border-radius: 8px; }
.bank-amount { display: flex; justify-content: space-between; gap: 12px; padding: 16px; background: var(--surface-2); border-radius: var(--radius); }
.bank-amount strong { font-size: 1.3em; }
.bank-note { white-space: pre-wrap; overflow-wrap: anywhere; }
.bank-steps { display: flex; flex-wrap: wrap; gap: 16px; padding: 12px 0; }
.bank-steps span { display: flex; align-items: center; gap: 6px; font-size: 13px; }
.bank-steps b { display: grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; background: var(--surface-2); color: var(--brand-dark); }
.bank-transfer-card > small { display: block; color: var(--text-muted); line-height: 1.5; }
@media (max-width: 600px) { .bank-instructions { flex-direction: column; align-items: stretch; gap: 16px; } .bank-qr { max-width: 100%; } .bank-amount { flex-wrap: wrap; } }
</style>
