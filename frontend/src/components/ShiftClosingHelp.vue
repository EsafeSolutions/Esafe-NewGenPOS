<template>
  <div class="shift-help" role="status" aria-live="polite">
    <div class="help-heading"><Icon :name="failed ? 'warning' : 'hourglass'" :size="20" /><strong>{{ issue.title }}</strong></div>
    <p>{{ issue.message }}</p>
    <p v-if="issue.item" class="item-name">{{ t('Item') }}: <b>{{ issue.item }}</b></p>
    <p>{{ issue.action }}</p>
    <p v-if="failed" class="muted small">
      {{ Number(state.closing_attempts) >= 30
        ? t('Automatic retries have paused after repeated failures. A manager can correct the cause and retry here.')
        : t('Background recovery retries posting, up to 30 attempts. Missing costs, stock or accounting settings need a manager to correct them first.') }}
    </p>
    <a v-if="issue.item && manager" class="entry-link" :href="`/app/item/${encodeURIComponent(issue.item)}`" target="_blank" rel="noopener">{{ t('Check item in ERPNext') }}</a>
    <details v-if="state.closing_error">
      <summary>{{ t('Details for manager') }}</summary>
      <p v-if="sessionName"><b>{{ t('Session') }}: {{ sessionName }}</b></p>
      <pre>{{ plainText(state.closing_error) }}</pre>
    </details>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import Icon from './Icon.vue'
import { closingIssue } from '../shiftHelp'
import { plainText } from '../format'
import { t } from '../i18n'
const props = defineProps({ state: { type: Object, required: true }, sessionName: String, manager: Boolean })
const issue = computed(() => closingIssue(props.state))
const failed = computed(() => props.state.closing_status === 'Failed')
</script>

<style scoped>
.shift-help { background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px; margin-bottom: 14px; line-height: 1.55; overflow-wrap: anywhere; }
.help-heading { display: flex; align-items: center; gap: 9px; font-size: 16px; }
.help-heading :first-child { flex-shrink: 0; color: var(--brand-dark); }
.shift-help p { margin: 8px 0 0; }
.small { font-size: 12px; }
.shift-help details { margin-top: 12px; border-top: 1px solid var(--border); padding-top: 10px; }
.shift-help summary { cursor: pointer; font-weight: 600; }
.shift-help pre { white-space: pre-wrap; overflow-wrap: anywhere; font: 12px/1.6 var(--mono); max-height: 180px; overflow-y: auto; user-select: text; }
.entry-link { display: inline-block; margin-top: 10px; color: var(--brand-dark); }
</style>
