// The real HR Vue workspace with deterministic fixtures; no live HR/payroll posting.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
const root = path.dirname(fileURLToPath(import.meta.url)), output = path.join(root, '../docs/screenshots/hr')
await mkdir(output, { recursive: true })
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
#app{display:flex;flex-direction:column}.check-header{height:50px;background:var(--pos-blue);color:white;padding:0 20px;display:flex;align-items:center;gap:24px;flex-shrink:0;font-weight:600}.check-header span:last-child{margin-left:auto}.check-main{display:flex;flex:1;min-height:0}.check-rail{width:48px;flex-shrink:0;display:flex;align-items:center;flex-direction:column;gap:25px;padding-top:20px;background:var(--card-bg);border-right:1px solid var(--border);color:var(--text-muted)}@media(max-width:700px){.check-rail{display:none}.check-header{padding:0 16px;font-size:12px}.check-header span:last-child{display:none}}
</style></head><body><div id="app"></div><script type="module">
import {createApp,h} from 'vue';import {createPinia} from 'pinia';import HRView from '/src/views/HRView.vue';import Icon from '/src/components/Icon.vue';import {useSessionStore} from '/src/stores/session.js';import '/src/styles.css';
const pinia=createPinia(),session=useSessionStore(pinia);Object.assign(session,{company:'ESAFE Retail',currency:'LKR',loaded:true,user:'payroll@example.com'});session.settings={enable_hr_integration:1};session.permissions={hr:true};window.test={session};
createApp({render:()=>h('div',{style:'display:contents'},[h('header',{class:'check-header'},[h('span','ESAFE ERP POS'),h('span','Human resources'),h('span','ESAFE Retail')]),h('main',{class:'check-main'},[h('aside',{class:'check-rail'},['store','clock','person','company','bank','report','settings'].map(name=>h(Icon,{name,size:18}))),h(HRView)])])}).use(pinia).mount('#app');
</script></body></html>`
const server = await createServer({ root, base: '/', server: { host: '127.0.0.1', port: 0, open: false }, plugins: [{ name: 'hr-check', configureServer(s) {
  s.middlewares.use('/hr-check.html', async (req, res) => { res.setHeader('Content-Type', 'text/html'); res.end(await s.transformIndexHtml('/hr-check.html', html)) })
} }] })
await server.listen()
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
page.setDefaultTimeout(15000)
const errors = [], calls = [], attendance = [{name:'HR-ATT-2026-001',attendance_date:'2026-11-26',status:'Present',docstatus:1}], claims = [], batches = [], salarySlips = []
let manager = true, payrollUser = true, failClaim = true, hideAttendance = false, rejectPost = false
const features = {enable_hr_integration:1,enable_attendance:1,enable_expense_claims:1,enable_day_salary:1,enable_sales_commissions:1,enable_commission_payroll:1}
const context = () => ({company:'ESAFE Retail',currency:'LKR',today:'2026-11-28',refreshed_at:'2026-11-28 12:30',versions:{frappe:'16.x',erpnext:'16.x',hrms:'16.x'},features:{...features,enable_attendance:hideAttendance?0:1},employees:[{name:'EMP-001',employee_name:'Nimal Perera',department:'Retail'},{name:'EMP-002',employee_name:'Ayesha Fernando',department:'Retail'}],can_attendance:manager,can_payroll:payrollUser,can_approve:manager,payroll_settings:{payroll_based_on:'Attendance',daily_wages_fraction_for_half_day:0.5,include_holidays_in_total_working_days:0,consider_unmarked_attendance_as:'Absent'},components:manager?['Daily wage','Sales commission']:[],expense_types:['Travel','Meals'],schema_ready:true,permissions:{Attendance:{read:true,create:manager,submit:manager},'Expense Claim':{read:true,create:true,submit:false},'Additional Salary':{read:payrollUser,create:manager,submit:manager},'Salary Slip':{read:payrollUser,create:payrollUser,submit:manager}}})
page.on('pageerror', error => errors.push(error.message))
await page.route('https://fonts.googleapis.com/**', route => route.abort())
await page.route('https://fonts.gstatic.com/**', route => route.abort())
await page.route('**/api/method/**', async route => {
  const method = route.request().url().split('.').pop(), args = route.request().postDataJSON(); calls.push({method,args})
  let message
  if(method==='get_context') message=context()
  else if(method==='list_attendance') message=attendance
  else if(method==='mark_attendance') {const row={name:'HR-ATT-2026-002',attendance_date:args.attendance_date,status:args.status,docstatus:1};attendance.unshift(row);message={name:row.name}}
  else if(method==='list_claims') message=claims
  else if(method==='create_claim') {
    if(failClaim) return route.fulfill({status:503,json:{exception:'ValidationError: Claim response unavailable; retry with the same request'}})
    const row={name:'HR-EXP-2026-001',posting_date:'2026-11-28',approval_status:'Draft',status:'Draft',total_claimed_amount:args.amount,total_amount_reimbursed:0,docstatus:0};claims.push(row);message=row
  }
  else if(method==='list_payroll') message=batches
  else if(method==='preview_salary') message={employee:args.employee,employee_name:'Nimal Perera',company:'ESAFE Retail',currency:'LKR',salary_structure:'Retail monthly salary',start_date:'2026-10-01',end_date:'2026-10-31',payment_days:23.5,total_working_days:26,gross_pay:75000,total_deduction:5000,net_pay:70000,fingerprint:'native-salary',earnings:[{salary_component:'Basic salary',amount:65000},{salary_component:'Daily allowance',amount:10000}],deductions:[{salary_component:'EPF',amount:5000}]}
  else if(method==='list_salary_slips') message=salarySlips
  else if(method==='save_salary_draft') {message={name:'HR-SAL-2026-00001',start_date:'2026-10-01',end_date:'2026-10-31',docstatus:0,currency:'LKR',net_pay:70000};salarySlips.push(message)}
  else if(method==='preview_payroll') message={company:'ESAFE Retail',employee:args.employee,employee_name:'Nimal Perera',month:args.month,kind:'Commission',component:args.component,currency:'LKR',amount:8750,fingerprint:'fresh-preview',warning:'Submitted invoice incentives, net of returns. Consolidated invoices excluded.',sources:[{doctype:'POS Invoice',name:'ACC-SINV-2026-00024',sales_person:'Nimal',allocated_percentage:100,incentives:10000},{doctype:'Sales Invoice',name:'ACC-SINV-RET-00003',sales_person:'Nimal',allocated_percentage:100,incentives:-1250}]}
  else if(method==='prepare_payroll') {message={name:'HR-PAY-001',kind:args.kind,employee:args.employee,month:args.month,amount:8750,currency:'LKR',status:'Draft'};batches.push(message)}
  else if(method==='approve_payroll') {message=batches.find(row=>row.name===args.name);Object.assign(message,{status:'Approved',approved_by:'payroll.manager@example.com'})}
  else if(method==='post_payroll') {if(rejectPost)return route.fulfill({status:409,json:{exception:'ValidationError: Payroll inputs changed after preparation'}});message=batches.find(row=>row.name===args.name);Object.assign(message,{status:'Posted',additional_salary:'HR-ADS-2026-00001'})}
  else throw new Error(`Unexpected API ${method}`)
  await route.fulfill({json:{message}})
})
const button = label => page.getByRole('button',{name:label,exact:true})
async function idle(){await page.waitForFunction(()=>!document.querySelector('.hr-heading-actions button')?.disabled)}
async function shot(name,width=1440,height=1000){await page.setViewportSize({width,height});await idle();await page.locator('.hr-workspace').evaluate(el=>el.scrollTop=0);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`no horizontal page overflow: ${name}`);await page.screenshot({path:path.join(output,name+'.png'),fullPage:true})}
async function detailShot(name,heading){await page.getByRole('heading',{name:heading,exact:true}).evaluate(el=>el.scrollIntoView({block:'start'}));await page.screenshot({path:path.join(output,name+'.png'),fullPage:true})}
try {
  await page.goto(`http://127.0.0.1:${server.config.server.port}/hr-check.html`,{waitUntil:'networkidle'})
  await button('Attendance').waitFor(); await shot('overview-desktop')
  await button('Attendance').click();await page.getByText('HR-ATT-2026-001',{exact:true}).waitFor()
  await page.getByLabel('Attendance date',{exact:true}).fill('2026-11-27');await page.getByLabel('Reason',{exact:true}).fill('Missed check-in reviewed by HR manager')
  await button('Record attendance').click();await page.getByRole('status').filter({hasText:'Attendance recorded'}).waitFor()
  await shot('attendance-desktop');await shot('attendance-mobile',390,844);await detailShot('attendance-form-mobile','Record attendance exception')
  await button('Expense claims').click();await page.getByLabel('Expense type',{exact:true}).selectOption('Travel');await page.getByLabel(/Amount/).fill('1850');await page.getByLabel('Description',{exact:true}).fill('Travel to outlet for stock handover')
  await button('Save claim draft').click();await page.getByRole('alert').filter({hasText:'Claim response unavailable'}).waitFor();const retryKey=calls.filter(row=>row.method==='create_claim').at(-1).args.request_id
  failClaim=false;await button('Save claim draft').click();await page.getByRole('link',{name:/Attach receipts and submit claim/}).waitFor();assert.equal(calls.filter(row=>row.method==='create_claim').at(-1).args.request_id,retryKey)
  assert.equal(claims[0].docstatus,0);await shot('claims-mobile',390,844)
  await button('Daily salary').click();await page.getByLabel('Month',{exact:true}).fill('2026-10');await idle();await button('Preview native salary').click();await page.getByRole('heading',{name:'Native Salary Slip preview'}).waitFor()
  assert.equal(salarySlips.length,0,'native preview creates no Salary Slip');assert.equal(await page.getByLabel('Half-day payable weight').count(),0,'no custom day-rate policy editor')
  await shot('daily-payroll-desktop');await shot('daily-payroll-tablet',768,1024);await shot('daily-salary-mobile',390,844);await detailShot('daily-salary-components-mobile','Native Salary Slip preview')
  await button('Save native Salary Slip draft').click();await page.getByRole('link',{name:'HR-SAL-2026-00001',exact:true}).waitFor();assert.equal(salarySlips[0].docstatus,0,'native draft is not submitted')
  const salaryPayload=calls.find(row=>row.method==='save_salary_draft').args;assert.equal('amount' in salaryPayload,false);assert.equal('payment_days' in salaryPayload,false)
  await button('Commission payroll').click();await idle();await page.getByLabel('Commission component',{exact:true}).selectOption('Sales commission');await idle();await button('Preview earnings').click();await page.getByRole('heading',{name:'Earnings preview'}).waitFor()
  assert.equal(batches.length,0,'commission preview creates no payout')
  await button('Save payroll period').click();await button('Approve period').waitFor();assert.equal(batches[0].status,'Draft');assert.equal(await button('Post to payroll').count(),0)
  await button('Approve period').click();await button('Post to payroll').waitFor();rejectPost=true;await button('Post to payroll').click();await page.getByRole('alert').filter({hasText:'inputs changed'}).waitFor();assert.equal(batches[0].status,'Approved')
  rejectPost=false;await button('Post to payroll').click();await page.getByRole('link',{name:'HR-ADS-2026-00001'}).waitFor();assert.equal(batches[0].status,'Posted');assert.equal(await button('Post to payroll').count(),0)
  await button('Preview earnings').click();await page.getByRole('link',{name:'ACC-SINV-RET-00003',exact:true}).waitFor();await shot('commission-desktop');await shot('commission-mobile',390,844);await detailShot('commission-sources-mobile','Earnings preview')
  await page.evaluate(()=>window.test.session.offline=true);assert.equal(await button('Preview earnings').isDisabled(),true);assert.equal(await button('Save payroll period').isDisabled(),true)
  await page.evaluate(()=>window.test.session.offline=false)
  manager=false;payrollUser=false;hideAttendance=true;await page.reload({waitUntil:'networkidle'});await button('Expense claims').waitFor();assert.equal(await button('Attendance').count(),0);assert.equal(await button('Daily salary').count(),0);assert.equal(await button('Commission payroll').count(),0)
  await button('Expense claims').click();await page.getByRole('heading',{name:'New expense claim'}).waitFor()
  await page.evaluate(()=>window.test.session.settings.enable_hr_integration=0);await page.getByRole('alert').filter({hasText:'HR is disabled'}).waitFor();assert.equal(await button('Save claim draft').count(),0)
  assert.deepEqual(errors,[])
  console.log('HR browser checks passed: attendance, draft claims, retry identity, native salary preview/draft, commission preview/save/approve/post, stale input rejection, native links, permissions, switches, offline, desktop/tablet/mobile and screenshots.')
} catch(error) { console.error((await page.locator('.hr-workspace').innerText()).slice(0,4000));throw error } finally {if(errors.length)console.error(errors);await browser.close();await server.close()}
