// A deployment is offered to the operator; detecting it never reloads a till.
export function safeToUpdate({ session, cart, route, document, jobs = [] }) {
  if (session.offline || session.syncing || session.locked || cart.submitting || cart.lines.length || cart.exchange) return false
  if (jobs.some((job) => ['preparing', 'submitting', 'printing'].includes(job.state))) return false
  if (document.querySelector('.modal-backdrop, .pay-overlay, [role="dialog"], dialog[open]')) return false
  if (document.querySelector('[data-b2b-dirty="true"]')) return false
  const field = document.activeElement
  if (field?.matches('input, textarea, select') && field.value) return false
  if (route.path === '/display') return false
  if (!session.loaded || session.error) return false
  return Boolean((route.path === '/' && session.registerOpen) || (session.reportsOnly && route.path === '/insights'))
}

function waitForWorker(worker, states) {
  return new Promise((resolve, reject) => {
    const finish = (error) => {
      clearTimeout(timer)
      worker.removeEventListener('statechange', changed)
      error ? reject(error) : resolve()
    }
    const changed = () => {
      if (worker.state === 'redundant') finish(new Error('The updated app could not be saved offline'))
      else if (states.includes(worker.state)) finish()
    }
    const timer = setTimeout(() => finish(new Error('The updated app is still downloading. Try again.')), 60000)
    worker.addEventListener('statechange', changed)
    changed()
  })
}

async function downloadUpdate(url, format, browser) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 60000)
  try {
    const response = await browser.fetch(url, { cache: 'no-store', credentials: 'same-origin', signal: controller.signal })
    if (!response.ok || response.redirected) throw new Error('The updated app is not ready. Try again shortly.')
    if (format === 'arrayBuffer') {
      const mime = response.headers.get('Content-Type') || ''
      const expected = url.includes('/pos.js?') ? /javascript|ecmascript/i : /text\/css/i
      if (!expected.test(mime)) throw new Error('The updated assets are not ready. Try again shortly.')
    }
    return await response[format]()
  } finally {
    clearTimeout(timer)
  }
}

export async function prepareAppUpdate(revision, browser = window) {
  const html = await downloadUpdate('/pos', 'text', browser)
  if (!html.includes(`window.esafepos_shell_revision = "${revision}"`)) throw new Error('The deployed app is still changing. Try again shortly.')
  await Promise.all(['pos.js', 'pos.css'].map((name) =>
    downloadUpdate(`/assets/esafepos/pos/${name}?v=${encodeURIComponent(revision)}`, 'arrayBuffer', browser)))
  const serviceWorker = browser.navigator.serviceWorker
  if (!serviceWorker) return null
  // If a worker already protects this till, a failed replacement must preserve
  // it and refuse the reload. Older sites/plain HTTP can still update online.
  let registration
  try {
    registration = await serviceWorker.register(`/sw.js?v=${encodeURIComponent(revision)}`, {
      scope: '/pos', updateViaCache: 'none',
    })
  } catch (error) {
    if (serviceWorker.controller) throw error
    return null
  }
  const worker = registration.installing || registration.waiting || registration.active
  if (!worker || new URL(worker.scriptURL).searchParams.get('v') !== revision) {
    throw new Error('The updated app is still downloading. Try again.')
  }
  await waitForWorker(worker, ['installed', 'activated'])
  // Activation is separate: the basket may have changed during the download.
  return async () => {
    if (worker.state === 'activated') return
    const activated = waitForWorker(worker, ['activated'])
    worker.postMessage({ type: 'esafepos-activate-update' })
    await activated
  }
}

export function startAppUpdates({ currentRevision, readRevision, canReload, onPending = () => {},
  onState = () => {}, browser = window, prepare = (revision) => prepareAppUpdate(revision, browser),
  reload = (revision) => {
    const url = new URL(browser.location.href)
    url.searchParams.set('v', revision)
    browser.location.replace(url.href)
  }, interval = 15000 }) {
  let stopped = false
  let checking = false
  let applying = false
  let reloading = false
  let pending = ''
  const available = () => !stopped && !reloading && browser.navigator.onLine !== false && !browser.document.hidden
  async function check() {
    if (!available() || checking || applying || !currentRevision) return
    checking = true
    try {
      const result = await readRevision()
      if (stopped || !result?.revision) return
      pending = result.revision === currentRevision ? '' : result.revision
      onPending(pending)
    } catch {
      // Keep the current app and offer when the server returns.
    } finally {
      checking = false
    }
  }
  async function apply() {
    if (applying || !available() || !pending) return false
    if (!canReload()) {
      onState({ busy: false, error: 'Finish your current task and return to Sell before updating.' })
      return false
    }
    applying = true
    onState({ busy: true, error: '' })
    const approved = pending
    try {
      const latest = await readRevision()
      if (latest?.revision !== approved) {
        pending = latest?.revision === currentRevision ? '' : (latest?.revision || pending)
        onPending(pending)
        throw new Error('The available update changed. Review and agree again.')
      }
      const activate = await prepare(approved)
      if (!available() || !canReload()) throw new Error('Finish your current task and return to Sell before updating.')
      if (activate) await activate()
      if (!available() || !canReload()) throw new Error('Finish your current task and return to Sell before updating.')
      reloading = true
      reload(approved)
      return true
    } catch (error) {
      onState({ busy: false, error: error.message || 'The update could not be applied. Try again.' })
      return false
    } finally {
      applying = false
      if (reloading) onState({ busy: true, error: '' })
    }
  }
  const timer = setInterval(check, interval)
  const events = [[browser, 'focus'], [browser, 'online'], [browser.document, 'visibilitychange']]
  events.forEach(([target, name]) => target.addEventListener(name, check))
  check()
  return { check, apply, stop() {
    stopped = true
    clearInterval(timer)
    events.forEach(([target, name]) => target.removeEventListener(name, check))
  } }
}
