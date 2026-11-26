// Browser workflows use simulated ERPNext APIs; this never closes a live shift.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
const root = path.dirname(fileURLToPath(import.meta.url)), output = path.join(root, '../docs/screenshots/register-bank')
await mkdir(output, { recursive: true })
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><div id="app"></div><script type="module">
import {createApp,h,ref,watch} from 'vue'; import {createPinia} from 'pinia';
import RegisterView from '/src/views/RegisterView.vue'; import BankDisplaySettings from '/src/components/BankDisplaySettings.vue'; import CustomerDisplayView from '/src/views/CustomerDisplayView.vue'; import PaymentOverlay from '/src/components/PaymentOverlay.vue';
import {useSessionStore} from '/src/stores/session.js'; import {useCartStore} from '/src/stores/cart.js'; import {useCatalogStore} from '/src/stores/catalog.js'; import {displayPayment,displayTerminalId,publishCart} from '/src/customerDisplay.js'; import {bankAccounts,bankQrSource} from '/src/bankDisplay.js'; import {setCurrency} from '/src/format.js'; import '/src/styles.css';
const pinia=createPinia(),session=useSessionStore(pinia),cart=useCartStore(pinia),catalog=useCatalogStore(pinia);setCurrency('LKR');
session.posProfile='Till A';session.user='manager';session.company='Osaka City';session.currency='LKR';session.availableProfiles=['Till A','Till B'];session.permissions={is_manager:true,settings:true,close_register:true,can_cash_in:true,can_cash_out:true};session.registerSession={name:'REG-A',opened_by:'manager'};
session.settings={enable_customer_display:1,variance_reason_mode:'Required',variance_reasons:['Counting mistake']};session.paymentModes=[{mode_of_payment:'Cash',type:'Cash',account_currency:'LKR'},{mode_of_payment:'Bank Transfer',type:'Bank',account_currency:'LKR'},{mode_of_payment:'Visa',type:'Bank',account_currency:'LKR'}];session.notify=(message)=>{window.notices.push(message)};session.bootstrap=async(profile)=>{session.posProfile=profile;session.registerSession={name:profile==='Till A'?'REG-A':'REG-B',opened_by:'manager'}};session.refreshQueueCount=async()=>{};catalog.fetch=async()=>{};catalog.cacheFullCatalog=async()=>{};catalog.cacheCustomers=async()=>{};cart.quote=async()=>({payable:12500,currency:'LKR'});window.notices=[];
const stage=ref(location.hash.startsWith('#/display')?'display':'register');let lastBank=null;const fixture={company:'Osaka City (PVT) LTD',items:[{name:'Premium rice',code:'RICE',qty:1,rate:'LKR 12,500.00',amount:'LKR 12,500.00'}],count:1,total:'LKR 12,500.00',subtotal:'LKR 12,500.00',savings:'LKR 500.00'};
watch(displayPayment,value=>{lastBank=value?.bankAccounts || null;publishCart({...fixture,...value})},{deep:true});
window.test={session,cart,stage,displayTerminalId,bankAccounts,bankQrSource,showBank:(accounts)=>publishCart({...fixture,due:'LKR 12,500.00',bankAccounts:accounts}),receipt:()=>publishCart({...fixture,receipt:'INV-1'}),lastBank:()=>lastBank};
createApp({render:()=>stage.value==='register'?h(RegisterView):stage.value==='settings'?h(BankDisplaySettings):stage.value==='display'?h(CustomerDisplayView):h(PaymentOverlay,{onClose:()=>{stage.value='settings'}})}).use(pinia).mount('#app');window.ready=true;
</script></body></html>`
const server = await createServer({ root, base: '/', server: { host: '127.0.0.1', port: 0, open: false }, plugins: [{ name: 'register-bank-check', configureServer(s) { s.middlewares.use('/register-bank-check.html', async (req, res) => { res.setHeader('Content-Type', 'text/html'); res.end(await s.transformIndexHtml('/register-bank-check.html', html)) }) } }] })
await server.listen()
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe' })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } }), page = await context.newPage(), errors = [], calls = []
page.on('pageerror', e => errors.push(e.message)); page.on('dialog', d => d.accept())
await context.route('https://fonts.googleapis.com/**', r => r.abort()); await context.route('https://fonts.gstatic.com/**', r => r.abort())
const account = { bank_name: 'Receiving Bank', holder: 'Osaka City (PVT) LTD', account_number: '001234567890', branch: 'Colombo', currency: 'LKR', payment_mode: 'Bank Transfer', pos_profile: 'Till A', logo: '', qr_image: '', qr_payload: 'BANK-PAYMENT-TEST-ONLY', instructions: 'Use your invoice number as the transfer reference.', logo_size: 72, qr_size: 220 }
let config = { enabled: true, trigger: 'checkout', accounts: [account] }, closed = [], failing = '', stale = '', amounts = { 'REG-A': 5000, 'REG-B': 8000 }
function summary(name) {
  return { session: name, status: 'Open', combined_drawer: null, company_currency: 'LKR', rates: {}, sales_count: 4, total_sales: 14800, total_discounts: 500, opening_float: 1000, cash_movements: [], customer_payments: [], on_account: 2000, customer_payments_total: 0,
    activity: { sale_count: 3, return_count: 1, sales: 15800, returns: 1000, esafepos_loyalty_change_amount: 8, loyalty_points: 40, loyalty_amount: 40, earned_points: 14 },
    expected: [{ mode_of_payment: 'Cash', expected_amount: amounts[name] + (stale === name ? 1 : 0), currency: 'LKR', is_cash: 1, opening_float: 1000, net_payments: amounts[name] - 1000 }, { mode_of_payment: 'Bank Transfer', expected_amount: 4000, currency: 'LKR', payment_type: 'Bank' }, { mode_of_payment: 'Visa', expected_amount: 3000, currency: 'LKR', payment_type: 'Bank' }] }
}
await context.route('**/api/method/**', async route => {
  const method = route.request().url().split('/').pop(), args = route.request().postDataJSON() || {}; calls.push({ method, args }); let message = []
  if (method.endsWith('all_registers')) message = ['REG-A', 'REG-B'].filter(name => !closed.includes(name)).map((name, i) => ({ session: name, pos_profile: i ? 'Till B' : 'Till A', opened_by: 'manager', opened_by_name: i ? 'Ishara' : 'Arshad', opened_at: '2026-11-26 08:00:00' }))
  else if (method.endsWith('get_session_summary')) message = summary(args.session)
  else if (method.endsWith('close_register')) { if (args.session === failing) return route.fulfill({ status: 409, json: { exception: 'Closing rejected: refresh required' } }); closed.push(args.session); message = { name: args.session, status: 'Closing', counts: [] } }
  else if (method.endsWith('add_cash_movement')) { amounts[args.session] += args.movement_type === 'Cash In' ? args.amount : -args.amount; message = {} }
  else if (method.endsWith('bank_display.get_settings')) message = config
  else if (method.endsWith('bank_display.save_settings')) { config = args.config; message = config }
  else if (method.endsWith('bank_display.upload_image')) message = { file_url: '/files/bank-logo.png' }
  else if (method.endsWith('shared_drawer.summary')) message = { members: [], expected: [] }
  else if (method.endsWith('get_cashback')) message = {}
  await route.fulfill({ json: { message } })
})
const url = `http://127.0.0.1:${server.httpServer.address().port}/register-bank-check.html`
async function openAll() { await page.getByRole('button', { name: 'All registers', exact: true }).click(); await page.locator('.hub-register').nth(1).waitFor(); await page.locator('.hub-quick').nth(1).waitFor() }
async function countAll() {
  for (const name of ['REG-A', 'REG-B']) {
    await page.getByLabel(`${name} Counted Cash`, { exact: true }).fill(String(amounts[name])); await page.getByLabel(`${name} Counted Bank Transfer`, { exact: true }).fill('4000'); await page.getByLabel(`${name} Counted Visa`, { exact: true }).fill('3000')
  }
  for (const checkbox of await page.locator('.hub-review input').all()) await checkbox.check()
}
try {
  await page.goto(url); await openAll()
  await page.locator('.hub-register').first().getByRole('button', { name: 'Full summary / adjust / close', exact: true }).click()
  await page.getByText('Change saved as points', { exact: true }).waitFor()
  await page.locator('.tally-guide summary').click()
  await page.screenshot({ path: path.join(output, 'all-registers-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
  await page.screenshot({ path: path.join(output, 'all-registers-mobile.png'), fullPage: true })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  assert.equal(await page.locator('.hub-actions button').first().evaluate(e => getComputedStyle(e).transitionDuration), '0s')
  await page.emulateMedia({ reducedMotion: 'no-preference' }); await page.setViewportSize({ width: 1440, height: 1000 })
  await page.locator('.hub-adjust summary').click(); await page.getByLabel('Adjustment amount', { exact: true }).fill('200'); await page.getByLabel('Adjustment reason', { exact: true }).fill('Extra change'); await page.getByRole('button', { name: 'Record adjustment', exact: true }).click()
  await page.waitForFunction(() => document.querySelector('.hub-register')?.textContent.includes('5,200.00'))
  assert.ok(calls.some(c => c.method.endsWith('add_cash_movement') && c.args.session === 'REG-A' && c.args.amount === 200))
  await page.getByRole('button', { name: 'Review and close all registers', exact: true }).click()
  assert.equal(await page.getByRole('button', { name: 'Close all registers', exact: true }).isDisabled(), true)
  await countAll()
  stale = 'REG-A'; await page.getByRole('button', { name: 'Close all registers', exact: true }).click(); await page.getByRole('alert').filter({ hasText: 'changed' }).waitFor(); assert.equal(closed.length, 0)
  stale = ''; await page.getByRole('button', { name: 'Refresh all', exact: true }).click(); await page.getByLabel('REG-B Counted Cash', { exact: true }).waitFor(); await countAll()
  failing = 'REG-B'; await page.getByRole('button', { name: 'Close all registers', exact: true }).click(); await page.getByRole('alert').filter({ hasText: '1 register(s) sent' }).waitFor(); assert.deepEqual(closed, ['REG-A'])
  const strict = calls.find(c => c.method.endsWith('close_register')); assert.equal(strict.args.expected_tallies.Cash.amount, 5200)
  failing = ''; await page.getByRole('button', { name: 'Close all registers', exact: true }).click(); await page.getByRole('status').filter({ hasText: 'sent for closing' }).waitFor(); assert.deepEqual(closed, ['REG-A', 'REG-B'])
  closed = []; await page.reload(); await openAll(); await page.locator('.hub-register').nth(1).getByRole('button', { name: 'Switch register', exact: true }).click(); await page.waitForFunction(() => test.session.posProfile === 'Till B')
  assert.equal(await page.getByRole('button', { name: 'This register', exact: true }).getAttribute('aria-pressed'), 'true')
  await page.reload()
  // Settings + real checkout publish into the customer monitor via BroadcastChannel.
  await page.evaluate(() => { test.stage.value = 'settings' })
  await page.getByRole('button', { name: 'Save bank display settings', exact: true }).waitFor()
  await page.getByLabel('Bank name *', { exact: true }).fill('Receiving Bank')
  await page.getByRole('button', { name: 'Save bank display settings', exact: true }).click(); await page.getByRole('status').filter({ hasText: 'settings saved' }).waitFor()
  await page.screenshot({ path: path.join(output, 'bank-settings-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 }); await page.screenshot({ path: path.join(output, 'bank-settings-mobile.png'), fullPage: true }); assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), JSON.stringify(await page.evaluate(() => [...document.querySelectorAll('*')].filter(e => e.getBoundingClientRect().right > innerWidth + 1).map(e => [e.tagName, e.className, e.getBoundingClientRect().width]).slice(0, 15)))); await page.setViewportSize({ width: 1440, height: 1000 })
  assert.equal(await page.evaluate(config => test.bankAccounts(config, 'Till B', 'LKR').length, config), 0)
  assert.equal(await page.evaluate(config => test.bankAccounts(config, 'Till A', 'USD').length, config), 0)
  assert.equal(await page.evaluate(config => test.bankAccounts({ ...config, trigger: 'bank' }, 'Till A', 'LKR', 'Cash').length, config), 0)
  assert.equal(await page.evaluate(config => test.bankAccounts({ ...config, trigger: 'bank' }, 'Till A', 'LKR', 'Bank Transfer').length, config), 1)
  assert.equal(await page.evaluate(() => test.bankQrSource({ account_number: '001234' })), '', 'An account number must not become an invented payment QR')
  assert.equal(await page.evaluate(() => test.bankQrSource({ qr_image: '/files/official-qr.png', qr_payload: 'ignored' })), '/files/official-qr.png')
  const terminal = await page.evaluate(() => test.displayTerminalId), display = await context.newPage(); display.on('pageerror', e => errors.push(e.message))
  await display.goto(url + '#/display?terminal=' + terminal)
  await page.evaluate(() => { test.stage.value = 'payment' }); await display.getByRole('heading', { name: 'Bank transfer details', exact: true }).waitFor(); await display.getByText('001234567890', { exact: true }).waitFor()
  assert.equal(await display.getByRole('img', { name: 'Bank payment QR code', exact: true }).count(), 1)
  await display.waitForFunction(() => getComputedStyle(document.querySelector('.bank-transfer-card')).opacity === '1')
  await display.screenshot({ path: path.join(output, 'bank-display-desktop.png'), fullPage: true })
  await display.setViewportSize({ width: 390, height: 844 }); assert.ok(await display.evaluate(() => document.documentElement.scrollWidth <= innerWidth)); await display.screenshot({ path: path.join(output, 'bank-display-mobile.png'), fullPage: true })
  const twoAccounts = [account, { ...account, bank_name: 'Second Receiving Bank', account_number: '009876543210' }]
  await page.evaluate(accounts => test.showBank(accounts), twoAccounts)
  await display.getByRole('button', { name: 'Second Receiving Bank · 3210', exact: true }).click(); await display.getByText('009876543210', { exact: true }).waitFor()
  await page.evaluate(accounts => test.showBank(accounts), twoAccounts)
  assert.equal(await display.getByRole('button', { name: 'Second Receiving Bank · 3210', exact: true }).getAttribute('aria-pressed'), 'true', 'Payment updates must retain the customer’s receiving-account choice')
  await page.evaluate(() => { test.session.settings.bank_transfer_display = { ...test.session.settings.bank_transfer_display, trigger: 'bank' } })
  await display.getByRole('heading', { name: 'Bank transfer details', exact: true }).waitFor({ state: 'hidden' })
  await page.getByRole('button', { name: 'Bank Transfer', exact: true }).click()
  await display.getByRole('heading', { name: 'Bank transfer details', exact: true }).waitFor()
  await page.getByRole('button', { name: 'Back to sale', exact: false }).click(); await display.getByRole('heading', { name: 'Bank transfer details', exact: true }).waitFor({ state: 'hidden' })
  await page.evaluate(() => test.receipt()); await display.getByText('Sale completed', { exact: true }).waitFor(); assert.equal(await display.locator('.bank-transfer-card').count(), 0)
  assert.deepEqual(errors, []); console.log('Register directory, adjustment, strict tallies, partial close, bank settings, checkout/display lifecycle, routing and desktop/mobile checks passed.')
} catch (error) {
  console.error('Browser errors:', errors)
  console.error('Checkout state:', await page.evaluate(() => ({ stage: test.stage.value, payment: test.lastBank(), settings: test.session.settings, currency: test.session.currency })))
  for (const [index, opened] of context.pages().entries()) await opened.screenshot({ path: path.join(output, `failure-${index}.png`), fullPage: true })
  throw error
} finally { await browser.close(); await server.close() }
