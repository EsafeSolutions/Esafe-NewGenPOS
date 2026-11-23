// Real register/count components against simulated ERPNext APIs; no live shift is closed.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
const root = path.dirname(fileURLToPath(import.meta.url)), output = path.join(root, '../docs/screenshots/register')
await mkdir(output, { recursive: true })
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><div id="app"></div><script type="module">
import { createApp } from 'vue'; import { createPinia } from 'pinia'; import RegisterView from '/src/views/RegisterView.vue'; import { useSessionStore } from '/src/stores/session.js'; import '/src/styles.css'; import { setCurrency } from '/src/format.js';
const pinia = createPinia(), session = useSessionStore(pinia); setCurrency('LKR'); session.user = 'manager'; session.posProfile = 'Till A'; session.company = 'Shop'; session.currency = 'LKR'; session.registerSession = { name: 'REG-A', opening_float: 5000 }; session.permissions = { is_manager: true, close_register: true }; session.paymentModes = [{ mode_of_payment: 'Cash', type: 'Cash', account_currency: 'LKR' }, { mode_of_payment: 'Store Credit', type: 'Bank' }, { mode_of_payment: 'Cash USD', type: 'Cash', account_currency: 'USD' }]; session.settings = { variance_reason_mode: 'Optional', variance_reasons: ['Counting mistake'] }; session.notify = (message) => { window.notices.push(message) }; session.bootstrap = async () => { session.registerSession = null }; session.refreshQueueCount = async () => {}; window.notices = []; window.test = { session }; createApp(RegisterView).use(pinia).mount('#app');
</script></body></html>`
const server = await createServer({ root, base: '/', server: { host: '127.0.0.1', port: 0, open: false }, plugins: [{ name: 'register-test', configureServer(s) {
  s.middlewares.use('/register-check.html', async (req, res) => { res.setHeader('Content-Type', 'text/html'); res.end(await s.transformIndexHtml('/register-check.html', html)) })
} }] })
await server.listen()
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true, args: ['--disable-gpu'] })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } }), errors = [], calls = []
page.on('pageerror', e => errors.push(e.message))
page.on('dialog', dialog => dialog.accept())
await page.route('https://fonts.googleapis.com/**', route => route.abort())
await page.route('https://fonts.gstatic.com/**', route => route.abort())
let linked = false, rejectClose = false, version = 'v1'
const expected = [
  { mode_of_payment: 'Cash', expected_amount: 24689, currency: 'LKR', is_cash: 1 },
  { mode_of_payment: 'Store Credit', expected_amount: -3690, currency: 'LKR' },
  { mode_of_payment: 'Cash USD', expected_amount: 7.25, currency: 'USD', is_cash: 1 },
]
const own = () => ({ session: 'REG-A', combined_drawer: linked ? 'REG-A' : null, company_currency: 'LKR', rates: { USD: 300 }, expected, sales_count: 5, total_sales: 19689, total_discounts: 20, opening_float: 5000, cash_movements: [], customer_payments: [] })
const members = [{ session: 'REG-A', opened_by_name: 'Arshad', pos_profile: 'Till A', status: 'Open' }, { session: 'REG-B', opened_by_name: 'Ishara', pos_profile: 'Till B', status: 'Open' }]
const combined = () => ({ group: linked ? 'REG-A' : null, members: linked ? members : [members[0]], all_open: true, expected: expected.map(r => ({ ...r, expected_amount: linked && r.mode_of_payment === 'Cash' ? 29689 : r.expected_amount })), company_currency: 'LKR', rates: { USD: 300 }, version, sales_count: linked ? 10 : 5 })
await page.route('**/api/method/**', async route => {
  const method = route.request().url().split('/').pop(), args = route.request().postDataJSON(); calls.push({ method, args })
  let message = []
  if (method.endsWith('get_session_summary')) message = own()
  else if (method.endsWith('shared_drawer.summary')) message = combined()
  else if (method.endsWith('shared_drawer.candidates')) message = linked ? [] : [members[1]]
  else if (method.endsWith('shared_drawer.combine')) { linked = true; message = combined() }
  else if (method.endsWith('shared_drawer.close')) {
    if (rejectClose) { await route.fulfill({ status: 409, json: { exception: 'ValidationError: The combined drawer changed. Refresh, re-check the cash, then close again.' } }); return }
    message = { group: 'REG-A', sessions: [] }
  } else if (method.endsWith('close_register')) message = { name: 'REG-A', status: 'Closed', counts: [], total_sales: 1 }
  await route.fulfill({ json: { message } })
})
try {
  const url = `http://127.0.0.1:${server.httpServer.address().port}/register-check.html`
  await page.goto(url, { waitUntil: 'networkidle' })
  const lkr = page.locator('.cash-counter').filter({ hasText: 'LKR' }).first()
  await lkr.locator('summary').click()
  await page.getByLabel('LKR 1000 notes', { exact: true }).fill('24')
  await page.getByLabel('LKR 100 notes', { exact: true }).fill('6')
  await page.getByLabel('LKR 10 coins', { exact: true }).fill('8')
  await page.getByLabel('LKR 1 coins', { exact: true }).fill('9')
  assert.equal(await page.getByLabel('Counted Cash', { exact: true }).inputValue(), '24689')
  assert.equal(await page.locator('.cash-counter').count(), 2, 'cash counters exclude store credit')
  await page.screenshot({ path: path.join(output, 'counter-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await lkr.scrollIntoViewIfNeeded()
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await page.screenshot({ path: path.join(output, 'counter-mobile.png'), fullPage: true })
  await page.getByLabel('LKR 1 coins', { exact: true }).fill('2.5')
  assert.equal(await page.getByRole('button', { name: 'Close Register', exact: true }).isDisabled(), true)
  // Reload the simulated open shift and merge it with its compatible colleague.
  await page.reload({ waitUntil: 'networkidle' })
  await page.getByLabel('Shift to combine').selectOption('REG-B')
  await page.getByRole('button', { name: 'Combine shifts', exact: true }).click()
  await page.locator('.drawer-members').getByText('Ishara · Till B · REG-B', { exact: true }).waitFor()
  assert.equal(await page.getByRole('button', { name: 'Close Register', exact: true }).count(), 0)
  await page.getByLabel('Combined count Cash', { exact: true }).fill('29689')
  await page.getByLabel('Combined count Store Credit', { exact: true }).fill('-3690')
  await page.getByLabel('Combined count Cash USD', { exact: true }).fill('7.25')
  const close = page.getByRole('button', { name: 'Close all linked shifts', exact: true })
  assert.equal(await close.isDisabled(), true)
  await page.getByRole('checkbox').check()
  assert.equal(await close.isEnabled(), true)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.screenshot({ path: path.join(output, 'combined-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await page.screenshot({ path: path.join(output, 'combined-mobile.png'), fullPage: true })
  rejectClose = true
  await close.click()
  await page.getByText(/The combined drawer changed/).waitFor()
  assert.equal(await page.evaluate(() => window.test.session.registerOpen), true)
  rejectClose = false; version = 'v2'
  await page.getByRole('button', { name: 'Refresh totals', exact: true }).click()
  await page.getByRole('checkbox').check()
  await page.evaluate(() => { window.test.session.offline = true })
  assert.equal(await close.isDisabled(), true)
  await page.evaluate(() => { window.test.session.offline = false; window.test.session.queuedCount = 1 })
  await close.click()
  await page.getByText('Upload offline sales before closing.', { exact: true }).waitFor()
  await page.evaluate(() => { window.test.session.queuedCount = 0 })
  await close.click()
  await page.waitForFunction(() => !window.test.session.registerOpen)
  const closing = calls.findLast(c => c.method.endsWith('shared_drawer.close'))
  assert.equal(closing.args.version, 'v2')
  assert.deepEqual(closing.args.counted, { Cash: 29689, 'Store Credit': -3690, 'Cash USD': 7.25 })
  // Cashier devices learn about the linked group and cannot close it alone.
  await page.reload({ waitUntil: 'networkidle' })
  await page.evaluate(() => { window.test.session.permissions.is_manager = false })
  await page.getByText('A manager counts and closes all linked shifts together.', { exact: true }).waitFor()
  assert.equal(await page.getByRole('button', { name: 'Close all linked shifts', exact: true }).count(), 0)
  // A normal close retains only the active denomination breakdown. Manually
  // editing a tender discards its old physical count instead of saving both.
  linked = false
  await page.reload({ waitUntil: 'networkidle' })
  const ownLkr = page.locator('.cash-counter').filter({ hasText: 'LKR' }).first()
  await ownLkr.locator('summary').click()
  await page.getByLabel('LKR 1000 notes', { exact: true }).fill('1')
  await page.getByLabel('Counted Cash', { exact: true }).fill('1200')
  assert.equal(await page.getByLabel('LKR 1000 notes', { exact: true }).inputValue(), '')
  await page.getByLabel('LKR 1000 notes', { exact: true }).fill('2')
  await page.getByRole('button', { name: 'Close Register', exact: true }).click()
  await page.waitForFunction(() => !window.test.session.registerOpen)
  const single = calls.findLast(c => c.method.endsWith('close_register'))
  assert.equal(single.args.counted.Cash, 2000)
  assert.equal(single.args.denomination_counts.Cash.rows.find(r => r.kind === 'notes' && r.value === 1000).quantity, 2)
  assert.deepEqual(errors, [])
  console.log('Register Chrome checks passed: LKR/foreign counters, mobile layout, merged shifts, stale close, offline and queued-sale guards, combined close payload.')
} finally { await browser.close(); await server.close() }
