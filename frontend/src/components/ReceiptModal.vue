<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<template>
  <div v-if="!deleteSaleOpen && !greetingOpen" class="modal-backdrop" @click.self="dismissReceipt">
    <div class="modal" style="width: 440px">
      <div class="modal-header">
        {{
          receipt.is_return
            ? receipt.offline ? t('Refund queued (offline)') : t('Refund complete')
            : receipt.offline ? t('Sale queued (offline)') : t('Sale complete')
        }}
        <button v-if="!canThankCustomer" class="btn-ghost" :aria-label="t('Close receipt')" @click="dismissReceipt"><Icon name="close" /></button>
      </div>
      <div class="modal-body">
        <div v-if="receipt.offline && receipt.is_return" class="offline-banner">
          {{ t('Refund {amount} to the customer. It posts to ERPNext when the connection is back.', { amount: money(Math.abs(receipt.grand_total), receipt.currency) }) }}
        </div>
        <div v-else-if="receipt.offline" class="offline-banner">
          {{ t('Saved offline, it will post to ERPNext automatically when the connection returns.') }}
        </div>
        <div v-if="receipt.change_amount > 0" class="change-banner">
          {{ t('Change due:') }}
          <strong>{{
            receipt.base_change_amount != null && receipt.company_currency && receipt.currency !== receipt.company_currency
              && receipt.change_currency !== receipt.currency
              ? money(receipt.base_change_amount, receipt.company_currency)
              : money(receipt.change_amount, receipt.currency)
          }}</strong>
        </div>
        <div v-if="canThankCustomer" class="handover-note">
          <p v-if="Number(receipt.loyalty_change_points) > 0"><Icon name="star" /> {{ t('{points} points saved from your change', { points: receipt.loyalty_change_points }) }}</p>
          <p>{{ Number(receipt.change_amount) > 0
            ? t('Hand over the change and receipt, then select Change handed over to thank the customer.')
            : t('Hand over the receipt, then select Thank customer to finish the sale.') }}</p>
        </div>
        <div v-if="receipt.gift_card_no" class="giftcard-banner">
          <Icon name="gift" /> {{ t('Gift card') }} <strong>{{ receipt.gift_card_no }}</strong>,
          {{ t('balance') }} {{ money(receipt.gift_card_balance) }}<span v-if="receipt.gift_card_expiry"> · {{ t('expires') }} {{ receipt.gift_card_expiry }}</span>
        </div>

        <!-- A return posts in the company that made the sale, so another
             company's outlet cannot take it back: say so now, not after the
             cashier has picked the items. -->
        <div v-if="otherCompany && !receipt.is_return" class="company-note">
          {{ t('Sold by {company}. It can be returned or exchanged at one of its outlets.', { company: receipt.company }) }}
        </div>
        <div v-if="shareOpen" class="receipt-message-panel">
          <button type="button" class="btn-ghost" :aria-label="t('Close message')" @click="shareOpen = false">{{ t('Close message') }}</button>
          <CustomerMessageComposer :invoice="receipt.name" :customer="profileCustomer" :mobile-number="receipt.customer_phone"
            :image-source="() => receiptView?.$el" />
        </div>
        <form v-if="customerEditorOpen" class="share-card" @submit.prevent="saveCustomerDetails">
          <label class="share-mobile">
            <span>{{ t('Contact number') }}</span>
            <input ref="customerPhoneInput" v-model.trim="customerPhone" type="tel" inputmode="tel"
              autocomplete="tel" maxlength="32" required :disabled="customerSaving" />
          </label>
          <label v-if="customerNameOpen" class="share-mobile">
            <span>{{ t('Customer name (optional)') }}</span>
            <input ref="customerNameInput" v-model.trim="customerName" autocomplete="name"
              maxlength="140" :disabled="customerSaving" />
          </label>
          <div class="share-help muted small">{{ t('Leave the name blank to use the contact number on this invoice.') }}</div>
          <div class="share-actions">
            <button v-if="!customerNameOpen" type="button" class="btn btn-outline"
              :disabled="customerSaving" @click="showCustomerName">{{ t('Add name') }}</button>
            <button type="button" class="btn btn-outline" :disabled="customerSaving" @click="customerEditorOpen = false">{{ t('Cancel') }}</button>
            <button class="btn btn-primary" :disabled="customerSaving">{{ t('Save details') }}</button>
          </div>
        </form>
        <ReceiptView ref="receiptView" :receipt="receipt" printable />
      </div>
      <div class="modal-footer">
        <button
          v-if="!receipt.is_return && !receipt.offline && canRefund && !otherCompany"
          class="btn btn-outline refund-btn"
          data-tour="receipt-refund"
          @click="$emit('refund', receipt.name)"
        >
          {{ t('Refund…') }}
        </button>
        <!-- Swap goods in one step: the same picker as a refund, then the sell
             screen for what the customer takes instead. -->
        <button
          v-if="!receipt.is_return && !receipt.offline && canExchange && !soldInOtherCurrency && !otherCompany"
          class="btn btn-outline"
          data-tour="receipt-exchange"
          @click="$emit('exchange', receipt.name)"
        >
          <Icon name="exchange" /> {{ t('Exchange…') }}
        </button>
        <!-- Refunds live in History (one money-flow path), jump there with
             this sale already open rather than duplicating the flow here. -->
        <button
          v-if="showOpenInHistory && !receipt.offline"
          class="btn btn-outline"
          @click="$emit('open-in-history', receipt.name)"
        >
          {{ t('Open in History') }}
        </button>
        <button
          v-if="session.settings.enable_email_receipt && !receipt.offline"
          class="btn btn-outline"
          :disabled="emailing"
          @click="emailReceipt"
        >
          {{ emailing ? t('Sending…') : t('Email receipt') }}
        </button>
        <button v-if="(receipt.can_edit_customer_details ?? receipt.can_edit_walk_in) && !session.offline && !receipt.offline"
          class="btn btn-outline" :aria-expanded="customerEditorOpen" @click="openCustomerDetails">
          {{ t('Change customer name') }}
        </button>
        <button v-if="receipt.can_link_customer && !session.offline && !receipt.offline"
          class="btn btn-outline" @click="linkCustomerOpen = true">
          {{ t('Add customer to invoice') }}
        </button>
        <button v-if="profileCustomer && session.permissions.customers && !receipt.offline" type="button" class="btn btn-outline" @click="openCustomerProfile">{{ t('Customer profile') }}</button>
        <button v-if="!receipt.offline" class="btn btn-outline" @click="toggleShare">
          <Icon name="globe" /> {{ t('Send e-invoice') }}
        </button>
        <button v-if="!isReprint || mayReprint" class="btn btn-outline" data-tour="receipt-print" :disabled="printing" @click="print()">
          {{ printing ? t('Printing…') : t('Print receipt') }}
        </button>
        <button v-if="useSilent && (!isReprint || mayReprint)" class="btn btn-outline" :disabled="printing" @click="print(true)">{{ t('Browser print') }}</button>
        <button v-if="useSilent && printManager.state.connection!=='connected'" class="btn btn-outline" :disabled="printing" @click="connectManager">{{ t('Connect Esafe Print Manager') }}</button>
        <span v-if="isReprint && !mayReprint" class="muted small reprint-note">{{ t('Printing it again is kept to whoever may reprint a receipt.') }}</span>
        <CashDrawerButton />
        <button v-if="allowPermanentDelete && isReprint && session.permissions.is_manager && session.permissions.can_delete_sales !== false && !receipt.offline"
          class="btn btn-outline" :disabled="session.offline || printing" @click="deleteSaleOpen = true">
          {{ t('Delete sale…') }}
        </button>
        <button ref="finishButton" class="btn btn-primary" :disabled="printing" :data-pos-sound="canThankCustomer ? 'off' : undefined" @click="finishReceipt">
          {{ canThankCustomer ? Number(receipt.change_amount) > 0 ? t('Change handed over') : t('Thank customer') : receipt.is_return ? t('Done') : t('New Sale') }}
        </button>
      </div>
    </div>
  </div>
  <SaleThankYou v-if="greetingOpen" :receipt="receipt" @close="$emit('close')" />
  <CustomerModal v-if="linkCustomerOpen" :invoice-receipt="receipt"
    @close="linkCustomerOpen = false" @linked="onCustomerLinked" />
  <DeleteSaleDialog v-if="deleteSaleOpen" :invoice="receipt.name" :doctype="receipt.doctype"
    @close="deleteSaleOpen = false" @deleted="onSaleDeleted" />
