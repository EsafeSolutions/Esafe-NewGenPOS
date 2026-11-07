// Regression checks for discount arithmetic, editing, permissions and offline receipts.
// Run: node discount-check.mjs; optional PLAYWRIGHT_MODULE / CHROME_PATH / DISCOUNT_ARTIFACTS.
import assert from 'node:assert/strict'
import { readFile, mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
import { discountBreakdown } from './src/discounts.js'

const root = path.dirname(fileURLToPath(import.meta.url))
const cases = JSON.parse(await readFile(new URL('./discount-scenarios.json', import.meta.url)))
const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 0.000001, `${actual} != ${expected}`)
for (const c of cases) {
  const r = discountBreakdown(c.lines, c.promo, c.bundles, c.order, c.factor || 1)
  r.perUnit.forEach((n, i) => near(n, c.expected.perUnit[i]))
  r.manual.forEach((n, i) => near(n, c.expected.manual[i]))
  near(r.orderTotal, c.expected.orderTotal)
  near(Math.max(...r.manualPercent, r.orderPercent), c.expected.maxPercent)
}
console.log(`PASS ${cases.length} shared Python/JS discount scenarios`)

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const output = process.env.DISCOUNT_ARTIFACTS
if (output) await mkdir(output, { recursive: true })
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>
<div id="app" style="max-width:400px; margin:16px auto"></div><script type="module">
import { createApp, h } from 'vue'
import { createPinia } from 'pinia'
import CartPanel from '/src/components/CartPanel.vue'
import { useCartStore } from '/src/stores/cart.js'
import { useSessionStore } from '/src/stores/session.js'
import '/src/styles.css'
const pinia = createPinia()
const app = createApp({ render: () => h(CartPanel) }).use(pinia)
const session = useSessionStore(pinia)
session.currency = 'LKR'
session.settings.enable_order_discount = 1
session.permissions = { can_edit_price: true, can_change_price: true }
session.offline = true
const cart = useCartStore(pinia)
cart.lines = [{ item_code: 'TEST', item_name: 'Test', price: 1000, qty: 2, manual_discount_percent: 0 }]
app.mount('#app')
window.cart = cart
window.session = session
window.ready = true
</script></body></html>`
const server = await createServer({ root, base: '/', server: { port: 0, host: '127.0.0.1', open: false },
  plugins: [{ name: 'discount-check', configureServer(server) {
    server.middlewares.use('/discount-check.html', async (req, res) => {
      res.setHeader('Content-Type', 'text/html')
      res.end(await server.transformIndexHtml('/discount-check.html', html))
    })
  } }],
})
await server.listen()
const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: 'chrome' }) })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/discount-check.html`)
  await page.waitForFunction(() => window.ready)
  await page.locator('.line-main').click()
  const itemDiscount = page.locator('#line-discount-0')
  await itemDiscount.fill('10')
  near(await page.evaluate(() => cart.total), 1800)
  await page.getByLabel('Item discount method').selectOption('amount')
  near(await page.evaluate(() => cart.total), 2000)
  await itemDiscount.fill('100')
  near(await page.evaluate(() => cart.total), 1800)
  await page.getByRole('button', { name: 'Discount', exact: true }).click()
  await page.getByLabel('Order discount method').selectOption('amount')
  await page.getByLabel('Order discount value').fill('50')
  near(await page.evaluate(() => cart.total), 1750)
  await page.getByLabel('Unit price (LKR)').fill('1200')
  await page.getByLabel('Unit price (LKR)').press('Tab')
  near(await page.evaluate(() => cart.total), 2150)
  await page.locator('.stepper .btn').last().click()
  near(await page.evaluate(() => cart.total), 3250)
  assert.deepEqual(await page.evaluate(() => {
    const p = cart._basePayload()
    return [p.items[0].price_override, p.items[0].manual_discount_amount, p.order_discount_amount]
  }), [1200, 100, 50])
  await page.evaluate(() => { session.settings.discount_limit_percent = 5 })
  assert.equal(await page.evaluate(() => cart.needsDiscountApproval), true)
  await page.evaluate(() => { cart.discountPasscode = 'approved'; cart.discountRequest = 'approved' })
  await itemDiscount.fill('101')
  assert.deepEqual(await page.evaluate(() => [cart.discountPasscode, cart.discountRequest]), [null, null])
  await itemDiscount.fill('100')
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    for (const locator of [page.getByLabel('Unit price (LKR)'), page.getByLabel('Item discount method'), itemDiscount, page.getByLabel('Order discount value')]) {
      const box = await locator.boundingBox()
      assert.ok(box.x >= 0 && box.x + box.width <= width)
    }
    if (output) await page.screenshot({ path: path.join(output, `discount-${width}.png`), fullPage: true })
  }
  await page.getByRole('button', { name: 'Reset price' }).click()
  near(await page.evaluate(() => cart.total), 2650)
  await page.evaluate(() => { session.permissions = { can_edit_price: false, can_change_price: false } })
  assert.equal(await page.getByLabel('Unit price (LKR)').isDisabled(), true)
  assert.equal(await itemDiscount.isDisabled(), true)
  assert.equal(await page.getByLabel('Order discount value').isDisabled(), true)
  await page.evaluate(() => { cart.setLinePrice(0, 500); cart.setLineDiscount(0, 900); cart.setOrderDiscount(900) })
  near(await page.evaluate(() => cart.total), 2650)
  await page.evaluate(() => { session.permissions = { can_edit_price: true, can_change_price: true } })
  await page.getByLabel('Order discount value').fill('99999')
  near(await page.evaluate(() => cart.total), 0)
  await page.getByLabel('Order discount value').fill('50')
  const receipt = await page.evaluate(async () => {
    const p = cart._basePayload()
    return await cart._queueOffline(p, [{ mode_of_payment: 'Cash', amount: cart.total }])
  })
  near(receipt.items.reduce((sum, l) => sum + l.amount, 0), receipt.grand_total)
  near(receipt.grand_total, 2650)
  assert.equal(await page.evaluate(() => cart.lines.length), 0)
  assert.deepEqual(errors, [])
  console.log('PASS cart controls, permissions, approval reset, desktop/mobile layout, payload and offline receipt')
} finally {
  await browser.close()
  await server.close()
}
