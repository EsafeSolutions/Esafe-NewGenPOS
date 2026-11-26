// Commit markers keep idle checks small; fallback reads cover SQL/import changes.
export function notifyCatalogChanged(browser = window) {
  browser.dispatchEvent(new Event('esafepos:catalog-changed'))
  try { browser.localStorage.setItem('esafepos:catalog-change', Date.now() + ':' + Math.random()) } catch { /* Private storage. */ }
}

export function startCatalogSync({ readRevision, refresh, canSync, scope, onError = () => {},
  browser = window, intervalMs = 3000, maxAgeMs = 15000 }) {
  let timer, busy = false, stopped = false, revision, lastRefresh = 0, activeScope = '', pending = false, failures = 0
  const schedule = delay => { browser.clearTimeout(timer); if (!stopped) timer = browser.setTimeout(() => check(), delay) }
  async function check(force = false) {
    if (stopped) return
    pending ||= force
    if (busy) return
    if (!canSync() || browser.document.visibilityState === 'hidden') { schedule(intervalMs); return }
    const context = scope()
    if (context !== activeScope) { activeScope = context; revision = undefined; lastRefresh = 0; pending = true }
    busy = true
    const forced = pending; pending = false
    try {
      const status = await readRevision()
      if (stopped || context !== scope()) return
      if (forced || status.direct_poll || revision !== status.revision || Date.now() - lastRefresh >= maxAgeMs) {
        const applied = await refresh()
        if (stopped || context !== scope()) return
        if (applied === false) { pending = true; return }
        lastRefresh = Date.now()
      }
      revision = status.revision; failures = 0; onError('')
    } catch (error) { failures++; pending ||= forced; onError(error.message) }
    finally {
      busy = false
      schedule(pending && !failures ? 300 : Math.min(30000, intervalMs * 2 ** Math.min(failures, 3)))
    }
  }
  const wake = () => { pending = true; if (!busy) schedule(100) }
  const storage = event => { if (event.key === 'esafepos:catalog-change') wake() }
  for (const event of ['focus', 'online', 'esafepos:catalog-changed']) browser.addEventListener(event, wake)
  browser.addEventListener('storage', storage)
  browser.document.addEventListener('visibilitychange', wake)
  schedule(100)
  return { check, stop() {
    stopped = true; browser.clearTimeout(timer)
    for (const event of ['focus', 'online', 'esafepos:catalog-changed']) browser.removeEventListener(event, wake)
    browser.removeEventListener('storage', storage)
    browser.document.removeEventListener('visibilitychange', wake)
  } }
}
