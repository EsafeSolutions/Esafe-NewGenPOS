// Actual Features editor, product tiles and IndexedDB; simulated APIs only.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || './.label-test-tools/node_modules/playwright/index.mjs')
const root = path.dirname(fileURLToPath(import.meta.url)), output = path.join(root, '../docs/screenshots/stock-totals')
await mkdir(output, { recursive: true })
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>#app{display:flex;flex-direction:column;padding:16px;height:100vh;box-sizing:border-box}h1{font-size:20px}</style></head><body><div id="app"></div><script type="module">
import { createApp, h } from 'vue'; import { createPinia } from 'pinia'; import { createRouter, createWebHashHistory, RouterView } from 'vue-router';
import ProductGrid from '/src/components/ProductGrid.vue'; import SettingsView from '/src/views/SettingsView.vue'; import { useSessionStore } from '/src/stores/session.js'; import { useCatalogStore } from '/src/stores/catalog.js'; import * as offline from '/src/offline.js'; import { call } from '/src/api.js'; import '/src/styles.css';
const pinia = createPinia(), session = useSessionStore(pinia), catalog = useCatalogStore(pinia);
session.user = 'cashier@example.com'; session.posProfile = 'SHOWROOM'; session.company = 'Shop'; session.permissions = {settings:true,is_manager:true}; session.settings.show_out_of_stock = 1; window.notices = []; session.notify = text => window.notices.push(text);
session.bootstrap = async () => { const settings = await call('esafepos.api.settings.get_settings'); session.settings.enable_item_stock_totals = settings.enable_item_stock_totals };
const item = (item_code, item_name, actual_qty, total_stock_qty) => ({item_code,item_name,actual_qty,total_stock_qty,total_stock_scope:[session.user,session.posProfile,session.company],total_stock_includes_register:true,stock_uom:'PCS',is_stock_item:true,price:345});
catalog.items = [item('JLD85122','22mm drive socket',46,157),item('JLD85324','24mm deep socket',0,63),{...item('OTHER','Older cached scope',5,9999),total_stock_scope:['other@example.com','OTHER']}];
const dashboard = { render: () => h('section', {style:'display:flex;flex-direction:column;min-height:0'}, [h('h1','Sell'), h(ProductGrid,{onSelect:item => window.selected = JSON.parse(JSON.stringify(item))})]) };
const router = createRouter({history:createWebHashHistory(),routes:[{path:'/',component:dashboard},{path:'/settings',component:SettingsView}]}); window.test = {session,catalog,offline,router}; createApp({render:()=>h(RouterView)}).use(pinia).use(router).mount('#app');
</script></body></html>`
const server = await createServer({root,base:'/',server:{host:'127.0.0.1',port:0,open:false,hmr:false},plugins:[{name:'stock-totals-check',configureServer(s){s.middlewares.use('/stock-totals-check.html',async(req,res)=>{res.setHeader('Content-Type','text/html');res.end(await s.transformIndexHtml('/stock-totals-check.html',html))})}}]})
await server.listen()
const browser = await chromium.launch({executablePath:process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true})
const page = await browser.newPage({viewport:{width:1200,height:900}}), errors = [], calls = []
page.on('pageerror', error => errors.push(error.message))
await page.route('https://fonts.googleapis.com/**', route => route.abort())
await page.route('https://fonts.gstatic.com/**', route => route.abort())
let settings = { enable_item_stock_totals:0,show_out_of_stock:1,companies:[],pos_profiles:[],company_settings:[] }
await page.route('**/api/method/**', async route => {
  const method = route.request().url().split('/').pop(), args = route.request().postDataJSON(); calls.push({method,args})
  let message = []
  if (method.endsWith('get_settings')) message = settings
  else if (method.endsWith('save_settings')) { settings = {...settings,...args.payload}; message = settings }
  else if (method.endsWith('get_access_management')) message = { users:[],levels:[],capabilities:[],presets:{},profiles:[],assignments:[] }
  else if (method.endsWith('inter_company.status')) message = {pending:[],recent:[]}
  else if (method.endsWith('get_index_health')) message = {tables:[]}
  else if (method.endsWith('get_messaging_settings')) message = {config:{},roles:[],whatsapp:{}}
  await route.fulfill({json:{message}})
})
try {
  await page.goto(server.resolvedUrls.local[0] + 'stock-totals-check.html#/')
  await page.getByText('46 in stock',{exact:true}).waitFor()
  assert.equal(await page.getByText('157 total in stock',{exact:true}).count(),0)
  await page.evaluate(() => window.test.router.push('/settings'))
  await page.getByRole('button',{name:'Features',exact:true}).click()
  const toggle = page.getByRole('checkbox',{name:/Show total stock on POS dashboard/})
  assert.equal(await toggle.isChecked(),false)
  await toggle.check()
  await toggle.locator('..').screenshot({path:path.join(output,'features-desktop.png')})
  await page.getByRole('button',{name:'Save Settings',exact:true}).click()
  await page.waitForFunction(() => window.notices.includes('Settings saved'))
  assert.equal(calls.findLast(call => call.method.endsWith('save_settings')).args.payload.enable_item_stock_totals,1)
  await page.evaluate(() => window.test.router.push('/'))
  await page.getByText('157 total in stock',{exact:true}).waitFor()
  assert.equal(await page.getByText('63 total in stock',{exact:true}).count(),1)
  assert.equal(await page.getByText('9999 total in stock',{exact:true}).count(),0)
  assert.equal(await page.getByText('5 in stock',{exact:true}).count(),1)
  assert.equal(await page.getByText('157 total in stock',{exact:true}).getAttribute('title'),'46 at this register')
  await page.getByRole('button',{name:'Add 22mm drive socket to cart',exact:true}).click()
  assert.equal(await page.evaluate(() => window.selected.actual_qty),46)
  await page.screenshot({path:path.join(output,'dashboard-desktop.png'),fullPage:true})
  await page.setViewportSize({width:390,height:844})
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),true)
  await page.screenshot({path:path.join(output,'dashboard-mobile.png'),fullPage:true})
  const cache = await page.evaluate(async () => {
    const {catalog,offline} = window.test
    await offline.saveCatalog(JSON.parse(JSON.stringify(catalog.items)))
    catalog.applyStock({'JLD85122':44})
    await offline.patchCatalogStock({'JLD85122':44})
    catalog.applyStockDelta([{item_code:'JLD85122',qty:3}])
    await new Promise(resolve => setTimeout(resolve,0))
    return (await offline.getCatalogItems(['JLD85122']))[0]
  })
  // Repeated authoritative levels do not subtract twice; offline sale updates both quantities.
  assert.equal(cache.actual_qty,41); assert.equal(cache.total_stock_qty,152)
  await page.getByText('152 total in stock',{exact:true}).waitFor()
  await page.evaluate(() => { window.test.session.settings.show_out_of_stock = 0 })
  assert.equal(await page.getByText('63 total in stock',{exact:true}).count(),0)
  await page.evaluate(() => window.test.router.push('/settings'))
  await page.getByRole('button',{name:'Features',exact:true}).click()
  assert.equal(await toggle.isChecked(),true)
  await toggle.uncheck()
  await page.getByRole('button',{name:'Save Settings',exact:true}).click()
  await page.waitForFunction(() => window.notices.filter(text => text === 'Settings saved').length === 2)
  await page.evaluate(() => window.test.router.push('/'))
  await page.getByText('41 in stock',{exact:true}).waitFor()
  assert.equal(await page.getByText('152 total in stock',{exact:true}).count(),0)
  assert.deepEqual(errors,[])
  console.log('Stock total checks passed: Features save/reload/on/off, dashboard total and register separation, user/profile cache scope, live/offline/IndexedDB updates, stock filtering and desktop/mobile layouts.')
} catch (error) {
  console.error({errors,calls:calls.slice(-5),body:(await page.locator('body').innerText()).slice(0,2500)})
  await page.screenshot({path:path.join(output,'failure.png'),fullPage:true})
  throw error
} finally {await browser.close();await server.close()}
