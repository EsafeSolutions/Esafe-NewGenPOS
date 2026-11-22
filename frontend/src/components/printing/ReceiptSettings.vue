<!-- Copyright (c) 2026 Esafe (PVT) LTD; SPDX-License-Identifier: AGPL-3.0-only -->
<template><section class="receipt-settings">
  <p v-if="session.offline" class="notice">{{ t('Connect to change receipt settings.') }}</p>
  <p v-if="loading" class="loading" role="status">{{ t('Loading receipt settings…') }}</p>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <fieldset v-if="ready" :disabled="loading || saving || session.offline">

        <div class="sec-title"><Icon name="image" /> {{ t('Receipt') }}</div>
        <p class="sec-note">{{ t('What the receipt shows and how it prints, shared or per outlet.') }}</p>
        <p class="muted hint-row" style="padding: 0 0 10px">
          {{ t('Design the receipt shown on screen and printed from the browser.') }}
        </p>
        <div v-if="activeFormat" class="pf-banner">
          <Icon name="report" />
          <div>
            <b>{{ t('Your own format is active:') }} {{ activeFormat }}</b>
            <div class="pf-sub">{{ t('This outlet uses an ERPNext Print Format. The design below controls the on-screen receipt. Select Built-in receipt under Printing → Printers to use this design for browser printing.') }}</div>
          </div>
        </div>
        <p v-else class="muted hint-row" style="padding: 0 0 12px">
          {{ t('Use Printing → Printers to choose an ERPNext Print Format, or keep the built-in receipt designed here.') }}
        </p>
        <div class="rc-scope">
          <span class="rc-scope-label">{{ t('Editing receipt for') }}</span>
          <select :disabled="loading || saving" :aria-label="t('Receipt outlet')" class="rc-scope-select" v-model="receiptScope" @change="onReceiptScopeChange">
            <option value="">{{ t('All outlets (default)') }}</option>
            <option v-for="p in posProfiles" :key="p" :value="p">
              {{ p }}{{ profileReceiptOverrides.includes(p) ? '  •' : '' }}
            </option>
          </select>
          <template v-if="receiptScope">
            <button class="btn btn-primary" :disabled="loading || saving || session.offline" @click="saveProfileReceipt">{{ t('Save for this outlet') }}</button>
            <button v-if="receiptHasOverride" class="btn btn-outline" @click="resetProfileReceipt">{{ t('Reset to default') }}</button>
            <span class="rc-scope-hint muted small">{{ receiptHasOverride ? t('This outlet has its own receipt.') : t('Customising from the default. Save to apply.') }}</span>
          </template>
          <span v-else class="rc-scope-hint muted small">{{ t('Save the default below, or pick an outlet to give it a different receipt.') }}</span>
        </div>
        <div class="receipt-config">
          <div class="rc-controls">
            <div class="seg-field">
              <span class="seg-label">{{ t('Template') }}</span>
              <div class="segmented">
                <button
                  v-for="tpl in RECEIPT_TEMPLATES"
                  :key="tpl"
                  class="seg-btn"
                  :class="{ on: receiptForm.receipt_template === tpl }"
                  @click="receiptForm.receipt_template = tpl"
                >
                  {{ t(tpl) }}
                </button>
              </div>
            </div>

            <label class="field" style="margin-top: 14px; max-width: 220px">
              <span>{{ t('Thermal paper width') }}</span>
              <select v-model="receiptForm.receipt_paper_width">
                <option value="80mm">80 mm</option>
                <option value="58mm">58 mm</option>
              </select>
              <span class="setting-desc">{{ t('Applies to browser and network-printer receipts. For browser printing, set the Windows printer paper type to Receipt or Continuous and margins to None; a fixed-length driver sheet cannot auto-cut to the receipt.') }}</span>
            </label>

            <div class="field-grid" style="margin-top: 14px">
              <label class="field span-2">
                <span>{{ t('Logo URL or path') }}</span>
                <input v-model="receiptForm.receipt_logo" :placeholder="t('/files/logo.png or https://…')" />
              </label>
              <label class="field span-2">
                <span>{{ t('Header line (under the company name)') }}</span>
                <input v-model="receiptForm.receipt_header" :placeholder="t('e.g. Main Branch · 0500000000')" />
              </label>
              <label class="field span-2">
                <span>{{ t('Shop contact number (above address)') }}</span>
                <input v-model="receiptForm.receipt_shop_phone" :placeholder="t('e.g. +94 11 234 5678')" />
              </label>
              <label class="field span-2">
                <span>{{ t('Custom footer line') }}</span>
                <input v-model="receiptForm.receipt_footer" :placeholder="t('e.g. Thank you for shopping with us')" />
              </label>
            </div>

            <div class="sub-label" style="margin-top: 14px">{{ t('Show on the receipt') }}</div>
            <div class="rc-toggles">
              <label class="inline-check"><input type="checkbox" v-model="receiptForm.receipt_show_item_code" :true-value="1" :false-value="0" /> {{ t('Item code') }}</label>
              <label class="inline-check"><input type="checkbox" v-model="receiptForm.receipt_show_barcode" :true-value="1" :false-value="0" /> {{ t('Barcode') }}</label>
              <label class="inline-check"><input type="checkbox" v-model="receiptForm.receipt_show_serial" :true-value="1" :false-value="0" /> {{ t('Serial numbers') }}</label>
              <label class="inline-check"><input type="checkbox" v-model="receiptForm.receipt_show_unit_price" :true-value="1" :false-value="0" /> {{ t('Unit price (qty × rate)') }}</label>
              <label class="inline-check"><input type="checkbox" v-model="receiptForm.receipt_show_payments" :true-value="1" :false-value="0" /> {{ t('Payment methods') }}</label>
              <label class="inline-check"><input type="checkbox" v-model="receiptForm.receipt_show_note" :true-value="1" :false-value="0" /> {{ t('Sale note') }}</label>
              <label class="inline-check"><input type="checkbox" v-model="receiptForm.receipt_show_cashier" :true-value="1" :false-value="0" /> {{ t('Cashier name') }}</label>
              <label class="inline-check"><input type="checkbox" v-model="receiptForm.receipt_show_terminal" :true-value="1" :false-value="0" /> {{ t('Terminal or user') }}</label>
              <label class="inline-check"><input type="checkbox" v-model="receiptForm.receipt_show_invoice_barcode" :true-value="1" :false-value="0" /> {{ t('Invoice barcode') }}</label>
            </div>

            <div class="rc-textfields">
              <label class="inline-check"><input type="checkbox" v-model="receiptForm.receipt_show_tax_id" :true-value="1" :false-value="0" /> {{ t('Tax / VAT ID') }}</label>
              <input v-if="receiptForm.receipt_show_tax_id" v-model="receiptForm.receipt_tax_id" :placeholder="t('e.g. 3001234567')" />
              <label class="inline-check"><input type="checkbox" v-model="receiptForm.receipt_show_address" :true-value="1" :false-value="0" /> {{ t('Store address') }}</label>
              <textarea v-if="receiptForm.receipt_show_address" v-model="receiptForm.receipt_address" rows="2" :placeholder="t('Street, city…')"></textarea>
              <label class="inline-check"><input type="checkbox" v-model="receiptForm.receipt_show_terms" :true-value="1" :false-value="0" /> {{ t('Terms & conditions') }}</label>
              <textarea v-if="receiptForm.receipt_show_terms" v-model="receiptForm.receipt_terms" rows="2" :placeholder="t('Return within 14 days with the receipt…')"></textarea>
            </div>
          </div>

          <div class="rc-preview">
            <div class="rc-preview-label muted small">{{ t('Live preview') }}</div>
            <ReceiptView ref="preview" :receipt="previewReceipt" :settings="receiptForm" />
          </div>
        </div>

        <!-- Dynamic custom fields, pull any field from the POS Profile or the
             sale invoice onto the receipt (text or an image such as a ZATCA QR). -->
        <div class="cf-section">
          <div class="sub-label">{{ t('Custom fields') }}</div>
          <p class="muted small" style="margin: 0 0 10px">
            {{ receiptScope
              ? t('Extra fields for this outlet, shown in addition to the global custom fields.')
              : t('Add any field from the POS Profile or the sale invoice, e.g. a ZATCA QR image, a CR number, or a country-specific field. These apply to every outlet, pick an outlet above to add extras just for it.') }}
          </p>
          <div v-for="(row, i) in customFields" :key="i" class="cf-row">
            <select class="cf-in" v-model="row.source" @change="onCfSource(row)">
              <option value="Sale Invoice">{{ t('Sale invoice') }}</option>
              <option value="POS Profile">{{ t('POS Profile') }}</option>
            </select>
            <select class="cf-in cf-field" v-model="row.fieldname">
              <option value="">{{ t('Choose a field…') }}</option>
              <option
                v-for="o in (fieldOptions[row.source] || [])"
                :key="o.fieldname"
                :value="o.fieldname"
              >{{ o.label }} · {{ o.fieldname }}</option>
            </select>
            <input class="cf-in" v-model="row.label" :placeholder="t('Label (optional)')" />
            <select class="cf-in" v-model="row.render">
              <option value="Text">{{ t('Text') }}</option>
              <option value="Image">{{ t('Image / QR') }}</option>
            </select>
            <select class="cf-in" v-model="row.position">
              <option value="Header">{{ t('Header') }}</option>
              <option value="Footer">{{ t('Footer') }}</option>
            </select>
            <button class="btn-ghost" :title="t('Remove')" @click="customFields.splice(i, 1)">
              <Icon name="close" />
            </button>
          </div>
          <button class="btn btn-outline add-row" @click="addCustomField">
            <Icon name="plus" /> {{ t('Add a field') }}
          </button>
        </div>

  </fieldset>
  <footer v-if="ready" class="actions">
    <button v-if="!receiptScope" class="btn btn-primary" :disabled="loading || saving || session.offline" @click="saveDefaults">{{ saving ? t('Saving…') : t('Save default receipt') }}</button>
    <button class="btn btn-outline" :disabled="loading || saving || session.offline" @click="printPreview">{{ t('Print preview') }}</button>
  </footer>
