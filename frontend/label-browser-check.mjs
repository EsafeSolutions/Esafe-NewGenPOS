// Requires installed Chrome, Playwright and @zxing/library for independent decoding.
// Isolated tools: npm install --prefix .label-test-tools --no-save --package-lock=false --ignore-scripts playwright@1.56.1 @zxing/library@0.21.3
import assert from 'node:assert/strict'
import { mkdir,writeFile } from 'node:fs/promises'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright').catch(()=>import('./.label-test-tools/node_modules/playwright/index.mjs'))
const require=createRequire(import.meta.url)
let decoder
try{decoder=require.resolve('@zxing/library/umd/index.min.js')}catch{decoder=new URL('./.label-test-tools/node_modules/@zxing/library/umd/index.min.js',import.meta.url)}
const root=path.dirname(fileURLToPath(import.meta.url)),out=process.env.LABEL_ARTIFACTS || path.join(root,'../artifacts/labels')
await mkdir(out,{recursive:true})
const html=`<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><div id="app"></div><script type="module">
import {createApp} from 'vue';import {createPinia} from 'pinia';import LabelsView from '/src/views/LabelsView.vue';import SettingsView from '/src/views/SettingsView.vue';import {useSessionStore} from '/src/stores/session.js';import '/src/styles.css';
import * as render from '/src/labels/render.js';import * as print from '/src/labels/printing.js';import * as stock from '/src/labels/stock.js';import * as design from '/src/labels/design.js';
const pinia=createPinia(),session=useSessionStore(pinia),settingsView=new URLSearchParams(location.search).get('view')==='settings';session.user='labels@example.com';session.company='Esafe Retail';session.posProfile='Main';session.permissions={print_labels:true,settings:true,is_manager:true};session.offline=settingsView;session.settings.receipt_logo='';createApp(settingsView ? SettingsView : LabelsView).use(pinia).mount('#app');
window.labelTest={render,print,stock,design,session};window.print=()=>{window.printCalled=true};
</script></body></html>`
const server=await createServer({root,base:'/',server:{port:0,host:'127.0.0.1',open:false},plugins:[{name:'labels-test',configureServer(s){s.middlewares.use('/label-decoder.js',(req,res)=>{res.setHeader('Content-Type','text/javascript');res.end(readFileSync(decoder))});s.middlewares.use('/label-check.html',async(req,res)=>{res.setHeader('Content-Type','text/html');res.end(await s.transformIndexHtml('/label-check.html',html))})}}]})
await server.listen()
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--disable-gpu']})
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[],calls=[]
await page.route('https://fonts.googleapis.com/**',(route)=>route.abort())
await page.route('https://fonts.gstatic.com/**',(route)=>route.abort())
page.on('pageerror',(error)=>errors.push(error.message))
await page.addInitScript(()=>{
  window.print=()=>{window.printCalled=true}
  const key='esafepos-labels-v2:labels@example.com:Main'
  if(!localStorage.getItem(key))localStorage.setItem(key,JSON.stringify({version:2,printer:{route:'qz',name:'Old label printer',offsetX:4},presets:[{id:'legacy-printer',title:'Legacy printer setup',kind:'Printer',configuration:{printer:{route:'qz',name:'Old label printer',dpi:300,offsetX:4}}}]}))
})
page.on('websocket',(socket)=>{if(new URL(socket.url()).port!==String(server.httpServer.address().port))errors.push(`Unexpected printer connection: ${socket.url()}`)})
const row={item_code:'LP1',item_name:'Ceylon tea 200 g',barcode:'LP1',qty:1,uom:'Nos',price_with_tax:450,price:450,currency:'LKR',equivalents:[]}
await page.route('**/api/method/**',async(route)=>{
  const method=route.request().url().split('/').pop(),args=route.request().postDataJSON();calls.push({method,args})
  let message=[]
  if(method.endsWith('.workspace'))message={presets:[],can_manage:true,needs_migration:false,logo:''}
  else if(method.endsWith('.get_items'))message={items:[row]}
  else if(method.endsWith('.resolve_scan'))message={found:true,item:row}
  else if(method.endsWith('.items'))message={rows:[{...row,qty:args.items[0].qty}]}
  else if(method.endsWith('.prepare_job'))message={name:'JOB-1',snapshot:{rows:args.rows.map((r)=>({...row,...r})),configuration:args.configuration}}
  else if(method.endsWith('.job_result'))message={status:args.status}
  await route.fulfill({json:{message}})
})
try{
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/label-check.html`,{waitUntil:'domcontentloaded'})
  await page.getByRole('heading',{name:'Label printing',exact:true}).waitFor()
  await page.getByPlaceholder('Scan or search items…').fill('LP1');await page.getByPlaceholder('Scan or search items…').press('Enter')
  await page.locator('.queue-list li').waitFor()
  await page.locator('.copies input').fill('25')
  await page.getByRole('button',{name:/Triple/}).click()
  await page.getByRole('tab',{name:'Design',exact:true}).click()
  await page.getByRole('button',{name:'Barcode right',exact:true}).click()
  await page.getByLabel('Advanced',{exact:true}).check()
  await page.getByLabel('Selected element',{exact:true}).selectOption('barcode')
  await page.getByRole('tab',{name:'Stock',exact:true}).click()
  await page.getByLabel('Size preset',{exact:true}).selectOption('32x25')
  await page.getByRole('tab',{name:'Design',exact:true}).click()
  await page.getByRole('button',{name:'Classic',exact:true}).click()
  await page.getByText('Barcode settings',{exact:true}).click()
  await page.getByLabel(/narrowest bar width/i).fill('0.19')
  await page.getByRole('button',{name:'Roll',exact:true}).click()
  await page.screenshot({path:path.join(out,'labels-desktop.png'),fullPage:true})
  // Return to a fitting single-column configuration and check the complete output flow.
  await page.getByRole('tab',{name:'Stock',exact:true}).click();await page.getByRole('button',{name:/Single/}).click()
  await page.getByLabel('Size preset',{exact:true}).selectOption('58x40')
  await page.getByRole('tab',{name:'Design',exact:true}).click();await page.getByRole('button',{name:'Classic',exact:true}).click()
  await page.locator('.copies input').fill('2')
  const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'Download PDF',exact:true}).click()])
  await download.saveAs(path.join(out,'labels.pdf'))
  assert.ok(calls.some((c)=>c.method.endsWith('.prepare_job')))
  await page.getByRole('status').filter({hasText:'Label file downloaded.'}).waitFor()
  assert.ok(calls.some((c)=>c.method.endsWith('.job_result')&&c.args.status==='Exported'))
  // Verify that a rendered three-column row actually occupies all three columns.
  const pdfInfo=await page.evaluate(async()=>{
    const {stock,design,render,print}=window.labelTest,g=stock.geometry({...stock.DEFAULT_STOCK,w:38,h:25,columns:3,gapX:2}),r={item_code:'LP1',item_name:'Tea',barcode:'LP1',price_text:'450',qty:3},d={...design.designFor('minimal'),module:.19}
    const j=stock.layoutJob([r],g),svg=render.pageSvg(j.pages[0],g,d),url=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml'})),img=new Image();img.src=url;await img.decode()
    const canvas=document.createElement('canvas');canvas.width=Math.round(g.pageW*8);canvas.height=200;const ctx=canvas.getContext('2d');ctx.drawImage(img,0,0,canvas.width,canvas.height);URL.revokeObjectURL(url)
    const bands=[0,40,80].map((x)=>{const pixels=ctx.getImageData(Math.round((x+1)*8),40,Math.round(36*8),70).data;let n=0;for(let i=0;i<pixels.length;i+=4)if(pixels[i]<100)n++;return n})
    const pdf=await print.pdfDocument([svg],g,203.2),data=await pdf.text(),zpl=await (await print.nativeDocument([svg],g,{dpi:203.2},'zpl')).text(),tspl=new Uint8Array(await (await print.nativeDocument([svg],g,{dpi:203.2},'tspl')).arrayBuffer())
    const logo=await print.resizeLogo(new Blob(['<svg xmlns="http://www.w3.org/2000/svg" width="120" height="40"><rect width="120" height="40" fill="black"/></svg>'],{type:'image/svg+xml'}))
    const logoCheck=render.labelScene({...r,logo},{...stock.DEFAULT_STOCK},design.designFor('branded'))
    return {bands,pdfSize:pdf.size,valid:data.startsWith('%PDF-1.4'),mediaBox:data.match(/\/MediaBox \[([^\]]+)\]/)?.[1],width:g.pageW,zplValid:zpl.startsWith('^XA^PW') && zpl.endsWith('^XZ\n') && zpl.includes('^GFA,23600,23600,118,'),tsplValid:new TextDecoder().decode(tspl.slice(0,50)).startsWith('SIZE 118 mm,25 mm'),logoValid:logo.startsWith('data:image/png;base64,') && !logoCheck.errors.length}
  })
  assert.ok(pdfInfo.bands.every((n)=>n>200));assert.ok(pdfInfo.valid);assert.ok(pdfInfo.pdfSize>500)
  assert.ok(pdfInfo.zplValid);assert.ok(pdfInfo.tsplValid);assert.ok(pdfInfo.logoValid)
  assert.ok(Math.abs(+pdfInfo.mediaBox.split(' ')[2]-pdfInfo.width*72/25.4)<.001)
  await page.addScriptTag({url:'/label-decoder.js'})
  const decoded=await page.evaluate(async()=>{
    const {stock,design,render}=window.labelTest,results=[]
    for(const key of ['classic','barcode-right','barcode-left','rotated','qr']){
      const r={item_code:'LP1',barcode:'LP1',item_name:'Tea',price_text:'450'},svg=render.labelScene(r,stock.DEFAULT_STOCK,design.designFor(key)).svg
      const img=new Image(),url=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml'}));img.src=url;await img.decode()
      const canvas=document.createElement('canvas');canvas.width=key==='rotated' ? 320 : 464;canvas.height=key==='rotated' ? 464 : 320;const ctx=canvas.getContext('2d')
      if(key==='rotated'){ctx.translate(0,464);ctx.rotate(-Math.PI/2)}
      ctx.drawImage(img,0,0,464,320);URL.revokeObjectURL(url)
      const rgba=ctx.getImageData(0,0,canvas.width,canvas.height).data,gray=new Uint8ClampedArray(canvas.width*canvas.height)
      for(let i=0;i<gray.length;i++)gray[i]=rgba[i*4]
      const source=new ZXing.RGBLuminanceSource(gray,canvas.width,canvas.height),bitmap=new ZXing.BinaryBitmap(new ZXing.HybridBinarizer(source)),hints=new Map([[ZXing.DecodeHintType.TRY_HARDER,true]])
      try{results.push({key,value:new ZXing.MultiFormatReader().decode(bitmap,hints).getText()})}
      catch(error){
        if(key==='qr'){
          try{const pure=new ZXing.BinaryBitmap(new ZXing.HybridBinarizer(source.crop(0,0,220,320)));results.push({key,value:new ZXing.QRCodeReader().decode(pure,new Map([[ZXing.DecodeHintType.PURE_BARCODE,true]])).getText()});continue}catch(e){error=e}
        }
        results.push({key,error:error.message || error.constructor.name,png:canvas.toDataURL().split(',')[1]})
      }
    }
    return results
  })
  for(const r of decoded)if(r.png){await writeFile(path.join(out,`decode-${r.key}.png`),Buffer.from(r.png,'base64'));delete r.png}
  assert.equal(decoded.length,5);assert.ok(decoded.every((r)=>r.value==='LP1'),JSON.stringify(decoded))
  row.price_with_tax=475
  await page.getByRole('button',{name:'Download PDF',exact:true}).click()
  await page.getByRole('status').filter({hasText:'Item details or prices changed.'}).waitFor()
  assert.ok(calls.some((c)=>c.method.endsWith('.job_result')&&c.args.status==='Canceled'))
  await page.getByRole('tab',{name:'Saved',exact:true}).click()
  await page.getByRole('button',{name:/Legacy printer setup/}).click()
  await page.getByRole('tab',{name:'Printer',exact:true}).click()
  assert.equal(await page.getByLabel('Actual resolution (DPI)',{exact:true}).inputValue(),'300')
  assert.equal(await page.getByLabel(/^Horizontal offset/).inputValue(),'0')
  assert.equal(await page.getByLabel('Print with',{exact:true}).count(),0)
  assert.equal(await page.getByRole('button',{name:'Find label printers',exact:true}).count(),0)
  await page.screenshot({path:path.join(out,'label-printer-desktop.png'),fullPage:true})
  await page.setViewportSize({width:390,height:900})
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true)
  await page.screenshot({path:path.join(out,'label-printer-mobile.png'),fullPage:true})
  await page.setViewportSize({width:1600,height:1000})
  await page.getByRole('button',{name:'Print labels',exact:true}).click()
  await page.getByRole('status').filter({hasText:'Print window opened.'}).waitFor()
  assert.ok(calls.some((c)=>c.method.endsWith('.job_result')&&c.args.status==='Dialog opened'))
  assert.ok(calls.filter((c)=>c.method.endsWith('.prepare_job')).every((c)=>c.args.configuration.printer.route==='browser'&&c.args.configuration.printer.name===''))
  assert.ok(!calls.some((c)=>/qz|sign_request/.test(c.method)))
  // Device setups persist, while zoom is deliberately excluded from saved print geometry.
  await page.getByRole('tab',{name:'Saved',exact:true}).click();await page.getByLabel('Name',{exact:true}).fill('Tea setup');await page.getByRole('button',{name:'Save on this device',exact:true}).click()
  await page.reload();await page.getByRole('tab',{name:'Saved',exact:true}).click();await page.getByRole('button',{name:'Tea setup',exact:false}).waitFor()
  await page.getByPlaceholder('Scan or search items…').fill('LP1');await page.getByPlaceholder('Scan or search items…').press('Enter');await page.locator('.queue-list li').waitFor()
  for(const width of [1024,390]){
    await page.setViewportSize({width,height:900});await page.getByRole('tab',{name:'Stock',exact:true}).click()
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true)
    await page.screenshot({path:path.join(out,`labels-${width}.png`),fullPage:true})
  }
  await page.setViewportSize({width:1440,height:1000})
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/label-check.html?view=settings`)
  assert.equal(await page.getByRole('button',{name:'Receipt',exact:true}).count(),0)
  assert.equal(await page.locator('.qz-card').count(),0)
  assert.equal(await page.getByText(/QZ Tray/).count(),0)
  await page.screenshot({path:path.join(out,'receipt-settings-desktop.png'),fullPage:true})
  await page.setViewportSize({width:390,height:900})
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true)
  await page.screenshot({path:path.join(out,'receipt-settings-mobile.png'),fullPage:true})
  assert.deepEqual(errors,[])
  await writeFile(path.join(out,'verification.json'),JSON.stringify({pdfInfo,decoded,requests:calls.map((c)=>c.method),errors},null,2))
  console.log('PASS label workspace desktop/tablet/mobile, retired printer fallback, receipt Settings cleanup, copies, designs, editor, persisted setup, PDF workflow and three-column raster output')
}catch(error){console.error(error);process.exitCode=1}finally{await browser.close();server.httpServer?.closeAllConnections();await server.close()}
