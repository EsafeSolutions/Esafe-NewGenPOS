// Real checkout/receipt components with mocked API responses; no live invoices.
// Run: node checkout-check.mjs (PLAYWRIGHT_MODULE / CHROME_PATH / CHECKOUT_ARTIFACTS optional).
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const root = path.dirname(fileURLToPath(import.meta.url))
const output = process.env.CHECKOUT_ARTIFACTS
if (output) await mkdir(output, { recursive: true })
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>
<div id="app"></div><script type="module">
import { createApp, h, ref } from 'vue'
import { createPinia } from 'pinia'
import PaymentOverlay from '/src/components/PaymentOverlay.vue'
import ReceiptModal from '/src/components/ReceiptModal.vue'
import { useSessionStore } from '/src/stores/session.js'
import { useCartStore } from '/src/stores/cart.js'
import { queueCount } from '/src/offline.js'
import '/src/styles.css'
const pinia = createPinia()
const session = useSessionStore(pinia)
session.currency = 'LKR'
session.company = 'Weerakoon Agro'
session.posProfile = 'Cashier 2'
session.settings = { credit_sales_enabled: 1, receipt_template: 'Retail', receipt_show_payments: 1 }
session.paymentModes = [{ mode_of_payment: 'Cash', type: 'Cash', default: 1 }]
session.permissions = { can_edit_price: true }
window.notices = []
session.notify = (message) => window.notices.push(message)
const cart = useCartStore(pinia)
const receipt = ref(null)
const readyToPay = ref(false)
createApp({ render: () => receipt.value ? h(ReceiptModal, { receipt: receipt.value })
  : readyToPay.value ? h(PaymentOverlay, { onDone: (value) => { receipt.value = value } }) : null }).use(pinia).mount('#app')
