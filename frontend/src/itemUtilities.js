export function generateItemBarcode() {
  const random = Math.random().toString(36).slice(2, 8).toUpperCase()
  const time = Date.now().toString(36).slice(-6).toUpperCase()
  return `ES${time}${random}`
}
