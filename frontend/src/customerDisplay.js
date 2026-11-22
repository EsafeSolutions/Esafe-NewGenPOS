// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
// "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
// Customer-facing display sync. The till (main window) publishes a fully
// pre-formatted cart snapshot over a BroadcastChannel; the display window
// (route #/display, opened on a second monitor) listens and renders it.
//
// A BroadcastChannel never receives its OWN posts, so the same channel object
// can both publish 'cart' and listen for the display's 'request' handshake
// (sent when a display opens so it gets the current cart immediately, without
// waiting for the next change).

import { newId } from './offline'
import { shallowRef } from 'vue'
import { money } from './format'

const NAME = 'esafepos-customer-display'
let channel = null
// Each till tab owns its display.
export const displayTerminalId = newId()
export const displayPayment = shallowRef(null)
export const displayReceipt = shallowRef(null)
export const displayContactRequest = shallowRef(null)

export function requestDisplayContact(mode = 'overlay') {
  displayContactRequest.value = { id: newId(), mode }
}

export function connectContactChannel(terminalId, handler) {
  if (!terminalId || typeof BroadcastChannel === 'undefined') return null
  const connection = new BroadcastChannel(NAME + '-contact-' + terminalId)
  connection.onmessage = (event) => handler(event.data)
  return connection
}

export function displayCustomerName(name) {
  const first = String(name || '').trim().split(/\s+/)[0]
  return /\p{L}/u.test(first) && !/\d/.test(first) ? first : ''
}

export function customerDisplayUrl() {
  return window.location.href.replace(/#.*$/, '') + '#/display?terminal=' + displayTerminalId
}

function chan() {
  if (channel === null && typeof BroadcastChannel !== 'undefined') {
    channel = new BroadcastChannel(NAME)
  }
  return channel
}

export function publishCart(snapshot) {
  try {
    chan()?.postMessage({ kind: 'cart', snapshot: { ...snapshot, terminalId: displayTerminalId } })
  } catch {
    /* channel unavailable, ignore */
  }
}

export function receiptSnapshot(receipt, images = {}, groups = {}) {
  const show = (value) => money(value, receipt.currency)
  return {
    receipt: receipt.name,
    pending: Boolean(receipt.offline),
    company: receipt.company,
    customer: displayCustomerName(receipt.customer_name),
    date: receipt.posting_date,
    time: receipt.posting_time?.slice(0, 5),
    terminal: receipt.terminal,
    cashier: receipt.cashier,
    items: (receipt.items || []).map((line) => ({
      name: line.item_name, code: line.item_code, image: images[line.item_code],
      group: groups[line.item_code],
      qty: line.qty, uom: line.uom, rate: show(line.rate), amount: show(line.amount),
      discount: Number(line.line_discount_amount) > 0 ? show(line.line_discount_amount) : '',
      gross: Number(line.line_discount_amount) > 0 ? show(line.gross_amount) : '',
    })),
    count: receipt.item_count ?? receipt.items?.length ?? 0,
    subtotal: show(receipt.gross_total ?? receipt.total ?? receipt.grand_total),
    equivalent: receipt.base_grand_total && receipt.company_currency
      ? money(receipt.base_grand_total, receipt.company_currency) : '',
    savings: Number(receipt.total_savings) > 0 ? show(receipt.total_savings) : '',
    tax: Number(receipt.total_taxes_and_charges) ? show(receipt.total_taxes_and_charges) : '',
    taxes: (receipt.taxes || []).filter((row) => Number(row.tax_amount)).map((row) => ({
      label: row.description || row.account_head, amount: show(row.tax_amount),
    })),
    rounding: Number(receipt.rounding_adjustment) ? show(receipt.rounding_adjustment) : '',
    total: show(receipt.rounded_total || receipt.grand_total),
    paid: show(receipt.paid_amount),
    due: Number(receipt.on_account?.owed_on_sale) > 0 ? show(receipt.on_account.owed_on_sale) : '',
    cashback: Number(receipt.cashback_earned) > 0 ? show(receipt.cashback_earned) : '',
    change: Number(receipt.change_amount) > 0
      ? money(receipt.change_currency && receipt.change_currency !== receipt.currency
        ? receipt.base_change_amount ?? receipt.change_amount : receipt.change_amount,
      receipt.change_currency || receipt.currency) : '',
    payments: (receipt.payments || []).map((payment) => ({
      label: payment.mode_of_payment,
      amount: payment.currency && payment.tendered != null ? money(payment.tendered, payment.currency) : show(payment.amount),
    })),
    redeemed: receipt.loyalty_amount > 0 ? show(receipt.loyalty_amount) : '',
    earnedPoints: receipt.loyalty_points_earned || 0,
    savedChangePoints: receipt.loyalty_change_points || 0,
    pointsBalance: receipt.loyalty?.balance,
  }
}

// Main window: answer a display's request for the current state.
export function onDisplayRequest(handler) {
  const c = chan()
  if (!c) return () => {}
  const fn = (e) => {
    if (e.data?.kind === 'request') handler()
  }
  c.addEventListener('message', fn)
  return () => c.removeEventListener('message', fn)
}

// Display window: receive cart snapshots, and ask for the current one now.
export function onCart(handler) {
  const c = chan()
  if (!c) return () => {}
  const fn = (e) => {
    if (e.data?.kind === 'cart') handler(e.data.snapshot)
  }
  c.addEventListener('message', fn)
  try {
    c.postMessage({ kind: 'request' })
  } catch {
    /* ignore */
  }
  return () => c.removeEventListener('message', fn)
}
