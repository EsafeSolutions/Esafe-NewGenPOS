// Workstation customer-screen preferences and safe media/link handling.
export const DISPLAY_MODES = [
  { value: 'live', label: 'Live sale', icon: 'list' },
  { value: 'closed', label: 'Counter closed', icon: 'ban' },
  { value: 'bank', label: 'Bank details', icon: 'bank' },
  { value: 'adverts', label: 'Adverts', icon: 'image' },
  { value: 'social', label: 'Social QR codes', icon: 'globe' },
  { value: 'message', label: 'Custom message', icon: 'detail' },
]
const modes = new Set(DISPLAY_MODES.map(row => row.value))
const text = (value, length) => String(value || '').trim().slice(0, length)
export const LOCAL_MEDIA_LIMIT = 100 * 1024 * 1024
export const LOCAL_MEDIA_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp', 'image/gif', 'video/mp4', 'video/webm', 'video/ogg'])

export function publicDisplayUrl(value) {
  try {
    const url = new URL(String(value || '').trim())
    return url.protocol === 'https:' && !url.username && !url.password ? url.href : ''
  } catch { return '' }
}

export function advertSource(value) {
  const source = publicDisplayUrl(value)
  if (!source) return null
  const url = new URL(source), host = url.hostname.replace(/^www\./, '')
  let id = ''
  if (host === 'youtu.be') id = url.pathname.slice(1)
  if (['youtube.com', 'm.youtube.com', 'youtube-nocookie.com'].includes(host)) {
    id = url.searchParams.get('v') || url.pathname.match(/^\/(?:embed|shorts|live)\/([^/]+)/)?.[1] || ''
  }
  if (/^[\w-]{11}$/.test(id)) return { type: 'embed', source: `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&mute=1&loop=1&playlist=${id}&playsinline=1&rel=0` }
  if (['tiktok.com', 'm.tiktok.com'].includes(host)) {
    const post = url.pathname.match(/\/(?:video|player\/v1)\/(\d+)/)?.[1]
    if (post) return { type: 'embed', source: `https://www.tiktok.com/player/v1/${post}?autoplay=1&muted=1&loop=1` }
  }
  if (/\.(mp4|webm|ogv|ogg)$/i.test(url.pathname)) return { type: 'video', source }
  if (/\.(png|jpe?g|webp|gif)$/i.test(url.pathname)) return { type: 'image', source }
  return null
}

export function normalizePresentation(value = {}) {
  if (!value || typeof value !== 'object') value = {}
  const defaultMode = modes.has(value.defaultMode) ? value.defaultMode : 'live'
  return {
    defaultMode,
    mode: modes.has(value.mode) ? value.mode : defaultMode,
    followSale: value.followSale !== false,
    screen: text(value.screen, 200),
    closedMessage: text(value.closedMessage, 500),
    messageTitle: text(value.messageTitle, 160),
    messageBody: text(value.messageBody, 1500),
    interval: Math.max(5, Math.min(300, Number(value.interval) || 15)),
    adverts: (Array.isArray(value.adverts) ? value.adverts : []).slice(0, 20).flatMap(row => {
      if (!row || typeof row !== 'object') return []
      const localId = /^[\w-]{1,100}$/.test(row.localId || '') ? row.localId : ''
      const remote = advertSource(row.url)
      if (!localId && !remote) return []
      return [{ id: text(row.id || localId || remote?.source, 300), title: text(row.title, 160),
        ...(localId ? { localId, type: row.type === 'video' ? 'video' : 'image' } : { url: publicDisplayUrl(row.url) }) }]
    }),
    social: (Array.isArray(value.social) ? value.social : []).slice(0, 12).flatMap(row => {
      if (!row || typeof row !== 'object') return []
      const url = publicDisplayUrl(row.url)
      // Stay within QR capacity including UTF-8 links.
      return url && new TextEncoder().encode(url).length <= 1500 ? [{ label: text(row.label, 80) || new URL(url).hostname, url }] : []
    }),
  }
}

export function presentationKey(profile) { return 'esafepos-display-content:' + encodeURIComponent(profile || '') }
export function loadPresentation(profile) {
  try {
    const saved = normalizePresentation(JSON.parse(localStorage.getItem(presentationKey(profile)) || '{}'))
    return { ...saved, mode: saved.defaultMode }
  } catch { return normalizePresentation() }
}

export function targetDisplay(screens, current, preference = '') {
  return screens.find(screen => preference && screen.label === preference) ||
    screens.find(screen => screen !== current) || screens[0]
}

let database
function mediaDatabase() {
  if (!database) database = new Promise((resolve, reject) => {
    const request = indexedDB.open('esafepos-display-media', 1)
    request.onupgradeneeded = () => request.result.createObjectStore('media')
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => { database = null; reject(request.error) }
  })
  return database
}
export async function displayMedia(operation, id, file) {
  const db = await mediaDatabase()
  return new Promise((resolve, reject) => {
    const transaction = db.transaction('media', operation === 'get' ? 'readonly' : 'readwrite')
    const store = transaction.objectStore('media')
    const request = operation === 'put' ? store.put(file, id) : operation === 'delete' ? store.delete(id) : store.get(id)
    transaction.oncomplete = () => resolve(request.result)
    transaction.onabort = transaction.onerror = () => reject(transaction.error || new Error('Local media storage is unavailable.'))
  })
}
