// Actual vendored SDK + real Vue components. Native bridge/ERP responses are test doubles only.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright').catch(()=>import('./.label-test-tools/node_modules/playwright/index.mjs'))
const root=path.dirname(fileURLToPath(import.meta.url)),out=path.join(root,'../artifacts/esafe-printing')
await mkdir(out,{recursive:true})
const html=`<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body style="margin:0"><div id="app" style="height:100vh;display:flex"></div><script type="module">
import {createApp,h,ref,nextTick} from 'vue';import {createPinia} from 'pinia';import {createRouter,createMemoryHistory} from 'vue-router';import PrintingView from '/src/views/PrintingView.vue';import ReceiptModal from '/src/components/ReceiptModal.vue';import {useSessionStore} from '/src/stores/session.js';import {printManager,nativeDocument} from '/src/printing/index.js';import '/src/styles.css';
const pinia=createPinia(),session=useSessionStore(pinia),stage=ref('printing'),generation=ref(0);session.user='cashier';session.company='ESAFE Retail';session.posProfile='Till A';session.availableProfiles=['Till A','Till B'];session.permissions={settings:true,is_manager:true,print_labels:true,can_reprint:true};session.settings={enable_labels:true,esafe_printing:{silent:false,automatic_receipt:false,receipt_output:'html',copies:1,document_paper:'A4'}};session.notify=(text)=>{window.notices ||= [];window.notices.push(text)};
const receipt={name:'INV-ESAFE-1',doctype:'POS Invoice',pos_profile:'Till A',company:'ESAFE Retail',currency:'LKR',posting_date:'2026-11-22',posting_time:'12:00:00',customer_name:'Walk-in',grand_total:450,items:[{item_name:'සිංහල தமிழ் Rice',qty:1,rate:450,amount:450}],payments:[{mode_of_payment:'Cash',amount:450}],receipt_settings:{receipt_paper_width:'80mm'}};
const router=createRouter({history:createMemoryHistory(),routes:[{path:'/printing',component:PrintingView}]});await router.push('/printing?section=printers');await router.isReady();
createApp({render:()=>stage.value==='printing' ? h(PrintingView) : h(ReceiptModal,{key:generation.value,receipt,autoPrint:true})}).use(pinia).use(router).mount('#app');window.esafeTest={session,printManager,receipt,printDocument:nativeDocument,showReceipt:async()=>{stage.value='receipt';generation.value++;await nextTick()},showSetup:async()=>{stage.value='printing';await router.replace('/printing?section=printers');await nextTick()}};window.ready=true;
</script></body></html>`
const server=await createServer({root,base:'/',server:{port:0,host:'127.0.0.1',open:false},plugins:[{name:'esafe-browser-check',configureServer(s){s.middlewares.use('/esafe-check.html',async(req,res)=>{res.setHeader('Content-Type','text/html');res.end(await s.transformIndexHtml('/esafe-check.html',html))})}}]})
await server.listen()
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe'})
const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[],apiCalls=[]
page.on('pageerror',(error)=>errors.push(error.message))
await page.route('https://fonts.googleapis.com/**',(r)=>r.abort());await page.route('https://fonts.gstatic.com/**',(r)=>r.abort())
await page.addInitScript(()=>{
  const NativeSocket=window.WebSocket
  const bridge=window.testBridge={approved:false,revoked:false,down:false,scopes:[],pairings:[],prints:[],jobs:[],signed:0,connections:[],printers:[{id:'receipt-id',name:'Counter receipt',isDefault:true},{id:'label-id',name:'Label printer'},{id:'office-id',name:'Office A4'}]}
  const encode=(bytes)=>btoa(String.fromCharCode(...new Uint8Array(bytes))),decode=(text)=>Uint8Array.from(atob(text),(c)=>c.charCodeAt(0))
  const canonical=(v)=>v===null || typeof v!=='object' ? JSON.stringify(v) : Array.isArray(v) ? '['+v.map(canonical).join(',')+']' : '{'+Object.keys(v).sort().map((k)=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}'
  class Socket {
    constructor(url,...args){
      if(!String(url).startsWith('wss://localhost:'))return new NativeSocket(url,...args)
      bridge.connections.push(String(url));this.url=String(url);this.readyState=0;this.seq=0;this.session=crypto.randomUUID();this.challenge='test-native-challenge';this.incoming=Promise.resolve()
      setTimeout(()=>{if(bridge.down || new URL(url).port!=='17651'){this.onerror?.({});this.close();return}this.readyState=1;this.message({event:'hello',sessionId:this.session,challenge:this.challenge,protocol:1,version:'0.1.0'})},0)
    }
    message(value){this.onmessage?.({data:JSON.stringify(value)})}
    send(value){this.incoming=this.incoming.then(()=>this.handle(JSON.parse(value))).catch((e)=>{window.nativeMockError=e.message;this.close()})}
    async handle(req){
      const respond=(result)=>this.message({jsonrpc:'2.0',id:req.id,result}),deny=()=>this.message({id:req.id,error:{code:'PERMISSION_DENIED',message:'Approve printer access in Esafe'}})
      if(req.method==='session.authenticate'){
        this.key=await crypto.subtle.importKey('raw',decode(req.params.publicKey),{name:'ECDSA',namedCurve:'P-256'},false,['verify'])
        if(!await crypto.subtle.verify({name:'ECDSA',hash:'SHA-256'},this.key,decode(req.params.signature),new TextEncoder().encode('esafe-v1\n'+this.session+'\n'+this.challenge+'\n'+location.origin)))throw new Error('Invalid SDK authentication signature')
        respond({authenticated:bridge.approved&&!bridge.revoked});return
      }
      const {signature,...envelope}=req
      if(req.seq!==++this.seq || !await crypto.subtle.verify({name:'ECDSA',hash:'SHA-256'},this.key,decode(signature),new TextEncoder().encode(canonical(envelope))))throw new Error('Invalid signed SDK request or sequence')
      bridge.signed++
      if(req.method==='pair.request'){bridge.scopes=req.params.permissions;bridge.pairings.push(req.params.permissions);respond({pairingId:'pair'});return}
      if(req.method==='pair.status'){bridge.approved=true;bridge.revoked=false;respond({state:'approved'});return}
      if(bridge.revoked){deny();return}
      if(req.method==='events.subscribe'){respond({subscribed:true});return}
      if(req.method==='printers.list'){respond(bridge.printers);return}
      if(req.method==='printers.capabilities'){respond({printerId:req.params.printerId,driver:'Test Windows driver',port:'USB001',maxCopies:99,color:false,duplex:false,physicalCompletionAvailable:false});return}
      if(req.method==='jobs.list'){respond(bridge.jobs);return}
      if(req.method==='jobs.get'){respond(bridge.jobs.find((j)=>j.id===req.params.jobId));return}
      if(req.method==='print'){
        if(!bridge.scopes.some((s)=>s.action==='print'&&s.resources.includes(req.params.printerId))){deny();return}
        bridge.prints.push(req.params)
        const job={id:crypto.randomUUID(),printerId:req.params.printerId,format:req.params.format,title:req.params.title,state:'queued',certainty:'durable acceptance',error:null,spoolId:null,createdAt:new Date().toISOString(),updatedAt:new Date().toISOString()}
        bridge.jobs.push(job);respond(job);setTimeout(()=>this.message({event:'job.changed',data:job}),0);return
      }
      if(req.method==='print.preview'){respond({format:'png',dataBase64:'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZ1cAAAAASUVORK5CYII=',pageCount:1});return}
      respond({})
    }
    close(){this.readyState=3;setTimeout(()=>this.onclose?.({}),0)}
  }
  window.WebSocket=Socket
})
let failDocument=false
let config={silent:false,automatic_receipt:false,receipt_output:'html',copies:1,document_paper:'A4'}
await page.route('**/api/method/**',async(route)=>{
  const method=route.request().url().split('/').pop(),args=route.request().postDataJSON() || {};apiCalls.push({method,args})
  let message={}
  if(method.endsWith('.receipt_workspace'))message={config:{receipt_template:'Retail'},profiles:['Till A','Till B'],print_formats:{},overrides:[],custom_fields:[]}
  else if(method.endsWith('.get_printer_settings'))message={host:'',port:9100,print_format:'',formats:[],invoice_doctype:'POS Invoice',can_write:true,needs_migration:false,esafe:config,esafe_needs_migration:false}
  else if(method.endsWith('.save_esafe_defaults')){config=args.values;message=config}
  else if(method.endsWith('.authorize_workstation_setup'))message={allowed:true}
  else if(method.endsWith('.register_intent'))message={name:args.request_id}
  else if(method.endsWith('.record_event'))message={ok:true}
  else if(method.endsWith('.document_pdf')){
    if(failDocument)return route.fulfill({status:417,json:{exception:'PDF renderer unavailable'}})
    message={format:'pdf',data:Buffer.from('%PDF-1.4\nSDK transport fixture only').toString('base64')}
  }
  await route.fulfill({json:{message}})
})
try{
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/esafe-check.html`)
  await page.getByRole('heading',{name:'Esafe Print Manager',exact:true}).waitFor()
  assert.equal(await page.evaluate(()=>testBridge.connections.length),0,'First setup must not attempt a WebSocket without Connect')
  await page.getByRole('button',{name:'Connect / reconnect',exact:true}).click()
  await page.getByLabel('Default receipt printer',{exact:true}).waitFor({state:'visible'})
  await page.waitForFunction(()=>esafeTest.printManager.state.connection==='connected')
  assert.deepEqual(await page.evaluate(()=>testBridge.pairings[0]),[{action:'printers.list',resources:['printers']}])
  await page.getByLabel('Default receipt printer',{exact:true}).selectOption('receipt-id')
  await page.getByLabel('Label printer',{exact:true}).selectOption('label-id')
  await page.getByLabel('Invoice / A4 printer',{exact:true}).selectOption('office-id')
  await page.getByLabel('Reports and payment receipts printer',{exact:true}).selectOption('receipt-id')
  await page.getByRole('button',{name:'Approve and save workstation printers',exact:true}).click()
  await page.getByRole('status').filter({hasText:'Workstation printer assignments saved.'}).waitFor()
  assert.deepEqual(await page.evaluate(()=>testBridge.scopes),[{action:'printers.list',resources:['printers']},{action:'print',resources:['label-id','office-id','receipt-id']}])
  assert.equal(await page.evaluate(()=>testBridge.prints.length),0,'Setup and pairing must not print or pulse a drawer')
  await page.getByLabel('Use Esafe silent printing for this outlet',{exact:true}).check()
  await page.getByLabel('Automatically print the receipt after a successful sale',{exact:true}).check()
  await page.getByRole('button',{name:'Save silent-printing defaults',exact:true}).click()
  await page.getByRole('status').filter({hasText:'Silent-printing defaults saved.'}).waitFor()
  await page.getByRole('button',{name:'Silent test receipt',exact:true}).click()
  await page.waitForFunction(()=>testBridge.prints.length===1)
  await page.getByRole('status').filter({hasText:'Print job accepted by Esafe.'}).waitFor()
  await page.locator('.printing-panel').evaluate((el)=>el.scrollTop=0)
  await page.screenshot({path:path.join(out,'setup-desktop.png')})
  await page.locator('.esafe-setup fieldset').nth(1).screenshot({path:path.join(out,'assignments-desktop.png')})
  await page.getByLabel('Outlet',{exact:true}).selectOption('Till B')
  assert.equal(await page.getByLabel('Default receipt printer',{exact:true}).inputValue(),'')
  await page.getByLabel('Outlet',{exact:true}).selectOption('Till A')
  await page.waitForFunction(()=>document.querySelector('select[aria-label="Default receipt printer"]')?.value==='receipt-id')
  assert.equal(await page.getByLabel('Default receipt printer',{exact:true}).inputValue(),'receipt-id')
  await page.setViewportSize({width:390,height:900});await page.locator('.printing-panel').evaluate((el)=>el.scrollTop=0)
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true)
  await page.screenshot({path:path.join(out,'setup-mobile.png')})
  await page.setViewportSize({width:1440,height:1100})
  await page.evaluate(()=>esafeTest.showReceipt())
  await page.waitForFunction(()=>testBridge.prints.length===2)
  await page.waitForFunction(()=>esafeTest.printManager.state.jobs.some((j)=>j.reference?.name==='INV-ESAFE-1'&&j.agentJobId))
  const receiptPrint=await page.evaluate(()=>testBridge.prints.at(-1))
  const decoded=Buffer.from(receiptPrint.dataBase64,'base64').toString('utf8')
  assert.ok(decoded.includes('සිංහල தமிழ் Rice'));assert.ok(decoded.includes('INV-ESAFE-1'))
  assert.ok(!/<img[^>]+src=["']https?:/i.test(decoded));assert.equal(receiptPrint.format,'html')
  await page.evaluate(()=>esafeTest.showReceipt());await page.waitForTimeout(400)
  assert.equal(await page.evaluate(()=>testBridge.prints.length),2,'Repeated completed-sale callback must reuse the original intent')
  await page.getByRole('button',{name:'Print receipt',exact:true}).click()
  await page.waitForFunction(()=>testBridge.prints.length===3)
  assert.ok(apiCalls.some((c)=>c.method.endsWith('.register_intent')&&c.args.reference.reprint===1))
  assert.equal(new Set(await page.evaluate(()=>testBridge.prints.map((p)=>p.idempotencyKey))).size,3)
  await page.evaluate(()=>{esafeTest.receipt.name='INV-ESAFE-58';esafeTest.receipt.receipt_settings.receipt_paper_width='58mm';return esafeTest.showReceipt()})
  await page.waitForFunction(()=>testBridge.prints.length===4)
  assert.equal(await page.evaluate(()=>testBridge.prints.at(-1).options.size.width),58)
  await page.evaluate(()=>esafeTest.showSetup())
  await page.getByRole('heading',{name:'Esafe Print Manager',exact:true}).waitFor()
  await page.evaluate(async()=>{testBridge.revoked=true;await esafeTest.printManager.refreshPrinters().catch(()=>{})})
  assert.equal(await page.evaluate(()=>esafeTest.printManager.state.connection),'approval-required')
  await page.getByRole('button',{name:'Connect / reconnect',exact:true}).click()
  await page.waitForFunction(()=>esafeTest.printManager.state.connection==='connected')
  assert.equal(await page.evaluate(()=>testBridge.prints.length),4,'Approval repair must never print')
  const documentJob=await page.evaluate(()=>esafeTest.printDocument('Sales Invoice','INV-OFFICE-1'))
  assert.ok(documentJob.agentJobId)
  assert.equal(await page.evaluate(()=>testBridge.prints.at(-1).format),'pdf')
  assert.equal(await page.evaluate(()=>testBridge.prints.at(-1).printerId),'office-id')
  assert.deepEqual(await page.evaluate(()=>testBridge.prints.at(-1).options.size),{width:210,height:297})
  await page.evaluate(()=>esafeTest.printDocument('Sales Invoice','INV-OFFICE-1'))
  assert.equal(await page.evaluate(()=>testBridge.prints.length),5,'Repeated document callbacks must not send another PDF')
  failDocument=true
  await page.evaluate(()=>esafeTest.printDocument('Quotation','Q-PDF-FAILED').catch(()=>{}))
  assert.equal(await page.evaluate(()=>testBridge.prints.length),5)
  await page.getByRole('tab',{name:'Print jobs',exact:true}).click()
  await page.getByRole('heading',{name:'Print jobs',exact:true}).waitFor()
  await page.getByText('Invoice and quotation browser fallback',{exact:true}).click()
  await page.getByRole('button',{name:'Open browser print view · Q-PDF-FAILED',exact:true}).waitFor()
  await page.screenshot({path:path.join(out,'jobs-desktop.png')})
  const isolated=await browser.newPage()
  await isolated.route('**/api/method/**',(r)=>r.fulfill({json:{message:{}}}))
  await isolated.route('https://fonts.googleapis.com/**',(r)=>r.abort())
  await isolated.goto(`http://127.0.0.1:${server.httpServer.address().port}/esafe-check.html`)
  await isolated.waitForFunction(()=>window.ready)
  assert.equal(await isolated.evaluate(async()=>(await esafeTest.printManager.binding('Till A')).receipt),'','A second workstation/browser must not inherit assignments')
  await isolated.close()
  assert.ok(!apiCalls.some((c)=>/submit_sale|take_payment|qz_printing|sign_request/.test(c.method)))
  assert.ok(await page.evaluate(()=>testBridge.signed>10))
  assert.ok(await page.evaluate(()=>!window.nativeMockError),await page.evaluate(()=>window.nativeMockError))
  assert.ok((await page.evaluate(()=>testBridge.connections)).every((url)=>/^wss:\/\/localhost:1765[1-9]|^wss:\/\/localhost:17660/.test(url)))
  assert.deepEqual(errors,[])
  console.log('PASS actual Esafe 0.1.0 SDK authentication/signatures, discovery-before-print pairing, exact scopes, workstation/outlet isolation, silent setup/test, Unicode 58/80mm HTML, automatic-original dedupe, deliberate reprint, PDF document dispatch/failure fallback, revocation repair and responsive UI')
}catch(error){console.error(error);await page.screenshot({path:path.join(out,'failure.png')});console.error(errors);process.exitCode=1}finally{await browser.close();server.httpServer?.closeAllConnections();await server.close()}
