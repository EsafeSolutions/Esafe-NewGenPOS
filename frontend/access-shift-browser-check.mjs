// Access settings and computer movement against simulated APIs; no live users change.
import assert from 'node:assert/strict'
import { mkdir, readFile } from 'node:fs/promises'
import path from 'node:path'
import vm from 'node:vm'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
const root = path.dirname(fileURLToPath(import.meta.url)), output = path.join(root, '../docs/screenshots/user-access')
await mkdir(output, { recursive: true })
const capabilities = ['Edit price / discount', 'Cash in', 'Cash out', 'Open the register', 'Close the register', 'See sales reports', 'See profit', 'Permanently delete sales']
const presets = { Cashier: ['Cash in', 'Open the register', 'Close the register'], Supervisor: ['Cash in', 'Cash out', 'Open the register', 'Close the register', 'See sales reports'], Manager: capabilities, 'Reports only': ['See sales reports', 'See profit'] }
const access = { levels: ['Use existing roles', ...Object.keys(presets), 'Custom'], capabilities, presets, profiles: [], assignments: [], can_manage_logins: true,
  users: [{ name: 'cashier@example.com', full_name: 'Cashier', simultaneous_sessions: 1 }, { name: 'supervisor@example.com', full_name: 'Supervisor', simultaneous_sessions: 2 }] }
