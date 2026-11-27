import { watch } from 'vue'
import { call } from './api'
import { t } from './i18n'
import { connectContactChannel, displayContactRequest, displayPayment, displayReceipt, displayTerminalId, setDisplayMode } from './customerDisplay'

export function connectTillContact(cart, session, route) {
  const canUse = () => route.path === '/' && session.posProfile && !session.locked &&
    session.settings?.enable_customer_display && !cart.submitting && !displayPayment.value
  const clear = () => { displayContactRequest.value = null }
  let lookup = null
  const channel = connectContactChannel(displayTerminalId, async (message) => {
    if (!message || !canUse()) return
    if (message.kind === 'next' && displayReceipt.value && !cart.lines.length) {
      displayReceipt.value = null
      clear()
      setDisplayMode('adverts')
      return
    }
    const request = displayContactRequest.value
    if (!request || request.id !== message.id) return
    if (message.kind === 'skip') {
      clear()
      return
    }
    if (message.kind !== 'submit' || lookup === request.id) return
    const profile = session.posProfile
    const previousCustomer = cart.customer
    const current = () => canUse() && displayContactRequest.value?.id === request.id &&
      profile === session.posProfile && cart.customer === previousCustomer
    const result = (error) => channel.postMessage({ kind: 'result', id: request.id, error })
    lookup = request.id
    try {
      if (session.offline) {
        result(t('Contact lookup needs a connection. You can continue as a walk-in.'))
        return
      }
      const customer = await call('esafepos.api.catalog.display_customer_lookup', {
        pos_profile: profile, mobile: message.mobile,
      })
      if (!current()) return
      if (!customer) {
        if (cart.customer) {
          result(t('A customer is already selected. Ask the cashier to change it.'))
          return
        }
        if (!/^\+?[0-9]{7,15}$/.test(message.mobile)) {
          result(t('Enter a valid contact number.'))
          return
        }
        cart.receiptContact = message.mobile
        clear()
        session.notify(t('Contact number added to this sale'))
        return
      }
      clear()
      if (cart.customer?.name !== customer.name) cart.setCustomer(customer)
      session.notify(t('Customer selected'))
    } catch {
      if (current()) result(t('Could not look up this number. Check it or ask the cashier.'))
    } finally {
      if (lookup === request.id) lookup = null
    }
  })
  const stop = watch(() => [route.path, session.posProfile, session.locked, session.offline,
    session.settings?.enable_customer_display, cart.submitting, cart.customer, displayPayment.value, cart.lines.length],
  (values, previous) => {
    if (!canUse() || session.offline || values[1] !== previous[1] || values[6] !== previous[6] ||
        (cart.lines.length && displayContactRequest.value?.mode === 'welcome')) clear()
  }, { flush: 'sync' })
  const stopActions = cart.$onAction(({ name }) => {
    if (['clear', 'restore', 'park', 'retrieve'].includes(name)) clear()
  })
  return () => {
    stop()
    stopActions()
    channel?.close()
    clear()
  }
}
