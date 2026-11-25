/* Copyright (c) 2026 Esafe (PVT) LTD
   SPDX-License-Identifier: AGPL-3.0-only
   "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.

   The shell stays on this device; business data and the durable sales queue
   remain in IndexedDB. New workers wait for the operator's update agreement.
   A tab's ?v= revision keeps it on its agreed shell even when another tab
   activates an update. Never cache API responses or the ERPNext desk.
*/
const VERSION = new URL(self.location.href).searchParams.get('v') || 'dev'
const PREFIX = 'esafepos-shell-'
const CACHE = PREFIX + VERSION
const PAGE = '/pos'
const ASSETS = '/assets/esafepos/pos/'
const FONT_HOSTS = ['fonts.googleapis.com', 'fonts.gstatic.com']
const PAGE_TIMEOUT = 8000

async function fetchShell(url, timeout = 60000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  try {
    const response = await fetch(url, { cache: 'no-store', credentials: 'same-origin', signal: controller.signal })
    if (!response.ok || response.redirected) throw new Error('Offline shell unavailable: ' + url)
    const path = new URL(url, self.location.origin).pathname
    const mime = response.headers.get('Content-Type') || ''
    if ((path.endsWith('.js') && !/javascript|ecmascript/i.test(mime)) ||
        (path.endsWith('.css') && !/text\/css/i.test(mime))) throw new Error('Invalid offline asset: ' + url)
    // Consume each download now. Unread large response streams can exhaust
    // browser connections while the remaining files wait for headers.
    const body = await response.arrayBuffer()
    const headers = new Headers(response.headers)
    headers.delete('Content-Encoding')
    headers.delete('Content-Length')
    return new Response(body, { headers })
  } finally {
    clearTimeout(timer)
  }
}

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE)
    // Stage the complete build before changing anything in the cached shell.
    // A failed deployment must leave the last working shell intact.
    const page = await fetchShell(PAGE)
    if (!(await page.clone().text()).includes('window.esafepos_shell_revision = "' + VERSION + '"')) {
      throw new Error('The deployed shell revision changed during installation')
    }
    const manifest = await fetchShell(ASSETS + 'offline-assets.json?v=' + encodeURIComponent(VERSION))
    const files = await manifest.json()
    if (!Array.isArray(files) || !files.includes('pos.js') || !files.includes('pos.css') ||
        files.some((name) => typeof name !== 'string' || !/^[\w./-]+$/.test(name) || name.includes('..') || name.startsWith('/'))) {
      throw new Error('Invalid offline asset manifest')
    }
    const urls = files.map((name) => ASSETS + name + (['pos.js', 'pos.css'].includes(name) ? '?v=' + encodeURIComponent(VERSION) : ''))
    const responses = await Promise.all(urls.map((url) => fetchShell(url)))
    await Promise.all(urls.map((url, index) => cache.put(url, responses[index])))
    await cache.put(PAGE, page)
    // Icons/installation metadata must not block a usable checkout shell.
    await Promise.all(['manifest.json', 'pos-icon.svg', 'pos-icon-192.png', 'pos-icon-512.png'].map(async (name) => {
      try { await cache.put(ASSETS + name, await fetchShell(ASSETS + name)) } catch { /* optional */ }
    }))
  })())
})

self.addEventListener('message', (event) => {
  if (event.data?.type === 'esafepos-activate-update') event.waitUntil(self.skipWaiting())
})

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const names = (await caches.keys()).filter((name) => name.startsWith(PREFIX))
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    // Keep every open till's build and the previous shell for recovery. Older
    // unused builds can go only after a successful replacement is installed.
    const keep = new Set([CACHE, names.filter((name) => name !== CACHE).pop()])
    for (const client of windows) {
      const revision = new URL(client.url).searchParams.get('v')
      if (revision) keep.add(PREFIX + revision)
    }
    await Promise.all(names.filter((name) => !keep.has(name)).map((name) => caches.delete(name)))
    await self.clients.claim()
  })())
})

function requestedCache(request) {
  const url = new URL(request.url)
  let revision = url.searchParams.get('v')
  if (!revision && request.referrer) {
    try { revision = new URL(request.referrer).searchParams.get('v') } catch { /* no referrer */ }
  }
  return revision ? PREFIX + revision : CACHE
}

async function cacheFirst(request) {
  const cache = await caches.open(requestedCache(request))
  const hit = await cache.match(request)
  if (hit) return hit
  const response = await fetch(request)
  if (response && (response.ok || response.type === 'opaque')) await cache.put(request, response.clone()).catch(() => {})
  return response
}

