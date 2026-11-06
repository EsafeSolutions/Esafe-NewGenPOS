# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
"""Display-only receipt switches, shared by settings and thermal printing."""

RECEIPT_OPTION_DEFAULTS = {
    "receipt_show_line_discount": 1,
    "receipt_show_mrp": 1,
    "receipt_show_gross_total": 1,
    "receipt_show_total_discount": 1,
    "receipt_show_savings": 1,
    "receipt_show_item_count": 1,
    "receipt_show_total_qty": 1,
    "receipt_show_loyalty": 1,
    "receipt_show_cashier": 1,
    "receipt_show_terminal": 1,
}


def receipt_option_enabled(settings, field):
    value = settings.get(field)
    if value is None:
        value = RECEIPT_OPTION_DEFAULTS.get(field, 1)
    return value not in (0, False, "0", "false", "", None)


def receipt_options(settings):
    return {field: int(receipt_option_enabled(settings, field)) for field in RECEIPT_OPTION_DEFAULTS}
