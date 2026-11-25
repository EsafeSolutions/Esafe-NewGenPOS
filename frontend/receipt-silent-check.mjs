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
createApp({render:()=>h(ReceiptView,{receipt,printable:true})}).use(pinia).mount('#app');
window.runSynthetic=async(width,template='Table',layout={})=>{receipt.name='SYNTHETIC-'+width+'-'+template+'-'+(layout.paperWidth||width);receipt.receipt_settings={...receipt.receipt_settings,receipt_paper_width:width+'mm',receipt_template:template};await nextTick();await printManager.connect({explicit:true});await printManager.saveBinding('SYNTHETIC',{receipt:'Xprinter XP-80(Copy 1)',receiptLayout:{[width]:layout}},async()=>{});const source=document.getElementById('receipt-print');const frame=await createReceiptPrintFrame(source,layout);const browser='<!doctype html>'+frame.contentDocument.documentElement.outerHTML;await nativeReceipt(receipt,source);return{browser,request:window.testBridge.prints.at(-1)}};window.ready=true;
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
  return {width:r.width,height:r.height,paddingLeft:style.paddingLeft,paddingRight:style.paddingRight,position:style.position,bodyMargin:getComputedStyle(document.body).margin,barcodeFont:getComputedStyle(root.querySelector('.receipt-barcode .mono')).fontFamily,tableLayout:getComputedStyle(root.querySelector('table')).tableLayout,borders,overflows,textOverflows,footer:root.textContent.includes('ESAFE ERP+POS'),text:root.textContent.includes('12,345.67')}
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
  const cases=baseline ? [[58,'Table',{}],[80,'Table',{}]] : [58,80].flatMap(w=>['Table','Retail','Classic','Compact','Standard','Detailed'].map(t=>[w,t,{}])).concat([[80,'Table',{paperWidth:72,printableWidth:72,inset:3}],[58,'Table',{paperWidth:48,printableWidth:48,inset:2}]])
  for(const [width,template,layout] of cases) {
    const result=await page.evaluate(({width,template,layout})=>runSynthetic(width,template,layout),{width,template,layout})
    const html=Buffer.from(result.request.dataBase64,'base64').toString('utf8'),name=width+'-'+template+'-'+(layout.paperWidth || width)
    await writeFile(path.join(output,name+'.html'),html);await writeFile(path.join(output,name+'.request.json'),JSON.stringify(result.request,null,2));await writeFile(path.join(output,name+'.browser.html'),result.browser)
    await render.setContent(result.browser);await render.emulateMedia({media:'print'});const browserMetrics=await render.evaluate(measure)
    if(template==='Table')await render.screenshot({path:path.join(output,name+'.browser.png'),fullPage:true})
    await render.setContent(html);const silentMetrics=await render.evaluate(measure)
    if(template==='Table') {await render.screenshot({path:path.join(output,name+'.silent.png'),fullPage:true});await render.pdf({path:path.join(output,name+'.pdf'),preferCSSPageSize:true,printBackground:true})}
    if(!baseline) {
      assert.equal(result.request.format,'html');assert.equal(result.request.printerId,'Xprinter XP-80(Copy 1)');assert.equal(result.request.options.size.width,layout.paperWidth || width)
      assert.equal(result.request.options.margins,0);assert.equal(result.request.options.orientation,'portrait');assert.equal(result.request.options.scale,'fit')
      assert.equal(silentMetrics.bodyMargin,'0px');assert.equal(silentMetrics.position,'static');assert.deepEqual(silentMetrics.overflows,[],name+' right/left edges')
      assert.deepEqual(silentMetrics.textOverflows,[],name+' complete monetary text')
      assert.ok(silentMetrics.footer && silentMetrics.text,name+' complete totals/footer')
      assert.ok(Math.abs(browserMetrics.width-silentMetrics.width)<1,name+' same content width')
      assert.equal(silentMetrics.barcodeFont,browserMetrics.barcodeFont,name+' same local font')
      assert.ok(Math.abs(browserMetrics.height-silentMetrics.height)<1,name+' same content height')
      if(template==='Table')for(const selector of Object.keys(browserMetrics.borders))assert.deepEqual(silentMetrics.borders[selector],browserMetrics.borders[selector],name+' '+selector)
      assert.ok(!/<(?:script|link|iframe)\b/i.test(html));assert.ok(!/<img[^>]+src=["']https?:/i.test(html))
    }
    results.push({name,options:result.request.options,browser:browserMetrics,silent:silentMetrics})
    console.log((baseline?'BASELINE ':'PASS ')+name)
  }
  await writeFile(path.join(output,'comparison.json'),JSON.stringify(results,null,2))
  console.log('Saved synthetic documents, exact SDK wire requests, comparisons and PDFs to '+output)
} finally { await browser.close();server.httpServer?.closeAllConnections();await server.close() }
