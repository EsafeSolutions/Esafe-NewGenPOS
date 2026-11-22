// Detect deployed builds even when the release number has not changed.
export function safeToUpdate({ session, cart, route, document, jobs = [] }) {
  if (session.offline || session.syncing || cart.submitting || cart.lines.length || cart.exchange) return false
  if (jobs.some((job) => ['preparing', 'submitting', 'printing'].includes(job.state))) return false
  if (document.querySelector('.modal-backdrop, .pay-overlay, [role="dialog"]')) return false
  const field = document.activeElement
  if (field?.matches('input, textarea, select') && field.value) return false
  if (route.path === '/display') return true
  if (!session.loaded || session.error) return false
  return Boolean((route.path === '/' && session.registerOpen) || (session.reportsOnly && route.path === '/insights'))
}

export async function prepareAppUpdate(revision, browser = window) {
  // Fetch the page outside navigation so an old worker cannot supply its
  // offline fallback as proof of a successful deploy. Validate before reloading.
  const response = await browser.fetch('/pos', { cache: 'no-store', credentials: 'same-origin' })
  if (!response.ok) throw new Error('The updated app is not ready')
  const html = await response.text()
  if (!html.includes(`window.esafepos_shell_revision = "${revision}"`)) throw new Error('The deployed app is still changing')
  const assets = await Promise.all(['pos.js', 'pos.css'].map((name) =>
    browser.fetch(`/assets/esafepos/pos/${name}?v=${encodeURIComponent(revision)}`, { cache: 'reload', credentials: 'same-origin' })
  ))
  if (assets.some((asset) => !asset.ok)) throw new Error('The updated assets are not ready')
  // A worker is optional (old Frappe versions / plain HTTP). Online navigation
  // still picks up the validated page and its revisioned assets without one.
  if (browser.navigator.serviceWorker) {
    const registration = await browser.navigator.serviceWorker.register(`/sw.js?v=${encodeURIComponent(revision)}`, {
      scope: '/pos', updateViaCache: 'none',
    }).catch(() => null)
    const worker = registration?.installing || registration?.waiting
    if (worker && worker.state !== 'activated' && worker.state !== 'redundant') {
      await new Promise((resolve) => {
        const finish = () => {
          clearTimeout(timer)
          worker.removeEventListener('statechange', changed)
          resolve()
        }
        const changed = () => { if (['activated', 'redundant'].includes(worker.state)) finish() }
        const timer = setTimeout(finish, 10000)
        worker.addEventListener('statechange', changed)
        changed()
      })
    }
  }
}

export function startAppUpdates({ currentRevision, readRevision, canReload, onPending = () => {},
  browser = window, prepare = (revision) => prepareAppUpdate(revision, browser),
  reload = () => browser.location.reload(), interval = 15000 }) {
  let stopped = false
  let checking = false
  let reloading = false
  let pending = ''
  async function check() {
    if (stopped || checking || reloading || !currentRevision || browser.navigator.onLine === false || browser.document.hidden) return
    checking = true
    try {
      const result = await readRevision()
      if (stopped || !result?.revision) return
      pending = result.revision === currentRevision ? '' : result.revision
      onPending(Boolean(pending))
      if (!pending || !canReload()) return
      await prepare(pending)
      // A cashier may have started a sale while the new shell downloaded.
      if (stopped || !canReload() || browser.navigator.onLine === false || browser.document.hidden) return
      reloading = true
      reload()
    } catch {
      // A deploy/restart or network failure is temporary. Keep the current app
      // and retry; the offline queue and draft transaction are never cleared.
    } finally {
      checking = false
    }
  }
  const timer = setInterval(check, interval)
  const events = [[browser, 'focus'], [browser, 'online'], [browser.document, 'visibilitychange']]
  events.forEach(([target, name]) => target.addEventListener(name, check))
  check()
  return { check, stop() {
    stopped = true
    clearInterval(timer)
    events.forEach(([target, name]) => target.removeEventListener(name, check))
  } }
}