</template>

<script setup>
import Icon from './Icon.vue'
import CustomerMessageComposer from './CustomerMessageComposer.vue'
import { useRouter } from 'vue-router'
import ReceiptView from './ReceiptView.vue'
import CashDrawerButton from './printing/CashDrawerButton.vue'
import CustomerModal from './CustomerModal.vue'
import DeleteSaleDialog from './DeleteSaleDialog.vue'
import SaleThankYou from './SaleThankYou.vue'
import { playSaleGreeting } from '../posSounds'
import { displayReceipt } from '../customerDisplay'
import { computed, nextTick, onMounted, ref } from 'vue'
import { call } from '../api'
import { useSessionStore } from '../stores/session'
import { money } from '../format'
import { t } from '../i18n'
import { printReceipt } from '../receiptPrint'
import { receiptLayoutFor } from '../receiptLayout.js'
import { nativeReceipt, printManager, printStatusMessage, silentPrinting, cashDrawer } from '../printing/index.js'

const props = defineProps({
  showOpenInHistory: { type: Boolean, default: false },
  receipt: Object,
  canRefund: { type: Boolean, default: false },
  canExchange: { type: Boolean, default: false },
  // Opened later, from History or Customers: printing it again is a reprint.
  reprint: { type: Boolean, default: false },
  autoPrint: { type: Boolean, default: false },
  allowPermanentDelete: { type: Boolean, default: false },
  checkoutCompletion: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'refund', 'exchange', 'open-in-history', 'updated', 'deleted'])

