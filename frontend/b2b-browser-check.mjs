// Actual B2B Vue workspace against deterministic API fixtures. No live posting.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
const root = path.dirname(fileURLToPath(import.meta.url)), output = path.join(root, '../docs/screenshots/b2b')
await mkdir(output, { recursive: true })
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>
#app{display:flex;flex-direction:column}.check-header{height:48px;flex-shrink:0;background:var(--pos-blue);color:white;padding:0 18px;display:flex;align-items:center;gap:20px;font-weight:700;font-size:13px}.check-header span:last-child{margin-left:auto}.check-main{display:flex;flex:1;min-height:0}.check-rail{width:48px;flex-shrink:0;background:var(--card-bg);border-right:1px solid var(--border);display:flex;align-items:center;flex-direction:column;gap:24px;padding-top:20px;color:var(--text-muted)}@media(max-width:650px){.check-rail{display:none}.check-header{font-size:11px;padding:0 12px;gap:10px}.check-header span:last-child{display:none}}
</style></head><body><div id="app"></div><script type="module">
import {createApp,h} from 'vue';import {createPinia} from 'pinia';import {createRouter,createMemoryHistory,RouterView} from 'vue-router';import B2BView from '/src/views/B2BView.vue';import Icon from '/src/components/Icon.vue';import {useSessionStore} from '/src/stores/session.js';import {setCurrency} from '/src/format.js';import '/src/styles.css';
const pinia=createPinia(),session=useSessionStore(pinia);Object.assign(session,{company:'Weerakoon Agro',currency:'LKR',posProfile:'Cashier 2',loaded:true,user:'Administrator',registerSession:{name:'SHIFT-1'},salesPersons:[{name:'Sales team',sales_person_name:'Sales team'}]});session.settings={enable_regular_invoices:1,enable_customer_balances:1};session.notify=(message,error)=>window.notices.push({message,error});window.notices=[];window.test={session};setCurrency('LKR');
const router=createRouter({history:createMemoryHistory(),routes:[{path:'/b2b',component:B2BView},{path:'/invoices',redirect:to=>({path:'/b2b',query:{...to.query,tab:'invoices'}})},{path:'/customers',component:{render:()=>h('p','Customer account')}}]});window.test.router=router;await router.push('/invoices');await router.isReady();
createApp({render:()=>h('div',{style:'display:contents'},[h('header',{class:'check-header'},[h('span','ESAFE ERP POS'),h('span','ESAFE B2B MODULE'),h('span','Weerakoon Agro / Administrator')]),h('main',{class:'check-main'},[h('aside',{class:'check-rail'},['store','clock','person','company','bookmark','bank','report','settings'].map(name=>h(Icon,{name,size:18}))),h(RouterView)])])}).use(pinia).use(router).mount('#app');
</script></body></html>`
const server = await createServer({ root, base: '/', server: { host: '127.0.0.1', port: 0, open: false }, plugins: [{ name: 'b2b-check', configureServer(s) {
  s.middlewares.use('/b2b-check.html', async (req, res) => { res.setHeader('Content-Type', 'text/html'); res.end(await s.transformIndexHtml('/b2b-check.html', html)) })
} }] })
await server.listen()
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
page.setDefaultTimeout(15000)
const errors = [], calls = [], docs = new Map(), cheques = [], receipts = [], nativePayments = []
let count = 0, failSave = false, permissions = true, receiptCount = 0, staleSubmit = false
const customer = { name: 'CUST-001', customer_name: 'Weerakoon Farm Supplies', mobile_no: '0771234567' }
const kinds = ['Quotation', 'Sales Order', 'Delivery Note', 'Sales Invoice']
const opts = () => ({company:'Weerakoon Agro',currency:'LKR',today:'2026-11-27',warehouse:'Stores - WA',warehouses:['Stores - WA','Main warehouse - WA'],kinds:Object.fromEntries(kinds.map(kind=>[kind,Object.fromEntries(['read','create','write','submit','cancel','amend','print'].map(key=>[key,true]))])),can_pay:permissions,can_cheque:permissions,can_statement:true,can_edit_price:permissions,can_change_rate:permissions,can_create_customer:true,can_edit_customer:true,payment_modes:[{name:'Cash',type:'Cash',account:'Cash - WA'},{name:'Bank Transfer',type:'Bank',account:'Commercial Bank - WA'},{name:'Cheque',type:'Bank',account:'Commercial Bank - WA'}],payment_terms:['30 days'],terms_templates:['Standard selling terms']})
const savedInvoice = {doctype:'Sales Invoice',name:'INV-OLD',customer:'CUST-001',customer_name:customer.customer_name,currency:'LKR',docstatus:1,status:'Unpaid',posting_date:'2026-11-20',due_date:'2026-11-25',grand_total:10000,outstanding_amount:10000,modified:'1',items:[{name:'OLD-LINE',item_code:'00001',item_name:'[Super Feed] Layer Pallet',qty:1,uom:'50 kg Pack',warehouse:'Stores - WA',base_rate:10000,rate:10000,amount:10000,discount_method:'Percent',discount_value:0}]}
docs.set(savedInvoice.name,savedInvoice)
const account = () => ({currency:'LKR',outstanding:[...docs.values()].filter(row=>row.doctype==='Sales Invoice'&&row.docstatus===1).reduce((sum,row)=>sum+row.outstanding_amount,0),overdue:10000,invoices:[...docs.values()].filter(row=>row.doctype==='Sales Invoice'&&row.docstatus===1&&row.outstanding_amount>0).map(row=>({...row,debit_to:'Debtors - WA'})),advances:[{doctype:'Payment Entry',name:'ADV-001',amount:2000,posting_date:'2026-11-01'}],advance_total:2000,pending_cheques:cheques.filter(row=>['Received','Deposited'].includes(row.status)),pending_total:cheques.filter(row=>['Received','Deposited'].includes(row.status)).reduce((sum,row)=>sum+row.amount,0),can_reconcile:true,refreshed_at:'2026-11-27 10:00'})
function calculate(payload) { const result=structuredClone(payload);result.currency='LKR';result.customer_name=customer.customer_name;result.docstatus=0;result.status='Draft';result.items=result.items.map((row,index)=>{const base=row.manual_rate?row.base_rate:8500;const discount=row.discount_method==='Amount'?Number(row.discount_value||0):base*Number(row.discount_value||0)/100;return {...row,name:row.name||`LINE-${index}`,item_name:'[Super Feed] Layer Pallet',base_rate:base,rate:base-discount,price_list_rate:8500,discount_amount:8500-(base-discount),discount_percentage:(8500-(base-discount))/8500*100,amount:(base-discount)*Number(row.qty)}});result.net_total=result.grand_total=result.items.reduce((sum,row)=>sum+row.amount,0);result.total_taxes_and_charges=0;result.connections=[];return result }
page.on('pageerror', error => errors.push(error.message))
page.on('dialog', dialog => dialog.accept())
await page.route('https://fonts.googleapis.com/**', route => route.abort())
await page.route('https://fonts.gstatic.com/**', route => route.abort())
await page.context().route('**/mock-print**', route=>route.fulfill({contentType:'text/html',body:'<!doctype html><h1>Native ERPNext print preview</h1>'}))
await page.route('**/api/method/**', async route => {
  const method=route.request().url().split('/').pop(),args=route.request().postDataJSON();calls.push({method,args});let message={}
  const refuse=async text=>route.fulfill({status:403,json:{exception:`ValidationError: ${text}`}})
  if(method.endsWith('b2b.get_context'))message=opts()
  else if(method.endsWith('search_customers'))message={items:[customer]}
  else if(method.endsWith('customer_detail'))message={...customer,stats:{},wallet:{}}
  else if(method.endsWith('customer_options'))message={addresses:[{name:'Farm billing',address_title:'Farm billing'}],contacts:[{name:'Sales contact',full_name:'Purchasing manager'}]}
  else if(method.endsWith('customer_account'))message=account()
  else if(method.endsWith('list_documents'))message={items:[...docs.values()].filter(row=>row.doctype===args.doctype&&(!args.status||row.docstatus==={Draft:0,Submitted:1,Cancelled:2}[args.status])),has_more:false}
  else if(method.endsWith('get_document'))message=docs.get(args.name)
  else if(method.endsWith('search_items'))message=[{name:'00001',item_name:'[Super Feed] Layer Pallet',stock_uom:'50 kg Pack'}]
  else if(method.endsWith('item_units'))message={stock_uom:'Kg',units:[{uom:'Kg',conversion_factor:1},{uom:'50 kg Pack',conversion_factor:50}]}
  else if(method.endsWith('b2b.preview'))message=calculate(args.payload)
  else if(method.endsWith('save_document')){if(failSave)return refuse('Save refused; draft retained');message=calculate(args.payload);message.name=args.payload.name||`B2B-${++count}`;message.modified=String(Date.now());docs.set(message.name,message)}
  else if(method.endsWith('submit_document')){if(staleSubmit)return refuse('This draft changed elsewhere');message=docs.get(args.name);message.docstatus=1;message.status='Unpaid';message.outstanding_amount=message.grand_total;message.modified=String(Date.now())}
  else if(method.endsWith('convert_document')){const source=docs.get(args.name);message={...structuredClone(source),doctype:args.target,name:`B2B-${++count}`,docstatus:0,status:'Draft',modified:String(Date.now()),connections:[{doctype:source.doctype,name:source.name}]};docs.set(message.name,message)}
  else if(method.endsWith('cancel_and_amend')){const source=docs.get(args.name);source.docstatus=2;message={...structuredClone(source),name:`B2B-${++count}`,docstatus:0,status:'Draft',amended_from:source.name,modified:String(Date.now())};docs.set(message.name,message)}
  else if(method.endsWith('sales_progress')){const source=docs.get(args.name);message={percent:source?.docstatus===1?60:0,complete:false,stages:kinds.map(doctype=>({doctype,state:doctype===source?.doctype?(source.docstatus===1?'Complete':'Draft'):'Skipped'})).concat([{doctype:'Payment',state:'In progress'}]),documents:[source],outstanding:source?.outstanding_amount||0,pending_cheques:cheques.filter(row=>row.status!=='Cleared').length}}
  else if(method.endsWith('list_payments'))message={items:nativePayments,settlements:receipts.map(row=>({name:row.name,posting_date:row.posting_date,amount:row.amount,collection_context:row.collection_context})),has_more:false}
  else if(method.endsWith('receive_settlement')){const payload=args.payload;message={doctype:'EsafePOS B2B Settlement',name:`RECEIPT-${++receiptCount}`,customer:customer.name,customer_name:customer.customer_name,company:'Weerakoon Agro',currency:'LKR',posting_date:payload.posting_date,collection_context:payload.collection_context,rows:[],amount:payload.tenders.reduce((sum,row)=>sum+row.amount,0)};for(const tender of payload.tenders){const refs=payload.allocations.map(row=>({reference_name:row.name,allocated_amount:Math.min(row.amount,tender.amount)}));const row={...tender,allocations:refs};if(tender.method==='Cheque'){const cheque={...tender,name:`CHEQUE-${cheques.length+1}`,customer:customer.name,status:'Received',currency:'LKR',cheque_date:tender.reference_date,modified:'1',allocations:JSON.stringify(refs.map(ref=>({name:ref.reference_name,amount:ref.allocated_amount}))),history:'[]'};cheques.push(cheque);row.cheque=cheque.name;row.status='Received'}else{row.payment=`PAY-${nativePayments.length+1}`;nativePayments.push({name:row.payment,posting_date:payload.posting_date,docstatus:1,status:'Submitted',mode_of_payment:tender.mode_of_payment,paid_amount:tender.amount,paid_from_account_currency:'LKR'});if(refs[0])docs.get(refs[0].reference_name).outstanding_amount-=tender.amount}message.rows.push(row)}receipts.push(message)}
  else if(method.endsWith('settlement_receipt'))message=receipts.find(row=>row.name===args.name)
  else if(method.endsWith('list_cheques'))message={items:cheques.filter(row=>!args.status||row.status===args.status),has_more:false}
  else if(method.endsWith('transition_cheque')){message=cheques.find(row=>row.name===args.name);message.status={deposit:'Deposited',clear:'Cleared',bounce:'Bounced',return:'Returned',cancel:'Cancelled'}[args.action];message.modified=String(Date.now());if(args.action==='clear'){message.clearance_date=args.event_date;message.payment_entry='PAY-CHEQUE';for(const ref of args.allocations)docs.get(ref.name).outstanding_amount-=ref.amount}message.history=JSON.stringify([...JSON.parse(message.history),{action:args.action,date:args.event_date,user:'Administrator',reason:args.reason}])}
  else if(method.endsWith('apply_advance'))message={doctype:'EsafePOS B2B Settlement',name:'RECEIPT-ADVANCE',customer_name:customer.customer_name,company:'Weerakoon Agro',currency:'LKR',posting_date:'2026-11-27',collection_context:'Advance allocation',rows:[{method:'Existing advance',amount:args.allocations.reduce((sum,row)=>sum+row.amount,0),source:args.payment,allocations:args.allocations.map(row=>({reference_name:row.name,allocated_amount:row.amount}))}]}
  else if(method.endsWith('customer_statement'))message={customer:customer.name,customer_name:customer.customer_name,company:'Weerakoon Agro',currency:'LKR',from_date:args.from_date,to_date:args.to_date,opening:2000,closing:12000,debit:15000,credit:5000,pending_total:account().pending_total,rows:[{date:'2026-11-20',doctype:'Sales Invoice',name:'INV-OLD',debit:15000,credit:0,balance:17000,can_open:true},{date:'2026-11-25',doctype:'Payment Entry',name:'PAY-OLD',debit:0,credit:5000,balance:12000,can_open:true}],refreshed_at:'2026-11-27 10:00'}
  else if(method.endsWith('statement_pdf'))message={format:'pdf',data:Buffer.from('%PDF-1.4\n%%EOF').toString('base64')}
  else if(method.endsWith('document_printview'))message={url:`/mock-print?doctype=${encodeURIComponent(args.doctype)}&name=${encodeURIComponent(args.name)}`}
  else throw new Error(`Unmocked API: ${method}`)
  await route.fulfill({json:{message}})
})
const tab = label => page.getByRole('tab',{name:label,exact:true})
const settleTab = () => tab('Payments').first()
try {
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/b2b-check.html`,{waitUntil:'networkidle',timeout:60000})
  await page.getByRole('heading',{name:'ESAFE B2B MODULE'}).waitFor()
  assert.equal(await page.evaluate(()=>window.test.router.currentRoute.value.query.tab),'invoices','legacy route redirects')
  await page.locator('#b2b-customer').fill('farm');await page.getByRole('button',{name:/Weerakoon Farm Supplies/}).click()
  await page.getByRole('button',{name:'New Sales Invoice',exact:true}).click()
  await page.locator('#b2b-item-search').fill('feed');await page.getByRole('button',{name:/Super Feed/}).click()
  await page.getByRole('spinbutton',{name:'Quantity',exact:true}).fill('6')
  await page.getByRole('spinbutton',{name:'Line discount',exact:true}).fill('5')
  await page.getByText('Totals confirmed',{exact:true}).waitFor()
  assert.match(await page.locator('.b2b-document-totals').innerText(),/48,450/)
  await page.getByRole('button',{name:'Save draft',exact:true}).click();await page.getByText('Draft B2B-1 saved',{exact:true}).count()
  await page.getByRole('heading',{name:'B2B-1',exact:true}).waitFor()
  assert.equal(docs.get('B2B-1').docstatus,0,'save does not submit')
  assert.equal(calls.filter(row=>row.method.endsWith('document_printview')).length,0,'save does not print')
  await page.screenshot({path:path.join(output,'invoice-desktop.png'),fullPage:true})
  for(const [width,height] of [[1024,768],[768,1024],[390,844]]){await page.setViewportSize({width,height});await page.screenshot({path:path.join(output,`invoice-${width}.png`),fullPage:true});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true,`no page overflow at ${width}`)}
  await page.setViewportSize({width:1440,height:1000})
  await page.getByRole('spinbutton',{name:'Quantity',exact:true}).fill('7');failSave=true
  await page.getByRole('button',{name:'Save draft',exact:true}).click();await page.getByRole('alert').filter({hasText:'Save refused'}).waitFor()
  assert.equal(await page.getByRole('spinbutton',{name:'Quantity',exact:true}).inputValue(),'7','failed save retains editor')
  const failedKey=calls.filter(row=>row.method.endsWith('save_document')).at(-1).args.idempotency_key
  failSave=false;await page.getByRole('button',{name:'Save draft',exact:true}).click()
  await page.waitForFunction(()=>window.notices.filter(row=>row.message.includes('saved')).length>=2)
  assert.equal(calls.filter(row=>row.method.endsWith('save_document')).at(-1).args.idempotency_key,failedKey,'save retry retains identity')
  staleSubmit=true;await page.getByRole('button',{name:'Submit',exact:true}).click();await page.getByRole('alert').filter({hasText:'changed elsewhere'}).waitFor();assert.equal(docs.get('B2B-1').docstatus,0)
  staleSubmit=false;await page.getByRole('button',{name:'Submit',exact:true}).click();await page.getByRole('button',{name:'Create Delivery Note',exact:true}).waitFor()
  const popup=page.waitForEvent('popup');await page.getByRole('button',{name:'Print',exact:true}).click();const print=await popup;await print.waitForURL('**/mock-print**');assert.match(print.url(),/B2B-1/);await print.close()
  await page.getByRole('tab',{name:'Payments',exact:true}).last().click();await page.getByRole('button',{name:'Take payment',exact:true}).click()
  await page.getByRole('heading',{name:'Customer settlement',exact:true}).waitFor()
  await page.getByRole('spinbutton',{name:'Allocate to B2B-1',exact:true}).fill('10000')
  await page.locator('.b2b-tender input[type=number]').first().fill('5000')
  await page.getByRole('button',{name:'Add split payment',exact:true}).click()
  const second=page.locator('.b2b-tender').nth(1);await second.locator('select').first().selectOption('Cheque');await second.locator('input[type=number]').fill('5000');await second.locator('input').nth(1).fill('000123');await second.locator('input[type=date]').fill('2026-11-27');await second.locator('input').last().fill('Commercial Bank')
  await page.screenshot({path:path.join(output,'settlement-desktop.png'),fullPage:true})
  await page.getByRole('button',{name:'Confirm settlement',exact:true}).click();await page.getByRole('heading',{name:'Customer settlement receipt',exact:true}).waitFor()
  assert.equal(nativePayments.length,1,'cheque receipt creates no posted payment')
  assert.match(await page.locator('.b2b-receipt').innerText(),/Awaiting clearance/)
  await tab('Cheques').click();await page.getByRole('button',{name:'Deposit cheque',exact:true}).click();await page.getByRole('button',{name:'Confirm Deposit cheque',exact:true}).click();await page.getByRole('button',{name:'Clear cheque',exact:true}).waitFor()
  await page.getByRole('button',{name:'Clear cheque',exact:true}).click();await page.getByRole('button',{name:'Confirm Clear cheque',exact:true}).click();await page.getByText('PAY-CHEQUE',{exact:true}).waitFor();assert.equal(cheques[0].status,'Cleared')
  await page.screenshot({path:path.join(output,'cheques-desktop.png'),fullPage:true})
  await tab('Customer Summary').click();await page.getByText('Closing balance',{exact:true}).waitFor();assert.match(await page.locator('.b2b-account-metrics').last().innerText(),/12,000/)
  const statementPopup=page.waitForEvent('popup');await page.getByRole('button',{name:'Print / PDF',exact:true}).click();const pdf=await statementPopup;await pdf.close();assert(calls.some(row=>row.method.endsWith('statement_pdf')))
  await tab('Quotations').click();await page.getByRole('button',{name:'New Quotation',exact:true}).click();await page.locator('#b2b-item-search').fill('feed');await page.getByRole('button',{name:/Super Feed/}).click();await page.getByRole('button',{name:'Save draft',exact:true}).click();await page.getByRole('button',{name:'Submit',exact:true}).click();await page.getByRole('button',{name:'Create Sales Order',exact:true}).click();await page.getByRole('button',{name:'Submit',exact:true}).waitFor();assert.equal([...docs.values()].at(-1).doctype,'Sales Order')
  await page.getByRole('tab',{name:'Connections',exact:true}).click();assert.match(await page.locator('.b2b-connection').innerText(),/Quotation/)
  await tab('Overview').click();await page.getByRole('button',{name:'New invoice',exact:true}).waitFor();await page.screenshot({path:path.join(output,'process-desktop.png'),fullPage:true})
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'process-mobile.png'),fullPage:true})
  await page.evaluate(()=>window.test.session.offline=true);assert.equal(await page.getByRole('button',{name:'New invoice',exact:true}).isDisabled(),true)
  permissions=false
  await page.reload({waitUntil:'networkidle'})
  await page.locator('#b2b-customer').fill('farm');await page.getByRole('button',{name:/Weerakoon Farm Supplies/}).click()
  await page.getByRole('button',{name:'New Sales Invoice',exact:true}).click();await page.locator('#b2b-item-search').fill('feed');await page.getByRole('button',{name:/Super Feed/}).click()
  assert.equal(await page.getByRole('spinbutton',{name:'Rate',exact:true}).isDisabled(),true)
  assert.equal(await page.getByRole('spinbutton',{name:'Line discount',exact:true}).isDisabled(),true)
  await tab('Payments').first().click();assert.equal(await page.getByRole('button',{name:'Confirm settlement',exact:true}).isDisabled(),true)
  assert.equal(errors.length,0,errors.join('\n'))
  console.log('B2B browser checks passed: drafts, discounts, retry/stale guards, submission, native print, split settlement, cheque lifecycle, statement PDF, quote/order mapping, responsive layouts, offline and permission controls.')
} finally { if(errors.length)console.error(errors);await browser.close();await server.close() }