let settings = { shift_scope: 'Per cashier', shift_multiple_computers: 1, shared_shift_management: 0, same_day_shifts: true, companies: [], pos_profiles: [], company_settings: [] }
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><div id="app" style="height:100%"></div><script type="module">
import { createApp } from 'vue'; import { createPinia } from 'pinia'; import { createRouter, createMemoryHistory } from 'vue-router';
import SettingsView from '/src/views/SettingsView.vue'; import RegisterView from '/src/views/RegisterView.vue'; import { useSessionStore } from '/src/stores/session'; import '/src/styles.css';
const pinia = createPinia(), session = useSessionStore(pinia), register = location.search.includes('register');
session.user = 'manager'; session.posProfile = 'SHOWROOM'; session.company = 'Shop'; session.currency = 'LKR'; session.settings = { shift_multiple_computers: 0 };
session.permissions = { settings: true, is_manager: true, open_register: true, close_register: true, can_move_cash: false };
session.paymentModes = [{ mode_of_payment: 'Cash', type: 'Cash', account_currency: 'LKR' }]; session.registerSession = register ? { name: 'REG-A', opened_by: 'cashier', opening_float: 100, workstation_allowed: false } : null;
window.notices = []; session.notify = message => window.notices.push(message); session.bootstrap = async () => { session.registerSession.workstation_allowed = true };
window.test = { session }; const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:pathMatch(.*)*', component: SettingsView }] });
createApp(register ? RegisterView : SettingsView).use(pinia).use(router).mount('#app');
</script></body></html>`
const server = await createServer({ root, base: '/', server: { host: '127.0.0.1', port: 0, open: false }, plugins: [{ name: 'access-shift-check', configureServer(s) {
  s.middlewares.use('/access-shift-check.html', async (req, res) => { res.setHeader('Content-Type', 'text/html'); res.end(await s.transformIndexHtml('/access-shift-check.html', html)) })
} }] })
await server.listen()
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } }), errors = [], calls = []
page.setDefaultTimeout(12000)
page.on('pageerror', error => { errors.push(error.message); console.error(error.stack) })
page.on('dialog', dialog => dialog.accept())
await page.route('https://fonts.googleapis.com/**', route => route.abort())
await page.route('https://fonts.gstatic.com/**', route => route.abort())
let denied = false
await page.route('**/api/method/**', async route => {
  const method = route.request().url().split('/').pop(), args = route.request().postDataJSON()
  calls.push({ method, args, workstation: route.request().headers()['x-esafepos-workstation'] })
  let message = []
  if (method.endsWith('get_access_management')) message = access
  else if (method.endsWith('save_user_level')) {
    if (denied) { await route.fulfill({ status: 403, json: { exception: 'PermissionError: This user has access outside your companies.' } }); return }
    access.assignments = [{ user: args.user, access_level: args.access_level, access_profile: args.access_profile }]; message = { saved: true }
  } else if (method.endsWith('save_access_profile')) {
    access.profiles = [{ ...args.profile, modified: 'now' }]; message = { saved: true }
  } else if (method.endsWith('get_settings')) message = settings
  else if (method.endsWith('inter_company.status')) message = { pending: [], recent: [] }
  else if (method.endsWith('save_settings')) { settings = { ...settings, ...args.payload }; message = settings }
  else if (method.endsWith('get_session_summary')) message = { session: 'REG-A', expected: [{ mode_of_payment: 'Cash', expected_amount: 100, is_cash: 1 }], sales_count: 0, total_sales: 0, opening_float: 100 }
  else if (method.endsWith('shared_drawer.summary')) message = { members: [], all_open: true, expected: [] }
  else if (method.endsWith('move_shift_to_this_computer')) message = { moved: true }
  await route.fulfill({ json: { message } })
})
const last = suffix => calls.findLast(call => call.method.endsWith(suffix))
const url = `http://127.0.0.1:${server.httpServer.address().port}/access-shift-check.html`
try {
  await page.goto(url, { waitUntil: 'networkidle' })
  assert.deepEqual(errors, [])
  await page.getByRole('button', { name: 'Shift Management', exact: true }).click()
  const shared = page.getByLabel('Allow different users to use the same shift', { exact: false })
  const computers = page.getByLabel('Use the same shift on multiple computers', { exact: false })
  const manage = page.getByLabel('Shared users may manage cash and close the shift', { exact: false })
  assert.equal(await manage.isDisabled(), true)
  await shared.check(); await computers.check(); await manage.check()
  await page.getByRole('button', { name: 'Save Settings', exact: true }).click()
  await page.waitForFunction(() => window.notices.length > 0)
  assert.equal(last('save_settings').args.payload.shift_scope, 'Per outlet')
  assert.equal(last('save_settings').args.payload.shift_multiple_computers, 1)
  assert.equal(last('save_settings').args.payload.shared_shift_management, 1)
  await page.locator('.sec-card:visible').first().screenshot({ path: path.join(output, 'shift-settings-desktop.png') })
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await page.locator('.sec-card:visible').first().screenshot({ path: path.join(output, 'shift-settings-mobile.png') })
  await page.setViewportSize({ width: 1440, height: 1100 })
  await page.getByRole('button', { name: 'Approvals and access', exact: true }).click()
  await page.getByRole('heading', { name: 'ESAFE POS USER ACCESS LEVELS' }).waitFor()
  const user = page.locator('.access-user').filter({ hasText: 'cashier@example.com' })
  await page.getByLabel('Access level cashier@example.com', { exact: true }).selectOption('Cashier')
  await user.getByRole('button', { name: 'Save user', exact: true }).click()
  await page.waitForFunction(() => window.notices.includes('User access level saved'))
  assert.equal(last('save_user_level').args.access_level, 'Cashier')
  await page.getByLabel('Concurrent logins cashier@example.com', { exact: true }).fill('2')
  await user.getByRole('button', { name: 'Save login limit', exact: true }).click()
  await page.waitForFunction(() => window.notices.includes('Concurrent login limit saved'))
  assert.equal(last('save_login_limit').args.simultaneous_sessions, 2)
  await page.getByRole('button', { name: 'Create profile', exact: true }).click()
  await page.getByLabel('Profile name', { exact: true }).fill('Counter supervisor')
  await page.getByLabel('Start from access level', { exact: true }).selectOption('Supervisor')
  await page.locator('.capability-grid').getByLabel('Cash out', { exact: true }).uncheck()
  await page.locator('.user-access').screenshot({ path: path.join(output, 'access-desktop.png') })
  await page.getByRole('button', { name: 'Save profile', exact: true }).click()
  await page.waitForFunction(() => window.notices.includes('Access profile saved'))
  assert.equal(last('save_access_profile').args.profile.capabilities.find(row => row.capability === 'Cash out').allowed, 0)
  await page.getByLabel('Access level cashier@example.com', { exact: true }).selectOption('Custom')
  assert.equal(await user.getByRole('button', { name: 'Save user', exact: true }).isDisabled(), true)
  await page.getByLabel('Custom profile cashier@example.com', { exact: true }).selectOption('Counter supervisor')
  await user.getByRole('button', { name: 'Save user', exact: true }).click()
  await page.waitForFunction(() => document.querySelector('.access-user button').disabled === false)
  assert.equal(last('save_user_level').args.access_profile, 'Counter supervisor')
  await page.getByRole('button', { name: 'Counter supervisor', exact: true }).click()
  assert.equal(await page.getByLabel('Profile name', { exact: true }).isDisabled(), true)
  await page.getByLabel('Start from access level', { exact: true }).selectOption('Reports only')
  assert.equal(await page.locator('.capability-grid').getByLabel('Cash out', { exact: true }).isDisabled(), true)
  assert.equal(await page.locator('.capability-grid').getByLabel('See profit', { exact: true }).isChecked(), true)
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  for (const width of [768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    assert.equal(await page.locator('.user-access').evaluate(el => el.scrollWidth <= el.clientWidth), true)
  }
  await page.locator('.user-access').screenshot({ path: path.join(output, 'access-mobile.png') })
  denied = true
  await user.getByRole('button', { name: 'Save user', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: 'outside your companies' }).waitFor()
  const originalIdentity = last('save_user_level').workstation
  assert.match(originalIdentity, /^[A-Za-z0-9-]{16,80}$/)
  const savedIdentity = await page.evaluate(async () => (await import('/src/offline.js')).kvGet('shift-workstation'))
  assert.equal(savedIdentity, originalIdentity, 'background uploads use the same durable browser identity')
  await page.goto(`${url}?register`, { waitUntil: 'networkidle' })
  await page.getByText('This shift is assigned to another computer. Ask a manager to move it from the Register page.', { exact: true }).waitFor()
  await page.getByRole('button', { name: 'Use this computer for this shift', exact: true }).click()
  await page.waitForFunction(() => window.test.session.registerSession.workstation_allowed)
  assert.equal(last('move_shift_to_this_computer').workstation, originalIdentity, 'identity survives reload')
  assert.equal(last('move_shift_to_this_computer').args.session, 'REG-A')
  await page.evaluate(() => { window.test.session.permissions.is_manager = false })
  assert.equal(await page.getByRole('button', { name: 'Use this computer for this shift', exact: true }).count(), 0)
  const second = await browser.newContext()
  const otherPage = await second.newPage()
  await otherPage.goto(url, { waitUntil: 'domcontentloaded' })
  const otherIdentity = await otherPage.evaluate(async () => (await import('/src/workstation.js')).workstationId())
  assert.notEqual(otherIdentity, originalIdentity, 'independent browsers have different identities')
  await second.close()
  assert.deepEqual(errors, [])
  // Execute the real service-worker transport, including the new header.
  let backgroundRequest
  const context = { self: { addEventListener() {} }, fetch: async (url, options) => { backgroundRequest = options; return { ok: true, json: async () => ({ message: { saved: true } }) } }, console, URL, Set, Promise }
  vm.createContext(context)
  vm.runInContext(await readFile(path.join(root, 'public/sw.js'), 'utf8'), context)
  await vm.runInContext(`post('esafepos.api.sales.submit_sale', {}, 'csrf', 'en', '${originalIdentity}')`, context)
  assert.equal(backgroundRequest.headers['X-ESAFEPOS-Workstation'], originalIdentity)
  console.log('Access/shift Chrome checks passed: settings persistence, presets, custom profiles, reports restrictions, login limits, errors, browser binding/movement, offline identity and desktop/mobile layouts.')
} finally { await browser.close(); await server.close() }
