// Uses the isolated Playwright/ZXing tools documented in label-browser-check.mjs.
import assert from 'node:assert/strict'
import { mkdir,readFile,writeFile } from 'node:fs/promises'
import { readFileSync } from 'node:fs'
import { inflateSync } from 'node:zlib'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { createServer } from 'vite'
const require=createRequire(import.meta.url)
const {chromium}=await import('playwright').catch(()=>import('./.label-test-tools/node_modules/playwright/index.mjs'))
const root=path.dirname(fileURLToPath(import.meta.url)),out=path.join(root,'../artifacts/labels/compact')
let decoder
try{decoder=require.resolve('@zxing/library/umd/index.min.js')}catch{decoder=new URL('./.label-test-tools/node_modules/@zxing/library/umd/index.min.js',import.meta.url)}
await mkdir(out,{recursive:true})
const html=`<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body><div id="app"></div><script type="module">
import {createApp} from 'vue';import {createPinia} from 'pinia';import LabelsView from '/src/views/LabelsView.vue';import {useSessionStore} from '/src/stores/session.js';import '/src/styles.css';
import * as render from '/src/labels/render.js';import * as symbols from '/src/labels/symbols.js';import * as stock from '/src/labels/stock.js';import * as design from '/src/labels/design.js';
const pinia=createPinia(),s=useSessionStore(pinia);s.user='compact@example.com';s.company='Weerakoon Agro';s.posProfile='Main';s.permissions={print_labels:true};s.settings={receipt_logo:'',esafe_printing:{silent:false}};createApp(LabelsView).use(pinia).mount('#app');window.compactTest={render,symbols,stock,design};
</script></body></html>`
const server=await createServer({root,base:'/',server:{port:0,host:'127.0.0.1',open:false},plugins:[{name:'compact-test',configureServer(s){
  s.middlewares.use('/compact-decoder.js',(req,res)=>{res.setHeader('Content-Type','text/javascript');res.end(readFileSync(decoder))})
  s.middlewares.use('/compact-check.html',async(req,res)=>{res.setHeader('Content-Type','text/html');res.end(await s.transformIndexHtml('/compact-check.html',html))})
}}]})
await server.listen()
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true})
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[],calls=[]
page.on('pageerror',(e)=>errors.push(e.message))
await page.route('https://fonts.googleapis.com/**',(r)=>r.abort())
await page.route('https://fonts.gstatic.com/**',(r)=>r.abort())
const row={item_code:'O1D34340021',barcode:'O1D34340021',item_name:'Albertis solution (UPL) 200g',qty:1,uom:'Nos',price:510,price_with_tax:510,currency:'LKR',equivalents:[]}
await page.route('**/api/method/**',async(route)=>{
  const method=route.request().url().split('/').pop(),args=route.request().postDataJSON();calls.push({method,args});let message=[]
  if(method.endsWith('.workspace'))message={presets:[],can_manage:true,needs_migration:false,logo:''}
  else if(method.endsWith('.resolve_scan'))message={found:true,item:row}
  else if(method.endsWith('.items'))message={rows:[row]}
  else if(method.endsWith('.prepare_job'))message={name:'COMPACT-1',snapshot:{rows:[row],configuration:args.configuration}}
  else if(method.endsWith('.job_result'))message={status:args.status}
  await route.fulfill({json:{message}})
})
try{
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/compact-check.html`,{waitUntil:'domcontentloaded'})
  await page.getByPlaceholder('Scan or search items…').fill(row.barcode);await page.getByPlaceholder('Scan or search items…').press('Enter');await page.locator('.queue-list li').waitFor()
  await page.getByLabel('Size preset',{exact:true}).selectOption('38x25')
  await page.getByRole('tab',{name:'Design',exact:true}).click();await page.getByText('Barcode settings',{exact:true}).click()
  await page.getByLabel('Automatically fit barcode to its box',{exact:true}).uncheck()
  await page.getByRole('alert').filter({hasText:'53.625 mm'}).waitFor()
  await page.getByRole('button',{name:'Make barcode fit',exact:true}).click()
  assert.equal(await page.getByRole('alert').count(),0)
  assert.ok(await page.locator('.barcode-tools').innerText().then(t=>t.includes('35.75 mm')))
  await page.screenshot({path:path.join(out,'code128-desktop.png'),fullPage:true})
  await page.getByRole('button',{name:'Use Data Matrix',exact:true}).click()
  assert.equal(await page.getByRole('alert').count(),0)
  assert.ok(await page.locator('.warning').innerText().then(t=>t.includes('2D scanner')))
  const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'Download PDF',exact:true}).click()])
  const pdfPath=path.join(out,'data-matrix-38x25.pdf');await download.saveAs(pdfPath)
  const prepared=calls.find(c=>c.method.endsWith('.prepare_job')).args
  assert.equal(prepared.rows[0].barcode,row.barcode);assert.equal(prepared.configuration.design.barcodeFormat,'DATAMATRIX')
  await page.screenshot({path:path.join(out,'data-matrix-desktop.png'),fullPage:true})
  await page.addScriptTag({url:'/compact-decoder.js'})
  const results=await page.evaluate(async()=>{
    const {render,stock,design}=window.compactTest,rows=[]
    window.decodeCompact=(pixels,width,height,format)=>{
      const source=new ZXing.RGBLuminanceSource(new Uint8ClampedArray(pixels),width,height)
      const cropped=source.crop(0,Math.floor(height*.435),width,Math.floor(height*.44))
      const bitmap=new ZXing.BinaryBitmap(new ZXing.HybridBinarizer(cropped)),hints=new Map([[ZXing.DecodeHintType.TRY_HARDER,true]])
      if(format==='QRCODE')hints.set(ZXing.DecodeHintType.PURE_BARCODE,true)
      return (format==='DATAMATRIX' ? new ZXing.DataMatrixReader() : format==='QRCODE' ? new ZXing.QRCodeReader() : new ZXing.MultiFormatReader()).decode(bitmap,hints).getText()
    }
    for(const value of ['O1D34340021','01D34340021'])for(const format of ['CODE128','CODE93','DATAMATRIX','QRCODE']){
      const labelWidth=format==='CODE93' ? 50 : 38,canvasWidth=labelWidth*8
      const r={item_code:value,barcode:value,item_name:'Albertis solution (UPL) 200g',price_text:'LKR 510.00'},d={...design.designFor('classic'),barcodeFormat:format},scene=render.labelScene(r,{...stock.DEFAULT_STOCK,w:labelWidth,h:25},d)
      if(scene.errors.length)throw Error(scene.errors.join('; '))
      const image=new Image(),url=URL.createObjectURL(new Blob([scene.svg],{type:'image/svg+xml'}));image.src=url;await image.decode()
      const canvas=document.createElement('canvas');canvas.width=canvasWidth;canvas.height=200;const ctx=canvas.getContext('2d');ctx.drawImage(image,0,0,canvasWidth,200);URL.revokeObjectURL(url)
      const rgba=ctx.getImageData(0,0,canvasWidth,200).data,gray=new Uint8ClampedArray(canvasWidth*200);for(let i=0;i<gray.length;i++)gray[i]=rgba[i*4]
      try{rows.push({value,format,labelWidth,decoded:window.decodeCompact(gray,canvasWidth,200,format)})}
      catch(error){rows.push({value,format,error:error.message || error.constructor.name,png:canvas.toDataURL().split(',')[1]})}
    }
    return rows
  })
  for(const r of results)if(r.png){await writeFile(path.join(out,`failed-${r.format}-${r.value}.png`),Buffer.from(r.png,'base64'));delete r.png}
  assert.ok(results.every(r=>r.decoded===r.value),JSON.stringify(results))
  // Read the exported PDF's lossless grayscale image, then decode those exact pixels.
  const pdf=await readFile(pdfPath),latin=pdf.toString('latin1'),header=latin.match(/\/Subtype \/Image \/Width (\d+) \/Height (\d+)[\s\S]*?\/Length (\d+) >>\nstream\n/)
  assert.ok(header);const start=header.index+header[0].length,pixels=inflateSync(pdf.subarray(start,start+ +header[3]))
  assert.equal(pixels.length,+header[1]* +header[2])
  const pdfValue=await page.evaluate(({pixels,width,height})=>window.decodeCompact(pixels,width,height,'DATAMATRIX'),{pixels:[...pixels],width:+header[1],height:+header[2]})
  assert.equal(pdfValue,row.barcode)
  await page.evaluate(()=>{
    const {render,symbols,stock,design}=window.compactTest,host=document.createElement('div')
    host.id='compact-comparison';host.style.cssText='position:absolute;left:0;top:0;z-index:10000;padding:24px;background:#fff;color:#25334a;font:14px Arial;width:max-content'
    host.innerHTML='<h2 style="margin:0 0 8px;font-size:21px">One code. Three label formats.</h2><p style="margin:0 0 20px;color:#68778d">O1D34340021 · 38 × 25 mm label · 203.2 DPI · full value preserved</p>'
    const cards=document.createElement('div');cards.style.cssText='display:flex;gap:20px'
    for(const [format,title] of [['CODE128','Code 128'],['DATAMATRIX','Data Matrix'],['QRCODE','QR Code']]){
      const d={...design.designFor('classic'),barcodeFormat:format,module:format==='CODE128' ? .33 : .25},r={item_code:'O1D34340021',barcode:'O1D34340021',item_name:'Albertis solution (UPL) 200g',price_text:'LKR 510.00'},s={...stock.DEFAULT_STOCK,w:38,h:25}
      const m=symbols.barcodeMetrics(r.barcode,d,stock.DEFAULT_PRINTER,{w:37,h:10.848}),card=document.createElement('div')
      card.style.cssText='width:328px;border:1px solid #dfe8eb;border-radius:8px;padding:12px'
      card.innerHTML='<strong>'+title+'</strong><p style="font-size:12px;color:#68778d;margin:6px 0 14px">'+m.width.toFixed(2)+' mm'+(m.matrix ? ' × '+m.height.toFixed(2)+' mm' : ' wide')+'</p><div style="width:304px;height:200px">'+render.labelScene(r,s,d).svg.replace('width="38mm" height="25mm"','width="304" height="200"')+'</div><p style="font-size:12px;color:#68778d;margin:12px 0 0">'+(m.matrix ? '2D scanner required' : 'Standard barcode scanner')+'</p>'
      cards.appendChild(card)
    }
    host.appendChild(cards);document.body.appendChild(host)
  })
  await page.locator('#compact-comparison').screenshot({path:path.join(out,'comparison.png')})
  await page.locator('#compact-comparison').evaluate(el=>el.remove())
  await page.setViewportSize({width:390,height:900});await page.getByRole('tab',{name:'Stock',exact:true}).click()
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true)
  await page.screenshot({path:path.join(out,'data-matrix-mobile.png'),fullPage:true})
  assert.deepEqual(errors,[])
  await writeFile(path.join(out,'verification.json'),JSON.stringify({results,pdfValue,errors},null,2))
  console.log('PASS 38×25 mm recovery, 8 independently decoded compact symbols, exact exported PDF decoding, scanner guidance and desktop/mobile layouts')
}finally{await browser.close();server.httpServer?.closeAllConnections();await server.close()}
