<template>
  <button v-if="visible" class="btn btn-outline" :disabled="busy || !ready" @click="open">{{ busy ? t('Opening…') : t('Open cash drawer') }}</button>
</template>
<script setup>
import { computed, onMounted, onActivated, ref, watch } from 'vue'
import { useSessionStore } from '../../stores/session'
import { t } from '../../i18n'
import { printManager as manager, cashDrawer } from '../../printing/index.js'
const session = useSessionStore(), enabled = ref(false), busy = ref(false), printerId = ref('')
const visible = computed(() => enabled.value && session.permissions.can_cash_out && session.registerSession?.name && !session.offline)
const ready = computed(() => manager.state.connection === 'connected' && manager.state.printGrants.includes(printerId.value) && manager.state.printers.some((p) => p.id === printerId.value))
async function load() { const binding = await manager.binding(session.posProfile); printerId.value = binding.receipt; enabled.value = !!binding.drawer?.enabled && binding.drawer.printerId === binding.receipt }
async function open() {
  if (busy.value || !ready.value) return
  const reason = window.prompt(t('Reason for opening the cash drawer (required, up to 140 characters):'))
  if (!reason?.trim()) return
  busy.value = true
  try {
    const result = await cashDrawer.open({ profile: session.posProfile, reference: { doctype: 'POS Register Session', name: session.registerSession.name }, user: session.user, mode: 'manual', reason: reason.trim() })
    session.notify(t(result.state === 'unknown' ? 'Drawer pulse outcome is unknown. Inspect the drawer and Print jobs before another opening.' : result.state === 'failed' ? `Drawer pulse failed: ${result.error}` : 'Drawer pulse accepted. Check the physical drawer.'))
  } catch (e) { session.notify(e.message, true) } finally { busy.value = false }
}
watch(() => [session.posProfile, manager.state.bindingRevision], load)
onMounted(load); onActivated(load)
</script>
