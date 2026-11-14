# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
"""ESC/POS receipt printing for network thermal printers (RAW TCP port 9100).

No third-party dependencies: the byte stream is built by hand. Works with the
vast majority of Epson-compatible thermal printers. The printer is configured
per POS Profile via the custom fields `esafepos_printer_ip` / `esafepos_printer_port`
(created by esafepos.install). If no printer is configured the client falls back
to browser printing.

Note: the *bench server* opens the socket, so the printer must be reachable
from where Frappe runs. On cloud-hosted sites use the browser-print fallback.
"""

from __future__ import annotations

import socket

import frappe
from frappe import _
from frappe.utils import cint, flt

from esafepos.api.sales import get_receipt

ESC = b"\x1b"
GS = b"\x1d"

INIT = ESC + b"@"
ALIGN_LEFT = ESC + b"a\x00"
ALIGN_CENTER = ESC + b"a\x01"
BOLD_ON = ESC + b"E\x01"
BOLD_OFF = ESC + b"E\x00"
DOUBLE_SIZE = GS + b"!\x11"
NORMAL_SIZE = GS + b"!\x00"
FEED_CUT = b"\n\n\n\n" + GS + b"V\x42\x00"
KICK_DRAWER = ESC + b"p\x00\x19\xfa"

WIDTH = 42  # characters per line on a typical 80mm printer


@frappe.whitelist()
def print_receipt(invoice: str, open_drawer: int | bool | str = 0, reprint: int | bool | str = 0):
    from esafepos.api import permissions

    # A cashier always prints the receipt for the sale they just made. Printing
    # one AGAIN later (and with it, opening the drawer) is the thing a shop may
    # want to keep to a supervisor, so only that is gated.
    if cint(reprint) and not permissions.can_reprint():
        frappe.throw(_("You are not allowed to reprint a receipt"), frappe.PermissionError)
    if cint(reprint):
        _log_reprint(invoice, _("{0} printed again on the receipt printer"))
    receipt = get_receipt(invoice)
    # A Sales Invoice outlet prints too: the sale's own doctype, not POS
    # Invoice only (it found no outlet and refused every such receipt).
    from esafepos.api.sales import _doctype_of

    profile = frappe.db.get_value(_doctype_of(invoice), invoice, "pos_profile")
    ip = frappe.db.get_value("POS Profile", profile, "esafepos_printer_ip")
    port = frappe.db.get_value("POS Profile", profile, "esafepos_printer_port") or 9100
    if not ip:
        frappe.throw(_("No receipt printer configured on POS Profile {0}").format(profile))

    data = build_receipt_bytes(receipt, open_drawer=int(open_drawer))
    _send(ip, int(port), data)
    return {"printed": True}


@frappe.whitelist()
def allow_reprint(invoice: str):
    """A receipt printed again from the browser or ERPNext's print view: the
    same rule as on the receipt printer, asked by the till BEFORE it prints,
    and written to the audit log (0.60.0). Until then only a network printer's
    reprint was checked, and a refused one fell back to the browser, so in
    practice anyone could print a receipt again. Asked by a shop in Nigeria
    (2026-10-03): after the cashier's first print, copies only by a
    supervisor."""
    from esafepos.api import permissions
    from esafepos.api.sales import _doctype_of

    if not permissions.can_reprint():
        frappe.throw(_("You are not allowed to reprint a receipt"), frappe.PermissionError)
    frappe.get_doc(_doctype_of(invoice), invoice).check_permission("read")
    _log_reprint(invoice, _("{0} printed again in the browser"))
    return {"allowed": 1}


def _log_reprint(invoice, message):
    from esafepos.api import audit
    from esafepos.api.sales import _doctype_of

    doctype = _doctype_of(invoice)
    audit.log(
        audit.REPRINT,
        detail=message.format(invoice),
        reference_doctype=doctype,
        reference_name=invoice,
        pos_profile=frappe.db.get_value(doctype, invoice, "pos_profile"),
    )