</section></template>
<script setup>
import { computed, onActivated, onMounted, ref } from 'vue'
import { call } from '../../api'
import { t } from '../../i18n'
import { useSessionStore } from '../../stores/session'
import { printReceipt } from '../../receiptPrint'
import Icon from '../Icon.vue'
import ReceiptView from '../ReceiptView.vue'

const session = useSessionStore()
const loading = ref(false), saving = ref(false), ready = ref(false), error = ref(''), preview = ref(null)
const defaultForm = ref({ receipt_custom_fields: [] }), posProfiles = ref([]), formats = ref({})
const profileReceiptOverrides = ref([]), receiptScope = ref(''), profileReceiptForm = ref({}), receiptHasOverride = ref(false)
const fieldOptions = ref({}), profileReceiptCustomFields = ref([])
const RECEIPT_TEMPLATES = ['Retail', 'Compact', 'Standard', 'Detailed', 'Table']
const receiptForm = computed(() => receiptScope.value ? profileReceiptForm.value : defaultForm.value)
const customFields = computed(() => receiptScope.value ? profileReceiptCustomFields.value : defaultForm.value.receipt_custom_fields)
const activeFormat = computed(() => (receiptScope.value || session.posProfile)===session.posProfile ? session.printFormat || '' : formats.value[receiptScope.value] || '')