const session = useSessionStore()
const router = useRouter()
const receiptView = ref(null)
const finishButton = ref(null)
const greetingOpen = ref(false)
const canThankCustomer = computed(() => props.checkoutCompletion && !props.reprint && !props.receipt.is_return)
function dismissReceipt() {
  if (canThankCustomer.value) {
    finishButton.value?.focus()
    return
  }
  emit('close')
}
function finishReceipt() {
  if (!canThankCustomer.value) { emit('close'); return }
  if (greetingOpen.value) return
  greetingOpen.value = true
  if (displayReceipt.value?.receipt === props.receipt.name) {
    displayReceipt.value = { ...displayReceipt.value, greeting: true }
  }
  playSaleGreeting()
}
const profileCustomer = computed(() => props.receipt.linked_customer ||
  (!props.receipt.walk_in_code && props.receipt.customer !== session.defaultCustomer ? props.receipt.customer : null))
const linkCustomerOpen = ref(false)
const deleteSaleOpen = ref(false)
function onSaleDeleted(result) {
  deleteSaleOpen.value = false
  emit('deleted', result)
  emit('close')
}
const printing = ref(false)
const emailing = ref(false)
const shareOpen = ref(false)
const customerEditorOpen = ref(false)
const customerSaving = ref(false)
const customerPhone = ref('')
const customerPhoneInput = ref(null)
const customerName = ref('')
const customerNameOpen = ref(false)
const customerNameInput = ref(null)

function onCustomerLinked(updated) {
  linkCustomerOpen.value = false
  customerEditorOpen.value = false
  shareOpen.value = false
  emit('updated', updated)
  session.notify(t('Customer linked to invoice'))
}

async function openCustomerDetails() {
  if (!customerEditorOpen.value) {
    customerPhone.value = props.receipt.customer_phone || ''
    customerName.value = props.receipt.receipt_name || ''
    customerNameOpen.value = Boolean(customerName.value)
  }
  shareOpen.value = false
  customerEditorOpen.value = true
  await nextTick()
  customerPhoneInput.value?.focus()
}

async function showCustomerName() {
  customerNameOpen.value = true
  await nextTick()
  customerNameInput.value?.focus()
}

async function saveCustomerDetails() {
  if (customerSaving.value) return
  customerSaving.value = true
  try {
    const updated = await call('esafepos.api.sales.save_walk_in_details', {
      invoice: props.receipt.name,
      mobile_no: customerPhone.value,
      ...(customerNameOpen.value ? { customer_name: customerName.value } : {}),
    })
    emit('updated', updated)
    customerEditorOpen.value = false
    session.notify(t('Customer details saved'))
  } catch (error) {
    session.notify(error.message, true)
  } finally {
    customerSaving.value = false
  }
}

