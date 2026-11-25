// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
import receiptStyles from './styles/receipt.css?inline'
import { receiptRollWidth, validateReceiptLayout } from './receiptLayout.js'

// Print only the receipt. Hiding the rest of the POS with visibility:hidden
// still leaves its viewport, scroll containers and modal offsets on paper.
export async function createReceiptPrintFrame(source, layout = {}) {
  if (!source) throw new Error('Receipt is not ready to print')
  document.getElementById('receipt-print-frame')?.remove()
  const roll = receiptRollWidth(source), geometry = validateReceiptLayout(layout, roll)
  const width = geometry.paperWidth, isReceipt = source.classList.contains('receipt')
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
    // are unnecessary: thermal output uses system fonts and monochrome rules.
    const styles = document.createElement('style')
    styles.textContent = isReceipt ? receiptStyles.replace(/:deep\(([^)]+)\)/g, '$1') : Array.from(document.styleSheets).map((sheet) => {
      try {
        return Array.from(sheet.cssRules).filter((rule) => rule.type !== 3).map((rule) => rule.cssText).join('\n')
      } catch {
        return '' // Cross-origin font stylesheets cannot be read.
      }
    }).join('\n')
    doc.head.appendChild(styles)
    const paper = doc.createElement('style')
    paper.textContent = `
      :root { --border: #000; --border-subtle: #000; --text: #000; --text-muted: #000; --mono: 'Courier New', monospace; }
      *, *::before, *::after { box-sizing: border-box; }
      html, body { width: ${width}mm !important; height: auto !important; min-height: 0 !important;
        margin: 0 !important; padding: 0 !important; overflow: visible !important; background: #fff !important; }
      body { position: relative !important; }
      #receipt-print { position: ${isReceipt ? 'static' : 'absolute'} !important; inset: auto !important;
        width: ${geometry.printableWidth}mm !important; max-width: 100% !important;
        margin: 0 !important; box-sizing: border-box; border: 0; border-radius: 0;
        padding: ${geometry.inset}mm; font-family: Arial, 'Nirmala UI', 'Iskoola Pota', Tahoma, sans-serif; line-height: 1.3;
        transform: none !important; zoom: 1 !important;
        background: #fff !important; color: #000 !important; }
      #receipt-print, #receipt-print * { visibility: visible !important; color: #000 !important; }
      #receipt-print img { max-width: 100%; }
      #receipt-print.tpl-table { --table-rule: #000; }
      #receipt-print.receipt table { width: 100%; border-collapse: collapse; table-layout: fixed; }
      #receipt-print.receipt :is(.retail-item-values td, .row > :last-child) { white-space: nowrap; }
      #receipt-print.receipt .row > :last-child, #receipt-print.receipt .retail-savings strong { flex-shrink: 0; }
      #receipt-print.receipt .row > :first-child { min-width: 0; overflow-wrap: anywhere; }
      #receipt-print.tpl-table :is(.retail-totals, .retail-loyalty) { display: grid; grid-template-columns: minmax(0, 1fr) max-content; }
      #receipt-print.tpl-table :is(.retail-totals, .retail-loyalty) .row { grid-template-columns: subgrid; grid-column: 1 / -1; min-width: 0; }
      #receipt-print.tpl-table .retail-loyalty-title { grid-column: 1 / -1; }
      #receipt-print.paper-58.tpl-table .retail-items :is(th, td) { padding-inline: 1px; }
      #receipt-print.paper-58.tpl-table .retail-items:not(.without-discount) th:nth-child(1) { width: 7%; }
      #receipt-print.paper-58.tpl-table .retail-items:not(.without-discount) th:nth-child(2) { width: 11%; }
      #receipt-print.paper-58.tpl-table .retail-items:not(.without-discount) th:nth-child(3) { width: 26%; }
      #receipt-print.paper-58.tpl-table .retail-items:not(.without-discount) th:nth-child(4) { width: 23%; }
      #receipt-print.paper-58.tpl-table .retail-items:not(.without-discount) th:nth-child(5) { width: 33%; }
      #receipt-print .retail-item-name td { white-space: normal; overflow-wrap: anywhere; }
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
    await doc.fonts?.ready
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
    frame.dataset.paperWidth = String(width)
    frame.dataset.printableWidth = String(geometry.printableWidth)
    frame.dataset.inset = String(geometry.inset)
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

export async function printReceipt(source, layout = {}) {
  const frame = await createReceiptPrintFrame(source, layout)
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
