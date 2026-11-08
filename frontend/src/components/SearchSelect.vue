<template>
  <div ref="root" class="search-select" @keydown.esc="open = false">
    <button class="search-select-trigger" type="button" :aria-expanded="open" @click="toggle">
      <span class="search-select-label">{{ label }}</span>
      <span class="search-select-value" :class="{ placeholder: !modelValue }">{{ selectedLabel }}</span>
      <span class="search-select-chevron" aria-hidden="true">⌄</span>
    </button>
    <div v-if="open" class="search-select-menu">
      <label class="search-select-search">
        <Icon name="search" />
        <input ref="searchInput" v-model="query" :aria-label="t('Search {label}', { label })" :placeholder="t('Search {label}', { label })" />
        <button v-if="query" type="button" class="search-select-clear" :aria-label="t('Clear search')" @click="query = ''; focusSearch()"><Icon name="close" /></button>
      </label>
      <div class="search-select-options" role="listbox" :aria-label="label">
        <button v-for="option in filtered" :key="option.value" type="button" role="option" :aria-selected="option.value === modelValue" class="search-select-option" :class="{ selected: option.value === modelValue }" @click="choose(option)">
          {{ option.label }}
        </button>
        <p v-if="!filtered.length" class="search-select-empty">{{ t('No matches') }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import Icon from './Icon.vue'
import { t } from '../i18n'

const props = defineProps({ label: String, modelValue: { type: String, default: '' }, options: { type: Array, default: () => [] } })
const emit = defineEmits(['update:modelValue', 'change'])
const root = ref(null)
const searchInput = ref(null)
const query = ref('')
const open = ref(false)
const selectedLabel = computed(() => props.options.find((item) => item.value === props.modelValue)?.label || props.options[0]?.label || '')
const filtered = computed(() => {
  const q = query.value.trim().toLocaleLowerCase()
  return q ? props.options.filter((item) => item.label.toLocaleLowerCase().includes(q)) : props.options
})

function focusSearch() { nextTick(() => searchInput.value?.focus()) }
function toggle() { open.value = !open.value; if (open.value) { query.value = ''; focusSearch() } }
function choose(option) { emit('update:modelValue', option.value); emit('change', option.value); open.value = false; query.value = '' }
function onOutside(event) { if (!root.value?.contains(event.target)) open.value = false }
onMounted(() => document.addEventListener('pointerdown', onOutside))
onBeforeUnmount(() => document.removeEventListener('pointerdown', onOutside))
</script>

<style scoped>
.search-select { position:relative; min-width:185px; }
.search-select-trigger { display:flex; align-items:center; gap:10px; width:100%; min-height:40px; padding:6px 11px; border:1px solid var(--border); border-radius:9px; background:var(--card-bg); text-align:left; }
.search-select-trigger:hover, .search-select-trigger[aria-expanded='true'] { border-color:var(--brand); }
.search-select-label { color:var(--text-muted); font-size:11px; font-weight:700; }
.search-select-value { flex:1; min-width:0; overflow:hidden; color:var(--text); font-size:13px; font-weight:600; text-overflow:ellipsis; white-space:nowrap; }
.search-select-value.placeholder { color:var(--text-muted); font-weight:500; }
.search-select-chevron { color:var(--text-muted); font-size:17px; line-height:1; }
.search-select-menu { position:absolute; top:calc(100% + 5px); left:0; z-index:30; width:max(100%, 270px); padding:6px; border:1px solid var(--border); border-radius:10px; background:var(--card-bg); box-shadow:var(--shadow-md); }
.search-select-search { display:flex; align-items:center; gap:8px; padding:0 9px; border:1px solid var(--border); border-radius:7px; color:var(--text-muted); }
.search-select-search input { width:100%; min-width:0; padding:8px 0; border:0; outline:0; background:transparent; box-shadow:none; font-size:13px; }
.search-select-clear { display:grid; place-items:center; padding:3px; }
.search-select-options { max-height:min(300px, 45vh); overflow-y:auto; padding-top:5px; }
.search-select-option { display:block; width:100%; padding:9px 10px; border-radius:6px; text-align:left; font-size:13px; }
.search-select-option:hover, .search-select-option.selected { background:var(--surface-2); color:var(--brand-dark); }
.search-select-empty { padding:10px; color:var(--text-muted); font-size:13px; }
@media(max-width:700px) { .search-select { flex:1 1 150px; min-width:0; } }
</style>
