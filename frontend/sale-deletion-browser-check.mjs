// Real History -> receipt -> deletion dialog, with simulated ERPNext APIs.
// No live invoices are cancelled or deleted.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
const root = path.dirname(fileURLToPath(import.meta.url)), output = path.join(root, '../docs/screenshots/sale-deletion')
await mkdir(output, { recursive: true })
const invoice = 'ACC-PSINV-2026-00037'
const receipt = { name: invoice, doctype: 'POS Invoice', company: 'Shop', pos_profile: 'Till', currency: 'LKR',
  posting_date: '2026-11-25', posting_time: '16:00:00', customer_name: 'Walk-in customer', cashier: 'Cashier',
  grand_total: 1500, rounded_total: 1500, total: 1500, net_total: 1500, total_qty: 1, item_count: 1,
  items: [{ item_code: 'ITEM', item_name: 'Rice', qty: 1, rate: 1500, price_list_rate: 1500, amount: 1500 }],
  payments: [{ mode_of_payment: 'Cash', amount: 1500 }], receipt_settings: {}, docstatus: 1, status: 'Paid' }
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><div id="app" style="height:100%"></div><script type="module">
import { createApp } from 'vue'; import { createPinia } from 'pinia'; import { createRouter, createMemoryHistory } from 'vue-router';
import HistoryView from '/src/views/HistoryView.vue'; import { useSessionStore } from '/src/stores/session.js'; import '/src/styles.css'; import { setCurrency } from '/src/format.js';
const pinia = createPinia(), session = useSessionStore(pinia); setCurrency('LKR'); session.user = 'manager'; session.company = 'Shop'; session.currency = 'LKR'; session.posProfile = 'Till'; session.availableProfiles = ['Till']; session.registerSession = { name: 'REG-A' };
session.permissions = { is_manager: !new URLSearchParams(location.search).has('cashier'), can_return: true, can_exchange: true, can_move_cash: false, can_reprint: true };
session.paymentModes = [{ mode_of_payment: 'Cash', type: 'Cash' }]; session.settings = { receipt_template: 'Retail', receipt_show_payments: 1 }; session.notify = message => window.notices.push(message); window.notices = []; window.test = { session };
const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: HistoryView }] }); createApp(HistoryView).use(pinia).use(router).mount('#app');
</script></body></html>`
const server = await createServer({ root, base: '/', server: { host: '127.0.0.1', port: 0, open: false }, plugins: [{ name: 'sale-delete-test', configureServer(s) {
  s.middlewares.use('/sale-delete-check.html', async (req, res) => { res.setHeader('Content-Type', 'text/html'); res.end(await s.transformIndexHtml('/sale-delete-check.html', html)) })
} }] })
await server.listen()
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true, args: ['--disable-gpu'] })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } }), errors = [], calls = []
page.setDefaultTimeout(10000)
page.on('pageerror', error => errors.push(error.message))
await page.route('https://fonts.googleapis.com/**', route => route.abort())
await page.route('https://fonts.gstatic.com/**', route => route.abort())
let deleted = false, eligible = true, failDelete = false, failCheck = false, loseDeleteReply = false
await page.route('**/api/method/**', async route => {
  const method = route.request().url().split('/').pop(), args = route.request().postDataJSON()
  calls.push({ method, args })
  let message = []
  if (method.endsWith('search_sales')) message = deleted ? [] : [receipt]
  else if (method.endsWith('get_receipt')) message = receipt
  else if (method.endsWith('check_sale_deletion')) {
    if (failCheck) { await route.fulfill({ status: 403, json: { exception: 'PermissionError: ERPNext delete permission is required.' } }); return }
    message = { deleted, eligible: eligible && !deleted, blocker: eligible ? '' : 'This sale has been consolidated. Its linked accounting documents must be handled in ERPNext first.',
      invoice, doctype: 'POS Invoice', amount: 1500, currency: 'LKR', modified: '2026-11-25 16:00:00', session: 'REG-A' }
  } else if (method.endsWith('permanently_delete_sale')) {
    if (failDelete) { await route.fulfill({ status: 409, json: { exception: 'ValidationError: ERPNext refused the linked transaction. The sale was not deleted.' } }); return }
    deleted = true; message = { deleted: true, invoice }
    if (loseDeleteReply) { await route.abort('failed'); return }
  } else if (method.endsWith('get_items')) message = { items: [], groups: [] }
  await route.fulfill({ json: { message } })
})
const url = `http://127.0.0.1:${server.httpServer.address().port}/sale-delete-check.html`
const openReceipt = async () => { await page.locator('.sale-open').first().click(); await page.getByRole('button', { name: 'Delete sale…', exact: true }).waitFor() }
const openDelete = async () => { await openReceipt(); await page.getByRole('button', { name: 'Delete sale…', exact: true }).click() }
try {
  await page.goto(url, { waitUntil: 'networkidle' })
  await openDelete()
  const dialog = page.getByRole('dialog', { name: 'Permanently delete sale', exact: true })
  const remove = dialog.getByRole('button', { name: 'Permanently delete sale', exact: true })
  await remove.waitFor()
  assert.equal(await remove.isDisabled(), true)
  await page.getByLabel('Reason for deletion', { exact: true }).fill('Wrong duplicate sale')
  await page.getByLabel('Type the exact invoice number to confirm', { exact: true }).fill('wrong')
  await dialog.getByRole('checkbox').check()
  assert.equal(await remove.isDisabled(), true)
  await page.getByLabel('Type the exact invoice number to confirm', { exact: true }).fill(invoice)
  assert.equal(await remove.isEnabled(), true)
  await page.evaluate(() => { window.test.session.offline = true })
  assert.equal(await remove.isDisabled(), true)
  await page.evaluate(() => { window.test.session.offline = false })
  await page.screenshot({ path: path.join(output, 'confirm-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await page.screenshot({ path: path.join(output, 'confirm-mobile.png'), fullPage: true })
  // Cache cleanup removes only this invoice's offline-return copy.
  await page.evaluate(async invoice => {
    const { putShiftSale } = await import('/src/offline.js')
    await putShiftSale({ key: 'deleted-local', name: invoice, session: 'REG-A' })
    await putShiftSale({ key: 'keep-local', name: 'OTHER-INVOICE', session: 'REG-A' })
  }, invoice)
  failDelete = true
  await remove.click()
  await dialog.getByRole('alert').filter({ hasText: 'ERPNext refused' }).waitFor()
  assert.equal(deleted, false)
  assert.equal(await page.getByLabel('Reason for deletion', { exact: true }).inputValue(), 'Wrong duplicate sale')
  failDelete = false
  await remove.click()
  await page.getByText('No sales match', { exact: true }).waitFor()
  const { _lang, ...sent } = calls.findLast(call => call.method.endsWith('permanently_delete_sale')).args
  assert.deepEqual(sent, { invoice, doctype: 'POS Invoice', reason: 'Wrong duplicate sale', confirm_invoice: invoice,
    expected_modified: '2026-11-25 16:00:00', payment_handled: 1 })
  const cached = await page.evaluate(async () => (await (await import('/src/offline.js')).listShiftSales()).map(row => row.name))
  assert.deepEqual(cached, ['OTHER-INVOICE'])
  assert.equal(await dialog.count(), 0)

  deleted = false; eligible = false
  await page.reload({ waitUntil: 'networkidle' })
  await openDelete()
  await page.getByText('This sale cannot be deleted here', { exact: true }).waitFor()
  assert.equal(await page.getByRole('button', { name: 'Permanently delete sale', exact: true }).count(), 0)
  await page.screenshot({ path: path.join(output, 'blocked-mobile.png'), fullPage: true })
  await page.getByRole('button', { name: 'Back to receipt', exact: true }).click()
  await page.getByRole('button', { name: 'Delete sale…', exact: true }).waitFor()
  failCheck = true
  await page.getByRole('button', { name: 'Delete sale…', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: 'delete permission' }).waitFor()
  assert.equal(await page.getByRole('button', { name: 'Permanently delete sale', exact: true }).count(), 0)
  failCheck = false
  await page.goto(`${url}?cashier`, { waitUntil: 'networkidle' })
  await page.locator('.sale-open').first().click()
  assert.equal(await page.getByRole('button', { name: 'Delete sale…', exact: true }).count(), 0)
  // A lost response is checked read-only; it never requires another deletion.
  eligible = true; deleted = false; loseDeleteReply = true
  await page.goto(url, { waitUntil: 'networkidle' })
  await openDelete()
  await page.getByLabel('Reason for deletion', { exact: true }).fill('Wrong duplicate sale')
  await page.getByLabel('Type the exact invoice number to confirm', { exact: true }).fill(invoice)
  await page.getByRole('dialog').getByRole('checkbox').check()
  const before = calls.filter(call => call.method.endsWith('permanently_delete_sale')).length
  await page.getByRole('button', { name: 'Permanently delete sale', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: 'could not be confirmed' }).waitFor()
  await page.getByRole('button', { name: 'Check again', exact: true }).click()
  await page.getByText('No sales match', { exact: true }).waitFor()
  assert.equal(calls.filter(call => call.method.endsWith('permanently_delete_sale')).length, before + 1)
  assert.deepEqual(errors, [])
  console.log('Sale deletion Chrome checks passed: History integration, manager-only action, typed confirmation, payment acknowledgement, offline guard, server refusal, cache cleanup, blocked dependencies and desktop/mobile layouts.')
} finally { await browser.close(); await server.close() }
