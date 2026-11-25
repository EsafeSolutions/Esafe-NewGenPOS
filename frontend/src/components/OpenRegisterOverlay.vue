<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<template>
  <div class="open-backdrop">
    <div class="modal" style="width: 460px">
      <div class="modal-header">{{ t('Open register') }}</div>

      <!-- A previous shift's closing hasn't finished (or failed): must be
           resolved before anyone can open or sell again. -->
      <template v-if="pending">
        <div class="modal-body">
          <div class="shift-banner warn">
            <div class="shift-name">{{ t('Previous shift') }} · {{ pending.session }}</div>
          </div>
          <ShiftClosingHelp :state="pending" :session-name="pending.session" :manager="session.permissions.is_manager" />
          <PeriodHint v-if="pending.closing_hint" :hint="pending.closing_hint" />
          <button
            v-if="canClose"
            class="btn btn-outline choice-btn"
            :disabled="busy || session.offline"
            @click="retry"
          >
            <Icon name="refresh" /> {{ busy ? t('Checking…') : t('Check and retry closing') }}
          </button>
          <p class="muted small">
            {{ t('Retries keep the saved counts and skip sales already posted.') }}
          </p>

          <!-- ERPNext 16 requires the previous native opening to finish first.
               Other modes can start a fresh shift without changing old counts. -->
          <p v-if="pending.new_shift_blocked" class="muted small">{{ t('This outlet must finish the previous closing before a new shift can start. Ask a manager to fix the issue above, then retry.') }}</p>
          <div v-if="canOpen && !pending.new_shift_blocked" class="force-new-block">
            <div class="or-sep"><span>{{ t('or open a new shift now') }}</span></div>
            <label class="field-label">{{ t('Opening float for the new shift') }}</label>
            <input
              class="float-input"
              type="text"
              inputmode="decimal"
              v-model="openingFloat"
              :disabled="busy"
            />
            <label v-for="d in foreignDrawers" :key="d.mode_of_payment" class="field-label">
              {{ t('{drawer} float ({currency})', { drawer: d.mode_of_payment, currency: d.account_currency }) }}
              <input
                class="float-input"
                type="text"
                inputmode="decimal"
                v-model="floats[d.mode_of_payment]"
                :disabled="busy"
              />
            </label>
            <button class="btn btn-primary choice-btn" :disabled="busy || session.offline" @click="forceNew">
              <Icon name="play" /> {{ busy ? t('Opening…') : t('Open a new shift') }}
              <span class="choice-hint"
                >{{ t('The previous shift keeps its own sales and closing count. A manager can finish posting it separately.') }}</span
              >
            </button>
          </div>

          <p v-if="!canClose" class="muted small dead-end">
            {{ t("You don't have permission to close registers. Ask a manager to retry the closing of") }} {{ pending.session }}.
          </p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" style="width: 100%" @click="$router.push('/register')">
            {{ t('Open the Register page') }}
          </button>
        </div>
      </template>

      <!-- Step 1: float entry -->
      <template v-else>
        <div class="modal-body">
          <!-- An ERPNext accounting period locks sales invoices today: the
               shift can sell, but its close would fail (0.58.1). -->
          <PeriodHint
            v-if="session.periodLock"
            :hint="session.periodLock"
            when="today"
            :invoice-mode="session.invoiceMode"
          />
          <!-- A native ERPNext opening made outside the POS blocks this outlet
               on ERPNext 16. Its guarded recovery controls live on Register. -->
          <div v-if="externalOpenings.length" class="shift-banner warn oe-warn">
            <div><Icon name="warning" /> {{ t('ERPNext opening needs attention') }}</div>
            <div v-for="entry in externalOpenings" :key="entry.opening_entry" class="oe-item">
              {{ entry.opened_by_name || entry.opened_by || t('Unknown') }}
              <span class="oe-sess">({{ entry.opening_entry }})</span>
            </div>
            <div class="choice-hint">
              {{ t('This opening was not created by ESAFE POS. Open Register to safely end an unused entry or take over an empty opening from today.') }}
            </div>
            <button type="button" class="oe-go" :disabled="busy" @click="router.push('/register')">
              {{ t('Open the Register page') }}
            </button>
          </div>
          <!-- Shifts this person still holds at other outlets. A reminder, or,
               when the shop allows one open shift per person, the reason this
               one cannot open yet, with a way to get to the open one. -->
          <div v-if="others.length" class="shift-banner warn oe-warn" :class="{ 'oe-block': oneShiftBlocked }">
            <div>
              <Icon name="warning" />
              {{
                oneShiftBlocked
                  ? t('Close your open shift first')
                  : others.length > 1
                    ? t('You still have {n} other registers open:', { n: others.length })
                    : t('You still have another register open:')
              }}
            </div>
            <div v-for="r in others" :key="r.session" class="oe-item">
              {{ r.pos_profile }} <span class="oe-sess">({{ r.session }})</span>
              <button
                v-if="r.reachable !== false && session.availableProfiles.includes(r.pos_profile)"
                type="button"
                class="oe-go"
                :disabled="busy"
                @click="goClose(r.pos_profile)"
              >
                {{ t('Go to its Register page') }}
              </button>
              <span v-else class="oe-ask">{{ t('Not open to you any more: ask a manager to close it.') }}</span>
            </div>
            <div v-if="oneShiftBlocked || anyReachable" class="choice-hint">
              {{
                oneShiftBlocked
                  ? t('This shop allows one open shift per person at a time. Close it, then open this one.')
                  : others.length > 1
                    ? t('Remember to close each one when its shift ends.')
                    : t('Remember to close it when its shift ends.')
              }}
            </div>
            <div v-if="oneShiftBlocked" class="choice-hint">
              {{ t("If you cannot close it, a manager can close it for you from that outlet's Register page.") }}
            </div>
          </div>
          <template v-if="session.availableProfiles.length > 1">
            <label class="field-label">{{ t('Outlet') }}</label>
            <select
              class="outlet-select"
              :value="session.posProfile"
              :disabled="busy"
              @change="onSwitchOutlet($event.target.value)"
            >
              <option v-for="p in session.availableProfiles" :key="p" :value="p">{{ session.outletLabel(p) }}</option>
            </select>
            <p class="muted" style="margin-top: 12px">
              {{ t('Enter the opening cash float to start selling.') }}
            </p>
          </template>
          <p v-else class="muted">
            {{ session.posProfile }}. {{ t('Enter the opening cash float to start selling.') }}
          </p>
          <label class="field-label">{{ t('Opening float') }}</label>
          <p class="muted small">{{ t('Opening float is the change you start with. Enter 0 only if the drawer is empty.') }}</p>
          <input
            ref="floatInput"
            type="text"
            inputmode="decimal"
            v-model="openingFloat"
            style="width: 100%"
            :disabled="!canOpen || oneShiftBlocked"
            @keydown.enter="open"
          />
          <!-- A drawer in another currency (Settings, General, Other
               currencies) starts with its own float, in its own money. -->
          <label v-for="d in foreignDrawers" :key="d.mode_of_payment" class="field-label">
            {{ t('{drawer} float ({currency})', { drawer: d.mode_of_payment, currency: d.account_currency }) }}
            <input
              type="text"
              inputmode="decimal"
              v-model="floats[d.mode_of_payment]"
              style="width: 100%"
              :disabled="!canOpen"
              @keydown.enter="open"
            />
          </label>
        </div>
        <div class="modal-footer">
          <button
            class="btn btn-primary btn-lg"
            style="width: 100%"
            :disabled="busy || !canOpen || oneShiftBlocked || session.offline"
            @click="open"
          >
            {{ busy ? t('Opening…') : t('Open Register') }}
          </button>
          <p v-if="!canOpen" class="muted small dead-end" style="text-align: center">
            {{ t("You don't have permission to open a register.") }}
          </p>
        </div>
      </template>

    </div>
  </div>
