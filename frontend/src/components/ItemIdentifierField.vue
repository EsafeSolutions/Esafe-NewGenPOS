<template>
  <div class="identifier-field">
    <label>{{ label }}
      <input :value="modelValue" :required="required" maxlength="140" :disabled="generating"
        @input="$emit('update:modelValue', $event.target.value.trim())" />
    </label>
    <div class="generation-controls">
      <label>{{ t('Code type') }}
        <select v-model="options.character_type" :disabled="generating" @change="typeChanged">
          <option value="numeric">{{ t('Numbers only') }}</option>
          <option value="alphanumeric">{{ t('Letters and numbers') }}</option>
        </select>
      </label>
      <label>{{ options.character_type === 'numeric' ? t('Digits') : t('Characters') }}
        <input v-model.number="options.length" type="number" :min="options.character_type === 'numeric' ? 1 : 2"
          max="140" step="1" :disabled="generating" />
      </label>
      <button type="button" class="btn btn-outline" :disabled="generating || session.offline || !validGenerationOptions(options)"
        @click="generate">{{ generating ? t('Generating…') : target === 'item_code' ? t('Generate item code') : t('Generate barcode') }}</button>
    </div>
    <small v-if="error" class="generation-error" role="alert">{{ error }}</small>
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { call } from '../api'
import { t } from '../i18n'
import { loadGenerationOptions, saveGenerationOptions, validGenerationOptions } from '../itemUtilities'
import { useSessionStore } from '../stores/session'

const props = defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, required: true },
  target: { type: String, required: true },
  required: Boolean,
  itemCode: { type: String, default: '' },
  exclude: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'busy'])
const session = useSessionStore()
const options = ref(loadGenerationOptions(session.posProfile, props.target))
const generating = ref(false)
const error = ref('')
let active = true
watch(options, (value) => saveGenerationOptions(session.posProfile, props.target, value), { deep: true })
watch(() => session.posProfile, (profile) => {
  options.value = loadGenerationOptions(profile, props.target)
  error.value = ''
})
onBeforeUnmount(() => { active = false })

function typeChanged() {
  if (options.value.character_type === 'alphanumeric' && options.value.length === 1) options.value.length = 2
}

async function generate() {
  if (generating.value || session.offline || !validGenerationOptions(options.value)) return
  generating.value = true
  error.value = ''
  emit('busy', true)
  const profile = session.posProfile
  const previous = props.modelValue
  try {
    const result = await call('esafepos.api.items.generate_identifier', {
      pos_profile: profile, target: props.target, ...options.value,
      item_code: props.itemCode || null,
      exclude: JSON.stringify([...new Set([...props.exclude, previous].filter(Boolean))]),
    })
    if (active && profile === session.posProfile && previous === props.modelValue && !session.offline) {
      if (props.exclude.some((value) => value?.trim().toUpperCase() === result.value.toUpperCase())) {
        error.value = t('This code is already used in this form. Generate another code.')
      } else {
        emit('update:modelValue', result.value)
      }
    }
  } catch (failure) {
    if (active && profile === session.posProfile) error.value = failure.message
  } finally {
    generating.value = false
    emit('busy', false)
  }
}
</script>

<style scoped>
.identifier-field { display: grid; gap: 8px; min-width: 0; }
label { display: grid; gap: 5px; min-width: 0; }
input, select { width: 100%; min-width: 0; }
.generation-controls { display: grid; grid-template-columns: minmax(0, 1fr) 90px auto; gap: 8px; align-items: end; }
.generation-error { color: var(--red); }
@media (max-width: 520px) {
  .generation-controls { grid-template-columns: minmax(0, 1fr) 90px; }
  .generation-controls button { grid-column: 1 / -1; }
}
</style>
