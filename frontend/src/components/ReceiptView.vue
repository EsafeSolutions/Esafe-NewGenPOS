<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<template>
  <div
    :id="printable ? 'receipt-print' : null"
    class="receipt"
    :class="[`tpl-${tpl}`, `paper-${paperWidth}`]"
  >
    <template v-if="retail">
      <div class="retail-head">
        <img v-if="s.receipt_logo" :src="s.receipt_logo" class="receipt-logo" alt="" />
        <div class="receipt-company">{{ receipt.company }}</div>
        <div v-if="s.receipt_header" class="muted small receipt-extra">{{ s.receipt_header }}</div>
        <div v-if="s.receipt_show_address && s.receipt_address" class="muted small receipt-extra">
          {{ s.receipt_address }}
        </div>
        <div v-if="s.receipt_show_tax_id && s.receipt_tax_id" class="muted small">
          {{ t('Tax ID') }}: {{ s.receipt_tax_id }}
        </div>
        <div v-if="receipt.is_return" class="return-stamp">{{ t('REFUND') }}</div>
      </div>

      <div class="retail-meta">
        <div class="retail-meta-row">
          <span>{{ t('Invoice #') }}</span><strong>{{ receipt.name }}</strong>
        </div>
        <div class="retail-meta-row">
          <span>{{ t('Time') }}</span><span>{{ receipt.posting_date }} {{ String(receipt.posting_time || '').split('.')[0] }}</span>
        </div>
        <div v-if="receipt.customer_name" class="retail-meta-row">
          <span>{{ t('Customer') }}</span><span>{{ receipt.customer_name }}<template v-if="receipt.customer_phone"> · {{ receipt.customer_phone }}</template></span>
        </div>
        <div v-if="receipt.cashier || receipt.sales_person" class="retail-meta-row">
          <span>{{ t('Cashier') }}</span><span>{{ receipt.cashier || receipt.sales_person }}</span>
        </div>
        <div v-if="receipt.terminal" class="retail-meta-row">
          <span>{{ t('Terminal') }}</span><span>{{ receipt.terminal }}</span>
        </div>
        <div v-if="receipt.return_against" class="retail-meta-row">
          <span>{{ t('against') }}</span><span>{{ receipt.return_against }}</span>
        </div>
        <div v-if="receipt.app_type" class="retail-meta-row">
          <span>{{ t('Channel') }}</span><span>{{ receipt.app_type }}<template v-if="receipt.order_id"> · {{ t('Order') }} {{ receipt.order_id }}</template></span>
        </div>
      </div>

      <div v-if="headerCustomFields.length" class="retail-custom-fields">
        <template v-for="(f, i) in headerCustomFields" :key="'rhcf' + i">
          <img v-if="f.render === 'Image'" :src="asImg(f.value)" class="receipt-cf-img" alt="" />
          <div v-else class="retail-meta-row"><span v-if="f.label">{{ f.label }}</span><span>{{ f.value }}</span></div>
        </template>
      </div>

      <table class="retail-items">
        <thead>
          <tr>
            <th class="retail-no">#</th><th class="retail-item-heading"></th><th>{{ t('Qty') }}</th><th>{{ t('MRP') }}</th><th>{{ t('Discount') }}</th><th>{{ t('Amount') }}</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="(item, i) in receipt.items" :key="i">
            <tr class="retail-item-name">
              <td class="retail-no">{{ i + 1 }}</td><td colspan="5">{{ item.item_name }}</td>
            </tr>
            <tr class="retail-item-values">
              <td></td>
              <td class="retail-item-meta">
                <span v-if="s.receipt_show_item_code && item.item_code">{{ item.item_code }}</span>
                <span v-if="s.receipt_show_barcode && item.barcode"><template v-if="s.receipt_show_item_code && item.item_code"> · </template>{{ item.barcode }}</span>
                <span v-if="s.receipt_show_serial && item.serial_no"><template v-if="(s.receipt_show_item_code && item.item_code) || (s.receipt_show_barcode && item.barcode)"> · </template>{{ t('SN') }} {{ String(item.serial_no).split('\n').join(', ') }}</span>
              </td>
              <td>{{ qty(item.qty) }}</td><td>{{ m(originalRate(item)) }}</td><td>{{ m(lineSaving(item)) }}</td><td>{{ m(item.amount) }}</td>
            </tr>
          </template>
        </tbody>
      </table>

      <div class="receipt-totals retail-totals">
        <div class="row"><span>{{ t('Gross total') }}</span><span>{{ m(grossTotal) }}</span></div>
        <div v-if="totalSavings > 0 && !receipt.is_return" class="row discount"><span>{{ t('Discount') }}</span><span>-{{ m(totalSavings) }}</span></div>
        <div v-for="tax in receipt.taxes" :key="tax.description" class="row">
          <span>{{ tax.description }}</span><span>{{ m(tax.tax_amount) }}</span>
        </div>
        <div v-if="roundingAdjustment" class="row"><span>{{ t('Rounding') }}</span><span>{{ m(roundingAdjustment) }}</span></div>
        <div class="row total"><span>{{ t('Net total') }}</span><span>{{ m(payableTotal) }}</span></div>
        <template v-if="foreign">
          <div class="row muted small"><span>{{ t('In {currency}', { currency: receipt.company_currency }) }}</span><span>{{ money(receipt.base_grand_total, receipt.company_currency) }}</span></div>
          <div class="row muted small"><span>{{ t('Rate') }}</span><span>{{ rateLine(receipt.currency, receipt.conversion_rate, receipt.company_currency) }}</span></div>
        </template>
        <template v-if="s.receipt_show_payments">
          <div v-for="payment in paymentRows" :key="payment.mode_of_payment" class="row">
            <span>{{ modeLabel(payment.mode_of_payment) }}</span><span>{{ foreign && payment.currency ? money(payment.tendered, payment.currency) : m(payment.amount) }}</span>
          </div>
        </template>
        <div v-if="receipt.loyalty_amount" class="row"><span>{{ t('Loyalty points') }} ({{ receipt.loyalty_points_redeemed }})</span><span>{{ money(receipt.loyalty_amount) }}</span></div>
        <div v-if="receipt.change_amount" class="row"><span>{{ t('Change') }}</span><span>{{ foreign && receipt.change_currency !== receipt.currency ? money(receipt.base_change_amount, receipt.company_currency) : m(receipt.change_amount) }}</span></div>
        <template v-if="receipt.on_account && !receipt.is_return">
          <div class="row total owed"><span>{{ t('Owed on this sale') }}</span><span>{{ m(receipt.on_account.owed_on_sale) }}</span></div>
          <div v-if="receipt.on_account.owed_total != null" class="row muted small"><span>{{ t('Owed in all') }}</span><span>{{ money(receipt.on_account.owed_total, receipt.company_currency) }}</span></div>
        </template>
        <template v-else-if="receipt.on_account">
          <div class="row"><span>{{ t('Taken off what is owed') }}</span><span>{{ m(Math.abs(receipt.on_account.amount)) }}</span></div>
          <div v-if="receipt.on_account.owed_total != null" class="row muted small"><span>{{ t('Owed in all') }}</span><span>{{ money(receipt.on_account.owed_total, receipt.company_currency) }}</span></div>
        </template>
      </div>

      <div class="retail-counts">
        <span>{{ t('Total items') }}: <b>{{ itemCount }}</b></span><span>{{ t('Total qty') }}: <b>{{ qty(totalQty) }}</b></span>
      </div>
      <div v-if="totalSavings > 0 && !receipt.is_return" class="retail-savings">
        <span>{{ t('You saved') }}</span><strong>{{ m(totalSavings) }}</strong>
      </div>
      <div v-if="loyaltyVisible" class="retail-loyalty">
        <div class="retail-loyalty-title">{{ t('Loyalty points') }}<span v-if="receipt.loyalty?.program"> · {{ receipt.loyalty.program }}</span></div>
        <div v-if="receipt.loyalty_points_earned" class="row"><span>{{ t('Points earned:') }}</span><span>{{ receipt.loyalty_points_earned }}</span></div>
        <div v-if="receipt.loyalty_points_redeemed" class="row"><span>{{ t('Points redeemed') }}</span><span>{{ receipt.loyalty_points_redeemed }}</span></div>
        <div v-if="receipt.loyalty" class="row retail-loyalty-balance"><span>{{ t('Points balance') }}</span><strong>{{ receipt.loyalty.balance }}</strong></div>
      </div>

      <div v-if="receipt.applied_promotions?.length" class="receipt-promos">
        <div v-for="promo in receipt.applied_promotions" :key="promo.name" class="muted small">★ {{ promo.title }} ({{ t('saved') }} {{ m(promo.savings) }})</div>
      </div>
      <div v-if="s.receipt_show_note && receipt.note" class="receipt-note small"><strong>{{ t('Note') }}:</strong> {{ receipt.note }}</div>
      <div v-if="s.receipt_show_terms && s.receipt_terms" class="receipt-terms small">{{ s.receipt_terms }}</div>
      <div v-if="footerCustomFields.length" class="receipt-cf-foot">
        <template v-for="(f, i) in footerCustomFields" :key="'rfcf' + i">
          <img v-if="f.render === 'Image'" :src="asImg(f.value)" class="receipt-cf-img" alt="" />
          <div v-else class="muted small receipt-extra"><span v-if="f.label">{{ f.label }}: </span>{{ f.value }}</div>
        </template>
      </div>
      <div class="receipt-foot muted small"><div v-if="s.receipt_footer" class="receipt-extra">{{ s.receipt_footer }}</div>{{ t('Thank you!') }}</div>
    </template>

    <template v-else>
    <div class="receipt-head">
      <img v-if="s.receipt_logo" :src="s.receipt_logo" class="receipt-logo" alt="" />
      <div class="receipt-company">{{ receipt.company }}</div>
      <div v-if="s.receipt_header" class="muted small receipt-extra">{{ s.receipt_header }}</div>
      <div v-if="s.receipt_show_address && s.receipt_address" class="muted small receipt-extra">
        {{ s.receipt_address }}
      </div>
      <div v-if="s.receipt_show_tax_id && s.receipt_tax_id" class="muted small">
        {{ t('Tax ID') }}: {{ s.receipt_tax_id }}
      </div>
      <div v-if="receipt.is_return" class="return-stamp">{{ t('REFUND') }}</div>
      <div class="muted small">
        {{ receipt.name }} · {{ receipt.posting_date }} {{ String(receipt.posting_time || '').split('.')[0] }}
      </div>
      <div class="muted small" v-if="receipt.return_against">{{ t('against') }} {{ receipt.return_against }}</div>
      <div class="muted small">{{ receipt.customer_name }}</div>
      <div class="muted small" v-if="receipt.sales_person">{{ t('Served by') }} {{ receipt.sales_person }}</div>
      <div class="muted small" v-if="receipt.app_type">
        {{ receipt.app_type }}<span v-if="receipt.order_id"> · {{ t('Order') }} {{ receipt.order_id }}</span>
      </div>
      <template v-for="(f, i) in headerCustomFields" :key="'hcf' + i">
        <img v-if="f.render === 'Image'" :src="asImg(f.value)" class="receipt-cf-img" alt="" />
        <div v-else class="muted small receipt-extra">
          <span v-if="f.label">{{ f.label }}: </span>{{ f.value }}
        </div>
      </template>
    </div>

    <table class="receipt-table">
      <tbody>
        <tr v-for="(item, i) in receipt.items" :key="i">
          <td>
            <div class="ritem-name">{{ item.item_name }}</div>
            <div
              v-if="(s.receipt_show_item_code && item.item_code) || (s.receipt_show_barcode && item.barcode)"
              class="muted small ritem-meta"
            >
              <span v-if="s.receipt_show_item_code">{{ item.item_code }}</span>
              <span v-if="s.receipt_show_barcode && item.barcode"> · {{ item.barcode }}</span>
            </div>
            <div v-if="s.receipt_show_serial && item.serial_no" class="muted small ritem-meta">
              {{ t('SN') }}: {{ String(item.serial_no).split('\n').join(', ') }}
            </div>
            <div v-if="s.receipt_show_unit_price" class="muted small">
              {{ item.qty }} × {{ m(item.rate) }}
            </div>
            <div v-else class="muted small">{{ t('Qty') }} {{ item.qty }}</div>
          </td>
          <td class="right">{{ m(item.amount) }}</td>
        </tr>
      </tbody>
    </table>

    <div class="receipt-totals">
      <div v-if="receipt.discount_amount" class="row">
        <span>{{ t('Discount') }}</span><span>-{{ m(receipt.discount_amount) }}</span>
      </div>
      <div v-for="tax in receipt.taxes" :key="tax.description" class="row">
        <span>{{ tax.description }}</span><span>{{ m(tax.tax_amount) }}</span>
      </div>
      <div class="row total">
        <span>{{ t('Total') }}</span><span>{{ m(receipt.rounded_total || receipt.grand_total) }}</span>
      </div>
      <!-- A sale in another currency: its local value and the rate it was sold at. -->
      <template v-if="foreign">
        <div class="row muted small">
          <span>{{ t('In {currency}', { currency: receipt.company_currency }) }}</span>
          <span>{{ money(receipt.base_grand_total, receipt.company_currency) }}</span>
        </div>
        <div class="row muted small">
          <span>{{ t('Rate') }}</span>
          <span>{{ rateLine(receipt.currency, receipt.conversion_rate, receipt.company_currency) }}</span>
        </div>
      </template>
      <template v-if="s.receipt_show_payments">
        <div v-for="payment in paymentRows" :key="payment.mode_of_payment" class="row">
          <span>{{ modeLabel(payment.mode_of_payment) }}</span>
          <span>{{ foreign && payment.currency ? money(payment.tendered, payment.currency) : m(payment.amount) }}</span>
        </div>
      </template>
      <div v-if="receipt.loyalty_amount" class="row">
        <span>{{ t('Loyalty points') }} ({{ receipt.loyalty_points_redeemed }})</span>
        <span>{{ money(receipt.loyalty_amount) }}</span>
      </div>
      <div v-if="receipt.change_amount" class="row">
        <span>{{ t('Change') }}</span>
        <span>{{ foreign && receipt.change_currency !== receipt.currency ? money(receipt.base_change_amount, receipt.company_currency) : m(receipt.change_amount) }}</span>
      </div>
      <!-- A sale on account (0.60.0): what stays owed, on this sale and in
           all, whatever the receipt shows of the payments. -->
      <template v-if="receipt.on_account && !receipt.is_return">
        <div class="row total owed">
          <span>{{ t('Owed on this sale') }}</span><span>{{ m(receipt.on_account.owed_on_sale) }}</span>
        </div>
        <div v-if="receipt.on_account.owed_total != null" class="row muted small">
          <span>{{ t('Owed in all') }}</span><span>{{ money(receipt.on_account.owed_total, receipt.company_currency) }}</span>
        </div>
      </template>
      <template v-else-if="receipt.on_account">
        <div class="row">
          <span>{{ t('Taken off what is owed') }}</span><span>{{ m(Math.abs(receipt.on_account.amount)) }}</span>
        </div>
        <div v-if="receipt.on_account.owed_total != null" class="row muted small">
          <span>{{ t('Owed in all') }}</span><span>{{ money(receipt.on_account.owed_total, receipt.company_currency) }}</span>
        </div>
      </template>
    </div>
    <div v-if="receipt.on_account && !receipt.is_return" class="receipt-sign small">
      {{ t('Customer signature') }}
    </div>

    <div v-if="receipt.applied_promotions?.length" class="receipt-promos">
      <div v-for="promo in receipt.applied_promotions" :key="promo.name" class="muted small">
        ★ {{ promo.title }} ({{ t('saved') }} {{ m(promo.savings) }})
      </div>
    </div>
    <div v-if="receipt.loyalty_points_earned" class="receipt-promos muted small">
      {{ t('Points earned:') }} {{ receipt.loyalty_points_earned }}
    </div>

    <div v-if="s.receipt_show_note && receipt.note" class="receipt-note small">
      <strong>{{ t('Note') }}:</strong> {{ receipt.note }}
    </div>
    <div v-if="s.receipt_show_terms && s.receipt_terms" class="receipt-terms small">
      {{ s.receipt_terms }}
    </div>

    <div v-if="footerCustomFields.length" class="receipt-cf-foot">
      <template v-for="(f, i) in footerCustomFields" :key="'fcf' + i">
        <img v-if="f.render === 'Image'" :src="asImg(f.value)" class="receipt-cf-img" alt="" />
        <div v-else class="muted small receipt-extra">
          <span v-if="f.label">{{ f.label }}: </span>{{ f.value }}
        </div>
      </template>
    </div>

    <div class="receipt-foot muted small">
      <div v-if="s.receipt_footer" class="receipt-extra">{{ s.receipt_footer }}</div>
      {{ t('Thank you!') }}
    </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { t } from '../i18n'
