// Browser regression checks for receipt geometry. Requires Playwright and Chrome.
// Run: node receipt-check.mjs
// Optional: PLAYWRIGHT_MODULE (module URL), CHROME_PATH, RECEIPT_ARTIFACTS (output folder).
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const root = path.dirname(fileURLToPath(import.meta.url))
const output = process.env.RECEIPT_ARTIFACTS
if (output) await mkdir(output, { recursive: true })
const server = await createServer({
  root, base: '/', server: { port: 0, host: '127.0.0.1', open: false },
  plugins: [{
    name: 'receipt-check',
    configureServer(server) {
      server.middlewares.use('/receipt-check.html', async (req, res) => {
        res.setHeader('Content-Type', 'text/html')
        res.end(await server.transformIndexHtml('/receipt-check.html', html))
      })
    },
  }],
})
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>
<div id="app"></div><script type="module">
import { createApp, h, nextTick, reactive } from 'vue'
import { createPinia } from 'pinia'
import ReceiptModal from '/src/components/ReceiptModal.vue'
import { createReceiptPrintFrame } from '/src/receiptPrint.js'
import { useSessionStore } from '/src/stores/session.js'
import '/src/styles.css'
const receipt = reactive({ name: 'ACC-PSINV-2026-00004', company: 'Weerakoon Agro',
  posting_date: '2026-11-07', posting_time: '04:28:56', customer_name: 'Walk-in customer',
  cashier: 'Cashier', terminal: 'Sales-01', currency: 'LKR', grand_total: 2000,
  items: [{ item_name: 'Test', qty: 2, rate: 1000, price_list_rate: 1000, amount: 2000 }],
  payments: [{ mode_of_payment: 'Cash', amount: 2000 }], receipt_settings: {} })
