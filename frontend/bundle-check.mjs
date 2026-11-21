// Bundle quantities/discounts and mixed pack/loose sales in the actual Sell view.
// Run: node bundle-check.mjs. Optional PLAYWRIGHT_MODULE / CHROME_PATH / BUNDLE_ARTIFACTS.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
  .catch(() => import('./.label-test-tools/node_modules/playwright/index.mjs'))
const root = path.dirname(fileURLToPath(import.meta.url))
const output = process.env.BUNDLE_ARTIFACTS || path.join(root, '../docs/screenshots/bundles')
await mkdir(output, { recursive: true })
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>
<div id="sell-header-tools"></div><div id="app" style="height:calc(100dvh - 40px);display:flex"></div><script type="module">
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SellView from '/src/views/SellView.vue'
import { useCartStore } from '/src/stores/cart.js'
import { useSessionStore } from '/src/stores/session.js'
import { useCatalogStore } from '/src/stores/catalog.js'
import { saveCatalog } from '/src/offline.js'
import { setCurrency } from '/src/format.js'
import '/src/styles.css'
const pinia = createPinia(), session = useSessionStore(pinia), catalog = useCatalogStore(pinia), cart = useCartStore(pinia)
session.currency = 'LKR'; session.posProfile = 'Till'; session.priceList = 'Standard Selling'
setCurrency('LKR')
session.permissions = { can_edit_price: true, can_change_price: true }; session.offline = true
const item = { item_code: 'FEED', item_name: 'Layer feed (loose)', stock_uom: 'Kg', whole_qty: false,
  price: 1000, actual_qty: 500, is_stock_item: 1, selling_units: [
    { uom: '25 kg Pack', factor: 25, price: 4500, whole_qty: true },
    { uom: '50 kg Pack', factor: 50, price: 8750, whole_qty: true }] }
catalog.items = [item]; await saveCatalog([item])
session.bundles = [{ name: 'PACK50', title: 'Layer feed 50 kg pack', bundle_price: 8750,
  items: [{ item_code: 'FEED', item_name: 'Layer feed (loose)', qty: 50 }] },
  { name: 'PACK25', title: 'Layer feed 25 kg pack', bundle_price: 4500,
  items: [{ item_code: 'FEED', item_name: 'Layer feed (loose)', qty: 25 }] }]
