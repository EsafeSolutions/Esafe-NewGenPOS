// Cashier-facing explanations. Keep the original error available for the manager.
import { plainText, parseMoney } from './format'
import { t } from './i18n'

export function closingIssue(state = {}) {
  const error = plainText(state.closing_error || '')
  const text = error.toLowerCase()
  if (state.closing_status !== 'Failed') {
    return { title: t('Finishing the shift'), message: t('Your closing count is saved. Sales are being posted in the background.'), action: t('You can leave this page. The status updates automatically.') }
  }
  if (/valuation rate|valuation_rate/.test(text)) {
    const item = error.match(/valuation rate for (?:the )?item\s+(.+?)\s*,?\s+is required/i)?.[1]?.replace(/,$/, '').trim()
    return { title: t('An item cost is missing'), item, message: t('The closing count is saved, but ERPNext needs an item cost before it can post these sales.'), action: t('Ask a manager to check the item valuation and incoming stock in ERPNext, then retry closing. Use zero cost only when the accounts team confirms it is correct.') }
  }
  if (/negative stock|insufficient stock|not enough stock/.test(text)) {
    return { title: t('Stock needs checking'), message: t('ERPNext cannot post the stock used by these sales.'), action: t('Ask a manager to check the warehouse, stock receipts and posting dates, then retry closing.') }
  }
  if (/accounting period|period.*closed|frozen|accounts frozen|stock frozen/.test(text)) {
    return { title: t('The posting date is locked'), message: t('The accounts or stock period prevents these sales from being posted.'), action: t('Ask the accounts team to review the locked period and posting date, then retry closing.') }
  }
  if (/permission|not permitted|not allowed|not authorized/.test(text)) {
    return { title: t('Manager access is needed'), message: t('ERPNext refused a permission needed to finish posting.'), action: t('Ask a manager to check the closing and accounting permissions, then retry closing.') }
  }
  if (/account.*(?:missing|required|not set|must|does not)|(?:set|missing|required).*account|cost center/.test(text)) {
    return { title: t('Accounting setup needs checking'), message: t('An account or cost centre needed for these sales is missing or invalid.'), action: t('Ask the accounts team to check the item, warehouse and payment accounts, then retry closing.') }
  }
  if (/deadlock|lock wait|timeout|timed out|connection|redis|worker|try again/.test(text)) {
    return { title: t('A temporary posting problem'), message: t('The server was busy or the connection was interrupted. Your closing count is saved.'), action: t('Use Check and retry closing. Temporary posting failures are also retried by the background recovery task.') }
  }
  return { title: t('Closing needs a manager to check'), message: t('Your closing count is saved. Some sales still need to be posted.'), action: t('Use Check and retry closing once. If it fails again, share Details for manager with your manager.') }
}

export function invalidCountModes(rows, counts) {
  return rows.filter(row => {
    const amount = parseMoney(counts[row.mode_of_payment])
    return amount == null || (row.is_cash && amount < 0)
  }).map(row => row.mode_of_payment)
}

// One request at a time, with slower checks while a manager fixes a failure.
// Disposing also ignores an already-running request when the page changes.
export function createClosingMonitor(read, onState) {
  let timer = null
  let generation = 0
  function stop() {
    generation += 1
    clearTimeout(timer)
  }
  function start(name) {
    stop()
    const current = generation
    async function check() {
      let delay = 3000
      try {
        const state = await read(name)
        if (current !== generation) return
        await onState(state, name)
        if (state.status === 'Closed' || current !== generation) return
        if (state.closing_status === 'Failed') delay = 15000
      } catch {
        delay = 15000
      }
      if (current === generation) timer = setTimeout(check, delay)
    }
    check()
  }
  return { start, stop }
}
