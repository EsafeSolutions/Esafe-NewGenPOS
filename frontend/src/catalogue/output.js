const bytes = value => new TextEncoder().encode(value)
const join = parts => { const out = new Uint8Array(parts.reduce((sum, p) => sum + p.length, 0)); let offset = 0; for (const part of parts) { out.set(part, offset); offset += part.length } return out }
export function downloadPdf(blob, name) {
  const url = URL.createObjectURL(blob), link = document.createElement('a')
  link.href = url; link.download = name; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}
export function documentHtml(doc) {
  return `<!doctype html><html><head><meta charset="UTF-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data: blob:; style-src 'unsafe-inline'"><style>@page{size:${doc.width}mm ${doc.height}mm;margin:0}html,body{margin:0;background:#edf2f1}.page{background:white;break-after:page;page-break-after:always}.page:last-child{break-after:auto;page-break-after:auto}svg{display:block;max-width:100%;height:auto}@media print{html,body{background:white}.page{width:${doc.width}mm;height:${doc.height}mm}svg{max-width:none;width:${doc.width}mm;height:${doc.height}mm}}</style></head><body>${doc.pages.map(svg => `<div class="page">${svg}</div>`).join('')}</body></html>`
}
export async function browserPrint(doc) {
  const frame = document.createElement('iframe')
  frame.title = 'Menu and catalogue print'; frame.setAttribute('sandbox', 'allow-same-origin allow-modals')
  frame.style.cssText = `position:fixed;left:-10000px;width:${doc.width}mm;height:${doc.height}mm;border:0`
  try {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('The catalogue print window did not load.')), 15000)
      frame.onload = () => { clearTimeout(timer); resolve() }
      frame.srcdoc = documentHtml(doc); document.body.appendChild(frame)
    })
    await frame.contentDocument.fonts.ready
    await Promise.all([...frame.contentDocument.querySelectorAll('image')].map(async element => {
      const img = new Image(); img.src = element.getAttribute('href'); await img.decode()
    }))
    frame.contentWindow.addEventListener('afterprint', () => frame.remove(), { once: true })
    frame.contentWindow.focus(); frame.contentWindow.print()
    setTimeout(() => frame.remove(), 60000)
  } catch (e) { frame.remove(); throw e }
}
export async function loadImages(items, progress = () => {}) {
  const images = {}, missing = [], urls = new Map()
  let index = 0, done = 0
  async function load(row) {
    try {
      const url = new URL(row.image, location.href)
      if (!['https:', 'http:'].includes(url.protocol) || (url.origin !== location.origin && url.protocol !== 'https:')) throw new Error('Unsupported image URL')
      if (!urls.has(url.href)) urls.set(url.href, (async () => {
        const response = await fetch(url.href, { credentials: url.origin === location.origin ? 'same-origin' : 'omit', signal: AbortSignal.timeout(12000) })
        if (!response.ok) throw new Error('Image unavailable')
        const blob = await response.blob()
        if (!blob.type.startsWith('image/') || blob.size > 8 * 1024 * 1024) throw new Error('Unsupported or oversized image')
        const object = URL.createObjectURL(blob), image = new Image()
        try {
          image.src = object; await image.decode()
          const scale = Math.min(1, 600 / Math.max(image.naturalWidth, image.naturalHeight))
          const canvas = document.createElement('canvas'); canvas.width = Math.max(1, Math.round(image.naturalWidth * scale)); canvas.height = Math.max(1, Math.round(image.naturalHeight * scale))
          const ctx = canvas.getContext('2d'); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height); ctx.drawImage(image, 0, 0, canvas.width, canvas.height)
          return canvas.toDataURL('image/jpeg', 0.88)
        } finally { URL.revokeObjectURL(object) }
      })())
      images[row.item_code] = await urls.get(url.href)
    } catch { missing.push(row.item_code) }
  }
  await Promise.all(Array.from({ length: 4 }, async () => {
    while (index < items.length) {
      const row = items[index++]
      if (row.image) await load(row)
      done++; progress(done, items.length)
    }
  }))
  return { images, missing }
}
export async function cataloguePdf(doc, progress = () => {}, sink = null) {
  // A file stream keeps large, complete catalogues out of an ever-growing
  // browser download buffer. Blob downloads remain available on other browsers.
  const chunks = [], offsets = [0], totalObjects = 2 + doc.pages.length * 3
  let length = 0
  async function write(data) {
    if (!sink && length + data.length > 150 * 1024 * 1024) throw new Error('This browser download exceeds 150 MB. Use direct file saving in desktop Chrome/Edge or browser Print to PDF for the complete catalogue. No partial PDF was exported.')
    if (sink) await sink.write(data)
    else chunks.push(data)
    length += data.length
  }
  async function object(number, data) {
    offsets[number] = length
    await write(join([bytes(number + ' 0 obj\n'), data, bytes('\nendobj\n')]))
  }
  await write(bytes('%PDF-1.4\n'))
  await object(1, bytes('<< /Type /Catalog /Pages 2 0 R >>'))
  const kids = doc.pages.map((_, i) => (5 + i * 3) + ' 0 R').join(' ')
  await object(2, bytes('<< /Type /Pages /Kids [' + kids + '] /Count ' + doc.pages.length + ' >>'))
  for (let i = 0; i < doc.pages.length; i++) {
    const objectUrl = URL.createObjectURL(new Blob([doc.pages[i]], { type: 'image/svg+xml' })), img = new Image()
    let jpeg, width, height
    try {
      img.src = objectUrl; await img.decode()
      const canvas = document.createElement('canvas'); width = canvas.width = Math.round(doc.width * 180 / 25.4); height = canvas.height = Math.round(doc.height * 180 / 25.4)
      const ctx = canvas.getContext('2d'); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, width, height); ctx.drawImage(img, 0, 0, width, height)
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.94))
      if (!blob) throw new Error('Catalogue page could not be rendered.')
      jpeg = new Uint8Array(await blob.arrayBuffer())
    } finally { URL.revokeObjectURL(objectUrl) }
    const image = 3 + i * 3, content = image + 1, page = image + 2
    await object(image, join([bytes('<< /Type /XObject /Subtype /Image /Width ' + width + ' /Height ' + height + ' /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ' + jpeg.length + ' >>\nstream\n'), jpeg, bytes('\nendstream')]))
    const pw = doc.width * 72 / 25.4, ph = doc.height * 72 / 25.4, commands = 'q ' + pw + ' 0 0 ' + ph + ' 0 0 cm /Im0 Do Q'
    await object(content, bytes('<< /Length ' + commands.length + ' >>\nstream\n' + commands + '\nendstream'))
    await object(page, bytes('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ' + pw + ' ' + ph + '] /Resources << /XObject << /Im0 ' + image + ' 0 R >> >> /Contents ' + content + ' 0 R >>'))
    progress(i + 1, doc.pages.length)
    await new Promise(resolve => setTimeout(resolve, 0))
  }
  const xref = length
  await write(bytes('xref\n0 ' + (totalObjects + 1) + '\n0000000000 65535 f\r\n' + offsets.slice(1).map(offset => String(offset).padStart(10, '0') + ' 00000 n\r\n').join('') + 'trailer\n<< /Size ' + (totalObjects + 1) + ' /Root 1 0 R >>\nstartxref\n' + xref + '\n%%EOF\n'))
  return sink ? null : new Blob(chunks, { type: 'application/pdf' })
}