def _send(ip, port, data):
    try:
        with socket.create_connection((ip, port), timeout=5) as sock:
            sock.sendall(data)
    except OSError as e:
        frappe.throw(_("Could not reach printer at {0}:{1} ({2})").format(ip, port, str(e)))


def build_receipt_bytes(receipt, open_drawer=0):
    out = bytearray(INIT)
    if open_drawer:
        out += KICK_DRAWER

    settings = receipt.get("receipt_settings") or {}
    width = 32 if settings.get("receipt_paper_width") == "58mm" else WIDTH
    if (settings.get("receipt_template") or "").lower() == "retail":
        out += _retail_receipt_body(receipt, width)
        out += FEED_CUT
        return bytes(out)

    out += ALIGN_CENTER + BOLD_ON + DOUBLE_SIZE
    out += _text(receipt["company"]) + b"\n"
    out += NORMAL_SIZE + BOLD_OFF
    out += _text(receipt["name"]) + b"\n"
    out += _text(f"{receipt['posting_date']} {str(receipt['posting_time']).split('.')[0]}") + b"\n"
    out += _text(receipt["customer_name"] or "") + b"\n"
    # The selling company's VAT number (its receipt's, else the company's own),
    # when the shop shows it on receipts.
    receipt_settings = receipt.get("receipt_settings") or {}
    tax_id = receipt_settings.get("receipt_tax_id")
    if tax_id and receipt_settings.get("receipt_show_tax_id"):
        out += _text(f"VAT {tax_id}") + b"\n"
    out += ALIGN_LEFT + _line() + b"\n"

    for item in receipt["items"]:
        out += _text(item["item_name"][:WIDTH]) + b"\n"
        qty_part = f"  {_num(item['qty'])} x {_num(item['rate'])}"
        out += _text(_pad(qty_part, _num(item["amount"]))) + b"\n"

    out += _line() + b"\n"
    if receipt.get("discount_amount"):
        out += _text(_pad("Discount", "-" + _num(receipt["discount_amount"]))) + b"\n"
    for tax in receipt.get("taxes", []):
        out += _text(_pad(tax["description"][: WIDTH - 12], _num(tax["tax_amount"]))) + b"\n"

    out += BOLD_ON
    total = receipt.get("rounded_total") or receipt["grand_total"]
    out += _text(_pad("TOTAL", f"{receipt['currency']} {_num(total)}")) + b"\n"
    out += BOLD_OFF
    # A sale in another currency (esafepos.currency): its local value and rate,
    # each tender in its own money, and the change in the money it was given
    # in: local, or the sale's own when it came from that currency's drawer.
    local = receipt.get("company_currency")
    foreign = bool(local and receipt.get("currency") != local and receipt.get("base_grand_total") is not None)
    if foreign:
        out += _text(_pad(f"= {local}", _num(receipt["base_grand_total"]))) + b"\n"
        out += _text(f"1 {receipt['currency']} = {flt(receipt.get('conversion_rate')):g} {local}") + b"\n"

    for payment in receipt.get("payments", []):
        if foreign and payment.get("currency"):
            shown = f"{payment['currency']} {_num(payment.get('tendered'))}"
        else:
            shown = _num(payment["amount"])
        out += _text(_pad(payment["mode_of_payment"], shown)) + b"\n"
    if receipt.get("loyalty_amount"):
        out += _text(_pad("Loyalty points", _num(receipt["loyalty_amount"]))) + b"\n"
    if receipt.get("change_amount"):
        if foreign and receipt.get("change_currency") != receipt.get("currency"):
            change = f"{local} {_num(receipt.get('base_change_amount'))}"
        elif foreign:
            change = f"{receipt['currency']} {_num(receipt['change_amount'])}"
        else:
            change = _num(receipt["change_amount"])
        out += _text(_pad("Change", change)) + b"\n"
    # A sale on account (esafepos.credit_sales, 0.60.0): what stays owed, on
    # this sale and in all, and a line for the customer to sign.
    owed = receipt.get("on_account") or {}
    if owed and not receipt.get("is_return"):
        out += BOLD_ON + _text(_pad("Owed on this sale", _num(owed.get("owed_on_sale")))) + b"\n" + BOLD_OFF
        if owed.get("owed_total") is not None:
            out += _text(_pad("Owed in all", _num(owed.get("owed_total")))) + b"\n"
        out += b"\n" + _text("Signature: ______________________") + b"\n"
    elif owed:
        out += _text(_pad("Off what is owed", _num(abs(flt(owed.get("amount")))))) + b"\n"

    promos = receipt.get("applied_promotions") or []
    if promos:
        out += _line() + b"\n"
        for promo in promos:
            out += _text(f"* {promo['title']} (saved {_num(promo['savings'])})") + b"\n"
    if receipt.get("loyalty_points_earned"):
        out += _text(f"Points earned: {receipt['loyalty_points_earned']}") + b"\n"

    out += ALIGN_CENTER + b"\n" + _text("Thank you!") + b"\n"
    out += FEED_CUT
    return bytes(out)


