<template>
  <section class="drawer-setup">
    <h3>{{ t('Cash drawer') }}</h3>
    <p>{{ t('Test / open sends a physical pulse to the saved receipt printer’s drawer port. It prints no receipt and feeds no paper.') }}</p>
    <p>{{ t('Printer') }}: <strong>{{ printerName || t('Save a receipt printer first') }}</strong></p>
    <p class="hint">{{ t('These settings belong to this site, outlet and workstation. Native manager settings are separate. Turn off Windows driver drawer automation to avoid two openings.') }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <p v-if="!ready" class="hint">{{ t('Connect, approve and save the exact receipt printer. Drawer setup also needs outlet write permission, the site migration and an online connection.') }}</p>
    <fieldset :disabled="!ready || busy">
      <label class="check"><input v-model="config.enabled" type="checkbox" />{{ t('Enable cash drawer') }}</label>
      <div class="fields">
        <label class="field"><span>{{ t('Drawer connector') }}</span><select v-model.number="config.pin" :aria-label="t('Drawer connector')"><option :value="0">{{ t('Pin 2 / drawer 1') }}</option><option :value="1">{{ t('Pin 5 / drawer 2') }}</option></select></label>
        <label class="field"><span>{{ t('Pulse ON milliseconds') }}</span><input v-model.number="config.onMs" :aria-label="t('Pulse ON milliseconds')" type="number" min="2" max="510" step="2" /></label>
        <label class="field"><span>{{ t('Pulse OFF milliseconds') }}</span><input v-model.number="config.offMs" :aria-label="t('Pulse OFF milliseconds')" type="number" min="2" max="510" step="2" /></label>
      </div>
      <p class="hint">{{ t('Use even whole milliseconds from 2 to 510. Defaults: ON 100, OFF 500.') }}</p>
      <label class="check"><input v-model="config.automatic" type="checkbox" :disabled="!config.enabled" />{{ t('Open after a successful cash payment') }}</label>
      <p class="hint">{{ t('Opens once for a new paid cash sale, including paid cash/card splits. Card-only, on-account, returned and offline sales do not open it. When printing a receipt, the pulse waits for submitted/completed status. It never follows a receipt reprint.') }}</p>
      <div class="actions"><button class="btn btn-primary" :disabled="busy || !ready" @click="save">{{ t('Save cash drawer settings') }}</button><button class="btn btn-outline" :disabled="busy || !ready || !config.enabled || dirty || !matched" @click="test">{{ t('Test / open cash drawer') }}</button></div>
    </fieldset>
    <p class="hint">{{ t('A job acceptance or spooler status does not prove the physical drawer opened. Unknown outcomes are never replayed automatically.') }}</p>
  </section>
</template>
<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { call } from '../../api'
import { t } from '../../i18n'
import { useSessionStore } from '../../stores/session'
import { printManager as manager, cashDrawer } from '../../printing/index.js'
import { validateDrawer } from '../../printing/drawer.js'
const props = defineProps({ profile: String, canWrite: Boolean, needsMigration: Boolean, offline: Boolean })
const session = useSessionStore(), config = ref(validateDrawer()), saved = ref(''), printerId = ref(''), matched = ref(false), busy = ref(false), error = ref(''), notice = ref('')
let sequence = 0
const printerName = computed(() => manager.state.printers.find((p) => p.id === printerId.value)?.name || printerId.value)
const ready = computed(() => props.canWrite && !props.needsMigration && !props.offline && manager.state.connection === 'connected' && manager.state.printers.some((p) => p.id === printerId.value) && manager.state.printGrants.includes(printerId.value))
const dirty = computed(() => JSON.stringify(config.value) !== saved.value)
async function load() {
  const seq = ++sequence, binding = await manager.binding(props.profile)
  if (seq !== sequence) return
  config.value = validateDrawer(binding.drawer); printerId.value = binding.receipt || ''
  matched.value = binding.drawer?.printerId === binding.receipt
  saved.value = JSON.stringify(config.value)
}
async function run(fn) { if (busy.value) return; busy.value = true; error.value = ''; notice.value = ''; try { await fn() } catch (e) { error.value = e.message } finally { busy.value = false } }
function save() { return run(async () => {
  const value = validateDrawer(config.value)
  await manager.saveDrawer(props.profile, value, (drawer, workstation) => call('esafepos.api.cash_drawer.save_setup', { pos_profile: props.profile, workstation, printer_id: drawer.printerId, values: value }))
  await load(); notice.value = t('Cash drawer settings saved for this workstation.')
}) }
function test() {
  if (!window.confirm(t('This sends a physical pulse to the receipt printer’s drawer port. Open the drawer now?'))) return
  return run(async () => {
    const result = await cashDrawer.open({ profile: props.profile, reference: { doctype: 'POS Profile', name: props.profile }, user: session.user, mode: 'test' })
    notice.value = t(result.state === 'unknown' ? 'Drawer pulse outcome is unknown. Inspect the drawer and Print jobs before another opening.' : result.state === 'failed' ? `Drawer pulse failed: ${result.error}` : 'Drawer pulse accepted. Check the physical drawer.')
  })
}
watch(() => [props.profile, manager.state.bindingRevision], load)
onMounted(load)
</script>
<style scoped>
.drawer-setup{border-top:1px solid var(--border);padding:22px 0}h3{font-size:16px;margin:0}p{font-size:12px;line-height:1.7;color:var(--text-muted)}fieldset{border:0;padding:0;min-width:0;margin:20px 0}.fields{display:flex;gap:12px;flex-wrap:wrap}.field{display:flex;flex:1;min-width:0;flex-direction:column;gap:6px;margin:12px 0;font-size:12px}.check{display:flex;gap:9px;align-items:center;font-size:13px;margin:16px 0}.check input{width:16px;flex:none}.field input,select{width:100%;padding:9px;border:1px solid var(--border);background:var(--input-bg);color:var(--text);border-radius:var(--radius);font:inherit;box-sizing:border-box}.actions{display:flex;flex-wrap:wrap;gap:9px;margin:16px 0}.error{color:var(--red)}@media(max-width:520px){.fields{flex-direction:column;gap:0}.actions>.btn{width:100%}}
</style>
