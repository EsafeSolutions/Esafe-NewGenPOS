import { fromBase64 } from '@esafe/printer-manager'
import { call } from './api'
import { nativeDocument, nativeElement, printManager, printStatusMessage, silentPrinting } from './printing/index.js'
import { useSessionStore } from './stores/session'

export async function printB2BDocument(doctype, name) {
  const session = useSessionStore()
  if (silentPrinting(session)) {
    const result = await nativeDocument(doctype, name, { key: `b2b:${doctype}:${name}:${crypto.randomUUID()}` })
    session.notify(printStatusMessage(result))
    return
  }
  const tab = window.open('about:blank', '_blank')
  if (!tab) throw new Error('Allow pop-ups to print this document.')
  try {
    const result = await call('esafepos.api.esafe_printing.document_printview', { doctype, name })
    tab.location.replace(result.url)
  } catch (error) { tab.close(); throw error }
}

export async function printB2BStatement(args) {
  const session = useSessionStore(), native = silentPrinting(session)
  const tab = native ? null : window.open('about:blank', '_blank')
  if (!native && !tab) throw new Error('Allow pop-ups to print the customer statement.')
  try {
    const result = await call('esafepos.api.b2b_reports.statement_pdf', args, { timeout: 60000 })
    if (native) {
      const job = await printManager.dispatch({ key: crypto.randomUUID(), profile: session.posProfile, role: 'report', format: 'pdf',
        data: fromBase64(result.data), title: `Customer statement ${args.customer}`, user: session.user,
        reference: { doctype: 'Customer', name: args.customer }, options: { copies: 1, size: { width: 210, height: 297 }, scale: 'actual' } })
      session.notify(printStatusMessage(job))
    } else {
      const url = URL.createObjectURL(new Blob([fromBase64(result.data)], { type: 'application/pdf' }))
      tab.location.replace(url)
      setTimeout(() => URL.revokeObjectURL(url), 120000)
    }
  } catch (error) { tab?.close(); throw error }
}

export async function printB2BReceipt(source, reference) {
  const session = useSessionStore()
  if (silentPrinting(session)) {
    session.notify(printStatusMessage(await nativeElement(source, reference, { width: 210, receipt: false, title: `Settlement ${reference.name}` })))
    return
  }
  const tab = window.open('about:blank', '_blank')
  if (!tab) throw new Error('Allow pop-ups to print this receipt.')
  tab.document.write(`<!doctype html><html><head><title>Customer settlement</title><style>body{font:14px Arial,sans-serif;color:#25334a;padding:24px}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px;border-bottom:1px solid #dfe8eb}h1{font-size:24px}@page{size:A4;margin:12mm}</style></head><body>${source.outerHTML}</body></html>`)
  tab.document.close()
  tab.focus()
  tab.print()
}
