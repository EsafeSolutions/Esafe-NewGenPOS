import assert from 'node:assert/strict'
import { startCatalogSync, notifyCatalogChanged } from './src/catalogSync.js'

function fixture(overrides = {}) {
  const browser = new EventTarget(), document = new EventTarget(), timers = new Map()
  let nextTimer = 0, context = 'Till A', allowed = true, revision = '1', reads = 0, refreshes = 0
  Object.assign(document, { visibilityState: 'visible' })
  Object.assign(browser, { document, setTimeout: (fn, delay) => { timers.set(++nextTimer, { fn, delay }); return nextTimer },
    clearTimeout: id => timers.delete(id), localStorage: { setItem() {} } })
  const errors = []
  const sync = startCatalogSync({ browser, scope: () => context, canSync: () => allowed,
    readRevision: async () => { reads++; return { revision, direct_poll: false } },
    refresh: async () => { refreshes++; return true }, onError: error => errors.push(error), ...overrides })
  return { browser, document, timers, sync, errors, reads: () => reads, refreshes: () => refreshes,
    scope: value => { context = value }, allow: value => { allowed = value }, revision: value => { revision = value } }
}

{
  const f = fixture()
  await f.sync.check(); assert.equal(f.refreshes(), 1)
  await f.sync.check(); assert.equal(f.refreshes(), 1, 'unchanged commit marker avoids a data reload')
  f.revision('2'); await f.sync.check(); assert.equal(f.refreshes(), 2)
  await f.sync.check(true); assert.equal(f.refreshes(), 3)
  assert.equal(f.timers.size, 1, 'one polling timer')
  f.sync.stop(); assert.equal(f.timers.size, 0)
}
{
  const f = fixture({ maxAgeMs: 0 })
  await f.sync.check(); await f.sync.check()
  assert.equal(f.refreshes(), 2, 'fallback notices changes without document events')
  f.sync.stop()
}
{
  const f = fixture()
  f.document.visibilityState = 'hidden'; await f.sync.check(); assert.equal(f.reads(), 0)
  f.document.visibilityState = 'visible'; f.allow(false); await f.sync.check(); assert.equal(f.reads(), 0)
  f.allow(true); await f.sync.check(); assert.equal(f.reads(), 1)
  f.scope('Till B'); await f.sync.check(); assert.equal(f.refreshes(), 2, 'outlet change refreshes despite equal marker')
  f.sync.stop()
}
{
  let release, refreshes = 0, reads = 0
  const pending = new Promise(resolve => { release = resolve })
  const f = fixture({ readRevision: async () => { reads++; return pending }, refresh: async () => { refreshes++; return true } })
  const running = f.sync.check()
  await f.sync.check(true); assert.equal(reads, 1, 'requests never overlap')
  f.scope('Till B'); release({ revision: '1' }); await running
  assert.equal(refreshes, 0, 'stale outlet response is discarded')
  await f.sync.check(); assert.equal(refreshes, 1)
  f.sync.stop()
}
{
  let fail = true
  const f = fixture({ readRevision: async () => { if (fail) throw new Error('Connection lost'); return { revision: '1' } } })
  await f.sync.check(); assert.equal(f.errors.at(-1), 'Connection lost')
  assert.equal([...f.timers.values()][0].delay, 6000)
  fail = false; await f.sync.check(); assert.equal(f.errors.at(-1), '')
  f.sync.stop()
}
{
  let permitted = false
  const f = fixture({ refresh: async () => permitted })
  await f.sync.check(); assert.equal([...f.timers.values()][0].delay, 300, 'busy catalog is retried without acknowledging its marker')
  permitted = true; await f.sync.check(); assert.equal([...f.timers.values()][0].delay, 3000)
  f.sync.stop()
}
{
  const f = fixture()
  let notified = 0, stored = ''
  f.browser.addEventListener('esafepos:catalog-changed', () => notified++)
  f.browser.localStorage.setItem = (key, value) => { stored = key + value }
  notifyCatalogChanged(f.browser)
  assert.equal(notified, 1); assert.match(stored, /^esafepos:catalog-change/)
  assert.equal([...f.timers.values()][0].delay, 100)
  f.sync.stop(); f.browser.dispatchEvent(new Event('focus')); assert.equal(f.timers.size, 0)
}
console.log('Catalog sync checks passed: commit markers, forced/fallback refresh, visibility/offline gating, outlet races, no overlap, backoff, deferred refresh, cross-tab notification and cleanup.')
