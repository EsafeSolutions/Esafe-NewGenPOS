// Real selling, checkout, handover and display components; synthetic sales only.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
const root = path.dirname(fileURLToPath(import.meta.url))
const output = path.resolve(root, '../docs/screenshots/sounds')
await mkdir(output, { recursive: true })
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body><header id="sell-header-tools" style="background:var(--pos-blue);padding:12px;display:flex;gap:8px"></header><div id="app" style="display:flex;min-height:calc(100dvh - 60px)"></div><script type="module">
import { createApp, h, ref, watch } from 'vue'; import { createPinia } from 'pinia'; import { createRouter, createMemoryHistory } from 'vue-router'
import SellView from '/src/views/SellView.vue'; import ReceiptModal from '/src/components/ReceiptModal.vue'; import CustomerDisplayView from '/src/views/CustomerDisplayView.vue'
import { useSessionStore } from '/src/stores/session.js'; import { useCartStore } from '/src/stores/cart.js'; import { useCatalogStore } from '/src/stores/catalog.js'
import { displayReceipt, displayTerminalId, publishCart, receiptSnapshot } from '/src/customerDisplay.js'
import * as sounds from '/src/posSounds.js'; import { setCurrency } from '/src/format.js'; import '/src/styles.css'
const pinia = createPinia(), session = useSessionStore(pinia), cart = useCartStore(pinia), catalog = useCatalogStore(pinia)
setCurrency('LKR'); session.currency='LKR'; session.company='ESAFE Retail'; session.user='cashier'; session.posProfile='Till A'; session.defaultCustomer='WALK-IN'
session.registerSession={ name:'REG-SOUNDS', opened_by:'cashier' }; session.permissions={ sell:true,can_edit_price:true }
session.settings={ ...session.settings, receipt_template:'Retail', receipt_show_payments:1, enable_customer_display:1, enable_price_checker:0 }
session.paymentModes=[{ mode_of_payment:'Cash',type:'Cash',default:1,account_currency:'LKR' }]; session.notify=(message)=>window.notices.push(message)
session.refreshQueueCount=async()=>{}; catalog.items=[{ item_code:'TEA', item_name:'Ceylon tea', stock_uom:'Nos', price:195, is_stock_item:1, actual_qty:100 }]
const historical=ref(null), directReceipt=ref(null), stage=ref(location.hash.startsWith('#/display')?'display':'sell')
watch(displayReceipt, value=>{ if(value) publishCart({...value,canStart:true}) })
const router=createRouter({ history:createMemoryHistory(),routes:[{path:'/',component:SellView},{path:'/customers',component:{render:()=>null}}] }); await router.push('/');await router.isReady()
createApp({ render:()=>stage.value==='display'?h(CustomerDisplayView):directReceipt.value?h(ReceiptModal,{receipt:directReceipt.value,checkoutCompletion:true,onClose:()=>{directReceipt.value=null}}):historical.value?h(ReceiptModal,{ receipt:historical.value,reprint:true,checkoutCompletion:true,onClose:()=>{historical.value=null} }):h(SellView) }).use(pinia).use(router).mount('#app')
window.test={ session,cart,catalog,historical,directReceipt,sounds,displayTerminalId,displayReceipt,publishCart,receiptSnapshot };window.notices=[];window.ready=true
</script></body></html>`
const server = await createServer({ root, base:'/', server:{ host:'127.0.0.1', port:0, open:false, hmr:false },
  plugins:[{ name:'sounds-fixture',configureServer(s){s.middlewares.use('/sounds-check.html',async(req,res)=>{res.setHeader('Content-Type','text/html');res.end(await s.transformIndexHtml('/sounds-check.html',html))})} }] })
await server.listen()
const browser = await chromium.launch({ headless:true, executablePath:process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe' })
const context = await browser.newContext({ viewport:{width:1440,height:1000} })
const page = await context.newPage(), errors=[]
page.on('pageerror',error=>errors.push(error.message))
await context.route('https://fonts.googleapis.com/**',route=>route.abort())
await context.route('https://fonts.gstatic.com/**',route=>route.abort())
await context.addInitScript(() => {
  window.soundEvents={ tones:0,disconnected:0,spoken:[],cancels:0 }
  const NativeAudio=window.AudioContext
  window.AudioContext=class extends NativeAudio {
    createOscillator(){ const tone=super.createOscillator();window.soundEvents.tones++;const disconnect=tone.disconnect.bind(tone);tone.disconnect=()=>{window.soundEvents.disconnected++;disconnect()};return tone }
  }
  const voices=window.speechSynthesis?.getVoices() || []
  Object.defineProperty(window,'speechSynthesis',{configurable:true,value:{
    getVoices:()=>voices, speak:(message)=>{window.soundEvents.spoken.push({text:message.text,lang:message.lang,volume:message.volume});window.lastUtterance=message},
    cancel:()=>{window.soundEvents.cancels++},
  }})
})
let rejectSale=false, offlineSubmit=false, submitted=null, sequence=0
await context.route('**/api/method/**',async route=>{
  const method=route.request().url().split('/api/method/')[1], args=route.request().postDataJSON() || {}
  let message={}
  if(method==='esafepos.api.sales.quote_sale') message={payable:195,currency:'LKR',rate:1,foreign:false,blocked_modes:{}}
  else if(method==='esafepos.api.sales.submit_sale') {
    if(rejectSale)return route.fulfill({status:417,json:{exception:'Synthetic sale rejected'}})
    if(offlineSubmit)return route.abort('failed')
    submitted=args.payload
    const paid=submitted.payments.reduce((sum,p)=>sum+p.amount,0), saved=submitted.loyalty_change_amount || 0
    message={name:'SOUND-INV-'+(++sequence),customer:'CUSTOMER',customer_name:'Nimal',company:'ESAFE Retail',currency:'LKR',company_currency:'LKR',
      posting_date:'2026-11-28',posting_time:'10:00:00',grand_total:195,rounded_total:195,paid_amount:paid,change_amount:Math.max(0,paid-195-saved),
      loyalty_change_points:saved,loyalty_change_amount:saved,loyalty:{balance:40+saved},payments:submitted.payments,
      items:[{item_code:'TEA',item_name:'Ceylon tea',qty:1,uom:'Nos',rate:195,amount:195}]}
  } else if(method==='esafepos.api.customers.get_wallet') message={loyalty_points:40,conversion_factor:1,loyalty_program:'Retail',change_to_loyalty:{enabled:true}}
  else if(method==='esafepos.api.cashback.get_cashback') message={}
  await route.fulfill({json:{message}})
})
const url=`http://127.0.0.1:${server.httpServer.address().port}/sounds-check.html`
async function openSell() { await page.goto(url);await page.waitForFunction(()=>window.ready);await page.getByRole('button',{name:'Add Ceylon tea to cart',exact:true}).waitFor() }
async function pay(amount=200,{points=false}={}) {
  await page.getByRole('button',{name:'Add Ceylon tea to cart',exact:true}).click()
  if(points) await page.evaluate(()=>{test.cart.customer={name:'CUSTOMER',customer_name:'Nimal'};test.cart.wallet={loyalty_program:'Retail',change_to_loyalty:{enabled:true},loyalty_points:40,conversion_factor:1}})
  await page.locator('.pay').click();await page.locator('.tender-input').fill(String(amount));await page.getByRole('button',{name:'Cash',exact:true}).click()
  if(points)await page.locator('.change-points-choice input').check()
  await page.locator('.complete').click()
}
async function assertNoOverflow(surface) {
  assert.ok(await surface.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal overflow')
}
try {
  await openSell()
  await page.getByRole('button',{name:'Add Ceylon tea to cart',exact:true}).click()
  assert.ok(await page.evaluate(()=>soundEvents.tones>0),'Ordering emits audio nodes')
  await page.waitForFunction(()=>soundEvents.disconnected===soundEvents.tones)
  await page.getByRole('button',{name:'POS sounds',exact:true}).click()
  await page.getByRole('dialog',{name:'POS sounds'}).waitFor()
  await page.getByLabel('Ordering click sounds',{exact:true}).uncheck()
  await page.getByLabel('Spoken thank-you greeting',{exact:true}).uncheck()
  await page.getByLabel('Volume',{exact:false}).fill('0.35')
  await page.getByRole('button',{name:'Done',exact:true}).click()
  const count=await page.evaluate(()=>soundEvents.tones)
  await page.getByRole('button',{name:'Add Ceylon tea to cart',exact:true}).click()
  assert.equal(await page.evaluate(()=>soundEvents.tones),count,'Muted ordering adds items silently')
  await page.reload();await page.waitForFunction(()=>window.ready)
  assert.deepEqual(await page.evaluate(()=>JSON.parse(localStorage.getItem('esafepos-sounds'))),{clicks:false,greeting:false,volume:0.35})
  await page.evaluate(()=>{test.sounds.setSoundPreference('clicks',true);test.sounds.setSoundPreference('greeting',true);test.sounds.setSoundPreference('volume',0.6)})
  await page.getByRole('button',{name:'POS sounds',exact:true}).click()
  await page.screenshot({path:path.join(output,'settings-desktop.png')})
  await page.setViewportSize({width:390,height:844});await assertNoOverflow(page)
  await page.screenshot({path:path.join(output,'settings-mobile.png')})
  await page.keyboard.press('Escape');assert.equal(await page.locator('dialog[open]').count(),0)
  await page.setViewportSize({width:1440,height:1000})
  console.log('PASS ordering audio, cleanup, mute, volume persistence and responsive sound controls')

  const terminal=await page.evaluate(()=>test.displayTerminalId), display=await context.newPage()
  display.on('pageerror',error=>errors.push(error.message));await display.goto(url+'#/display?terminal='+terminal)
  await pay()
  await page.getByRole('button',{name:'Change handed over',exact:true}).waitFor()
  assert.equal(await page.locator('.sale-thank-you[open]').count(),0)
  assert.equal(await page.evaluate(()=>soundEvents.spoken.length),0,'No greeting before handover')
  assert.equal(await display.locator('.cd-farewell').count(),0)
  await page.screenshot({path:path.join(output,'handover-desktop.png')})
  await page.setViewportSize({width:390,height:844});await assertNoOverflow(page)
  await page.screenshot({path:path.join(output,'handover-mobile.png')})
  await page.setViewportSize({width:1440,height:1000})
  await page.getByRole('button',{name:'Change handed over',exact:true}).click()
  await page.getByRole('dialog',{name:'Thank you very much for your purchase!'}).waitFor()
  assert.deepEqual(await page.evaluate(()=>soundEvents.spoken.map(x=>x.text)),['Thank you very much for your purchase. Come again. We wish you all the best!'])
  await display.locator('.cd-farewell').waitFor()
  await display.getByText('Change handed over',{exact:false}).waitFor()
  await page.screenshot({path:path.join(output,'greeting-desktop.png')})
  await display.screenshot({path:path.join(output,'display-desktop.png')})
  await page.setViewportSize({width:390,height:844});await assertNoOverflow(page)
  await page.screenshot({path:path.join(output,'greeting-mobile.png')})
  await display.setViewportSize({width:390,height:844});await assertNoOverflow(display)
  await display.screenshot({path:path.join(output,'display-mobile.png')})
  assert.equal(await page.evaluate(()=>document.activeElement?.textContent.trim()),'New Sale','The next-sale button receives focus')
  await page.getByRole('button',{name:'Replay greeting',exact:true}).click()
  assert.equal(await page.evaluate(()=>soundEvents.spoken.length),2,'Replay is explicit')
  await page.getByRole('button',{name:'New Sale',exact:true}).click()
  assert.ok(await page.evaluate(()=>soundEvents.cancels>=2),'Closing cancels the owned greeting')
  assert.equal(await page.locator('.sale-thank-you[open]').count(),0)
  await display.close()
  console.log('PASS cash handover gate, single greeting, replay/cancel, customer monitor and desktop/mobile layouts')

  await page.setViewportSize({width:1440,height:1000});await openSell();await pay(200,{points:true})
  await page.getByRole('button',{name:'Thank customer',exact:true}).waitFor()
  assert.equal(submitted.loyalty_change_amount,5)
  assert.equal(await page.evaluate(()=>soundEvents.spoken.length),0)
  await page.getByRole('button',{name:'Thank customer',exact:true}).click()
  await page.locator('.sale-thank-you[open]').waitFor()
  await page.getByText('5 points saved from your change',{exact:true}).waitFor()
  assert.equal(await page.locator('.sale-thank-you').getByText('Change handed over',{exact:false}).count(),0)
  await page.screenshot({path:path.join(output,'points-desktop.png')})
  await page.setViewportSize({width:390,height:844});await assertNoOverflow(page)
  await page.screenshot({path:path.join(output,'points-mobile.png')})
  await page.keyboard.press('Escape')
  console.log('PASS saved-change points are confirmed before the greeting')

  await page.setViewportSize({width:1440,height:1000});await openSell();await pay(200.5,{points:true})
  await page.getByRole('button',{name:'Change handed over',exact:true}).click();await page.locator('.sale-thank-you[open]').waitFor()
  await page.getByText('5 points saved from your change',{exact:true}).waitFor()
  assert.match(await page.locator('.thanks-summary').textContent(),/LKR\s*0.50/)
  await page.keyboard.press('Escape')
  await page.evaluate(()=>{test.directReceipt.value={name:'FOREIGN-CHANGE',currency:'USD',company_currency:'LKR',change_currency:'LKR',change_amount:1,base_change_amount:300,grand_total:5,items:[]}})
  await page.getByRole('button',{name:'Change handed over',exact:true}).click();await page.locator('.sale-thank-you[open]').waitFor()
  assert.match(await page.locator('.thanks-summary').textContent(),/LKR\s*300.00/)
  await page.keyboard.press('Escape')
  console.log('PASS partial points retain fractional cash confirmation; foreign change uses the actual drawer currency')

  await openSell();await page.evaluate(()=>test.sounds.setSoundPreference('greeting',false));await pay(195)
  await page.getByRole('button',{name:'Thank customer',exact:true}).click();await page.locator('.sale-thank-you[open]').waitFor()
  assert.equal(await page.evaluate(()=>soundEvents.spoken.length),0,'Voice switch is independent')
  await page.keyboard.press('Escape')
  await openSell();await page.evaluate(()=>{test.sounds.setSoundPreference('greeting',true);Object.defineProperty(window,'speechSynthesis',{configurable:true,value:undefined});window.AudioContext=class{constructor(){throw new Error('Audio denied')}}})
  await pay(195);await page.getByRole('button',{name:'Thank customer',exact:true}).click()
  await page.getByRole('dialog').getByRole('status').filter({hasText:'Voice is unavailable'}).waitFor()
  await page.keyboard.press('Escape')
  console.log('PASS exact payment, muted voice, unsupported speech and denied audio never block checkout')

  await openSell();rejectSale=true;await pay()
  await page.waitForFunction(()=>notices.some(x=>x.includes('Synthetic sale rejected')))
  assert.equal(await page.locator('.sale-thank-you[open]').count(),0)
  assert.equal(await page.evaluate(()=>soundEvents.spoken.length),0)
  assert.equal(await page.evaluate(()=>test.cart.lines.length),1)
  rejectSale=false
  await openSell();offlineSubmit=true;await pay();await page.getByRole('button',{name:'Change handed over',exact:true}).waitFor()
  assert.equal(await page.evaluate(()=>soundEvents.spoken.length),0)
  await page.getByRole('button',{name:'Change handed over',exact:true}).click();await page.locator('.sale-thank-you[open]').waitFor()
  await page.getByText('Saved offline, it will post to ERPNext automatically when the connection returns.',{exact:true}).waitFor()
  offlineSubmit=false
  console.log('PASS rejected sales retain the basket without greeting; queued sales wait for handover')

  await openSell();await page.evaluate(()=>{test.historical.value={name:'OLD-RECEIPT',currency:'LKR',grand_total:195,items:[],change_amount:5}})
  await page.getByRole('button',{name:'New Sale',exact:true}).click()
  assert.equal(await page.evaluate(()=>soundEvents.spoken.length),0,'Reprints never trigger a purchase greeting')
  await page.evaluate(()=>{test.historical.value={name:'RETURN',currency:'LKR',grand_total:-195,is_return:true,items:[]}})
  await page.getByRole('button',{name:'Done',exact:true}).click()
  assert.equal(await page.evaluate(()=>soundEvents.spoken.length),0,'Refunds never trigger a purchase greeting')
  await openSell()
  await page.evaluate(()=>{
    window.AudioContext=class {
      state='suspended'
      resume(){return new Promise(resolve=>{window.resumeAudio=()=>{this.state='running';resolve()}})}
      createOscillator(){soundEvents.tones++;throw new Error('Stale audio was scheduled')}
    }
    test.sounds.playOrderSound()
  })
  assert.equal(await page.evaluate(()=>soundEvents.tones),0,'Suspended audio never queues a tap')
  await page.evaluate(async()=>{await new Promise(resolve=>setTimeout(resolve,300));resumeAudio();await Promise.resolve()})
  assert.equal(await page.evaluate(()=>soundEvents.tones),0,'A late resume discards stale ordering sounds')
  assert.deepEqual(errors,[])
  console.log('PASS receipt reprints and refunds stay silent; suspended audio drops stale taps; no browser errors')
} catch(error) {
  await page.screenshot({path:path.join(output,'failure.png'),fullPage:true}).catch(()=>{})
  console.error('Browser errors:',errors);throw error
} finally { await browser.close();await server.close() }