async function cachedPage(request) {
  const cache = await caches.open(requestedCache(request))
  const hit = await cache.match(PAGE)
  if (hit) return hit
  // An uncached first visit still needs the server. Do not hang indefinitely
  // or replace a cached working shell with a login/maintenance/error page.
  try {
    return await fetchShell(request.url, PAGE_TIMEOUT)
  } catch { /* use the installed shell */ }
  const fallback = await (await caches.open(CACHE)).match(PAGE)
  return fallback || new Response('Connect once to prepare this POS for offline use.', { status: 503, headers: { 'Content-Type': 'text/plain' } })
}

self.addEventListener('fetch', (event) => {
  const request = event.request
  if (request.method !== 'GET') return
  const url = new URL(request.url)
  const sameOrigin = url.origin === self.location.origin
  if (request.mode === 'navigate') {
    if (sameOrigin && (url.pathname === PAGE || url.pathname.startsWith(PAGE + '/'))) event.respondWith(cachedPage(request))
    return
  }
  if (request.cache === 'no-store') return
  if ((sameOrigin && url.pathname.startsWith(ASSETS)) || FONT_HOSTS.includes(url.hostname)) event.respondWith(cacheFirst(request))
})

// --- sending the queue in the background (0.56.0) ----------------------------
// A till that queued sales (or returns) without a connection asks for a
// Background Sync (offline.requestBackgroundUpload). The browser fires it as
// soon as it has a network, even when no till tab is open any more (Chrome,
// Edge, Android), and this sends the queue the way the till does
// (stores/session._sendQueue): in order, each with its idempotency key, so
// nothing can post twice. The till and this take turns through one Web Lock.
// An entry the server refuses stays queued with its reason, for the till's
// offline log. A request that fails leaves the rest for the next attempt,
// which the browser schedules itself.

const DB_NAME = 'esafepos'
const SYNC_TAG = 'esafepos-queue'
const UPLOAD_LOCK = 'esafepos-queue-upload'
// The session is the till's problem, not a refusal: leave the entry queued.
const SESSION_ERRORS = ['CSRFTokenError', 'SessionExpired', 'AuthenticationError']

self.addEventListener('sync', (event) => {
  if (event.tag !== SYNC_TAG) return
  event.waitUntil(withUploadLock(sendQueue))
})

function withUploadLock(fn) {
  if (self.navigator && navigator.locks && navigator.locks.request) {
    return navigator.locks.request(UPLOAD_LOCK, fn)
  }
  return fn()
}

function idb(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

// The till's own database, never created or upgraded from here.
async function openTillDb() {
  if (indexedDB.databases) {
    const known = await indexedDB.databases().catch(() => null)
    if (known && !known.some((d) => d.name === DB_NAME)) return null
  }
  return new Promise((resolve) => {
    let request
    try {
      request = indexedDB.open(DB_NAME)
    } catch (e) {
      resolve(null)
      return
    }
    request.onsuccess = () => {
      const db = request.result
      db.onversionchange = () => db.close() // the till is moving to a newer version
      resolve(db)
    }
    request.onerror = () => resolve(null)
  })
}

function read(db, store, key) {
  if (!db.objectStoreNames.contains(store)) return Promise.resolve(null)
  return idb(db.transaction(store).objectStore(store).get(key)).catch(() => null)
}

function patchRow(db, store, key, patch) {
  return new Promise((resolve) => {
    if (!key || !db.objectStoreNames.contains(store)) return resolve()
    const tx = db.transaction(store, 'readwrite')
    const rows = tx.objectStore(store)
    const current = rows.get(key)
    current.onsuccess = () => {
      if (current.result) rows.put(Object.assign({}, current.result, patch))
    }
    tx.oncomplete = () => resolve()
    tx.onerror = () => resolve()
  })
}

function removeQueued(db, localId) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction('queue', 'readwrite')
    tx.objectStore('queue').delete(localId)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

// A fresh CSRF token from the page itself, as the till does after an outage
// (api.refreshCsrfToken). None means nobody is signed in: leave it all.
async function csrfToken() {
  const response = await fetch(PAGE, { cache: 'no-store', credentials: 'same-origin' })
  const found = (await response.text()).match(/csrf_token\s*=\s*"([^"]+)"/)
  return found && found[1] !== 'None' ? found[1] : null
}

