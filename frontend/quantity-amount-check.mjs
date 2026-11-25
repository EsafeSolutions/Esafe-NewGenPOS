// Sell actual items by amount through the popup and cart; APIs are local fixtures.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
import { quantityAmount, quantityFromAmount } from './src/quantityAmount.js'

for (const [amount, price, whole, quantity] of [
  [500, 1000, false, 0.5], ['1,500', 1000, false, 1.5], ['٥٠٠', 1000, false, 0.5],
  ['12,50', 25, false, 0.5], [9000, 4500, true, 2], [333.33, 1000, false, 0.3333],
  [5, 1000 / 30, false, 0.15],
]) assert.equal(quantityFromAmount(amount, price, whole).quantity, quantity)
for (const [amount, price, whole, error] of [
  ['', 1000, false, 'amount'], ['oops', 1000, false, 'amount'], [-1, 1000, false, 'amount'],
  [0, 1000, false, 'amount'], [500, 0, false, 'price'], [500, Infinity, false, 'price'],
  [0.09, 1000, false, 'small'], [2250, 4500, true, 'whole'], [Infinity, 1000, false, 'amount'],
  [1e20, 1, false, 'large'],
]) assert.equal(quantityFromAmount(amount, price, whole).error, error)
assert.equal(quantityAmount(0.3333, 1000), 333.3)
console.log('PASS amount arithmetic, localized input, minimum quantity and whole-unit boundaries')

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
const root = path.dirname(fileURLToPath(import.meta.url))
const output = path.join(root, '../docs/screenshots/quantity-amount')
await mkdir(output, { recursive: true })
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>
<header style="height:48px;background:var(--pos-blue);color:white;display:flex;align-items:center;justify-content:space-between;padding:0 16px"><b>ESAFE ERP POS / Sell</b><span>Weerakoon Agro</span><div id="sell-header-tools"></div></header><div id="app" style="height:calc(100dvh - 48px);display:flex"></div><script type="module">
import { createApp } from 'vue'; import { createPinia } from 'pinia'; import { createRouter, createMemoryHistory } from 'vue-router';
import SellView from '/src/views/SellView.vue'; import { useCartStore } from '/src/stores/cart.js'; import { useSessionStore } from '/src/stores/session.js'; import { useCatalogStore } from '/src/stores/catalog.js'; import { setCurrency } from '/src/format.js'; import '/src/styles.css';
const pinia = createPinia(), session = useSessionStore(pinia), catalog = useCatalogStore(pinia), cart = useCartStore(pinia);
session.currency='LKR'; session.posProfile='Till'; session.priceList='Retail'; session.company='Shop'; session.registerSession={name:'REG'}; setCurrency('LKR'); session.permissions={can_edit_price:true,can_change_price:true}; session.notify=message=>window.notices.push(message); window.notices=[];
const item={item_code:'FEED',item_name:'[Super Feed] premium dog food',description:'Sell loose by weight or choose a pack.',stock_uom:'Kg',whole_qty:false,price:1000,actual_qty:500,is_stock_item:1,selling_units:[{uom:'25 kg Pack',factor:25,price:4500,whole_qty:true}]}; catalog.items=[item]; catalog.fetch=async()=>{}; cart.prefetchQuote=()=>{};
const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',component:SellView}]}); await router.push('/'); await router.isReady(); createApp(SellView).use(pinia).use(router).mount('#app'); window.test={cart,session,catalog,item}; window.ready=true;
</script></body></html>`
const server = await createServer({ root, base: '/', server: { port: 0, host: '127.0.0.1', open: false }, plugins: [{ name: 'quantity-amount-check', configureServer(s) {
  s.middlewares.use('/quantity-amount-check.html', async (req, res) => { res.setHeader('Content-Type', 'text/html'); res.end(await s.transformIndexHtml('/quantity-amount-check.html', html)) })
} }] })
await server.listen()
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe' })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
page.setDefaultTimeout(15000)
const errors = [], calls = []
let customerPrice = 600, failPrices = false, holdPrices = null, releasePrices
page.on('pageerror', error => errors.push(error.message))
await page.route('https://fonts.googleapis.com/**', route => route.abort())
await page.route('https://fonts.gstatic.com/**', route => route.abort())
await page.route('**/api/method/**', async route => {
  const method = route.request().url().split('/').pop(), args = route.request().postDataJSON()
  calls.push({ method, args })
  let message = {}
  if (method.endsWith('get_prices')) {
    if (holdPrices) await holdPrices
    if (failPrices) { await route.fulfill({ status: 500, json: { exception: 'ValidationError: Price list unavailable' } }); return }
    message = { price_list: args.customer ? 'Customer list' : 'Retail', prices: { FEED: args.customer ? customerPrice : 1000 },
      standard_prices: { FEED: 1000 }, selling_units: { FEED: { '25 kg Pack': args.customer ? 4000 : 4500 } } }
  }
  await route.fulfill({ json: { message } })
})
const dialog = page.getByRole('dialog', { name: '[Super Feed] premium dog food', exact: true })
const popupAmount = () => dialog.getByLabel('Amount (LKR)', { exact: true })
const popupQty = () => dialog.getByLabel('Quantity (Kg)', { exact: true })
const openItem = async () => { await page.locator('.tile-main').first().click(); await dialog.waitFor() }
const cartQuantity = () => page.evaluate(() => test.cart.lines[0].qty)
try {
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/quantity-amount-check.html`)
  await page.waitForFunction(() => window.ready)
  await openItem()
  await popupAmount().fill('')
  await popupAmount().pressSequentially('500')
  assert.equal(await popupAmount().inputValue(), '500')
  assert.equal(await popupQty().inputValue(), '0.5')
  assert.equal(await dialog.getByLabel('Unit price (LKR)', { exact: true }).inputValue(), '1000')
  await page.screenshot({ path: path.join(output, 'popup-desktop.png'), fullPage: true })
  await dialog.getByRole('button', { name: 'Add to cart', exact: true }).click()
  assert.equal(await cartQuantity(), 0.5)
  assert.equal(await page.evaluate(() => test.cart.lines[0].price_override ?? null), null)
  assert.equal(await page.evaluate(() => test.cart.total), 500)

  await page.locator('.line-main').first().click()
  const cartAmount = page.getByLabel('Amount (LKR)', { exact: true })
  await cartAmount.fill('250')
  assert.equal(await cartQuantity(), 0.25)
  await page.getByLabel('Quantity (Kg)', { exact: true }).fill('0.75')
  await page.getByLabel('Quantity (Kg)', { exact: true }).press('Tab')
  assert.equal(await cartAmount.inputValue(), '750')
  await page.getByLabel('Unit price (LKR)', { exact: true }).fill('1200')
  await page.getByLabel('Unit price (LKR)', { exact: true }).press('Tab')
  assert.equal(await cartAmount.inputValue(), '900')
  await cartAmount.fill('600')
  assert.equal(await cartQuantity(), 0.5)
  assert.equal(await page.evaluate(() => test.cart.lines[0].price_override), 1200)
  await page.locator('#line-discount-0').fill('10')
  assert.equal(await page.evaluate(() => test.cart.total), 540)
  assert.equal(await cartAmount.inputValue(), '600')
  await page.evaluate(() => { test.session.permissions = {can_edit_price:false,can_change_price:false} })
  assert.equal(await page.getByLabel('Unit price (LKR)', { exact: true }).isDisabled(), true)
  await cartAmount.fill('300')
  assert.equal(await cartQuantity(), 0.25)
  for (const value of ['', 'oops', '-1', '0', '0.01']) {
    await cartAmount.fill(value)
    assert.equal(await cartQuantity(), 0.25)
    assert.equal(await cartAmount.getAttribute('aria-invalid'), 'true')
  }
  await cartAmount.fill('600')
  await page.screenshot({ path: path.join(output, 'cart-desktop.png'), fullPage: true })

  // Popup editing changes only the selected line's quantity; invalid drafts cannot be saved.
  await openItem()
  assert.equal(await popupAmount().inputValue(), '600')
  await popupAmount().fill('bad')
  assert.equal(await dialog.getByRole('button', { name: 'Update cart', exact: true }).isDisabled(), true)
  await popupAmount().fill('300')
  await dialog.getByRole('button', { name: 'Update cart', exact: true }).click()
  assert.equal(await cartQuantity(), 0.25)
  await openItem()
  await popupAmount().fill('999999')
  await dialog.getByRole('button', { name: 'Update cart', exact: true }).click()
  assert.equal(await dialog.isVisible(), true)
  assert.equal(await cartQuantity(), 0.25)
  assert.match(await page.evaluate(() => window.notices.at(-1)), /only 500 in stock/)
  await dialog.getByRole('button', { name: 'Cancel', exact: true }).click()

  // Whole selling units reject partial packs and preserve stock conversion factors.
  await page.evaluate(() => { test.cart.clear(); test.session.permissions={can_edit_price:true,can_change_price:true} })
  await openItem()
  await dialog.getByLabel('Unit price (LKR)', { exact: true }).fill('0')
  assert.equal(await popupAmount().isDisabled(), true)
  await dialog.getByLabel('Unit price (LKR)', { exact: true }).fill('1000')
  await dialog.getByLabel('Selling unit').selectOption('25 kg Pack')
  await popupAmount().fill('2250')
  await dialog.getByRole('alert').waitFor()
  assert.equal(await dialog.getByLabel('Quantity (25 kg Pack)').inputValue(), '1')
  await popupAmount().fill('9000')
  assert.equal(await dialog.getByLabel('Quantity (25 kg Pack)').inputValue(), '2')
  await dialog.getByRole('button', { name: 'Add to cart', exact: true }).click()
  assert.deepEqual(await page.evaluate(() => [test.cart.lines[0].qty, test.cart.lines[0].conversion_factor, test.cart._basePayload().items[0].uom]), [2, 25, '25 kg Pack'])
  await page.locator('.line-main').first().click()
  await cartAmount.fill('13500')
  assert.equal(await cartQuantity(), 3)

  // Customer pricing is fetched before calculating a new popup quantity.
  await page.evaluate(() => { test.cart.clear(); test.cart.customer={name:'CUSTOMER',customer_group:'Individual',default_currency:'LKR'} })
  holdPrices = new Promise(resolve => { releasePrices = resolve })
  await openItem()
  assert.equal(await popupAmount().isDisabled(), true)
  releasePrices(); holdPrices = null
  await page.waitForFunction(() => document.querySelector('.item-detail input[id="item-quantity-amount"]').value === '600')
  await popupAmount().fill('300')
  assert.equal(await popupQty().inputValue(), '0.5')
  holdPrices = new Promise(resolve => { releasePrices = resolve })
  await dialog.getByRole('button', { name: 'Add to cart', exact: true }).click()
  assert.equal(await page.evaluate(() => test.cart.lines[0].price), 600)
  assert.equal(await page.evaluate(() => test.cart.total), 300)
  releasePrices(); holdPrices = null
  await page.waitForFunction(() => !test.cart._pricePending)
  await page.locator('.line-main').first().click()
  customerPrice = 800
  holdPrices = new Promise(resolve => { releasePrices = resolve })
  await page.evaluate(() => { test.cart.reprice() })
  assert.equal(await cartAmount.isDisabled(), true)
  releasePrices(); holdPrices = null
  await page.waitForFunction(() => !test.cart._pricePending && test.cart.lines[0].price === 800)
  await cartAmount.fill('400')
  assert.equal(await cartQuantity(), 0.5)
  failPrices = true
  await openItem()
  await dialog.getByRole('alert').waitFor()
  assert.equal(await dialog.getByRole('button', { name: 'Update cart', exact: true }).isDisabled(), true)
  failPrices = false
  await dialog.getByRole('button', { name: 'Retry', exact: true }).click()
  await page.waitForFunction(() => !document.querySelector('.item-detail button[type="submit"]').disabled)
  await dialog.getByRole('button', { name: 'Cancel', exact: true }).click()

  // Minimum-quantity rounding is shown, with amounts and quantity synced on blur.
  await page.evaluate(() => { test.cart.clear() })
  customerPrice = 1000
  await openItem()
  await page.waitForFunction(() => document.querySelector('#item-quantity-amount').value === '1000')
  await popupAmount().fill('333.33')
  assert.equal(await popupQty().inputValue(), '0.3333')
  await dialog.getByText(/Quantity rounds to/).waitFor()
  await popupAmount().press('Tab')
  assert.equal(await popupAmount().inputValue(), '333.3')
  for (const width of [1024, 768, 390]) {
    await page.setViewportSize({ width, height: 940 })
    const box = await popupAmount().boundingBox()
    assert.ok(box.x >= 0 && box.x + box.width <= width)
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    if (width === 390) await page.screenshot({ path: path.join(output, 'popup-mobile.png'), fullPage: true })
  }
  await dialog.getByRole('button', { name: 'Add to cart', exact: true }).click()
  await page.locator('.line-main').first().click()
  await cartAmount.scrollIntoViewIfNeeded()
  await page.screenshot({ path: path.join(output, 'cart-mobile.png'), fullPage: true })

  // The divisor uses the precise active sale-currency rate, even if its label rounds.
  await page.evaluate(() => {
    test.cart.customer = {name:'FOREIGN',default_currency:'USD'}
    test.session.multiCurrency={enabled:1,outlet_currency:'LKR',outlet_rate:1,currencies:[{currency:'USD',rate:30}]}
    test.cart.lines[0].price=1000
  })
  await page.getByLabel('Amount (USD)', { exact: true }).fill('5')
  assert.equal(await cartQuantity(), 0.15)
  await openItem()
  await dialog.getByLabel('Amount (USD)', { exact: true }).fill('5')
  assert.equal(await popupQty().inputValue(), '0.15')
  await dialog.getByRole('button', { name: 'Update cart', exact: true }).click()
  assert.equal(await cartQuantity(), 0.15)

  // Offline plain loose sales retain the calculated quantity in their receipt.
  await page.evaluate(() => { test.cart.customer=null; test.session.multiCurrency={enabled:0}; test.session.offline=true })
  await cartAmount.fill('500')
  const receipt = await page.evaluate(async () => test.cart._queueOffline(test.cart._basePayload(), [{mode_of_payment:'Cash',amount:500}]))
  assert.equal(receipt.items[0].qty, 0.5)
  assert.equal(receipt.grand_total, 500)

  // Serial quantities and complete bundle recipes have no independent amount control.
  await page.evaluate(() => { test.cart.clear(); test.cart.addItem({...test.item,has_serial_no:1},'SERIAL-1') })
  await page.locator('.line-main').first().click()
  assert.equal(await page.locator('.line-edit .quantity-amount').count(), 0)
  await page.evaluate(() => { test.cart.lines[0].has_serial_no=0; test.cart.lines[0].bundle_key='BUNDLE'; test.cart.lines[0].bundle_qty=1 })
  assert.equal(await page.locator('.line-edit .quantity-amount').count(), 0)
  assert.deepEqual(errors, [])
  console.log('PASS popup/cart amount entry, unchanged prices, discounts/permissions, whole UOM, customer price retry, rounding, FX, offline receipt, serial/bundle rules and responsive layouts')
} finally {
  releasePrices?.()
  await browser.close()
  await server.close()
}