// A sale of another company (a manager covering outlets of two companies).
const otherCompany = computed(
  () => Boolean(props.receipt?.company && session.company) && props.receipt.company !== session.company
)

// Exchanges stay in the outlet's currency (esafepos.currency): a sale in
// another currency is refunded and the new goods rung up as a new sale.
const soldInOtherCurrency = computed(
  () =>
    Boolean(props.receipt?.company_currency) &&
    Boolean(props.receipt?.currency) &&
    props.receipt.currency !== props.receipt.company_currency
)

function toggleShare() { shareOpen.value = !shareOpen.value }
function openCustomerProfile() {
  if (!profileCustomer.value) return
  router.push({path: '/customers', query: {customer: profileCustomer.value}})
  emit('close')
}

async function emailReceipt() {
  emailing.value = true
  try {
    // Try the address on file first; if there is none (or it fails), ask once.
    const res = await call('esafepos.api.sales.email_receipt', { invoice: props.receipt.name })
    session.notify(t('Receipt emailed to {email}', { email: res.email }))
  } catch (e) {
    const typed = (window.prompt(t('Email the receipt to:'), '') || '').trim()
    if (!typed) {
      if (e.message) session.notify(e.message, true)
      return
    }
    try {
      const res = await call('esafepos.api.sales.email_receipt', {
        invoice: props.receipt.name,
        email: typed,
      })
      session.notify(t('Receipt emailed to {email}', { email: res.email }))
    } catch (e2) {
      session.notify(e2.message, true)
    }
  } finally {
    emailing.value = false
  }
}

// A copy printed again (Who can do what, Reprint a receipt): opened later
// from History or Customers, or printed a second time from this screen. The
// sale's own first print never is (0.60.0: until then only a network printer
// checked it, and a refused one fell back to the browser).
const printedOnce = ref(false)
const isReprint = computed(() => props.reprint || printedOnce.value)
const mayReprint = computed(() => session.permissions?.can_reprint !== false)
const nativeConfig = computed(() => props.receipt.printing_defaults || session.settings.esafe_printing || {})
const useSilent = computed(() => !!nativeConfig.value.silent && !session.offline && !props.receipt.offline)

