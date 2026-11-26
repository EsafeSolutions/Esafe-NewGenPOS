import { toBlob } from 'html-to-image'

export function messagingNumber(value, countryCode = '94') {
  let number = String(value || '').trim()
  if (!/^[+0-9\s()-]+$/.test(number)) throw new Error('Enter a valid customer mobile number.')
  number = number.replace(/[\s()-]/g, '')
  if (number.startsWith('00')) number = '+' + number.slice(2)
  if (number.startsWith('0')) number = '+' + countryCode + number.slice(1)
  if (!/^\+?[1-9][0-9]{5,14}$/.test(number)) throw new Error('Enter a valid mobile number including its country code.')
  return number.replace(/^\+/, '')
}

export function whatsappUrl(mobile, message, countryCode) {
  return `https://wa.me/${messagingNumber(mobile, countryCode)}?text=${encodeURIComponent(message)}`
}

export async function receiptImage(node, invoice) {
  if (!node) throw new Error('Open the receipt preview before preparing an image.')
  const width = Math.ceil(node.getBoundingClientRect().width)
  const height = Math.ceil(node.scrollHeight)
  if (!width || !height || width * height * 4 > 24000000 || height * 2 > 30000) {
    throw new Error('This receipt is too long for one image. Share the e-invoice link instead.')
  }
  await Promise.all(Array.from(node.querySelectorAll('img')).map(image => image.decode()))
  const blob = await toBlob(node, { pixelRatio: 2, backgroundColor: '#ffffff', width, height, skipFonts: true,
    style: { margin: '0', overflow: 'visible', maxHeight: 'none' } })
  if (!blob || !blob.size) throw new Error('The receipt image could not be prepared. Share its link or try again.')
  const name = `${String(invoice || 'receipt').replace(/[^a-zA-Z0-9_-]/g, '_')}.png`
  return new File([blob], name, { type: 'image/png' })
}