import { money, rateLine } from '../format'
import { useSessionStore } from '../stores/session'

const props = defineProps({
  receipt: { type: Object, required: true },
  // Optional settings override (for the live Settings preview); defaults to the
  // session's saved settings.
  settings: { type: Object, default: null },
  // Only the real receipt gets id="receipt-print" so the print stylesheet
  // targets it (the Settings preview must never be the print target).
  printable: { type: Boolean, default: false },
})

const session = useSessionStore()
// The receipt of the outlet that made the sale (sent with it), over this
// till's own: a reprint of another outlet's sale shows that outlet's tax ID,
// address and logo.
const s = computed(
  () => props.settings || { ...(session.settings || {}), ...(props.receipt.receipt_settings || {}) }
)

// Amounts print in the sale's own currency (lumenpos.currency). A sale in
// another currency also shows its local value, the rate, each tender in its own
// money and the change in local money (it always comes out of the main drawer).
const m = (amount) => money(amount, props.receipt.currency)
const foreign = computed(
  () =>
    Boolean(props.receipt.company_currency) &&
    props.receipt.currency !== props.receipt.company_currency &&
    props.receipt.base_grand_total != null
)
const tpl = computed(() => (s.value.receipt_template || 'Retail').toLowerCase())
const retail = computed(() => tpl.value === 'retail')
const paperWidth = computed(() => (s.value.receipt_paper_width === '58mm' ? '58' : '80'))
const number = (value) => Number(value) || 0
const qty = (value) => {
  const amount = number(value)
  return Number.isInteger(amount) ? String(amount) : String(amount)
}
const originalRate = (item) =>
  item.price_list_rate != null ? number(item.price_list_rate) : number(item.rate)
