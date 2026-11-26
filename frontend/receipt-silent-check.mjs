// Synthetic receipts only: real Vue layout + actual SDK, test-only transport/ERP.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { createServer } from 'vite'
import { installEsafeTestBridge } from './test-utils/esafeBridge.mjs'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright').catch(() => import('./.label-test-tools/node_modules/playwright/index.mjs'))
const baseline = process.argv.includes('--baseline')
const root = path.dirname(new URL(import.meta.url).pathname).replace(/^\/(\w:)/, '$1')
const output = path.resolve(root, '../artifacts/esafe-printing/receipt-layout', baseline ? 'before' : 'after')
await mkdir(output, { recursive: true })
const fixture = `<!doctype html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="app"></div><script type="module">
import {createApp,h,reactive,nextTick} from 'vue';import{createPinia}from'pinia';import ReceiptView from '/src/components/ReceiptView.vue';import{useSessionStore}from'/src/stores/session.js';import{printManager,nativeReceipt}from'/src/printing/index.js';import{createReceiptPrintFrame}from'/src/receiptPrint.js';import'/src/styles.css';
const pinia=createPinia(),session=useSessionStore(pinia);session.user='synthetic-test';session.posProfile='SYNTHETIC';session.settings={esafe_printing:{silent:true,receipt_output:'html',copies:1}};
const receipt=reactive({doctype:'POS Invoice',name:'SYNTHETIC',pos_profile:'SYNTHETIC',company:'ESAFE SYNTHETIC SHOP',currency:'LKR',customer_name:'Synthetic fixture',posting_date:'2026-11-26',posting_time:'12:00:00',grand_total:12345.67,rounded_total:12345.67,gross_total:12745.67,total_savings:400,change_amount:654.33,items:[{item_code:'SYNTHETIC-A',item_name:'Long synthetic product name — සිංහල தமிழ் — wraps across receipt lines',qty:2,rate:5000,price_list_rate:5200,amount:10000},{item_code:'SYNTHETIC-B',item_name:'Second synthetic item',qty:1,rate:2345.67,price_list_rate:2345.67,amount:2345.67}],payments:[{mode_of_payment:'Cash',amount:13000}],loyalty:{balance:245,program:'Synthetic loyalty'},loyalty_points_earned:12,receipt_settings:{receipt_template:'Table',receipt_paper_width:'80mm',receipt_show_saved:1,receipt_show_payments:1,receipt_show_invoice_barcode:1,receipt_footer:'Synthetic fixture — not a sale'}});
const defaultReceiptSettings={...receipt.receipt_settings};createApp({render:()=>h(ReceiptView,{receipt,printable:true})}).use(pinia).mount('#app');
window.runSynthetic=async(width,template='Table',layout={})=>{receipt.name='SYNTHETIC-'+width+'-'+template+'-'+(layout.paperWidth||width)+(layout.margins?'-M'+['left','right','top','bottom'].map(k=>layout.margins[k]).join('-'):'')+(layout.receiptDesign?'-CUSTOM':'')+(!layout.paperWidth?'-SAFE':'')+(layout.stress?'-LONG':'');receipt.company=layout.stress?'SYNTHETICSHOPNAMEWITHOUTSPACES'.repeat(3):'ESAFE SYNTHETIC SHOP';receipt.walk_in_code=layout.stress?'SYNTHETICCUSTOMERCODE'.repeat(8):'';receipt.loyalty.program=layout.stress?'SYNTHETICLOYALTYPROGRAM'.repeat(6):'Synthetic loyalty';receipt.receipt_settings={...defaultReceiptSettings,...(layout.receiptDesign?{receipt_design:layout.receiptDesign,receipt_show_loyalty:0,receipt_show_mrp:0,receipt_show_line_discount:0,receipt_show_gross_total:0,receipt_show_item_count:0,receipt_show_total_qty:0}:{}),receipt_paper_width:width+'mm',receipt_template:template};await nextTick();await printManager.connect({explicit:true});await printManager.saveBinding('SYNTHETIC',{receipt:'Xprinter XP-80(Copy 1)',receiptLayout:{[width]:layout}},async()=>{});const source=document.getElementById('receipt-print');const frame=await createReceiptPrintFrame(source,layout);const browser='<!doctype html>'+frame.contentDocument.documentElement.outerHTML;await nativeReceipt(receipt,source);return{browser,fit:JSON.parse(frame.dataset.fit),request:window.testBridge.prints.at(-1)}};window.tryImpossibleNative=async()=>{const before=testBridge.prints.length;try{await nativeReceipt(receipt,document.getElementById('receipt-print'),{reprint:true});return{blocked:false}}catch(e){return{blocked:true,message:e.message,unchanged:before===testBridge.prints.length,frames:document.querySelectorAll('#receipt-print-frame').length}}};window.ready=true;
</script></body></html>`
const server = await createServer({ root, base:'/', server:{ host:'127.0.0.1',port:0,open:false }, plugins:[{ name:'receipt-silent-fixture', configureServer(s){s.middlewares.use('/receipt-silent.html',async(req,res)=>{res.setHeader('Content-Type','text/html');res.end(await s.transformIndexHtml('/receipt-silent.html',fixture))})} }] })
await server.listen()
const browser = await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe'})
function measure() {
  const root=document.getElementById('receipt-print'),r=root.getBoundingClientRect(),style=getComputedStyle(root)
  const selectors=['.retail-head','.retail-meta','.retail-items th','.retail-item-values td:last-child','.retail-totals','.retail-totals .row + .row','.retail-totals .row > :last-child','.retail-savings','.retail-loyalty']
  const borders=Object.fromEntries(selectors.map((selector)=>{const e=root.querySelector(selector);if(!e)return[selector,null];const s=getComputedStyle(e);return[selector,{top:s.borderTop,bottom:s.borderBottom,left:s.borderLeft,right:s.borderRight}]}))
  const overflows=[...root.querySelectorAll('th,td,.row > *, .retail-savings > *')].filter(e=>{const b=e.getBoundingClientRect();return b.right>r.right+1 || b.left<r.left-1}).map(e=>e.className || e.tagName)
  const textOverflows=[...root.querySelectorAll('.retail-item-values td,.row > :last-child')].filter(e=>{if(!e.textContent.trim())return false;const range=document.createRange();range.selectNodeContents(e);const text=range.getBoundingClientRect(),box=e.getBoundingClientRect();return text.right>box.right+1 || text.left<box.left-1}).map(e=>e.textContent)
  return {width:r.width,height:r.height,paddingTop:style.paddingTop,paddingBottom:style.paddingBottom,paddingLeft:style.paddingLeft,paddingRight:style.paddingRight,position:style.position,bodyMargin:getComputedStyle(document.body).margin,barcodeFont:getComputedStyle(root.querySelector('.receipt-barcode .mono')).fontFamily,tableLayout:getComputedStyle(root.querySelector('table')).tableLayout,borders,overflows,textOverflows,footer:root.textContent.includes('ESAFE ERP+POS'),text:root.textContent.includes('12,345.67')}
}
try {
  const page=await browser.newPage({viewport:{width:1280,height:1000}}),render=await browser.newPage({viewport:{width:500,height:1400}})
  await page.addInitScript(installEsafeTestBridge)
  await page.route('https://fonts.googleapis.com/**',r=>r.abort())
  await page.route('**/api/method/**',r=>r.fulfill({json:{message:{ok:true}}}))
  await page.goto('http://127.0.0.1:'+server.httpServer.address().port+'/receipt-silent.html')
  await page.waitForFunction(()=>window.ready)
  await page.evaluate(()=>{testBridge.printers=[{id:'Xprinter XP-80(Copy 1)',name:'Xprinter XP-80(Copy 1)',isDefault:true}]})
  const results=[]
  const cases=baseline ? [[58,'Table',{}],[80,'Table',{}]] : [58,80].flatMap(w=>['Table','Retail','Classic','Compact','Standard','Detailed'].map(t=>[w,t,{paperWidth:w,printableWidth:w}])).concat([[80,'Table',{paperWidth:72,printableWidth:72,inset:3}],[58,'Table',{paperWidth:48,printableWidth:48,inset:2}],[80,'Table',{paperWidth:72,printableWidth:72,margins:{left:3,right:7,top:1,bottom:6}}],[58,'Table',{margins:{left:1,right:4,top:0,bottom:8}}],[80,'Retail',{margins:{left:2,right:10,top:0,bottom:0}}],[58,'Table',{}],[80,'Table',{}],[80,'Retail',{stress:true}],[58,'Table',{stress:true}],[58,'Table',{receiptDesign:{fontSize:16,totalSize:24}}],[80,'Table',{paperWidth:72,printableWidth:72,receiptDesign:{headerAlign:'left',footerAlign:'right',itemAlign:'left',labelAlign:'left',valueAlign:'right',fontSize:11,totalSize:15,lineHeight:1.3,paddingTop:1,paddingRight:1,paddingBottom:2,paddingLeft:1,sectionGap:2,itemPadding:0.3,borderWidth:1.2,barcodeHeight:32}}]])
  for(const [width,template,layout] of cases) {
    const result=await page.evaluate(({width,template,layout})=>runSynthetic(width,template,layout),{width,template,layout})
    const html=Buffer.from(result.request.dataBase64,'base64').toString('utf8'),name=width+'-'+template+'-'+(layout.paperWidth || width)+(layout.margins?'-M'+['left','right','top','bottom'].map(k=>layout.margins[k]).join('-'):'')+(layout.receiptDesign?'-CUSTOM':'')+(!layout.paperWidth?'-SAFE':'')+(layout.stress?'-LONG':'')
    await writeFile(path.join(output,name+'.html'),html);await writeFile(path.join(output,name+'.request.json'),JSON.stringify(result.request,null,2));await writeFile(path.join(output,name+'.browser.html'),result.browser)
    await render.setContent(result.browser);await render.emulateMedia({media:'print'});const browserMetrics=await render.evaluate(measure)
    if(template==='Table')await render.screenshot({path:path.join(output,name+'.browser.png'),fullPage:true})
    await render.setContent(html);const silentMetrics=await render.evaluate(measure)
    if(template==='Table') {await render.screenshot({path:path.join(output,name+'.silent.png'),fullPage:true});await render.pdf({path:path.join(output,name+'.pdf'),preferCSSPageSize:true,printBackground:true})}
    if(!baseline) {
      assert.equal(result.request.format,'html');assert.equal(result.request.printerId,'Xprinter XP-80(Copy 1)');assert.equal(result.request.options.size.width,layout.paperWidth || (width===58?48:72))
      assert.equal(result.request.options.margins,0);assert.equal(result.request.options.orientation,'portrait');assert.equal(result.request.options.scale,'fit')
      assert.equal(silentMetrics.bodyMargin,'0px');assert.equal(silentMetrics.position,'static');assert.deepEqual(silentMetrics.overflows,[],name+' right/left edges')
      assert.deepEqual(silentMetrics.textOverflows,[],name+' complete monetary text')
      assert.ok(silentMetrics.footer && silentMetrics.text,name+' complete totals/footer')
      assert.ok(Math.abs(browserMetrics.width-silentMetrics.width)<1,name+' same content width')
      for(const side of ['top','right','bottom','left']) { const key='padding'+side[0].toUpperCase()+side.slice(1);assert.equal(silentMetrics[key],browserMetrics[key],name+' '+side+' margin');if(layout.margins)assert.ok(Math.abs(parseFloat(silentMetrics[key])-layout.margins[side]*96/25.4)<0.05,name+' exact '+side+' mm') }
      assert.equal(silentMetrics.barcodeFont,browserMetrics.barcodeFont,name+' same local font')
      assert.ok(Math.abs(browserMetrics.height-silentMetrics.height)<1,name+' same content height')
      if(template==='Table')for(const selector of Object.keys(browserMetrics.borders))assert.deepEqual(silentMetrics.borders[selector],browserMetrics.borders[selector],name+' '+selector)
      if(layout.receiptDesign?.paddingRight!==undefined) {assert.ok(!html.includes('Points balance'));assert.ok(!html.includes('Gross total'));assert.ok(!html.includes('>MRP<'));assert.equal(await render.locator('.receipt-company').evaluate(e=>getComputedStyle(e).textAlign),'left');assert.ok(Math.abs(parseFloat(silentMetrics.paddingRight)-4*96/25.4)<0.05)}
      assert.ok(!/<(?:script|link|iframe)\b/i.test(html));assert.ok(!/<img[^>]+src=["']https?:/i.test(html))
    }
    if(layout.receiptDesign?.totalSize===24)assert.ok(result.fit.adjusted>0,'Oversized values must be fitted rather than clipped')
    results.push({name,fit:result.fit,options:result.request.options,browser:browserMetrics,silent:silentMetrics})
    console.log((baseline?'BASELINE ':'PASS ')+name)
  }
  const blocked=await page.evaluate(async()=>{const before=testBridge.prints.length;try{await runSynthetic(58,'Table',{paperWidth:48,printableWidth:48,margins:{left:18,right:18,top:0,bottom:0}});return{blocked:false}}catch(e){return{blocked:true,message:e.message,unchanged:before===testBridge.prints.length,frames:document.querySelectorAll('#receipt-print-frame').length}}})
  assert.ok(blocked.blocked && blocked.unchanged && blocked.frames===0,JSON.stringify(blocked))
  assert.match(blocked.message,/does not fit/)
  const blockedNative=await page.evaluate(()=>tryImpossibleNative())
  assert.ok(blockedNative.blocked && blockedNative.unchanged && blockedNative.frames===0,JSON.stringify(blockedNative))
  assert.match(blockedNative.message,/does not fit/)
  console.log('PASS oversized content blocked before dispatch, with frame cleanup')
  await writeFile(path.join(output,'comparison.json'),JSON.stringify(results,null,2))
  console.log('Saved synthetic documents, exact SDK wire requests, comparisons and PDFs to '+output)
} finally { await browser.close();server.httpServer?.closeAllConnections();await server.close() }
