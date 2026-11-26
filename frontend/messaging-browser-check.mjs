// Customer/receipt/settings flows against local provider fixtures. No real sends.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
import vue from '@vitejs/plugin-vue'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
const root = path.dirname(fileURLToPath(import.meta.url)), output = path.join(root, '../docs/screenshots/messaging')
await mkdir(output, {recursive:true})
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><div id="app"></div><script type="module">
import {createApp,h,reactive} from 'vue'; import {createPinia} from 'pinia'; import {createRouter,createMemoryHistory,RouterView,RouterLink} from 'vue-router';
import NavRail from '/src/components/NavRail.vue'; import MessagesView from '/src/views/MessagesView.vue'; import CustomersView from '/src/views/CustomersView.vue'; import CustomerMessagingSettings from '/src/components/CustomerMessagingSettings.vue'; import ReceiptModal from '/src/components/ReceiptModal.vue'; import {useSessionStore} from '/src/stores/session.js'; import '/src/styles.css';
const pinia=createPinia(),session=useSessionStore(pinia); session.company='Weerakoon Agro'; session.currency='LKR'; session.posProfile='Till'; session.priceList='Retail'; session.permissions={customers:true,settings:true,is_manager:true}; session.settings={receipt_template:'Retail',receipt_show_payments:1,receipt_show_unit_price:1}; session.notify=message=>window.notices.push(message); window.notices=[];
const receipt={name:'ACC-PSINV-2026-00303',doctype:'POS Invoice',pos_profile:'Till',company:'Weerakoon Agro',currency:'LKR',customer:'CUST',customer_name:'A Rahman',customer_phone:'0771234567',posting_date:'2026-11-26',posting_time:'14:32:45',grand_total:1985,net_total:1985,items:[{item_name:'Cat litter',qty:1,rate:345,price_list_rate:345,amount:345},{item_name:'Grow More Nitro Plus 1kg',qty:1,rate:1490,price_list_rate:1490,amount:1490},{item_name:'Cattle feed',qty:1,rate:150,price_list_rate:150,amount:150}],payments:[{mode_of_payment:'Cash',amount:1985}],receipt_settings:{receipt_template:'Retail',receipt_paper_width:'80mm'}};
const state=reactive({receiptOpen:false}); const router=createRouter({history:createMemoryHistory(),routes:[{path:'/messages',component:MessagesView},{path:'/customers',component:CustomersView},{path:'/settings',component:CustomerMessagingSettings},{path:'/history',component:{template:'<p>Invoice history</p>'}}]}); await router.push('/messages');await router.isReady();
createApp({render:()=>h('div',{style:'display:flex;flex-direction:column;height:100dvh'},[h('header',{style:'background:var(--pos-blue);color:white;padding:12px 18px;display:flex;justify-content:space-between;gap:10px'},[h('b','ESAFE ERP POS / Customer messaging'),h('button',{class:'btn btn-outline',onClick:()=>state.receiptOpen=true},'Open sample receipt')]),h('main',{style:'display:flex;flex:1;min-height:0'},[h(NavRail),h('div',{style:'display:flex;flex:1;min-width:0;overflow:auto;padding:12px'},[h(RouterView)])]),state.receiptOpen?h(ReceiptModal,{receipt,onClose:()=>state.receiptOpen=false}):null])}).use(pinia).use(router).mount('#app');window.test={session,router,state,receipt};
</script></body></html>`
const server=await createServer({root,configFile:false,cacheDir:'node_modules/.vite-messaging-check',define:{__ESAFEPOS_VERSION__:JSON.stringify('test')},base:'/',server:{port:0,host:'127.0.0.1',open:false},plugins:[vue(),{name:'messaging-browser-check',configureServer(s){s.middlewares.use('/messaging-check.html',async(req,res)=>{res.setHeader('Content-Type','text/html');res.end(await s.transformIndexHtml('/messaging-check.html',html))})}}]})
await server.listen()
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe'})
const page=await browser.newPage({viewport:{width:1440,height:1060}})
page.setDefaultTimeout(15000)
const errors=[],calls=[],history=[],requests=new Map()
page.on('pageerror',e=>errors.push(e.message))
await page.addInitScript(()=>{
  window.popups=[];window.open=(url,target,features)=>{const popup={url,features,opener:null,location:{replace(value){popup.url=value}},close(){popup.closed=true}};window.popups.push(popup);return popup}
  Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.copiedText=text},write:async items=>{window.copiedImage=items.length}}})
  Object.defineProperty(navigator,'canShare',{value:()=>true});Object.defineProperty(navigator,'share',{value:async data=>{window.sharedFiles=data.files.map(file=>file.name)}})
})
await page.route('https://fonts.googleapis.com/**',route=>route.abort())
await page.route('https://fonts.gstatic.com/**',route=>route.abort())
let nextStatus=null
const config={enabled:1,sms_enabled:1,whatsapp_enabled:1,image_enabled:1,country_code:'94',sms_number_format:'As entered',whatsapp_target:'Popup',invoice_template:'Hello {customer},\nYour invoice {invoice}: {link}',customer_template:'Hello {customer},',whatsapp_template_name:'pos_receipt',whatsapp_template_language:'en',whatsapp_template_parameters:'customer,invoice,total,link',whatsapp_api_roles:['EsafePOS Cashier','EsafePOS Manager','System Manager']}
config.whatsapp_template_image=1
const options={config,ready:true,can_sms:true,sms_configured:true,can_manage:true,whatsapp_configured:true,can_whatsapp_api:true}
const settings=()=>({config,ready:true,can_configure_sms:true,roles:['EsafePOS Cashier','EsafePOS Manager','System Manager'],whatsapp:{phone_number_id:'123456789',api_version:'v27.0',token_configured:true},gateway:{sms_gateway_url:'https://sms.example.test/send',message_parameter:'message',receiver_parameter:'to',use_post:1,parameters:[{name:'PARAM',parameter:'token',value:'',has_value:true,header:1}],allowed_roles:['EsafePOS Cashier']}})
await page.route('**/api/method/**',async route=>{
  const method=route.request().url().split('/').pop(),args=route.request().postDataJSON();calls.push({method,args});let message={}
  if(method.endsWith('customers.search_customers')) message={items:[{name:'CUST',customer_name:'A Rahman',mobile_no:'0771234567',customer_group:'Individual'}],has_more:false}
  else if(method.endsWith('customer_groups'))message=['Individual']
  else if(method.endsWith('customer_detail'))message={name:'CUST',customer_name:'A Rahman',mobile_no:'0771234567',customer_group:'Individual',currency:'LKR',stats:{sales_count:12,net_spent:24500,returns_count:0},wallet:{loyalty_points:20,store_credit:0},can_edit_price_list:false}
  else if(method.endsWith('search_sales'))message=[]
  else if(method.endsWith('messaging.compose'))message={customer:'CUST',mobile:'0771234567',url:args.invoice?'https://shop.example.test/einvoice?t=P&i=ACC-PSINV-2026-00303&s=SIGNED':'',message:args.invoice?'Hello A Rahman,\nYour invoice ACC-PSINV-2026-00303: https://shop.example.test/einvoice?t=P&i=ACC-PSINV-2026-00303&s=SIGNED':'Hello A Rahman,',template_values:{customer:'A Rahman',invoice:args.invoice||'',total:'1985.00',link:'https://shop.example.test/einvoice?SIGNED'},options}
  else if(method.endsWith('send_message')){
    if(requests.has(args.request_key))message={...requests.get(args.request_key),duplicate:true}
    else{message={name:'MSG-'+(history.length+1),status:nextStatus||(args.channel==='SMS'?'Submitted to gateway':args.channel==='WhatsApp API'?'Submitted to WhatsApp':'Opened in WhatsApp'),mobile:'+94771234567',channel:args.channel,error:nextStatus==='Outcome unknown'?'Check the provider before sending again.':''};nextStatus=null;requests.set(args.request_key,message);history.unshift({...message,creation:'2026-11-26 15:00:00',customer:'CUST',invoice:args.invoice,message:args.message})}
  }
  else if(method.endsWith('recent_messages'))message=history
  else if(method.endsWith('get_messaging_settings')||method.endsWith('save_sms_gateway'))message=settings()
  else if(method.endsWith('save_messaging_settings'))message={config:{...config,...args.payload}}
  else if(method.endsWith('save_whatsapp_connection'))message={saved:true}
  else if(method.endsWith('check_whatsapp_connection'))message={connected:true,name:'Weerakoon Agro',phone:'+94770000000'}
  await route.fulfill({json:{message}})
})
const sends=()=>calls.filter(call=>call.method.endsWith('send_message'))
try{
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/messaging-check.html`)
  await page.getByRole('button',{name:'A Rahman 0771234567'}).click()
  const composer=page.locator('.message-composer')
  await composer.getByLabel('Message',{exact:true}).fill('Hello Rahman,\nYour order is ready. Thank you!')
  const apiButton=composer.getByRole('button',{name:'Send via WhatsApp API',exact:true})
  assert.equal(await apiButton.isDisabled(),true)
  await composer.getByLabel('This customer messaged our WhatsApp business within the last 24 hours.').check()
  await apiButton.click()
  await composer.getByText('Submitted to WhatsApp',{exact:true}).waitFor()
  assert.equal(sends().at(-1).args.message,'Hello Rahman,\nYour order is ready. Thank you!')
  assert.equal(sends().at(-1).args.channel,'WhatsApp API')
  assert.equal(await apiButton.isDisabled(),true)
  await composer.getByRole('button',{name:'Send SMS',exact:true}).click()
  await composer.getByText('Submitted to gateway',{exact:true}).waitFor()
  assert.equal(sends().at(-1).args.channel,'SMS')
  await composer.getByLabel('Message',{exact:true}).fill('Please call us about your order.')
  nextStatus='Outcome unknown'
  await apiButton.click()
  await composer.getByText('Outcome unknown',{exact:true}).waitFor()
  assert.equal(await apiButton.isDisabled(),true)
  const count=sends().length
  await page.getByRole('button',{name:'Refresh',exact:true}).click()
  assert.equal(sends().length,count)
  await composer.getByRole('button',{name:'WhatsApp popup',exact:true}).click()
  await page.waitForFunction(()=>window.popups[0]?.url.startsWith('https://wa.me/'))
  const popup=await page.evaluate(()=>window.popups[0])
  assert.match(popup.features,/popup/)
  assert.match(popup.url,/94771234567/)
  await composer.getByRole('button',{name:'Copy message',exact:true}).click()
  assert.equal(await page.evaluate(()=>window.copiedText),'Please call us about your order.')
  await page.screenshot({path:path.join(output,'messages-desktop.png'),fullPage:true})

  // Receipt composer renders the actual receipt to PNG and sends the media payload.
  await page.getByRole('button',{name:'Open sample receipt',exact:true}).click()
  await page.getByRole('button',{name:'Send e-invoice',exact:true}).click()
  const receiptComposer=page.locator('.receipt-message-panel .message-composer')
  await receiptComposer.getByLabel('Message',{exact:true}).waitFor()
  await receiptComposer.getByLabel('Message',{exact:true}).fill('Thank you for shopping with us. Your invoice is attached.')
  await receiptComposer.getByLabel('WhatsApp API format',{exact:true}).selectOption('Image')
  await receiptComposer.getByLabel('This customer messaged our WhatsApp business within the last 24 hours.').check()
  await receiptComposer.getByRole('button',{name:'Prepare receipt image',exact:true}).click()
  await receiptComposer.getByAltText('Receipt image preview').waitFor()
  const dimensions=await receiptComposer.getByAltText('Receipt image preview').evaluate(image=>({w:image.naturalWidth,h:image.naturalHeight}))
  assert.ok(dimensions.w>400&&dimensions.h>400)
  const downloadPromise=page.waitForEvent('download')
  await receiptComposer.getByRole('link',{name:'Download PNG',exact:true}).click()
  const download=await downloadPromise;await download.saveAs(path.join(output,'receipt-share.png'))
  await receiptComposer.getByRole('button',{name:'Share image…',exact:true}).click()
  assert.deepEqual(await page.evaluate(()=>window.sharedFiles),['ACC-PSINV-2026-00303.png'])
  await receiptComposer.getByRole('button',{name:'Send via WhatsApp API',exact:true}).click()
  await receiptComposer.getByText('Submitted to WhatsApp',{exact:true}).waitFor()
  assert.equal(sends().at(-1).args.delivery_type,'Image')
  assert.match(sends().at(-1).args.image_data,/^data:image\/png;base64,/)
  await receiptComposer.getByLabel('WhatsApp API format',{exact:true}).selectOption('Template')
  await receiptComposer.getByRole('button',{name:'Send via WhatsApp API',exact:true}).click()
  await receiptComposer.getByText('Submitted to WhatsApp',{exact:true}).waitFor()
  assert.equal(sends().at(-1).args.delivery_type,'Template')
  assert.match(sends().at(-1).args.image_data,/^data:image\/png;base64,/)
  await receiptComposer.getByLabel('WhatsApp API format',{exact:true}).selectOption('Text')
  await page.locator('.modal-body').evaluate(element=>{element.scrollTop=0})
  await page.screenshot({path:path.join(output,'receipt-messaging-desktop.png'),fullPage:true})
  await page.setViewportSize({width:390,height:940})
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true)
  await page.screenshot({path:path.join(output,'receipt-messaging-mobile.png'),fullPage:true})
  await page.getByRole('button',{name:'Customer profile',exact:true}).click()
  await page.getByRole('heading',{name:'A Rahman',exact:true}).waitFor()
  assert.equal(await page.evaluate(()=>test.router.currentRoute.value.query.customer),'CUST')
  await page.getByRole('button',{name:'SMS / WhatsApp',exact:true}).click()
  await page.locator('.cust-detail .message-composer').waitFor()

  // Settings save native SMS fields and a server-only token without sending a test message.
  await page.evaluate(()=>test.router.push('/settings?section=messaging'))
  await page.getByRole('heading',{name:'WhatsApp Business API integration',exact:true}).waitFor()
  await page.getByLabel('SMS recipient number format',{exact:true}).selectOption('International digits')
  await page.getByRole('button',{name:'Save messaging settings',exact:true}).click()
  await page.waitForFunction(()=>window.notices.includes('Messaging settings saved'))
  assert.equal(calls.findLast(call=>call.method.endsWith('save_messaging_settings')).args.payload.sms_number_format,'International digits')
  await page.getByLabel('Access token',{exact:true}).fill('FAKE-LOCAL-TEST-TOKEN')
  const before=sends().length
  await page.getByRole('button',{name:'Save WhatsApp connection',exact:true}).click()
  await page.waitForFunction(()=>window.notices.includes('WhatsApp connection saved'))
  assert.equal(await page.getByLabel('Access token',{exact:true}).inputValue(),'')
  await page.getByRole('button',{name:'Check saved connection',exact:true}).click()
  await page.getByText('Connected: Weerakoon Agro · +94770000000',{exact:true}).waitFor()
  await page.getByRole('button',{name:'Save SMS gateway',exact:true}).click()
  await page.waitForFunction(()=>window.notices.includes('SMS gateway saved'))
  assert.equal(sends().length,before)
  const gateway=calls.findLast(call=>call.method.endsWith('save_sms_gateway')).args.payload
  assert.equal(gateway.parameters[0].value,'')
  await page.setViewportSize({width:1440,height:1060})
  await page.getByRole('heading',{name:'WhatsApp Business API integration',exact:true}).scrollIntoViewIfNeeded()
  await page.screenshot({path:path.join(output,'settings-desktop.png'),fullPage:true})
  for(const width of [1024,768,390]){
    await page.setViewportSize({width,height:940})
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true)
    await page.getByRole('heading',{name:'WhatsApp Business API integration',exact:true}).scrollIntoViewIfNeeded()
    if(width===390)await page.screenshot({path:path.join(output,'settings-mobile.png'),fullPage:true})
  }
  assert.deepEqual(errors,[])
  console.log('PASS actual customer profiles, typed SMS/WhatsApp API, service-window gate, template/image payloads, PNG export, popup, duplicate controls, masked settings, no-send connection checks and responsive layouts')
}catch(error){console.error(error);process.exitCode=1}finally{await browser.close();await Promise.race([server.close(),new Promise(resolve=>setTimeout(resolve,3000))])}
