// Real Vue workspace with simulated APIs. No live stock or Item is changed.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
const root = path.dirname(fileURLToPath(import.meta.url))
const output = path.join(root, '../docs/screenshots/stock-manager')
await mkdir(output, { recursive: true })
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>#app{display:flex;flex-direction:column}body{overflow:hidden}</style></head><body><div id="app"></div><script type="module">
import { createApp, h } from 'vue'; import { createPinia } from 'pinia'; import { createRouter, createWebHashHistory, RouterView } from 'vue-router'; import StockManagerView from '/src/views/StockManagerView.vue'; import { useSessionStore } from '/src/stores/session.js'; import { useCatalogStore } from '/src/stores/catalog.js'; import { useCartStore } from '/src/stores/cart.js'; import { startCatalogSync } from '/src/catalogSync.js'; import { getCatalogItems } from '/src/offline.js'; import '/src/styles.css';
const pinia = createPinia(), session = useSessionStore(pinia); session.user = 'manager'; session.posProfile = 'SHOWROOM - Secondary'; session.permissions = { edit_items: true, stock_count: true }; session.notify = message => window.notices.push(message); window.notices = []; const catalog = useCatalogStore(pinia); catalog.fetch = async () => {}; catalog.cacheFullCatalog = async () => {}; catalog.items = [{item_code:'FLW-001',price:990,actual_qty:24}]; const cart = useCartStore(pinia); cart.reprice = async () => {}; window.test = { session, catalog, cart, getCatalogItems }; window.test.sync = startCatalogSync({scope:()=>session.posProfile,canSync:()=>!session.offline && !!session.permissions.edit_items,readRevision:()=>import('/src/api.js').then(api=>api.call('esafepos.api.catalog_sync.revision',{pos_profile:session.posProfile})),refresh:()=>catalog.refreshLive(),onError:error=>catalog.liveError=error});
const router = createRouter({ history: createWebHashHistory(), routes: [{path:'/items',component:StockManagerView}, {path:'/count',redirect:{path:'/items',query:{section:'count'}}}] }); createApp({render:()=>h(RouterView)}).use(pinia).use(router).mount('#app');
</script></body></html>`
const server = await createServer({ root, base: '/', server: { host: '127.0.0.1', port: 0, open: false }, plugins: [{ name: 'stock-manager-check', configureServer(s) {
  s.middlewares.use('/stock-manager-check.html', async (req, res) => { res.setHeader('Content-Type', 'text/html'); res.end(await s.transformIndexHtml('/stock-manager-check.html', html)) })
} }] })
await server.listen()
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
const errors = [], calls = [], transfers = new Map()
page.on('pageerror', error => errors.push(error.message))
page.on('dialog', dialog => dialog.accept())
await page.route('https://fonts.googleapis.com/**', route => route.abort())
await page.route('https://fonts.gstatic.com/**', route => route.abort())
let product = { name: 'FLW-001', item_name: 'Roses flower bouquet', stock_uom: 'Nos', item_group: 'Flowers', brand: 'Osaka', image: '', disabled: false, is_stock_item: true, is_sales_item: true, is_purchase_item: true, has_variants: false, variant_of: '' }
let template = { name: 'TSHIRT', item_name: 'Cotton T-shirt', stock_uom: 'Nos', has_variants: true, disabled: false }
let attributes = [{ name: 'Color', values: ['Red', 'Blue'] }, { name: 'Size', values: ['Small', 'Medium', 'Large'] }]
let variantRows = [{ name: 'TSHIRT-R-S', item_name: 'Cotton T-shirt Red Small', stock_uom: 'Nos', disabled: false }]
let quantity = 24, destination = 6, loseTransferResponse = true, rejectRetry = true, sellingPrice = 990, revision = 1, loseReceiptResponse = true
const receipts = new Map()
const stockSnapshot = () => ({ stock_uom: 'Nos', currency: 'LKR', can_adjust: true, can_transfer: true, can_receive: true, can_view_movements: true, rows: [
  { warehouse: 'Showroom - Shop', actual_qty: quantity, reserved_qty: 3, available_qty: quantity - 3 }, { warehouse: 'Main stores - Shop', actual_qty: destination, reserved_qty: 0, available_qty: destination }] })
const catalogSnapshot = () => ({ items: product.disabled ? [] : [{ ...product, item_code: product.name, price: sellingPrice, standard_price: sellingPrice, actual_qty: quantity }], removed: product.disabled ? [product.name] : [] })
function detail(code) {
  return { ...product, disabled: Boolean(product.disabled), is_sales_item: Boolean(product.is_sales_item), is_purchase_item: Boolean(product.is_purchase_item), item_code: code, ...(code.startsWith('TSHIRT-') ? { item_name: 'Cotton T-shirt Red Small', variant_of: 'TSHIRT' } : {}),
    description: '', can_edit_item: true, can_edit_prices: true, has_serial_no: false, has_batch_no: false,
    price_list: 'Retail', currency: 'LKR', barcodes: [{ barcode: '00999', uom: 'Nos' }],
    units: [{ uom: 'Nos', factor: 1, price: sellingPrice, active_price: sellingPrice, editable: true, has_explicit_price: true }] }
}
await page.route('**/api/method/**', async route => {
  const method = route.request().url().split('/').pop(), args = route.request().postDataJSON()
  calls.push({ method, args })
  let message
  if (method.endsWith('editor_options')) message = { can_create_items: true, can_edit_prices: true, can_view_stock: true, can_transfer_stock: true,
    item_groups: ['Flowers', 'Clothing'], brands: ['Osaka'], stock_uoms: ['Nos', 'Box'], uoms: ['Nos', 'Box'],
    price_lists: [{ name: 'Retail', currency: 'LKR' }], default_price_list: 'Retail', warehouses: ['Showroom - Shop', 'Main stores - Shop'] }
  else if (method.endsWith('search_items')) message = args.item_type === 'template' ? [template] :
    (args.status === 'disabled' && !product.disabled || args.status === 'active' && product.disabled) ? [] :
    [{ ...product, ...(args.include_stock ? { actual_qty: quantity + destination, reserved_qty: 3, available_qty: quantity + destination - 3 } : {}) }]
  else if (method.endsWith('item_details')) message = detail(args.item_code)
  else if (method.endsWith('save_item')) { product = { ...product, ...args }; if (args.prices?.length) sellingPrice = Number(args.prices[0].price); revision++; message = { ...detail(args.item_code), catalog: catalogSnapshot() } }
  else if (method.endsWith('catalog_sync.revision')) message = { revision: String(revision), direct_poll: false }
  else if (method.endsWith('catalog_sync.item_updates')) message = catalogSnapshot()
  else if (method.endsWith('warehouse_stock')) message = stockSnapshot()
  else if (method.endsWith('transfer_stock')) {
    if (!transfers.has(args.request_id)) { transfers.set(args.request_id, args); quantity -= Number(args.qty); destination += Number(args.qty) }
    if (loseTransferResponse) { loseTransferResponse = false; await route.abort(); return }
    if (rejectRetry) { rejectRetry = false; await route.fulfill({ status: 403, json: { exception: 'Transfer access temporarily unavailable', exc_type: 'PermissionError' } }); return }
    revision++; message = { name: 'POS-TRF-TEST-1', replayed: true, stock: stockSnapshot() }
  }
  else if (method.endsWith('receive_stock')) {
    if (!receipts.has(args.request_id)) { receipts.set(args.request_id, args); quantity += Number(args.qty); revision++ }
    if (loseReceiptResponse) { loseReceiptResponse = false; await route.abort(); return }
    message = { name: 'POS-RCV-TEST-1', replayed: true, stock: stockSnapshot() }
  }
  else if (method.endsWith('adjust_stock')) { quantity = Number(args.qty); revision++; message = { name: 'REC-TEST-1', stock: stockSnapshot() } }
  else if (method.endsWith('stock_movements')) message = [{ name: 'SLE-1', posting_date: '2026-11-26', warehouse: 'Showroom - Shop', actual_qty: -5, qty_after_transaction: quantity, voucher_type: 'Stock Entry', voucher_no: 'POS-TRF-TEST-1' }]
  else if (method.endsWith('item_variants.options')) message = { attributes, can_create: true, can_create_attribute: true }
  else if (method.endsWith('template_details')) message = { item_code: template.name, item_name: template.item_name, disabled: false, variant_based_on: 'Item Attribute', attributes: ['Color', 'Size'], variants: variantRows }
  else if (method.endsWith('create_attribute')) { attributes.push({ name: args.attribute_name, values: args.values.map(row => row.attribute_value) }); message = { name: args.attribute_name } }
  else if (method.endsWith('create_template')) { template = { ...template, name: args.item_code, item_name: args.item_name }; message = { item_code: args.item_code } }
  else if (method.endsWith('create_variant')) { variantRows.push({ name: 'TSHIRT-B-M', item_name: 'Cotton T-shirt Blue Medium', stock_uom: 'Nos', disabled: false }); message = { item_code: 'TSHIRT-B-M', existing: false } }
  else if (method.endsWith('count_setup')) message = { warehouses: ['Showroom - Shop'], warehouse: 'Showroom - Shop', shared: false, blind: false }
  else if (method.endsWith('count_lookup')) message = { found: true, item_code: product.name, item_name: product.item_name, has_serial_no: false, shelf: quantity }
  else if (method.endsWith('count_sessions')) message = []
  else throw new Error('Unexpected API: ' + method)
  await route.fulfill({ json: { message } })
})
const url = server.resolvedUrls.local[0] + 'stock-manager-check.html'
try {
  await page.goto(url + '#/items')
  await page.getByRole('tab', { name: 'Inventory & transfers' }).waitFor()
  assert.equal(await page.getByRole('tab').count(), 4)
  await page.getByRole('button', { name: /Roses flower bouquet/ }).click()
  await page.getByLabel('Disable item', { exact: true }).check()
  await page.getByRole('button', { name: 'Save changes', exact: true }).click()
  await page.getByText('This item is disabled.', { exact: false }).waitFor()
  assert.equal(calls.findLast(call => call.method.endsWith('save_item')).args.disabled, 1)
  await page.getByLabel('Disable item', { exact: true }).uncheck()
  await page.getByRole('button', { name: 'Save changes', exact: true }).click()
  await page.waitForFunction(() => window.notices.filter(text => text === 'Item saved').length === 2)
  await page.locator('.items-page').evaluate(element => { element.scrollTop = 0 })
  await page.screenshot({ path: path.join(output, 'item-details-desktop.png'), fullPage: true })

  await page.getByRole('tab', { name: 'Inventory & transfers' }).click()
  await page.getByLabel('To warehouse').selectOption('Main stores - Shop')
  await page.getByLabel('Transfer quantity', { exact: true }).fill('5')
  await page.getByLabel('Transfer reason', { exact: true }).fill('Move five bouquets to main stores')
  await page.getByRole('button', { name: 'Post transfer', exact: true }).click()
  await page.getByRole('button', { name: 'Check and retry transfer', exact: true }).waitFor()
  assert.equal(transfers.size, 1)
  // Recover the identity across a reload after a lost response.
  await page.goto(url + '#/items?section=inventory&item=FLW-001')
  await page.reload()
  await page.getByRole('button', { name: 'Check and retry transfer', exact: true }).click()
  await page.waitForFunction(() => window.notices.length > 0)
  assert.equal(await page.getByLabel('Transfer quantity', { exact: true }).isDisabled(), true)
  await page.getByRole('button', { name: 'Check and retry transfer', exact: true }).click()
  await page.getByText('Posted successfully', { exact: false }).waitFor()
  assert.equal(transfers.size, 1)
  const transferCalls = calls.filter(call => call.method.endsWith('transfer_stock'))
  assert.equal(transferCalls.length, 3)
  assert.equal(transferCalls[0].args.request_id, transferCalls[1].args.request_id)
  assert.equal(transferCalls[1].args.request_id, transferCalls[2].args.request_id)
  assert.equal(quantity, 19)
  await page.screenshot({ path: path.join(output, 'inventory-desktop.png'), fullPage: true })
  await page.getByRole('button', { name: 'Stock movements', exact: true }).click()
  await page.getByRole('cell', { name: '-5', exact: true }).waitFor()
  await page.getByRole('button', { name: 'Adjust stock', exact: true }).click()
  await page.getByLabel('New on-hand quantity', { exact: true }).fill('20')
  await page.getByLabel('Reason', { exact: true }).fill('Verified shelf quantity')
  await page.getByRole('button', { name: 'Post stock adjustment', exact: true }).click()
  await page.getByRole('link', { name: 'REC-TEST-1' }).waitFor()
  assert.equal(quantity, 20)

  await page.getByRole('tab', { name: 'Variants', exact: true }).click()
  await page.getByRole('button', { name: /Cotton T-shirt TSHIRT/ }).click()
  await page.getByLabel('Color').selectOption('Blue')
  await page.getByLabel('Size').selectOption('Medium')
  await page.getByRole('button', { name: 'Create variant', exact: true }).click()
  await page.getByText('Cotton T-shirt Blue Medium', { exact: true }).waitFor()
  await page.screenshot({ path: path.join(output, 'variants-desktop.png'), fullPage: true })
  await page.getByRole('button', { name: 'New attribute', exact: true }).click()
  await page.getByLabel('Attribute name', { exact: true }).fill('Fabric')
  await page.getByLabel('Values and abbreviations', { exact: true }).fill('Cotton=COT\nLinen=LIN')
  await page.getByRole('button', { name: 'Create attribute', exact: true }).click()
  await page.waitForFunction(() => window.notices.includes('Attribute created'))
  await page.getByRole('button', { name: 'New template', exact: true }).click()
  await page.getByLabel('Template code', { exact: true }).fill('POLO')
  await page.getByLabel('Item name', { exact: true }).last().fill('Polo shirt')
  await page.getByLabel('Category').last().selectOption('Clothing')
  await page.getByLabel('Stock unit').selectOption('Nos')
  await page.getByLabel('Color', { exact: true }).check()
  await page.getByLabel('Size', { exact: true }).check()
  await page.getByRole('button', { name: 'Create template', exact: true }).click()
  await page.getByRole('heading', { name: 'Polo shirt', exact: true }).waitFor()

  await page.getByRole('tab', { name: 'Stock count', exact: true }).click()
  const scan = page.getByPlaceholder('Scan a barcode or a serial number, or search for an item…')
  await scan.fill('00999'); await scan.press('Enter')
  await page.locator('.count .rt tbody tr').waitFor()
  await page.getByRole('tab', { name: 'Item details', exact: true }).click()
  await page.getByRole('tab', { name: 'Stock count', exact: true }).click()
  assert.equal(await page.locator('.count .rt tbody tr').count(), 1)
  assert.equal(calls.filter(call => call.method.endsWith('count_setup')).length, 1)
  await page.screenshot({ path: path.join(output, 'count-desktop.png'), fullPage: true })
  await page.getByRole('tab', { name: 'Item details', exact: true }).focus()
  await page.keyboard.press('End')
  assert.equal(await page.getByRole('tab', { name: 'Stock count', exact: true }).getAttribute('aria-selected'), 'true')

  for (const section of ['Item details', 'Inventory & transfers', 'Variants', 'Stock count']) {
    await page.setViewportSize({ width: 390, height: 1000 })
    await page.getByRole('tab', { name: section, exact: true }).click()
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, section + ' page overflow')
    await page.screenshot({ path: path.join(output, section.split(' ')[0].toLowerCase() + '-mobile.png'), fullPage: true })
  }
  // Changes made outside this POS are discovered through commit-marker polling.
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.getByRole('tab', { name: 'Item details', exact: true }).click()
  sellingPrice = 1250; revision++
  const priceInput = page.locator('.unit-price-row input[type="number"]').last()
  await priceInput.waitFor()
  await page.waitForFunction(() => document.querySelector('.unit-price-row input[placeholder="Selling price"]')?.value === '1250', null, { timeout: 10000 })
  assert.equal(await page.evaluate(() => window.test.catalog.items[0].price), 1250)
  await priceInput.fill('1375')
  sellingPrice = 1490; revision++
  await page.getByText('ERPNext has newer values.', { exact: false }).waitFor({ timeout: 10000 })
  assert.equal(await priceInput.inputValue(), '1375')
  await page.getByRole('button', { name: 'Save changes', exact: true }).click()
  await page.waitForFunction(() => window.test.catalog.items[0].price === 1375)
  assert.equal(sellingPrice, 1375)
  await page.waitForFunction(async () => (await window.test.getCatalogItems(['FLW-001']))[0]?.price === 1375)
  await page.getByRole('tab', { name: 'Inventory & transfers' }).click()
  quantity = 38; revision++
  await page.waitForFunction(() => document.querySelector('.stock-table tbody tr td')?.textContent === '38', null, { timeout: 10000 })
  await page.getByRole('button', { name: 'Add to warehouse', exact: true }).click()
  await page.getByLabel('Quantity received', { exact: true }).fill('10')
  await page.getByLabel('Unit cost').fill('400')
  await page.getByLabel('Receipt reason / reference', { exact: true }).fill('Supplier delivery REF-103')
  await page.locator('.items-page').evaluate(element => { element.scrollTop = 0 })
  await page.screenshot({ path: path.join(output, 'material-receipt-desktop.png'), fullPage: true })
  await page.getByRole('button', { name: 'Post Material Receipt', exact: true }).click()
  await page.getByRole('button', { name: 'Check and retry receipt', exact: true }).waitFor()
  await page.reload()
  await page.getByRole('button', { name: 'Check and retry receipt', exact: true }).click()
  await page.getByRole('link', { name: 'POS-RCV-TEST-1' }).waitFor()
  assert.equal(quantity, 48); assert.equal(receipts.size, 1)
  const receiptCalls = calls.filter(call => call.method.endsWith('receive_stock'))
  assert.equal(receiptCalls.length, 2); assert.equal(receiptCalls[0].args.request_id, receiptCalls[1].args.request_id)
  assert.equal(await page.locator('.stock-table tbody tr').first().locator('td').first().textContent(), '48')
  await page.setViewportSize({ width: 390, height: 1000 })
  await page.getByLabel('Quantity received', { exact: true }).fill('4')
  await page.getByLabel('Unit cost').fill('400')
  await page.getByLabel('Receipt reason / reference', { exact: true }).fill('Incoming delivery')
  await page.locator('.receipt-form').screenshot({ path: path.join(output, 'material-receipt-mobile.png') })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  const cartAfterSync = await page.evaluate(() => {
    const cart = window.test.cart
    cart.lines = [{ item_code: 'FLW-001', qty: 2, price: 88, price_override: 88, manual_discount_percent: 5, selling_uom: 'Box', conversion_factor: 10 }]
    cart.applyCatalogUpdate([{ item_code: 'FLW-001', item_name: 'Updated bouquet', price: 1375, actual_qty: 48, selling_units: [{ uom: 'Box', price: 13000 }] }])
    return JSON.parse(JSON.stringify(cart.lines[0]))
  })
  assert.equal(cartAfterSync.price, 88); assert.equal(cartAfterSync.price_override, 88)
  assert.equal(cartAfterSync.qty, 2); assert.equal(cartAfterSync.manual_discount_percent, 5)
  assert.equal(cartAfterSync.catalog_price, 13000); assert.equal(cartAfterSync.actual_qty, 48)
  await page.evaluate(() => { window.test.session.permissions = { stock_count: true } })
  assert.equal(await page.getByRole('tab').count(), 1)
  assert.equal(await page.getByRole('tab').textContent(), 'Stock count')
  await page.goto(url + '#/count')
  await page.waitForURL('**#/items?section=count')
  assert.deepEqual(errors, [])
  console.log('Stock manager browser checks passed: Material Receipt/reload recovery, live ERPNext price/stock changes, dirty-edit preservation, immediate saved prices and IndexedDB, existing manager flows, permissions and desktop/mobile layouts.')
} catch (error) {
  console.error({ errors, calls: calls.slice(-6), body: (await page.locator('body').innerText()).slice(0, 3000) })
  await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true })
  throw error
} finally { await browser.close(); await server.close() }
