"""Edit items and standing selling prices for the active outlet."""

from __future__ import annotations

import json
import math

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from esafepos.api.permissions import assert_outlet
from esafepos.item_units import conversions
from esafepos.price_books import get_price_map


def can_edit():
    return all(frappe.has_permission(dt, mode) for dt, mode in (
        ("Item", "read"), ("Item", "write"), ("Item Price", "read"), ("Item Price", "write"),
    ))


def _profile(pos_profile):
    if not pos_profile or not can_edit():
        frappe.throw(_("You cannot edit items and selling prices."), frappe.PermissionError)
    assert_outlet(pos_profile)
    return frappe.get_cached_doc("POS Profile", pos_profile)


@frappe.whitelist()
def search_items(pos_profile: str, search: str):
    _profile(pos_profile)
    term = (search or "").strip()
    item_code = frappe.db.get_value("Item Barcode", {"barcode": term}, "parent") if term else None
    conditions = ({"name": item_code} if item_code else {
        "name": ["like", "%" + term + "%"], "item_name": ["like", "%" + term + "%"],
    }) if term else None
    return frappe.get_list("Item", filters={"disabled": 0, "is_sales_item": 1, "has_variants": 0},
                           or_filters=conditions, fields=["name", "item_name", "stock_uom"],
                           order_by="item_name asc, name asc", limit_page_length=50)


def _standing_price(item_code, price_list, unit, stock_unit):
    rows = _standing_prices(item_code, price_list, unit)
    if not rows and unit == stock_unit:
        rows = _standing_prices(item_code, price_list, ("is", "not set"))
    if len(rows) > 1:
        frappe.throw(_("There is more than one standing price for {0}. Review its Item Prices in ERPNext.").format(unit))
    return rows[0] if rows else None


def _standing_prices(item_code, price_list, unit):
    rows = frappe.get_list("Item Price", filters={
        "item_code": item_code, "price_list": price_list, "selling": 1, "uom": unit,
        "customer": ("is", "not set"), "supplier": ("is", "not set"), "batch_no": ("is", "not set"),
        "valid_upto": ("is", "not set"), "packing_unit": ("in", [0, 1]),
    }, fields=["name", "price_list_rate", "valid_from"], limit_page_length=0)
    today = getdate(nowdate())
    active = sorted(
        (row for row in rows if not row.valid_from or getdate(row.valid_from) <= today),
        key=lambda row: getdate(row.valid_from) if row.valid_from else getdate("1900-01-01"),
        reverse=True,
    )
    return [row for row in active if (row.valid_from or "") == (active[0].valid_from or "")] if active else []


@frappe.whitelist()
def item_details(pos_profile: str, item_code: str):
    profile = _profile(pos_profile)
    item = frappe.get_doc("Item", item_code)
    item.check_permission("read")
    if item.disabled or not item.is_sales_item or item.has_variants:
        frappe.throw(_("This item is unavailable for sale."))
    stock_unit = item.stock_uom
    factors = {stock_unit: 1}
    if not item.has_serial_no:
        factors.update({unit: factor for (_, unit), factor in conversions([item_code]).items() if unit != stock_unit})
    price_list = profile.selling_price_list
    return {
        "item_code": item.name, "item_name": item.item_name, "stock_uom": stock_unit,
        "price_list": price_list, "currency": frappe.db.get_value("Price List", price_list, "currency"),
        "units": [
            {"uom": unit, "factor": factor,
             "price": flt(row.price_list_rate) if row else None,
             "active_price": get_price_map([item_code], price_list,
                                           {item_code: stock_unit} if unit == stock_unit else None,
                                           exact_uom=unit if unit != stock_unit else None).get(item_code)}
            for unit, factor in factors.items()
            for row in [_standing_price(item_code, price_list, unit, stock_unit)]
        ],
    }


@frappe.whitelist()
def save_item(pos_profile: str, item_code: str, item_name: str, prices: list | str):
    profile = _profile(pos_profile)
    item = frappe.get_doc("Item", item_code)
    item.check_permission("write")
    if item.disabled or not item.is_sales_item or item.has_variants:
        frappe.throw(_("This item is unavailable for sale."))
    name = (item_name or "").strip()
    if not name or len(name) > 140:
        frappe.throw(_("Enter an item name of 1 to 140 characters."))
    if isinstance(prices, str):
        prices = json.loads(prices)
    if not isinstance(prices, list) or not all(isinstance(row, dict) for row in prices):
        frappe.throw(_("Send a list of unit prices."))

    allowed_units = {item.stock_uom}
    if not item.has_serial_no:
        allowed_units.update(unit for _, unit in conversions([item_code]))
    pending = []
    seen = set()
    for row in prices:
        unit = row.get("uom")
        rate = flt(row.get("price"))
        if unit not in allowed_units or unit in seen or not math.isfinite(rate) or rate <= 0:
            frappe.throw(_("Use a configured unit and a price greater than zero."))
        seen.add(unit)
        price = _standing_price(item_code, profile.selling_price_list, unit, item.stock_uom)
        doc = frappe.get_doc("Item Price", price.name) if price else frappe.new_doc("Item Price")
        if not price:
            doc.update({"item_code": item_code, "price_list": profile.selling_price_list, "uom": unit})
        doc.price_list_rate = rate
        pending.append(doc)
    if item.item_name != name:
        item.item_name = name
        item.save()
    for doc in pending:
        doc.save()
    from esafepos.api import audit

    audit.log("Item updated in POS", detail=item.name, reference_doctype="Item",
              reference_name=item.name, pos_profile=profile.name)
    return item_details(pos_profile, item_code)