function plain(text) {
  return String(text || '')
    .replace(/<[^>]*>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, '&')
}

// The server's reason, as api.extractMessage reads it.
function reasonOf(data, status) {
  try {
    if (data._server_messages) {
      return JSON.parse(data._server_messages)
        .map((m) => {
          try {
            return plain(JSON.parse(m).message)
          } catch (e) {
            return plain(m)
          }
        })
        .join('\n')
    }
    if (data.exception) {
      const parts = String(data.exception).split(':')
      return parts.slice(1).join(':').trim() || String(data.exception)
    }
  } catch (e) {
    /* fall through */
  }
  return 'Request failed (' + status + ')'
}

// A network failure throws, which fails the sync and makes the browser retry.
async function post(method, body, csrf, lang, workstation) {
  const response = await fetch('/api/method/' + method, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      'X-Frappe-CSRF-Token': csrf,
      'X-ESAFEPOS-Workstation': workstation || '',
    },
    body: JSON.stringify(Object.assign({}, body, lang ? { _lang: lang } : {})),
  })
  let data = {}
  try {
    data = (await response.json()) || {}
  } catch (e) {
    /* not JSON */
  }
  if (response.status >= 500 && !data.exc_type && !data._server_messages && !data.exception) {
    throw new Error('The server is temporarily unavailable')
  }
  return { ok: response.ok, status: response.status, data }
}

async function sendQueue() {
  const db = await openTillDb()
  if (!db) return
  const report = { type: 'esafepos-queue', synced: 0, failed: 0, stock: {} }
  try {
    if (!db.objectStoreNames.contains('queue')) return
    // The shop switched background sending off: the till sends it when open.
    const boot = await read(db, 'kv', 'bootstrap')
    const workstation = await read(db, 'kv', 'shift-workstation')
    if (boot && boot.settings && Number(boot.settings.background_upload) === 0) return
    const entries = await idb(db.transaction('queue').objectStore('queue').getAll())
    if (!entries.length) return
    const csrf = await csrfToken()
    if (!csrf) return
    const customers = {} // a customer made offline -> the real one
    for (const entry of entries) {
      const payload = entry.payload || {}
      const key = payload.idempotency_key
      const isReturn = entry.kind === 'return'
      let body = isReturn ? payload : { payload }
      let answer = null
      const local = !isReturn && typeof payload.customer === 'string' && payload.customer.indexOf('__local__') === 0
      if (local && !customers[payload.customer]) {
        const pending = await read(db, 'pending_customers', payload.customer)
        answer = pending
          ? await post('esafepos.api.catalog.resolve_pending_customer', { payload: pending.payload }, csrf, entry.lang, workstation)
          : { ok: false, status: 0, data: { exception: 'x: offline customer record is missing' } }
        if (answer.ok) customers[payload.customer] = answer.data.message && answer.data.message.name
      }
      if (local && customers[payload.customer]) {
        body = { payload: Object.assign({}, payload, { customer: customers[payload.customer] }) }
      }
      if (!local || customers[payload.customer]) {
        answer = await post(
          isReturn ? 'esafepos.api.sales.create_return' : 'esafepos.api.sales.submit_sale',
          body,
          csrf,
          entry.lang,
          workstation
        )
      }
      if (answer.ok) {
        const receipt = answer.data.message || {}
        await removeQueued(db, entry.local_id)
        await patchRow(db, 'sale_log', key, {
          status: 'synced',
          receipt: receipt.name || null,
          synced_at: new Date().toISOString(),
          error: null,
          gap: receipt.offline_gap || 0,
        })
        // The till folds the receipt into the sale it keeps for a return
        // without a connection (session.loadShiftSales).
        if (!isReturn) {
          await patchRow(db, 'shift_sales', key, { name: receipt.name || null, queued: false, posted_receipt: receipt })
        }
        Object.assign(report.stock, receipt.stock_after || {})
        report.synced += 1
      } else if (answer.status === 401 || SESSION_ERRORS.includes(answer.data && answer.data.exc_type)) {
        return
      } else {
        await patchRow(db, 'sale_log', key, {
          status: 'failed',
          error: reasonOf(answer.data || {}, answer.status),
          error_at: new Date().toISOString(),
        })
        report.failed += 1
      }
    }
  } finally {
    db.close()
    if (report.synced || report.failed) {
      const tills = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      for (const till of tills) till.postMessage(report)
    }
  }
}