async function load() {
  if (session.offline) return
  loading.value = true; error.value = ''
  try {
    const data = await call('esafepos.api.printing_settings.receipt_workspace')
    defaultForm.value = { ...data.config, receipt_custom_fields: data.custom_fields || [] }
    posProfiles.value = data.profiles || []; formats.value = data.print_formats || {}
    profileReceiptOverrides.value = data.overrides || []; ready.value = true
    await Promise.all([loadFieldOptions('Sale Invoice'), loadFieldOptions('POS Profile')])
  } catch (e) { error.value = e.message } finally { loading.value = false }
}
let scopeRequest = 0
async function onReceiptScopeChange() {
  const request = ++scopeRequest, scope = receiptScope.value
  if (!scope) return
  loading.value = true; error.value = ''
  try {
    const data = await call('esafepos.api.settings.get_profile_receipt', { pos_profile: scope })
    if (request !== scopeRequest) return
    profileReceiptForm.value = data.config || {}; profileReceiptCustomFields.value = data.custom_fields || []
    receiptHasOverride.value = !!data.has_override
  } catch (e) { if (request === scopeRequest) { error.value = e.message; receiptScope.value = '' } }
  finally { if (request === scopeRequest) loading.value = false }
}
async function syncReceipt() {
  const data = session.posProfile
    ? await call('esafepos.api.settings.get_profile_receipt', { pos_profile: session.posProfile })
    : { config: defaultForm.value }
  Object.assign(session.settings, data.config)
}
async function saveDefaults() {
  await save(async () => {
    await call('esafepos.api.printing_settings.save_receipt_defaults', { config: defaultForm.value, custom_fields: defaultForm.value.receipt_custom_fields })
    await syncReceipt(); session.notify(t('Default receipt saved.'))
  })
}
async function saveProfileReceipt() {
  const profile = receiptScope.value
  if (!profile) return
  await save(async () => {
    await call('esafepos.api.settings.save_profile_receipt', { pos_profile: profile, config: profileReceiptForm.value, custom_fields: profileReceiptCustomFields.value })
    if (!profileReceiptOverrides.value.includes(profile)) profileReceiptOverrides.value.push(profile)
    receiptHasOverride.value = true; await syncReceipt()
    session.notify(t('Receipt saved for {outlet}', { outlet: profile }))
  })
}
async function resetProfileReceipt() {
  const profile = receiptScope.value
  await save(async () => {
    await call('esafepos.api.settings.clear_profile_receipt', { pos_profile: profile })
    profileReceiptOverrides.value = profileReceiptOverrides.value.filter((p) => p !== profile)
    await onReceiptScopeChange(); await syncReceipt()
    session.notify(t('{outlet} now uses the default receipt', { outlet: profile }))
  })
}
async function save(action) {
  if (saving.value || session.offline || loading.value) return
  saving.value = true; error.value = ''
  try { await action() } catch (e) { error.value = e.message } finally { saving.value = false }
}
async function printPreview() {
  await save(() => printReceipt(preview.value.$el))
}
onMounted(load)
onActivated(async () => {
  if (!ready.value || session.offline) return
  try { const data = await call('esafepos.api.printing_settings.receipt_workspace'); formats.value = data.print_formats || {} } catch { /* Preserve the current draft if status refresh is unavailable. */ }
})
const sampleReceipt = {
  name: 'INV-2026-00042',
  company: session.company || 'Your Store',
  currency: 'LKR',
  customer_name: 'Walk-in Customer',
  customer_phone: '077 123 4567',
  cashier: 'Cashier',
  terminal: 'Till 02',
  sales_person: 'Cashier',
  posting_date: '2026-06-30',
  posting_time: '14:32:00',
  note: 'Gift wrap requested',
  is_return: false,
  items: [
    { item_code: 'BACKPACK', item_name: 'Backpack', barcode: '6291041500213', serial_no: null, qty: 1, price_list_rate: 500, rate: 450, amount: 450, gross_amount: 500, line_discount_amount: 50 },
    { item_code: 'CAMERA-DSLR', item_name: 'DSLR Camera', barcode: '6291041500220', serial_no: 'SN-00123', qty: 1, price_list_rate: 900, rate: 810, amount: 810, gross_amount: 900, line_discount_amount: 90 },
  ],
  discount_amount: 0,
  gross_total: 1400,
  item_discount_total: 140,
  total_savings: 140,
  rounding_adjustment: 0,
  item_count: 2,
  total_qty: 2,
  taxes: [],
  grand_total: 1260,
  rounded_total: 1260,
  payments: [{ mode_of_payment: 'Cash', amount: 1260 }],
  loyalty_amount: 0,
  change_amount: 0,
  applied_promotions: [],
  loyalty_points_earned: 14,
  loyalty: { program: 'Rewards', balance: 184, conversion_factor: 0.1 },
}

