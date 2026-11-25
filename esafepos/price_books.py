# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
"""Vend-style price books, a set of per-item override prices that apply for a
period, scoped by outlet and customer group, with a priority to break ties.

A price book is NOT a separate ERPNext Price List. It simply holds
(item -> price) rows on the POS Price Book itself: while the book is active
(validity window + outlet + customer group match), those items sell at the book
price; everything else keeps its normal selling price. When several books match,
the HIGHEST priority wins per item. Delivery-app and assigned customer price
lists take priority over price books, with outlet rates for unpriced items.
"""

import frappe
from frappe.utils import cint, flt, getdate, nowdate


def resolve_price_list(profile, customer_group=None, app_price_list=None, customer=None):
    """Delivery app, then an enabled customer list in the outlet currency,
    then the outlet list. Foreign customer lists use currency.own_list_prices."""
    if app_price_list:
        return app_price_list
    if customer:
        own = frappe.get_cached_value("Customer", customer, "default_price_list")
        if own:
            row = frappe.get_cached_value("Price List", own, ["enabled", "selling", "currency"], as_dict=True)
            outlet_currency = frappe.get_cached_value("Price List", profile.selling_price_list, "currency")
            if row and cint(row.enabled) and cint(row.selling) and row.currency == outlet_currency:
                return own
    return profile.selling_price_list


def get_price_map(item_codes, price_list, stock_uom_map=None, on_date=None, exact_uom=None):
    """Batch price lookup for a list of items on one price list.

    ONLY rows actually in effect today count. Without this an Item Price row
    that is future-dated takes effect immediately, an expired promo keeps
    applying, and a zero rate (a draft row, or a blank cell in an import)
    silently shadows the real price down to 0.00 at the till.
    Among the rows in effect the LATEST valid_from wins, so a scheduled sale
    price still beats the standing one."""
    if not item_codes or not price_list:
        return {}
    today = getdate(on_date or nowdate())
    filters = {"item_code": ["in", item_codes], "price_list": price_list, "selling": 1}
    if exact_uom:
        filters.update({"uom": exact_uom, "customer": ("is", "not set"), "supplier": ("is", "not set"),
                        "batch_no": ("is", "not set"), "packing_unit": ("in", [0, 1])})
    prices = frappe.get_all(
        "Item Price",
        filters=filters,
        fields=["item_code", "price_list_rate", "uom", "valid_from", "valid_upto"],
        order_by="valid_from asc",
    )
    price_map = {}
    for p in prices:
        if p.uom and stock_uom_map and p.uom != stock_uom_map.get(p.item_code):
            continue
        # not started yet / already expired
        if p.valid_from and today < getdate(p.valid_from):
            continue
        if p.valid_upto and today > getdate(p.valid_upto):
            continue
        # a 0.00 rate is an unfilled row, never a real selling price
        if flt(p.price_list_rate) <= 0:
            continue
        price_map[p.item_code] = p.price_list_rate
    return price_map


def book_overrides(profile, customer_group, item_codes, on_date=None):
    """{item_code: rate} from the active price books that match this outlet,
    customer group and date, highest priority wins per item."""
    if not item_codes:
        return {}
    today = getdate(on_date or nowdate())
    remaining = set(item_codes)
    overrides = {}
    books = frappe.get_all(
        "POS Price Book",
        filters={"status": "Active"},
        fields=["name", "priority", "valid_from", "valid_to"],
        order_by="priority desc, modified desc",
    )
    for book in books:
        if not remaining:
            break
        if book.valid_from and today < getdate(book.valid_from):
            continue
        if book.valid_to and today > getdate(book.valid_to):
            continue
        doc = frappe.get_cached_doc("POS Price Book", book.name)
        profiles = [r.pos_profile for r in (doc.pos_profiles or [])]
        from esafepos import scope

        if not scope.applies_to(doc.get("company"), profiles, profile.name):
            continue
        groups = [r.customer_group for r in (doc.customer_groups or [])]
        if groups and (not customer_group or customer_group not in groups):
            continue
        for row in (doc.get("items") or []):
            if row.item_code in remaining:
                # A 0.00 book rate is an UNFILLED cell (a blank column in an
                # imported sheet), not a giveaway price. Skip it so the item
                # falls through to the next book / the list price instead of
                # ringing up free.
                if flt(row.rate) <= 0:
                    continue
                overrides[row.item_code] = flt(row.rate)
                remaining.discard(row.item_code)
    return overrides


def effective_prices(profile, item_codes, customer_group=None, app_price_list=None, stock_uom_map=None, customer=None):
    """Delivery/customer list rates with outlet fallback for missing items.
    Price books apply when using the outlet's normal pricing."""
    base_list = resolve_price_list(profile, customer_group, app_price_list, customer)
    prices = get_price_map(item_codes, base_list, stock_uom_map)
    # Items unpriced on an app/customer list fall back to the outlet price.
    if base_list != profile.selling_price_list:
        missing = [c for c in item_codes if not prices.get(c)]
        if missing:
            for code, rate in get_price_map(missing, profile.selling_price_list, stock_uom_map).items():
                prices.setdefault(code, rate)
    if not app_price_list and base_list == profile.selling_price_list:
        for code, rate in book_overrides(profile, customer_group, item_codes, ).items():
            prices[code] = rate
    return prices


def standard_prices(profile, item_codes, stock_uom_map=None):
    """The plain selling price (no books, no apps), promotions on the
    'Standard Price' basis discount from this."""
    return get_price_map(item_codes, profile.selling_price_list, stock_uom_map)


def get_effective_price_map(item_codes, price_list, default_price_list, stock_uom_map=None):
    """Legacy helper kept for the delivery-app price editor: prices from
    `price_list`, falling back to `default_price_list` for unpriced items."""
    effective = get_price_map(item_codes, price_list, stock_uom_map)
    if default_price_list and default_price_list != price_list:
        missing = [code for code in item_codes if not effective.get(code)]
        if missing:
            for code, rate in get_price_map(missing, default_price_list, stock_uom_map).items():
                effective.setdefault(code, rate)
    return effective
