// Actual App + Settings UI, with read-only deployment metadata fixtures.
import assert from 'node:assert/strict'
import { mkdir, readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
const root = path.dirname(fileURLToPath(import.meta.url)), output = path.join(root, '../docs/screenshots/versions')
await mkdir(output, { recursive: true })
const catalog = JSON.parse(await readFile(path.join(root, '../esafepos/release_notes.json'), 'utf8'))
const version = catalog.current_version
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><div id="app"></div><script type="module">
import { createApp, h } from 'vue'; import { createPinia } from 'pinia'; import { createRouter, createMemoryHistory } from 'vue-router';
import App from '/src/App.vue'; import SettingsView from '/src/views/SettingsView.vue'; import {useSessionStore} from '/src/stores/session.js'; import {useCartStore} from '/src/stores/cart.js'; import {useCatalogStore} from '/src/stores/catalog.js'; import {useHelpStore} from '/src/stores/help.js'; import {printManager} from '/src/printing/index.js'; import '/src/styles.css';
window.esafepos_shell_revision='${version}-fixture';const pinia=createPinia(),session=useSessionStore(pinia),cart=useCartStore(pinia),catalog=useCatalogStore(pinia);session.loaded=true;session.user='manager';session.userFullname='Administrator';session.posProfile='Cashier 2';session.company='Weerakoon Agro';session.currency='LKR';session.registerSession={name:'REG-TEST',opened_at:'2026-11-26 08:00:00'};session.availableProfiles=['Cashier 2'];session.permissions={settings:true,is_manager:true};session.settings={version:'0.69.5',till_languages:['en'],enable_till_lock:0};session.bootstrap=async()=>{};session.watchConnection=()=>{};session.notify=(message)=>{window.notices.push(message)};for(const key of ['fetch','cacheFullCatalog','cacheCustomers'])catalog[key]=async()=>{};useHelpStore(pinia).init=()=>{};printManager.resume=async()=>{};window.notices=[];cart.lines=[{item_code:'RICE',price:250,qty:1}];const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',component:{render:()=>h('p','Active sale retained')}},{path:'/settings',component:SettingsView}]});await router.push('/settings');await router.isReady();createApp(App).use(pinia).use(router).mount('#app');window.test={session,cart,router,help:useHelpStore(pinia)};window.ready=true;
</script></body></html>`
const server = await createServer({ root, base: '/', server: { host: '127.0.0.1', port: 0, open: false }, plugins: [{ name: 'versions-check', configureServer(s) { s.middlewares.use('/versions-check.html', async (req, res) => { res.setHeader('Content-Type', 'text/html'); res.end(await s.transformIndexHtml('/versions-check.html', html)) }) } }] })
await server.listen()
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe' })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } }), errors = [], calls = []
page.on('pageerror', e => { errors.push(e.message); console.error(e.stack) })
await page.addInitScript(() => Object.defineProperty(navigator, 'serviceWorker', { value: undefined }))
await page.route('https://fonts.googleapis.com/**', r => r.abort()); await page.route('https://fonts.gstatic.com/**', r => r.abort())
let liveVersion = version, liveRevision = `${version}-fixture`, liveCatalog = catalog, fail = false, reloads = 0
await page.route('**/api/method/**', async route => {
  const method = route.request().url().split('/').pop(); calls.push(method); let message = []
  if (method.endsWith('app_revision')) message = { version: liveVersion, revision: liveRevision }
  else if (method.endsWith('updates.get_updates')) {
    if (fail) return route.fulfill({ status: 503, json: { exception: 'Release service unavailable' } })
    message = { version: liveVersion, revision: liveRevision, catalog: liveCatalog }
  } else if (method.endsWith('settings.get_settings')) message = { version: '0.69.5', companies: [], can_manage: true, delivery_apps: [] }
  else if (method.endsWith('inter_company.status')) message = { pending: [], recent: [], companies: {} }
  else if (method.endsWith('get_inter_company_settings')) message = {}
  await route.fulfill({ json: { message } })
})
await page.route('**/pos', route => { reloads++; return route.fulfill({ body: '' }) })
try {
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/versions-check.html`)
  await page.getByRole('button', { name: 'Updates & versions', exact: true }).click()
  const panel = page.locator('.workspace-content .updates-panel')
  await panel.getByRole('heading', { name: 'Updates & versions', exact: true }).waitFor()
  assert.equal(await page.locator('.pos-version').textContent(), `v${version}`)
  assert.deepEqual(await panel.locator('.updates-counts strong').allTextContents(), ['1', '6', '2', '1'])
  assert.equal(await panel.locator('.release-changes li').count(), 9)
  await panel.getByRole('button', { name: 'Check for updates', exact: true }).click()
  await panel.getByText('Up to date', { exact: true }).waitFor(); assert.equal(reloads, 0)
  for (const width of [1440, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `No overflow at ${width}`)
    if (width === 1440 || width === 390) await page.screenshot({ path: path.join(output, `updates-${width}.png`), fullPage: true })
  }
  await panel.getByLabel('Change type', { exact: true }).selectOption('fix'); assert.equal(await panel.locator('.release-changes li').count(), 1)
  assert.deepEqual(await panel.locator('.updates-counts strong').allTextContents(), ['1', '6', '2', '1'], 'Filtering must not change release totals')
  await panel.getByLabel('Change type', { exact: true }).selectOption('all')
  await panel.getByLabel('Search updates', { exact: true }).fill('F-005'); assert.equal(await panel.locator('.release-changes li').count(), 1)
  await panel.getByLabel('Search updates', { exact: true }).fill('unknown feature'); await panel.getByText('No recorded changes match this search.', { exact: true }).waitFor()
  await panel.getByLabel('Search updates', { exact: true }).fill('')
  await page.evaluate(() => { test.session.offline = true }); assert.equal(await panel.getByRole('button', { name: 'Check for updates', exact: true }).isDisabled(), true); assert.equal(await panel.locator('.release-changes li').count(), 9)
  await page.evaluate(() => { test.session.offline = false }); fail = true; await panel.getByRole('button', { name: 'Check for updates', exact: true }).click(); await panel.getByRole('alert').waitFor(); assert.equal(await panel.locator('.release-changes li').count(), 9)
  fail = false; liveVersion = '0.71.0'; liveRevision = '0.71.0-future'; liveCatalog = { ...catalog, current_version: liveVersion, releases: [{ number: 2, version: liveVersion, date: '2026-11-26', title: 'Future deployment fixture', changes: [{ id: 'F-007', type: 'feature', title: 'A newly deployed feature', text: 'Fixture metadata only.' }] }, ...catalog.releases] }
  await panel.getByRole('button', { name: 'Check for updates', exact: true }).click(); await panel.getByText('Update available', { exact: true }).waitFor()
  assert.deepEqual(await panel.locator('.updates-counts strong').allTextContents(), ['2', '7', '2', '1'])
  assert.equal(await page.locator('.pos-version').textContent(), `v${version}`, 'Checking a newer server must not relabel the running interface')
  assert.equal(await page.evaluate(() => test.help.version), version)
  assert.equal(await page.evaluate(() => test.cart.lines.length), 1); assert.equal(reloads, 0)
  await page.setViewportSize({ width: 1440, height: 1000 }); await panel.getByRole('button', { name: 'Review available update', exact: true }).click(); await page.getByText('Active sale retained', { exact: true }).waitFor()
  assert.equal(reloads, 0); assert.equal(await page.evaluate(() => test.cart.lines.length), 1)
  await page.locator('.pos-version').click(); const dialog = page.getByRole('dialog'); await dialog.getByRole('heading', { name: 'Updates & versions', exact: true }).waitFor()
  await page.emulateMedia({ reducedMotion: 'reduce' }); assert.equal(await dialog.evaluate(e => getComputedStyle(e).animationName), 'none')
  await page.setViewportSize({ width: 390, height: 844 }); assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await page.screenshot({ path: path.join(output, 'version-details-mobile.png'), fullPage: true }); await page.keyboard.press('Escape'); await dialog.waitFor({ state: 'hidden' }); assert.equal(await page.locator('.pos-version').evaluate(e => e === document.activeElement), true)
  assert.ok(calls.every(method => !/save|close_register|submit|rebuild/.test(method))); assert.deepEqual(errors, [])
  console.log('PASS running/server versions, Settings history, stable counts/IDs, filter/search, future releases, offline/failure, update consent, active basket, keyboard, reduced motion and desktop/mobile layout')
} finally { await browser.close(); await Promise.race([server.close(), new Promise(resolve => setTimeout(resolve, 3000))]) }
