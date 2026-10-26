# Copyright (c) 2026 Lumen Solutions
# SPDX-License-Identifier: AGPL-3.0-only
# "LumenPOS" is a trademark of Lumen Solutions. See TRADEMARKS.md.
"""Barcode and price labels (0.67.0).

The till's Labels screen prints shelf and product labels: the item's name, its
barcode and the price a walk-in customer pays at this outlet, tax included, the
way ERPNext works it out. Items come from a search or a scan, from an ERPNext
document that brought goods in (a Purchase Receipt, a Purchase Invoice that
updated stock, a Stock Entry), with its quantities, or from the prices changed
since a date. The barcode is the item's own (Item Barcode, an EAN or UPC first),
else the till prints its item code as Code 128.

A switch in Settings (General, Features) and the capability "Print labels" (open
until a shop names someone) gate every call here.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, getdate

from lumenpos.api import permissions

SWITCH = "enable_labels"
DOCTYPES = ("Purchase Receipt", "Purchase Invoice", "Stock Entry")
MAX_ITEMS = 500
# Item Barcode types a till prints as they are (EAN-13 / UPC-A), first choice.
SHELF_TYPES = ("EAN", "EAN-13", "EAN-12", "UPC-A", "UPC")


def enabled() -> bool:
    """On unless a shop switched it off (a site updated without its migrate
    has no such field yet: on, as it ships)."""
    try:
        stored = frappe.db.sql(
            "select value from tabSingles where doctype=%s and field=%s", ("LumenPOS Settings", SWITCH)
        )
    except Exception:
        return True
    return bool(cint(stored[0][0])) if stored else True


def can_print_labels(user=None) -> bool:
    return enabled() and permissions.allowed(permissions.PRINT_LABELS, user)


def _guard(pos_profile):
    if not can_print_labels():
        frappe.throw(_("You're not allowed to print labels."), frappe.PermissionError)
    permissions.assert_outlet(pos_profile)
    return frappe.get_cached_doc("POS Profile", pos_profile)


def _barcodes(codes):
    """The barcode each item prints with: its EAN or UPC first, else its first
    Item Barcode, else none (the till then prints the item code)."""
    rows = frappe.get_all(
        "Item Barcode",
        filters={"parent": ["in", codes], "parenttype": "Item"},
        fields=["parent", "barcode", "barcode_type", "idx"],
        order_by="idx asc",
    )
    best = {}
    for r in rows:
        shelf = (r.barcode_type or "").upper() in SHELF_TYPES
        have = best.get(r.parent)
        if not have or (shelf and not have[1]):
            best[r.parent] = (r.barcode, shelf)
    return {code: value[0] for code, value in best.items()}


def _tax_factors(profile, codes, prices):
    """What one unit costs with the outlet's tax, as a factor on its price,
    worked out by ERPNext: one invoice built (never saved) with every item at
    its price, so each line gets the item tax template ERPNext would give it;
    then, for each template, one line at 100 shows what tax adds. A charge of a
    fixed amount (Actual) belongs to a whole sale, not to a shelf price: left
    out. Without a tax template on the outlet the price is the price."""
    if not profile.get("taxes_and_charges") or not codes:
        return {code: 1.0 for code in codes}
    from lumenpos.api.layaway import _build_sale

    customer = profile.get("customer")
    lines = [{"item_code": c, "qty": 1, "rate": flt(prices.get(c)) or 1, "price_list_rate": flt(prices.get(c)) or 1}
             for c in codes]
    invoice = _build_sale(profile, customer, lines, None, with_taxes=True)
    template_of = {row.item_code: (row.get("item_tax_template") or "") for row in invoice.items}
    factor_of = {}
    for template in set(template_of.values()):
        sample = next(c for c, t in template_of.items() if t == template)
        one = _build_sale(profile, customer, [{"item_code": sample, "qty": 1, "rate": 100, "price_list_rate": 100}],
                          None, with_taxes=True)
        for row in one.taxes or []:
            if row.charge_type == "Actual":
                row.tax_amount = 0
        one.run_method("calculate_taxes_and_totals")
        factor_of[template] = flt(one.grand_total) / 100 if flt(one.grand_total) else 1.0
    return {code: factor_of.get(template_of.get(code, ""), 1.0) for code in codes}


def _equivalents(profile):
    """The other currencies the shop shows beside its own (Settings, General,
    Other currencies, Show the equivalent), each with its rate today."""
    from lumenpos import currency

    try:
        config = currency.client_config(profile, None)
    except Exception:
        return [], 1.0
    if not cint(config.get("enabled")):
        return [], 1.0
    shown = [
        {"currency": c["currency"], "rate": flt(c.get("rate"))}
        for c in config.get("currencies") or []
        if cint(c.get("show_equivalent")) and flt(c.get("rate"))
    ]
    return shown, flt(config.get("outlet_rate")) or 1.0


def _rows(profile, wanted):
    """Label rows for [(item_code, qty)], in that order, one row per item."""
    from lumenpos.price_books import effective_prices

    order = []
    qty = {}
    for code, n in wanted:
        if not code:
            continue
        if code not in qty:
            order.append(code)
            qty[code] = 0
        qty[code] += max(0, cint(n))
    order = order[:MAX_ITEMS]
    if not order:
        return []
    items = {
        d.name: d
        for d in frappe.get_all(
            "Item",
            filters={"name": ["in", order]},
            fields=["name", "item_name", "stock_uom", "disabled", "is_sales_item"],
        )
    }
    order = [c for c in order if c in items]
    uom_map = {c: items[c].stock_uom for c in order}
    prices = effective_prices(profile, order, stock_uom_map=uom_map)
    factors = _tax_factors(profile, order, prices)
    barcodes = _barcodes(order)
    shown, outlet_rate = _equivalents(profile)
    from lumenpos import currency

    ccy = profile.get("currency") or currency.company_currency(profile.company)
    out = []
    for code in order:
        price = flt(prices.get(code))
        with_tax = flt(price * factors.get(code, 1.0), 2)
        out.append(
            {
                "item_code": code,
                "item_name": items[code].item_name or code,
                "uom": items[code].stock_uom,
                "barcode": barcodes.get(code) or "",
                "price": flt(price, 2),
                "price_with_tax": with_tax,
                "currency": ccy,
                "equivalents": [
                    {"currency": e["currency"], "amount": flt(with_tax * outlet_rate / e["rate"], 2)} for e in shown
                ],
                "qty": qty[code] or 1,
                "unpriced": not price,
                "disabled": cint(items[code].disabled),
            }
        )
    return out


def _parse(items):
    if isinstance(items, str):
        items = json.loads(items or "[]")
    return [(row.get("item_code"), row.get("qty", 1)) for row in items or [] if isinstance(row, dict)]


@frappe.whitelist()
def items(pos_profile: str, items: str | list | None = None):
    """Label rows for the items given ([{item_code, qty}])."""
    profile = _guard(pos_profile)
    return {"rows": _rows(profile, _parse(items)), "company": profile.company}


@frappe.whitelist()
def from_document(pos_profile: str, doctype: str, name: str):
    """The items a document brought in, with their quantities in the stock
    unit: a Purchase Receipt, a Purchase Invoice that updated stock, or a
    Stock Entry. Only a document of a company this person may see, and not a
    cancelled one."""
    profile = _guard(pos_profile)
    if doctype not in DOCTYPES:
        frappe.throw(_("Labels come from a Purchase Receipt, a Purchase Invoice or a Stock Entry."))
    doc = frappe.db.get_value(doctype, name, ["name", "company", "docstatus"], as_dict=True)
    if not doc:
        frappe.throw(_("{0} {1} was not found.").format(_(doctype), name))
    allowed = permissions.allowed_companies()
    if allowed is not None and doc.company not in allowed:
        frappe.throw(_("You're not allowed to see {0}.").format(doc.company), frappe.PermissionError)
    if cint(doc.docstatus) == 2:
        frappe.throw(_("{0} {1} is cancelled.").format(_(doctype), name))
    child = "Stock Entry Detail" if doctype == "Stock Entry" else doctype + " Item"
    qty_field = "transfer_qty" if doctype == "Stock Entry" else "stock_qty"
    lines = frappe.get_all(
        child,
        filters={"parent": name, "parenttype": doctype},
        fields=["item_code", qty_field, "idx"],
        order_by="idx asc",
    )
    wanted = [(r.item_code, int(round(flt(r.get(qty_field))))) for r in lines if flt(r.get(qty_field)) > 0]
    return {"rows": _rows(profile, wanted), "company": profile.company, "document": name}


@frappe.whitelist()
def price_changes(pos_profile: str, since: str):
    """Every item whose selling price on this outlet's price list was set or
    changed since a date: one label each."""
    profile = _guard(pos_profile)
    start = get_datetime(getdate(since))
    codes = frappe.get_all(
        "Item Price",
        filters={"price_list": profile.selling_price_list, "selling": 1, "modified": [">=", start]},
        order_by="modified desc",
        limit_page_length=MAX_ITEMS * 2,
        pluck="item_code",
    )
    once = list(dict.fromkeys(codes))
    return {"rows": _rows(profile, [(c, 1) for c in once]), "company": profile.company}


@frappe.whitelist()
def documents(pos_profile: str, doctype: str, search: str = ""):
    """The latest documents of a kind to take labels from (not cancelled), of
    the companies this person may see: name, date, supplier or purpose."""
    _guard(pos_profile)
    if doctype not in DOCTYPES:
        frappe.throw(_("Labels come from a Purchase Receipt, a Purchase Invoice or a Stock Entry."))
    filters = {"docstatus": ["<", 2]}
    allowed = permissions.allowed_companies()
    if allowed is not None:
        filters["company"] = ["in", sorted(allowed)]
    if doctype == "Purchase Invoice":
        filters["update_stock"] = 1
    party = "stock_entry_type" if doctype == "Stock Entry" else "supplier"
    or_filters = None
    if search:
        or_filters = {"name": ["like", f"%{search}%"], party: ["like", f"%{search}%"]}
    rows = frappe.get_all(
        doctype,
        filters=filters,
        or_filters=or_filters,
        fields=["name", "posting_date", party, "docstatus"],
        order_by="posting_date desc, creation desc",
        limit_page_length=20,
    )
    return [{"name": r.name, "date": str(r.posting_date), "party": r.get(party) or "", "draft": not cint(r.docstatus)} for r in rows]
