import { createReceiptPrintFrame } from '../receiptPrint'

const PROPERTIES = ['display','position','box-sizing','width','max-width','min-width','height','font-size','font-weight','font-style','font-variant-numeric','text-transform','text-decoration','line-height','text-align','white-space','word-break','overflow-wrap','letter-spacing','direction','color','background-color','padding','margin','border-top','border-right','border-bottom','border-left','border-collapse','border-spacing','border-radius','table-layout','vertical-align','flex','flex-direction','flex-wrap','justify-content','align-items','gap','grid-template-columns','grid-column','break-inside','page-break-inside','object-fit','opacity']
async function embeddedImage(url) {
  if (url.startsWith('data:')) return url
  const target = new URL(url, location.href)
  if (!['https:', 'http:'].includes(target.protocol)) throw new Error('The print image URL is not supported.')
  const response = await fetch(target.href, { credentials: target.origin === location.origin ? 'same-origin' : 'omit' })
  if (!response.ok) throw new Error('A print image could not be embedded. Check the logo or custom image.')
  const blob = await response.blob()
  if (blob.size > 5 * 1024 * 1024 || !/^image\/(png|jpeg|webp|svg\+xml)$/.test(blob.type)) throw new Error('Use a supported image smaller than 5 MiB.')
  return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(blob) })
}
export async function selfContainedHtml(source, { width = 80, height, receipt = false, layout = {} } = {}) {
  if (!source) throw new Error('The print document is not ready.')
  let frame
  try {
    if (receipt) { frame = await createReceiptPrintFrame(source, layout); width = Number(frame.dataset.paperWidth); source = frame.contentDocument.getElementById('receipt-print'); height = Number.parseFloat(frame.style.height) }
    await source.ownerDocument.fonts?.ready
    const clone = source.cloneNode(true), originals = [source, ...source.querySelectorAll('*')], copies = [clone, ...clone.querySelectorAll('*')]
    for (let i = 0; i < originals.length; i++) {
      const original = originals[i], copy = copies[i], style = source.ownerDocument.defaultView.getComputedStyle(original)
      for (const name of PROPERTIES) copy.style.setProperty(name, style.getPropertyValue(name))
      copy.style.color = '#000'; copy.style.backgroundColor = 'transparent'; copy.style.backgroundImage = 'none'
      // The dedicated receipt frame already uses local system fonts. Preserve
      // its computed family, including monospace item details and barcode text.
      copy.style.fontFamily = receipt ? style.fontFamily : 'Arial, "Nirmala UI", "Iskoola Pota", Tahoma, sans-serif'
      for (const attr of [...copy.attributes]) if (/^on/i.test(attr.name)) copy.removeAttribute(attr.name)
      if (copy.tagName === 'IMG') { copy.src = await embeddedImage(original.currentSrc || original.src); copy.removeAttribute('srcset') }
      if (['SCRIPT', 'IFRAME', 'OBJECT', 'EMBED', 'LINK'].includes(copy.tagName)) copy.remove()
      if (copy.tagName === 'A') copy.removeAttribute('href')
      if (copy.tagName === 'INPUT') copy.setAttribute('value', original.value)
    }
    // Native HTML sanitizers can remove inline SVG. Keep generated invoice
    // barcodes as embedded vector images rather than low-resolution screenshots.
    for (const svg of clone.querySelectorAll('svg')) {
      const img = source.ownerDocument.createElement('img')
      img.setAttribute('style', svg.getAttribute('style') || '')
      img.src = await new Promise((resolve, reject) => {
        const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject
        reader.readAsDataURL(new Blob([svg.outerHTML], { type: 'image/svg+xml' }))
      })
      img.alt = ''; svg.replaceWith(img)
    }
    clone.style.position = 'static'; clone.style.inset = 'auto'; clone.style.margin = '0'; clone.style.width = `${frame?.dataset.printableWidth || width}mm`; clone.style.maxWidth = '100%'
    clone.style.transform = 'none'; clone.style.zoom = '1'
    clone.style.color = '#000'; clone.style.backgroundColor = '#fff'
    const size = height ? `${width}mm ${height}mm` : `${width}mm auto`
    const styles = frame ? [...frame.contentDocument.querySelectorAll('style')].map((s) => s.textContent).join('\n') : ''
    const html = `<!doctype html><html lang="${document.documentElement.lang || 'en'}" dir="${document.documentElement.dir || 'ltr'}"><head><meta charset="UTF-8"><style>${styles}\n@page{size:${size};margin:0}html,body{margin:0;padding:0;background:white;color:black;width:${width}mm}*{box-sizing:border-box;print-color-adjust:exact}img{max-width:100%}</style></head><body>${clone.outerHTML}</body></html>`
    if (new TextEncoder().encode(html).length > 10 * 1024 * 1024) throw new Error('Split this print document into smaller parts.')
    return { html, width, height }
  } finally { frame?.remove() }
}
