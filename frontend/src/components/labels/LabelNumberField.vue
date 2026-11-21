<template>
  <label class="label-number">
    <span>{{ label }}<small v-if="unit"> {{ unit }}</small></span>
    <input type="number" :value="shown" :min="min" :max="max" :step="step" @input="update($event.target.value)" />
  </label>
</template>
<script setup>
import { computed } from 'vue'
import { displayUnit, mm } from '../../labels/stock.js'
const props=defineProps({modelValue:[Number,String],label:String,unit:{type:String,default:''},min:[Number,String],max:[Number,String],step:{type:[Number,String],default:.1}})
const emit=defineEmits(['update:modelValue'])
const shown=computed(() => props.modelValue === '' ? '' : displayUnit(props.modelValue,props.unit))
function update(value) {emit('update:modelValue',value === '' ? '' : mm(value,props.unit))}
</script>
<style scoped>
.label-number{display:flex;flex-direction:column;gap:5px;min-width:0;font-size:12px;color:var(--text-muted)}
.label-number small{font-size:11px;font-weight:400;margin-inline-start:4px}
.label-number input{width:100%;min-width:0;padding:8px 9px;border:1px solid var(--border);border-radius:7px;background:var(--input-bg);color:var(--text);font:inherit;font-size:13px}
input:focus-visible{outline:2px solid var(--brand);outline-offset:2px}
</style>