</template>

<script setup>
import Icon from './Icon.vue'
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '../stores/session'
import { useCatalogStore } from '../stores/catalog'
import { call } from '../api'
import { t } from '../i18n'
import { parseMoney } from '../format'
import PeriodHint from './PeriodHint.vue'
import ShiftClosingHelp from './ShiftClosingHelp.vue'
import { createClosingMonitor } from '../shiftHelp'

const session = useSessionStore()
const catalog = useCatalogStore()
const openingFloat = ref('0')
const busy = ref(false)
const floatInput = ref(null)
const pending = ref(session.pendingClosing)

// Cash drawers in another currency ("Cash USD"): each counts its own money.
// None while selling in other currencies is off, though the drawers stay on
// the outlet (the server ignores such a float too).
const foreignDrawers = computed(() =>
  session.multiCurrency?.enabled
    ? (session.paymentModes || []).filter(
        (m) => m.type === 'Cash' && m.account_currency && m.account_currency !== session.localCurrency
      )
    : []
)
const floats = ref({})

// {drawer: amount} for the drawers in another currency, as the server takes it.
function foreignFloats() {
  const out = {}
  for (const d of foreignDrawers.value) {
    const raw = floats.value[d.mode_of_payment]
    if (raw == null || String(raw).trim() === '') continue
    const value = parseMoney(raw)
    if (value == null || value < 0) throw new Error(t('Enter a valid opening float for {drawer}.', { drawer: d.mode_of_payment }))
    if (value && value > 0) out[d.mode_of_payment] = value
  }
  return JSON.stringify(out)
}

const canOpen = computed(() => session.permissions.open_register !== false)

// Shifts this person still holds at other outlets, and whether the shop's
// "one open shift per person" setting stops this one until they are closed
// (the server refuses it too, esafepos.api.register).
const router = useRouter()
const others = computed(() => session.otherOpenRegisters || [])
const externalOpenings = computed(() => session.externalOpenings || [])
// Only a shift this person can still reach blocks; one at an outlet they
// cannot reach any more is for a manager, and never locks them out.
const anyReachable = computed(() => others.value.some((r) => r.reachable !== false))
const oneShiftBlocked = computed(() => !!session.settings?.one_shift_per_user && anyReachable.value)
async function goClose(profile) {
  await onSwitchOutlet(profile)
  router.push('/register')
}
const canClose = computed(() => session.permissions.close_register !== false)

