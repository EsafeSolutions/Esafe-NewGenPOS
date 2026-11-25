// Real worker, IndexedDB/session/cart stores and fixture APIs; no live invoices.
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import { once } from 'node:events'
import { fileURLToPath } from 'node:url'
import { build } from 'vite'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
const worker = await readFile(new URL('./public/sw.js', import.meta.url), 'utf8')
const shell = await readFile(new URL('../esafepos/www/pos.html', import.meta.url), 'utf8')
const fixture = `
import { createPinia, setActivePinia } from 'pinia'
import { useSessionStore } from '/src/stores/session.js'
import { useCartStore } from '/src/stores/cart.js'
import { useCatalogStore } from '/src/stores/catalog.js'
import * as offline from '/src/offline.js'
import { call, ApiError } from '/src/api.js'
import { ready, setLocale, locale } from '/src/i18n.js'
import { startAppUpdates } from '/src/appUpdates.js'
import '/src/styles.css'
window.loadedAssetRevision = '__BUILD_REVISION__'
setActivePinia(createPinia())
const session = useSessionStore(), cart = useCartStore(), catalog = useCatalogStore()
await ready
await session.bootstrap(); await catalog.cacheFullCatalog(); await catalog.fetch()
window.busy = false; window.pending = ''; window.updateError = ''
window.test = { session, cart, catalog, offline, call, ApiError, setLocale, locale }
window.updater = startAppUpdates({ currentRevision: window.esafepos_shell_revision, interval: 1000000,
  readRevision: () => fetch('/revision').then((r) => r.json()),
  canReload: () => !window.busy && !cart.lines.length && !cart.submitting && !session.offline,
  onPending: (value) => { window.pending = value }, onState: (state) => { window.updateError = state.error } })
window.ready = true
`
const built = await build({ configFile: false, root: fileURLToPath(new URL('.', import.meta.url)),
  base: '/assets/esafepos/pos/', logLevel: 'error', plugins: [{
    name: 'offline-fixture', resolveId(id) { if (id === 'offline-fixture') return '\0offline-fixture' },
    load(id) { if (id === '\0offline-fixture') return fixture },
  }], build: { target: 'esnext', write: false, rollupOptions: { input: 'offline-fixture', output: {
    entryFileNames: 'pos.js', chunkFileNames: 'chunk-[name]-[hash].js',
    assetFileNames: (asset) => asset.name?.endsWith('.css') ? 'pos.css' : '[name][extname]',
  } } } })
const assets = new Map(built.output.map((asset) => [asset.fileName, asset.code || asset.source]))
assets.set('offline-assets.json', JSON.stringify([...assets.keys()]))
let revision = 'build-one', failure = '', serverStatus = 200, submitted = []
const requests = []
const bootstrap = { user: 'Administrator', pos_profile: 'Till', company: 'Test shop', currency: 'LKR',
  default_customer: 'Walk-in', default_customer_name: 'Walk-in', price_list: 'Standard Selling',
  payment_modes: [{ mode_of_payment: 'Cash', type: 'Cash' }], register_session: { name: 'REG-TEST' },
  settings: { background_upload: 0 }, permissions: {} }
