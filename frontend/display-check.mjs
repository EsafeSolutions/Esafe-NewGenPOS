// Browser regression checks for the till catalog and its read-only customer display.
// Run: node display-check.mjs. Optional PLAYWRIGHT_MODULE, CHROME_PATH and DISPLAY_ARTIFACTS.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

const root = path.dirname(fileURLToPath(import.meta.url))
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>
<div id="app"></div><script type="module">
import { createApp, h, ref } from 'vue'
import { createPinia } from 'pinia'
import ProductGrid from '/src/components/ProductGrid.vue'
import ItemDetailModal from '/src/components/ItemDetailModal.vue'
import CustomerDisplayView from '/src/views/CustomerDisplayView.vue'
import ItemsView from '/src/views/ItemsView.vue'
import { scaleBarcodeOptions, useCatalogStore } from '/src/stores/catalog.js'
import { saveCatalog, searchCatalog } from '/src/offline.js'
import { useCartStore } from '/src/stores/cart.js'
import { useSessionStore } from '/src/stores/session.js'
import { publishCart, onDisplayRequest, displayTerminalId, receiptSnapshot } from '/src/customerDisplay.js'
import '/src/styles.css'

const pinia = createPinia()
const mode = ref('image')
const item = ref(null)
const catalog = useCatalogStore(pinia)
const session = useSessionStore(pinia)
const cart = useCartStore(pinia)
session.permissions = { can_change_price: true, can_edit_price: true, edit_items: true }
session.posProfile = 'Test Till'
const image = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
catalog.items = Array.from({ length: 81 }, (_, i) => ({
  item_code: 'ITEM-' + i, item_name: i === 0 ? 'Roasted coffee' : 'Product ' + i,
  image, price: 20, stock_uom: 'Kg', description: '<p>Full description of the product.</p>',
  selling_units: [{ uom: 'Pack', factor: 0.5, price: 12, whole_qty: true }],
}))
const isDisplay = location.hash.startsWith('#/display')
const isItems = location.hash.startsWith('#/items')
createApp({ render: () => isDisplay ? h(CustomerDisplayView) : isItems ? h(ItemsView) : h('main', [
  h(ProductGrid, { mode: mode.value, onInspect: (row) => { item.value = row }, onSelect: (row) => { window.added = row.item_code } }),
  item.value ? h(ItemDetailModal, { item: item.value, onClose: () => { item.value = null }, onSave: (edits) => { window.edits = edits; item.value = null } }) : null,
]) }).use(pinia).mount('#app')

