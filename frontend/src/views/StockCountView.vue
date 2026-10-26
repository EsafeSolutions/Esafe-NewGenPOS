<!-- Copyright (c) 2026 Lumen Solutions
     SPDX-License-Identifier: AGPL-3.0-only
     "LumenPOS" is a trademark of Lumen Solutions. See TRADEMARKS.md. -->
<!-- Stock count from the till (0.69.0, lumenpos.api.stock_app): scan or search, count, and
     either save the count as an ERPNext Stock Reconciliation draft (and submit it), or take
     part in a shared count with the phones of the Lumen Stock app and merge it. -->
<template>
  <div class="count">
    <section class="card main">
      <div v-if="!session.permissions.stock_count" class="muted empty">{{ t("You're not allowed to count stock here.") }}</div>
      <template v-else>
        <div class="head">
          <label class="field">
            <span>{{ t('Warehouse') }}</span>
            <select v-model="warehouse" class="cf-in" :disabled="busy || joined" data-tour="count-warehouse" @change="onWarehouse">
              <option v-for="w in setup.warehouses" :key="w" :value="w">{{ w }}</option>
            </select>
          </label>
          <div v-if="setup.shared" class="modes" role="tablist" data-tour="count-mode">
            <button type="button" :class="['mode', { on: mode === 'alone' }]" :disabled="joined" @click="setMode('alone')">{{ t('Count alone') }}</button>
            <button type="button" :class="['mode', { on: mode === 'shared' }]" @click="setMode('shared')">{{ t('Shared count') }}</button>
          </div>
        </div>

        <!-- A shared count: join one, or start one -->
        <div v-if="mode === 'shared' && !joined" class="shared-pick">
          <div class="src-title">{{ t('Open shared counts') }}</div>
          <div v-if="!sessions.length" class="muted small">{{ t('No shared count is open for this warehouse.') }}</div>
          <button v-for="s in sessions" :key="s.name" type="button" class="found-row" @click="join(s)">
            <bdi>{{ s.title || s.name }}</bdi>
            <span class="muted small"><bdi dir="ltr">{{ s.name }}</bdi> · {{ t('{n} devices', { n: s.devices }) }}<span v-if="s.full_count"> · {{ t('Full count') }}</span></span>
          </button>
          <div class="start">
            <input v-model="newTitle" class="cf-in grow" :placeholder="t('Title of the new count')" />
            <label class="check"><input v-model="newFull" type="checkbox" /> {{ t('Full count') }}</label>
            <button class="btn btn-outline" type="button" :disabled="busy" @click="startShared">{{ t('Start a shared count') }}</button>
          </div>
          <p class="muted small">{{ t('A full count sets every item with stock that nobody counted to zero when the count is merged.') }}</p>
        </div>
        <div v-if="joined" class="joined">
          <div>
            <b><bdi>{{ joined.title || joined.name }}</bdi></b>
            <span class="muted small after"><bdi dir="ltr">{{ joined.name }}</bdi><span v-if="joined.full_count"> · {{ t('Full count') }}</span></span>
          </div>
          <div class="muted small">
            {{ t('{n} devices', { n: status.devices ? status.devices.length : 0 }) }} · {{ t('{n} items', { n: status.items || 0 }) }}
            <span v-if="lastSent"> · {{ t('Sent at {time}', { time: lastSent }) }}</span>
          </div>
        </div>

        <template v-if="mode === 'alone' || joined">
          <div class="add-row">
            <div class="search-box" data-tour="count-scan">
              <Icon name="barcode" />
              <input
                ref="scanInput"
                v-model="query"
                :placeholder="t('Scan a barcode or a serial number, or search for an item…')"
                @input="debouncedSearch"
                @keydown.enter.prevent="scan"
              />
            </div>
          </div>
          <div v-if="found.length" class="found">
            <button v-for="item in found" :key="item.item_code" type="button" class="found-row" @click="pick(item)">
              <bdi>{{ item.item_name }}</bdi>
              <span class="muted small" dir="ltr">{{ item.item_code }}</span>
            </button>
          </div>
          <div v-if="waitingSerial" class="note small">{{ t('{item} is counted by serial number: scan each serial number.', { item: waitingSerial }) }}</div>
          <div v-if="error" class="neg small err">{{ error }}</div>
          <div v-if="info" class="ok small err">{{ info }}</div>

          <div v-if="!lines.length" class="muted empty">{{ t('Scan or search to count the first item.') }}</div>
          <div v-else class="wrap">
            <table class="rt">
              <thead>
                <tr>
                  <th>{{ t('Item') }}</th>
                  <th v-if="!setup.blind" class="num">{{ t('On the shelf') }}</th>
                  <th class="num">{{ t('Counted') }}</th>
                  <th v-if="!setup.blind" class="num">{{ t('Difference') }}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in lines" :key="row.item_code">
                  <td>
                    <div><bdi>{{ row.item_name }}</bdi></div>
                    <div class="muted small" dir="ltr">{{ row.item_code }}</div>
                    <div v-if="row.serials.length" class="muted small" dir="ltr">{{ row.serials.join(', ') }}</div>
                  </td>
                  <td v-if="!setup.blind" class="num">{{ qtyText(row.shelf) }}</td>
                  <td class="num">
                    <span v-if="row.has_serial_no">{{ row.serials.length }}</span>
                    <input v-else v-model.number="row.qty" type="number" min="0" step="any" class="qty" @change="persist" />
                  </td>
                  <td v-if="!setup.blind" :class="['num', diffClass(row)]">{{ diffText(row) }}</td>
                  <td><button class="btn-ghost" type="button" :title="t('Remove')" @click="remove(row)"><Icon name="close" /></button></td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="actions" data-tour="count-actions">
            <template v-if="mode === 'alone'">
              <label class="check"><input v-model="zeroUncounted" type="checkbox" /> {{ t('Full count: set what was not counted to zero') }}</label>
              <button class="btn btn-primary" type="button" :disabled="busy || !lines.length" @click="saveAlone">
                <Icon name="check" /> {{ recoName ? t('Save the count again') : t('Save the count') }}
              </button>
            </template>
            <template v-else>
              <button class="btn btn-primary" type="button" :disabled="busy" @click="send">
                <Icon name="upload" /> {{ t('Send my count') }}
              </button>
              <button class="btn btn-outline" type="button" :disabled="busy" @click="refreshStatus"><Icon name="refresh" /> {{ t('Refresh') }}</button>
              <button class="btn btn-outline" type="button" :disabled="busy" @click="merge">{{ t('Merge into a stock count') }}</button>
              <button class="btn-ghost danger" type="button" :disabled="busy" @click="closeShared">{{ t('Close the shared count') }}</button>
              <button class="btn-ghost" type="button" :disabled="busy" @click="leave">{{ t('Leave') }}</button>
            </template>
          </div>
          <div v-if="recoName" class="saved">
            <div>{{ t('Saved as a draft stock count: {name}', { name: recoName }) }}</div>
            <div class="row">
              <button v-for="a in actions" :key="a.action" class="btn btn-outline" type="button" :disabled="busy" @click="submit(a.action)">
                {{ a.action === 'Submit' ? t('Submit') : a.action }}
              </button>
              <span v-if="!actions.length" class="muted small">{{ t('Someone allowed to submit it can do so in ERPNext.') }}</span>
            </div>
          </div>
        </template>
      </template>
    </section>

    <aside class="card side">
      <div class="side-body">
        <div class="src-title">{{ t('Lumen Stock app') }}</div>
        <p class="muted small">{{ t('Count with phones too: install the Lumen Stock app on Android phones or handheld scanners and sign in with your ERPNext account.') }}</p>
        <a class="btn btn-outline dl" :href="setup.downloads.phone" target="_blank" rel="noopener"><Icon name="download" /> {{ t('Download for phones') }}</a>
        <a class="btn btn-outline dl" :href="setup.downloads.handheld" target="_blank" rel="noopener"><Icon name="download" /> {{ t('Download for handheld scanners') }}</a>
        <p class="muted small">{{ t('A count is checked against what is on the shelf: sales of an open shift leave the stock only when the shift is closed, so close the shifts before you save or merge a count.') }}</p>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { call } from '../api'
