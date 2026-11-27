// Browser workflow checks with local API fixtures; no live accounting writes.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
const root = path.dirname(fileURLToPath(import.meta.url))
const output = path.join(root, '../docs/screenshots/buying')
await mkdir(output, { recursive: true })
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><title>Buying workflow check</title></head><body style="overflow:auto">
<header style="height:52px;background:var(--pos-blue);color:white;display:flex;align-items:center;justify-content:space-between;padding:0 20px"><b>ESAFE ERP POS / Buying</b><span>Weerakoon Agro</span></header><div id="app" style="height:calc(100dvh - 52px);display:flex;overflow:hidden"></div><script type="module">
import { createApp } from 'vue'; import { createPinia } from 'pinia'; import BuyingView from '/src/views/BuyingView.vue'; import { useSessionStore } from '/src/stores/session.js'; import '/src/styles.css';
const pinia=createPinia(), session=useSessionStore(pinia); session.posProfile='Main till'; session.company='Weerakoon Agro'; session.currency='LKR'; session.settings.enable_buying=1; session.permissions={buying:true}; window.test={session}; createApp(BuyingView).use(pinia).mount('#app'); window.ready=true;
</script></body></html>`
const server = await createServer({ root, base: '/', server: { port: 0, host: '127.0.0.1', open: false }, plugins: [{ name: 'buying-check', configureServer(s) {
  s.middlewares.use('/buying-check.html', async (req, res) => { res.setHeader('Content-Type', 'text/html'); res.end(await s.transformIndexHtml('/buying-check.html', html)) })
} }] })
await server.listen()
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe' })
const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } })
page.setDefaultTimeout(15000)
const errors = [], calls = []
page.on('pageerror', error => errors.push(error.message))
await page.route('https://fonts.googleapis.com/**', route => route.abort())
await page.route('https://fonts.gstatic.com/**', route => route.abort())
let invoiceNumber = 1, balance = 8500, failPayment = false, rejectPayment = false, nativePayments = 0
let canCreateItem = true, canEditPrices = true, sellingPriceList = { name: 'Standard Selling', currency: 'LKR' }, loseItemResponse = false, holdItemCreation = null
const createdItems = []
const suppliers = [{ name: 'SUP-001', supplier_name: 'Greenfield Agri Supplies', supplier_group: 'Agriculture' }, { name: 'SUP-002', supplier_name: 'Lanka Seed Company', supplier_group: 'Agriculture' }]
const invoices = [{ name: 'PINV-0001', posting_date: '2026-11-20', due_date: '2026-12-20', bill_no: 'GF-2947', grand_total: 8500, outstanding_amount: 8500, currency: 'LKR', credit_to: 'Creditors - WA', status: 'Unpaid' }]
const payments = []
const posted = new Map()
const item = { name: 'SEED-025', item_name: 'Premium vegetable seed', stock_uom: 'Packet', is_stock_item: 1, last_purchase_rate: 100 }
await page.route('**/api/method/**', async route => {
  const method = route.request().url().split('.').pop(), args = route.request().postDataJSON()
  calls.push({ method, args })
  let message
  if (method === 'options') message = { company: 'Weerakoon Agro', currency: 'LKR', today: '2026-11-26', warehouse: 'Main Stores - WA', warehouses: ['Main Stores - WA', 'Shop - WA'], cost_accounts: ['Freight and handling - WA'], supplier_groups: ['Agriculture'], can_create_supplier: true, can_create_invoice: true, can_create_item: canCreateItem, can_edit_prices: canEditPrices, selling_price_list: canEditPrices ? sellingPriceList : null, item_groups: ['Agriculture'], stock_uoms: ['Kg', 'Packet'], can_pay: true, payment_modes: [{ name: 'Cash', type: 'Cash', account: 'Cash - WA' }, { name: 'Bank Transfer', type: 'Bank', account: 'Commercial Bank - WA' }, { name: 'Cheque', type: 'Bank', account: 'Commercial Bank - WA' }] }
  if (method === 'search_suppliers') message = suppliers.filter(row => !args.search || `${row.name} ${row.supplier_name}`.toLowerCase().includes(args.search.toLowerCase()))
  if (method === 'create_supplier') { message = { name: 'SUP-003', supplier_name: args.supplier_name, supplier_group: args.supplier_group }; if (!suppliers.some(row => row.name === message.name)) suppliers.push(message) }
  if (method === 'supplier_account') message = { currency: 'LKR', balance: args.supplier === 'SUP-001' ? balance : 0, open_invoices: args.supplier === 'SUP-001' ? invoices.filter(row => row.outstanding_amount > 0) : [], invoices: args.supplier === 'SUP-001' ? invoices : [], payments: args.supplier === 'SUP-001' ? payments : [] }
  if (method === 'search_items') message = [item, ...createdItems].filter(row => `${row.name} ${row.item_name}`.toLowerCase().includes(args.search.toLowerCase()))
  if (method === 'generate_identifier') message = { value: '00999' }
  if (method === 'create_item') {
    if (holdItemCreation) await holdItemCreation
    if ([item, ...createdItems].some(row => row.name === args.item_code)) {
      await route.fulfill({ status: 409, json: { exception: 'DuplicateEntryError: Item code already exists.' } }); return
    }
    createdItems.push({ name: args.item_code, item_name: args.item_name, stock_uom: args.stock_uom, is_stock_item: 1, last_purchase_rate: 0 })
    message = { item_code: args.item_code }
    if (loseItemResponse) { loseItemResponse = false; await route.abort('failed'); return }
  }
  if (method === 'create_invoice') {
    if (!posted.has(args.idempotency_key)) {
      const cost = args.costs.reduce((sum, row) => sum + row.amount, 0)
      const total = args.items.reduce((sum, row) => sum + row.qty * row.rate, 0) + cost
      const invoice = { name: `PINV-${String(++invoiceNumber).padStart(4, '0')}`, posting_date: args.posting_date, due_date: args.due_date, bill_no: args.bill_no, grand_total: total, outstanding_amount: total, currency: 'LKR', credit_to: 'Creditors - WA', status: 'Unpaid', items: args.items, costs: args.costs }
      invoices.unshift(invoice); balance += total; posted.set(args.idempotency_key, invoice)
    }
    message = posted.get(args.idempotency_key)
  }
  if (method === 'pay_supplier') {
    if (rejectPayment) { rejectPayment = false; await route.fulfill({ status: 417, contentType: 'application/json', body: JSON.stringify({ exc_type: 'ValidationError', exception: 'ValidationError: Outstanding balance changed. Refresh and try again.' }) }); return }
    if (!posted.has(args.idempotency_key)) {
      nativePayments++
      let left = args.amount
      for (const invoice of [...invoices].sort((a,b) => a.posting_date.localeCompare(b.posting_date))) {
        if (args.invoices.some(row => row.name === invoice.name)) { const take = Math.min(invoice.outstanding_amount, left); invoice.outstanding_amount -= take; left -= take; if (!invoice.outstanding_amount) invoice.status = 'Paid' }
      }
      balance -= args.amount
      const payment = { name: `PAY-${nativePayments}`, payment_type: 'Pay', paid_amount: args.amount, paid_from_account_currency: 'LKR', mode_of_payment: args.mode_of_payment, reference_no: args.reference_no, reference_date: args.reference_date, posting_date: args.posting_date }
      payments.unshift(payment); posted.set(args.idempotency_key, payment)
    }
    message = posted.get(args.idempotency_key)
    if (failPayment) { failPayment = false; await route.abort('failed'); return }
  }
  if (method === 'invoice_details') {
    const invoice = invoices.find(row => row.name === args.name)
    message = { ...invoice, update_stock: 1, supplier: 'SUP-001', items: (invoice.items || [{ item_code: item.name, qty: 85, rate: 100 }]).map(row => ({ ...row, item_name: item.item_name, uom: item.stock_uom, valuation_rate: 110 })), costs: (invoice.costs || []).map(row => ({ ...row, category: 'Valuation and Total' })) }
  }
  await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ message }) })
})

const submitPayment = () => page.getByRole('button', { name: 'Submit supplier payment', exact: true })
const selectInvoice = (name) => page.getByLabel(`Select ${name}`, { exact: true }).check()
async function screenshot(name) {
  await page.screenshot({ path: path.join(output, name), fullPage: true })
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `No page overflow: ${name}`)
}
try {
  await page.goto(`http://127.0.0.1:${server.config.server.port}/buying-check.html`)
  await page.getByRole('button', { name: /Greenfield Agri Supplies/ }).click()
  await page.getByText('Unpaid purchase invoices', { exact: true }).waitFor()
  assert.ok(await page.locator('.buying-workspace').evaluate(el => el.getBoundingClientRect().width >= window.innerWidth - 1), 'Buying fills its flex parent')
  await screenshot('account-desktop.png')
  await page.getByRole('button', { name: 'New purchase invoice', exact: true }).click()
  await page.getByLabel('Supplier invoice number', { exact: true }).fill('GF-2959')
  await page.getByLabel('Add items', { exact: true }).fill('seed')
  await page.getByRole('button', { name: /Premium vegetable seed/ }).click()
  await page.getByLabel('Quantity for Premium vegetable seed').fill('10')
  await page.getByLabel('Unit cost for Premium vegetable seed').fill('100')
  await page.getByRole('button', { name: 'Add cost', exact: true }).click()
  await page.getByLabel('Description', { exact: true }).fill('Freight')
  await page.getByLabel('Amount', { exact: true }).fill('100')
  assert.match(await page.locator('.summary-total').innerText(), /1,100/)
  assert.match(await page.locator('.valuation-preview').innerText(), /110/)
  for (const value of ['', '-1', 'oops']) {
    await page.getByLabel('Unit cost for Premium vegetable seed').fill(value)
    assert.equal(await page.getByRole('button', { name: 'Submit purchase invoice', exact: true }).isDisabled(), true)
  }
  await page.getByLabel('Unit cost for Premium vegetable seed').fill('100')
  // Switching supplier retains separate drafts and does not carry a bill to another supplier.
  await page.getByRole('button', { name: /Lanka Seed Company/ }).click()
  await page.getByRole('button', { name: 'New purchase invoice', exact: true }).click()
  assert.equal(await page.getByLabel('Supplier invoice number', { exact: true }).inputValue(), '')
  await page.getByRole('button', { name: /Greenfield Agri Supplies/ }).click()
  await page.getByRole('button', { name: 'New purchase invoice', exact: true }).click()
  assert.equal(await page.getByLabel('Supplier invoice number', { exact: true }).inputValue(), 'GF-2959')
  await screenshot('purchase-desktop.png')
  await page.setViewportSize({ width: 390, height: 844 })
  await screenshot('purchase-mobile.png')
  await page.getByRole('button', { name: 'Submit purchase invoice', exact: true }).click()
  await page.getByRole('status').filter({ hasText: 'PINV-0002' }).waitFor()
  const invoiceCall = calls.find(row => row.method === 'create_invoice')
  assert.deepEqual(invoiceCall.args.items, [{ item_code: 'SEED-025', qty: 10, rate: 100 }])
  assert.deepEqual(invoiceCall.args.costs, [{ description: 'Freight', account: 'Freight and handling - WA', amount: 100 }])
  assert.equal(balance, 9600)
  await page.getByRole('button', { name: 'Pay supplier', exact: true }).click()
  await page.getByLabel('Payment amount').fill('100')
  await page.getByLabel(/^Pay from/).selectOption('Cash')
  await submitPayment().click()
  await page.getByRole('status').filter({ hasText: 'PAY-1' }).waitFor()
  assert.equal(balance, 9500)
  assert.equal(invoices.find(row => row.name === 'PINV-0002').outstanding_amount, 1000)

  await selectInvoice('PINV-0002')
  await page.getByRole('button', { name: 'Pay supplier', exact: true }).click()
  await page.getByLabel(/^Payment method/).selectOption('Cheque')
  await page.getByLabel(/^Pay from/).selectOption('Cheque')
  await page.getByLabel('Payment amount').fill('300')
  assert.equal(await submitPayment().isDisabled(), true)
  await page.getByLabel('Cheque number', { exact: true }).fill('CHQ-728591')
  await page.getByLabel('Cheque date', { exact: true }).fill('2026-12-01')
  await screenshot('cheque-mobile.png')
  await page.setViewportSize({ width: 1440, height: 1050 })
  await screenshot('cheque-desktop.png')
  await submitPayment().click()
  await page.getByRole('status').filter({ hasText: 'PAY-2' }).waitFor()
  assert.equal(balance, 9200)

  await selectInvoice('PINV-0002')
  await selectInvoice('PINV-0001')
  await page.getByRole('button', { name: 'Pay supplier', exact: true }).click()
  await page.getByLabel(/^Payment method/).selectOption('Bank Transfer')
  await page.getByLabel(/^Pay from/).selectOption('Bank Transfer')
  await page.getByLabel('Payment amount').fill('9201')
  await page.getByLabel('Transfer reference', { exact: true }).fill('TRF-67419')
  assert.equal(await submitPayment().isDisabled(), true)
  await page.getByLabel('Payment amount').fill('9200')
  // A lost response after posting retains the exact request ID for a retry.
  failPayment = true
  await submitPayment().click()
  await page.getByRole('alert').filter({ hasText: 'No connection' }).waitFor()
  const beforeRetry = calls.filter(row => row.method === 'pay_supplier').at(-1)
  assert.equal(await page.getByLabel('Payment amount').isDisabled(), true)
  await page.getByRole('button', { name: 'Refresh balances', exact: true }).click()
  await page.getByText('No unpaid purchase invoices for this supplier.').waitFor()
  await page.getByRole('button', { name: 'Check posting result', exact: true }).click()
  await page.getByRole('status').filter({ hasText: 'PAY-3' }).waitFor()
  const afterRetry = calls.filter(row => row.method === 'pay_supplier').at(-1)
  assert.equal(beforeRetry.args.idempotency_key, afterRetry.args.idempotency_key)
  assert.equal(nativePayments, 3)
  assert.equal(balance, 0)
  await page.getByText('No unpaid purchase invoices for this supplier.').waitFor()
  await page.getByRole('button', { name: 'PINV-0002', exact: true }).click()
  await page.locator('.invoice-detail').waitFor()
  assert.match(await page.locator('.invoice-detail').innerText(), /110/)
  await screenshot('settled-desktop.png')
  await page.setViewportSize({ width: 390, height: 844 })
  await screenshot('account-mobile.png')

  // Create a missing product without leaving or submitting the supplier draft.
  await page.setViewportSize({ width: 1440, height: 1050 })
  await page.getByRole('button', { name: 'New purchase invoice', exact: true }).click()
  await page.getByLabel('Supplier invoice number', { exact: true }).fill('GF-EMERGENCY-1')
  await page.getByLabel('Add items', { exact: true }).fill('Emergency rice')
  await page.getByRole('button', { name: 'Create missing item', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Emergency item entry' })
  const createItem = () => dialog.getByRole('button', { name: 'Create and add item', exact: true })
  assert.equal(await dialog.getByLabel('Item name', { exact: true }).inputValue(), 'Emergency rice')
  assert.equal(await createItem().isDisabled(), true)
  await dialog.getByLabel(/^Category/).selectOption('Agriculture')
  await dialog.getByLabel(/^Stock unit/).selectOption('Kg')
  await dialog.getByLabel('Quantity', { exact: true }).fill('2.5')
  await dialog.getByLabel('Unit cost', { exact: false }).fill('125.50')
  await dialog.getByLabel('Standard selling price', { exact: false }).fill('175.50')
  await dialog.getByLabel('Item code', { exact: true }).fill('SEED-025')
  await createItem().click()
  await dialog.getByRole('alert').filter({ hasText: 'already exists' }).waitFor()
  assert.equal(await dialog.getByLabel('Quantity', { exact: true }).inputValue(), '2.5')
  await dialog.getByRole('button', { name: 'Generate item code', exact: true }).click()
  await page.waitForFunction(() => document.querySelector('dialog .identifier-field input').value === '00999')
  await dialog.getByLabel('Barcode (optional)', { exact: true }).fill('8901234567890')
  for (const value of ['', '0', '-1', 'oops', 'Infinity']) {
    await dialog.getByLabel('Quantity', { exact: true }).fill(value)
    assert.equal(await createItem().isDisabled(), true)
    await dialog.getByLabel('Quantity', { exact: true }).fill('2.5')
    await dialog.getByLabel('Unit cost', { exact: false }).fill(value)
    assert.equal(await createItem().isDisabled(), true)
    await dialog.getByLabel('Unit cost', { exact: false }).fill('125.50')
  }
  for (const value of ['0', '-1', 'oops', 'Infinity']) {
    await dialog.getByLabel('Standard selling price', { exact: false }).fill(value)
    assert.equal(await createItem().isDisabled(), true)
  }
  await dialog.getByLabel('Standard selling price', { exact: false }).fill('175.50')
  await dialog.getByText(/Saved to Standard Selling per stock unit \(Kg\)/).waitFor()
  await screenshot('emergency-item-desktop.png')
  await page.setViewportSize({ width: 390, height: 844 })
  assert.ok(await dialog.evaluate(el => {
    const body = el.querySelector('.modal-body'), footer = el.querySelector('.modal-footer')
    return body.scrollHeight > body.clientHeight && body.getBoundingClientRect().bottom <= footer.getBoundingClientRect().top + 1
      && footer.getBoundingClientRect().bottom <= window.innerHeight
  }), 'Mobile form scrolls within its body and leaves the footer visible')
  await dialog.getByLabel('Standard selling price', { exact: false }).scrollIntoViewIfNeeded()
  await screenshot('emergency-item-mobile.png')
  await page.evaluate(() => { test.session.offline = true })
  assert.equal(await createItem().isDisabled(), true)
  await dialog.getByRole('alert').filter({ hasText: 'Connect to the server' }).waitFor()
  await page.evaluate(() => { test.session.offline = false })
  // In-flight saves cannot be submitted twice or cancelled.
  let finishCreation
  holdItemCreation = new Promise(resolve => { finishCreation = resolve })
  await createItem().click()
  await dialog.getByRole('button', { name: 'Saving…', exact: true }).waitFor()
  assert.equal(await dialog.getByRole('button', { name: 'Cancel', exact: true }).isDisabled(), true)
  await page.keyboard.press('Escape')
  assert.equal(await dialog.isVisible(), true)
  finishCreation(); holdItemCreation = null
  await dialog.waitFor({ state: 'detached' })
  assert.equal(await page.getByLabel('Quantity for Emergency rice').inputValue(), '2.5')
  assert.equal(await page.getByLabel('Unit cost for Emergency rice').inputValue(), '125.5')
  assert.equal(await page.getByLabel('Supplier invoice number', { exact: true }).inputValue(), 'GF-EMERGENCY-1')
  assert.match(await page.locator('.summary-total').innerText(), /313\.75/)
  assert.equal(calls.filter(row => row.method === 'create_invoice').length, 1, 'Item creation does not post an invoice')
  const created = calls.filter(row => row.method === 'create_item').at(-1).args
  assert.equal(created.pos_profile, 'Main till')
  assert.equal(created.barcode, '8901234567890')
  assert.equal(created.item_code, '00999')
  assert.equal(created.price_list, 'Standard Selling')
  assert.deepEqual(JSON.parse(created.prices), [{ uom: 'Kg', price: 175.5 }], 'Separate selling price is saved per stock unit')
  assert.equal(created.qty, undefined, 'Item creation does not receive stock')
  await page.getByLabel('Quantity for Emergency rice').scrollIntoViewIfNeeded()
  await screenshot('emergency-draft-mobile.png')
  await page.setViewportSize({ width: 1440, height: 1050 })
  await page.locator('.buying-workspace').evaluate(el => { el.scrollTop = 0 })
  await screenshot('emergency-draft-desktop.png')
  await page.getByRole('button', { name: 'Emergency item entry', exact: true }).click()
  await page.keyboard.press('Escape')
  await dialog.waitFor({ state: 'detached' })
  assert.equal(await page.getByRole('button', { name: 'Emergency item entry', exact: true }).evaluate(el => el === document.activeElement), true)
  // An uncertain item save is found by its original code, without automatic recreation.
  await page.getByRole('button', { name: 'Emergency item entry', exact: true }).click()
  await dialog.getByLabel('Item name', { exact: true }).fill('Recovery fertilizer')
  await dialog.getByLabel('Item code', { exact: true }).fill('RECOVER-001')
  await dialog.getByLabel(/^Category/).selectOption('Agriculture')
  await dialog.getByLabel(/^Stock unit/).selectOption('Packet')
  await dialog.getByLabel('Unit cost', { exact: false }).fill('50')
  loseItemResponse = true
  await createItem().click()
  await dialog.getByRole('alert').filter({ hasText: 'may already be saved' }).waitFor()
  assert.equal(await createItem().isDisabled(), true)
  await dialog.getByRole('button', { name: 'Find saved item', exact: true }).click()
  assert.equal(calls.filter(row => row.method === 'create_item').at(-1).args.prices, undefined, 'Blank selling price creates no Item Price')
  await page.getByRole('button', { name: /Recovery fertilizer/ }).click()
  assert.equal(createdItems.filter(row => row.name === 'RECOVER-001').length, 1)
  await page.getByLabel('Unit cost for Recovery fertilizer').fill('50')
  await page.getByRole('button', { name: 'Submit purchase invoice', exact: true }).click()
  await page.getByRole('status').filter({ hasText: 'PINV-0003' }).waitFor()
  assert.deepEqual(calls.filter(row => row.method === 'create_invoice').at(-1).args.items,
    [{ item_code: '00999', qty: 2.5, rate: 125.5 }, { item_code: 'RECOVER-001', qty: 1, rate: 50 }])

  // Price access is independent of item creation; a missing setup never chooses another list.
  canEditPrices = false
  await page.reload()
  await page.getByRole('button', { name: /Greenfield Agri Supplies/ }).click()
  await page.getByRole('button', { name: 'New purchase invoice', exact: true }).click()
  await page.getByRole('button', { name: 'Emergency item entry', exact: true }).click()
  assert.equal(await dialog.getByLabel('Standard selling price', { exact: false }).isDisabled(), true)
  await dialog.getByLabel('Item name', { exact: true }).fill('No price access item')
  await dialog.getByLabel('Item code', { exact: true }).fill('NOPRICE-001')
  await dialog.getByLabel(/^Category/).selectOption('Agriculture')
  await dialog.getByLabel(/^Stock unit/).selectOption('Kg')
  await dialog.getByLabel('Unit cost', { exact: false }).fill('25')
  await createItem().click()
  await dialog.waitFor({ state: 'detached' })
  assert.equal(calls.filter(row => row.method === 'create_item').at(-1).args.prices, undefined)
  canEditPrices = true; sellingPriceList = null
  await page.reload()
  await page.getByRole('button', { name: /Greenfield Agri Supplies/ }).click()
  await page.getByRole('button', { name: 'New purchase invoice', exact: true }).click()
  await page.getByRole('button', { name: 'Emergency item entry', exact: true }).click()
  assert.equal(await dialog.getByLabel('Standard selling price', { exact: false }).isDisabled(), true)
  await dialog.getByText('Configure an enabled, accessible selling price list on this outlet to set a selling price.').waitFor()
  await page.keyboard.press('Escape')
  sellingPriceList = { name: 'Retail USD', currency: 'USD' }
  await page.reload()
  await page.getByRole('button', { name: /Greenfield Agri Supplies/ }).click()
  await page.getByRole('button', { name: 'New purchase invoice', exact: true }).click()
  await page.getByRole('button', { name: 'Emergency item entry', exact: true }).click()
  assert.equal(await dialog.getByLabel('Standard selling price (USD)', { exact: true }).isEnabled(), true)
  assert.equal(await dialog.getByLabel('Unit cost (LKR)', { exact: true }).isEnabled(), true)
  await page.keyboard.press('Escape')

  // Item creation can be withheld independently of buying/invoice access.
  canCreateItem = false
  await page.reload()
  await page.getByRole('button', { name: /Greenfield Agri Supplies/ }).click()
  await page.getByRole('button', { name: 'New purchase invoice', exact: true }).click()
  assert.equal(await page.getByRole('button', { name: 'Emergency item entry', exact: true }).count(), 0)
  await page.getByLabel('Add items', { exact: true }).fill('Unlisted product')
  await page.getByText('No matching items. Ask a user with item creation access to add the product.').waitFor()
  assert.equal(await page.getByRole('button', { name: 'Create missing item', exact: true }).count(), 0)

  // New supplier and offline/permission boundaries remain accessible on phones.
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: 'Change supplier', exact: true }).click()
  await page.getByRole('button', { name: 'Add supplier', exact: true }).click()
  await page.getByLabel('Supplier name', { exact: true }).fill('Harvest Freight Services')
  await page.getByLabel(/^Supplier group/).selectOption('Agriculture')
  await page.getByRole('button', { name: 'Save supplier', exact: true }).click()
  await page.getByRole('status').filter({ hasText: 'Harvest Freight Services' }).waitFor()
  await page.getByRole('button', { name: 'New purchase invoice', exact: true }).click()
  await page.evaluate(() => { test.session.offline = true })
  await page.getByRole('alert').filter({ hasText: 'cannot be queued offline' }).waitFor()
  assert.equal(await page.getByRole('button', { name: 'Submit purchase invoice', exact: true }).isDisabled(), true)
  await page.evaluate(() => { test.session.offline = false; test.session.permissions.buying = false })
  await page.getByRole('alert').filter({ hasText: 'does not have buying access' }).waitFor()
  assert.equal(await page.getByRole('button', { name: 'New purchase invoice', exact: true }).count(), 0)
  assert.deepEqual(errors, [])
  console.log('PASS purchase with valuation charges, separate supplier drafts, cash/cheque/transfer, partial/full settlement, overpayment guard, lost-response retry, emergency item creation/generation/duplicates/validation/recovery, supplier creation, offline/access controls and desktop/mobile overflow/screenshots')
} finally {
  await browser.close()
  await server.close()
}
