// Verify the update lifecycle wired into the actual Vue App, with fixture stores.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const root = path.dirname(fileURLToPath(import.meta.url))
const output = process.env.UPDATE_ARTIFACTS
if (output) await mkdir(output, { recursive: true })
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>
<div id="app"></div><script type="module">
import { createApp, h } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import App from '/src/App.vue'
import { useSessionStore } from '/src/stores/session.js'
import { useCartStore } from '/src/stores/cart.js'
import { useCatalogStore } from '/src/stores/catalog.js'
import { useHelpStore } from '/src/stores/help.js'
import { printManager } from '/src/printing/index.js'
import '/src/styles.css'
window.esafepos_shell_revision = 'old'
const pinia = createPinia(), session = useSessionStore(pinia), cart = useCartStore(pinia), catalog = useCatalogStore(pinia)
session.bootstrap = async () => { session.loaded = true }
session.watchConnection = () => {}
session.loaded = true; session.user = 'Administrator'; session.company = 'Weerakoon Agro'
session.posProfile = 'Cashier 2'; session.registerSession = { name: 'REG-TEST' }
session.permissions = { is_manager: true }; session.settings = { enable_till_lock: 0 }
for (const method of ['fetch', 'cacheFullCatalog', 'cacheCustomers']) catalog[method] = async () => {}
useHelpStore(pinia).init = () => {}
printManager.resume = async () => {}
cart.lines = [{ item_code: 'POT', price: 195, qty: 1 }]
const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { render: () => h('p', 'A sale is in progress') } }] })
await router.push('/'); await router.isReady()
createApp(App).use(pinia).use(router).mount('#app')
window.cart = cart; window.ready = true
</script></body></html>`
const server = await createServer({ root, base: '/', server: { port: 0, host: '127.0.0.1', open: false },
  plugins: [{ name: 'update-layout-check', configureServer(server) {
    server.middlewares.use('/update-layout.html', async (req, res) => {
      res.setHeader('Content-Type', 'text/html')
      res.end(await server.transformIndexHtml('/update-layout.html', html))
    })
  } }],
})
await server.listen()
const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: 'chrome' }) })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', (error) => { errors.push(error.message); console.error(error.message) })
  await page.route('https://fonts.googleapis.com/**', (route) => route.abort())
  await page.route('**/api/method/**', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ message: { revision: 'new' } }) }))
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/update-layout.html`)
  await page.locator('.update-notice').waitFor()
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 })
    assert.equal(await page.evaluate(() => cart.lines.length), 1)
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    if (output) await page.screenshot({ path: path.join(output, `update-${width}.png`), fullPage: true })
  }
  let prepared = 0
  await page.route('**/pos', (route) => { prepared++; return route.fulfill({ contentType: 'text/html', body: 'window.esafepos_shell_revision = "new"' }) })
  await page.route('**/assets/esafepos/pos/pos.*?*', (route) => route.fulfill({ contentType: 'text/plain', body: '' }))
  // Observe the real App watch scheduling a safe reload when the basket clears.
  await Promise.all([page.waitForEvent('framenavigated', { predicate: (frame) => frame === page.mainFrame() }),
    page.evaluate(() => { cart.lines = [] })])
  assert.ok(prepared > 0)
  assert.deepEqual(errors, [])
  console.log('PASS real App update banner, desktop/mobile layout, retained basket and reload after sale clears')
} catch (error) {
  console.error(error)
  throw error
} finally {
  await browser.close()
  await Promise.race([server.close(), new Promise((resolve) => setTimeout(resolve, 3000))])
}
