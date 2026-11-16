<template>
  <form class="image-search-config" @submit.prevent="save">
    <p class="muted">{{ t('Find online works without an API key. Gemini can suggest more precise search terms from the item name, brand and barcode.') }}</p>
    <fieldset :disabled="busy || !loaded">
      <label class="image-search-toggle">
        <input v-model="enabled" type="checkbox" />
        {{ t('Enable Gemini search assistance') }}
      </label>
      <label class="image-search-key">
        {{ t('Gemini API key') }}
        <input v-model.trim="key" type="password" autocomplete="new-password" maxlength="256"
          :placeholder="configured ? t('Key saved. Enter a new key to replace it.') : ''" />
      </label>
      <button type="submit" class="btn btn-primary">{{ t('Save Gemini settings') }}</button>
    </fieldset>
    <p v-if="message" role="status">{{ message }}</p>
  </form>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { call } from '../api'
import { t } from '../i18n'

const enabled = ref(false)
const configured = ref(false)
const key = ref('')
const loaded = ref(false)
const busy = ref(false)
const message = ref('')
const api = 'esafepos.api.item_image_search.'

function applyConfig(config) {
  enabled.value = config.enabled
  configured.value = config.configured
}

onMounted(async () => {
  try {
    applyConfig(await call(api + 'get_config'))
    loaded.value = true
  } catch (error) {
    message.value = error.message
  }
})

async function save() {
  if (busy.value || !loaded.value) return
  busy.value = true
  message.value = ''
  try {
    applyConfig(await call(api + 'save_config', { enabled: enabled.value, api_key: key.value }))
    key.value = ''
    message.value = t('Gemini settings saved')
  } catch (error) {
    message.value = error.message
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.image-search-config fieldset { display: grid; gap: 12px; border: 0; margin: 0; padding: 0; min-width: 0; justify-items: start; }
.image-search-key { display: grid; gap: 5px; width: min(100%, 420px); }
.image-search-toggle { display: flex; align-items: center; gap: 8px; }
</style>
