<template>
  <section class="receipt-layout">
    <h4>{{ t('Receipt paper on this workstation') }}</h4>
    <p>{{ t('Use the same Windows queue and paper setting for browser and silent printing. Roll width, Windows page width and printable width can differ. The SDK lists supported forms, but does not identify the active Windows form or hardware printable area.') }}</p>
    <p>{{ t('Saved receipt queue') }}: <strong>{{ printer || t('Choose a receipt printer first') }}</strong></p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <fieldset :disabled="!canWrite || offline || needsMigration || !printer || busy">
      <div class="fields">
        <label class="field"><span>{{ t('Physical roll width') }}</span><select v-model.number="roll" :aria-label="t('Physical roll width')" @change="load"><option :value="58">58 mm</option><option :value="80">80 mm</option></select></label>
        <label class="field"><span>{{ t('Windows paper width (mm)') }}</span><input v-model.number="layout.paperWidth" :aria-label="t('Windows paper width (mm)')" type="number" min="10" :max="roll" step="0.1" /></label>
        <label class="field"><span>{{ t('Printable width (mm)') }}</span><input v-model.number="layout.printableWidth" :aria-label="t('Printable width (mm)')" type="number" min="10" :max="layout.paperWidth" step="0.1" /></label>
        <label class="field"><span>{{ t('Receipt inset (mm)') }}</span><input v-model.number="layout.inset" :aria-label="t('Receipt inset (mm)')" type="number" min="0" max="10" step="0.1" /></label>
      </div>
      <p>{{ t('Match the widths to Printing preferences and the driver’s printable area. Do not assume every 80 mm roll uses an 80 mm driver page. The inset is applied once; HTML receipts use portrait, zero driver margins, fit scaling and a measured page length.') }}</p>
      <p>{{ t('These measurements are saved separately for 58 mm and 80 mm rolls on the assigned queue. Raw ESC/POS text does not reproduce the designer’s borders; choose built-in HTML or an ERPNext PDF for a bordered receipt.') }}</p>
      <p>{{ t('Browser printing can feed to the end of a fixed Windows form after the footer. Check the driver’s receipt or continuous-paper mode and cut-after-document option where available. A content-sized browser page cannot force a driver to cut early.') }}</p>
      <button class="btn btn-outline" :disabled="busy" @click="save">{{ t('Save workstation receipt layout') }}</button>
    </fieldset>
  </section>
</template>
<script setup>
import { onMounted, ref, watch } from 'vue'
import { t } from '../../i18n'
import { call } from '../../api'
import { useSessionStore } from '../../stores/session'
import { printManager as manager } from '../../printing/index.js'
import { validateReceiptLayout } from '../../receiptLayout.js'
const props = defineProps({ profile: String, canWrite: Boolean, offline: Boolean, needsMigration: Boolean })
const session = useSessionStore()
const roll = ref(session.settings.receipt_paper_width === '58mm' ? 58 : 80)
const layout = ref(validateReceiptLayout({}, roll.value))
const printer = ref(''), busy = ref(false), error = ref(''), notice = ref('')
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
</style>
