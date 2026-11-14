# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
import frappe

from esafepos.digital_receipts import InvalidReceiptLink, public_receipt


no_cache = 1


def get_context(context):
    context.no_cache = 1
    context.no_breadcrumbs = True
    context.valid = False
    try:
        context.receipt = public_receipt(
            frappe.form_dict.get("t"),
            frappe.form_dict.get("i"),
            frappe.form_dict.get("e"),
            frappe.form_dict.get("s"),
        )
        context.valid = True
        context.title = context.receipt["name"]
    except InvalidReceiptLink:
        context.title = "Invoice link unavailable"
    return context