async function loadFieldOptions(source) {
  if (!source || fieldOptions.value[source]) return
  try {
    const opts = await call('esafepos.api.settings.receipt_field_options', { source })
    fieldOptions.value = { ...fieldOptions.value, [source]: opts }
  } catch {
    /* ignore, the picker just stays empty */
  }
}

function addCustomField() {
  customFields.value.push({
    source: 'Sale Invoice',
    fieldname: '',
    label: '',
    render: 'Text',
    position: 'Footer',
  })
  loadFieldOptions('Sale Invoice')
}

function onCfSource(row) {
  row.fieldname = ''
  loadFieldOptions(row.source)
}

function cfLabel(row) {
  if (row.label) return row.label
  const o = (fieldOptions.value[row.source] || []).find((x) => x.fieldname === row.fieldname)
  return (o && o.label) || row.fieldname
}

// A tiny placeholder image so the preview shows where an Image/QR field lands.
const SAMPLE_CF_IMG =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="88" height="88"><rect width="88" height="88" fill="#111"/><rect x="12" y="12" width="64" height="64" fill="#fff"/><rect x="24" y="24" width="40" height="40" fill="#111"/><rect x="36" y="36" width="16" height="16" fill="#fff"/></svg>'
  )

const previewReceipt = computed(() => ({
  ...sampleReceipt,
  custom_fields: customFields.value
    .filter((r) => r.fieldname)
    .map((r) => ({
      label: cfLabel(r),
      value: r.render === 'Image' ? SAMPLE_CF_IMG : t('Sample value'),
      render: r.render,
      position: r.position,
    })),
}))

