// Browser-origin storage. SDK identity/private keys stay in the SDK's own database.
const DATABASE = 'esafepos-printing'
let opened
function database() {
  if (!opened) opened = new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1)
    request.onupgradeneeded = () => {
      request.result.createObjectStore('settings')
      const intents = request.result.createObjectStore('intents', { keyPath: 'key' })
      intents.createIndex('createdAt', 'createdAt')
    }
    request.onsuccess = () => { request.result.onversionchange = () => { request.result.close(); opened = null }; resolve(request.result) }
    request.onerror = () => { opened = null; reject(request.error) }
  })
  return opened
}
async function transaction(store, mode, action) {
  const db = await database()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, mode)
    let result
    try { const request = action(tx.objectStore(store)); request.onsuccess = () => { result = request.result }; request.onerror = () => reject(request.error) }
    catch (error) { tx.abort(); reject(error) }
    tx.oncomplete = () => resolve(result)
    tx.onerror = () => reject(tx.error)
    tx.onabort = () => reject(tx.error || new Error('Print storage transaction aborted'))
  })
}
export const printJournal = {
  setting: (key) => transaction('settings', 'readonly', (s) => s.get(key)),
  saveSetting: (key, value) => transaction('settings', 'readwrite', (s) => s.put(value, key)),
  settings: () => transaction('settings', 'readonly', (s) => s.getAll()),
  get: (key) => transaction('intents', 'readonly', (s) => s.get(key)),
  put: (value) => transaction('intents', 'readwrite', (s) => s.put(value)),
  list: () => transaction('intents', 'readonly', (s) => s.getAll()),
}
export async function workstationId() {
  // A Web Lock protects first initialization across tabs, just like dispatch.
  if (!navigator.locks) throw new Error('Silent printing needs a browser with Web Locks support. Use current Chrome or Edge.')
  return navigator.locks.request('esafepos-print-workstation', async () => {
    let id = await printJournal.setting('workstation')
    if (!id) { id = crypto.randomUUID(); await printJournal.saveSetting('workstation', id) }
    return id
  })
}
