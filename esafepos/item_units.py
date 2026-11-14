"""ERPNext selling units and explicit alternate-unit prices."""

import frappe
from frappe.utils import flt


def conversions(codes):
    if not codes:
        return {}
    return {
        (row.parent, row.uom): flt(row.conversion_factor)
        for row in frappe.get_all(
            "UOM Conversion Detail", filters={"parenttype": "Item", "parent": ["in", list(codes)]},
            fields=["parent", "uom", "conversion_factor"],
        )
        if flt(row.conversion_factor) > 0
    }


def prices_by_unit(units, price_list):
    from esafepos.price_books import get_price_map

    return {
        (code, unit): rate
        for unit in {unit for _, unit in units}
        for code, rate in get_price_map(
            [code for code, candidate in units if candidate == unit], price_list,
            exact_uom=unit,
        ).items()
    }


def add_options(items, price_list):
    details = {item["item_code"]: item for item in items if not item.get("has_serial_no")}
    units = conversions(details)
    units = {(code, unit): factor for (code, unit), factor in units.items()
             if unit != details[code]["stock_uom"]}
    rates = prices_by_unit(units, price_list)
    whole = set(frappe.get_all("UOM", filters={
        "name": ["in", sorted({unit for _, unit in units})], "must_be_whole_number": 1,
    }, pluck="name")) if units else set()
    for (code, unit), factor in units.items():
        item = details[code]
        rate = rates.get((code, unit))
        if rate:
            item.setdefault("selling_units", []).append({
                "uom": unit, "factor": factor, "price": rate, "whole_qty": unit in whole,
            })
