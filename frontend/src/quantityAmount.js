// Amount entry changes quantity, never the selling rate or discount.
import { parseMoney } from './format.js'

export const QUANTITY_STEP = 0.0001

export function quantityAmount(quantity, unitPrice) {
  const total = Number(quantity) * Number(unitPrice)
  return Number.isFinite(total) ? Math.round((total + Number.EPSILON) * 100) / 100 : null
}

export function quantityFromAmount(value, unitPrice, wholeQuantity = false) {
  const price = Number(unitPrice)
  if (!Number.isFinite(price) || price <= 0) return { error: 'price' }
  const amount = parseMoney(value)
  if (amount == null || amount <= 0) return { error: 'amount' }
  const raw = amount / price
  if (!Number.isFinite(raw) || raw * 10000 > Number.MAX_SAFE_INTEGER) return { error: 'large' }
  if (wholeQuantity && (raw < 1 || Math.abs(raw - Math.round(raw)) > 1e-9)) return { error: 'whole' }
  if (!wholeQuantity && raw < QUANTITY_STEP - 1e-12) return { error: 'small' }
  const quantity = wholeQuantity ? Math.round(raw) : Math.round((raw + Number.EPSILON) * 10000) / 10000
  return { quantity, amount: quantityAmount(quantity, price), requested: amount }
}