const pinia = createPinia()
createApp({ render: () => h(ReceiptModal, { receipt }) }).use(pinia).mount('#app')
const session = useSessionStore(pinia)
session.settings = { receipt_template: 'Retail', receipt_show_payments: 1, receipt_show_unit_price: 1 }
session.offline = true
window.prepare = async ({ width, count, template = 'Retail', currency = 'LKR', dark = false, rtl = false, extras = false }) => {
  document.documentElement.dataset.theme = dark ? 'dark' : 'light'
  document.documentElement.dir = rtl ? 'rtl' : 'ltr'
  receipt.currency = currency
  receipt.receipt_settings = { receipt_paper_width: width + 'mm', receipt_template: template,
    receipt_show_item_code: extras, receipt_show_serial: extras,
    receipt_logo: extras ? '/receipt-logo.svg' : '' }
  receipt.items = Array.from({ length: count }, (_, i) => ({
    item_name: count === 1 ? 'Test' : 'Ceylon Salt Iodated Table Salt 400 G',
    qty: i ? 1.01 : 2, rate: 1000, price_list_rate: 1200, amount: i ? 1010 : 2000,
    item_code: 'LONG-ITEM-CODE-1234567890', serial_no: 'SN-1234567890'
  }))
  receipt.grand_total = receipt.items.reduce((sum, item) => sum + item.amount, 0)
  receipt.payments[0].amount = receipt.grand_total
  await nextTick()
  await createReceiptPrintFrame(document.getElementById('receipt-print'))
}
window.ready = true
</script></body></html>`
await server.listen()
const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: 'chrome' }) })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  await page.route('https://fonts.googleapis.com/**', (route) => route.abort())
  await page.route('**/receipt-logo.svg', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 150))
    await route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><rect width="200" height="100" fill="black"/></svg>' })
  })
  const errors = []
  page.on('pageerror', (error) => { errors.push(error.message); console.error(error.message) })
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/receipt-check.html`, { waitUntil: 'domcontentloaded' })
  await page.waitForFunction(() => window.ready)
  let shortHeight = 0
  for (const config of [
    { width: 80, count: 1 },
    { width: 80, count: 13, dark: true },
    { width: 58, count: 13 },
    { width: 80, count: 80 },
    { width: 58, count: 1, template: 'Classic', rtl: true },
    { width: 80, count: 1, template: 'Compact' },
    { width: 58, count: 1, template: 'Detailed' },
    { width: 80, count: 1, currency: 'KWD' },
    { width: 58, count: 1, currency: 'JPY' },
    { width: 58, count: 13, extras: true },
  ]) {
    await page.evaluate((config) => window.prepare(config), config)
    assert.equal(await page.locator('#receipt-print-frame').count(), 1, 'Repeated printing must remove stale frames')
    const frame = page.frames().find((frame) => frame !== page.mainFrame())
    const geometry = await frame.evaluate(() => {
      const receipt = document.getElementById('receipt-print')
      const rect = receipt.getBoundingClientRect()
      const cells = [...receipt.querySelectorAll('.retail-item-values td, .retail-no')]
      return { width: rect.width, height: rect.height, scrollWidth: receipt.scrollWidth,
        color: getComputedStyle(receipt).color,
        fontSize: getComputedStyle(receipt).fontSize,
        overflow: cells.filter((cell) => cell.scrollWidth > cell.clientWidth + 1).length,
        amounts: cells.map((cell) => cell.textContent),
        counts: receipt.querySelector('.retail-counts')?.textContent,
        logoHeight: receipt.querySelector('img')?.getBoundingClientRect().height,
        mode: document.compatMode,
        html: '<!doctype html>' + document.documentElement.outerHTML }
    })
    assert.ok(Math.abs(geometry.width - config.width * 96 / 25.4) < 1, 'Paper width must match saved settings')
    assert.ok(geometry.scrollWidth <= geometry.width + 1, 'Receipt must fit the roll')
    assert.equal(geometry.overflow, 0, 'Price columns must fit without clipping')
    assert.equal(geometry.mode, 'CSS1Compat', 'Table fonts must inherit in standards mode')
    assert.ok(!geometry.counts?.includes('999999'), 'Fractional quantity sums must not print floating-point noise')
    if (config.extras) assert.ok(geometry.logoHeight > 0, 'Wait for logo loading before measuring paper')
    assert.equal(geometry.color, 'rgb(0, 0, 0)', 'Dark-mode receipts must print black')
    assert.ok(parseFloat(geometry.fontSize) >= 11, 'Thermal text must remain readable')
    if (config.count === 1 && config.width === 80 && !config.template && !config.currency) shortHeight = geometry.height
    if (config.count > 1) assert.ok(geometry.height > shortHeight, 'Paper must grow with the receipt')
    if (config.currency === 'KWD') assert.ok(geometry.amounts.some((amount) => amount.includes('2,000.000')))
    if (config.currency === 'JPY') assert.ok(geometry.amounts.some((amount) => amount.includes('2,000') && !amount.includes('.')))

    // Render the exact prepared document as a PDF: screen and print geometry
    // must agree or auto-sized thermal paper will clip/produce blank pages.
    const printPage = await browser.newPage()
    await printPage.route('**/receipt-logo.svg', (route) => route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><rect width="200" height="100" fill="black"/></svg>' }))
    await printPage.setContent(geometry.html)
    await printPage.emulateMedia({ media: 'print' })
    const printedHeight = await printPage.locator('#receipt-print').evaluate((el) => el.getBoundingClientRect().height)
    assert.ok(Math.abs(printedHeight - geometry.height) < 1, 'Measurement must use the final print layout')
    const pdf = await printPage.pdf({ preferCSSPageSize: true, displayHeaderFooter: true })
    const pdfText = pdf.toString('latin1')
    assert.match(pdfText, /\/Type \/Pages\s*\/Count 1\b/, 'Each receipt must occupy one fitted page')
    const box = pdfText.match(/\/MediaBox \[0 0 ([\d.]+) ([\d.]+)\]/)
    assert.ok(box, 'PDF must declare its page dimensions')
    assert.ok(Math.abs(Number(box[1]) - config.width * 72 / 25.4) < 1)
    assert.ok(Number(box[2]) * 96 / 72 >= geometry.height - 1)
    assert.ok(Number(box[2]) * 96 / 72 < geometry.height + 10, 'No long blank paper tail')
    if (output && config.width === 80 && config.count === 13) {
      await printPage.setViewportSize({ width: Math.ceil(geometry.width), height: Math.ceil(geometry.height) })
      await printPage.screenshot({ path: path.join(output, 'receipt-80mm.png'), fullPage: true })
    }
    await printPage.close()
    console.log('PASS', JSON.stringify(config), `${Math.round(geometry.height * 25.4 / 96)}mm content`)
  }
  await page.evaluate(() => window.prepare({ width: 80, count: 13 }))
  if (output) {
    await page.screenshot({ path: path.join(output, 'receipt-desktop.png') })
    await page.setViewportSize({ width: 390, height: 844 })
    await page.screenshot({ path: path.join(output, 'receipt-mobile.png') })
  }
  // Exercise the real Print receipt button without opening a native dialog.
  await page.evaluate(() => {
    window.printCalls = 0
    const append = document.body.appendChild
    document.body.appendChild = function (node) {
      const result = append.call(this, node)
      if (node.id === 'receipt-print-frame') {
        node.contentWindow.print = () => {
          window.printCalls++
          node.contentWindow.dispatchEvent(new Event('afterprint'))
        }
      }
      return result
    }
  })
  for (let count = 1; count <= 2; count++) {
    await page.getByRole('button', { name: 'Print receipt', exact: true }).click()
    await page.waitForFunction((count) => window.printCalls === count && !document.getElementById('receipt-print-frame'), count)
  }
  assert.equal(await page.locator('#receipt-print').count(), 1, 'Printing must leave the original receipt intact')
  console.log('PASS print button, offline reprint and afterprint cleanup')
  assert.deepEqual(errors, [], 'Receipt must render without browser errors')
} finally {
  await browser.close()
  await server.close()
}
