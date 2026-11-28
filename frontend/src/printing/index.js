import { fromBase64 } from '@esafe/printer-manager'
import { call } from '../api'
import { useSessionStore } from '../stores/session'
import { createEsafeService } from './esafe.js'
import { selfContainedHtml } from './documents.js'
import { createDrawerController } from './drawer.js'
import { receiptLayoutFor, receiptHtmlOptions } from '../receiptLayout.js'
import { receiptPdf } from './receiptPdf.js'

export const printManager = createEsafeService({
  authorize: (record) => call('esafepos.api.esafe_printing.register_intent', {
    pos_profile: record.profile, request_id: record.intentId, workstation: record.workstation,
    payload_hash: record.payloadHash, reference: record.reference, role: record.role, output: record.format,
    reprint_of: record.reprintOf || '', automatic: record.automatic ? 1 : 0,
    printer_id: record.printerId, drawer: record.drawer || null,
  }),
  report: (record) => call('esafepos.api.esafe_printing.record_event', {
    request_id: record.intentId, state: record.state, job_id: record.agentJobId || '',
    certainty: record.certainty || '', detail: record.error || '',
  }),
})
export const cashDrawer = createDrawerController(printManager, (profile, doctype, name) =>
  call('esafepos.api.cash_drawer.payment_eligibility', { pos_profile: profile, doctype, name }))
export function silentPrinting(session = useSessionStore()) { return !!session.settings?.esafe_printing?.silent && !session.offline }
export async function nativeReceipt(receipt, source, { reprint = false, automatic = false } = {}) {
  const session = useSessionStore(), config = receipt.printing_defaults || session.settings.esafe_printing || {}, profile = receipt.pos_profile || session.posProfile
  if (!config.silent || session.offline || receipt.offline) return null
  const key = reprint ? crypto.randomUUID() : `receipt:${receipt.doctype || session.invoiceMode}:${receipt.name}:original`
  let format = config.receipt_output || 'html', data, dimensions
  if (format === 'html') { const binding = await printManager.binding(profile); dimensions = await receiptPdf(source, receiptLayoutFor(source, binding)); data = dimensions.data; format = 'pdf' }
  else { const rendered = await call('esafepos.api.esafe_printing.receipt_output', { invoice: receipt.name, output: format, reprint: reprint ? 1 : 0 }, {timeout:60000}); data = fromBase64(rendered.data) }
  const previous = printManager.state.jobs.find((j) => j.reference?.name === receipt.name && j.role === 'receipt')
  return printManager.dispatch({ key, profile, role: 'receipt', format, data,
    options: dimensions ? { ...receiptHtmlOptions(dimensions, config.copies || 1), duplex: 'none', color: false } : { copies: config.copies || 1 },
    title: `Receipt ${receipt.name}`, reference: { doctype: receipt.doctype || session.invoiceMode || 'POS Invoice', name: receipt.name, reprint: reprint ? 1 : 0 },
    reprintOf: reprint ? previous?.intentId || '' : '', user: session.user, automatic })
}
export async function nativeDocument(doctype, name, { profile, key } = {}) {
  const session = useSessionStore()
  if (!silentPrinting(session)) return null
  profile = profile || session.posProfile
  key = key || `document:${doctype}:${name}:original`
  // Keep a manual browser route even if PDF preparation fails before dispatch.
  await printManager.rememberDocument({ key, doctype, name, profile, user: session.user })
  const rendered = await call('esafepos.api.esafe_printing.document_pdf', { doctype, name }, {timeout:60000})
  const paper = session.settings.esafe_printing?.document_paper === 'Letter' ? { width: 215.9, height: 279.4 } : { width: 210, height: 297 }
  return printManager.dispatch({ key, profile,
    role: 'document', format: 'pdf', data: fromBase64(rendered.data), title: `${doctype} ${name}`,
    options: { copies: session.settings.esafe_printing?.copies || 1, size: paper, scale: 'actual' },
    reference: { doctype, name }, user: session.user })
}
export async function nativeElement(source, reference, { role = 'report', title, key, width = 80, receipt = true } = {}) {
  const session = useSessionStore()
  if (!silentPrinting(session)) return null
  const doc = await selfContainedHtml(source, { receipt, width })
  return printManager.dispatch({ key: key || crypto.randomUUID(), profile: session.posProfile, role, format: 'html', data: doc.html,
    title: title || reference.name, reference, user: session.user, options: { copies: session.settings.esafe_printing?.copies || 1, size: { width: doc.width, height: doc.height }, margins: 0, scale: 'actual' } })
}
export function printStatusMessage(record) {
  if (!record) return 'The document is ready for browser printing.'
  return record.state === 'unknown' ? 'Print acceptance is uncertain. Check Printing → Print jobs before retrying or using browser print.'
    : record.state === 'cancelled' ? 'The print job was cancelled. Check the printer before requesting another copy.'
    : record.state === 'completed' ? 'Windows reported completion. Check the printer for paper output.'
    : record.state === 'prepared' ? 'The print intent is prepared. Open Printing → Print jobs to retry its submission.'
    : record.state === 'failed' ? `Printing failed: ${record.error || 'See Recent jobs.'}`
      : 'Print job accepted by Esafe. Check the printer for paper output.'
}
