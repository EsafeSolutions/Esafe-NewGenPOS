// Exercise actual service-worker caches and multiple open POS windows.
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import { once } from 'node:events'

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const updaterSource = await readFile(new URL('./src/appUpdates.js', import.meta.url), 'utf8')
const workerSource = await readFile(new URL('./public/sw.js', import.meta.url), 'utf8')
let revision = '0.69.5-build-one'
let assetsReady = true
const server = createServer((req, res) => {
  res.setHeader('Cache-Control', 'no-store')
  if (req.url === '/revision') {
    res.setHeader('Content-Type', 'application/json')
    return res.end(JSON.stringify({ revision }))
  }
  if (req.url.startsWith('/sw.js')) {
    res.setHeader('Content-Type', 'text/javascript')
    res.setHeader('Service-Worker-Allowed', '/pos')
    return res.end(workerSource)
  }
  if (req.url === '/appUpdates.js') {
    res.setHeader('Content-Type', 'text/javascript')
    return res.end(updaterSource)
  }
  if (req.url.startsWith('/assets/esafepos/pos/pos.js')) {
    res.setHeader('Content-Type', 'text/javascript')
    res.statusCode = assetsReady ? 200 : 503
    return res.end(`window.loadedAssetRevision = '${revision}'`)
  }
  if (req.url.startsWith('/assets/esafepos/pos/pos.css')) {
    res.setHeader('Content-Type', 'text/css')
    return res.end('body { background: white }')
  }
  if (req.url.split('?')[0] === '/pos') {
    res.setHeader('Content-Type', 'text/html')
    return res.end(`<!doctype html><html><head><title>Update fixture</title>
      <link rel="stylesheet" href="/assets/esafepos/pos/pos.css?v=${revision}"></head><body>
      <div id="revision">${revision}</div><script>window.esafepos_shell_revision = "${revision}";</script>
      <script src="/assets/esafepos/pos/pos.js?v=${revision}"></script><script type="module">
      import { startAppUpdates } from '/appUpdates.js'
      window.busy = false; window.pending = false
      await navigator.serviceWorker.register('/sw.js?v=${revision}', { scope: '/pos', updateViaCache: 'none' })
      await navigator.serviceWorker.ready
      window.updater = startAppUpdates({ currentRevision: window.esafepos_shell_revision, interval: 1000000,
        readRevision: () => fetch('/revision').then((r) => r.json()),
        canReload: () => !window.busy, onPending: (value) => { window.pending = value } })
      window.ready = true
      </script></body></html>`)
  }
  res.statusCode = 404
  res.end()
})
server.listen(0, '127.0.0.1')
await once(server, 'listening')
const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: 'chrome' }) })
try {
  const context = await browser.newContext()
  const first = await context.newPage()
  const second = await context.newPage()
  const url = `http://127.0.0.1:${server.address().port}/pos`
  for (const page of [first, second]) {
    await page.goto(url)
    await page.waitForFunction(() => window.ready)
  }
  await first.evaluate(() => { busy = true })
  revision = '0.69.5-build-two'
  await first.evaluate(() => updater.check())
  assert.equal(await first.evaluate(() => pending), true)
  assert.equal(await first.evaluate(() => esafepos_shell_revision), '0.69.5-build-one')
  await second.evaluate(() => updater.check())
  await second.waitForFunction((value) => window.ready && window.esafepos_shell_revision === value, revision)
  assert.equal(await second.evaluate(() => loadedAssetRevision), revision)
  await first.evaluate(() => { busy = false; updater.check() })
  await first.waitForFunction((value) => window.ready && window.esafepos_shell_revision === value, revision)
  assert.equal(await first.evaluate(() => loadedAssetRevision), revision)
  console.log('PASS both open POS windows receive same-release update; active transaction defers reload')

  revision = '0.69.5-build-three'
  assetsReady = false
  await second.evaluate(() => updater.check())
  assert.equal(await second.evaluate(() => esafepos_shell_revision), '0.69.5-build-two')
  assetsReady = true
  await second.evaluate(() => updater.check())
  await second.waitForFunction((value) => window.ready && window.esafepos_shell_revision === value, revision)
  await second.waitForFunction((value) => navigator.serviceWorker.controller?.scriptURL.includes(value), revision)
  const caches = await second.evaluate(() => window.caches.keys())
  assert.deepEqual(caches.filter((name) => name.startsWith('esafepos-shell-')), ['esafepos-shell-' + revision])
  console.log('PASS incomplete deployment retries and obsolete shell caches are replaced')

  await context.setOffline(true)
  await second.reload()
  await second.locator('#revision').waitFor()
  assert.equal(await second.locator('#revision').textContent(), revision)
  assert.equal(await second.evaluate(() => loadedAssetRevision), revision)
  console.log('PASS updated installed shell reopens offline with matching JavaScript')
  await context.close()
} finally {
  await browser.close()
  await new Promise((resolve) => server.close(resolve))
}