import { t } from '../i18n'
import { useSessionStore } from '../stores/session'
import Icon from '../components/Icon.vue'

const session = useSessionStore()
const STORE_KEY = 'lumenpos-count'
const DEVICE_KEY = 'lumenpos-count-device'
const DOWNLOADS = {
  phone: 'https://lumen-solutions.co/downloads/LumenStock.apk',
  handheld: 'https://lumen-solutions.co/downloads/LumenStock-handheld.apk',
}

const setup = ref({ warehouses: [], blind: 0, shared: 0, submit: 0, downloads: DOWNLOADS })
const warehouse = ref('')
const mode = ref('alone')
const lines = ref([])
const query = ref('')
const found = ref([])
const scanInput = ref(null)
const busy = ref(false)
const error = ref('')
const info = ref('')
const waitingSerial = ref('')
const recoName = ref('')
const actions = ref([])
const zeroUncounted = ref(false)
const sessions = ref([])
const joined = ref(null)
const status = ref({})
const lastSent = ref('')
const newTitle = ref('')
const newFull = ref(false)
let dirty = false
let timer = null

// The device keeps its count, a convenience only: the count itself is saved in ERPNext.
function stored() {
  try {
    return JSON.parse(localStorage.getItem(STORE_KEY) || 'null') || {}
  } catch {
    return {}
  }
}
function persist() {
  dirty = true
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify({
      warehouse: warehouse.value, mode: mode.value, lines: lines.value, recoName: recoName.value,
      joined: joined.value, profile: session.posProfile,
    }))
  } catch {
    /* private window: the count lives on the screen only */
  }
}
function deviceId() {
  try {
    let id = localStorage.getItem(DEVICE_KEY)
    if (!id) {
      id = 'till-' + Math.random().toString(36).slice(2, 10)
      localStorage.setItem(DEVICE_KEY, id)
    }
    return id
  } catch {
    return 'till-' + (session.posProfile || 'pos')
  }
}

