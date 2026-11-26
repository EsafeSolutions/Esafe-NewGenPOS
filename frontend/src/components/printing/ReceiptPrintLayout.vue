<template>
  <section class="receipt-layout">
    <h4>{{ t('Receipt paper and margins') }}</h4>
    <p>{{ t('Use the same Windows queue and paper setting for browser and silent printing. Roll width, Windows page width and printable width can differ. The SDK lists supported forms, but does not identify the active Windows form or hardware printable area.') }}</p>
    <p>{{ t('Saved receipt queue') }}: <strong>{{ printer || t('Choose a receipt printer first') }}</strong></p>
    <p>{{ t('New receipt setups start at 72 mm for an 80 mm roll and 48 mm for a 58 mm roll. These are starting widths; match the actual Windows form before printing. Wider calibrated layouts remain available.') }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <fieldset :disabled="!canWrite || offline || needsMigration || !printer || busy">
      <div class="fields">
        <label class="field"><span>{{ t('Physical roll width') }}</span><select v-model.number="roll" :aria-label="t('Physical roll width')" @change="load"><option :value="58">58 mm</option><option :value="80">80 mm</option></select></label>
        <label class="field"><span>{{ t('Windows paper width (mm)') }}</span><input v-model.number="layout.paperWidth" :aria-label="t('Windows paper width (mm)')" type="number" min="10" :max="roll" step="0.1" /></label>
        <label class="field"><span>{{ t('Printable width (mm)') }}</span><input v-model.number="layout.printableWidth" :aria-label="t('Printable width (mm)')" type="number" min="10" :max="layout.paperWidth" step="0.1" /></label>
      </div>
      <h5>{{ t('Receipt margins (mm)') }}</h5>
      <div class="fields margin-fields">
        <label v-for="side in sides" :key="side.key" class="field"><span>{{ t(side.label) }}</span><input v-model.number="layout.margins[side.key]" :aria-label="t(side.label)" type="number" min="0" max="20" step="0.1" /></label>
      </div>
      <p v-if="contentWidth !== null" class="width-summary">{{ t('Receipt content width') }}: <strong>{{ contentWidth }} mm</strong></p>
      <p>{{ t('If amounts are cut off on the right, first match the Windows paper and printable widths, then increase the right margin. Left and right margins reduce the content width. Top and bottom margins add space before and after the receipt; page length follows the content.') }}</p>
      <p>{{ t('Margins apply once to browser and built-in HTML receipts. Use zero margins in the browser print dialog. ERPNext PDF uses its own Print Format, and raw ESC/POS uses its own command layout. Settings are separate for each assigned receipt queue, outlet, workstation and 58/80 mm roll.') }}</p>
      <div class="layout-actions">
        <button class="btn btn-outline" @click="useSafeLayout">{{ t('Use safe thermal layout') }}</button>
        <button class="btn btn-outline" @click="resetMargins">{{ t('Reset margins to 3 mm') }}</button>
        <button class="btn btn-outline" @click="previewMargins">{{ t('Preview receipt margins') }}</button>
        <button class="btn btn-outline" @click="browserTest">{{ t('Browser margin test') }}</button>
        <button class="btn btn-primary" @click="save">{{ t('Save workstation receipt layout') }}</button>
      </div>
      <p>{{ t('Preview and the browser test use the current entries before saving, with synthetic amounts. They do not create a sale or open the drawer. Check both edges on paper before saving for normal receipts.') }}</p>
      <div v-if="preview" class="margin-preview"><iframe :srcdoc="preview.html" sandbox="" :style="{ width: preview.width + 'mm', height: preview.height + 'mm' }" :title="t('Receipt margin preview')"></iframe></div>
      <p>{{ t('Browser printing can feed to the end of a fixed Windows form after the footer. Check the driver’s receipt or continuous-paper mode and cut-after-document option where available. A content-sized browser page cannot force a driver to cut early.') }}</p>
    </fieldset>
    <div ref="testSource" class="margin-test-source" aria-hidden="true"><ReceiptView :receipt="calibration" :settings="calibration.receipt_settings" :printable="false" /></div>
  </section>
</template>
<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { t } from '../../i18n'
import { call } from '../../api'
import { useSessionStore } from '../../stores/session'
import { printManager as manager } from '../../printing/index.js'
import { validateReceiptLayout } from '../../receiptLayout.js'
import { selfContainedHtml } from '../../printing/documents.js'
import { printReceipt } from '../../receiptPrint.js'
import ReceiptView from '../ReceiptView.vue'
const props = defineProps({ profile: String, canWrite: Boolean, offline: Boolean, needsMigration: Boolean })
const session = useSessionStore()
const roll = ref(session.settings.receipt_paper_width === '58mm' ? 58 : 80)
const layout = ref(validateReceiptLayout({}, roll.value))
const printer = ref(''), busy = ref(false), error = ref(''), notice = ref('')
const preview = ref(null), testSource = ref(null)
const sides = [{ key: 'left', label: 'Left margin (mm)' }, { key: 'right', label: 'Right margin (mm)' }, { key: 'top', label: 'Top margin (mm)' }, { key: 'bottom', label: 'Bottom margin (mm)' }]
const contentWidth = computed(() => {
  try { const value = validateReceiptLayout(layout.value, roll.value); return Number((value.printableWidth - value.margins.left - value.margins.right).toFixed(2)) }
  catch { return null }
})
const calibration = computed(() => ({
  name: 'RCPT-MARGIN-TEST', company: 'Receipt margin test', currency: 'LKR',
  customer_name: 'Synthetic test only', grand_total: 12345.67, rounded_total: 12345.67,
  items: [{ item_name: 'Check both edges and the full amount', qty: 1, rate: 12345.67, amount: 12345.67 }],
  payments: [{ mode_of_payment: 'Cash', amount: 12345.67 }],
  receipt_settings: { receipt_template: 'Table', receipt_paper_width: roll.value + 'mm', receipt_show_invoice_barcode: 0, receipt_show_cashier: 0, receipt_show_terminal: 0, receipt_footer: 'Margin test only — no sale' },
}))
function resetMargins() { layout.value.margins = { top: 3, right: 3, bottom: 3, left: 3 } }
function useSafeLayout() { layout.value = validateReceiptLayout({}, roll.value); notice.value = t('Safe starting layout loaded. Preview and test both edges, then save for this printer.') }
async function prepareTest(browser = false) {
  if (busy.value) return
  error.value = ''; busy.value = true
  try {
    const geometry = validateReceiptLayout(layout.value, roll.value)
    await nextTick()
    const source = testSource.value.querySelector('.receipt')
    if (browser) await printReceipt(source, geometry)
    else preview.value = await selfContainedHtml(source, { receipt: true, layout: geometry })
  } catch (e) { error.value = e.message }
  finally { busy.value = false }
}
function previewMargins() { return prepareTest() }
function browserTest() { return prepareTest(true) }
watch([layout, roll], () => { preview.value = null }, { deep: true })
let generation = 0
async function load() {
  const seq = ++generation
  try {
    const binding = await manager.binding(props.profile)
    if (seq !== generation) return
    printer.value = binding.receipt || ''
    layout.value = validateReceiptLayout(binding.receiptLayout?.[roll.value], roll.value)
  } catch (e) {
    if (seq === generation) error.value = e.message
  }
}
async function save() {
  if (busy.value) return
  error.value = ''; notice.value = ''; busy.value = true
  try {
    await manager.saveReceiptLayout(props.profile, roll.value, layout.value, () => call(
      'esafepos.api.printing_settings.authorize_workstation_setup', { pos_profile: props.profile }
    ))
    notice.value = t('Receipt layout saved for this workstation and roll width.')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
watch(() => [props.profile, manager.state.bindingRevision], load)
onMounted(load)
</script>
<style scoped>
.receipt-layout{border-top:1px solid var(--border);padding:20px 0}h4{font-size:14px;margin:0}p{font-size:12px;line-height:1.7;color:var(--text-muted)}fieldset{border:0;padding:0;min-width:0}.fields{display:flex;flex-wrap:wrap;gap:12px}.field{display:flex;flex-direction:column;gap:6px;flex:1;min-width:130px;font-size:12px;margin:12px 0}input,select{width:100%;box-sizing:border-box;padding:9px;border:1px solid var(--border);border-radius:var(--radius);background:var(--input-bg);color:var(--text);font:inherit}.error{color:var(--red)}@media(max-width:520px){.fields{flex-direction:column;gap:0}.btn{width:100%}}
h5{font-size:13px;margin:16px 0 0}.layout-actions{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}.width-summary strong{color:var(--text)}.margin-preview{padding:12px;background:var(--input-bg);border:1px solid var(--border);overflow:auto}.margin-preview iframe{display:block;max-width:100%;max-height:420px;border:0;background:#fff}.margin-test-source{position:fixed;left:-10000px;top:0;width:80mm;pointer-events:none}
</style>
