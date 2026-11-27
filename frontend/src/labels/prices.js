// Label-only presentation: preserve the selling amount and non-zero fractions.
import { money, isolate, outletCurrency } from '../format.js'

export function labelMoney(amount, currency = outletCurrency()) {
  const value = Number(amount || 0)
  try {
    const formatter = new Intl.NumberFormat(undefined, { style: 'currency', currency })
    const parts = formatter.formatToParts(value)
    const fraction = parts.find(part => part.type === 'fraction')?.value
    const zero = formatter.formatToParts(0).find(part => part.type === 'fraction')?.value
    return isolate(parts.filter(part => !fraction || fraction !== zero || !['decimal', 'fraction'].includes(part.type)).map(part => part.value).join(''))
  } catch {
    return money(value, currency).replace(/\.00(?=[^\d]*$)/, '')
  }
}
