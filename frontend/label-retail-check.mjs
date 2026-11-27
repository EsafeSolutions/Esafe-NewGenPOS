// Real Vue/editor/SVG/PDF pipeline; ERP traffic and native print calls are not used.
import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const { chromium } = await import('./.label-test-tools/node_modules/playwright/index.mjs')
const require = createRequire(import.meta.url)
const decoder = require.resolve('./.label-test-tools/node_modules/@zxing/library/umd/index.min.js')
const root = path.dirname(fileURLToPath(import.meta.url)), out = path.join(root, '../artifacts/labels/retail')
await mkdir(out, { recursive: true })
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><div id="app"></div><script type="module">
import {createApp} from 'vue';import {createPinia} from 'pinia';import LabelsView from '/src/views/LabelsView.vue';import {useSessionStore} from '/src/stores/session.js';import * as render from '/src/labels/render.js';import * as design from '/src/labels/design.js';import * as stock from '/src/labels/stock.js';import * as print from '/src/labels/printing.js';import * as prices from '/src/labels/prices.js';import '/src/styles.css';
const pinia=createPinia(),session=useSessionStore(pinia);session.user='retail-test';session.company='OSAKA CITY (PVT) LTD';session.posProfile='Main';session.permissions={print_labels:true,settings:true};createApp(LabelsView).use(pinia).mount('#app');window.labelTest={render,design,stock,print,prices};
</script></body></html>`
const server = await createServer({root,base:'/',server:{host:'127.0.0.1',port:0,open:false},plugins:[{name:'retail-label-test',configureServer(s){s.middlewares.use('/retail-check.html',async(req,res)=>{res.setHeader('Content-Type','text/html');res.end(await s.transformIndexHtml('/retail-check.html',html))})}}]})
await server.listen()
const browser = await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'})
const page = await browser.newPage({viewport:{width:1600,height:1100}}), errors=[], calls=[]
page.on('pageerror',error=>errors.push(error.message))
await page.route('https://fonts.googleapis.com/**',route=>route.abort())
await page.route('https://fonts.gstatic.com/**',route=>route.abort())
await page.route('**/api/method/**',async route=>{
  const method=route.request().url().split('/').pop();calls.push(method)
  let message={}
  if(method.endsWith('.workspace'))message={presets:[],can_manage:true,needs_migration:false,logo:''}
  if(method.endsWith('.resolve_scan'))message={found:true,item:{item_code:'LIVE-ITEM',item_name:'Actual priced item'}}
  if(method.endsWith('.items'))message={rows:[{item_code:'LIVE-ITEM',item_name:'Actual priced item',barcode:'00123456',price_with_tax:1250.75,currency:'LKR',uom:'Nos',qty:1}]}
  await route.fulfill({json:{message}})
})
try {
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/retail-check.html`)
  await page.getByRole('heading',{name:'Label printing',exact:true}).waitFor()
  await page.getByLabel('Size preset',{exact:true}).selectOption('60x30')
  await page.getByRole('tab',{name:'Design',exact:true}).click()
  await page.getByRole('button',{name:'Bold retail',exact:true}).click()
  assert.equal(await page.getByLabel('Label font',{exact:true}).inputValue(),'Impact')
  await page.locator('.art [data-element="shop"]').waitFor()
  assert.match(await page.locator('.art').textContent(),/FOLDING WASHING.M 9L/)
  assert.match(await page.locator('.art').textContent(),/OSAKA CITY \(PVT\) LTD/)
  assert.match(await page.locator('.art').textContent(),/30820392/)
  assert.doesNotMatch(await page.locator('.art [data-element="price"]').textContent(),/\.00/)
  const fullPriceSize=Number(await page.locator('.art [data-element="price"] text').getAttribute('font-size'))
  assert.ok(await page.locator('.art').evaluate(el=>el.querySelector('[data-element="price"] text').getBoundingClientRect().height>el.querySelector('svg').getBoundingClientRect().height*.88),'The price fills the available label height')
  assert.match(await page.locator('.art [data-element="price"]').getAttribute('transform'),/rotate\(90\)/)
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true})
  await page.addScriptTag({content:await readFile(decoder,'utf8')})
  const proof = await page.evaluate(async()=>{
    const {render,design,stock,print,prices}=labelTest,row={item_name:'FOLDING WASHING.M 9L',item_code:'30820392',barcode:'30820392',price_text:prices.labelMoney(3990,'LKR'),shop:'OSAKA CITY (PVT) LTD',qty:1}
    const d=design.designFor('bold-retail'),s={...stock.DEFAULT_STOCK,w:60,h:30},scene=render.labelScene(row,s,d)
    if(scene.errors.length)throw Error(scene.errors.join('\n'))
    const svg=document.querySelector('.art svg'),outside=[]
    for(const el of svg.querySelectorAll('[data-element]')) {
      const b=el.getBoundingClientRect(),paper=svg.getBoundingClientRect()
      if(b.left<paper.left-.5||b.right>paper.right+.5||b.top<paper.top-.5||b.bottom>paper.bottom+.5)outside.push(el.dataset.element)
    }
    const fits=[...svg.querySelectorAll('text')].every(el=>el.querySelectorAll('tspan').length===1)
    const url=URL.createObjectURL(new Blob([scene.svg],{type:'image/svg+xml'})),image=new Image();image.src=url;await image.decode()
    const canvas=document.createElement('canvas');canvas.width=60*8;canvas.height=30*8;canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);URL.revokeObjectURL(url)
    // Decode only the main barcode area, preserving the symbol's quiet zones.
    const crop=document.createElement('canvas');crop.width=48*8;crop.height=12*8
    crop.getContext('2d').drawImage(canvas,0,7*8,48*8,12*8,0,0,48*8,12*8)
    const decoded=await new ZXing.BrowserMultiFormatReader().decodeFromImageUrl(crop.toDataURL())
    const job=stock.layoutJob([row],s),pages=print.jobSvgs(job,d,stock.DEFAULT_PRINTER,false)
    const pdf=await print.pdfDocument(pages,job.geometry,203.2,true)
    const pdfText=await pdf.text()
    return {outside,fits,decoded:decoded.text,svg:scene.svg,pdf:Array.from(new Uint8Array(await pdf.arrayBuffer())),pdfValid:pdfText.startsWith('%PDF-1.4'),font:svg.querySelector('[data-element="name"] text').getAttribute('font-family')}
  })
  assert.deepEqual(proof.outside,[]);assert.equal(proof.fits,true);assert.equal(proof.decoded,'30820392');assert.equal(proof.pdfValid,true)
  await writeFile(path.join(out,'sample.svg'),proof.svg)
  await writeFile(path.join(out,'sample.pdf'),Buffer.from(proof.pdf))
  const specimen=await browser.newPage({viewport:{width:900,height:450}})
  await specimen.setContent(`<style>body{margin:0}svg{display:block;width:900px;height:450px}</style>${proof.svg}`)
  await specimen.screenshot({path:path.join(out,'label.png')});await specimen.close()
  await page.getByLabel('Advanced',{exact:true}).check()
  await page.getByLabel('Selected element',{exact:true}).selectOption('price')
  assert.equal(await page.getByLabel('Keep on one line',{exact:true}).isChecked(),true)
  assert.equal(await page.getByLabel('Fill text box',{exact:true}).isChecked(),true)
  await page.getByLabel('Fill text box',{exact:true}).uncheck()
  assert.ok(Number(await page.locator('.art [data-element="price"] text').getAttribute('font-size'))<fullPriceSize,'Auto-fill is larger than ordinary fixed-size fitting')
  await page.getByLabel('Fill text box',{exact:true}).check()
  await page.getByLabel('Element font',{exact:true}).selectOption('Arial')
  assert.equal(await page.locator('.art [data-element="price"] text').getAttribute('font-family'),'Arial,sans-serif')
  // A real queued item must replace the demonstration text and amount.
  await page.getByPlaceholder('Scan or search items…').fill('LIVE-ITEM')
  await page.getByPlaceholder('Scan or search items…').press('Enter')
  await page.locator('.queue-list li').waitFor()
  assert.match(await page.locator('.art').textContent(),/Actual priced item/)
  assert.match(await page.locator('.art').textContent(),/1,250.75/)
  assert.doesNotMatch(await page.locator('.art').textContent(),/FOLDING WASHING/)
  await page.reload()
  await page.getByRole('tab',{name:'Design',exact:true}).click()
  assert.equal(await page.getByLabel('Label font',{exact:true}).inputValue(),'Impact','The selected font survives local setup reload')
  await page.getByLabel('Advanced',{exact:true}).check()
  await page.getByLabel('Selected element',{exact:true}).selectOption('price')
  await page.getByLabel('Element font',{exact:true}).selectOption('')
  await page.getByLabel('Advanced',{exact:true}).uncheck()
  await page.setViewportSize({width:390,height:900})
  await page.locator('.preview-panel').scrollIntoViewIfNeeded()
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true})
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true)
  assert.ok(!calls.some(method=>/prepare_job|register_intent|submit_sale|save_preset/.test(method)))
  assert.deepEqual(errors,[])
  await writeFile(path.join(out,'result.json'),JSON.stringify({decoded:proof.decoded,font:proof.font,outside:proof.outside,singleLineFit:proof.fits,pdfValid:proof.pdfValid,physicalPrint:false},null,2)+'\n')
  console.log('PASS reference label preview, condensed/override fonts, whole-price formatting, full-box price sizing, single-line bounds, independently decoded Code 128, PDF pipeline, actual decimal-price/name isolation, persisted setup and mobile layout; no physical print')
} catch(error) {console.error(error);await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});process.exitCode=1}
finally {await browser.close();server.httpServer?.closeAllConnections();await server.close()}
