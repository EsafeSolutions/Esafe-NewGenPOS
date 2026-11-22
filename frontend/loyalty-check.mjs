// Real checkout/receipt components, simulated ERPNext; no live invoice is posted.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
const root = path.dirname(fileURLToPath(import.meta.url))
const output = path.join(root, '../docs/screenshots/loyalty')
await mkdir(output, { recursive: true })
const html = `<!doctype html><html data-theme="dark"><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>
<div id="app"></div><script type="module">
import { createApp, h, ref } from 'vue'; import { createPinia } from 'pinia'
import PaymentOverlay from '/src/components/PaymentOverlay.vue'; import ReceiptModal from '/src/components/ReceiptModal.vue'
import { useSessionStore } from '/src/stores/session.js'; import { useCartStore } from '/src/stores/cart.js'
import { queueCount } from '/src/offline.js'; import '/src/styles.css'
import { setCurrency } from '/src/format.js'; setCurrency('LKR')
const pinia = createPinia(), session = useSessionStore(pinia), cart = useCartStore(pinia), receipt = ref(null), show = ref(false)
session.currency = 'LKR'; session.company = 'ESAFE Retail'; session.posProfile = 'Till A'
session.settings = { receipt_template: 'Retail', receipt_show_payments: 1, enable_customer_display: 1 }
session.paymentModes = [{ mode_of_payment: 'Cash', type: 'Cash', default: 1 }, { mode_of_payment: 'Card', type: 'Bank' }]
window.notices = []; session.notify = (message) => notices.push(message)
createApp({ render: () => receipt.value ? h(ReceiptModal, { receipt: receipt.value }) : show.value ? h(PaymentOverlay, { onDone: value => { receipt.value = value } }) : null }).use(pinia).mount('#app')
window.test = { session, cart, receipt, queueCount, start: () => { show.value = true } }; window.ready = true
</script></body></html>`
const server = await createServer({ root, base: '/', server: { port: 0, host: '127.0.0.1', open: false },
  plugins: [{ name: 'loyalty-check', configureServer(server) {
    server.middlewares.use('/loyalty-check.html', async (req, res) => {
      res.setHeader('Content-Type', 'text/html'); res.end(await server.transformIndexHtml('/loyalty-check.html', html))
    })
  } }],
})
await server.listen()
const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: 'chrome' }) })
try {
  const page = await browser.newPage({ viewport: { width: 1502, height: 810 } })
  const errors = []
  page.on('pageerror', error => { errors.push(error.message); console.error(error.message) })
  let total = 1602, submitted, failSubmit = false
  await page.route('**/api/method/**', async route => {
    const method = route.request().url().split('/api/method/')[1]
    let message = {}
    if (method === 'esafepos.api.sales.quote_sale') message = { payable: total, currency: 'LKR', rate: 1, foreign: false, blocked_modes: {} }
    if (method === 'esafepos.api.credit.checkout_credit') message = { enabled: 0 }
    if (method === 'esafepos.api.sales.submit_sale') {
      if (failSubmit) return route.abort('failed')
      submitted = route.request().postDataJSON().payload
      const saved = submitted.loyalty_change_amount
      const paid = submitted.payments.reduce((sum, row) => sum + row.amount, 0)
      const redeemed = submitted.redeem_loyalty_points
      message = { name: 'POS-2026-001', doctype: 'POS Invoice', company: 'ESAFE Retail', customer_name: 'Nimal Perera',
        currency: 'LKR', company_currency: 'LKR', posting_date: '2026-11-23', posting_time: '10:00:00',
        grand_total: total, rounded_total: total, paid_amount: paid, change_amount: paid + redeemed - total - saved,
        loyalty_change_amount: saved, loyalty_change_points: saved, loyalty_amount: redeemed, loyalty_points_redeemed: redeemed,
        loyalty: { program: 'LKR Rewards', balance: saved }, payments: submitted.payments,
        items: [{ item_code: 'RICE', item_name: 'Rice', qty: 1, rate: total, amount: total }],
      }
    }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ message }) })
  })
  const url = `http://127.0.0.1:${server.httpServer.address().port}/loyalty-check.html`
  async function checkout({ points = 0, configured = true, customer = true } = {}) {
    await page.goto(url); await page.waitForFunction(() => window.ready)
    await page.evaluate(({ total, points, configured, customer }) => {
      test.cart.customer = customer ? { name: 'CUSTOMER', customer_name: 'Nimal Perera' } : null
      document.documentElement.dataset.theme = 'dark'
      test.cart.lines = [{ item_code: 'RICE', item_name: 'Rice', qty: 1, price: total }]
      test.cart.wallet = { customer: 'CUSTOMER', loyalty_program: 'LKR Rewards', loyalty_points: points, conversion_factor: 1,
        change_to_loyalty: { enabled: configured, reason: configured ? null : 'Set the ERPNext Loyalty Program conversion factor to 1 for 1 LKR = 1 point.' } }
      test.start()
    }, { total, points, configured, customer })
    await page.locator('.tender-input').waitFor()
  }
  async function cash(value) {
    await page.locator('.tender-input').fill(String(value))
    await page.getByRole('button', { name: 'Cash', exact: true }).click()
  }
  await checkout(); await cash(1610)
  assert.match(await page.locator('.due-value').textContent(), /8.00/)
  assert.match(await page.locator('.change-points').textContent(), /Save.*LKR\s*8.00.*as 8 points/)
  assert.equal(await page.getByRole('checkbox').isChecked(), false)
  await page.screenshot({ path: path.join(output, 'change-1502.png') })
  await page.getByRole('checkbox').check()
  assert.match(await page.locator('.due-value').textContent(), /0.00/)
  await page.screenshot({ path: path.join(output, 'saved-1502.png') })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: path.join(output, 'saved-390.png') })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await page.locator('.complete').click(); await page.locator('.receipt').waitFor()
  assert.equal(submitted.loyalty_change_amount, 8)
  assert.match(await page.locator('.receipt').textContent(), /Change saved as points/)
  await page.screenshot({ path: path.join(output, 'receipt-390.png') })
  console.log('PASS screenshot example: opt-in 8 LKR to 8 points; cash change, receipt and mobile layout')
  total = 1601.75
  await checkout(); await cash(1610); await page.getByRole('checkbox').check()
  assert.match(await page.locator('.change-points-result').textContent(), /0.25/)
  await page.getByRole('checkbox').uncheck()
  assert.match(await page.locator('.due-value').textContent(), /8.25/)
  console.log('PASS whole points retain fractional cash and opt-out restores change')
  await checkout({ configured: false }); await cash(1610)
  assert.equal(await page.getByRole('checkbox').count(), 0)
  assert.match(await page.locator('.change-points').textContent(), /conversion factor to 1/)
  await checkout({ customer: false }); await cash(1610)
  assert.equal(await page.getByRole('checkbox').count(), 0)
  assert.match(await page.locator('.change-points').textContent(), /Select a customer/)
  console.log('PASS ERPNext setup and named customer requirements')
  total = 8
  await checkout({ points: 8 })
  await page.screenshot({ path: path.join(output, 'redeem-390.png') })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await page.getByRole('button', { name: 'Use points', exact: true }).click()
  assert.match(await page.locator('.due-value').textContent(), /0.00/)
  await page.locator('.complete').click(); await page.locator('.receipt').waitFor()
  assert.equal(submitted.redeem_loyalty_points, 8)
  assert.deepEqual(submitted.payments, [])
  console.log('PASS later sale paid entirely with saved loyalty points')
  total = 1602
  await checkout(); await cash(1610); await page.getByRole('checkbox').check()
  failSubmit = true
  await page.locator('.complete').click()
  await page.waitForFunction(() => notices.some(value => value.includes('Saving change as loyalty points needs a connection')))
  assert.equal(await page.evaluate(() => test.cart.lines.length), 1)
  assert.equal(await page.evaluate(() => test.queueCount()), 0)
  assert.equal(await page.locator('.receipt').count(), 0)
  assert.deepEqual(errors, [])
  console.log('PASS connection loss preserves basket and never queues a transfer; no browser errors')
} finally {
  await browser.close()
  await Promise.race([server.close(), new Promise(resolve => setTimeout(resolve, 3000))])
}
