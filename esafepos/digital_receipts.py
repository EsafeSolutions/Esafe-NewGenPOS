# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
"""Signed, customer-safe links for submitted POS invoices.

The public page never accepts an invoice name by itself.  A short HMAC made
with the site's encryption key covers the doctype, invoice and expiry.  That
keeps Desk permissions and session cookies out of links sent to customers,
while a cancelled document immediately stops rendering.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.utils import cint, flt, fmt_money, get_url


LINK_LIFETIME_SECONDS = 365 * 24 * 60 * 60
TYPE_CODES = {"P": "POS Invoice", "S": "Sales Invoice"}
DOCTYPE_CODES = {value: key for key, value in TYPE_CODES.items()}


class InvalidReceiptLink(Exception):
    pass


def _secret():
    secret = frappe.conf.get("encryption_key")
    if not secret:
        frappe.throw(_("The site encryption key is missing, so a secure invoice link cannot be made."))
    return str(secret).encode("utf-8")


def _signature(type_code, invoice, expires):
    payload = "\n".join((type_code, invoice, str(expires))).encode("utf-8")
    # 128 bits is ample for an unguessable customer link and keeps SMS URLs
    # short enough to avoid an unnecessary extra message segment.
    digest = hmac.new(_secret(), payload, hashlib.sha256).digest()[:16]
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def invoice_doctype(invoice):
    if frappe.db.exists("Sales Invoice", invoice):
        return "Sales Invoice"
    if frappe.db.exists("POS Invoice", invoice):
        return "POS Invoice"
    return None


def make_link(doc, lifetime=LINK_LIFETIME_SECONDS):
    type_code = DOCTYPE_CODES.get(doc.doctype)
    if not type_code:
        frappe.throw(_("{0} is not a sale invoice.").format(doc.doctype))
    expires = int(time.time()) + cint(lifetime or LINK_LIFETIME_SECONDS)
    query = {
        "t": type_code,
        "i": doc.name,
        "e": expires,
        "s": _signature(type_code, doc.name, expires),
    }
    return "{0}/einvoice?{1}".format(get_url().rstrip("/"), urlencode(query))


def message_for(doc, url):
    if cint(doc.get("is_return")):
        return _("Your credit note {0} from {1}: {2}").format(doc.name, doc.company, url)
    return _("Your invoice {0} from {1}: {2}").format(doc.name, doc.company, url)


def share_details(doc):
    url = make_link(doc)
    mobile = doc.get("contact_mobile") or doc.get("contact_phone") or ""
    if not mobile and doc.get("customer"):
        mobile = frappe.db.get_value("Customer", doc.customer, "mobile_no") or ""
    return {"url": url, "message": message_for(doc, url), "mobile": mobile}


def _verified_document(type_code, invoice, expires, signature):
    doctype = TYPE_CODES.get(type_code)
    if not doctype or not invoice or not signature:
        raise InvalidReceiptLink()
    try:
        expires = int(expires)
    except (TypeError, ValueError):
        raise InvalidReceiptLink()
    if expires < int(time.time()):
        raise InvalidReceiptLink()
    expected = _signature(type_code, invoice, expires)
    if not hmac.compare_digest(expected, str(signature)):
        raise InvalidReceiptLink()
    if not frappe.db.exists(doctype, invoice):
        raise InvalidReceiptLink()
    doc = frappe.get_doc(doctype, invoice)
    if cint(doc.docstatus) != 1:
        raise InvalidReceiptLink()
    return doc


def _safe_logo(value):
    value = (value or "").strip()
    if value.startswith(
        (
            "/files/",
            "https://",
            "http://",
            "data:image/png",
            "data:image/jpeg",
            "data:image/webp",
            "data:image/gif",
        )
    ):
        return value
    return ""


def _money(value, currency):
    return fmt_money(flt(value), currency=currency)


def _qty(value):
    return ("{0:.6f}".format(flt(value))).rstrip("0").rstrip(".") or "0"


def public_receipt(type_code, invoice, expires, signature):
    """Return only fields intended for a customer's public invoice page."""
    doc = _verified_document(type_code, invoice, expires, signature)
    from esafepos.api.settings import effective_receipt

    settings = effective_receipt(doc.get("pos_profile")) if doc.get("pos_profile") else {}
    currency = doc.get("currency") or frappe.db.get_default("currency")
    payable = doc.get("rounded_total") or doc.get("grand_total")
    show_item_code = cint(settings.get("receipt_show_item_code"))
    items = []
    for row in doc.get("items") or []:
        list_rate = flt(row.get("price_list_rate") or row.get("rate"))
        amount = flt(row.get("amount"))
        saving = max(0, flt(list_rate * flt(row.get("qty")) - amount))
        items.append(
            {
                "item_name": row.get("item_name") or row.get("item_code"),
                "item_code": row.get("item_code") if show_item_code else "",
                "qty": _qty(row.get("qty")),
                "rate": _money(row.get("rate"), currency),
                "amount": _money(amount, currency),
                "saving": _money(saving, currency) if saving else "",
            }
        )

    taxes = [
        {
            "description": row.get("description") or row.get("account_head") or _("Tax"),
            "amount": _money(row.get("tax_amount"), currency),
        }
        for row in (doc.get("taxes") or [])
        if flt(row.get("tax_amount"))
    ]
    payments = []
    if cint(settings.get("receipt_show_payments")):
        payments = [
            {
                "mode": row.get("mode_of_payment"),
                "amount": _money(row.get("amount"), currency),
            }
            for row in (doc.get("payments") or [])
            if flt(row.get("amount"))
        ]

    tax_id = settings.get("receipt_tax_id")
    if not tax_id:
        tax_id = frappe.get_cached_value("Company", doc.company, "tax_id") or ""
    owed = 0
    if not cint(doc.get("is_return")):
        try:
            from esafepos import credit_sales

            owed = flt((credit_sales.receipt_facts(doc) or {}).get("owed_on_sale"))
        except Exception:
            owed = max(0, flt(doc.get("outstanding_amount")))

    return {
        "name": doc.name,
        "is_return": cint(doc.get("is_return")),
        "return_against": doc.get("return_against") or "",
        "company": doc.company,
        "customer_name": doc.get("customer_name") or "",
        "posting_date": str(doc.get("posting_date") or ""),
        "posting_time": str(doc.get("posting_time") or "").split(".")[0],
        "currency": currency,
        "items": items,
        "taxes": taxes,
        "payments": payments,
        "net_total": _money(doc.get("net_total"), currency),
        "discount": _money(abs(flt(doc.get("discount_amount"))), currency) if flt(doc.get("discount_amount")) else "",
        "grand_total": _money(payable, currency),
        "owed": _money(owed, currency) if owed else "",
        "logo": _safe_logo(settings.get("receipt_logo")),
        "header": settings.get("receipt_header") or "",
        "footer": settings.get("receipt_footer") or "",
        "address": settings.get("receipt_address") if cint(settings.get("receipt_show_address")) else "",
        "tax_id": tax_id if cint(settings.get("receipt_show_tax_id")) else "",
        "terms": settings.get("receipt_terms") if cint(settings.get("receipt_show_terms")) else "",
    }
