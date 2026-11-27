// Real POS shell, toolbar, customer window and browser media storage; no live ERP writes.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
import { advertSource, normalizePresentation, publicDisplayUrl, targetDisplay } from './src/displayContent.js'

for (const link of ['javascript:alert(1)', 'data:text/html,hi', 'file:///ad.mp4', 'https://user:pass@example.com/ad.mp4']) assert.equal(publicDisplayUrl(link), '')
assert.equal(advertSource('https://youtube.com.evil.example/watch?v=dQw4w9WgXcQ'), null)
assert.match(advertSource('https://youtu.be/dQw4w9WgXcQ').source, /^https:\/\/www.youtube-nocookie.com\/embed\/dQw4w9WgXcQ/)
assert.equal(advertSource('https://youtube.com/shorts/dQw4w9WgXcQ').type, 'embed')
assert.match(advertSource('https://www.tiktok.com/@shop/video/6718335390845095173').source, /player\/v1\/6718335390845095173/)
assert.equal(advertSource('https://instagram.com/shop/'), null)
assert.equal(advertSource('https://cdn.example.com/ad.mp4?token=abc').type, 'video')
assert.equal(normalizePresentation({ mode: 'bad', interval: -2, social: [{ url: 'javascript:alert(1)' }] }).mode, 'live')
assert.equal(normalizePresentation({ interval: -2 }).interval, 5)
assert.equal(normalizePresentation({ interval: Infinity }).interval, 300)
assert.equal(normalizePresentation({ social: Array.from({ length: 20 }, () => ({ label: 'Website', url: 'https://example.com/' })) }).social.length, 12)
const mainScreen = { label: 'Cashier' }, secondScreen = { label: 'Customer' }
assert.equal(targetDisplay([mainScreen, secondScreen], mainScreen), secondScreen)
assert.equal(targetDisplay([mainScreen, secondScreen], mainScreen, 'Cashier'), mainScreen)
assert.equal(targetDisplay([mainScreen, secondScreen], mainScreen, 'Disconnected'), secondScreen)

