import assert from 'node:assert/strict'
import { safeToUpdate, startAppUpdates, prepareAppUpdate } from './src/appUpdates.js'

const document = Object.assign(new EventTarget(), { hidden: false, activeElement: null, querySelector: () => null })
const browser = Object.assign(new EventTarget(), { navigator: { onLine: true }, document })
const session = { loaded: true, registerOpen: true }
const cart = { lines: [], submitting: false }
const route = { path: '/' }
const safe = () => safeToUpdate({ session, cart, route, document })
assert.equal(safe(), true)
for (const [object, key, value] of [[cart, 'lines', [{}]], [cart, 'submitting', true], [cart, 'exchange', {}],
  [session, 'offline', true], [session, 'syncing', true], [session, 'registerOpen', false], [route, 'path', '/settings']]) {
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
console.log('PASS update deferral for sales, exchanges, offline sync, forms, dialogs and printing')

let revision = '0.69.5-old'
let reloads = 0
let preparations = 0
let pending = false
let deployReady = true
const updater = startAppUpdates({ currentRevision: revision, browser, interval: 1000000,
  readRevision: async () => ({ revision }), canReload: safe, onPending: (value) => { pending = value },
  prepare: async () => { preparations++; if (!deployReady) throw new Error('Deploy in progress') },
  reload: () => { reloads++ },
})
await new Promise((resolve) => setImmediate(resolve))
assert.equal(reloads, 0)
cart.lines = [{}]
revision = '0.69.5-new'
await updater.check()
assert.equal(pending, true)
assert.equal(preparations, 0)
cart.lines = []
deployReady = false
await updater.check()
assert.equal(reloads, 0)
deployReady = true
browser.navigator.onLine = false
await updater.check()
assert.equal(reloads, 0)
browser.navigator.onLine = true
browser.document.hidden = true
await updater.check()
assert.equal(reloads, 0)
browser.document.hidden = false
browser.dispatchEvent(new Event('focus'))
await new Promise((resolve) => setImmediate(resolve))
assert.equal(reloads, 1)
await updater.check()
assert.equal(reloads, 1)
updater.stop()
console.log('PASS same-release update, pending sale, interrupted deploy, reconnect/focus and one reload')

let releasePrepare
const changing = startAppUpdates({ currentRevision: 'old', browser, interval: 1000000,
  readRevision: async () => ({ revision: 'new' }), canReload: safe,
  prepare: () => new Promise((resolve) => { releasePrepare = resolve }), reload: () => { reloads++ },
})
await new Promise((resolve) => setImmediate(resolve))
cart.lines = [{}]
releasePrepare()
await new Promise((resolve) => setImmediate(resolve))
assert.equal(reloads, 1, 'Starting a basket during download must cancel the reload')
changing.stop()
cart.lines = []
console.log('PASS basket started during update preparation is preserved')

let fetched = []
const prepareBrowser = { navigator: {}, fetch: async (url, options) => {
  fetched.push([url, options.cache])
  return { ok: true, text: async () => 'window.esafepos_shell_revision = "new";' }
} }
await prepareAppUpdate('new', prepareBrowser)
assert.deepEqual(fetched.map(([url]) => url), ['/pos', '/assets/esafepos/pos/pos.js?v=new', '/assets/esafepos/pos/pos.css?v=new'])
assert.equal(fetched[0][1], 'no-store')
await assert.rejects(prepareAppUpdate('different', prepareBrowser), /still changing/)
prepareBrowser.fetch = async () => ({ ok: false })
await assert.rejects(prepareAppUpdate('new', prepareBrowser), /not ready/)
console.log('PASS new-page revision and critical asset validation; no worker required')