window.cart = cart
window.session = session
window.queueCount = queueCount
window.startCheckout = () => { readyToPay.value = true }
window.receipt = receipt
window.ready = true
</script></body></html>`
const server = await createServer({ root, base: '/', server: { port: 0, host: '127.0.0.1', open: false },
  plugins: [{ name: 'checkout-check', configureServer(server) {
    server.middlewares.use('/checkout-check.html', async (req, res) => {
      res.setHeader('Content-Type', 'text/html')
      res.end(await server.transformIndexHtml('/checkout-check.html', html))
    })
  } }],
})
await server.listen()
const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: 'chrome' }) })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  let available = 1000
  let reason = null
  let offlineSubmit = false
  let quoteCalls = 0
  let submitted = null
  let lastReceipt = null
  const quote = () => ({ payable: 195, currency: 'LKR', rate: 1, foreign: false, blocked_modes: {},
    on_account: { enabled: 1, can_sell: 1, currency: 'LKR', owed: 0, available, reason } })
  await page.route('**/api/method/**', async (route) => {
    const method = route.request().url().split('/api/method/')[1]
    let message = {}
    if (method === 'esafepos.api.sales.quote_sale') {
      quoteCalls++
      message = quote()
    } else if (method === 'esafepos.api.sales.submit_sale') {
      if (offlineSubmit) return route.abort('failed')
      submitted = route.request().postDataJSON().payload
      const credit = submitted.payments.filter((p) => p.mode_of_payment === 'Credit Sale').reduce((n, p) => n + p.amount, 0)
      message = { name: 'ACC-PSINV-2026-00168', company: 'Weerakoon Agro', customer_name: 'Test customer',
        customer: 'CUSTOMER', cashier: 'Administrator', terminal: 'Cashier 2', currency: 'LKR', company_currency: 'LKR',
        posting_date: '2026-11-22', posting_time: '12:24:20', grand_total: 195, rounded_total: 195,
        gross_total: 195, total_savings: 0, change_amount: 0,
        items: [{ item_code: 'POT', item_name: '27cm Flower Pot -Black', qty: 1, rate: 195, price_list_rate: 195,
          amount: 195, line_discount_amount: 0 }], payments: submitted.payments,
        on_account: credit ? { amount: credit, owed_on_sale: credit, owed_total: credit } : null }
      lastReceipt = message
    }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ message }) })
  })
  const url = `http://127.0.0.1:${server.httpServer.address().port}/checkout-check.html`
  async function openCheckout({ cached = false } = {}) {
    await page.goto(url)
    await page.waitForFunction(() => window.ready)
    await page.evaluate(async ({ cached, answer }) => {
      // Mount after initializing the basket so the quote describes the sale.
      cart.customer = { name: 'CUSTOMER', customer_name: 'Test customer' }
      cart.lines = [{ item_code: 'POT', item_name: '27cm Flower Pot -Black', qty: 1, price: 195 }]
      if (cached) cart._quoteCache = { signature: JSON.stringify(cart._basePayload()), at: Date.now(), promise: Promise.resolve(answer) }
      startCheckout()
    }, { cached, answer: quote() })
    await page.locator('.oa-btn').waitFor({ state: reason ? 'hidden' : 'visible' })
    await page.waitForFunction(() => document.querySelector('.due-value')?.textContent.includes('195.00'))
  }
  await openCheckout()
  await page.getByRole('button', { name: /Put.*195.00.*on account/ }).click()
  assert.equal(await page.locator('.complete').isEnabled(), true)
  await page.locator('.complete').click()
  await page.locator('.receipt').waitFor()
  assert.equal(submitted.payments[0].amount, 195)
  assert.equal(submitted.payments[0].mode_of_payment, 'Credit Sale')
  assert.equal(await page.locator('.retail-savings').count(), 0)
  assert.match(await page.locator('.retail-totals .total').first().textContent(), /195.00/)
  assert.match(await page.locator('.owed').textContent(), /195.00/)
  assert.deepEqual((await page.locator('.retail-item-values td').allTextContents()).map((value) => value.replace(/[\u2066-\u2069]/g, '')),
    ['', '1', '195.00', '0.00', '195.00'])
  if (output) {
    await page.screenshot({ path: path.join(output, 'receipt-desktop.png') })
    await page.setViewportSize({ width: 390, height: 844 })
    await page.screenshot({ path: path.join(output, 'receipt-mobile.png') })
  }
  console.log('PASS full on-account checkout and full-price receipt without false savings')
  await page.setViewportSize({ width: 1440, height: 1000 })
  await openCheckout()
  await page.locator('.tender-input').fill('50')
  await page.getByRole('button', { name: 'Cash', exact: true }).click()
  await page.getByRole('button', { name: /Put.*145.00.*on account/ }).click()
  if (output) {
    await page.screenshot({ path: path.join(output, 'checkout-desktop.png') })
    await page.setViewportSize({ width: 390, height: 844 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    await page.screenshot({ path: path.join(output, 'checkout-mobile.png') })
  }
  await page.locator('.complete').click()
  await page.locator('.receipt').waitFor()
  assert.deepEqual(submitted.payments.map((p) => [p.mode_of_payment, p.amount]), [['Cash', 50], ['Credit Sale', 145]])
  console.log('PASS split cash/account checkout')
  // A cached basket quote must not reuse a stale credit balance at checkout.
  const calls = quoteCalls
  available = 100
  await openCheckout({ cached: true })
  assert.ok(quoteCalls > calls)
  await page.getByRole('button', { name: /Put.*100.00.*on account/ }).click()
  assert.equal(await page.locator('.complete').isDisabled(), true)
  assert.equal(await page.locator('.oa-btn').isDisabled(), true)
  console.log('PASS fresh credit quote, credit limit and remaining balance')
  reason = 'This customer is not allowed to buy on account.'
  await openCheckout()
  assert.match(await page.locator('.oa-why').textContent(), /not allowed/)
  assert.equal(await page.locator('.oa-btn').count(), 0)
  console.log('PASS customer credit refusal')
  reason = null
  available = 1000
  await openCheckout()
  await page.getByRole('button', { name: /Put.*195.00.*on account/ }).click()
  offlineSubmit = true
  await page.locator('.complete').click()
  await page.waitForFunction(() => notices.includes('A sale on account needs a connection.'))
  assert.equal(await page.evaluate(() => cart.lines.length), 1)
  assert.equal(await page.evaluate(() => queueCount()), 0)
  assert.equal(await page.locator('.receipt').count(), 0)
  console.log('PASS connection loss preserves basket without queuing an account sale')
  // An actual partial discount must still show its saving, not the full price.
  await page.evaluate((value) => { receipt.value = value }, { ...lastReceipt, grand_total: 175.5, rounded_total: 175.5,
    total_savings: 19.5, items: [{ ...lastReceipt.items[0], rate: 175.5, amount: 175.5, line_discount_amount: 19.5 }] })
  assert.match(await page.locator('.retail-savings').textContent(), /19.50/)
  assert.match(await page.locator('.retail-totals .total').first().textContent(), /175.50/)
  assert.deepEqual(errors, [])
  console.log('PASS partial-discount receipt and no browser errors')
} finally {
  await browser.close()
  await server.close()
}
