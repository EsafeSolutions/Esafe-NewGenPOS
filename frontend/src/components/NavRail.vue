<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<template>
  <nav id="pos-navigation" class="rail" :class="{ 'rail-open': mobileOpen }" :aria-label="t('POS navigation')"
    data-tour="nav-rail" @click="onNavClick">
    <PosBrandMark class="rail-brand" />
    <router-link v-if="!session.reportsOnly" to="/" class="rail-item" :title="t('Sell')" exact-active-class="active">
      <svg viewBox="0 0 24 24"><path d="M7 18a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm10 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM3 2h2.5l3.1 11.6A2 2 0 0 0 10.5 15h8.2a2 2 0 0 0 1.9-1.4L23 6H6.1" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <span class="rail-label">{{ t('Sell') }}</span>
    </router-link>
    <router-link v-if="!session.reportsOnly && session.permissions.view_history !== false" to="/history" class="rail-item" :title="t('History')" active-class="active">
      <svg viewBox="0 0 24 24"><path d="M12 8v5l3.5 2M21 12a9 9 0 1 1-9-9 9 9 0 0 1 9 9z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <span class="rail-label">{{ t('History') }}</span>
    </router-link>
    <router-link v-if="session.permissions.customers" to="/customers" class="rail-item" :title="t('Customers')" active-class="active">
      <svg viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <span class="rail-label">{{ t('Customers') }}</span>
    </router-link>
    <router-link v-if="!session.reportsOnly && session.permissions.customers" to="/messages" class="rail-item" :title="t('Customer messaging')" active-class="active">
      <svg viewBox="0 0 24 24"><path d="M4 4h16v12H8l-4 4V4zm4 4h8m-8 4h5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <span class="rail-label">{{ t('Customer messaging') }}</span>
    </router-link>
    <router-link v-if="!session.reportsOnly && session.settings.enable_regular_invoices && session.permissions.sell !== false" to="/invoices" class="rail-item" :title="t('Invoices')" active-class="active">
      <svg viewBox="0 0 24 24"><path d="M6 3h9l4 4v14l-3-1.5L13 21l-3-1.5L7 21l-1-1V3zm9 0v5h5M9 12h6M9 16h6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <span class="rail-label">{{ t('Invoices') }}</span>
    </router-link>
    <router-link v-if="!session.reportsOnly && session.settings.enable_buying && session.permissions.buying" to="/buying" class="rail-item" :title="t('Buying')" active-class="active">
      <svg viewBox="0 0 24 24"><path d="M3 7h18v14H3zM7 7V3h10v4M9 12l3 3 3-3m-3-2v5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <span class="rail-label">{{ t('Buying') }}</span>
    </router-link>
    <router-link v-if="holdsVisible" to="/holds" class="rail-item" :title="t('Holds')" active-class="active">
      <svg viewBox="0 0 24 24"><path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>
      <span class="rail-label">{{ t('Holds') }}</span>
    </router-link>
    <router-link v-if="!session.reportsOnly" to="/register" class="rail-item" :title="t('Register')" active-class="active">
      <svg viewBox="0 0 24 24"><path d="M3 9h18v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9zm3-5h12l2 5H4l2-5zm5 9h2" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <span class="rail-label">{{ t('Register') }}</span>
    </router-link>
    <router-link v-if="session.permissions.insights || salespeopleVisible || session.permissions.sales_reports || session.permissions.cashier_report || session.permissions.profit_report" to="/insights" class="rail-item" :title="t('Insights')" active-class="active">
      <svg viewBox="0 0 24 24"><path d="M3 3v18h18M8 17v-6m5 6V7m5 10v-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <span class="rail-label">{{ t('Insights') }}</span>
    </router-link>
    <router-link v-if="!session.reportsOnly && (session.permissions.edit_items || session.permissions.stock_count)" to="/items" class="rail-item" :title="t('Items & stock')" active-class="active" data-tour="count-rail">
      <svg viewBox="0 0 24 24"><path d="m3 7 9-4 9 4v10l-9 4-9-4zM3 7l9 4 9-4m-9 4v10" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>
      <span class="rail-label">{{ t('Items & stock') }}</span>
    </router-link>
    <!-- Barcode and price labels (0.67.0): the shop's switch and the person's permission. -->
    <router-link v-if="session.permissions.settings || (!session.reportsOnly && (session.settings.esafe_printing?.silent || session.settings.enable_labels && session.permissions.print_labels))" to="/printing" class="rail-item" :title="t('Printing')" active-class="active" data-tour="labels-rail">
      <svg viewBox="0 0 24 24"><path d="M6 9V3h12v6M6 18H3V9h18v9h-3M6 14h12v7H6zM17 12h1" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <span class="rail-label">{{ t('Printing') }}</span>
    </router-link>
    <button
      v-if="session.canApprove"
      type="button"
      class="rail-item"
      :class="{ active: approvalsOpen }"
      :title="t('Approvals')"
      @click="approvalsOpen = true"
    >
      <span class="icon-wrap">
        <svg viewBox="0 0 24 24"><path d="M9 12l2 2 4-4M21 12a9 9 0 1 1-9-9 9 9 0 0 1 9 9z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
        <span v-if="pendingCount" class="badge">{{ pendingCount }}</span>
      </span>
      <span class="rail-label">{{ t('Approvals') }}</span>
    </button>
    <router-link v-if="session.canManageAny" to="/settings" class="rail-item" :title="t('Settings')" active-class="active">
      <svg viewBox="0 0 24 24"><path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <span class="rail-label">{{ t('Settings') }}</span>
    </router-link>
  </nav>
  <ApprovalsModal v-if="approvalsOpen" @close="onApprovalsClose" @changed="refreshPending" />
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useSessionStore } from '../stores/session'
import { call } from '../api'
import { t } from '../i18n'
import PosBrandMark from './PosBrandMark.vue'

