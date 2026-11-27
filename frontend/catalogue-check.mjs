// Complete catalogue UI, image embedding, colour PDF and print tests. Synthetic data only.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const { chromium } = await import('./.label-test-tools/node_modules/playwright/index.mjs')
const root = path.dirname(fileURLToPath(import.meta.url)), out = path.resolve(root, '../artifacts/catalogue')
await mkdir(out, { recursive: true })
const fixture = `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0"><div id="app" style="height:100vh;display:flex"></div><script type="module">
import{createApp,h}from'vue';import{createPinia}from'pinia';import{createRouter,createMemoryHistory}from'vue-router';import PrintingView from'/src/views/PrintingView.vue';import{useSessionStore}from'/src/stores/session.js';import{cataloguePages,groupItems}from'/src/catalogue/document.js';import{cataloguePdf,loadImages,documentHtml}from'/src/catalogue/output.js';import'/src/styles.css';
const pinia=createPinia(),session=useSessionStore(pinia);session.user='synthetic';session.company='Synthetic shop';session.posProfile='Till A';session.availableProfiles=['Till A','Till B'];session.settings={enable_labels:false};session.permissions={settings:true,print_labels:false,print_catalogue:new URLSearchParams(location.search).get('denied')!=='1'};session.notify=()=>{};
const router=createRouter({history:createMemoryHistory(),routes:[{path:'/printing',component:PrintingView}]});await router.push('/printing?section=catalogue');await router.isReady();createApp({render:()=>h(PrintingView)}).use(pinia).use(router).mount('#app');window.test={session,cataloguePages,groupItems,cataloguePdf,loadImages,documentHtml};window.ready=true;
</script></body></html>`
const server = await createServer({ root, base: '/', server: { host: '127.0.0.1', port: 0 }, plugins: [{ name: 'catalogue-fixture', configureServer(s) { s.middlewares.use('/catalogue-check.html', async (req, res) => { res.setHeader('Content-Type', 'text/html'); res.end(await s.transformIndexHtml('/catalogue-check.html', fixture)) }) } }] })
await server.listen()
const browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true }), calls = [], errors = []
page.setDefaultTimeout(60000)
page.on('pageerror', error => errors.push(error.message))
await page.addInitScript(() => { window.print = () => { window.__cataloguePrinted = true }; Object.defineProperty(window, 'showSaveFilePicker', { value: undefined, configurable: true, writable: true }) })
await page.route('https://fonts.googleapis.com/**', route => route.abort())
const items = Array.from({ length: 235 }, (_, i) => ({ item_code: `CAT-${String(i).padStart(4, '0')}`, item_name: ['Arabica coffee', 'Ceylon tea தமிழ்', 'සිංහල Herbal blend', 'Seasonal pantry selection'][i % 4] + ' ' + i, category: i % 2 ? 'Drinks' : 'Pantry', brand: i % 3 ? 'Hill Country' : 'Coastal', uom: 'Nos', description: i === 234 ? ('Full description must continue without losing any words. '.repeat(150) + 'DESCRIPTION-END-MARKER') : 'A complete synthetic description, prepared for the catalogue printing check.', image: i === 3 ? '/catalogue-missing.png' : '/catalogue-image-' + (i % 3) + '.svg', price: i === 2 ? 0 : 450 + i, regular_price: 500 + i, unpriced: i === 2, offers: i % 5 ? [] : ['Automatic offer', 'Buy two (conditions apply)'] }))
let failAfter = null
await page.route('**/api/method/**', async route => {
  const method = route.request().url().split('/').pop(), args = route.request().postDataJSON() || {}; calls.push({ method, args })
  if (method === 'esafepos.api.print_catalogue.page') {
    if (failAfter !== null && args.after === failAfter) { failAfter = null; return route.fulfill({ status: 500, json: { exception: 'Synthetic page failure' } }) }
    const after = args.after || '', rows = items.filter(row => row.item_code > after).slice(0, 100), has_more = rows.at(-1)?.item_code !== items.at(-1).item_code
    return route.fulfill({ json: { message: { items: rows, has_more, next: has_more ? rows.at(-1).item_code : '', company: 'ESAFE SYNTHETIC STORE', outlet: args.pos_profile, currency: 'LKR', price_list: 'Retail', generated_at: '2026-11-27 12:00:00', pricing_engine: 'EsafePOS', price_note: 'One stock unit. Default outlet customer. Conditional offers may change checkout totals.' } } })
  }
  return route.fulfill({ json: { message: {} } })
})
await page.route('**/catalogue-image-*.svg', route => {
  const color = ['#d62e36', '#238668', '#285db5'][Number(route.request().url().match(/image-(\d)/)?.[1] || 0)]
  return route.fulfill({ contentType: 'image/svg+xml', body: `<svg xmlns="http://www.w3.org/2000/svg" width="180" height="180"><rect x="30" y="10" width="120" height="160" rx="12" fill="${color}"/><rect x="40" y="45" width="100" height="70" fill="white"/><text x="90" y="75" font-family="Arial" font-size="15" text-anchor="middle">SYNTHETIC</text><text x="90" y="96" font-family="Arial" font-size="15" text-anchor="middle">PRODUCT</text></svg>` })
})
await page.route('**/catalogue-missing.png', route => route.fulfill({ status: 404, body: '' }))
try {
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/catalogue-check.html`)
  await page.getByText('235 / 235 items selected', { exact: true }).waitFor()
  assert.equal(calls.filter(c => c.method.endsWith('print_catalogue.page')).length, 3, 'Load every API page')
  await page.getByRole('button', { name: 'Prepare complete document', exact: true }).click()
  await page.getByRole('button', { name: 'Export one PDF', exact: true }).waitFor({ state: 'visible' })
  await page.waitForFunction(() => !document.querySelector('.output-actions button:last-child').disabled)
  await page.getByText(/1 product images could not be loaded/).waitFor()
  const preview = page.frameLocator('iframe[title="Menu and catalogue preview"]')
  await preview.locator('svg').first().waitFor()
  const content = await preview.locator('body').evaluate(body => ({ html: body.innerHTML, count: body.querySelectorAll('svg').length, text: body.textContent, clipped: [...body.querySelectorAll('svg > text')].filter(el => { if (!el.textContent.trim()) return false; const b = el.getBBox(), svg = el.ownerSVGElement.viewBox.baseVal; return b.x < 10 || b.x + b.width > svg.width - 10 || b.y + b.height > svg.height - 3 }).map(el => el.textContent) }))
  assert.ok(content.count > 20)
  assert.ok(content.text.includes('DESCRIPTION-END-MARKER'))
  for (const row of items) assert.ok(content.text.includes(row.item_code), 'Missing item ' + row.item_code)
  assert.deepEqual(content.clipped, [])
  assert.ok(!/<image[^>]+href="https?:/i.test(content.html))
  await writeFile(path.join(out, 'all-items.html'), '<!doctype html><html><body>' + content.html + '</body></html>')
  await page.screenshot({ path: path.join(out, 'catalogue-desktop.png') })
  const download = page.waitForEvent('download', { timeout: 180000 })
  await page.getByRole('button', { name: 'Export one PDF', exact: true }).click()
  await (await download).saveAs(path.join(out, 'all-items.pdf'))
  await page.getByRole('button', { name: 'Print catalogue', exact: true }).click()
  await page.waitForFunction(() => document.querySelector('iframe[title="Menu and catalogue print"]')?.contentWindow.__cataloguePrinted)
  const printPages = await page.locator('iframe[title="Menu and catalogue print"]').evaluate(frame => frame.contentDocument.querySelectorAll('.page').length)
  assert.equal(printPages, content.count)
  await page.locator('iframe[title="Menu and catalogue print"]').evaluate(frame => frame.contentWindow.dispatchEvent(new Event('afterprint')))
  await page.getByLabel('Catalogue category', { exact: true }).selectOption('Drinks')
  assert.equal(await page.getByRole('button', { name: 'Export one PDF', exact: true }).isDisabled(), true, 'Changed filters invalidate the prepared document')
  await page.getByLabel('Catalogue brand', { exact: true }).selectOption('Hill Country')
  await page.getByLabel('Catalogue grouping', { exact: true }).selectOption('brand-category')
  await page.getByLabel('Catalogue layout', { exact: true }).selectOption('menu')
  await page.getByLabel('Catalogue paper', { exact: true }).selectOption('Letter')
  await page.getByRole('button', { name: 'Prepare complete document', exact: true }).click()
  await page.waitForFunction(() => !document.querySelector('.output-actions button:last-child').disabled)
  assert.equal(await preview.locator('svg').first().getAttribute('width'), '215.9mm')
  assert.ok(!(await preview.locator('body').textContent()).includes('Pantry'))
  await page.setViewportSize({ width: 390, height: 1000 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await page.screenshot({ path: path.join(out, 'catalogue-mobile.png') })
  await page.locator('.catalogue-preview').screenshot({ path: path.join(out, 'catalogue-mobile-preview.png') })
  failAfter = 'CAT-0099'
  await page.getByRole('button', { name: 'Refresh all items', exact: true }).click()
  await page.getByRole('alert').waitFor()
  assert.equal(await page.getByRole('button', { name: 'Prepare complete document', exact: true }).isDisabled(), true)
  assert.equal(await page.getByRole('button', { name: 'Export one PDF', exact: true }).isDisabled(), true)
  await page.getByText('100 / 100 items selected', { exact: true }).waitFor()
  const sample = await page.evaluate(async rows => {
    const assets = await test.loadImages(rows)
    const meta = {company:'ESAFE SYNTHETIC STORE',outlet:'Sample outlet',currency:'LKR',price_list:'Retail',generated_at:'2026-11-27 12:00:00',price_note:'Synthetic catalogue only. One stock unit. Offers subject to conditions.'}
    const doc = test.cataloguePages(rows,meta,{title:'Sample product catalogue',mode:'catalogue',paper:'A4',grouping:'category-brand',images:true,descriptions:true,discounts:true},assets.images)
    const pdf = await test.cataloguePdf(doc)
    const streamed=[]
    await test.cataloguePdf(doc,()=>{}, {write:async chunk=>streamed.push(chunk)})
    const streamedPdf=new Blob(streamed)
    const hash=async blob=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',await blob.arrayBuffer()))].join(',')
    const streamsMatch=(await hash(pdf))===(await hash(streamedPdf))
    const menu = test.cataloguePages(rows,meta,{title:'Sample menu',mode:'menu',paper:'Letter',grouping:'brand-category',images:true,descriptions:true,discounts:true},assets.images)
    const menuPdf = await test.cataloguePdf(menu)
    const currencyChecks={}
    for(const currency of ['KWD','JPY','USDT'])currencyChecks[currency]=test.cataloguePages([{...rows[0],price:12.3456,regular_price:12.3456}],{...meta,currency},{title:'Currency check',mode:'menu',paper:'A4',images:false,descriptions:false,discounts:false}).pages.join('')
    currencyChecks.micro=test.cataloguePages([{...rows[0],price:12.345,regular_price:12.347}],{...meta,currency:'KWD'},{title:'Discount check',mode:'menu',paper:'A4',images:false,descriptions:false,discounts:true}).pages.join('')
    const collisions=test.groupItems([{...rows[0],category:'A/B',brand:'C'},{...rows[1],category:'A',brand:'B/C'}]).length
    return {html:test.documentHtml(doc),pdf:[...new Uint8Array(await pdf.arrayBuffer())],menuPdf:[...new Uint8Array(await menuPdf.arrayBuffer())],currencyChecks,collisions,streamsMatch}
  }, items.slice(0,12))
  await writeFile(path.join(out,'sample-catalogue.pdf'),Buffer.from(sample.pdf))
  await writeFile(path.join(out,'sample-menu.pdf'),Buffer.from(sample.menuPdf))
  await writeFile(path.join(out,'sample-catalogue.html'),sample.html)
  assert.ok(sample.currencyChecks.KWD.includes('KWD 12.346'))
  assert.ok(sample.currencyChecks.JPY.includes('JPY 12'))
  assert.ok(sample.currencyChecks.USDT.includes('USDT 12.35'))
  assert.ok(sample.currencyChecks.micro.includes('Save KWD 0.002'))
  assert.equal(sample.collisions,2,'Category/brand labels containing slashes must not merge distinct groups')
  assert.ok(sample.streamsMatch,'Streaming and browser-download PDF bytes must match exactly')
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/catalogue-check.html?denied=1`)
  assert.equal(await page.getByRole('tab', { name: 'Menu & catalogue', exact: true }).count(), 0)
  assert.ok(calls.every(c => !/submit|payment|register_intent|save|print_receipt/.test(c.method)))
  assert.deepEqual(errors, [])
  await writeFile(path.join(out, 'result.json'), JSON.stringify({ itemCount: items.length, pageCount: content.count, pdf: 'all-items.pdf', backendPages: 3, physicalPrintPerformed: false, imagesInColour: true }, null, 2))
  console.log(`PASS ${items.length} items over all API pages, ${content.count} pages in one colour PDF, complete descriptions, images/placeholders, filters, grouping, A4/Letter, browser print, responsive UI and failure/permission guards`)
} catch (e) { console.error(e); await page.screenshot({ path: path.join(out, 'failure.png') }); console.error(errors); process.exitCode = 1 }
finally { await browser.close(); server.httpServer?.closeAllConnections(); await server.close() }
