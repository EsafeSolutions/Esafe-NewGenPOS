// Actual Customers view and cart against simulated APIs; no live records change.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
const root = path.dirname(fileURLToPath(import.meta.url))
const output = path.join(root, '../docs/screenshots/customers')
await mkdir(output, { recursive: true })
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>
#app{display:flex;flex-direction:column} .check-header{background:var(--pos-blue);color:white;padding:16px 20px;font-weight:700;display:flex;justify-content:space-between;gap:12px} .check-main{display:flex;flex:1;min-height:0} @media(max-width:700px){.check-header{font-size:13px}}
</style></head><body><div id="app"></div><script type="module">
import { createApp, h } from 'vue'; import { createPinia } from 'pinia'; import { createRouter, createMemoryHistory } from 'vue-router'; import CustomersView from '/src/views/CustomersView.vue'; import { useSessionStore } from '/src/stores/session.js'; import { useCartStore } from '/src/stores/cart.js'; import { setCurrency } from '/src/format.js'; import '/src/styles.css';
const pinia = createPinia(), session = useSessionStore(pinia); session.company = 'Osaka City'; session.currency = 'LKR'; session.priceList = 'Retail'; session.posProfile = 'Showroom'; session.profileCompanies = {Showroom:'Osaka City', Branch:'Second company'}; session.settings = {enable_customer_balances:1}; session.notify = message => window.notices.push(message); window.notices = []; setCurrency('LKR'); const cart = useCartStore(pinia); window.test = {session, cart};
const router = createRouter({history:createMemoryHistory(), routes:[{path:'/', component:CustomersView}]});
createApp({render:()=>h('div',{style:'display:contents'},[h('header',{class:'check-header'},[h('span','ESAFE ERP POS / Customers'),h('span','Osaka City')]),h('main',{class:'check-main'},[h(CustomersView)])])}).use(pinia).use(router).mount('#app');
</script></body></html>`
const server = await createServer({ root, base: '/', server: { host: '127.0.0.1', port: 0, open: false }, plugins: [{ name: 'customers-check', configureServer(s) {
  s.middlewares.use('/customers-check.html', async (req, res) => { res.setHeader('Content-Type', 'text/html'); res.end(await s.transformIndexHtml('/customers-check.html', html)) })
} }] })
await server.listen()
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
page.setDefaultTimeout(15000)
const errors = [], calls = []
page.on('pageerror', error => errors.push(error.message))
await page.route('https://fonts.googleapis.com/**', route => route.abort())
await page.route('https://fonts.gstatic.com/**', route => route.abort())
let assignment = null, canEdit = true, failSearch = false, failSave = false, holdList = null
const customer = number => ({ name: `CUST-${number}`, customer_name: number === 1 ? 'A Rahman' : `Customer ${String(number).padStart(2, '0')}`,
  customer_group: 'Individual', mobile_no: '077 123 4567', default_currency: 'LKR', default_price_list: number === 1 ? assignment : null })
await page.route('**/api/method/**', async route => {
  const method = route.request().url().split('/').pop(), args = route.request().postDataJSON()
  calls.push({ method, args })
  let message = []
  if (method.endsWith('customer_groups')) message = ['Individual', 'Commercial']
  else if (method.endsWith('customers.search_customers')) {
    if (holdList && args.activity === 'new_today') await holdList
    if (failSearch) { await route.fulfill({ status: 403, json: { exception: 'PermissionError: Customer search unavailable' } }); return }
    const rows = Array.from({ length: 33 }, (_, i) => ({ ...customer(i + 1), ...(args.still_owes ? { outstanding: 1250 } : {}) }))
    message = { items: rows.slice(args.start, args.start + args.limit), has_more: args.start + args.limit < rows.length, currency: 'LKR' }
  } else if (method.endsWith('customer_detail')) message = {
    ...customer(Number(args.customer.split('-')[1])), member_since: '2026-11-24', billing_currency: 'LKR', currency: 'LKR',
    stats: { sales_count: 12, returns_count: 0, net_spent: 24500, last_purchase: '2026-11-25' }, wallet: { loyalty_points: 20, store_credit: 0 }, can_edit_price_list: canEdit,
  }
  else if (method.endsWith('customer_price_lists')) message = [{ name: 'Retail', currency: 'LKR' }, { name: 'Wholesale', currency: 'LKR' }]
  else if (method.endsWith('set_customer_price_list')) {
    if (failSave) { await route.fulfill({ status: 403, json: { exception: 'PermissionError: Price list change denied' } }); return }
    assignment = args.price_list
    message = { customer: args.customer, default_price_list: assignment }
  }
  else if (method.endsWith('customer_credit')) message = { enabled: true, currency: 'LKR', owed: 1250, items: [], can_set: false, can_take_payment: false }
  else if (method.endsWith('get_wallet')) message = { loyalty_points: 20, store_credit: 0 }
  else if (method.endsWith('get_prices')) {
    const own = args.customer === 'CUST-1' && assignment
    message = { price_list: args.app_type ? 'Delivery' : own || 'Retail', prices: { FEED: args.app_type ? 120 : own ? 80 : 100 },
      standard_prices: { FEED: 100 }, selling_units: { FEED: { '25 kg Pack': own ? 1900 : 2400 } } }
  }
  await route.fulfill({ json: { message } })
})
const searchCalls = () => calls.filter(c => c.method.endsWith('customers.search_customers'))
try {
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/customers-check.html`, { waitUntil: 'domcontentloaded', timeout: 60000 })
  await page.locator('.cust-row').first().waitFor()
  assert.equal(await page.locator('.cust-row').count(), 30)
  await page.getByRole('button', { name: 'Load more', exact: true }).click()
  await page.waitForFunction(() => document.querySelectorAll('.cust-row').length === 33)
  assert.equal(searchCalls().at(-1).args.start, 30)

  await page.getByLabel('Account balance', { exact: true }).selectOption('owes')
  await page.getByLabel('Customer activity', { exact: true }).selectOption('new_yesterday')
  await page.getByLabel('Customer group', { exact: true }).selectOption('Individual')
  await page.getByLabel('Search customers', { exact: true }).fill('Rahman')
  await page.waitForFunction(() => document.querySelector('.list-head input').value === 'Rahman' && document.querySelectorAll('.cust-row').length === 30)
  await page.waitForTimeout(350)
  const filterArgs = searchCalls().at(-1).args
  assert.equal(filterArgs.activity, 'new_yesterday')
  assert.equal(filterArgs.still_owes, 1)
  assert.equal(filterArgs.customer_group, 'Individual')
  assert.equal(filterArgs.search, 'Rahman')
  assert.equal(filterArgs.start, 0)
  await page.locator('.customer-owed').first().waitFor()

  await page.getByRole('button', { name: 'Clear filters', exact: true }).click()
  await page.getByLabel('Customer activity', { exact: true }).selectOption('purchased_date')
  await page.getByText('Choose a purchase date.', { exact: true }).waitFor()
  await page.getByLabel('Purchase date', { exact: true }).fill('2026-11-24')
  await page.locator('.cust-row').first().waitFor()
  assert.equal(searchCalls().at(-1).args.activity_date, '2026-11-24')
  await page.getByLabel('Company', { exact: true }).selectOption('Second company')
  await page.locator('.cust-row').first().waitFor()
  assert.equal(searchCalls().at(-1).args.company, 'Second company')
  await page.getByLabel('Company', { exact: true }).selectOption('Osaka City')

  // A slow prior filter must not replace a newer page of results.
  let release
  holdList = new Promise(resolve => { release = resolve })
  await page.getByLabel('Customer activity', { exact: true }).selectOption('new_today')
  await page.getByLabel('Customer activity', { exact: true }).selectOption('purchased_today')
  await page.locator('.cust-row').first().waitFor()
  release(); holdList = null
  await page.waitForTimeout(100)
  assert.equal(await page.getByLabel('Customer activity', { exact: true }).inputValue(), 'purchased_today')

  await page.getByLabel('Account balance', { exact: true }).selectOption('owes')
  await page.locator('.cust-row').first().click()
  await page.getByLabel('Selling price list', { exact: true }).waitFor()
  await page.waitForFunction(() => document.querySelector('.pricing-controls select') && !document.querySelector('.pricing-controls select').disabled)
  await page.evaluate(async () => {
    const { cart } = window.test
    cart.addItem({ item_code: 'FEED', item_name: 'Feed', stock_uom: 'Kg', price: 100 })
    cart.addItem({ item_code: 'FEED', item_name: '25 kg Feed', stock_uom: 'Kg', price: 2400, selling_uom: '25 kg Pack', conversion_factor: 25 })
    await cart.setCustomer({ name: 'CUST-1', customer_name: 'A Rahman', default_currency: 'LKR' })
  })
  await page.getByLabel('Selling price list', { exact: true }).selectOption('Wholesale')
  await page.getByRole('button', { name: 'Save price list', exact: true }).click()
  await page.waitForFunction(() => window.notices.includes('Customer price list saved'))
  assert.equal(assignment, 'Wholesale')
  assert.deepEqual(await page.evaluate(() => window.test.cart.lines.map(line => line.price)), [80, 1900])
  assert.equal(await page.evaluate(() => window.test.cart.activePriceList), 'Wholesale')
  const cached = await page.evaluate(async () => (await (await import('/src/offline.js')).searchCustomersOffline('Rahman')))
  assert.equal(cached[0].default_price_list, 'Wholesale')
  const blocked = await page.evaluate(async () => {
    try { await window.test.cart._queueOffline({ items: [] }, []); return null } catch (e) { return e.message }
  })
  assert.match(blocked, /Customer price lists need a connection/)

  await page.screenshot({ path: path.join(output, 'customers-desktop.png'), fullPage: true })
  for (const width of [1024, 768, 390]) {
    await page.setViewportSize({ width, height: 900 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    if (width === 390) {
      await page.screenshot({ path: path.join(output, 'customer-pricing-mobile.png'), fullPage: true })
      await page.getByRole('button', { name: 'All customers', exact: false }).click()
      await page.screenshot({ path: path.join(output, 'customer-filters-mobile.png'), fullPage: true })
      assert.equal(await page.locator('.cust-row').first().isVisible(), true)
      await page.locator('.cust-row').first().click()
      await page.waitForFunction(() => document.querySelector('.pricing-controls select') && !document.querySelector('.pricing-controls select').disabled)
    }
  }

  // Failed writes retain the saved value and can be retried or cleared.
  failSave = true
  await page.getByLabel('Selling price list', { exact: true }).selectOption('Retail')
  await page.getByRole('button', { name: 'Save price list', exact: true }).click()
  await page.getByRole('alert').waitFor()
  assert.equal(assignment, 'Wholesale')
  failSave = false
  await page.getByLabel('Selling price list', { exact: true }).selectOption('')
  await page.getByRole('button', { name: 'Save price list', exact: true }).click()
  await page.waitForFunction(() => window.test.cart.customer.default_price_list === null)
  assert.deepEqual(await page.evaluate(() => window.test.cart.lines.map(line => line.price)), [100, 2400])

  await page.evaluate(async () => { window.test.cart.lines[0].price_override = 60; window.test.cart.lines[0].price = 60; await window.test.cart.reprice() })
  assert.equal(await page.evaluate(() => window.test.cart.lines[0].price), 60)
  await page.evaluate(async () => { window.test.cart.lines[0].price_override = null; await window.test.cart.setChannel('Delivery app') })
  assert.equal(await page.evaluate(() => window.test.cart.lines[0].price), 120)

  await page.getByRole('button', { name: 'All customers', exact: false }).click()
  canEdit = false
  await page.locator('.cust-row').first().click()
  await page.locator('.pricing-current').waitFor()
  assert.equal(await page.getByLabel('Selling price list', { exact: true }).count(), 0)

  await page.getByRole('button', { name: 'All customers', exact: false }).click()
  failSearch = true
  await page.getByLabel('Customer activity', { exact: true }).selectOption('new_today')
  await page.getByRole('alert').waitFor()
  failSearch = false
  await page.getByRole('button', { name: 'Retry', exact: true }).click()
  await page.locator('.cust-row').first().waitFor()
  assert.equal(errors.length, 0, errors.join('\n'))
  console.log('Customer browser checks passed: filters, pagination, company, save/clear, cart and pack prices, offline guard, permissions, retry, responsive layouts.')
} finally {
  await browser.close()
  await server.close()
}
