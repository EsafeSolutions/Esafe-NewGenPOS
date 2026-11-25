// Guided shift recovery against simulated APIs. Never touches a live register.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
const root = path.dirname(fileURLToPath(import.meta.url))
const output = path.join(root, '../docs/screenshots/shift-help')
await mkdir(output, { recursive: true })
const valuationError = 'Valuation Rate for the Item flower bool, is required to do accounting entries for Sales Invoice ACC-SINV-2026-00037.'
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><div id="app" style="height:100%;overflow:auto"></div><script type="module">
import { createApp } from 'vue'; import { createPinia } from 'pinia'; import { createRouter, createMemoryHistory } from 'vue-router';
import RegisterView from '/src/views/RegisterView.vue'; import OpenRegisterOverlay from '/src/components/OpenRegisterOverlay.vue';
import { useSessionStore } from '/src/stores/session.js'; import '/src/styles.css'; import { setCurrency } from '/src/format.js';
const params = new URLSearchParams(location.search), pending = params.has('pending'), overlay = params.has('overlay');
const pinia = createPinia(), session = useSessionStore(pinia); setCurrency('LKR'); session.user = 'cashier'; session.posProfile = 'SHOWROOM'; session.company = 'Shop'; session.currency = 'LKR';
session.registerSession = pending ? null : { name: 'REG-A', opening_float: 5000 };
session.pendingClosing = pending ? { session: 'REG-OLD', closing_status: 'Failed', closing_error: ${JSON.stringify(valuationError)}, closing_attempts: 30, new_shift_blocked: true } : null;
session.permissions = { is_manager: true, close_register: true, open_register: true, can_move_cash: false };
session.paymentModes = [{ mode_of_payment: 'Cash', type: 'Cash', account_currency: 'LKR' }, { mode_of_payment: 'Card', type: 'Bank' }];
session.settings = { variance_reason_mode: 'Optional' }; window.notices = []; session.notify = message => window.notices.push(message);
session.bootstrap = async () => { session.registerSession = null; session.pendingClosing = null };
session.refreshQueueCount = async () => {}; session.flushQueue = async () => { window.uploads++; session.queuedCount = 0 };
window.uploads = 0; window.test = { session }; const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:pathMatch(.*)*', component: RegisterView }] });
createApp(overlay ? OpenRegisterOverlay : RegisterView).use(pinia).use(router).mount('#app');
</script></body></html>`
const server = await createServer({ root, base: '/', server: { host: '127.0.0.1', port: 0, open: false }, plugins: [{ name: 'shift-help-test', configureServer(s) {
  s.middlewares.use('/shift-help-check.html', async (req, res) => { res.setHeader('Content-Type', 'text/html'); res.end(await s.transformIndexHtml('/shift-help-check.html', html)) })
} }] })
await server.listen()
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true, args: ['--disable-gpu'] })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } }), errors = [], calls = []
page.setDefaultTimeout(10000)
page.on('pageerror', e => errors.push(e.message))
page.on('dialog', dialog => dialog.accept())
await page.route('https://fonts.googleapis.com/**', route => route.abort())
await page.route('https://fonts.gstatic.com/**', route => route.abort())
let status = 'Failed', retryFails = false
const expected = [{ mode_of_payment: 'Cash', expected_amount: 6000, currency: 'LKR', is_cash: 1 }, { mode_of_payment: 'Card', expected_amount: 500, currency: 'LKR' }]
const summary = { session: 'REG-A', company_currency: 'LKR', expected, sales_count: 2, total_sales: 1500, total_discounts: 0, opening_float: 5000, cash_movements: [], customer_payments: [] }
await page.route('**/api/method/**', async route => {
  const method = route.request().url().split('/').pop(), args = route.request().postDataJSON()
  calls.push({ method, args })
  let message = []
  if (method.endsWith('get_session_summary')) message = summary
  else if (method.endsWith('shared_drawer.summary')) message = { members: [{ session: 'REG-A', status: 'Open' }], all_open: true, group: null, expected }
  else if (method.endsWith('closing_entry_status')) message = { status: status === 'Submitted' ? 'Closed' : 'Closing', closing_status: status, closing_error: status === 'Failed' ? valuationError : null, closing_attempts: 30 }
  else if (method.endsWith('retry_closing')) {
    if (retryFails) { await route.fulfill({ status: 403, json: { exception: 'PermissionError: Ask a manager' } }); return }
    status = 'Queued'; message = { status: 'Closing', closing_status: 'Queued', queued: true }
  } else if (method.endsWith('close_register')) message = { name: 'REG-A', status: 'Closed', counts: [], total_sales: 1500 }
  await route.fulfill({ json: { message } })
})
const url = `http://127.0.0.1:${server.httpServer.address().port}/shift-help-check.html`
try {
  await page.goto(url, { waitUntil: 'networkidle' })
  assert.deepEqual(errors, [], 'initial render errors')
  const close = page.getByRole('button', { name: 'Close Register', exact: true })
  assert.equal(await close.isDisabled(), true, 'blank counts cannot silently become zero')
  await page.getByLabel('Counted Cash', { exact: true }).fill('bad')
  await page.getByLabel('Counted Card', { exact: true }).fill('0')
  assert.equal(await close.isDisabled(), true)
  await page.getByLabel('Counted Cash', { exact: true }).fill('-1')
  assert.equal(await close.isDisabled(), true, 'physical cash cannot be negative')
  await page.getByLabel('Counted Cash', { exact: true }).fill('6,000')
  await page.getByLabel('Counted Card', { exact: true }).fill('500')
  assert.equal(await close.isEnabled(), true)
  await page.evaluate(() => { window.test.session.queuedCount = 2 })
  await page.getByRole('button', { name: 'Check and prepare', exact: true }).click()
  await page.waitForFunction(() => window.uploads === 1)
  assert.equal(await page.getByLabel('Counted Cash', { exact: true }).inputValue(), '6,000', 'preparation preserves the physical count')
  await page.evaluate(() => { window.test.session.offline = true })
  assert.equal(await close.isDisabled(), true)
  assert.equal(await page.getByRole('button', { name: 'Check and prepare', exact: true }).isDisabled(), true)
  await page.evaluate(() => { window.test.session.offline = false })
  await page.screenshot({ path: path.join(output, 'closing-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await page.screenshot({ path: path.join(output, 'closing-mobile.png'), fullPage: true })
  await close.click()
  await page.waitForFunction(() => !window.test.session.registerOpen)
  assert.deepEqual(calls.findLast(c => c.method.endsWith('close_register')).args.counted, { Cash: 6000, Card: 500 })

  // Exact screenshot error, capped retries and ERPNext 16 opening restrictions.
  status = 'Failed'
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(`${url}?pending`, { waitUntil: 'networkidle' })
  await page.getByText('An item cost is missing', { exact: true }).waitFor()
  await page.getByText('flower bool', { exact: true }).waitFor()
  assert.equal(await page.getByRole('button', { name: /^Open a new shift/ }).count(), 0)
  assert.equal(await page.locator('.shift-help pre').isVisible(), false, 'technical details start collapsed')
  await page.getByText(/Automatic retries have paused/).waitFor()
  assert.match(await page.getByRole('link', { name: 'Check item in ERPNext' }).getAttribute('href'), /flower%20bool$/)
  await page.screenshot({ path: path.join(output, 'recovery-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await page.screenshot({ path: path.join(output, 'recovery-mobile.png'), fullPage: true })
  await page.getByText('Details for manager', { exact: true }).click()
  assert.match(await page.locator('.shift-help pre').innerText(), /ACC-SINV-2026-00037/)
  retryFails = true
  await page.getByRole('button', { name: 'Check and retry closing', exact: true }).click()
  await page.waitForFunction(() => window.notices.some(message => message.includes('Ask a manager')))
  await page.getByText('An item cost is missing', { exact: true }).waitFor()
  retryFails = false
  await page.getByRole('button', { name: 'Check and retry closing', exact: true }).click()
  await page.getByText('Finishing the shift', { exact: true }).waitFor()
  status = 'Submitted'
  await page.getByRole('button', { name: 'Open Register', exact: true }).waitFor({ timeout: 10000 })

  // A manager fixing the shift elsewhere is detected even after a failure.
  status = 'Failed'
  await page.goto(`${url}?pending&overlay`, { waitUntil: 'networkidle' })
  await page.getByText('An item cost is missing', { exact: true }).waitFor()
  assert.equal(await page.getByRole('button', { name: /^Open a new shift/ }).count(), 0)
  await page.evaluate(() => { window.test.session.permissions.close_register = false })
  await page.getByText(/You don't have permission to close registers/).waitFor()
  status = 'Submitted'
  await page.getByRole('button', { name: 'Open Register', exact: true }).waitFor({ timeout: 20000 })

  // Earlier ERPNext can keep trading; opening permission is independent of closing.
  status = 'Failed'
  await page.goto(`${url}?pending&overlay`, { waitUntil: 'networkidle' })
  await page.evaluate(() => { window.test.session.permissions.close_register = false; window.test.session.pendingClosing.new_shift_blocked = false })
  await page.getByRole('button', { name: /^Open a new shift/ }).waitFor()
  await page.evaluate(() => {
    window.test.session.multiCurrency.enabled = 1
    window.test.session.paymentModes.push({ mode_of_payment: 'Cash USD', type: 'Cash', account_currency: 'USD' })
  })
  await page.getByLabel('Cash USD float (USD)', { exact: true }).fill('-1')
  await page.getByRole('button', { name: /^Open a new shift/ }).click()
  await page.waitForFunction(() => window.notices.some(message => message.includes('Enter a valid opening float for Cash USD')))
  assert.equal(calls.some(call => call.method.endsWith('open_register')), false, 'invalid foreign float never reaches opening API')
  await page.getByLabel('Cash USD float (USD)', { exact: true }).fill('0')
  await page.screenshot({ path: path.join(output, 'opening-mobile.png'), fullPage: true })
  // Error branches and signed non-cash values through the actual browser module.
  const issues = await page.evaluate(async () => {
    const { closingIssue, invalidCountModes } = await import('/src/shiftHelp.js')
    return {
      titles: ['Negative stock is not allowed', 'Accounting Period locked', 'Not permitted', 'Income account is required', 'Deadlock found', 'Unexpected error'].map(closing_error => closingIssue({ closing_status: 'Failed', closing_error }).title),
      invalid: invalidCountModes([{ mode_of_payment: 'Credit' }], { Credit: -3690 }),
    }
  })
  assert.deepEqual(issues.titles, ['Stock needs checking', 'The posting date is locked', 'Manager access is needed', 'Accounting setup needs checking', 'A temporary posting problem', 'Closing needs a manager to check'])
  assert.deepEqual(issues.invalid, [])
  assert.deepEqual(errors, [])
  console.log('Shift help Chrome checks passed: explicit counts, queue preparation, offline guards, actionable errors, capped retries, ERPNext opening restrictions, automatic recovery and mobile layouts.')
} finally { await browser.close(); await server.close() }