const qtyText = (n) => (n === null || n === undefined ? '' : String(Math.round(Number(n) * 1000) / 1000))
function counted(row) {
  return row.has_serial_no ? row.serials.length : Number(row.qty) || 0
}
function diffText(row) {
  if (row.shelf === null || row.shelf === undefined) return ''
  const d = Math.round((counted(row) - Number(row.shelf)) * 1000) / 1000
  return d > 0 ? '+' + d : String(d)
}
function diffClass(row) {
  const d = counted(row) - Number(row.shelf || 0)
  return d > 0 ? 'pos' : d < 0 ? 'neg' : ''
}

async function run(fn) {
  error.value = ''
  info.value = ''
  busy.value = true
  try {
    await fn()
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    busy.value = false
  }
}

function addItem(item, serial) {
  let row = lines.value.find((r) => r.item_code === item.item_code)
  if (!row) {
    row = { item_code: item.item_code, item_name: item.item_name, has_serial_no: item.has_serial_no, shelf: item.shelf, qty: 0, serials: [] }
    lines.value.unshift(row)
  }
  if (item.has_serial_no) {
    if (!serial) {
      waitingSerial.value = item.item_name
      return
    }
    if (row.serials.includes(serial)) {
      error.value = t('Serial number {serial} is already counted.', { serial })
      return
    }
    row.serials.push(serial)
    waitingSerial.value = ''
  } else {
    row.qty = (Number(row.qty) || 0) + 1
  }
  info.value = item.item_name + ' · ' + counted(row)
  persist()
}

async function scan() {
  const code = query.value.trim()
  if (!code) return
  clearTimeout(searchTimer)
  await run(async () => {
    const hit = await call('lumenpos.api.stock_app.count_lookup', { warehouse: warehouse.value, code })
    if (hit && hit.found) {
      addItem(hit, hit.serial_no || null)
      if (hit.needs_serial) waitingSerial.value = hit.item_name
      query.value = ''
      found.value = []
    } else {
      await search()
      if (!found.value.length) error.value = (hit && hit.reason) || t('No item matches {query}.', { query: code })
    }
  })
  scanInput.value?.focus()
}

let searchTimer = null
function debouncedSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(search, 300)
}
async function search() {
  const text = query.value.trim()
  if (text.length < 2) {
    found.value = []
    return
  }
  try {
    found.value = await call('lumenpos.api.stock_app.count_search', { warehouse: warehouse.value, text })
  } catch {
    found.value = []
  }
}
function pick(item) {
  addItem(item, null)
  found.value = []
  query.value = ''
  scanInput.value?.focus()
}
function remove(row) {
  lines.value = lines.value.filter((r) => r !== row)
  persist()
}

function payload() {
  return lines.value.map((r) => ({ item_code: r.item_code, qty: counted(r), serials: r.serials }))
}

async function saveAlone() {
  await run(async () => {
    const res = await call('lumenpos.api.stock_app.count_save', {
      pos_profile: session.posProfile, warehouse: warehouse.value, lines: JSON.stringify(payload()),
      name: recoName.value || null, zero_uncounted: zeroUncounted.value ? 1 : 0,
    })
    recoName.value = res.name
    info.value = t('Differences put into the count: {n}. Matching the shelf: {m}.', { n: res.rows, m: res.unchanged })
    persist()
    await loadActions()
  })
}
async function loadActions() {
  actions.value = []
  if (!recoName.value || !setup.value.submit) return
  const res = await call('lumenpos.api.stock_app.stock_actions', { doctype: 'Stock Reconciliation', name: recoName.value })
  actions.value = res.actions || []
}
async function submit(action) {
  if (!confirm(t('Submit the stock count {name}? The stock is set to the counted quantities.', { name: recoName.value }))) return
  await run(async () => {
    await call('lumenpos.api.stock_app.stock_submit', { doctype: 'Stock Reconciliation', name: recoName.value, action })
    info.value = t('Stock count {name} is submitted.', { name: recoName.value })
    recoName.value = ''
    actions.value = []
    lines.value = []
    persist()
  })
}