let snapshot = { company: 'ESAFE POS', count: 1, items: [
  { name: 'Roasted coffee', code: 'ITEM-0', image, qty: 2, uom: 'Kg', rate: '20.00', amount: '32.00', gross: '40.00', discount: '8.00' },
], subtotal: '40.00', total: '32.00', savings: '8.00', due: '12.00', paid: '20.00' }
window.showReceipt = () => {
  snapshot = receiptSnapshot({
    name: 'POS-0001', company: 'ESAFE POS', currency: 'LKR', posting_date: '2026-11-15', posting_time: '11:20:00',
    items: [{ item_name:'Roasted coffee', item_code:'ITEM-0', qty: 2, uom:'Kg', rate:16, gross_amount:40, line_discount_amount:8, amount:32 }],
    gross_total: 40, grand_total: 32, total_savings: 8, paid_amount: 40, change_amount: 8,
    payments:[{ mode_of_payment:'Cash', amount:40 }], loyalty_points_earned:3, loyalty:{ balance:18 },
  }, { 'ITEM-0': image })
  publishCart(snapshot)
}
if (!isDisplay) onDisplayRequest(() => publishCart(snapshot))
window.checkUnits = () => {
  const product = catalog.items[0]
  cart.addItem(product, null, 1.25)
  cart.addItem({ ...product, selling_uom:'Pack', conversion_factor:0.5, price:12 })
  return cart._basePayload().items
}
window.checkOfflineScale = async () => {
  await saveCatalog([{ item_code:'01234', item_name:'Loose coffee' }])
  const label = '2001234015006'
  const enabled = await searchCatalog(label, null, 5, '', scaleBarcodeOptions({ enable_scale_barcodes: 1 }))
  const disabled = await searchCatalog(label, null, 5, '', scaleBarcodeOptions({ enable_scale_barcodes: 0 }))
  return [enabled.length, disabled.length]
}
Object.assign(window, { ready: true, mode, displayTerminalId, publishCart })
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
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: 'chrome' }),
  })
  try {
    const context = await browser.newContext()
    const errors = []
    const till = await context.newPage()
    till.on('pageerror', (error) => errors.push(error.message))
    await till.goto(url)
    await till.waitForFunction(() => window.ready)
    await till.getByRole('button', { name: 'Add Roasted coffee to cart' }).click()
    assert.equal(await till.evaluate(() => window.added), 'ITEM-0')
    await till.getByRole('button', { name: /Roasted coffee ITEM-0/ }).click()
    const editor = till.getByRole('dialog')
    await editor.getByText('Full description of the product.').waitFor()
    await editor.getByLabel(/Quantity/).fill('1.25')
    await editor.getByLabel(/Unit price/).fill('18')
    await editor.getByLabel(/^Discount /).fill('10')
    await editor.getByRole('button', { name: 'Add to cart' }).click()
    assert.deepEqual(await till.evaluate(() => window.edits), { qty: 1.25, price: 18, discount: 10, method: 'percent' })
    await till.getByRole('button', { name: /Roasted coffee ITEM-0/ }).click()
    await editor.getByLabel('Selling unit').selectOption('Pack')
    assert.equal(await editor.getByLabel(/Unit price/).inputValue(), '12')
    assert.equal(await editor.getByLabel(/Quantity/).getAttribute('step'), '1')
    await editor.getByRole('button', { name: 'Add to cart' }).click()
    assert.equal(await till.evaluate(() => window.edits.unit.factor), 0.5)
    assert.deepEqual(await till.evaluate(() => window.checkUnits().map((line) => [line.qty, line.uom || null])), [[1.25, null], [1, 'Pack']])
    assert.deepEqual(await till.evaluate(() => window.checkOfflineScale()), [1, 0])
    await till.evaluate(() => { mode.value = 'list' })
    await till.locator('.grid.list').waitFor()
    assert.equal(await till.locator('.tile img').count(), 0)
    await till.evaluate(() => { mode.value = 'detail' })
    await till.locator('.grid.detail').waitFor()
    assert.equal(await till.locator('.tile-copy p').count(), 12)
    await till.getByRole('button', { name: 'Load more items' }).click()
    assert.equal(await till.locator('.tile-copy p').count(), 24)

    const terminal = await till.evaluate(() => window.displayTerminalId)
    const display = await context.newPage()
    display.on('pageerror', (error) => errors.push(error.message))
    await display.goto(url + '#/display?terminal=' + terminal)
    await display.getByText('Roasted coffee').waitFor()
    await display.getByText('Balance due').waitFor()
    assert.equal(await display.locator('input').count(), 0)
    assert.equal(await display.locator('del').textContent(), '40.00')
    const otherTill = await context.newPage()
    await otherTill.goto(url)
    await otherTill.waitForFunction(() => window.ready)
    await otherTill.evaluate(() => publishCart({ items: [{ name:'Different till' }] }))
    await till.evaluate(() => showReceipt())
    await display.getByText(/POS-0001/).waitFor()
    assert.equal(await display.getByText('Different till').count(), 0)
    for (const label of ['Change', 'Points earned', 'Points balance', 'You save']) {
      await display.getByText(label, { exact: true }).waitFor()
    }
    for (const width of [1440, 390]) {
      await display.setViewportSize({ width, height: 900 })
      assert.ok(await display.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
      if (output) {
        await display.screenshot({ path: path.join(output, `customer-display-${width}.png`), fullPage: true })
        await till.setViewportSize({ width, height: 900 })
        await till.screenshot({ path: path.join(output, `catalog-detail-${width}.png`), fullPage: false })
      }
    }
    const manager = await context.newPage()
    manager.on('pageerror', (error) => errors.push(error.message))
    const details = { item_code: 'ITEM-0', item_name: 'Roasted coffee', stock_uom: 'Kg',
      price_list: 'Standard Selling', currency: 'LKR',
      units: [{ uom: 'Kg', factor: 1, price: 20 }, { uom: 'Pack', factor: 0.5, price: 12 }] }
    await manager.route('**/api/method/**', async (route) => {
      const method = route.request().url().split('.').pop()
      let message = []
      if (method === 'search_items') message = [{ name: 'ITEM-0', item_name: details.item_name, stock_uom: 'Kg' }]
      if (method === 'get_items') message = { items: [] }
      if (method === 'item_details') message = details
      if (method === 'save_item') {
        const payload = route.request().postDataJSON()
        assert.equal(payload.item_name, 'Fresh roasted coffee')
        assert.deepEqual(payload.prices, [{ uom: 'Pack', price: 13 }])
        message = { ...details, item_name: payload.item_name }
      }
      await route.fulfill({ json: { message } })
    })
    await manager.goto(url + '#/items')
    await manager.getByRole('button', { name: /Roasted coffee/ }).click()
    await manager.getByLabel('Item name').fill('Fresh roasted coffee')
    await manager.getByLabel(/Pack/).fill('13')
    await manager.getByRole('button', { name: 'Save changes' }).click()
    await manager.getByRole('button', { name: /Fresh roasted coffee/ }).waitFor()
    if (output) {
      for (const width of [1440, 390]) {
        await manager.setViewportSize({ width, height: 900 })
        assert.ok(await manager.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
        await manager.screenshot({ path: path.join(output, `items-editor-${width}.png`) })
      }
    }
    assert.deepEqual(errors, [])
    console.log('PASS catalog modes, pack and loose cart lines, selling-price editor, customer display and responsive layout')
  } finally {
    await browser.close()
    await server.close()
  }
}
