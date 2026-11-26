<template>
  <section class="bank-settings sec-card">
    <h2><Icon name="bank" /> {{ t('Bank details on customer display') }}</h2>
    <p class="muted">{{ t('Show receiving instructions automatically during payment. Upload your bank logo and official payment QR, then preview what the customer sees.') }}</p>
    <p v-if="!session.settings.enable_customer_display" class="bank-message">{{ t('Enable Customer-facing display in Features, then open Display from Sell on the customer monitor.') }}</p>
    <p v-if="loading" role="status">{{ t('Loading…') }}</p>
    <template v-else>
      <label class="inline-check"><input type="checkbox" v-model="config.enabled" /> {{ t('Show bank details automatically') }}</label>
      <label class="field"><span>{{ t('When to show') }}</span><select v-model="config.trigger"><option value="checkout">{{ t('When the payment page opens') }}</option><option value="bank">{{ t('When the configured bank payment method is selected') }}</option></select></label>
      <div class="bank-account-tabs"><button v-for="(account, index) in config.accounts" :key="index" class="btn btn-outline" :aria-pressed="active === index" @click="active = index">{{ account.bank_name || t('Account {n}', { n: index + 1 }) }}</button><button class="btn btn-outline" :disabled="config.accounts.length >= 12" @click="addAccount"><Icon name="plus" /> {{ t('Add bank account') }}</button></div>
      <div v-if="current" class="bank-editor">
        <div class="bank-fields">
          <label v-for="field in fields" :key="field.key" class="field"><span>{{ t(field.label) }}</span><input v-model="current[field.key]" :maxlength="field.key === 'currency' ? 3 : 140" /></label>
          <label class="field"><span>{{ t('Register / outlet') }}</span><select v-model="current.pos_profile"><option value="">{{ t('All authorized outlets') }}</option><option v-for="profile in session.availableProfiles" :key="profile" :value="profile">{{ profile }}</option></select></label>
          <label class="field"><span>{{ t('Payment method') }}</span><input v-model="current.payment_mode" list="bank-payment-modes" :placeholder="t('Exact Mode of Payment name')" /><datalist id="bank-payment-modes"><option v-for="mode in session.paymentModes" :key="mode.mode_of_payment" :value="mode.mode_of_payment" /></datalist></label>
          <p class="muted small span-all">{{ t('A blank currency matches any sale currency. For a bank-only trigger, enter the exact bank payment method. Accounts for another outlet or currency stay hidden.') }}</p>
          <label class="field span-all"><span>{{ t('Customer instructions') }}</span><textarea v-model="current.instructions" maxlength="500" rows="2" /></label>
          <label class="field"><span>{{ t('Bank logo') }}</span><input type="file" accept="image/png,image/jpeg,image/webp" :disabled="!!uploading" @change="upload($event, 'logo')" /><button v-if="current.logo" class="btn btn-outline" @click="current.logo = ''">{{ t('Remove logo') }}</button></label>
          <label class="field"><span>{{ t('Official bank QR image') }}</span><input type="file" accept="image/png,image/jpeg,image/webp" :disabled="!!uploading" @change="upload($event, 'qr_image')" /><button v-if="current.qr_image" class="btn btn-outline" @click="current.qr_image = ''">{{ t('Remove QR image') }}</button></label>
          <label class="field span-all"><span>{{ t('QR payload (optional alternative to an image)') }}</span><textarea v-model="current.qr_payload" rows="2" /><small class="muted">{{ t('Paste the payment payload supplied by your bank. An uploaded image takes priority. An account number alone is not a payment QR.') }}</small></label>
          <label class="field"><span>{{ t('Logo size') }} · {{ current.logo_size }} px</span><input type="range" min="32" max="160" v-model.number="current.logo_size" /></label>
          <label class="field"><span>{{ t('QR size') }} · {{ current.qr_size }} px</span><input type="range" min="140" max="360" v-model.number="current.qr_size" /></label>
          <button class="btn btn-outline" :disabled="!!uploading" @click="removeAccount"><Icon name="trash" /> {{ t('Remove bank account') }}</button>
        </div>
        <div class="bank-preview"><h3><Icon name="monitor" /> {{ t('Customer preview') }}</h3><BankTransferCard :account="current" :amount="money(12500, current.currency || session.localCurrency)" /></div>
      </div>
      <p v-if="uploading" role="status">{{ t('Uploading…') }}</p>
      <p v-if="error" role="alert" class="neg">{{ error }}</p>
      <p v-if="saved" role="status" class="bank-message">{{ t('Bank display settings saved.') }}</p>
      <button class="btn btn-primary" :disabled="saving || !!uploading || session.offline" @click="save"><Icon name="check" /> {{ saving ? t('Saving…') : t('Save bank display settings') }}</button>
    </template>
  </section>