// Shared counts
async function loadSessions() {
  if (mode.value !== 'shared' || !warehouse.value) return
  try {
    sessions.value = await call('lumenpos.api.stock_app.count_sessions', { warehouse: warehouse.value })
  } catch (e) {
    sessions.value = []
    error.value = e.message || String(e)
  }
}
async function startShared() {
  await run(async () => {
    const s = await call('lumenpos.api.stock_app.count_session_open', {
      warehouse: warehouse.value, title: newTitle.value || null, full_count: newFull.value ? 1 : 0,
    })
    newTitle.value = ''
    newFull.value = false
    await join(s)
  })
}
async function join(s) {
  joined.value = { name: s.name, title: s.title, full_count: s.full_count }
  if (!lines.value.length) {
    // this till's own lines, if it sent some before (the count was reopened)
    try {
      const own = await call('lumenpos.api.stock_app.count_session_device', { session: s.name, device_id: deviceId() })
      for (const [code, v] of Object.entries(own.data || {})) {
        lines.value.push({ item_code: code, item_name: code, has_serial_no: (v.s || []).length ? 1 : 0, shelf: null, qty: v.q || 0, serials: v.s || [] })
      }
    } catch {
      /* nothing sent before */
    }
  }
  persist()
  await refreshStatus()
}
async function send() {
  if (!joined.value) return
  await run(async () => {
    const data = {}
    for (const r of lines.value) data[r.item_code] = r.serials.length ? { q: r.serials.length, s: r.serials } : { q: Number(r.qty) || 0 }
    const label = (session.posProfile || 'LumenPOS') + (session.userFullname ? ' · ' + session.userFullname : '')
    const res = await call('lumenpos.api.stock_app.count_session_push', {
      session: joined.value.name, device_id: deviceId(), device_label: label, data: JSON.stringify(data),
    })
    lastSent.value = String(res.last_sync || '').slice(11, 16)
    dirty = false
    await refreshStatus()
  })
}
async function refreshStatus() {
  if (!joined.value) return
  try {
    status.value = await call('lumenpos.api.stock_app.count_session_status', { session: joined.value.name })
  } catch (e) {
    error.value = e.message || String(e)
  }
}
async function merge() {
  if (!confirm(t('Merge every device of {name} into one stock count draft? Send your own count first.', { name: joined.value.title || joined.value.name }))) return
  await run(async () => {
    const res = await call('lumenpos.api.stock_app.count_session_merge', { session: joined.value.name })
    recoName.value = res.reconciliation
    joined.value = null
    lines.value = []
    mode.value = 'alone'
    info.value = t('Differences put into the count: {n}. Matching the shelf: {m}.', { n: res.rows, m: res.unchanged })
    persist()
    await loadActions()
  })
}
async function closeShared() {
  if (!confirm(t('Close {name} without making a stock count?', { name: joined.value.title || joined.value.name }))) return
  await run(async () => {
    await call('lumenpos.api.stock_app.count_session_close', { session: joined.value.name })
    leave()
  })
}
function leave() {
  joined.value = null
  status.value = {}
  lines.value = []
  persist()
  loadSessions()
}

function setMode(m) {
  mode.value = m
  persist()
  loadSessions()
}
function onWarehouse() {
  lines.value = []
  recoName.value = ''
  actions.value = []
  persist()
  loadSessions()
}