const lineSaving = (item) =>
  item.line_discount_amount != null
    ? number(item.line_discount_amount)
    : originalRate(item) * number(item.qty) - number(item.amount)
const grossTotal = computed(() =>
  props.receipt.gross_total != null
    ? number(props.receipt.gross_total)
    : (props.receipt.items || []).reduce(
        (sum, item) => sum + originalRate(item) * number(item.qty),
        0
      )
)
const totalSavings = computed(() =>
  props.receipt.total_savings != null
    ? number(props.receipt.total_savings)
    : (props.receipt.items || []).reduce((sum, item) => sum + lineSaving(item), 0) + number(props.receipt.discount_amount)
)
const payableTotal = computed(() => props.receipt.rounded_total || props.receipt.grand_total || 0)
const roundingAdjustment = computed(() =>
  props.receipt.rounding_adjustment != null
    ? number(props.receipt.rounding_adjustment)
    : number(payableTotal.value) - number(props.receipt.grand_total)
)
const itemCount = computed(() => props.receipt.item_count ?? (props.receipt.items || []).length)
const totalQty = computed(() =>
  props.receipt.total_qty != null
    ? number(props.receipt.total_qty)
    : (props.receipt.items || []).reduce((sum, item) => sum + Math.abs(number(item.qty)), 0)
)
const loyaltyVisible = computed(() =>
  Boolean(props.receipt.loyalty) ||
  Boolean(props.receipt.loyalty_points_earned) ||
  Boolean(props.receipt.loyalty_points_redeemed)
)

