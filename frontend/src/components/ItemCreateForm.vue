<template>
  <form class="card create-item" @submit.prevent="create">
    <h2>{{ t('Add item') }}</h2>
    <fieldset :disabled="saving">
      <label>{{ t('Item code') }}<input v-model.trim="draft.item_code" required maxlength="140" /></label>
      <label>{{ t('Item name') }}<input v-model.trim="draft.item_name" required maxlength="140" /></label>
      <label>{{ t('Category') }}<select v-model="draft.item_group" required><option value="" disabled>{{ t('Choose a category') }}</option><option v-for="name in options.item_groups" :key="name">{{ name }}</option></select></label>
      <label>{{ t('Stock unit') }}<select v-model="draft.stock_uom" required><option value="" disabled>{{ t('Choose a unit') }}</option><option v-for="name in options.stock_uoms" :key="name">{{ name }}</option></select></label>
      <label>{{ t('Brand') }}<select v-model="draft.brand"><option value="">{{ t('No brand') }}</option><option v-for="name in options.brands" :key="name">{{ name }}</option></select></label>
      <label>{{ t('Barcode (optional)') }}<input v-model.trim="draft.barcode" maxlength="140" /></label>
      <p class="muted">{{ t('Creates a stock item. Add its selling prices and warehouse stock after saving.') }}</p>
      <button class="btn btn-primary">{{ saving ? t('Saving…') : t('Create item') }}</button>
      <button type="button" class="btn btn-outline" @click="$emit('cancel')">{{ t('Cancel') }}</button>
    </fieldset>
  </form>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { call } from '../api'
import { t } from '../i18n'
import { useSessionStore } from '../stores/session'
defineProps({ options: { type: Object, required: true } })
const emit = defineEmits(['created', 'cancel', 'busy'])
const session = useSessionStore()
const saving = ref(false)
const draft = reactive({ item_code: '', item_name: '', item_group: '', stock_uom: '', barcode: '', brand: '' })
async function create() {
  if (saving.value || session.offline) return
  saving.value = true
  emit('busy', true)
  const profile = session.posProfile
  try {
    const result = await call('esafepos.api.items.create_item', { pos_profile: profile, ...draft })
    if (profile !== session.posProfile) return
    session.notify(t('Item created'))
    emit('created', result.item_code)
  } catch (error) {
    session.notify(error.message, true)
  } finally {
    saving.value = false
    emit('busy', false)
  }
}
</script>

<style scoped>
.create-item { padding: 16px; min-width: 0; }
h2 { margin: 0 0 16px; }
fieldset { border: 0; padding: 0; margin: 0; display: grid; gap: 14px; min-width: 0; }
label { display: grid; gap: 5px; }
input, select { width: 100%; min-width: 0; }
</style>
