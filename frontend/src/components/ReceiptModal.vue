<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<template>
  <div class="modal-backdrop" @click.self="$emit('close')">
    <div class="modal" style="width: 440px">
      <div class="modal-header">
        {{
          receipt.is_return
            ? receipt.offline ? t('Refund queued (offline)') : t('Refund complete')
            : receipt.offline ? t('Sale queued (offline)') : t('Sale complete')
        }}
        <button class="btn-ghost" @click="$emit('close')"><Icon name="close" /></button>
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
        <div v-if="shareOpen" class="share-card">
          <div class="share-heading">
            <div>
              <strong>{{ t('Send e-invoice') }}</strong>
              <div class="muted small">{{ t('Share a secure invoice link with the customer.') }}</div>
            </div>
            <button class="btn-ghost" :aria-label="t('Close')" @click="shareOpen = false"><Icon name="close" /></button>
          </div>
          <label class="share-mobile">
            <span>{{ t('Customer mobile') }}</span>
            <input v-model.trim="shareMobile" type="tel" inputmode="tel" autocomplete="tel" :placeholder="t('e.g. +94770000000')" />
          </label>
          <div class="share-actions">
            <button class="btn btn-outline" :disabled="sharing || smsing" @click="openWhatsApp">
              {{ sharing ? t('Preparing…') : t('WhatsApp') }}
            </button>
            <button class="btn btn-outline" :disabled="sharing || smsing" @click="sendSms">
              {{ smsing ? t('Sending…') : t('Send SMS') }}
            </button>
            <button class="btn btn-outline" :disabled="sharing || smsing" @click="copyInvoiceLink">
              {{ copied ? t('Link copied') : t('Copy link') }}
            </button>
          </div>
          <div class="muted small share-note">
            {{ t('WhatsApp opens a ready message for confirmation. SMS uses ERPNext SMS Settings.') }}
          </div>
        </div>
        <ReceiptView :receipt="receipt" printable />
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
        <button v-if="!receipt.offline" class="btn btn-outline" @click="toggleShare">
          <Icon name="globe" /> {{ t('Send e-invoice') }}
        </button>
        <button v-if="!isReprint || mayReprint" class="btn btn-outline" data-tour="receipt-print" :disabled="printing" @click="print">
          {{ printing ? t('Printing…') : t('Print receipt') }}
        </button>
        <span v-else class="muted small reprint-note">{{ t('Printing it again is kept to whoever may reprint a receipt.') }}</span>
        <button class="btn btn-primary" @click="$emit('close')">
          {{ receipt.is_return ? t('Done') : t('New Sale') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import Icon from './Icon.vue'
import ReceiptView from './ReceiptView.vue'
import { computed, nextTick, ref } from 'vue'
import { call } from '../api'
import { useSessionStore } from '../stores/session'
import { money } from '../format'
import { t } from '../i18n'
import { printReceipt } from '../receiptPrint'

const props = defineProps({
  showOpenInHistory: { type: Boolean, default: false },
  receipt: Object,
  canRefund: { type: Boolean, default: false },
  canExchange: { type: Boolean, default: false },
  // Opened later, from History or Customers: printing it again is a reprint.
  reprint: { type: Boolean, default: false },
})
defineEmits(['close', 'refund', 'exchange', 'open-in-history'])

const session = useSessionStore()
const printing = ref(false)
const emailing = ref(false)
const shareOpen = ref(false)
const shareMobile = ref('')
const sharing = ref(false)
const smsing = ref(false)
const copied = ref(false)
const shareDetails = ref(null)

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

function toggleShare() {
  shareOpen.value = !shareOpen.value
  if (shareOpen.value && !shareMobile.value) shareMobile.value = props.receipt.customer_phone || ''
}

async function getShareDetails() {
  if (shareDetails.value) return shareDetails.value
  shareDetails.value = await call('esafepos.api.sales.receipt_share_link', {
    invoice: props.receipt.name,
  })
  if (!shareMobile.value && shareDetails.value.mobile) shareMobile.value = shareDetails.value.mobile
  return shareDetails.value
}

function whatsAppNumber() {
  let value = String(shareMobile.value || '').trim().replace(/[\s()-]/g, '')
  if (value.startsWith('00')) value = `+${value.slice(2)}`
  if (value.startsWith('0')) {
    throw new Error(t('Add the country code before sending to WhatsApp (for example +94…).'))
  }
  const digits = value.replace(/^\+/, '')
  if (!/^\d{6,15}$/.test(digits)) {
    throw new Error(t('Enter a valid mobile number, including the country code.'))
  }
  return digits
}

async function openWhatsApp() {
  let digits
  try {
    digits = whatsAppNumber()
  } catch (e) {
    session.notify(e.message, true)
    return
  }
  // Open synchronously so browsers do not treat the tab as an unsolicited
  // popup while the signed link is being requested.
  const tab = window.open('about:blank', '_blank')
  if (!tab) {
    session.notify(t('Allow pop-ups to open WhatsApp.'), true)
    return
  }
  sharing.value = true
  try {
    const details = await getShareDetails()
    const url = `https://wa.me/${digits}?text=${encodeURIComponent(details.message)}`
    tab.location.replace(url)
  } catch (e) {
    tab.close()
    session.notify(e.message, true)
  } finally {
    sharing.value = false
  }
}

async function sendSms() {
  const mobile = String(shareMobile.value || '').trim()
  if (!mobile) {
    session.notify(t('Enter the customer mobile number.'), true)
    return
  }
  smsing.value = true
  try {
    const res = await call('esafepos.api.sales.sms_receipt', {
      invoice: props.receipt.name,
      mobile,
    })
    session.notify(t('E-invoice sent by SMS to {mobile}', { mobile: res.mobile }))
  } catch (e) {
    session.notify(e.message, true)
  } finally {
    smsing.value = false
  }
}

async function copyInvoiceLink() {
  sharing.value = true
  try {
    const details = await getShareDetails()
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(details.url)
    } else {
      const area = document.createElement('textarea')
      area.value = details.url
      area.style.position = 'fixed'
      area.style.opacity = '0'
      document.body.appendChild(area)
      area.select()
      document.execCommand('copy')
      area.remove()
    }
    copied.value = true
    session.notify(t('E-invoice link copied'))
    window.setTimeout(() => { copied.value = false }, 1800)
  } catch (e) {
    session.notify(e.message, true)
  } finally {
    sharing.value = false
  }
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

async function print() {
  const again = isReprint.value
  if (again && !mayReprint.value) {
    session.notify(t('You are not allowed to reprint a receipt'), true)
    return
  }
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
  if (session.printerConfigured && !props.receipt.offline && !session.offline) {
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
    await printReceipt(document.getElementById('receipt-print'))
  } catch (e) {
    session.notify(e.message, true)
  } finally {
    printing.value = false
  }
}
</script>

<style scoped>
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
.share-note { margin-top: 9px; line-height: 1.4; }
@media (max-width: 460px) {
  .share-actions { grid-template-columns: 1fr; }
}
</style>