// Dynamic custom fields resolved by the server (get_receipt), each is
// { label, value, render: 'Text'|'Image', position: 'Header'|'Footer' }.
const cf = computed(() => props.receipt.custom_fields || [])
const headerCustomFields = computed(() => cf.value.filter((f) => f.position === 'Header'))
const footerCustomFields = computed(() => cf.value.filter((f) => f.position !== 'Header'))
function asImg(value) {
  const v = String(value || '').trim()
  if (!v) return ''
  // Accept a data URL, an http(s) URL or a /files path as-is; treat anything
  // else as raw base64 PNG (e.g. a ZATCA QR stored as a base64 string).
  return /^(data:|https?:|\/)/i.test(v) ? v : `data:image/png;base64,${v}`
}

// EsafePOS's own tender for a sale on account reads in the till's language.
function modeLabel(mode) {
  return mode && mode === session.creditMode ? t('On account') : mode
}
// A return's part taken off the debt has its own row, in plain words, so its
// tender line is not printed twice.
const paymentRows = computed(() =>
  (props.receipt.payments || []).filter(
    (p) => !(props.receipt.is_return && props.receipt.on_account && p.mode_of_payment === session.creditMode)
  )
)
</script>

<style scoped>
.receipt {
  border: 1px dashed var(--border);
  border-radius: var(--radius);
  padding: 16px;
  font-size: 13px;
}
.row.owed { margin-top: 6px; }
.receipt-sign {
  margin-top: 26px;
  padding-top: 4px;
  border-top: 1px solid currentColor;
  width: 70%;
}
.receipt-head { text-align: center; margin-bottom: 12px; }
.receipt-logo {
  max-height: 64px;
  max-width: 70%;
  object-fit: contain;
  margin: 0 auto 8px;
  display: block;
}
.receipt-company { font-weight: 800; font-size: 15px; }
.receipt-extra { white-space: pre-line; margin: 3px 0; }
.return-stamp { color: var(--red); font-weight: 800; letter-spacing: 0.2em; }
.receipt-table { width: 100%; border-collapse: collapse; }
.receipt-table td {
  padding: 5px 0;
  border-bottom: 1px solid var(--border-subtle);
  vertical-align: top;
}
.ritem-name { font-weight: 600; }
.ritem-meta { font-family: var(--mono); }
.receipt-totals { margin-top: 10px; }
.row { display: flex; justify-content: space-between; padding: 2.5px 0; }
.row.total { font-weight: 800; font-size: 15px; padding: 6px 0; }
.receipt-promos {
  margin-top: 8px;
  border-top: 1px solid var(--border-subtle);
  padding-top: 8px;
}
.receipt-note {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--border-subtle);
  white-space: pre-line;
}
.receipt-terms {
  margin-top: 10px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-muted);
  white-space: pre-line;
}
.receipt-foot { text-align: center; margin-top: 12px; }
.receipt-cf-img { max-width: 60%; max-height: 150px; object-fit: contain; margin: 6px auto; display: block; }
.receipt-cf-foot {
  text-align: center;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--border-subtle);
}
.small { font-size: 11.5px; }