defineProps({ mobileOpen: Boolean })
const emit = defineEmits(['navigate'])

function onNavClick(event) {
  if (event.target.closest('a')) emit('navigate')
}

import ApprovalsModal from './ApprovalsModal.vue'

const session = useSessionStore()
// Holds show when the shop uses them, and keep showing while any are still
// open: switching the feature off must not strand a customer's deposit.
const holdsVisible = computed(
  () =>
    !session.reportsOnly &&
    (session.settings.enable_layaway || session.settings.open_holds) &&
    session.permissions.can_hold_goods !== false
)
// Insights also opens for the salesperson report alone (its Salespeople tab): for
// whoever may see it, while the shop uses salespeople.
const salespeopleVisible = computed(
  () => session.permissions.sales_by_person && (session.settings.salesperson_mode || 'Optional') !== 'Off'
)
const approvalsOpen = ref(false)
const pendingCount = ref(0)
let timer = null

async function refreshPending() {
  if (!session.canApprove || session.offline) {
    pendingCount.value = 0
    return
  }
  try {
    // No profile scoping, an approver sees every open-shift request they can
    // act on, even when their till is on a different POS profile than the cashier.
    const rows = await call('esafepos.api.approval_requests.pending_requests', {})
    pendingCount.value = rows.length
  } catch {
    /* ignore, the badge is best-effort */
  }
}

function onApprovalsClose() {
  approvalsOpen.value = false
  refreshPending()
}

onMounted(() => {
  if (!session.canApprove) return
  refreshPending()
  timer = setInterval(refreshPending, 10000)
  window.addEventListener('focus', refreshPending)
})
onUnmounted(() => {
  clearInterval(timer)
  window.removeEventListener('focus', refreshPending)
})
</script>

<style scoped>
.rail {
  width: 56px;
  background: var(--card-bg);
  border-inline-end: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 4px;
  padding: 8px 6px 10px;
  flex-shrink: 0;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
}
.rail-brand { align-self: center; margin-bottom: 8px; }
.rail-item {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 39px;
  padding: 6px;
  color: var(--text-muted);
  text-decoration: none;
  font-size: 13px;
  font-weight: 600;
  border: 1px solid transparent;
  border-radius: 8px;
}
.rail-item svg {
  width: 19px;
  height: 19px;
  flex: none;
}
.rail-item:hover { color: var(--text); background: var(--surface-2); }
.rail-item:focus-visible { outline: 2px solid var(--brand); outline-offset: -2px; }
.rail-item.active {
  color: var(--text);
  background: var(--surface-2);
  border-color: var(--border);
  box-shadow: var(--shadow);
}
@media (min-width: 701px) {
  .rail-label { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
}
@media (max-width: 700px) {
  .rail {
    display: none;
    position: absolute;
    width: min(192px, 75vw);
    inset-block: 52px 0;
    inset-inline-start: 0;
    padding: 8px;
    z-index: 42;
  }
  .rail-open { display: flex; }
  .rail .rail-brand { display: none; }
  .rail-item { justify-content: flex-start; padding-inline: 10px; text-align: start; }
  .rail-label { overflow-wrap: anywhere; }
}
.icon-wrap { position: relative; display: inline-flex; }
.badge {
  position: absolute;
  top: -6px;
  right: -9px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 999px;
  background: var(--red);
  color: #fff;
  font-size: 10px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
}
</style>