onMounted(async () => {
  if (!session.permissions.stock_count) return
  await run(async () => {
    const res = await call('lumenpos.api.stock_app.count_setup', { pos_profile: session.posProfile })
    setup.value = { ...res, downloads: res.downloads || DOWNLOADS }
    const keep = stored()
    const same = keep.profile === session.posProfile && res.warehouses.includes(keep.warehouse)
    warehouse.value = same ? keep.warehouse : res.warehouse
    if (same) {
      lines.value = keep.lines || []
      recoName.value = keep.recoName || ''
      mode.value = res.shared && keep.mode === 'shared' ? 'shared' : 'alone'
      joined.value = res.shared ? keep.joined || null : null
    }
  })
  await loadSessions()
  if (joined.value) await refreshStatus()
  if (recoName.value) await loadActions().catch(() => {})
  // a shared count sends this till's lines every minute while they change
  timer = setInterval(() => {
    if (joined.value && dirty && !busy.value) send()
  }, 60000)
  scanInput.value?.focus()
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.count { flex: 1; min-width: 0; display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(260px, 1fr); gap: 14px; padding: 14px; overflow: auto; align-items: start }
.main, .side { padding: 0; overflow: hidden }
.head { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end; padding: 12px 14px }
.field { display: flex; flex-direction: column; gap: 5px; font-size: 13px; min-width: 0; flex: 1 }
.field > span { font-weight: 600; color: var(--text-muted); font-size: 12.5px }
.modes { display: flex; border: 1px solid var(--border); border-radius: 8px; overflow: hidden }
.mode { background: transparent; border: 0; padding: 8px 12px; font: inherit; color: var(--text); cursor: pointer }
.mode.on { background: var(--accent, #1463ff); color: #fff }
.mode:disabled { opacity: 0.5; cursor: default }
.shared-pick, .joined { padding: 0 14px 12px; display: flex; flex-direction: column; gap: 8px }
.joined { flex-direction: row; justify-content: space-between; flex-wrap: wrap; align-items: baseline }
.after { margin-inline-start: 8px }
.start { display: flex; flex-wrap: wrap; gap: 8px; align-items: center }
.src-title { font-size: 12.5px; font-weight: 700; color: var(--text-muted) }
.add-row { padding: 0 14px }
.search-box { display: flex; align-items: center; gap: 6px; border: 1px solid var(--border); border-radius: 8px; padding: 0 9px; background: var(--card-bg) }
.search-box :deep(svg) { width: 16px; height: 16px; color: var(--text-muted) }
.search-box input { flex: 1; border: 0; padding: 10px 0; font: inherit; background: transparent; color: var(--text); outline: none; min-width: 0 }
.found { margin: 6px 14px 0; border: 1px solid var(--border); border-radius: 8px; max-height: 240px; overflow: auto }
.found-row { width: 100%; display: flex; justify-content: space-between; gap: 10px; padding: 8px 10px; background: transparent; border: 1px solid var(--border); border-radius: 8px; text-align: start; font: inherit; color: var(--text); cursor: pointer }
.found .found-row { border: 0; border-bottom: 1px solid var(--border); border-radius: 0 }
.found .found-row:last-child { border-bottom: 0 }
.found-row:hover { background: var(--surface-2) }
.grow { flex: 1; min-width: 0 }
.check { display: flex; align-items: center; gap: 7px; font-size: 13px }
.note { margin: 8px 14px 0; padding: 8px 10px; border-radius: 8px; background: var(--surface-2) }
.err { padding: 8px 14px 0 }
.neg { color: var(--danger, #d33) }
.pos { color: var(--accent, #1463ff) }
.ok { color: var(--success, #1a7f37) }
.empty { padding: 26px; text-align: center }
.wrap { overflow-x: auto; border-top: 1px solid var(--border); margin-top: 12px }
.rt { width: 100%; border-collapse: collapse; font-size: 13.5px }
.rt th, .rt td { padding: 8px 12px; border-bottom: 1px solid var(--border); text-align: start; vertical-align: top }
.rt th { font-size: 12px; color: var(--text-muted); font-weight: 600 }
.rt .num { text-align: end; white-space: nowrap }
.qty { width: 80px; padding: 5px 6px; border: 1px solid var(--border); border-radius: 6px; background: var(--card-bg); color: var(--text); font: inherit; text-align: end }
.actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding: 12px 14px }
.actions .check { margin-inline-end: auto }
.danger { color: var(--danger, #d33) }
.saved { margin: 0 14px 14px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; display: flex; flex-direction: column; gap: 8px }
.saved .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center }
.side-body { display: flex; flex-direction: column; gap: 10px; padding: 14px }
.dl { justify-content: center; text-decoration: none }
.small { font-size: 12px }
@media (max-width: 900px) {
  .count { grid-template-columns: 1fr }
}
@media (max-width: 520px) {
  .count { padding: 8px; gap: 10px }
  .head { flex-direction: column; align-items: stretch }
  .modes .mode { flex: 1 }
  .rt th, .rt td { padding: 7px 5px }
  .rt th.num { white-space: normal }
  .rt td:first-child { min-width: 110px; overflow-wrap: anywhere }
  .qty { width: 56px; padding: 5px 4px }
}
</style>