/* ---- Retail breakdown ---- */
.tpl-retail {
  border-style: solid;
  border-radius: 4px;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.retail-head { text-align: center; padding-bottom: 9px; border-bottom: 1px solid var(--border); }
.retail-head .receipt-logo { max-height: 58px; margin-bottom: 5px; }
.retail-head .receipt-company { font-size: 16px; letter-spacing: 0.01em; }
.retail-meta { padding: 8px 0; border-bottom: 1px solid var(--border); }
.retail-meta-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  padding: 1.5px 0;
  font-size: 10.5px;
}
.retail-meta-row > :first-child {
  color: var(--text-muted);
  font-weight: 700;
  letter-spacing: 0.035em;
  text-transform: uppercase;
  white-space: nowrap;
}
.retail-meta-row > :last-child { text-align: right; overflow-wrap: anywhere; }
.retail-custom-fields { border-bottom: 1px solid var(--border); padding: 5px 0; }
.retail-items { width: 100%; border-collapse: collapse; table-layout: fixed; margin-top: 7px; }
.retail-items th {
  border-bottom: 1px solid var(--text);
  color: var(--text-muted);
  font-size: 9.5px;
  letter-spacing: 0.035em;
  padding: 0 1px 4px;
  text-align: right;
}
.retail-items th:nth-child(1), .retail-items th:nth-child(2) { text-align: left; }
.retail-items th:nth-child(1) { width: 6%; }
.retail-items th:nth-child(2) { width: 31%; }
.retail-items th:nth-child(3) { width: 10%; }
.retail-items th:nth-child(4) { width: 17%; }
.retail-items th:nth-child(5) { width: 18%; }
.retail-items th:nth-child(6) { width: 18%; }
.retail-items td { padding: 1px; overflow-wrap: anywhere; }
.retail-item-name td { padding-top: 6px; font-weight: 700; line-height: 1.2; }
.retail-item-values td { border-bottom: 1px solid var(--border-subtle); color: var(--text-muted); font-size: 10.5px; text-align: right; padding-bottom: 5px; }
.retail-item-values .retail-item-meta { color: var(--text-muted); font-family: var(--mono); font-size: 9.5px; text-align: left; }
.retail-no { color: var(--text-muted); }
.retail-totals { border-top: 1px solid var(--text); padding-top: 5px; margin-top: 8px; }
.retail-totals .row { padding: 3px 0; }
.retail-totals .discount { font-weight: 700; }
.retail-totals .total { border-top: 1px solid var(--text); border-bottom: 2px solid var(--text); font-size: 16px; margin-top: 3px; padding: 6px 0; }
.retail-counts { display: flex; justify-content: space-between; padding: 8px 0 0; font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.03em; }
.retail-savings { align-items: center; border: 1px solid var(--text); display: flex; justify-content: space-between; margin-top: 10px; padding: 7px 9px; text-transform: uppercase; }
.retail-savings span { font-size: 10px; font-weight: 700; letter-spacing: 0.05em; }
.retail-savings strong { font-size: 19px; line-height: 1; }
.retail-loyalty { border-top: 1px solid var(--border); margin-top: 10px; padding-top: 8px; }
.retail-loyalty-title { font-size: 11px; font-weight: 800; letter-spacing: 0.06em; text-align: center; text-transform: uppercase; }
.retail-loyalty .row { padding: 2px 0; }
.retail-loyalty-balance { border-top: 1px solid var(--border-subtle); margin-top: 3px; padding-top: 5px !important; }