const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: SellView }] })
await router.push('/'); await router.isReady()
createApp(SellView).use(pinia).use(router).mount('#app')
window.test = { cart, session, catalog, item }; window.ready = true
</script></body></html>`
const server = await createServer({ root, base: '/', server: { port: 0, host: '127.0.0.1', open: false },
  plugins: [{ name: 'bundle-check', configureServer(s) {
    s.middlewares.use('/bundle-check.html', async (req, res) => {
      res.setHeader('Content-Type', 'text/html')
      res.end(await s.transformIndexHtml('/bundle-check.html', html))
    })
  } }],
})
await server.listen()
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe' })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.route('https://fonts.googleapis.com/**', (route) => route.abort())
  await page.route('https://fonts.gstatic.com/**', (route) => route.abort())
  await page.route('**/api/method/**', async (route) => {
    const method = route.request().url().split('/').pop()
    const message = method.endsWith('.resolve_scan') ? { found: true, item: await page.evaluate(() => test.item) }
      : method.endsWith('.get_prices') ? { prices: { FEED: 1000 } } : {}
    await route.fulfill({ json: { message } })
  })
  const total = async (value) => assert.equal(await page.evaluate(() => test.cart.total), value)
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/bundle-check.html`)
  await page.waitForFunction(() => window.ready)
  await page.getByRole('button', { name: 'Bundles', exact: true }).click()
  // Concurrent taps while item details load must still produce one group.
  await page.evaluate(async () => {
    await Promise.all([test.cart.addBundle(test.session.bundles[1]), test.cart.addBundle(test.session.bundles[1])])
    if (test.cart.lines.length !== 1 || test.cart.lines[0].bundle_qty !== 2) throw new Error('Concurrent bundle Add created duplicate groups')
    test.cart.clear()
  })
  const pack50 = page.locator('.bundle-card').first()
  await pack50.getByRole('button', { name: 'Add', exact: true }).click()
  await page.waitForFunction(() => test.cart.lines.length === 1)
  await pack50.getByRole('button', { name: 'Add', exact: true }).click()
  await page.waitForFunction(() => test.cart.lines[0].qty === 100)
  assert.equal(await page.evaluate(() => test.cart.lines.length), 1)
  await total(17500)
  await page.locator('.line-main').click()
  const quantity = page.getByLabel('Packs', { exact: true })
  await quantity.fill('3'); await quantity.press('Tab'); await total(26250)
  await quantity.fill('1.5'); await quantity.press('Tab'); assert.equal(await quantity.inputValue(), '3')
  await quantity.fill('2'); await quantity.press('Tab')
  await page.getByLabel('Bundle discount', { exact: true }).fill('10'); await total(15750)
  await page.getByLabel('Bundle discount method').selectOption('amount')
  await page.getByLabel('Discount per bundle', { exact: true }).fill('250'); await total(17000)
  assert.deepEqual(await page.evaluate(() => {
    const row = test.cart._basePayload().items[0]
    return [row.qty, row.bundle_qty, row.bundle_discount_amount]
  }), [100, 2, 250])
  await page.evaluate(() => { test.session.settings.discount_limit_percent = 2 })
  assert.equal(await page.evaluate(() => test.cart.needsDiscountApproval), true)
  await page.evaluate(() => { test.cart.discountPasscode = 'ok'; test.cart.discountRequest = 'ok' })
  await page.getByRole('button', { name: 'Increase bundle quantity' }).click()
  assert.deepEqual(await page.evaluate(() => [test.cart.discountPasscode, test.cart.discountRequest]), [null, null])
  await page.getByRole('button', { name: 'Decrease bundle quantity' }).click()
  await page.evaluate(() => { test.session.permissions.can_edit_price = false; test.cart.setBundleDiscount(test.cart.lines[0].bundle_key, 99) })
  assert.equal(await page.getByLabel('Discount per bundle', { exact: true }).isDisabled(), true)
  await total(17000)
  await page.evaluate(() => { test.session.permissions.can_edit_price = true; test.session.offline = false })
  await pack50.getByRole('button', { name: 'Sell loose' }).click()
  await page.getByLabel('Selling unit').selectOption('25 kg Pack')
  await page.getByLabel('Quantity (25 kg Pack)').fill('2')
  await page.getByRole('button', { name: 'Add to cart', exact: true }).click()
  await total(26000)
  await pack50.getByRole('button', { name: 'Sell loose' }).click()
  await page.getByLabel('Quantity (Kg)').fill('1.25')
  await page.getByRole('button', { name: 'Add to cart', exact: true }).click()
  await total(27250)
  assert.equal(await page.evaluate(() => test.cart.lines.reduce((sum, row) => sum + row.qty * (row.conversion_factor || 1), 0)), 151.25)
  const payload = await page.evaluate(() => test.cart._basePayload())
  assert.equal(payload.items[1].uom, '25 kg Pack')
  assert.equal(payload.items[2].qty, 1.25)
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    for (const control of [quantity, page.getByLabel('Bundle discount method'), page.getByLabel('Discount per bundle', { exact: true })]) {
      const box = await control.boundingBox()
      assert.ok(box.x >= 0 && box.x + box.width <= width)
    }
    await page.screenshot({ path: path.join(output, `bundle-${width}.png`), fullPage: true })
  }
  // Stock includes loose quantities and every selected selling UOM.
  const before = await page.evaluate(() => test.cart.lines[0].qty)
  await quantity.fill('11'); await quantity.press('Tab')
  assert.equal(await page.evaluate(() => test.cart.lines[0].qty), before)
  // Offline bundle receipts preserve the discount and multiplied stock quantity.
  await page.evaluate(() => { test.cart.lines = [test.cart.lines[0]]; test.session.offline = true })
  const receipt = await page.evaluate(async () => {
    const cart = test.cart
    return cart._queueOffline(cart._basePayload(), [{ mode_of_payment: 'Cash', amount: cart.total }])
  })
  assert.equal(receipt.grand_total, 17000)
  assert.equal(receipt.items[0].qty, 100)
  assert.equal(receipt.items[0].amount, 17000)
  assert.deepEqual(errors, [])
  console.log('PASS bundle count, repeat Add, discounts, approvals, permissions, mixed UOM, stock guard, offline receipt and desktop/mobile layout')
} finally {
  await browser.close()
  await server.close()
}
