import { call } from './api'
import { newId, putCustomer, savePendingCustomer, searchCustomersOffline } from './offline'
import { displayTerminalId, onDisplayCustomer, replyDisplayCustomer } from './customerDisplay'
import { t } from './i18n'

export function customerEntryError(name, mobile) {
  if (!name.trim() || name.trim().length > 140) return t('Enter your name.')
  const digits = mobile.replace(/\D/g, '')
  if (!/^[+\d\s().-]+$/.test(mobile) || digits.length < 7 || digits.length > 15 || mobile.length > 32) {
    return t('Enter a valid contact number, including the area or country code.')
  }
  return ''
}

async function resolveCustomer(payload, session) {
  if (!session.offline) return call('lumenpos.api.catalog.create_customer', { payload })
  const digits = (value) => String(value || '').replace(/\D/g, '')
  const matches = await searchCustomersOffline('', Number.MAX_SAFE_INTEGER)
  const existing = matches.find((c) => digits(c.mobile_no) === digits(payload.mobile_no))
  if (existing) return existing
  const missing = (session.settings?.customer_form?.fields || [])
    .some((field) => field.individual === 'Required' && !payload[field.fieldname])
  if (missing) throw new Error(t('More customer details are required. Please ask the cashier for help.'))
  const tempId = '__local__' + newId()
  await savePendingCustomer({ temp_id: tempId, payload, created_at: new Date().toISOString() })
  const customer = { name: tempId, ...payload, customer_group: '', __local: true }
  await putCustomer(customer)
  return customer
}

// Runs only in the cashier tab; the display sends details without calling APIs.
export function connectDisplayCustomerEntry(cart, session, publish) {
  let pending = false
  return onDisplayCustomer(async (message) => {
    if (message.terminalId !== displayTerminalId) return
    const reply = (data) => replyDisplayCustomer({ requestId: message.requestId, saleId: message.saleId, ...data })
    const current = () => session.settings?.enable_customer_display && !session.locked &&
      !cart.submitting && cart.lines.length > 0 && cart.displaySaleId === message.saleId
    if (!current()) return reply({ error: t('This sale has changed. Please ask the cashier to try again.') })
    if (pending) return reply({ error: t('Your details are being saved. Please wait.') })
    const name = String(message.customer_name || '').trim()
    const mobile = String(message.mobile_no || '').trim()
    const error = customerEntryError(name, mobile)
    if (error) return reply({ error })
    pending = true
    const previousCustomer = cart.customer?.name
    try {
      const customer = await resolveCustomer({ customer_type: 'Individual', customer_name: name, mobile_no: mobile }, session)
      // The cashier may have completed the sale or selected someone else while
      // the request was in flight. Never attach these details to a later sale.
      if (!current() || cart.customer?.name !== previousCustomer) {
        return reply({ error: t('This sale has changed. Please ask the cashier to try again.') })
      }
      await cart.setCustomer(customer)
      if (!current()) return reply({ error: t('This sale has changed. Please ask the cashier to try again.') })
      publish()
      reply({ ok: true, offline: Boolean(customer.__local) })
    } catch (error) {
      reply({ error: error.message || t('Could not save your details. Please ask the cashier for help.') })
    } finally {
      pending = false
    }
  })
}