def _retail_receipt_body(receipt, width):
    """The same supermarket-style breakdown as the browser receipt.

    ESC/POS cannot reliably print an arbitrary uploaded logo, so the raw
    printer keeps the identity in text while browser printing can use the
    configured image.  All monetary facts come from ``get_receipt`` so neither
    path recomputes a discount, tax, or loyalty balance independently.
    """
    settings = receipt.get("receipt_settings") or {}
    out = bytearray()
    out += ALIGN_CENTER + BOLD_ON + DOUBLE_SIZE
    out += _text(receipt.get("company") or "") + b"\n"
    out += NORMAL_SIZE + BOLD_OFF
    for line in (
        settings.get("receipt_header") if settings.get("receipt_header") else None,
        settings.get("receipt_address")
        if settings.get("receipt_show_address") and settings.get("receipt_address")
        else None,
        "VAT " + settings.get("receipt_tax_id")
        if settings.get("receipt_show_tax_id") and settings.get("receipt_tax_id")
        else None,
    ):
        if line:
            for part in str(line).splitlines() or [line]:
                out += _text(part[:width]) + b"\n"

    if receipt.get("is_return"):
        out += BOLD_ON + _text("REFUND") + BOLD_OFF + b"\n"
    out += ALIGN_LEFT
    out += _text(_pad("INVOICE #", receipt.get("name") or "", width)) + b"\n"
    when = "{} {}".format(
        receipt.get("posting_date") or "", str(receipt.get("posting_time") or "").split(".")[0]
    ).strip()
    if when:
        out += _text(_pad("TIME", when, width)) + b"\n"
    if receipt.get("customer_name"):
        customer = receipt["customer_name"]
        if receipt.get("customer_phone"):
            customer += " / " + receipt["customer_phone"]
        out += _text(_pad("CUSTOMER", customer, width)) + b"\n"
    if receipt.get("cashier"):
        out += _text(_pad("CASHIER", receipt["cashier"], width)) + b"\n"
    if receipt.get("terminal"):
        out += _text(_pad("TERMINAL", receipt["terminal"], width)) + b"\n"
    if receipt.get("return_against"):
        out += _text(_pad("AGAINST", receipt["return_against"], width)) + b"\n"

    out += _line(width) + b"\n"
    out += _text(_retail_columns("QTY", "MRP", "DISC", "AMOUNT", width)) + b"\n"
    out += _line(width) + b"\n"
    for index, item in enumerate(receipt.get("items") or []):
        name = "{}) {}".format(index + 1, item.get("item_name") or item.get("item_code") or "")
        out += _text(name[:width]) + b"\n"
        out += _text(
            _retail_columns(
                _num(item.get("qty")),
                _num(item.get("price_list_rate")),
                _num(item.get("line_discount_amount")),
                _num(item.get("amount")),
                width,
            )
        ) + b"\n"

    out += _line(width) + b"\n"
    out += _text(_pad("GROSS TOTAL", _num(receipt.get("gross_total")), width)) + b"\n"
    savings = flt(receipt.get("total_savings"))
    if savings > 0 and not receipt.get("is_return"):
        out += BOLD_ON + _text(_pad("DISCOUNT", "-" + _num(savings), width)) + BOLD_OFF + b"\n"
    for tax in receipt.get("taxes") or []:
        out += _text(_pad((tax.get("description") or "TAX")[: width - 12], _num(tax.get("tax_amount")), width)) + b"\n"
    rounding = flt(receipt.get("rounding_adjustment"))
    if rounding:
        out += _text(_pad("ROUNDING", _num(rounding), width)) + b"\n"
    out += BOLD_ON
    total = receipt.get("rounded_total") or receipt.get("grand_total")
    out += _text(_pad("NET TOTAL", "{} {}".format(receipt.get("currency") or "", _num(total)).strip(), width)) + b"\n"
    out += BOLD_OFF

    for payment in receipt.get("payments") or []:
        out += _text(_pad(payment.get("mode_of_payment") or "PAID", _num(payment.get("amount")), width)) + b"\n"
    if receipt.get("loyalty_amount"):
        out += _text(_pad("LOYALTY REDEEMED", _num(receipt.get("loyalty_amount")), width)) + b"\n"
    if receipt.get("change_amount"):
        out += _text(_pad("CHANGE", _num(receipt.get("change_amount")), width)) + b"\n"
    out += _text(_pad("ITEMS", receipt.get("item_count") or len(receipt.get("items") or []), width)) + b"\n"
    out += _text(_pad("TOTAL QTY", _num(receipt.get("total_qty")), width)) + b"\n"

    loyalty = receipt.get("loyalty") or {}
    if loyalty:
        out += _line(width) + b"\n"
        out += ALIGN_CENTER + BOLD_ON + _text("LOYALTY POINTS") + BOLD_OFF + b"\n" + ALIGN_LEFT
        if receipt.get("loyalty_points_earned"):
            out += _text(_pad("POINTS EARNED", receipt.get("loyalty_points_earned"), width)) + b"\n"
        if receipt.get("loyalty_points_redeemed"):
            out += _text(_pad("POINTS REDEEMED", receipt.get("loyalty_points_redeemed"), width)) + b"\n"
        out += BOLD_ON + _text(_pad("POINTS BALANCE", loyalty.get("balance", 0), width)) + BOLD_OFF + b"\n"

    if savings > 0 and not receipt.get("is_return"):
        out += _line(width) + b"\n"
        out += ALIGN_CENTER + BOLD_ON + _text("YOU SAVED " + _num(savings)) + BOLD_OFF + b"\n" + ALIGN_LEFT
    if settings.get("receipt_terms") and settings.get("receipt_show_terms"):
        out += _line(width) + b"\n"
        for part in str(settings["receipt_terms"]).splitlines() or [settings["receipt_terms"]]:
            out += _text(part[:width]) + b"\n"
    out += ALIGN_CENTER + b"\n"
    if settings.get("receipt_footer"):
        out += _text(settings["receipt_footer"][:width]) + b"\n"
    out += _text("Thank you!") + b"\n"
    return out


def _retail_columns(qty, mrp, discount, amount, width):
    """Right-align the four retail columns within a 58 mm or 80 mm line."""
    amount_width = 10 if width >= 42 else 8
    price_width = 9 if width >= 42 else 7
    discount_width = 9 if width >= 42 else 7
    qty_width = width - amount_width - price_width - discount_width - 3
    values = (qty, mrp, discount, amount)
    widths = (qty_width, price_width, discount_width, amount_width)
    return " ".join(_right(value, size) for value, size in zip(values, widths))


def _right(value, width):
    value = str(value)
    return value[-width:].rjust(width)


def _text(value):
    # Thermal printers default to single-byte codepages; replace anything
    # exotic rather than printing garbage.
    return str(value).encode("ascii", errors="replace")


def _line(width=WIDTH):
    return b"-" * width


def _pad(left, right, width=WIDTH):
    right = str(right)
    space = max(1, width - len(left) - len(right))
    return f"{left}{' ' * space}{right}"


def _num(value):
    return f"{flt(value):,.2f}"