onMounted(() => {
  if (!pending.value) floatInput.value?.focus()
  else startPoll(pending.value.session)
})
onBeforeUnmount(() => monitor.stop())

// Choose which outlet to open the register for (users assigned to more than one
// POS Profile). Switching reloads that outlet, if it's already open the dialog
// closes and you're selling on it; if closed, the dialog now opens that outlet.
async function onSwitchOutlet(name) {
  if (!name || name === session.posProfile) return
  await session.switchProfile(name)
  catalog.fetch()
  catalog.cacheFullCatalog()
  catalog.cacheCustomers()
  pending.value = session.pendingClosing
  monitor.stop()
  if (pending.value) startPoll(pending.value.session)
  openingFloat.value = '0'
  floats.value = {}
}

async function open() {
  if (busy.value || session.offline || !canOpen.value || oneShiftBlocked.value) return
  const amount = parseMoney(openingFloat.value)
  if (amount == null || amount < 0) {
    session.notify(t('Enter the opening float as a number, e.g. 1500 or 1500.50'), true)
    return
  }
  if (amount === 0 && !confirm(t('Open with an opening float of 0.00? Confirm the drawer is empty.'))) return
  busy.value = true
  try {
    // Opening is always a fresh shift, there is no resume/retry branch.
    await session.openRegister(amount, { floats: foreignFloats() })
    session.notify(t('Register opened'))
  } catch (e) {
    session.notify(e.message, true)
  } finally {
    busy.value = false
  }
}

async function forceNew() {
  if (!pending.value?.new_shift_blocked) await open()
}

async function retry() {
  if (busy.value || session.offline || !canClose.value) return
  busy.value = true
  try {
    const result = await call('esafepos.api.register.retry_closing', { session: pending.value.session })
    pending.value = { ...pending.value, closing_status: result.closing_status || 'Queued' }
    session.notify(t('Finalising the previous shift…'))
    startPoll(pending.value.session)
  } catch (e) {
    session.notify(e.message, true)
  } finally {
    busy.value = false
  }
}

const monitor = createClosingMonitor(
  name => session.offline ? Promise.reject() : call('esafepos.api.register.closing_entry_status', { session: name }),
  async (res, name) => {
    if (pending.value?.session !== name) return
    pending.value = { ...pending.value, ...res }
    session.pendingClosing = pending.value
    if (res.status !== 'Closed') return
    session.pendingClosing = null
    pending.value = null
    await session.bootstrap(session.posProfile)
    pending.value = session.pendingClosing
    session.notify(t('Previous shift closed, you can open the register now'))
    if (pending.value) startPoll(pending.value.session)
  }
)
function startPoll(name) { monitor.start(name) }
</script>

<style scoped>
/* Covers only the content area (not the nav rail) so the cashier can still
   reach Register, History and Settings while the register is closed. */
.open-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(24, 30, 44, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 30;
}
.field-label {
  display: block;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-muted);
  margin: 10px 0 6px;
}
.shift-banner {
  background: rgba(245, 166, 35, 0.12);
  border-radius: var(--radius);
  padding: 14px 16px;
  margin-bottom: 14px;
  font-weight: 600;
}
.shift-banner.warn { background: rgba(226, 48, 48, 0.12); }
.shift-name {
  font-size: 16px;
  font-weight: 800;
  margin-top: 4px;
}
.small { font-size: 12px; }
.choice-btn {
  width: 100%;
  flex-direction: column;
  gap: 2px;
  padding: 14px;
  margin-bottom: 10px;
}
.choice-hint {
  font-size: 11.5px;
  font-weight: 500;
  opacity: 0.8;
}
.dead-end { margin: 4px 0 0; }
.force-new-block { margin-top: 6px; }
.float-input { width: 100%; }
.oe-warn { text-align: start; }
.oe-item { font-weight: 800; margin-top: 4px; }
.oe-sess { font-weight: 500; opacity: 0.7; font-size: 12px; }
.oe-item { display: flex; align-items: center; flex-wrap: wrap; gap: 6px 8px; }
.oe-go {
  margin-inline-start: auto;
  font-size: 12px;
  font-weight: 700;
  color: var(--brand-dark);
  background: rgba(19, 167, 149, 0.08);
  border: 1px solid rgba(19, 167, 149, 0.3);
  border-radius: 999px;
  padding: 3px 10px;
  cursor: pointer;
}
html[data-theme='dark'] .oe-go { color: #9fc0ff; background: rgba(47, 123, 255, 0.16); }
.oe-block { border-color: var(--red); }
.oe-ask { flex-basis: 100%; font-size: 12px; font-weight: 600; opacity: 0.85; }
.outlet-select {
  width: 100%;
  padding: 11px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}
.or-sep {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 16px 0 6px;
  color: var(--text-muted);
  font-size: 11.5px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.or-sep::before,
.or-sep::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border);
}
</style>