/* ---- Templates ---- */
.tpl-compact { font-size: 11.5px; padding: 12px; border: none; }
.tpl-compact .receipt-company { font-size: 13.5px; }
.tpl-compact .receipt-head { margin-bottom: 8px; }
.tpl-compact .receipt-table td { padding: 3px 0; }
.tpl-compact .row.total { font-size: 13.5px; }

.tpl-detailed { font-size: 13px; padding: 22px; }
.tpl-detailed .receipt-head {
  padding-bottom: 12px;
  margin-bottom: 14px;
  border-bottom: 2px solid var(--border);
}
.tpl-detailed .receipt-company { font-size: 18px; }
.tpl-detailed .receipt-table td { padding: 7px 0; }
.tpl-detailed .row { padding: 4px 0; }

@media print {
  #receipt-print.tpl-retail {
    border: 0;
    border-radius: 0;
    box-sizing: border-box;
    padding: 3mm 2.5mm;
    font-size: 10px;
  }
  #receipt-print.paper-58 { width: 58mm !important; padding: 2.5mm 2mm; font-size: 8.5px; }
  #receipt-print.paper-58 .retail-head .receipt-company { font-size: 13px; }
  #receipt-print.paper-58 .retail-meta-row { font-size: 8px; gap: 4px; }
  #receipt-print.paper-58 .retail-items th { font-size: 7px; }
  #receipt-print.paper-58 .retail-item-values td { font-size: 7.5px; }
  #receipt-print.paper-58 .retail-item-values .retail-item-meta { font-size: 7px; }
  #receipt-print.paper-58 .retail-totals .total { font-size: 13px; }
  #receipt-print.paper-58 .retail-savings strong { font-size: 15px; }
}
</style>
