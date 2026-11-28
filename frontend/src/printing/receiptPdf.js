// Freeze the validated, self-contained print document before native rendering.
import { selfContainedHtml } from './documents.js'
import { pdfDocument } from '../labels/printing.js'

export async function receiptPdf(source, layout) {
  const prepared = await selfContainedHtml(source, { receipt: true, layout })
  const { width, height } = prepared, ratio = 203.2 / 96
  const cssWidth = width * 96 / 25.4, cssHeight = height * 96 / 25.4
  if (cssWidth * cssHeight * ratio * ratio > 20000000 || cssHeight * ratio > 30000) throw new Error('This receipt is too long for one print-ready page. Split the receipt into smaller sales.')
  // Use the exact HTML checked for geometry. Another computed-style cloner
  // can round fonts and break colspan widths, so do not clone it again.
  const parsed = new DOMParser().parseFromString(prepared.html, 'text/html')
  for (const style of [...parsed.head.querySelectorAll('style')]) parsed.body.prepend(style)
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  svg.setAttribute('width', String(cssWidth)); svg.setAttribute('height', String(cssHeight))
  const foreign = document.createElementNS(svg.namespaceURI, 'foreignObject')
  foreign.setAttribute('width', '100%'); foreign.setAttribute('height', '100%')
  foreign.appendChild(parsed.body); svg.appendChild(foreign)
  const image = new Image()
  image.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(svg))
  await image.decode()
  const canvas = document.createElement('canvas')
  canvas.width = Math.ceil(cssWidth * ratio); canvas.height = Math.ceil(cssHeight * ratio)
  const context = canvas.getContext('2d')
  context.fillStyle = '#fff'; context.fillRect(0, 0, canvas.width, canvas.height)
  context.drawImage(image, 0, 0, canvas.width, canvas.height)
  const page = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}mm" height="${height}mm" viewBox="0 0 ${canvas.width} ${canvas.height}"><image href="${canvas.toDataURL('image/png')}" width="100%" height="100%"/></svg>`
  const data = await pdfDocument([page], { pageW: width, pageH: height }, 203.2, true)
  return { data, width, height }
}