</script>
<style scoped>
.receipt-settings{padding:22px;max-width:1400px;margin:0 auto;width:100%;box-sizing:border-box}
fieldset{border:0;padding:0;margin:0;min-width:0}.sec-title{font-size:18px;font-weight:650;display:flex;align-items:center;gap:8px}.sec-title svg{width:18px;height:18px}.sec-note,.hint-row,.setting-desc{font-size:12px;color:var(--text-muted);line-height:1.65}.sec-note{margin:7px 0 18px}.rc-scope{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:14px 0;margin:5px 0 24px;border-bottom:1px solid var(--border)}.rc-scope-label{font-size:13px;font-weight:600}.rc-scope-hint{font-size:12px;color:var(--text-muted)}.rc-scope select{min-width:200px}.receipt-config{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:36px;align-items:start}.rc-controls{min-width:0}.rc-preview{position:sticky;top:16px;min-width:0}.rc-preview-label{font-size:12px;margin-bottom:10px;color:var(--text-muted)}.field{display:flex;flex-direction:column;gap:6px;min-width:0}.field>span,.seg-label,.sub-label{font-size:12px;color:var(--text-muted)}.field-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.span-2{grid-column:1/-1}.seg-label{display:block;margin-bottom:9px}.segmented{display:flex;gap:4px;flex-wrap:wrap}.seg-btn{padding:8px 13px;border:1px solid var(--border);border-radius:var(--radius)}.seg-btn.on{background:var(--brand);border-color:var(--brand);color:white}.rc-toggles{display:grid;grid-template-columns:1fr 1fr;gap:11px 16px;margin:12px 0}.inline-check{display:flex;align-items:center;gap:8px;font-size:12px;justify-content:flex-start}.inline-check input{width:15px;min-height:0;flex:none}.rc-textfields{display:flex;flex-direction:column;gap:12px;margin-top:20px}.rc-textfields input:not([type=checkbox]),textarea{width:100%;box-sizing:border-box}.cf-section{padding-top:22px;margin-top:26px;border-top:1px solid var(--border)}.sub-label{font-weight:600;margin-bottom:10px}.cf-row{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}.cf-row>*{min-width:0;flex:1 1 120px}.cf-row button{flex:0 0 35px}.cf-field{flex-grow:2}.pf-banner{display:flex;align-items:start;gap:12px;background:var(--surface-2);border:1px solid var(--border);border-radius:var(--radius);padding:14px;margin-bottom:20px;font-size:13px}.pf-banner svg{width:20px;flex:none}.pf-sub{font-size:12px;line-height:1.65;margin-top:5px}.actions{display:flex;align-items:center;gap:10px;padding-top:22px;margin-top:20px;border-top:1px solid var(--border)}.error{color:var(--red);font-size:13px}.notice{color:var(--text-muted);font-size:13px}input,select,textarea{font:inherit;font-size:13px;color:var(--text);background:var(--input-bg);border:1px solid var(--border);border-radius:var(--radius);padding:9px 10px}button:disabled{opacity:.5}.cf-row svg{width:16px}.loading{font-size:13px;color:var(--text-muted)}
@media(max-width:1000px){.receipt-config{grid-template-columns:1fr}.rc-preview{position:static;max-width:100%;width:320px;margin:10px auto}.receipt-settings{padding:18px}}
@media(max-width:520px){.receipt-settings{padding:14px}.rc-toggles{grid-template-columns:1fr}.rc-scope{align-items:stretch}.rc-scope select{width:100%;min-width:0}.field-grid{grid-template-columns:1fr}.actions{flex-wrap:wrap}.rc-preview{width:100%}.seg-btn{padding:7px 10px}}
</style>