const root = path.dirname(fileURLToPath(import.meta.url)), output = path.join(root, '../docs/screenshots/customer-display')
await mkdir(output, { recursive: true })
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><div id="app"></div><script type="module">
import {createApp} from 'vue'; import {createPinia} from 'pinia'; import {createRouter,createWebHashHistory} from 'vue-router';
import App from '/src/App.vue'; import SellView from '/src/views/SellView.vue'; import CustomerDisplayView from '/src/views/CustomerDisplayView.vue';
import {useSessionStore} from '/src/stores/session.js'; import {useCatalogStore} from '/src/stores/catalog.js'; import {useCartStore} from '/src/stores/cart.js';
import * as display from '/src/customerDisplay.js'; import * as content from '/src/displayContent.js'; import '/src/styles.css';
const pinia=createPinia(),session=useSessionStore(pinia),catalog=useCatalogStore(pinia),cart=useCartStore(pinia);
session.loaded=true; session.user='manager'; session.userFullname='Cashier'; session.posProfile='Till A'; session.company='Osaka City (PVT) LTD'; session.currency='LKR';
session.permissions={}; session.settings.enable_customer_display=1; session.settings.enable_till_lock=0; session.settings.enable_quick_keys=0;
session.registerSession={name:'REG-TEST',opened_at:'2026-11-28 08:00:00'};
session.settings.bank_transfer_display={enabled:true,trigger:'bank',accounts:[{bank_name:'Receiving Bank',holder:session.company,account_number:'001234567890',currency:'LKR',pos_profile:'Till A',qr_payload:'EXPLICIT-BANK-QR',instructions:'Use the invoice reference.'},{bank_name:'Other Register Bank',holder:'Other',account_number:'002345',pos_profile:'Till B',currency:'LKR'}]};
session.bootstrap=async()=>{};session.watchConnection=()=>{};catalog.fetch=async()=>{};catalog.cacheFullCatalog=async()=>{};catalog.cacheCustomers=async()=>{};cart.reprice=async()=>{};
const router=createRouter({history:createWebHashHistory(),routes:[{path:'/',component:SellView},{path:'/display',component:CustomerDisplayView}]});
createApp(App).use(pinia).use(router).mount('#app');
Object.assign(window,{test:{session,cart,...display,...content}});
</script></body></html>`
const server = await createServer({ root, base: '/', cacheDir: 'node_modules/.vite-display-content-check', server: { port: 5196, host: '127.0.0.1', open: false, hmr: false }, plugins: [{ name: 'display-content-check', configureServer(server) {
  server.middlewares.use('/display-content-test.html', async (req, res) => { res.setHeader('Content-Type', 'text/html'); res.end(await server.transformIndexHtml('/display-content-test.html', html)) })
} }] })
await server.listen()
const url = `http://127.0.0.1:${server.httpServer.address().port}/display-content-test.html`
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
let browser
try {
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe' })
  const context = await browser.newContext({ viewport: { width: 1440, height: 960 } }), till = await context.newPage(), errors = []
  context.on('page', page => page.on('pageerror', error => errors.push(error.message)))
  till.on('pageerror', error => errors.push(error.message))
  await context.route('https://fonts.googleapis.com/**', route => route.abort())
  await context.route('https://fonts.gstatic.com/**', route => route.abort())
  await context.route('**/api/method/**', route => route.fulfill({ json: { message: {} } }))
  // Do not rely on network playback for the embed routing checks.
  await context.route('https://www.youtube-nocookie.com/**', route => route.fulfill({ contentType: 'text/html', body: '<p>Provider player fixture</p>' }))
  await till.goto(url)
  await till.getByRole('button', { name: 'Display', exact: true }).click()
  const panel = till.getByRole('dialog', { name: 'Customer display', exact: true })
  await panel.waitFor()
  await panel.getByRole('button', { name: 'Counter closed', exact: true }).click()
  await panel.getByLabel('Closed-counter message').fill('Please use counter 2. Thank you.')
  await panel.getByLabel('Default content when the till opens').selectOption('closed')
  await panel.getByRole('button', { name: 'Save and show' }).click()
  await panel.getByRole('status').waitFor()
  // Denial and unsupported browsers still open the window and offer manual placement.
  await till.evaluate(() => { window.getScreenDetails = async () => { throw new DOMException('Denied', 'NotAllowedError') } })
  const popupPromise = till.waitForEvent('popup')
  await panel.getByRole('button', { name: 'Open second display' }).click()
  let display = await popupPromise
  await display.getByRole('heading', { name: 'Counter closed', exact: true }).waitFor()
  await display.getByText('Please use counter 2. Thank you.').waitFor()
  await panel.getByText(/Move it to the second monitor/).waitFor()
  const placement = await till.evaluate(async () => {
    const original = window.open, calls = []
    const cashier = { label: 'Cashier', availLeft: 0, availTop: 0, availWidth: 1440, availHeight: 900 }
    const customer = { label: 'Customer', availLeft: -1920, availTop: 0, availWidth: 1920, availHeight: 1080 }
    const details = { screens: [cashier, customer], currentScreen: cashier }
    window.open = (url, name, features) => { calls.push({ url, name, features }); return { moveTo: (...args) => calls.push(args), resizeTo: (...args) => calls.push(args) } }
    try { await test.openDisplayWindow('', details); return calls } finally { window.open = original }
  })
  assert.match(placement[0].name, /^esafepos-customer-display-/)
  assert.match(placement[0].features, /left=-1920/)
  assert.deepEqual(placement[1], [-1920, 0])
  assert.deepEqual(placement[2], [1920, 1080])
  const assertLayout = async page => assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'No horizontal page overflow')
  const screenshot = async (page, name) => { await assertLayout(page); await page.screenshot({ path: path.join(output, name), fullPage: true }) }
  await screenshot(till, 'controls-desktop.png')
  await screenshot(display, 'counter-closed-desktop.png')
  await till.setViewportSize({ width: 390, height: 844 })
  await screenshot(till, 'controls-mobile.png')
  await display.setViewportSize({ width: 390, height: 844 })
  await screenshot(display, 'counter-closed-mobile.png')
  await till.setViewportSize({ width: 1440, height: 960 })
  await display.setViewportSize({ width: 1440, height: 960 })
  await panel.getByRole('button', { name: 'Social QR codes', exact: true }).click()
  for (const [index, label, link] of [[0, 'Facebook', 'https://facebook.com/osakacity'], [1, 'Instagram', 'https://instagram.com/osakacity'], [2, 'WhatsApp', 'https://wa.me/94770000000'], [3, 'Customer reviews', 'https://example.com/reviews']]) {
    await panel.getByRole('button', { name: 'Add QR code' }).click()
    await panel.getByLabel('QR label ' + (index + 1), { exact: true }).fill(label)
    await panel.getByLabel('QR link ' + (index + 1), { exact: true }).fill(link)
  }
  await panel.getByRole('button', { name: 'Save and show' }).click()
  await display.getByRole('heading', { name: 'Stay connected' }).waitFor()
  assert.equal(await display.locator('.dc-qr-grid img').count(), 4)
  assert.match(await display.getByAltText('QR code for Instagram', { exact: true }).getAttribute('src'), /^data:image\/gif;base64,/)
  await screenshot(display, 'social-qr-desktop.png')
  await display.setViewportSize({ width: 390, height: 844 }); await screenshot(display, 'social-qr-mobile.png')
  await till.setViewportSize({ width: 390, height: 844 }); await panel.getByLabel('QR link 1', { exact: true }).scrollIntoViewIfNeeded(); await screenshot(till, 'social-editor-mobile.png')
  await till.setViewportSize({ width: 1440, height: 960 }); await display.setViewportSize({ width: 1440, height: 960 })
  await panel.getByLabel('QR link 1', { exact: true }).fill('javascript:alert(1)')
  await panel.getByRole('button', { name: 'Save and show' }).click(); await panel.getByRole('alert').waitFor()
  await panel.getByLabel('QR link 1', { exact: true }).fill('https://facebook.com/osakacity')
  await panel.getByRole('button', { name: 'Bank details', exact: true }).click()
  await panel.getByRole('button', { name: 'Save and show' }).click()
  await display.getByText('001234567890', { exact: true }).waitFor()
  assert.equal(await display.getByText('Other Register Bank', { exact: true }).count(), 0)
  await screenshot(display, 'bank-standby-desktop.png')
  await till.evaluate(() => { test.session.currency = 'USD'; test.session.settings.bank_transfer_display = { ...test.session.settings.bank_transfer_display } })
  await display.getByText('Bank details are not available for this counter. Please ask the cashier.').waitFor()
  await till.evaluate(() => { test.session.currency = 'LKR'; test.session.settings.bank_transfer_display = { ...test.session.settings.bank_transfer_display } })
  await panel.getByRole('button', { name: 'Custom message', exact: true }).click()
  await panel.getByLabel('Message heading', { exact: true }).fill('Welcome to Osaka City')
  await panel.getByLabel('Message text', { exact: true }).fill('New arrivals are available upstairs.\nAsk our team for help.')
  await panel.getByRole('button', { name: 'Save and show' }).click()
  await display.getByRole('heading', { name: 'Welcome to Osaka City' }).waitFor()
  // Active basket overrides idle content and retains totals; Counter closed is explicit.
  await till.evaluate(() => { test.cart.addItem({ item_code: 'MUG', item_name: 'Ceramic mug', price: 250, stock_uom: 'Nos', is_stock_item: 0 }) })
  await display.locator('.cd-latest').getByText('Ceramic mug', { exact: true }).waitFor()
  await panel.getByRole('button', { name: 'Counter closed', exact: true }).click()
  await display.getByRole('heading', { name: 'Counter closed', exact: true }).waitFor()
  assert.equal(await display.locator('.cd-latest').count(), 0)
  await till.evaluate(() => test.cart.clear())
  await panel.getByRole('button', { name: 'Adverts', exact: true }).click()
  await panel.getByLabel('Advert link', { exact: true }).fill('https://instagram.com/osakacity')
  await panel.getByRole('button', { name: 'Add advert link' }).click(); await panel.getByRole('alert').waitFor()
  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aok8AAAAASUVORK5CYII=', 'base64')
  await panel.locator('input[type=file]').setInputFiles({ name: 'shop-offer.png', mimeType: 'image/png', buffer: png })
  await panel.getByLabel('Advert title 1', { exact: true }).fill('Our latest offers')
  await panel.getByLabel('Advert link', { exact: true }).fill('https://youtu.be/dQw4w9WgXcQ')
  await panel.getByRole('button', { name: 'Add advert link' }).click()
  await panel.getByLabel('Seconds per advert').fill('5')
  await panel.getByRole('button', { name: 'Save and show' }).click()
  await display.getByAltText('Our latest offers', { exact: true }).waitFor()
  await display.waitForFunction(() => document.querySelector('.dc-media-frame img')?.naturalWidth > 0)
  const localId = await till.evaluate(() => test.displayPresentation.value.adverts[0].localId)
  assert.equal(await display.evaluate(async id => (await test.displayMedia('get', id)).type, localId), 'image/png')
  await display.getByRole('button', { name: 'Pause adverts', exact: true }).click()
  await display.getByRole('button', { name: 'Next advert', exact: true }).click()
  await display.getByText('Adverts paused', { exact: true }).waitFor()
  await display.getByRole('button', { name: 'Play adverts', exact: true }).click()
  await display.locator('iframe[src^="https://www.youtube-nocookie.com/embed/"]').waitFor()
  await display.getByRole('button', { name: 'Previous advert', exact: true }).click()
  await display.getByAltText('Our latest offers', { exact: true }).waitFor()
  await display.getByRole('button', { name: 'Pause adverts', exact: true }).click()
  // An unsupported/corrupt local video must leave a useful fallback and controls.
  await panel.locator('input[type=file]').setInputFiles({ name: 'unplayable.webm', mimeType: 'video/webm', buffer: Buffer.from('unsupported video fixture') })
  await panel.getByRole('button', { name: 'Save and show' }).click()
  await display.locator('.dc-playback span').filter({ hasText: '1 / 3' }).waitFor()
  await display.getByRole('button', { name: 'Next advert', exact: true }).click()
  await display.getByRole('button', { name: 'Next advert', exact: true }).click()
  await display.getByText('This advert is unavailable. Please ask the cashier.', { exact: true }).waitFor()
  await panel.getByRole('button', { name: 'Remove advert', exact: true }).nth(2).click()
  await panel.getByRole('button', { name: 'Save and show' }).click()
  await display.locator('.dc-playback span').filter({ hasText: '1 / 2' }).waitFor()
  await display.getByRole('button', { name: 'Pause adverts', exact: true }).click()
  await context.setOffline(true)
  await display.getByRole('button', { name: 'Next advert', exact: true }).click()
  await display.getByRole('button', { name: 'Previous advert', exact: true }).click()
  await display.getByAltText('Our latest offers', { exact: true }).waitFor()
  await display.waitForFunction(() => document.querySelector('.dc-media-frame img')?.naturalWidth > 0)
  await context.setOffline(false)
  // Reject executable files before they enter local storage.
  await panel.locator('input[type=file]').setInputFiles({ name: 'unsafe.html', mimeType: 'text/html', buffer: Buffer.from('<script>alert(1)</script>') })
  await panel.getByRole('alert').filter({ hasText: 'supported image or video' }).waitFor()
  await panel.getByRole('button', { name: 'Save and show' }).click()
  await screenshot(till, 'advert-editor-desktop.png')
  await till.setViewportSize({ width: 390, height: 844 }); await panel.getByLabel('Advert title 1', { exact: true }).scrollIntoViewIfNeeded(); await screenshot(till, 'advert-editor-mobile.png')
  await till.setViewportSize({ width: 1440, height: 960 })
  // Counter-closed default and per-register storage survive a cashier refresh.
  await panel.getByLabel('Default content when the till opens').selectOption('closed')
  await panel.getByRole('button', { name: 'Save and show' }).click()
  await till.reload(); await till.waitForFunction(() => window.test)
  // A refreshed cashier tab owns a new terminal identity, so reopen its display.
  await display.close(); display = await context.newPage()
  await display.goto(await till.evaluate(() => test.customerDisplayUrl()))
  await display.getByRole('heading', { name: 'Counter closed', exact: true }).waitFor()
  await till.evaluate(() => { test.session.posProfile = 'Till B' })
  await display.waitForFunction(() => !document.querySelector('.display-content-closed'))
  assert.equal(await till.evaluate(() => test.displayPresentation.value.adverts.length), 0)
  await till.evaluate(() => { test.session.posProfile = 'Till A' })
  await display.getByRole('heading', { name: 'Counter closed', exact: true }).waitFor()
  // A separate till cannot inject cart or content into this window.
  const stranger = await context.newPage(); await stranger.goto(url)
  await stranger.waitForFunction(() => window.test)
  await stranger.evaluate(() => test.publishCart({ company: 'Wrong terminal', items: [], presentation: { mode: 'message', messageTitle: 'Wrong terminal' } }))
  await display.getByRole('heading', { name: 'Counter closed', exact: true }).waitFor()
  assert.equal(await display.getByText('Wrong terminal', { exact: true }).count(), 0)
  // Popup blocking has a visible recovery message.
  await till.getByRole('button', { name: 'Display', exact: true }).click()
  await till.evaluate(() => { window.open = () => null })
  await till.getByRole('button', { name: 'Open second display', exact: true }).click()
  await till.getByRole('alert').filter({ hasText: 'Allow pop-ups' }).waitFor()
  await till.keyboard.press('Escape'); await till.getByRole('dialog', { name: 'Customer display', exact: true }).waitFor({ state: 'hidden' })
  assert.deepEqual(errors, [])
  console.log('PASS real POS toolbar, second-screen popup/fallback, modes, filtered bank details, QR validation, local media/offline, defaults, register and terminal isolation, responsive layouts')
} finally { await browser?.close(); await server.close() }