</template>
<script setup>
import { computed, ref, onMounted } from 'vue'
import { useSessionStore } from '../stores/session'
import { call } from '../api'
import { money } from '../format'
import { t } from '../i18n'
import Icon from './Icon.vue'
import BankTransferCard from './BankTransferCard.vue'
const session = useSessionStore()
const config = ref({ enabled: false, trigger: 'checkout', accounts: [] })
const active = ref(0), loading = ref(true), saving = ref(false), uploading = ref(''), error = ref(''), saved = ref(false)
const current = computed(() => config.value.accounts[active.value])
const fields = [{ key: 'bank_name', label: 'Bank name *' }, { key: 'holder', label: 'Account holder *' }, { key: 'account_number', label: 'Account number *' }, { key: 'branch', label: 'Branch' }, { key: 'swift', label: 'SWIFT / bank code' }, { key: 'currency', label: 'Account currency (e.g. LKR)' }]
function addAccount() {
  config.value.accounts.push({ bank_name: '', holder: '', account_number: '', branch: '', swift: '', currency: session.localCurrency, pos_profile: session.posProfile, payment_mode: '', logo: '', qr_image: '', qr_payload: '', instructions: '', logo_size: 72, qr_size: 240 })
  active.value = config.value.accounts.length - 1
}
function removeAccount() { config.value.accounts.splice(active.value, 1); active.value = Math.max(active.value - 1, 0) }
async function upload(event, field) {
  const file = event.target.files?.[0], account = current.value
  if (!file || !account) return
  error.value = ''; saved.value = false
  if (file.size > 2 * 1024 * 1024) { error.value = t('Choose an image smaller than 2 MB.'); event.target.value = ''; return }
  uploading.value = field
  try {
    const content = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(',')[1]); reader.onerror = reject; reader.readAsDataURL(file) })
    const result = await call('esafepos.api.bank_display.upload_image', { content, kind: field === 'logo' ? 'logo' : 'qr' })
    account[field] = result.file_url
  } catch (e) { error.value = e.message || t('Upload failed') }
  finally { uploading.value = ''; event.target.value = '' }
}
async function save() {
  error.value = ''; saved.value = false
  if (config.value.trigger === 'bank' && config.value.accounts.some(row => !row.payment_mode.trim())) { error.value = t('Choose a payment method for every bank account when using the bank-only trigger.'); return }
  saving.value = true
  try { config.value = await call('esafepos.api.bank_display.save_settings', { config: config.value }); session.settings.bank_transfer_display = config.value; saved.value = true }
  catch (e) { error.value = e.message }
  finally { saving.value = false }
}
onMounted(async () => { try { config.value = await call('esafepos.api.bank_display.get_settings') } catch (e) { error.value = e.message } finally { loading.value = false } })
</script>
<style scoped>
.bank-settings h2, .bank-preview h3 { display: flex; align-items: center; gap: 8px; font-size: 18px; }
.bank-settings > p { line-height: 1.6; }
.bank-settings > .field { margin-top: 18px; max-width: 550px; }
.bank-account-tabs { display: flex; flex-wrap: wrap; gap: 8px; margin: 20px 0; }
.bank-account-tabs [aria-pressed=true] { border-color: var(--brand); color: var(--brand-dark); background: var(--surface-2); }
.bank-editor { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 24px; margin-bottom: 24px; }
.bank-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; align-content: start; }
.field { display: grid; align-content: start; gap: 7px; font-size: 13px; }
.field input, .field select, .field textarea { width: 100%; min-width: 0; }
.field input[type=range] { margin-inline: 0; padding: 0; }
.span-all { grid-column: 1 / -1; }
.bank-message { padding: 12px; border-inline-start: 3px solid var(--brand); background: var(--surface-2); }
.bank-settings button { transition: transform .16s ease, background .16s ease; }
.bank-settings button:hover:not(:disabled) { transform: translateY(-1px); }
.bank-settings button:active:not(:disabled) { transform: translateY(1px); }
@media (max-width: 1100px) { .bank-editor { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 500px) { .bank-fields { grid-template-columns: minmax(0, 1fr); } }
@media (prefers-reduced-motion: reduce) { .bank-settings button { transition: none; transform: none !important; } }
</style>
