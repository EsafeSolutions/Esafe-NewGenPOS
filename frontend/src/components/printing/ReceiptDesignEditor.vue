<template>
  <details class="design-editor">
    <summary>{{ t('Advanced custom receipt editor') }}</summary>
    <p>{{ t('Adjust alignment, typography and space inside the receipt. Blank values keep the selected template. Design padding is added inside the workstation printer margins.') }}</p>
    <p>{{ t('Applies to the live preview, browser receipts and silent built-in HTML. Raw printers and ERPNext Print Formats use their own layout.') }}</p>
    <div class="design-fields">
      <label v-for="field in alignments" :key="field.key" class="field">
        <span>{{ t(field.label) }}</span>
        <select :aria-label="t(field.label)" :value="design[field.key] || ''" @change="update(field.key, $event.target.value)">
          <option value="">{{ t('Template default') }}</option><option value="left">{{ t('Left') }}</option><option value="center">{{ t('Center') }}</option><option value="right">{{ t('Right') }}</option>
        </select>
      </label>
      <label v-for="field in numbers" :key="field.key" class="field">
        <span>{{ t(field.label) }}</span>
        <input type="number" :aria-label="t(field.label)" :value="design[field.key] ?? ''" :min="DESIGN_RANGES[field.key][0]" :max="DESIGN_RANGES[field.key][1]" step="0.1" :placeholder="t('Template default')" @input="update(field.key, $event.target.value)" />
      </label>
    </div>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <button class="btn btn-outline" @click="$emit('update:modelValue', {})">{{ t('Reset advanced design') }}</button>
  </details>
</template>
<script setup>
import { computed } from 'vue'
import { t } from '../../i18n'
import { cleanReceiptDesign, DESIGN_RANGES } from '../../receiptDesign.js'
const props = defineProps({ modelValue: { type: [Object, String], default: () => ({}) } })
const emit = defineEmits(['update:modelValue'])
const design = computed(() => {
  try { return typeof props.modelValue === 'string' ? JSON.parse(props.modelValue || '{}') : props.modelValue || {} }
  catch { return {} }
})
const error = computed(() => { try { cleanReceiptDesign(design.value); return '' } catch (e) { return e.message } })
function update(key, value) {
  const next = { ...design.value }
  if (value === '') delete next[key]
  else next[key] = DESIGN_RANGES[key] ? Number(value) : value
  emit('update:modelValue', next)
}
const alignments = [
  { key: 'headerAlign', label: 'Header alignment' }, { key: 'footerAlign', label: 'Footer alignment' },
  { key: 'itemAlign', label: 'Item name alignment' }, { key: 'labelAlign', label: 'Totals label alignment' },
  { key: 'valueAlign', label: 'Totals amount alignment' },
]
const numbers = [
  { key: 'fontSize', label: 'Body font size (px)' }, { key: 'totalSize', label: 'Net total size (px)' },
  { key: 'lineHeight', label: 'Line height' }, { key: 'sectionGap', label: 'Section spacing (mm)' },
  { key: 'paddingTop', label: 'Design top padding (mm)' }, { key: 'paddingRight', label: 'Design right padding (mm)' },
  { key: 'paddingBottom', label: 'Design bottom padding (mm)' }, { key: 'paddingLeft', label: 'Design left padding (mm)' },
  { key: 'itemPadding', label: 'Item row padding (mm)' }, { key: 'borderWidth', label: 'Border thickness (px)' },
  { key: 'logoHeight', label: 'Logo maximum height (px)' }, { key: 'barcodeHeight', label: 'Invoice barcode height (px)' },
]
</script>
<style scoped>
.design-editor{border:1px solid var(--border);border-radius:var(--radius);padding:14px;margin:18px 0}summary{cursor:pointer;font-weight:650;font-size:14px}p{font-size:12px;color:var(--text-muted);line-height:1.7}.design-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:16px 0}.field{display:flex;flex-direction:column;gap:6px;font-size:12px}input,select{width:100%;box-sizing:border-box;font:inherit;border:1px solid var(--border);border-radius:var(--radius);padding:9px;background:var(--input-bg);color:var(--text)}.error{color:var(--red)}@media(max-width:520px){.design-fields{grid-template-columns:1fr}}
</style>
