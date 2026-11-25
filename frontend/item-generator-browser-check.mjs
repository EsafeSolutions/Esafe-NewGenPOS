// Actual Items forms against simulated APIs; no live Item is created or changed.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
const root = path.dirname(fileURLToPath(import.meta.url))
const output = path.join(root, '../docs/screenshots/item-generator')
await mkdir(output, { recursive: true })
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><div id="app"></div><script type="module">
import { createApp } from 'vue'; import { createPinia } from 'pinia'; import ItemsView from '/src/views/ItemsView.vue'; import { useSessionStore } from '/src/stores/session.js'; import { useCatalogStore } from '/src/stores/catalog.js'; import { useCartStore } from '/src/stores/cart.js'; import '/src/styles.css';
const pinia = createPinia(), session = useSessionStore(pinia); session.user = 'manager'; session.posProfile = 'Till A'; session.permissions = { edit_items: true }; session.notify = (message) => window.notices.push(message); window.notices = []; const catalog = useCatalogStore(pinia); catalog.fetch = async () => {}; catalog.cacheFullCatalog = async () => {}; useCartStore(pinia).reprice = async () => {}; window.test = { session }; createApp(ItemsView).use(pinia).mount('#app');
</script></body></html>`
const server = await createServer({ root, base: '/', server: { host: '127.0.0.1', port: 0, open: false }, plugins: [{ name: 'item-generator-check', configureServer(s) {
  s.middlewares.use('/item-generator-check.html', async (req, res) => { res.setHeader('Content-Type', 'text/html'); res.end(await s.transformIndexHtml('/item-generator-check.html', html)) })
} }] })
await server.listen()
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
const errors = [], calls = []
page.on('pageerror', error => errors.push(error.message))
await page.route('https://fonts.googleapis.com/**', route => route.abort())
await page.route('https://fonts.gstatic.com/**', route => route.abort())
let generationFailure = false, holdGeneration = null, generated = 122, saved = null
const item = () => ({
  item_code: saved?.item_code || 'ITEM-A', item_name: saved?.item_name || 'Sample item', stock_uom: 'Nos',
  item_group: 'Products', brand: '', image: '', price_list: 'Retail', currency: 'LKR',
  can_edit_item: true, can_edit_prices: false, has_serial_no: false,
  units: [{ uom: 'Nos', factor: 1, price: 100, active_price: 100, editable: false }],
  barcodes: saved ? JSON.parse(saved.barcodes) : [{ barcode: '00999', uom: 'Nos' }],
})
await page.route('**/api/method/**', async route => {
  const method = route.request().url().split('/').pop(), args = route.request().postDataJSON()
  calls.push({ method, args })
  let message = []
  if (method.endsWith('editor_options')) message = {
    can_create_items: true, can_edit_prices: false, can_view_stock: false,
    item_groups: ['Products'], stock_uoms: ['Nos', 'Box'], uoms: ['Nos', 'Box'], brands: [], price_lists: [],
  }
  else if (method.endsWith('search_items')) message = [{ name: saved?.item_code || 'ITEM-A', item_name: saved?.item_name || 'Sample item', stock_uom: 'Nos', item_group: 'Products' }]
  else if (method.endsWith('generate_identifier')) {
    if (holdGeneration) await holdGeneration
    if (generationFailure) {
      await route.fulfill({ status: 409, json: { exception: 'ValidationError: No unused code was found at this length. Increase the length or try again.' } })
      return
    }
    const counter = String(++generated).padStart(args.length, '0')
    message = { value: args.character_type === 'numeric' ? counter.slice(-args.length) : `A${counter.slice(-(args.length - 1))}` }
  }
  else if (method.endsWith('create_item')) { saved = args; message = { item_code: args.item_code } }
  else if (method.endsWith('item_details') || method.endsWith('save_item')) message = item()
  await route.fulfill({ json: { message } })
})
const generationCalls = () => calls.filter(call => call.method.endsWith('generate_identifier'))
try {
  const url = `http://127.0.0.1:${server.httpServer.address().port}/item-generator-check.html`
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 })
  await page.getByRole('button', { name: 'Add item', exact: true }).click()
  const code = page.locator('.create-item .identifier-field').nth(0)
  const barcode = page.locator('.create-item .identifier-field').nth(1)
  assert.equal(await code.getByLabel('Digits', { exact: true }).inputValue(), '5')
  await code.getByRole('button', { name: 'Generate item code', exact: true }).click()
  await page.waitForFunction(() => document.querySelector('.create-item .identifier-field input').value === '00123')
  assert.equal(generationCalls().at(-1).args.character_type, 'numeric')
  assert.equal(generationCalls().at(-1).args.length, 5)

  await barcode.getByLabel('Code type').selectOption('alphanumeric')
  await barcode.getByLabel('Characters', { exact: true }).fill('8')
  await barcode.getByRole('button', { name: 'Generate barcode', exact: true }).click()
  await page.waitForFunction(() => document.querySelectorAll('.create-item .identifier-field')[1].querySelector('input').value.length === 8)
  assert.match(await barcode.getByLabel('Barcode (optional)', { exact: true }).inputValue(), /^(?=.*[A-Z])(?=.*[0-9])[A-Z0-9]{8}$/)
  assert.deepEqual(JSON.parse(generationCalls().at(-1).args.exclude), ['00123'])
  await barcode.getByLabel('Code type').selectOption('numeric')
  await barcode.getByLabel('Digits', { exact: true }).fill('5')
  await barcode.getByRole('button', { name: 'Generate barcode', exact: true }).click()
  await page.waitForFunction(() => document.querySelectorAll('.create-item .identifier-field')[1].querySelector('input').value === '00125')

  for (const invalid of ['0', '141', '2.5', '']) {
    await code.getByLabel('Digits', { exact: true }).fill(invalid)
    assert.equal(await code.getByRole('button').isDisabled(), true)
  }
  await code.getByLabel('Digits', { exact: true }).fill('1')
  await code.getByLabel('Code type').selectOption('alphanumeric')
  assert.equal(await code.getByLabel('Characters', { exact: true }).inputValue(), '2')
  await code.getByLabel('Code type').selectOption('numeric')
  await code.getByLabel('Digits', { exact: true }).fill('5')
  await page.getByLabel('Item name', { exact: true }).fill('Sample product')
  await page.locator('.create-item').getByLabel('Category').selectOption('Products')
  await page.locator('.create-item').getByLabel('Stock unit').first().selectOption('Nos')
  await page.screenshot({ path: path.join(output, 'create-desktop.png'), fullPage: true })
  for (const width of [1024, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    assert.equal(await page.locator('.items-page').evaluate(el => el.scrollWidth <= el.clientWidth), true)
    if (width === 390) {
      await page.locator('.create-item').scrollIntoViewIfNeeded()
      await page.locator('.create-item').screenshot({ path: path.join(output, 'create-mobile.png') })
    }
  }

  // Failed generation keeps the current value and exposes a retryable error.
  generationFailure = true
  await code.getByRole('button').click()
  await code.getByRole('alert').waitFor()
  assert.match(await code.getByRole('alert').innerText(), /Increase the length/)
  assert.equal(await code.getByLabel('Item code', { exact: true }).inputValue(), '00123')
  generationFailure = false

  // Saving waits until an in-flight generator has returned its string value.
  let release
  holdGeneration = new Promise(resolve => { release = resolve })
  await code.getByRole('button').click()
  await code.getByRole('button', { name: 'Generating…', exact: true }).waitFor()
  assert.equal(await page.getByRole('button', { name: 'Create item', exact: true }).isDisabled(), true)
  release(); holdGeneration = null
  await page.waitForFunction(() => document.querySelector('.create-item .identifier-field input').value === '00126')
  await page.getByRole('button', { name: 'Create item', exact: true }).click()
  await page.locator('.edit-item').waitFor()
  assert.equal(saved.item_code, '00126')
  assert.equal(saved.barcode, '00125')
  assert.equal(JSON.parse(saved.barcodes)[0].barcode, '00125')

  // Existing item barcodes use the same controls and exclude all unsaved rows.
  const existing = page.locator('.barcode-row .identifier-field').first()
  await existing.getByLabel('Code type').selectOption('alphanumeric')
  await existing.getByLabel('Characters', { exact: true }).fill('7')
  await existing.getByRole('button').click()
  await page.waitForFunction(() => document.querySelector('.barcode-row input').value.startsWith('A'))
  assert.equal(generationCalls().at(-1).args.item_code, '00126')
  assert.deepEqual(JSON.parse(generationCalls().at(-1).args.exclude), ['00126', '00125'])
  await page.getByRole('button', { name: 'Add barcode', exact: true }).click()
  const second = page.locator('.barcode-row .identifier-field').nth(1)
  assert.equal(await second.getByLabel('Characters', { exact: true }).inputValue(), '7')
  await second.getByRole('button').click()
  await page.waitForFunction(() => document.querySelectorAll('.barcode-row')[1].querySelector('input').value.startsWith('A'))
  assert.equal(JSON.parse(generationCalls().at(-1).args.exclude).includes(await existing.getByLabel('Barcode', { exact: true }).inputValue()), true)
  await page.setViewportSize({ width: 1440, height: 1100 })
  await page.screenshot({ path: path.join(output, 'edit-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 1000 })
  await page.locator('.barcode-row').first().screenshot({ path: path.join(output, 'edit-mobile.png') })
  assert.equal(await page.locator('.items-page').evaluate(el => el.scrollWidth <= el.clientWidth), true)
  await page.getByRole('button', { name: 'Save changes', exact: true }).click()
  await page.waitForFunction(() => window.notices.includes('Item saved'))
  assert.match(JSON.parse(calls.findLast(call => call.method.endsWith('save_item')).args.barcodes)[1].barcode, /^[A-Z0-9]{7}$/)

  // Preferences survive a new form; offline generation cannot issue API calls.
  await page.getByRole('button', { name: 'Add item', exact: true }).click()
  assert.equal(await barcode.getByLabel('Characters', { exact: true }).inputValue(), '7')

  // Other fields may change while a request is running; never insert a now-duplicate value.
  await code.getByLabel('Item code', { exact: true }).fill('KEEP')
  holdGeneration = new Promise(resolve => { release = resolve })
  await code.getByRole('button').click()
  await code.getByRole('button', { name: 'Generating…', exact: true }).waitFor()
  await barcode.getByLabel('Barcode (optional)', { exact: true }).fill('00129')
  release(); holdGeneration = null
  await code.getByRole('alert').waitFor()
  assert.match(await code.getByRole('alert').innerText(), /already used in this form/)
  assert.equal(await code.getByLabel('Item code', { exact: true }).inputValue(), 'KEEP')

  // Switching outlets discards the old result and loads the new outlet's defaults.
  holdGeneration = new Promise(resolve => { release = resolve })
  await code.getByRole('button').click()
  await code.getByRole('button', { name: 'Generating…', exact: true }).waitFor()
  const oldResponse = page.waitForResponse(response => response.url().endsWith('generate_identifier'))
  await page.evaluate(() => {
    localStorage.setItem('esafepos-code-generator:Till B:item_code', '{invalid json')
    window.test.session.posProfile = 'Till B'
  })
  await page.getByRole('button', { name: 'Add item', exact: true }).click()
  release(); holdGeneration = null
  await oldResponse
  assert.equal(await code.getByLabel('Item code', { exact: true }).inputValue(), '')
  assert.equal(await code.getByLabel('Digits', { exact: true }).inputValue(), '5')
  assert.equal(await barcode.getByLabel('Digits', { exact: true }).inputValue(), '5')
  const beforeOffline = generationCalls().length
  await page.evaluate(() => { window.test.session.offline = true })
  await page.getByText('Editing items needs a connection.', { exact: true }).waitFor()
  assert.equal(generationCalls().length, beforeOffline)
  assert.deepEqual(errors, [])
  console.log('Item generator browser checks passed: numeric/mixed formats, length validation, leading zeroes, exclusions, errors, busy/save guards, stored preferences, corrupt storage, stale requests, outlet changes, existing item barcodes, offline, and desktop/mobile layouts.')
} catch (error) {
  console.error({ pageErrors: errors, body: (await page.locator('body').innerText()).slice(0, 1200) })
  throw error
} finally {
  await browser.close()
  await server.close()
}
