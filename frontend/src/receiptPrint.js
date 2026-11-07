// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only

// Print only the receipt. Hiding the rest of the POS with visibility:hidden
// still leaves its viewport, scroll containers and modal offsets on paper.
export async function createReceiptPrintFrame(source) {
  if (!source) throw new Error('Receipt is not ready to print')
  document.getElementById('receipt-print-frame')?.remove()
  const width = source.classList.contains('paper-58') ? 58 : 80
  const frame = document.createElement('iframe')
  frame.id = 'receipt-print-frame'
  frame.title = 'Receipt print'
  frame.setAttribute('aria-hidden', 'true')
  frame.style.cssText = `position:fixed;left:-10000px;top:0;width:${width}mm;height:1px;border:0;pointer-events:none`
  document.body.appendChild(frame)
  try {
    const doc = frame.contentDocument
    // about:blank starts in quirks mode, where tables do not inherit receipt
    // typography. Use standards mode for both measurement and printing.
    doc.open()
    doc.write('<!doctype html><html><head></head><body></body></html>')
    doc.close()
    doc.documentElement.lang = document.documentElement.lang
    doc.documentElement.dir = document.documentElement.dir || 'ltr'
    // Reuse the loaded Vue scoped styles, including offline. Remote font imports
    // are unnecessary: thermal output uses system fonts and solid black rules.
    const styles = document.createElement('style')
    styles.textContent = Array.from(document.styleSheets).map((sheet) => {
      try {
        return Array.from(sheet.cssRules).filter((rule) => rule.type !== 3).map((rule) => rule.cssText).join('\n')
      } catch {
        return '' // Cross-origin font stylesheets cannot be read.
      }
    }).join('\n')
    doc.head.appendChild(styles)
    const paper = doc.createElement('style')
    paper.textContent = `
      :root { --border: #000; --border-subtle: #000; --text: #000; --text-muted: #000; --mono: monospace; }
      html, body { width: ${width}mm !important; height: auto !important; min-height: 0 !important;
        margin: 0 !important; padding: 0 !important; overflow: visible !important; background: #fff !important; }
      body { position: relative !important; }
      #receipt-print { position: absolute !important; inset: 0 auto auto 0 !important;
        width: ${width}mm !important; max-width: none !important;
        margin: 0 !important; box-sizing: border-box; border: 0; border-radius: 0;
        padding: 3mm; font-family: Arial, Tahoma, sans-serif; line-height: 1.3;
        background: #fff !important; color: #000 !important; }
      #receipt-print, #receipt-print * { visibility: visible !important; color: #000 !important; }
      #receipt-print img { max-width: 100%; }
    `
    doc.head.appendChild(paper)
    const receipt = source.cloneNode(true)
    receipt.id = 'receipt-print'
    receipt.classList.add('receipt-paper')
    // Resolve relative logo/custom-field image URLs against the POS document.
    const originalImages = source.querySelectorAll('img')
    receipt.querySelectorAll('img').forEach((img, index) => {
      const original = originalImages[index]
      img.src = original.currentSrc || original.src
      img.removeAttribute('srcset')
      img.loading = 'eager'
    })
    doc.body.appendChild(receipt)
    await Promise.all(Array.from(receipt.querySelectorAll('img')).map((img) => new Promise((resolve) => {
      if (img.complete) return resolve()
      const done = () => {
        clearTimeout(timer)
        img.onload = img.onerror = null
        resolve()
      }
      const timer = setTimeout(() => {
        // A late logo must not change the measured paper length.
        img.style.display = 'none'
        done()
      }, 5000)
      img.onload = img.onerror = done
    })))
    // Calibrate CSS pixels against a real CSS millimetre in this frame instead
    // of assuming 96dpi: browser zoom and Windows display scaling otherwise
    // make some thermal drivers receive a page almost twice as long.
    const ruler = doc.createElement('div')
    ruler.style.cssText = 'position:absolute;left:-10000px;top:0;width:100mm;height:1px'
    doc.body.appendChild(ruler)
    const pxPerMm = ruler.getBoundingClientRect().width / 100 || (96 / 25.4)
    ruler.remove()
    // Round up with a 1mm feed allowance so fractional layout cannot spill a
    // short receipt onto a second sheet. Give the iframe and document the same
    // explicit height: Chromium otherwise lets a fixed-length Windows driver
    // centre an auto-height body inside its much longer page.
    const contentPx = Math.max(receipt.scrollHeight, receipt.getBoundingClientRect().height)
    const height = Math.ceil(contentPx / pxPerMm) + 1
    frame.style.height = `${height}mm`
    paper.textContent += `
      html, body { height: ${height}mm !important; max-height: ${height}mm !important; }
      @page { size: ${width}mm ${height}mm; margin: 0 !important; }
    `
    // Force layout after the page box changes before opening print preview.
    void receipt.offsetHeight
    return frame
  } catch (error) {
    frame.remove()
    throw error
  }
}

export async function printReceipt(source) {
  const frame = await createReceiptPrintFrame(source)
  const win = frame.contentWindow
  win.addEventListener('afterprint', () => setTimeout(() => frame.remove(), 0), { once: true })
  try {
    win.focus()
    win.print()
  } catch (error) {
    frame.remove()
    throw error
  }
}
