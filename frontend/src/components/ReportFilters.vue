<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<!-- The period and the outlets of a report in Insights (0.62.0). "Today" is the
     site's today, not the device's: a till in another time zone would otherwise
     ask for the wrong day (the 0.61.1 lesson of the shift clock). Emits
     `change` with what the server's report takes. -->
<template>
  <div class="rf">
    <div class="seg">
      <button v-for="p in PERIODS" :key="p.key" type="button" class="seg-btn" :class="{ on: period === p.key }" @click="pick(p.key)">
        {{ t(p.label) }}
      </button>
    </div>
    <template v-if="period === 'custom'">
      <input v-model="fromDate" type="date" class="cf-in" @change="emitChange" />
      <input v-model="toDate" type="date" class="cf-in" @change="emitChange" />
    </template>
    <!-- The reports alone (0.65.0): every company whole, or one outlet of it. -->
    <select v-if="session.reportsOnly" v-model="scope" class="cf-in" @change="emitChange">
      <option v-for="c in session.reportChoices" :key="c.value" :value="c.value">{{ c.label }}</option>
    </select>
    <select v-else v-model="scope" class="cf-in" @change="emitChange">
      <!-- An outlet of several registers (0.64.0): this register, or all of them. -->
      <option v-if="shared" value="register">{{ t('This register') }}: {{ session.posProfile }}</option>
      <option value="outlet">{{ t('This outlet') }}: {{ outletName }}</option>
      <option value="company">{{ t('Every outlet of {company}', { company: session.company }) }}</option>
    </select>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { t } from '../i18n'
import { useSessionStore } from '../stores/session'

const props = defineProps({ defaultScope: { type: String, default: 'outlet' } })
const emit = defineEmits(['change'])
const session = useSessionStore()
const PERIODS = [
  { key: 'today', label: 'Today' },
  { key: 'yesterday', label: 'Yesterday' },
  { key: 'week', label: 'Last 7 days' },
  { key: 'month', label: 'This month' },
  { key: 'custom', label: 'Custom' },
]
const period = ref('today')
const shared = computed(() => (session.myOutlet?.size || 0) > 1)
const outletName = computed(() => (shared.value ? session.myOutlet.name : session.posProfile))
const scope = ref(
  session.reportsOnly
    ? session.reportChoices[0]?.value || ''
    : props.defaultScope === 'company' ? 'company' : 'outlet'
)
const fromDate = ref('')
const toDate = ref('')

// session.siteNow() is the site's wall clock on a UTC scale, so the UTC parts
// of it are the site's own date.
const iso = (ms) => new Date(ms).toISOString().slice(0, 10)
const DAY = 86400000

function range(key) {
  const now = session.siteNow()
  const d = new Date(now)
  if (key === 'yesterday') return [iso(now - DAY), iso(now - DAY)]
  if (key === 'week') return [iso(now - 6 * DAY), iso(now)]
  if (key === 'month') return [iso(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1)), iso(now)]
  return [iso(now), iso(now)]
}

function emitChange() {
  emit('change', {
    from_date: fromDate.value,
    to_date: toDate.value || fromDate.value,
    ...session.reportScope(scope.value),
  })
}

function pick(key) {
  period.value = key
  if (key === 'custom') {
    if (!fromDate.value) [fromDate.value, toDate.value] = range('week')
  } else {
    ;[fromDate.value, toDate.value] = range(key)
  }
  emitChange()
}

onMounted(() => pick('today'))
</script>

<style scoped>
.rf { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 12px 14px; border-bottom: 1px solid var(--border); }
.seg { display: inline-flex; flex-wrap: wrap; border: 1px solid var(--border); border-radius: 9px; overflow: hidden; }
.seg-btn { background: transparent; border: 0; padding: 7px 12px; font: inherit; font-size: 13px; color: var(--text); cursor: pointer; }
.seg-btn + .seg-btn { border-inline-start: 1px solid var(--border); }
.seg-btn.on { background: var(--brand); color: #fff; }
.rf select.cf-in { max-width: 100%; }
</style>
