import { encodeCashDrawerPulse } from '@esafe/printer-manager'

export function validateDrawer(value = {}) {
  const settings = { enabled: false, automatic: false, pin: 0, onMs: 100, offMs: 500, ...value }
  if (typeof settings.enabled !== 'boolean' || typeof settings.automatic !== 'boolean') throw new Error('Choose enabled or disabled for drawer policies.')
  if (![0, 1].includes(settings.pin) || typeof settings.pin !== 'number') throw new Error('Choose connector pin 2 or pin 5.')
  for (const key of ['onMs', 'offMs']) if (!Number.isInteger(settings[key]) || settings[key] < 2 || settings[key] > 510 || settings[key] % 2) throw new Error('Pulse times must be even integers from 2 to 510 milliseconds.')
  return Object.fromEntries(['enabled', 'automatic', 'pin', 'onMs', 'offMs'].map((key) => [key, settings[key]]))
}

export function createDrawerController(service, eligible) {
  const pending = new Map()
  async function open({ profile, reference, user, mode, reason = '', key = crypto.randomUUID(), receiptJob }) {
    const binding = await service.binding(profile), config = validateDrawer(binding.drawer)
    if (!config.enabled || !binding.receipt || binding.drawer?.printerId !== binding.receipt) throw new Error('Save and enable the drawer for the exact receipt printer first.')
    if (!service.state.printGrants.includes(binding.receipt)) throw new Error('Approve the saved receipt printer before opening the drawer.')
    const drawer = { ...config, mode, reason, receiptIntent: receiptJob?.intentId || '' }
    return service.dispatch({ key, profile, role: 'drawer', format: 'raw', data: encodeCashDrawerPulse(config), options: { copies: 1 },
      title: `Cash drawer ${mode}: ${reference.name}`, reference, user, automatic: mode === 'payment', drawer,
      beforeAuthorize: receiptJob ? () => service.waitSubmitted(receiptJob) : undefined })
  }
  function afterSale({ receipt, profile, user, offline = false, reprint = false, receiptJob }) {
    if (offline || reprint || receipt.offline || receipt.is_return || Number(receipt.on_account?.amount || 0) > 0) return Promise.resolve(null)
    const key = `drawer:${receipt.doctype || 'POS Invoice'}:${receipt.name}:original`
    if (pending.has(key)) return pending.get(key)
    const task = (async () => {
      const binding = await service.binding(profile)
      if (!binding.drawer?.enabled || !binding.drawer?.automatic) return null
      if (!(await eligible(profile, receipt.doctype || 'POS Invoice', receipt.name)).eligible) return null
      return open({ key, profile, user, mode: 'payment', reference: { doctype: receipt.doctype || 'POS Invoice', name: receipt.name }, receiptJob })
    })().finally(() => pending.delete(key))
    pending.set(key, task)
    return task
  }
  return { open, afterSale }
}