async function connectManager() {
  printing.value = true
  try { await printManager.resume(); await printManager.connect({ explicit: true }) }
  catch (error) { session.notify(error.message, true) }
  finally { printing.value = false }
}
onMounted(async () => {
  if (canThankCustomer.value) finishButton.value?.focus()
  if (props.autoPrint && !props.reprint && nativeConfig.value.automatic_receipt && useSilent.value) {
    await nextTick()
    await print(false, true)
  } else if (props.autoPrint && !props.reprint) {
    openAfterPayment()
  }
})
function openAfterPayment(receiptJob) {
  cashDrawer.afterSale({ receipt: props.receipt, profile: props.receipt.pos_profile || session.posProfile,
    user: session.user, offline: session.offline, reprint: props.reprint, receiptJob })
    .then((result) => { if (result) session.notify(t(result.state === 'unknown' ? 'Drawer pulse outcome is unknown. Inspect the drawer and Print jobs; nothing is replayed automatically.' : result.state === 'failed' ? `Drawer pulse failed: ${result.error}` : 'Drawer pulse accepted. Check the physical drawer.')) })
    .catch((error) => session.notify(error.message, true))
}
async function print(forceBrowser = false, automatic = false) {
  if (printing.value) return
  const again = isReprint.value
  if (again && !mayReprint.value) {
    session.notify(t('You are not allowed to reprint a receipt'), true)
    return
  }
  if (!forceBrowser && useSilent.value) {
    printing.value = true
    try {
      await nextTick()
      const result = await nativeReceipt(props.receipt, document.getElementById('receipt-print'), { reprint: again, automatic })
      if (result) {
        printedOnce.value = !!result.agentJobId || result.state === 'unknown'
        session.notify(t(printStatusMessage(result)), ['failed', 'unknown'].includes(result.state))
        if (automatic && !again) openAfterPayment(result)
      }
    } catch (error) { session.notify(error.message, true) }
    finally { printing.value = false }
    return
  }
  if (forceBrowser && printManager.state.jobs.some((job) => job.reference?.name === props.receipt.name && job.state === 'unknown') &&
      !window.confirm(t('An Esafe print may already have reached the printer. Continue with an additional browser copy?'))) return
  // Asked of the server before anything prints, and kept in the audit log.
  // Offline it cannot be asked: the permission the till holds decides.
  if (again && !props.receipt.offline && !session.offline) {
    try {
      await call('esafepos.api.printing.allow_reprint', { invoice: props.receipt.name })
    } catch (e) {
      session.notify(e.message, true)
      return
    }
  }
  // Priority: ESC/POS network printer -> the POS Profile's Print Format
  // (ERPNext print view) -> the built-in receipt via the browser dialog.
  if (!forceBrowser && session.printerConfigured && !props.receipt.offline && !session.offline) {
    printing.value = true
    try {
      await call('esafepos.api.printing.print_receipt', {
        invoice: props.receipt.name,
        // The reprint was allowed (and logged) above: the printer is not asked again.
        reprint: 0,
      })
      session.notify(t('Receipt sent to printer'))
      printedOnce.value = true
      return
    } catch (e) {
      session.notify(t('Printer failed ({error}), using browser print', { error: e.message }), true)
    } finally {
      printing.value = false
    }
  }
  printedOnce.value = true
  if (session.printFormat && !props.receipt.offline && !session.offline) {
    // Use the sale's ACTUAL doctype (POS Invoice or Sales Invoice, per the
    // profile's mode), hardcoding "POS Invoice" broke custom Print Formats in
    // Sales-Invoice mode.
    const doctype = props.receipt.doctype || session.invoiceMode || 'POS Invoice'
    const url =
      `/printview?doctype=${encodeURIComponent(doctype)}` +
      `&name=${encodeURIComponent(props.receipt.name)}` +
      `&format=${encodeURIComponent(session.printFormat)}` +
      `&no_letterhead=0&trigger_print=1`
    window.open(url, '_blank')
    return
  }
  printing.value = true
  try {
    await nextTick()
    const source = document.getElementById('receipt-print')
    const binding = await printManager.binding(props.receipt.pos_profile || session.posProfile).catch(() => ({}))
    await printReceipt(source, receiptLayoutFor(source, binding))
  } catch (e) {
    session.notify(e.message, true)
  } finally {
    printing.value = false
  }
}
</script>

<style scoped>
.handover-note { margin-bottom: 14px; padding: 14px; background: var(--surface-2); border-radius: var(--radius); line-height: 1.5; font-size: 13px; }
.handover-note p { margin: 0; }
.handover-note p + p { margin-top: 8px; }
.reprint-note { align-self: center; max-width: 220px; }
.offline-banner {
  background: rgba(245, 166, 35, 0.14);
  color: #9a6a0a;
  border-radius: var(--radius);
  padding: 12px 16px;
  text-align: center;
  margin-bottom: 16px;
  font-weight: 600;
}
.giftcard-banner {
  background: rgba(19, 167, 149, 0.08);
  color: var(--brand-dark);
  border-radius: var(--radius);
  padding: 12px 16px;
  text-align: center;
  margin-bottom: 16px;
  font-weight: 600;
}
.change-banner {
  background: rgba(19, 167, 149, 0.1);
  color: var(--brand-dark);
  border-radius: var(--radius);
  padding: 12px 16px;
  font-size: 16px;
  text-align: center;
  margin-bottom: 16px;
}
.refund-btn { margin-inline-end: auto; color: var(--red); }
.company-note {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 14px;
}
.share-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface-2);
  padding: 14px;
  margin-bottom: 14px;
}
.modal-footer { flex-wrap: wrap; }
.share-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.share-mobile { display: grid; gap: 6px; font-size: 12px; font-weight: 700; }
.share-mobile input { width: 100%; background: var(--card-bg); }
.share-actions { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 10px; }
.share-actions .btn { padding: 9px 8px; font-size: 12px; }
.share-link { display: grid; gap: 6px; margin-top: 10px; font-size: 12px; font-weight: 700; }
.share-link small { color: var(--text-muted); font-weight: 500; }
.share-link input { width: 100%; min-height: 44px; padding: 9px 10px; color: var(--text); background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; font-size: 13px; user-select: all; }
.share-note { margin-top: 9px; line-height: 1.4; }
@media (max-width: 460px) {
  .share-actions { grid-template-columns: 1fr; }
}
</style>
