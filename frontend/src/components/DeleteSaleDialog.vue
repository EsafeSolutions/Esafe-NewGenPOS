<template>
  <div class="modal-backdrop" @click.self="close" @keydown.esc.prevent="close">
    <section class="modal delete-sale" role="dialog" aria-modal="true" aria-labelledby="delete-sale-title">
      <div class="modal-header">
        <span id="delete-sale-title">{{ t('Permanently delete sale') }}</span>
        <button class="btn-ghost" :aria-label="t('Close')" :disabled="deleting" @click="close"><Icon name="close" /></button>
      </div>
      <div class="modal-body">
        <p class="invoice-number">{{ invoice }}</p>
        <p v-if="loading" role="status">{{ t('Checking this sale and its linked transactions…') }}</p>
        <p v-if="error" class="delete-error" role="alert">{{ error }}</p>
        <div v-if="check && !check.eligible" class="delete-error" role="alert">
          <b>{{ t('This sale cannot be deleted here') }}</b>
          <p>{{ check.blocker }}</p>
        </div>
        <form v-if="check?.eligible" id="delete-sale-form" @submit.prevent="remove">
          <p>{{ t('ERPNext will cancel this invoice and reverse its native stock and accounting effects before removing the invoice and its lines.') }}</p>
          <div class="delete-impact">
            <b>{{ money(check.amount, check.currency) }}</b>
            <p>{{ t('This cannot be undone from the POS. The manager audit keeps the invoice number, amount and reason.') }}</p>
            <p>{{ t('Card refunds and physical cash must be handled separately. Refresh affected tills before using offline returns.') }}</p>
          </div>
          <label>
            <span>{{ t('Reason for deletion') }}</span>
            <textarea ref="reasonInput" v-model.trim="reason" rows="2" minlength="5" maxlength="500" required :disabled="deleting" :placeholder="t('Explain the mistake (at least 5 characters)')" />
          </label>
          <label>
            <span>{{ t('Type the exact invoice number to confirm') }}</span>
            <input v-model="confirmation" type="text" autocomplete="off" spellcheck="false" required :disabled="deleting" />
          </label>
          <label class="payment-confirmation">
            <input v-model="paymentHandled" type="checkbox" :disabled="deleting" />
            <span>{{ t('I have checked the customer payment and handled any cash or card refund required.') }}</span>
          </label>
        </form>
      </div>
      <div class="modal-footer">
        <button class="btn btn-outline" :disabled="deleting" @click="close">{{ t('Back to receipt') }}</button>
        <button v-if="error || check && !check.eligible" class="btn btn-outline" :disabled="loading || deleting || session.offline" @click="load">{{ t('Check again') }}</button>
        <button v-if="check?.eligible" class="btn btn-danger" type="submit" form="delete-sale-form" :disabled="!ready || deleting || session.offline">
          {{ deleting ? t('Deleting…') : t('Permanently delete sale') }}
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import Icon from './Icon.vue'
import { call, OfflineError } from '../api'
import { useSessionStore } from '../stores/session'
import { forgetShiftSale } from '../offline'
import { money } from '../format'
import { t } from '../i18n'
const props = defineProps({ invoice: { type: String, required: true }, doctype: { type: String, required: true } })
const emit = defineEmits(['close', 'deleted'])
const session = useSessionStore()
const check = ref(null), loading = ref(false), deleting = ref(false), error = ref('')
const reason = ref(''), confirmation = ref(''), paymentHandled = ref(false), reasonInput = ref(null)
const ready = computed(() => check.value?.eligible && reason.value.length >= 5 && reason.value.length <= 500 && confirmation.value === props.invoice && paymentHandled.value)
function close() { if (!deleting.value) emit('close') }
async function load() {
  if (loading.value || deleting.value) return
  if (session.offline) { error.value = t('Connect to the internet to check or delete a sale.'); return }
  loading.value = true
  error.value = ''
  check.value = null
  confirmation.value = ''
  paymentHandled.value = false
  try {
    check.value = await call('esafepos.api.sale_deletion.check_sale_deletion', { invoice: props.invoice, doctype: props.doctype })
    if (check.value.deleted) { await finish(check.value); return }
    await nextTick()
    reasonInput.value?.focus()
  } catch (e) { error.value = e.message }
  finally { loading.value = false }
}
async function finish(result) {
  await forgetShiftSale(props.invoice).catch(() => {})
  session.notify(t('Sale permanently deleted'))
  emit('deleted', result)
}
async function remove() {
  if (!ready.value || deleting.value || session.offline) return
  deleting.value = true
  error.value = ''
  try {
    const result = await call('esafepos.api.sale_deletion.permanently_delete_sale', {
      invoice: props.invoice, doctype: props.doctype, reason: reason.value, confirm_invoice: confirmation.value,
      expected_modified: check.value.modified, payment_handled: paymentHandled.value ? 1 : 0,
    }, { timeout: 30000 })
    await finish(result)
  } catch (e) {
    error.value = e instanceof OfflineError
      ? t('The delete result could not be confirmed. Press Check again to read the server status.')
      : e.message
  } finally { deleting.value = false }
}
onMounted(load)
</script>

<style scoped>
.delete-sale { width: 500px; max-width: calc(100vw - 24px); }
.delete-sale p { line-height: 1.55; }
.invoice-number { font-weight: 700; overflow-wrap: anywhere; margin-top: 0; }
.delete-impact { padding: 12px; border: 1px solid var(--border); border-inline-start: 3px solid var(--red); border-radius: var(--radius); background: var(--surface-2); margin: 14px 0; }
.delete-impact p { margin: 8px 0 0; font-size: 12px; }
.delete-sale form > label { display: grid; gap: 6px; margin-top: 14px; font-size: 12px; font-weight: 600; }
.delete-sale textarea, .delete-sale input[type='text'] { width: 100%; min-width: 0; }
.delete-sale .payment-confirmation { display: flex; gap: 10px; align-items: flex-start; line-height: 1.5; }
.payment-confirmation input { margin-top: 3px; flex-shrink: 0; }
.delete-error { color: var(--red); line-height: 1.6; overflow-wrap: anywhere; }
.delete-sale .modal-footer { flex-wrap: wrap; }
@media (max-width: 480px) { .delete-sale .modal-footer > button { flex: 1 1 100%; } }
</style>
