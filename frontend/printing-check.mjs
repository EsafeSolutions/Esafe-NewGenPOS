// Printing consolidation: permissions, receipt scopes, printer setup and responsive UI.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright').catch(()=>import('./.label-test-tools/node_modules/playwright/index.mjs'))
const root=path.dirname(fileURLToPath(import.meta.url)),out=path.join(root,'../artifacts/printing-workspace')
await mkdir(out,{recursive:true})
const html=`<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body style="margin:0"><div id="app" style="height:100vh;display:flex;min-width:0"></div><script type="module">
import {createApp,h} from 'vue';import {createPinia} from 'pinia';import {createRouter,createMemoryHistory,RouterView} from 'vue-router';import PrintingView from '/src/views/PrintingView.vue';import SettingsView from '/src/views/SettingsView.vue';import NavRail from '/src/components/NavRail.vue';import {useSessionStore} from '/src/stores/session.js';import '/src/styles.css';
const pinia=createPinia(),session=useSessionStore(pinia),mode=new URLSearchParams(location.search).get('role') || 'manager';session.user='printer@example.com';session.company='Esafe Retail';session.posProfile='Till A';session.availableProfiles=['Till A','Till B'];session.settings={enable_labels:mode!=='no-labels',receipt_logo:''};session.permissions={settings:mode!=='cashier'&&mode!=='blocked',print_labels:mode!=='blocked',is_manager:mode!=='cashier'&&mode!=='blocked'};
const router=createRouter({history:createMemoryHistory(),routes:[{path:'/printing',component:PrintingView},{path:'/labels',redirect:{path:'/printing',query:{section:'labels'}}},{path:'/settings',component:SettingsView}]});await router.push('/labels');await router.isReady();
createApp({render:()=>h('div',{style:'height:100vh;width:100%;display:flex;min-width:0'},[h(NavRail),h('div',{style:'display:flex;flex:1;min-width:0;min-height:0'},h(RouterView))])}).use(pinia).use(router).mount('#app');window.test={session,router};window.ready=true;
</script></body></html>`
const server=await createServer({root,base:'/',server:{port:0,host:'127.0.0.1',open:false},plugins:[{name:'printing-test',configureServer(s){s.middlewares.use('/printing-check.html',async(req,res)=>{res.setHeader('Content-Type','text/html');res.end(await s.transformIndexHtml('/printing-check.html',html))})}}]})
await server.listen()
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe'})
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],calls=[]
await page.route('https://fonts.googleapis.com/**',(r)=>r.abort());await page.route('https://fonts.gstatic.com/**',(r)=>r.abort())
await page.addInitScript(()=>{window.print=()=>{window.printCalled=true}})
page.on('pageerror',(e)=>errors.push(e.message))
const defaults={receipt_template:'Retail',receipt_paper_width:'80mm',receipt_footer:'Original footer',receipt_show_cashier:1,receipt_show_terminal:1,receipt_show_invoice_barcode:1,receipt_show_payments:1,receipt_show_unit_price:1,receipt_show_serial:1}
const overrides={},printers={'Till A':{host:'',port:9100,print_format:''},'Till B':{host:'192.168.1.22',port:9100,print_format:''}}
let canWrite=true
await page.route('**/api/method/**',async(route)=>{
  const method=route.request().url().split('/').pop(),args=route.request().postDataJSON() || {};calls.push({method,args})
  let message=[]
  if(method.endsWith('.receipt_workspace'))message={config:defaults,custom_fields:[],profiles:['Till A','Till B'],overrides:Object.keys(overrides),print_formats:Object.fromEntries(Object.entries(printers).map(([k,v])=>[k,v.print_format]))}
  else if(method.endsWith('.get_profile_receipt'))message={config:overrides[args.pos_profile] || defaults,custom_fields:[],has_override:!!overrides[args.pos_profile]}
  else if(method.endsWith('.save_receipt_defaults')){Object.assign(defaults,args.config);message={ok:true}}
  else if(method.endsWith('.save_profile_receipt')){overrides[args.pos_profile]=args.config;message={ok:true}}
  else if(method.endsWith('.clear_profile_receipt')){delete overrides[args.pos_profile];message={ok:true}}
  else if(method.endsWith('.receipt_field_options'))message=[{fieldname:'remarks',label:'Remarks'}]
  else if(method.endsWith('.get_printer_settings') || method.endsWith('.save_printer_settings')){
    if(method.endsWith('.save_printer_settings'))printers[args.pos_profile]={host:args.host,port:+args.port,print_format:args.print_format}
    message={...printers[args.pos_profile],formats:['Retail document'],invoice_doctype:'POS Invoice',can_write:canWrite,needs_migration:false}
  }else if(method.endsWith('.test_printer'))message={submitted:true}
  else if(method.endsWith('.workspace'))message={presets:[],can_manage:true,needs_migration:false}
  await route.fulfill({json:{message}})
})
async function open(role='manager'){
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/printing-check.html?role=${role}`)
  await page.waitForFunction(()=>window.ready)
}
async function screenshot(name){assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(out,name+'.png'),fullPage:true})}
try{
  await open()
  assert.equal(await page.evaluate(()=>test.router.currentRoute.value.path),'/printing')
  assert.equal(await page.getByRole('link',{name:'Printing',exact:true}).count(),1)
  assert.equal(await page.getByRole('tab',{name:'Printers',exact:true}).count(),1)
  await screenshot('labels-desktop')
  await page.getByPlaceholder('Scan or search items…').fill('draft label search')
  await page.getByRole('tab',{name:'Receipt',exact:true}).click()
  await page.getByRole('button',{name:'Save default receipt',exact:true}).waitFor()
  await page.locator('.rc-preview .retail-loyalty').waitFor()
  await page.getByRole('button',{name:'Hide loyalty points section',exact:true}).click()
  assert.equal(await page.locator('.rc-preview .retail-loyalty').count(),0)
  await page.getByRole('button',{name:'Hide optional sections',exact:true}).click()
  assert.equal(await page.locator('.rc-preview .retail-counts').count(),0)
  assert.equal(await page.locator('.rc-preview .retail-items th').count(),3)
  assert.ok(await page.locator('.rc-preview').getByText('Net total',{exact:true}).count())
  await page.getByRole('button',{name:'Show all optional sections',exact:true}).click()
  await page.getByRole('button',{name:'Hide loyalty points section',exact:true}).click()
  await page.getByText('Advanced custom receipt editor',{exact:true}).click()
  await page.getByLabel('Header alignment',{exact:true}).selectOption('left')
  await page.getByLabel('Footer alignment',{exact:true}).selectOption('right')
  await page.getByLabel('Design right padding (mm)',{exact:true}).fill('1')
  await page.getByLabel('Item row padding (mm)',{exact:true}).fill('0.4')
  await page.getByLabel('Invoice barcode height (px)',{exact:true}).fill('32')
  assert.equal(await page.locator('.rc-preview .receipt-barcode svg').evaluate(el=>getComputedStyle(el).height),'32px')
  await page.getByLabel('Body font size (px)',{exact:true}).fill('99')
  const saves=calls.filter(c=>c.method.endsWith('.save_receipt_defaults')).length
  await page.getByRole('button',{name:'Save default receipt',exact:true}).click()
  await page.getByRole('alert').first().waitFor()
  assert.equal(calls.filter(c=>c.method.endsWith('.save_receipt_defaults')).length,saves)
  await page.getByLabel('Body font size (px)',{exact:true}).fill('11')
  await page.getByLabel('Custom footer line',{exact:true}).fill('New default footer')
  await page.getByLabel('Cashier name',{exact:true}).uncheck()
  await page.getByRole('button',{name:'Save default receipt',exact:true}).click()
  await page.waitForFunction(()=>test.session.settings.receipt_footer==='New default footer')
  assert.equal(defaults.receipt_show_cashier,0)
  assert.equal(defaults.receipt_show_loyalty,0)
  assert.equal(defaults.receipt_design.headerAlign,'left')
  assert.equal(defaults.receipt_design.paddingRight,1)
  assert.equal(await page.locator('.rc-preview .receipt-company').evaluate(el=>getComputedStyle(el).textAlign),'left')
  await page.locator('.design-editor').screenshot({path:path.join(out,'advanced-editor-desktop.png')})
  await page.getByRole('button',{name:'Print preview',exact:true}).click()
  await page.locator('#receipt-print-frame').waitFor({state:'attached'})
  const previewFrame=page.frames().find((frame)=>frame!==page.mainFrame())
  await previewFrame.evaluate(()=>window.dispatchEvent(new Event('afterprint')))
  await page.getByLabel('Receipt outlet',{exact:true}).selectOption('Till B')
  await page.getByRole('button',{name:'Save for this outlet',exact:true}).waitFor()
  await page.getByLabel('Custom footer line',{exact:true}).fill('Till B footer')
  await page.getByLabel('Terminal or user',{exact:true}).uncheck()
  await page.getByLabel('Invoice barcode',{exact:true}).uncheck()
  await page.getByRole('button',{name:'Save for this outlet',exact:true}).click()
  await page.getByRole('button',{name:'Reset to default',exact:true}).waitFor()
  assert.equal(overrides['Till B'].receipt_show_terminal,0);assert.equal(overrides['Till B'].receipt_show_invoice_barcode,0)
  assert.equal(defaults.receipt_footer,'New default footer')
  await screenshot('receipt-desktop')
  await page.setViewportSize({width:390,height:900});await screenshot('receipt-mobile');await page.setViewportSize({width:390,height:1700});await page.locator('.design-editor').screenshot({path:path.join(out,'advanced-editor-mobile.png')})
  await page.setViewportSize({width:1440,height:1000})
  await page.getByRole('button',{name:'Reset to default',exact:true}).click()
  await page.getByRole('button',{name:'Reset to default',exact:true}).waitFor({state:'detached'})
  assert.equal(overrides['Till B'],undefined)
  await page.getByRole('tab',{name:'Labels',exact:true}).click()
  assert.equal(await page.getByPlaceholder('Scan or search items…').inputValue(),'draft label search')
  await page.getByRole('tab',{name:'Printers',exact:true}).click()
  await page.getByLabel('Printer IP address or hostname',{exact:true}).waitFor()
  await page.getByLabel('Printer IP address or hostname',{exact:true}).fill('192.168.1.50')
  await page.getByLabel('Receipt and document format',{exact:true}).selectOption('Retail document')
  assert.equal(await page.getByRole('button',{name:'Print test receipt',exact:true}).isDisabled(),true)
  await page.getByRole('button',{name:'Save printer settings',exact:true}).click()
  await page.getByRole('status').filter({hasText:'Printer settings saved.'}).waitFor()
  assert.equal(await page.evaluate(()=>test.session.printerConfigured),true)
  assert.equal(await page.evaluate(()=>test.session.printFormat),'Retail document')
  await page.getByRole('button',{name:'Print test receipt',exact:true}).click()
  await page.getByRole('status').filter({hasText:'Test receipt sent.'}).waitFor()
  assert.ok(calls.some((c)=>c.method.endsWith('.test_printer')&&c.args.pos_profile==='Till A'))
  await screenshot('printers-desktop')
  await page.setViewportSize({width:390,height:900});await screenshot('printers-mobile')
  await page.getByRole('button',{name:'Save printer settings',exact:true}).scrollIntoViewIfNeeded()
  await screenshot('printers-mobile-actions')
  await page.setViewportSize({width:1024,height:900});await screenshot('printers-tablet')
  await page.setViewportSize({width:1440,height:1000})
  await page.evaluate(async()=>{test.session.offline=true;await test.router.push('/settings')})
  await page.locator('.workspace-nav').waitFor()
  assert.equal(await page.locator('.workspace-nav').getByRole('button',{name:'Receipt',exact:true}).count(),0)
  assert.equal(await page.getByLabel('Custom footer line',{exact:true}).count(),0)
  const before=calls.length
  await open('cashier')
  assert.equal(await page.getByRole('tab',{name:'Receipt',exact:true}).count(),0)
  assert.equal(await page.getByRole('tab',{name:'Printers',exact:true}).count(),0)
  await page.evaluate(()=>test.router.replace('/printing?section=receipt'))
  assert.equal(await page.getByRole('tab',{name:'Labels',exact:true}).getAttribute('aria-selected'),'true')
  assert.ok(!calls.slice(before).some((c)=>c.method.includes('printing_settings')))
  await open('no-labels')
  assert.equal(await page.getByRole('tab',{name:'Labels',exact:true}).count(),0)
  await page.getByRole('button',{name:'Save default receipt',exact:true}).waitFor()
  canWrite=false
  await page.getByRole('tab',{name:'Printers',exact:true}).click()
  await page.getByText('You need permission to edit this POS Profile to change its printer setup.').waitFor()
  assert.equal(await page.getByRole('button',{name:'Save printer settings',exact:true}).isDisabled(),true)
  await open('blocked')
  await page.getByText('You do not have access to printing settings or labels.').waitFor()
  assert.deepEqual(errors,[])
  console.log('PASS Printing navigation/legacy route, receipt defaults and overrides/reset, new visibility toggles, scoped printer save/test, mobile/tablet layouts and permission isolation')
}catch(error){console.error(error);await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});console.error(await page.locator('label').allTextContents());process.exitCode=1}finally{await browser.close();server.httpServer?.closeAllConnections();await server.close()}
