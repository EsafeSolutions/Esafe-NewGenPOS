import assert from 'node:assert/strict'
import { safeToUpdate, startAppUpdates, prepareAppUpdate } from './src/appUpdates.js'

const tick = () => new Promise((resolve) => setImmediate(resolve))
const document = Object.assign(new EventTarget(), { hidden: false, activeElement: null, querySelector: () => null })
const browser = Object.assign(new EventTarget(), { navigator: { onLine: true }, document })
const session = { loaded: true, registerOpen: true }
const cart = { lines: [], submitting: false }
const route = { path: '/' }
const safe = () => safeToUpdate({ session, cart, route, document })
assert.equal(safe(), true)
for (const [object, key, value] of [[cart, 'lines', [{}]], [cart, 'submitting', true], [cart, 'exchange', {}],
  [session, 'offline', true], [session, 'syncing', true], [session, 'locked', true], [session, 'registerOpen', false],
  [route, 'path', '/settings'], [route, 'path', '/display']]) {
  const previous = object[key]
  object[key] = value
  assert.equal(safe(), false, key)
  object[key] = previous
}
document.activeElement = { matches: () => true, value: 'unsaved search' }
assert.equal(safe(), false)
document.activeElement = null
document.querySelector = () => ({})
assert.equal(safe(), false)
document.querySelector = () => null
assert.equal(safeToUpdate({ session, cart, route, document, jobs: [{ state: 'submitting' }] }), false)
console.log('PASS sales, exchanges, offline sync, locked tills, forms, dialogs and printing block updates')

let revision = 'old', reloads = 0, preparations = 0, pending = '', error = '', deployReady = true
const updater = startAppUpdates({ currentRevision: revision, browser, interval: 1000000,
  readRevision: async () => ({ revision }), canReload: safe, onPending: (value) => { pending = value },
  onState: (state) => { error = state.error },
  prepare: async () => { preparations++; if (!deployReady) throw new Error('Deploy in progress') },
  reload: () => { reloads++ },
})
try {
  await tick()
  revision = 'new'
  await updater.check()
  assert.equal(pending, 'new')
  await updater.check()
  browser.dispatchEvent(new Event('focus'))
  await tick()
  assert.equal(preparations, 0, 'An idle till still requires agreement')
  assert.equal(reloads, 0)
  cart.lines = [{}]
  assert.equal(await updater.apply(), false)
  assert.match(error, /Finish/)
  cart.lines = []
  await updater.check()
  assert.equal(reloads, 0, 'Finishing a sale is not agreement')
  deployReady = false
  assert.equal(await updater.apply(), false)
  assert.equal(reloads, 0)
  deployReady = true
  browser.navigator.onLine = false
  assert.equal(await updater.apply(), false)
  browser.navigator.onLine = true
  document.hidden = true
  assert.equal(await updater.apply(), false)
  document.hidden = false
  assert.equal(await updater.apply(), true)
  assert.equal(await updater.apply(), false)
  assert.equal(reloads, 1)
} finally { updater.stop() }
console.log('PASS polling/focus never update without consent; explicit apply retries failed deployments exactly once')

let releasePrepare, activated = 0
const changing = startAppUpdates({ currentRevision: 'old', browser, interval: 1000000,
  readRevision: async () => ({ revision: 'new' }), canReload: safe,
  prepare: () => new Promise((resolve) => { releasePrepare = () => resolve(() => { activated++ }) }),
  reload: () => { reloads++ },
})
try {
  await tick()
  const applying = changing.apply()
  await tick()
  assert.equal(await changing.apply(), false, 'Double click cannot start another install')
  cart.lines = [{}]
  releasePrepare()
  assert.equal(await applying, false)
  assert.equal(activated, 0)
  assert.equal(reloads, 1)
} finally { changing.stop(); cart.lines = [] }
console.log('PASS a basket started during preparation prevents worker activation and reload')

revision = 'new'
const replaced = startAppUpdates({ currentRevision: 'old', browser, interval: 1000000,
  readRevision: async () => ({ revision }), canReload: safe,
  onState: (state) => { error = state.error }, prepare: async () => { preparations++ }, reload: () => { reloads++ },
})
try {
  await tick()
  revision = 'newer'
  const before = preparations
  assert.equal(await replaced.apply(), false)
  assert.match(error, /agree again/)
  assert.equal(preparations, before)
  assert.equal(await replaced.apply(), true)
} finally { replaced.stop() }
console.log('PASS agreement is limited to the offered revision; a replacement needs fresh agreement')

let fetched = []
const prepareBrowser = { navigator: {}, fetch: async (url, options) => {
  fetched.push([url, options.cache])
  return new Response('window.esafepos_shell_revision = "new";', { headers: {
    'Content-Type': url.includes('pos.js?') ? 'text/javascript' : url.includes('pos.css?') ? 'text/css' : 'text/html',
  } })
} }
await prepareAppUpdate('new', prepareBrowser)
assert.deepEqual(fetched.map(([url]) => url), ['/pos', '/assets/esafepos/pos/pos.js?v=new', '/assets/esafepos/pos/pos.css?v=new'])
assert.ok(fetched.every(([, mode]) => mode === 'no-store'))
await assert.rejects(prepareAppUpdate('different', prepareBrowser), /still changing/)
prepareBrowser.navigator.serviceWorker = {
  controller: {}, register: async () => ({ active: { state: 'activated', scriptURL: 'https://pos.test/sw.js?v=old' } }),
}
await assert.rejects(prepareAppUpdate('new', prepareBrowser), /still downloading/)
delete prepareBrowser.navigator.serviceWorker
prepareBrowser.fetch = async () => new Response('Maintenance', { headers: { 'Content-Type': 'text/html' } })
await assert.rejects(prepareAppUpdate('new', prepareBrowser), /still changing/)
prepareBrowser.fetch = async () => ({ ok: false })
await assert.rejects(prepareAppUpdate('new', prepareBrowser), /not ready/)
console.log('PASS page/revision/critical assets validated over network; sites without a worker can update online')
