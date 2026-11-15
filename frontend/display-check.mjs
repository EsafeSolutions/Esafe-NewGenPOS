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
import { createApp, h, ref, watch } from 'vue'
import { createPinia } from 'pinia'
import ProductGrid from '/src/components/ProductGrid.vue'
import ItemDetailModal from '/src/components/ItemDetailModal.vue'
import CustomerDisplayView from '/src/views/CustomerDisplayView.vue'
import ItemsView from '/src/views/ItemsView.vue'
import { scaleBarcodeOptions, useCatalogStore } from '/src/stores/catalog.js'
import { saveCatalog, searchCatalog } from '/src/offline.js'
import { useCartStore } from '/src/stores/cart.js'
import { useSessionStore } from '/src/stores/session.js'
import { publishCart, onDisplayRequest, displayContactRequest, displayCustomerName, displayTerminalId, receiptSnapshot, requestDisplayContact } from '/src/customerDisplay.js'
import { connectTillContact } from '/src/displayContact.js'
import '/src/styles.css'

const pinia = createPinia()
const mode = ref('image')
const item = ref(null)
const catalog = useCatalogStore(pinia)
const session = useSessionStore(pinia)
const cart = useCartStore(pinia)
session.permissions = { can_change_price: true, can_edit_price: true, edit_items: true }
session.posProfile = 'Test Till'
session.settings.enable_customer_display = 1
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
if (!isDisplay && !isItems) {
  const sync = () => publishCart({ ...snapshot, customer: displayCustomerName(cart.customer?.customer_name), contact: displayContactRequest.value })
  onDisplayRequest(sync)
  connectTillContact(cart, session, { path: '/' })
  watch(() => [displayContactRequest.value, cart.customer], sync)
  window.showContact = (mode) => {
    if (mode === 'welcome') snapshot = { company: 'ESAFE POS', items: [] }
    else {
      snapshot = { company: 'ESAFE POS', items: [{ code: 'rice', name: 'Red rice', qty: 1, rate: '15', amount: '15' }], total: '15' }
    }
    requestDisplayContact(mode)
  }
  window.bumpEarlierItem = () => {
    const rice = { code: 'rice', name: 'Red rice', qty: 2, uom: 'Kg', rate: '15', amount: '30' }
    const milk = { code: 'milk', name: 'Milk', qty: 1, rate: '20', amount: '20' }
    publishCart({ items: [{ ...rice, qty: 1 }, milk], total: '35' })
    publishCart({ items: [rice, milk], total: '50' })
  }
}
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
Object.assign(window, { ready: true, mode, catalog, cart, session, displayTerminalId, publishCart })
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
    await display.locator('.cd-latest').getByText('Roasted coffee').waitFor()
    await display.getByText('Balance due').waitFor()
    assert.equal(await display.locator('input').count(), 0)
    assert.equal(await display.locator('.cd-item del').textContent(), '40.00')
    const otherTill = await context.newPage()
    await otherTill.goto(url)
    await otherTill.waitForFunction(() => window.ready)
    await otherTill.evaluate(() => publishCart({ items: [{ name:'Different till' }] }))
    await till.evaluate(() => showReceipt())
    await display.getByText('ESAFE ERP+POS - pos.esafe.lk', { exact: true }).waitFor()
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
    await till.route('**/api/method/esafepos.api.catalog.display_customer_lookup', async (route) => {
      const { mobile } = route.request().postDataJSON()
      await route.fulfill({ json: { message: mobile === '0771234567'
        ? { name: 'CUSTOMER-1', customer_name: 'Maya Silva', mobile_no: mobile } : null } })
    })
    await till.route('**/api/method/esafepos.api.loyalty.get_wallet', (route) => route.fulfill({ json: { message: {} } }))
    await till.route('**/api/method/esafepos.api.catalog.get_prices', (route) => route.fulfill({ json: { message: { prices: {} } } }))
    await till.evaluate(() => showContact('welcome'))
    await display.locator('.cd-welcome').waitFor()
    for (const width of [1024, 390]) {
      await display.setViewportSize({ width, height: 768 })
      if (output) await display.screenshot({ path: path.join(output, `membership-welcome-${width}.png`) })
    }
    await display.getByRole('button', { name: 'Skip' }).click()
    await display.locator('.cd-welcome').waitFor({ state: 'hidden' })
    await till.route('**/api/method/esafepos.api.sales.submit_sale', async (route) => {
      const { payload } = route.request().postDataJSON()
      assert.equal(payload.customer, null)
      assert.equal(payload.receipt_contact, '0770000000')
      await route.fulfill({ json: { message: { name: 'POS-0002', receipt_contact: payload.receipt_contact } } })
    })
    await till.evaluate(() => { cart.clear(); showContact('welcome') })
    await display.getByLabel('Contact number').fill('0770000000')
    await display.getByRole('button', { name: 'Continue' }).click()
    await display.locator('.cd-welcome').waitFor({ state: 'hidden' })
    assert.equal(await display.getByText('0770000000').count(), 0)
    const submitted = await till.evaluate(() => {
      cart.addItem(catalog.items[0])
      return cart.submit([{ mode_of_payment: 'Cash', amount: 20 }])
    })
    assert.equal(submitted.receipt_contact, '0770000000')
    assert.equal(await till.evaluate(() => cart.receiptContact), '')
    await till.evaluate(() => showContact('overlay'))
    const dialog = display.getByRole('dialog')
    await dialog.waitFor()
    if (output) {
      await display.setViewportSize({ width: 1024, height: 768 })
      await display.screenshot({ path: path.join(output, 'membership-popup-1024.png') })
    }
    await dialog.getByLabel('Contact number').fill('0770000000')
    await dialog.getByRole('button', { name: 'Continue' }).click()
    await dialog.waitFor({ state: 'hidden' })
    assert.equal(await till.evaluate(() => cart.receiptContact), '0770000000')
    await till.evaluate(() => showContact('overlay'))
    await dialog.getByLabel('Contact number').fill('0771234567')
    await dialog.getByRole('button', { name: 'Continue' }).click()
    await dialog.waitFor({ state: 'hidden' })
    await display.getByText('Maya', { exact: true }).waitFor()
    assert.equal(await till.evaluate(() => cart.receiptContact), '')
    assert.equal(await display.getByText('0771234567').count(), 0)
    assert.equal(await display.locator('.cd-item .grains svg').count(), 1)
    await till.evaluate(() => bumpEarlierItem())
    await display.locator('.cd-latest').getByText('Red rice').waitFor()
    await display.locator('.cd-latest').getByText('2 Kg × 15').waitFor()
    if (output) {
      await display.setViewportSize({ width: 1024, height: 768 })
      await display.screenshot({ path: path.join(output, 'customer-live-1024.png') })
    }
    // A stock-only offline cache must not hide later pages from online Sell.
    await till.route('**/api/method/esafepos.api.catalog.get_items', (route) => {
      const { start, limit } = route.request().postDataJSON()
      const items = Array.from({ length: start === 0 ? limit : 1 }, (_, index) => ({
        item_code: 'LIVE-' + (start + index), item_name: 'Live item ' + (start + index), price: 12,
      }))
      return route.fulfill({ json: { message: { items } } })
    })
    await till.evaluate(async () => {
      mode.value = 'list'
      await catalog.fetch()
      await catalog.fetch(true)
    })
    assert.equal(await till.evaluate(() => catalog.items.length), 81)
    assert.equal(await till.evaluate(() => catalog.items.at(-1).item_code), 'LIVE-80')
    assert.equal(await till.evaluate(() => catalog.hasMore), false)
    await till.evaluate(async () => {
      session.offline = true
      await catalog.fetch()
    })
    assert.equal(await till.evaluate(() => catalog.items[0].item_code), '01234')

    const manager = await context.newPage()
    let priceAccess = true
    manager.on('pageerror', (error) => errors.push(error.message))
    const details = { item_code: 'ITEM-0', item_name: 'Roasted coffee', stock_uom: 'Kg',
      price_list: 'Standard Selling', currency: 'LKR', can_edit_item: true, can_edit_prices: true,
      units: [{ uom: 'Kg', factor: 1, price: 20, editable: false }, { uom: 'Pack', factor: 0.5, price: 12, editable: true }] }
    const imagePng = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aok8AAAAASUVORK5CYII=', 'base64')
    await manager.route('**/api/method/**', async (route) => {
      const method = route.request().url().split('.').pop()
      let message = []
      if (method === 'editor_options') message = {
        item_groups: ['Groceries'], brands: ['Hill Coffee'], default_price_list: 'Standard Selling',
        price_lists: priceAccess ? [{ name: 'Standard Selling', currency: 'LKR' }, { name: 'Wholesale', currency: 'LKR' }] : [],
      }
      if (method === 'search_items') {
        const { start, limit, item_group, brand } = route.request().postDataJSON()
        message = Array.from({ length: start === 0 && !item_group && !brand ? limit : 1 }, (_, index) => ({
          name: 'ITEM-' + (start + index),
          item_name: start + index === 0 ? details.item_name : 'Editor item ' + (start + index),
          stock_uom: 'Kg',
          item_group: 'Groceries', brand: 'Hill Coffee',
        }))
      }
      if (method === 'get_items') message = { items: [] }
      if (method === 'item_details') {
        message = !priceAccess ? { ...details, can_edit_prices: false, price_list: null, units: [] }
          : route.request().postDataJSON().price_list === 'Wholesale'
          ? { ...details, price_list: 'Wholesale', units: [{ uom: 'Pack', factor: 0.5, price: 10, editable: true }] }
          : details
      }
      if (method === 'save_item') {
        const payload = route.request().postDataJSON()
        if (!priceAccess) {
          assert.equal(payload.item_name, 'Coffee with updated label')
          assert.deepEqual(payload.prices, [])
          return route.fulfill({ json: { message: { ...details, item_name: payload.item_name, can_edit_prices: false, price_list: null, units: [] } } })
        }
        assert.equal(payload.item_name, 'Fresh roasted coffee')
        assert.equal(payload.price_list, 'Wholesale')
        assert.equal(payload.image_content, imagePng.toString('base64'))
        assert.deepEqual(payload.prices, [{ uom: 'Pack', price: 13 }])
        message = { ...details, item_name: payload.item_name, price_list: 'Wholesale',
          image: 'data:image/png;base64,' + payload.image_content,
          units: [{ uom: 'Pack', factor: 0.5, price: 13, editable: true }] }
      }
      await route.fulfill({ json: { message } })
    })
    await manager.goto(url + '#/items')
    await manager.getByRole('button', { name: 'Load more items' }).click()
    await manager.getByRole('button', { name: /Editor item 50/ }).waitFor()
    await manager.getByRole('button', { name: /Category All categories/ }).click()
    const categorySearch = manager.waitForRequest((request) => request.url().endsWith('.search_items') &&
      request.postDataJSON().item_group === 'Groceries')
    await manager.getByRole('option', { name: 'Groceries' }).click()
    await categorySearch
    await manager.getByRole('button', { name: /Brand All brands/ }).click()
    const brandSearch = manager.waitForRequest((request) => request.url().endsWith('.search_items') &&
      request.postDataJSON().item_group === 'Groceries' && request.postDataJSON().brand === 'Hill Coffee')
    await manager.getByRole('option', { name: 'Hill Coffee' }).click()
    await brandSearch
    await manager.getByRole('button', { name: /Roasted coffee/ }).click()
    assert.equal(await manager.getByLabel('Kg', { exact: true }).getAttribute('readonly'), '')
    await manager.getByLabel('Item name').fill('Fresh roasted coffee')
    await manager.getByLabel('Product image').setInputFiles({ name: 'coffee.png', mimeType: 'image/png', buffer: imagePng })
    await manager.getByLabel('Selling price list').selectOption('Wholesale')
    await manager.waitForFunction(() => document.querySelector('.unit-prices input')?.value === '10')
    assert.equal(await manager.getByLabel('Item name').inputValue(), 'Fresh roasted coffee')
    assert.match(await manager.locator('.image-preview img').getAttribute('src'), /^blob:/)
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
    priceAccess = false
    await manager.reload()
    await manager.getByRole('button', { name: /Roasted coffee/ }).click()
    await manager.getByText('Your account cannot edit item selling prices.').waitFor()
    assert.equal(await manager.getByLabel('Selling price list').count(), 0)
    await manager.getByLabel('Item name').fill('Coffee with updated label')
    await manager.getByRole('button', { name: 'Save changes' }).click()
    await manager.getByRole('button', { name: /Coffee with updated label/ }).waitFor()
    assert.deepEqual(errors, [])
    console.log('PASS catalog paging, item filters, image upload, price access, display and responsive layout')
  } finally {
    await browser.close()
    await server.close()
  }
}
