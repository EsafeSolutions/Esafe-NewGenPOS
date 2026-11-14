// Two-window customer display regression checks. Uses a local isolated cashier,
// real Vue stores/BroadcastChannel/IndexedDB, and mocked ERP HTTP responses.
// node display-check.mjs [--serve]; optional PLAYWRIGHT_MODULE / CHROME_PATH / DISPLAY_ARTIFACTS.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

const root = path.dirname(fileURLToPath(import.meta.url))
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>
<div id="app"></div><script type="module">
import { createApp, h } from 'vue'
import { createPinia } from 'pinia'
import CustomerDisplayView from '/src/views/CustomerDisplayView.vue'
import { useCartStore } from '/src/stores/cart.js'
import { useSessionStore } from '/src/stores/session.js'
import { connectDisplayCustomerEntry } from '/src/displayCustomerEntry.js'
import { publishCart, onDisplayRequest, onDisplayCustomerResult, displayTerminalId } from '/src/customerDisplay.js'
import { setCurrency } from '/src/format.js'
import '/src/styles.css'
localStorage.setItem('esafepos-theme', 'dark')
document.documentElement.dataset.theme = 'dark'
if (location.hash.startsWith('#/display')) {
  onDisplayCustomerResult((result) => { window.lastCustomerResult = result })
  createApp(CustomerDisplayView).mount('#app')
} else {
  const pinia = createPinia()
  createApp({ render: () => h('div', { style: 'padding:24px' }, [h('h1', 'Customer display test till'), h('a', { href: '#/display?terminal=' + displayTerminalId, target: '_blank' }, 'Open customer display')]) }).use(pinia).mount('#app')
  const session = useSessionStore(pinia)
  session.company = 'Weerakoon Agro'
  session.currency = 'LKR'
  setCurrency('LKR')
  session.settings.enable_customer_display = 1
  session.offline = true
  const cart = useCartStore(pinia)
  const seed = () => { cart.lines = [{ item_code:'TEST', item_name:'Test', price:1000, qty:2, manual_discount_percent:0 }] }
  seed()
  const publish = () => publishCart({ company: session.company, saleId: cart.displaySaleId,
    customer: cart.customer?.customer_name || '', customerKey: cart.customer?.name || '',
    customerEntryEnabled: !session.locked && !cart.submitting,
    items: cart.lines.map((l) => ({ name:l.item_name, qty:l.qty, rate:cart.show(l.price), amount:cart.show(l.qty*l.price) })),
    count:cart.itemCount, total:cart.show(cart.total), savings:'' })
  cart.$subscribe(publish)
  onDisplayRequest(publish)
  connectDisplayCustomerEntry(cart, session, publish)
  Object.assign(window, { cart, session, publish, seed, displayTerminalId })
}
window.ready = true
</script></body></html>`
const server = await createServer({ root, base: '/', server: { port: 0, host: '127.0.0.1', open: false },
  plugins: [{ name: 'display-check', configureServer(server) {
    server.middlewares.use('/display-check.html', async (req, res) => {
      res.setHeader('Content-Type', 'text/html')
      res.end(await server.transformIndexHtml('/display-check.html', html))
    })
  } }],
})
await server.listen()
const url = `http://127.0.0.1:${server.httpServer.address().port}/display-check.html`
console.log(url)
if (!process.argv.includes('--serve')) {
  const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
  const output = process.env.DISPLAY_ARTIFACTS
  if (output) await mkdir(output, { recursive: true })
  const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: 'chrome' }) })
  try {
    const context = await browser.newContext()
    const errors = []
    const till = await context.newPage()
    till.on('pageerror', (e) => errors.push(e.message))
    await till.goto(url)
    await till.waitForFunction(() => window.ready)
    const terminal = await till.evaluate(() => window.displayTerminalId)
    const display = await context.newPage()
    display.on('pageerror', (e) => errors.push(e.message))
    await display.setViewportSize({ width: 1896, height: 940 })
    await display.goto(url + '#/display?terminal=' + terminal)
    await display.getByLabel('Customer name').waitFor()
    assert.equal(await display.evaluate(() => document.documentElement.dataset.theme), 'light')
    assert.equal(await till.evaluate(() => document.documentElement.dataset.theme), 'dark')
    assert.equal(await display.evaluate(() => localStorage.getItem('esafepos-theme')), 'dark')
    assert.equal(await display.locator('.cdisplay').evaluate((el) => getComputedStyle(el).backgroundColor), 'rgb(255, 255, 255)')
    for (const width of [1896, 390]) {
      await display.setViewportSize({ width, height: 940 })
      assert.equal(await display.evaluate(() => document.querySelector('.cdisplay').scrollWidth <= innerWidth), true)
      if (output) await display.screenshot({ path: path.join(output, `customer-display-${width}.png`), fullPage: true })
    }
    await display.setViewportSize({ width: 1896, height: 940 })
    await display.getByLabel('Customer name').fill('Display Test Customer')
    await display.getByLabel('Contact number').fill('abc')
    await display.getByRole('button', { name: 'Save details' }).click()
    await display.getByRole('alert').waitFor()
    assert.equal(await till.evaluate(() => cart.customer), null)
    await display.getByLabel('Contact number').fill('0770000000')
    await display.getByRole('button', { name: 'Save details' }).click()
    await display.getByText('Thank you. Your details have been added to this sale.').waitFor()
    const first = await till.evaluate(() => ({ ...cart.customer }))
    assert.equal(first.customer_name, 'Display Test Customer')
    assert.equal(first.mobile_no, '0770000000')
    assert.equal(first.__local, true)
    await display.getByRole('button', { name: 'Edit details' }).click()
    await display.getByRole('button', { name: 'Save details' }).click()
    await display.getByText('Thank you. Your details have been added to this sale.').waitFor()
    assert.equal(await till.evaluate(() => cart.customer.name), first.name, 'Reuse offline mobile match')

    // Another cashier tab must not overwrite this display or receive its input.
    const other = await context.newPage()
    await other.goto(url)
    await other.waitForFunction(() => window.ready)
    await other.evaluate(() => { session.company = 'Other till'; publish() })
    assert.equal(await display.locator('.cd-company').textContent(), 'Weerakoon Agro')
    assert.equal(await other.evaluate(() => cart.customer), null)

    await till.evaluate(() => { cart.clear(); seed() })
    await display.waitForFunction(() => document.getElementById('display-customer-name')?.value === '')
    assert.equal(await display.getByLabel('Contact number').inputValue(), '')
    await till.evaluate(() => { session.offline = false })
    await till.route('**/api/method/**', async (route) => {
      if (route.request().url().includes('create_customer')) {
        await route.fulfill({ json: { message: { name: 'CUST-ONLINE', customer_name: 'Online Customer', mobile_no: '0770000001' } } })
      } else await route.fulfill({ json: { message: {} } })
    })
    await display.getByLabel('Customer name').fill('Online Customer')
    await display.getByLabel('Contact number').fill('0770000001')
    await display.getByRole('button', { name: 'Save details' }).click()
    await display.getByText('Thank you. Your details have been added to this sale.').waitFor()
    assert.equal(await till.evaluate(() => cart.customer.name), 'CUST-ONLINE')

    // Backend validation/permission errors remain visible and the form can retry.
    await display.getByRole('button', { name: 'Edit details' }).click()
    await till.unroute('**/api/method/**')
    await till.route('**/api/method/**', async (route) => {
      await route.fulfill({ status: 403, json: { exception: 'PermissionError: Please ask the cashier for help.' } })
    })
    await display.getByRole('button', { name: 'Save details' }).click()
    await display.getByRole('alert').waitFor()
    assert.equal(await display.getByRole('button', { name: 'Save details' }).isEnabled(), true)
    assert.equal(await till.evaluate(() => cart.customer.name), 'CUST-ONLINE')

    // A response arriving after the sale changes cannot select the next customer.
    await till.evaluate(() => { cart.clear(); seed() })
    await display.waitForFunction(() => document.getElementById('display-customer-name')?.value === '')
    let release
    const held = new Promise((resolve) => { release = resolve })
    await till.unroute('**/api/method/**')
    await till.route('**/api/method/**', async (route) => {
      await held
      await route.fulfill({ json: { message: { name:'STALE', customer_name:'Previous customer' } } })
    })
    await display.getByLabel('Customer name').fill('Previous customer')
    await display.getByLabel('Contact number').fill('0770000002')
    await display.evaluate(() => { window.lastCustomerResult = null })
    const request = till.waitForRequest('**/api/method/esafepos.api.catalog.create_customer')
    await display.getByRole('button', { name: 'Save details' }).click()
    await request
    await till.evaluate(() => { cart.clear(); seed() })
    release()
    await display.waitForFunction(() => window.lastCustomerResult?.error)
    await display.waitForFunction(() => document.getElementById('display-customer-name')?.value === '')
    assert.equal(await till.evaluate(() => cart.customer), null)
    assert.deepEqual(errors, [])
    console.log('PASS light display, responsive form, validation, offline matching, online save, till isolation and stale-sale protection')
  } finally {
    await browser.close()
    await server.close()
  }
}