const item = { item_code: 'POT', item_name: 'Flower pot', price: 195, actual_qty: 100, is_stock_item: 1 }
const server = createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost')
  requests.push(url.pathname)
  if (process.env.DEBUG_OFFLINE) {
    console.log('GET', req.url)
    res.on('finish', () => console.log('SENT', req.url, res.statusCode))
  }
  res.setHeader('Cache-Control', 'no-store')
  if (url.pathname === '/revision') {
    res.setHeader('Content-Type', 'application/json'); return res.end(JSON.stringify({ revision }))
  }
  if (url.pathname === '/sw.js') {
    res.setHeader('Content-Type', 'text/javascript'); res.setHeader('Service-Worker-Allowed', '/pos'); return res.end(worker)
  }
  if (url.pathname.startsWith('/api/')) {
    if (serverStatus !== 200) { res.statusCode = serverStatus; return res.end('Server maintenance') }
    let body = ''; for await (const part of req) body += part
    const args = body ? JSON.parse(body) : {}; let message = {}
    if (url.pathname.endsWith('.get_bootstrap')) message = bootstrap
    else if (url.pathname.endsWith('.get_full_catalog')) message = [item]
    else if (url.pathname.endsWith('.get_items')) message = { items: [item] }
    else if (url.pathname.endsWith('.submit_sale')) {
      submitted.push(args.payload); message = { name: 'INV-' + args.payload.idempotency_key, items: [], grand_total: 195 }
    } else if (url.pathname.endsWith('.refuse')) {
      res.statusCode = 417; res.setHeader('Content-Type', 'application/json')
      return res.end(JSON.stringify({ exc_type: 'ValidationError', exception: 'ValidationError: Sale refused' }))
    }
    res.setHeader('Content-Type', 'application/json'); return res.end(JSON.stringify({ message }))
  }
  if (url.pathname.startsWith('/assets/esafepos/pos/')) {
    const name = url.pathname.split('/').pop()
    if (failure === 'html' && name === 'pos.js') {
      res.setHeader('Content-Type', 'text/html'); return res.end('Maintenance')
    }
    if ((failure === 'main' && name === 'pos.js') || (failure === 'chunk' && name.startsWith('chunk-'))) {
      res.statusCode = 503; return res.end('Deploy in progress')
    }
    if (assets.has(name)) {
      res.setHeader('Content-Type', name.endsWith('.js') ? 'text/javascript' : name.endsWith('.css') ? 'text/css' : 'application/json')
      return res.end(String(assets.get(name)).replaceAll('__BUILD_REVISION__', revision))
    }
  }
  if (url.pathname === '/pos') {
    res.setHeader('Content-Type', 'text/html')
    return res.end(shell.replace(/\{#-[\s\S]*?#\}/g, '').replaceAll('{{ csrf_token }}', 'test-token')
      .replaceAll('{{ esafepos_version }}', 'test').replaceAll('{{ pos_shell_revision }}', revision))
  }
  res.statusCode = 404; res.end()
})
server.listen(0, '127.0.0.1'); await once(server, 'listening')
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe' })
try {
  const context = await browser.newContext()
  await context.route('https://fonts.googleapis.com/**', (route) => route.abort())
  await context.route('https://fonts.gstatic.com/**', (route) => route.abort())
  const first = await context.newPage(), second = await context.newPage()
  const url = `http://127.0.0.1:${server.address().port}/pos`
  const ready = (page, value) => page.waitForFunction((revision) => window.ready && window.esafepos_shell_revision === revision && window.loadedAssetRevision === revision, value)
  for (const page of [first, second]) {
    page.on('pageerror', (error) => console.error(error.message))
    await page.goto(url, { waitUntil: 'domcontentloaded' }); await ready(page, revision)
    await page.waitForFunction(() => navigator.serviceWorker.controller).catch(async (error) => {
      console.error(await page.evaluate(async () => { const r = await navigator.serviceWorker.getRegistration('/pos'); return { registration: r && { active: r.active?.state, installing: r.installing?.state, waiting: r.waiting?.state }, caches: await caches.keys() } }), requests)
      throw error
    })
  }
  revision = 'build-two'
  for (const page of [first, second]) {
    await page.evaluate(() => updater.check()); assert.equal(await page.evaluate(() => pending), revision)
    assert.equal(await page.evaluate(() => esafepos_shell_revision), 'build-one')
  }
  await second.evaluate(() => updater.apply()); await ready(second, revision)
  await first.reload(); await ready(first, 'build-one')
  console.log('PASS idle tills require agreement; accepting one leaves another unchanged even on reload')
  await context.setOffline(true)
  await first.reload(); await ready(first, 'build-one')
  await second.reload(); await ready(second, 'build-two')
  assert.equal(await second.evaluate(() => test.session.offline), true)
  assert.equal(await second.evaluate(() => test.catalog.items[0].item_code), 'POT')
  assert.equal(await second.evaluate(async () => { await test.setLocale('fr'); return test.locale.value }), 'fr')
  const sale = () => second.evaluate(async () => {
    test.cart.lines = [{ item_code: 'POT', item_name: 'Flower pot', price: 195, qty: 1 }]
    return test.cart.submit([{ mode_of_payment: 'Cash', amount: 195 }])
  })
  assert.equal((await sale()).offline, true)
  assert.equal(await second.evaluate(() => test.offline.queueCount()), 1)
  await second.reload(); await ready(second, 'build-two')
  assert.equal(await second.evaluate(() => test.offline.queueCount()), 1)
  assert.equal(await second.evaluate(() => test.locale.value), 'fr')
  console.log('PASS offline reopening, cached catalog, previously unused language and durable cash sale after reboot')
  await context.setOffline(false)
  await second.evaluate(async () => { test.session.stopHeartbeat(); await test.session.flushQueue(); await test.session.bootstrap() })
  assert.equal(await second.evaluate(() => test.offline.queueCount()), 0); assert.equal(submitted.length, 1)
  await second.evaluate(() => test.session.flushQueue()); assert.equal(submitted.length, 1)
  assert.ok(submitted[0].idempotency_key)
  console.log('PASS reconnect uploads once with the original idempotency key')
  for (const status of [502, 503, 504]) {
    serverStatus = status; assert.equal((await sale()).offline, true)
    await second.evaluate(() => test.session.stopHeartbeat())
  }
  assert.equal(await second.evaluate(() => test.offline.queueCount()), 3)
  // The background worker must leave maintenance failures pending for retry.
  await second.evaluate(async () => {
    const boot = await test.offline.kvGet('bootstrap')
    boot.settings.background_upload = 1
    await test.offline.kvSet('bootstrap', boot)
  })
  const activeWorker = context.serviceWorkers().find((worker) => worker.url().includes('build-two'))
  await assert.rejects(activeWorker.evaluate(() => sendQueue()), /temporarily unavailable/)
  assert.equal(await second.evaluate(() => test.offline.queueCount()), 3)
  assert.ok(await second.evaluate(async () => (await test.offline.listSaleLog()).every((row) => row.status !== 'failed')))
  serverStatus = 200
  assert.equal(await second.evaluate(async () => { try { await test.call('test.refuse') } catch (e) { return e instanceof test.ApiError } }), true)
  await second.evaluate(async () => { await test.session.flushQueue(); await test.session.bootstrap() })
  console.log('PASS maintenance/gateway outages queue sales and preserve background retries; validation stays a refusal')
  revision = 'build-three'
  for (const missing of ['main', 'chunk', 'html']) {
    failure = missing; await second.evaluate(() => updater.check())
    assert.equal(await second.evaluate(() => updater.apply()), false)
    assert.equal(await second.evaluate(() => esafepos_shell_revision), 'build-two')
    await context.setOffline(true); await second.reload(); await ready(second, 'build-two')
    await context.setOffline(false); await second.evaluate(() => test.session.bootstrap())
  }
  failure = ''; await second.evaluate(() => updater.check())
  await second.evaluate(() => updater.apply()); await ready(second, revision)
  const names = await second.evaluate(() => caches.keys())
  assert.ok(names.includes('esafepos-shell-build-one'))
  await context.setOffline(true); await second.reload(); await ready(second, revision)
  await first.reload(); await ready(first, 'build-one')
  console.log('PASS partial deployments preserve working caches; retry installs a complete shell and keeps old open tills offline')
  await context.close()
} finally { await browser.close(); await new Promise((resolve) => server.close(resolve)) }
