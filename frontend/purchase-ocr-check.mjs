// Scanner UX checks use explicit fixtures, never a real API key or Google call.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
const root = path.dirname(fileURLToPath(import.meta.url))
const output = path.join(root, '../docs/screenshots/buying-ocr')
await mkdir(output, { recursive: true })
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><title>Invoice scanner verification</title></head><body style="overflow:hidden"><header style="height:52px;background:var(--pos-blue);color:white;display:flex;align-items:center;justify-content:space-between;padding:0 20px"><b>ESAFE ERP POS / Buying</b><span>Weerakoon Agro</span></header><div id="app" style="height:calc(100dvh - 52px);display:flex;overflow:hidden"></div><script type="module">
import {createApp} from 'vue'; import {createPinia} from 'pinia'; import BuyingView from '/src/views/BuyingView.vue'; import {useSessionStore} from '/src/stores/session.js'; import '/src/styles.css';
const pinia=createPinia(),session=useSessionStore(pinia);session.posProfile='Main till';session.company='Weerakoon Agro';session.currency='LKR';session.settings.enable_buying=1;session.permissions={buying:true};window.test={session};createApp(BuyingView).use(pinia).mount('#app');</script></body></html>`
const server = await createServer({ root, base: '/', cacheDir: 'node_modules/.vite-ocr-check', server: { port: 0, host: '127.0.0.1', open: false }, plugins: [{ name: 'ocr-check', configureServer(s) { s.middlewares.use('/ocr-check.html', async (req,res) => {res.setHeader('Content-Type','text/html');res.end(await s.transformIndexHtml('/ocr-check.html',html))}) } }] })
await server.listen()
const browser = await chromium.launch({ headless:true, executablePath:process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe' })
const page = await browser.newPage({ viewport:{width:1440,height:1050} })
page.setDefaultTimeout(30000)
const errors=[], calls=[]
page.on('pageerror', e=>errors.push(e.message))
await page.route('https://fonts.googleapis.com/**', r=>r.abort()); await page.route('https://fonts.gstatic.com/**', r=>r.abort())
const supplier={name:'SUP-001',supplier_name:'Greenfield Agri Supplies',supplier_group:'Agriculture'}
const seed={name:'SEED-025',item_name:'Premium vegetable seed',stock_uom:'Packet',is_stock_item:1,last_purchase_rate:100}
const fertilizer={name:'FERT-050',item_name:'Organic fertilizer',stock_uom:'Kg',is_stock_item:1,last_purchase_rate:60}
let enabled=false, configured=false, failScan=false, duplicate=false, foreign=false, failAccount=true
await page.route('**/api/method/**', async route=>{
  const method=route.request().url().split('.').pop(),args=route.request().postDataJSON();calls.push({method,args})
  let message=[]
  if(method==='options')message={company:'Weerakoon Agro',currency:'LKR',today:'2026-11-26',warehouse:'Main Stores - WA',warehouses:['Main Stores - WA'],cost_accounts:['Freight and handling - WA'],tax_accounts:['Input tax - WA'],supplier_groups:['Agriculture'],can_create_supplier:true,can_create_invoice:true,can_pay:true,payment_modes:[{name:'Cash',type:'Cash',account:'Cash - WA'}]}
  if(method==='search_suppliers')message=[supplier]
  if(method==='supplier_account'){
    if(failAccount){failAccount=false;await route.fulfill({status:417,contentType:'application/json',body:JSON.stringify({exc_type:'ValidationError',exception:'ValidationError: Supplier account is temporarily unavailable.'})});return}
    message={currency:'LKR',balance:0,open_invoices:[],invoices:[],payments:[]}
  }
  if(method==='scan_status')message={enabled,configured,max_bytes:8388608,migrated:true,can_configure:true}
  if(method==='get_config')message={enabled,configured,model:'gemini-3.5-flash-lite'}
  if(method==='save_config'){enabled=Boolean(args.enabled);configured=Boolean(args.api_key);message={enabled,configured,model:args.model}}
  if(method==='search_items')message=[fertilizer]
  if(method==='check_invoice_reference')message=duplicate?[{name:'PINV-EXISTS',docstatus:1}]:[]
  if(method==='scan_invoice'){
    if(failScan){failScan=false;await route.fulfill({status:429,contentType:'application/json',body:JSON.stringify({exc_type:'ValidationError',exception:'ValidationError: Gemini quota is temporarily unavailable. Check billing or try again later.'})});return}
    message={supplier_name:supplier.supplier_name,invoice_number:'GF-2959',invoice_date:'2026-11-25',due_date:'2026-12-25',currency:foreign?'USD':'LKR',total:2714,tax_amount:414,discount_amount:0,
      suppliers:[supplier],matched_supplier:supplier.name,duplicate_invoices:[],warnings:['Check the fertilizer bag size against the stock unit.'],
      items:[{description:seed.item_name,item_code:seed.name,unit:'Packet',quantity:10,unit_price:100,amount:1000,candidates:[seed],matched_item:seed.name},{description:'Organic fertilizer — 20 kg bag',item_code:'SUPPLIER-BAG',unit:'Bag',quantity:1,unit_price:1200,amount:1200,candidates:[],matched_item:''}],additional_costs:[{description:'Freight',amount:100}]}
  }
  if(method==='create_invoice')message={name:'PINV-SCAN-1',grand_total:2714}
  await route.fulfill({contentType:'application/json',body:JSON.stringify({message})})
})
async function shot(name){await page.screenshot({path:path.join(output,name)});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),name)}
try{
  // A synthetic invoice image is the uploaded fixture, not an OCR accuracy claim.
  const source=await browser.newPage({viewport:{width:600,height:760}})
  await source.setContent('<body style="font:18px Arial;padding:35px;color:#172534"><h1>Greenfield Agri Supplies</h1><p>Supplier invoice GF-2959<br>25 November 2026</p><hr><p>Premium vegetable seed — 10 packets: LKR 1,000</p><p>Organic fertilizer — 1 × 20 kg bag: LKR 1,200</p><p>Freight: LKR 100</p><p>Tax: LKR 414</p><hr><h2>Total LKR 2,714</h2><small>Synthetic test invoice</small></body>')
  const image=await source.screenshot();await source.close()
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/ocr-check.html`, {waitUntil:'domcontentloaded',timeout:60000})
  await page.getByRole('button',{name:/Greenfield Agri Supplies/}).click()
  await page.getByText('Supplier account could not be loaded',{exact:true}).waitFor()
  await shot('account-retry-desktop.png')
  await page.getByRole('button',{name:'Retry supplier account',exact:true}).click()
  await page.getByText('No unpaid purchase invoices for this supplier.').waitFor()
  await page.getByRole('button',{name:'Scan supplier invoice',exact:true}).click()
  await page.getByRole('button',{name:'Set up invoice scanning',exact:true}).click()
  await page.getByLabel('Gemini API key',{exact:true}).fill('fixture-key-never-use-live')
  await page.getByLabel('Enable purchase invoice scanning',{exact:true}).check()
  await page.getByRole('button',{name:'Save invoice scanning settings',exact:true}).click()
  await page.getByLabel('Invoice photo or PDF',{exact:true}).waitFor()
  const upload=page.getByLabel('Invoice photo or PDF',{exact:true})
  await upload.setInputFiles({name:'bad.txt',mimeType:'text/plain',buffer:Buffer.from('not an invoice')})
  await page.getByRole('alert').filter({hasText:'Choose a JPG'}).waitFor()
  assert.equal(calls.filter(row=>row.method==='scan_invoice').length,0)
  await upload.setInputFiles({name:'supplier-invoice.png',mimeType:'image/png',buffer:image})
  failScan=true
  await page.getByRole('button',{name:'Read invoice',exact:true}).click()
  await page.getByRole('alert').filter({hasText:'quota'}).waitFor()
  await page.getByRole('button',{name:'Read invoice',exact:true}).click()
  await page.getByText('Review detected invoice',{exact:true}).waitFor()
  const fill=page.getByRole('button',{name:'Fill purchase draft',exact:true})
  assert.equal(await fill.isDisabled(),true)
  await page.getByLabel('Search product 2',{exact:true}).fill('fertilizer')
  await page.getByLabel(/^Match product 2/).selectOption('FERT-050')
  await page.getByLabel('Detected quantity 2',{exact:true}).fill('20')
  await page.getByLabel('Detected unit cost 2',{exact:true}).fill('60')
  await page.getByLabel(/I checked the quantity and cost are per Kg/).check()
  await page.getByLabel(/^Valuation expense account/).selectOption('Freight and handling - WA')
  await page.getByLabel(/^Tax account/).selectOption('Input tax - WA')
  await page.getByLabel('Detected quantity 1',{exact:true}).fill('9')
  await page.getByLabel('I checked the supplier, dates, products, units and totals against the original invoice.',{exact:true}).check()
  assert.equal(await fill.isDisabled(),true,'Total mismatch prevents importing')
  await page.getByLabel('Detected quantity 1',{exact:true}).fill('10')
  duplicate=true
  await page.getByLabel('Detected invoice number',{exact:true}).fill('GF-EXISTS')
  await page.getByRole('link',{name:'PINV-EXISTS',exact:true}).waitFor()
  assert.equal(await fill.isDisabled(),true,'Duplicate invoice prevents importing')
  duplicate=false
  await page.getByLabel('Detected invoice number',{exact:true}).fill('GF-2959')
  await page.getByRole('link',{name:'PINV-EXISTS',exact:true}).waitFor({state:'detached'})
  await page.getByLabel('I checked the supplier, dates, products, units and totals against the original invoice.',{exact:true}).check()
  await page.locator('.scan-heading').last().scrollIntoViewIfNeeded();await shot('review-desktop.png')
  await page.setViewportSize({width:390,height:844})
  await page.locator('.scan-item').last().scrollIntoViewIfNeeded();await shot('review-mobile.png')
  await fill.click()
  await page.getByRole('status').filter({hasText:'Invoice draft filled'}).waitFor()
  assert.equal(calls.filter(row=>row.method==='create_invoice').length,0,'Scanning does not post a purchase')
  assert.equal(await page.getByLabel('Quantity for Organic fertilizer',{exact:true}).inputValue(),'20')
  assert.match(await page.locator('.summary-total').innerText(),/2,714/)
  assert.match(await page.locator('.valuation-preview').innerText(),/104.55/)
  await page.locator('.purchase-summary').scrollIntoViewIfNeeded();await shot('draft-summary-mobile.png')
  const scanCall=calls.find(row=>row.method==='scan_invoice')
  assert.ok(scanCall.args.file_data.startsWith('iVBOR'))
  assert.equal(scanCall.args.mime_type,'image/png')
  assert.equal(scanCall.args.api_key,undefined)
  await page.setViewportSize({width:1440,height:1050})
  await page.getByRole('button',{name:'Scan supplier invoice',exact:true}).click()
  const pdf=Buffer.from('%PDF-1.7\nfixture')
  await page.getByLabel('Invoice photo or PDF',{exact:true}).setInputFiles({name:'foreign-invoice.pdf',mimeType:'application/pdf',buffer:pdf})
  foreign=true
  await page.getByRole('button',{name:'Read invoice',exact:true}).click()
  await page.getByText(/The detected invoice uses another currency/).waitFor()
  assert.equal(await page.getByRole('button',{name:'Fill purchase draft',exact:true}).isDisabled(),true)
  await page.getByRole('button',{name:'Close scanner',exact:true}).click()
  await page.evaluate(()=>{test.session.offline=true})
  assert.equal(await page.getByRole('button',{name:'Scan supplier invoice',exact:true}).isDisabled(),true)
  assert.deepEqual(errors,[])
  console.log('PASS flex-parent width, account error recovery, encrypted-key settings UI, file validation, Gemini failure/retry, supplier/product matching, pack-unit review, tax/valuation separation, total/duplicate/FX guards, draft-only import, PDF upload, offline controls and responsive screenshots')
}finally{await browser.close();await server.close()}
