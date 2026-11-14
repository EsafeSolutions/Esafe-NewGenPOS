# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
"""What each payment was handed over in (0.66.0).

ERPNext keeps a payment row in the sale's currency only. Money handed over in
another currency (ZWG typed on a dollar sale, the till's "Amount in", 0.61.2; US
dollars on a ZWG sale) used to leave nothing but its worth in the sale's money,
so the reports could only say "US$5.00" where the customer gave ZWG 135.

`record` keeps the currency and the amount on the payment row
(`esafepos_paid_currency`, `esafepos_paid_amount` on Sales Invoice Payment), and
only when that amount is worth what the row books at the shift's rates, so a
figure from the till that does not add up is never stored. A sale in another
currency already holds its own money on the row (`amount`): `of_row` reads that
for a sale made before 0.66.0, as the receipt does.

The close's merge (ERPNext's POS Invoice Merge Log) reuses the first sale's row
for each method and adds up only `amount` and `base_amount`, so the merged Sales
Invoice would carry that one sale's figure as if it were the whole shift's:
`clear_on_merged` empties the two fields there. The sales keep theirs.
"""

from __future__ import annotations

import frappe
from frappe.utils import cint, flt

CURRENCY = "esafepos_paid_currency"
AMOUNT = "esafepos_paid_amount"


def has_fields() -> bool:
    try:
        return frappe.get_meta("Sales Invoice Payment").has_field(CURRENCY)
    except Exception:
        return False


def _handed(payment, ctx):
    """(currency, amount) the till says this payment was handed over in."""
    if ctx.foreign:
        return payment.get("tender_currency"), flt(payment.get("tender_amount"))
    return payment.get("typed_currency"), flt(payment.get("typed_amount"))


def record(invoice, payments, session_name=None):
    """Fill the two fields on each payment row of a sale being built. A method
    paid in two different currencies on one sale keeps neither (one row cannot
    hold both)."""
    from esafepos import currency

    ctx = invoice.flags.get("esafepos_currency")
    if not ctx or not has_fields():
        return
    company = invoice.company
    local = ctx.company_currency
    shop = set(currency.currency_rows() or [])

    def rate(code):
        if code == local:
            return 1.0
        if ctx.foreign and code == ctx.currency and flt(ctx.rate):
            return flt(ctx.rate)
        return flt(currency.shift_rate(session_name, code, company))

    per_mode = {}
    for p in payments or []:
        amount = flt(p.get("amount"))
        mode = p.get("mode_of_payment")
        if not amount or not mode:
            continue
        code, paid = _handed(p, ctx)
        if not code or code == local or paid <= 0:
            continue
        if code != ctx.currency and code not in shop:
            continue
        try:
            worth = paid * rate(code) / (rate(ctx.currency) or 1.0)
        except Exception:
            continue
        # Two decimals both ways at the till: a cent or half a percent apart.
        if abs(worth - amount) > max(0.05, abs(amount) * 0.005):
            continue
        per_mode.setdefault(mode, {})
        per_mode[mode][code] = flt(per_mode[mode].get(code)) + paid
    for row in invoice.payments or []:
        got = per_mode.get(row.mode_of_payment)
        if got and len(got) == 1:
            code, paid = next(iter(got.items()))
            row.set(CURRENCY, code)
            row.set(AMOUNT, flt(paid, 2))


def clear_on_merged(doc, method=None):
    """Sales Invoice before_insert: the close's merged invoice keeps neither
    field (see the module's note)."""
    if not cint(doc.get("is_consolidated")):
        return
    for row in doc.get("payments") or []:
        if row.get(CURRENCY) or row.get(AMOUNT):
            row.set(CURRENCY, None)
            row.set(AMOUNT, 0)


def of_row(row, company, company_currency):
    """(currency, amount) a payment row of a report was handed over in, or
    (None, 0) when that is the company's own money. `row` carries
    mode_of_payment, amount, currency (the invoice's) and, where the site has
    the fields, paid_currency and paid_amount."""
    from esafepos import currency

    code, paid = row.get("paid_currency"), flt(row.get("paid_amount"))
    if not code:
        # Before 0.66.0: a sale in another currency paid by a method of that
        # currency took its own money, as the receipt reads it.
        sale = row.get("currency")
        if sale and sale != company_currency and currency.mode_currency(row.mode_of_payment, company) == sale:
            code, paid = sale, flt(row.get("amount"))
    if not code or code == company_currency or not paid:
        return None, 0.0
    return code, paid
