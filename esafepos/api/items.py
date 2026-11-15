"""Edit items and standing selling prices for the active outlet."""

from __future__ import annotations

import base64
import binascii
import json
import math
from io import BytesIO

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from esafepos.api.permissions import ITEM_PRICE_EDIT, allowed, assert_outlet
from esafepos.item_units import conversions
from esafepos.price_books import get_price_map

MAX_IMAGE_BYTES = 5 * 1024 * 1024


def _can_edit_prices():
    return (
        allowed(ITEM_PRICE_EDIT)
        and frappe.has_permission("Price List", "read")
        and frappe.has_permission("Item Price", "read")
        and (frappe.has_permission("Item Price", "write") or frappe.has_permission("Item Price", "create"))
    )


def can_edit():
    return frappe.has_permission("Item", "read") and (frappe.has_permission("Item", "write") or _can_edit_prices())


def _profile(pos_profile):
    if not pos_profile or not can_edit():
        frappe.throw(_("You do not have access to the Items editor."), frappe.PermissionError)
    assert_outlet(pos_profile)
    return frappe.get_cached_doc("POS Profile", pos_profile)


@frappe.whitelist()
def editor_options(pos_profile: str):
    profile = _profile(pos_profile)
    return {
        "item_groups": _filter_names("Item Group"),
        "brands": _filter_names("Brand"),
        "price_lists": _selling_lists() if _can_edit_prices() else [],
        "default_price_list": profile.selling_price_list,
    }


def _filter_names(doctype):
    if not frappe.has_permission(doctype, "read"):
        return []
    return frappe.get_list(doctype, pluck="name", order_by="name asc", limit_page_length=0)


def _selling_lists():
    return frappe.get_list("Price List", filters={"enabled": 1, "selling": 1},
                           fields=["name", "currency"], order_by="name asc", limit_page_length=0)


@frappe.whitelist()
def search_items(pos_profile: str, search: str, start: int | str = 0, limit: int | str = 50,
                 item_group: str = "", brand: str = ""):
    _profile(pos_profile)
    from esafepos.api.catalog import item_groups_under

    term = (search or "").strip()
    item_code = frappe.db.get_value("Item Barcode", {"barcode": term}, "parent") if term else None
    filters = {"disabled": 0, "is_sales_item": 1, "has_variants": 0}
    groups = item_groups_under([item_group]) if item_group else None
    if groups:
        filters["item_group"] = ["in", groups]
    if brand:
        filters["brand"] = brand
    conditions = None
    if item_code:
        filters["name"] = item_code
    elif term:
        conditions = {"name": ["like", "%" + term + "%"], "item_name": ["like", "%" + term + "%"]}
    return frappe.get_list("Item", filters=filters, or_filters=conditions,
                           fields=["name", "item_name", "stock_uom", "item_group", "brand", "image"],
                           order_by="item_name asc, name asc", limit_start=max(0, cint(start)),
                           limit_page_length=min(100, max(1, cint(limit))))


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


def _selling_list(profile, price_list):
    if not price_list:
        lists = _selling_lists()
        if not lists:
            return None
        price_list = next((row.name for row in lists if row.name == profile.selling_price_list), lists[0].name)
    doc = frappe.get_doc("Price List", price_list)
    doc.check_permission("read")
    if not doc.enabled or not doc.selling:
        frappe.throw(_("Choose an enabled selling price list."))
    return doc


def _item_price_doc(row, item_code, price_list, unit):
    if row:
        return frappe.get_doc("Item Price", row.name)
    doc = frappe.new_doc("Item Price")
    doc.update({"item_code": item_code, "price_list": price_list, "uom": unit})
    return doc


@frappe.whitelist()
def item_details(pos_profile: str, item_code: str, price_list: str | None = None):
    profile = _profile(pos_profile)
    item = frappe.get_doc("Item", item_code)
    item.check_permission("read")
    if item.disabled or not item.is_sales_item or item.has_variants:
        frappe.throw(_("This item is unavailable for sale."))
    can_edit_prices = _can_edit_prices()
    selected_list = _selling_list(profile, price_list) if can_edit_prices else None
    stock_unit = item.stock_uom
    factors = {stock_unit: 1}
    if not item.has_serial_no:
        factors.update({unit: factor for (_, unit), factor in conversions([item_code]).items() if unit != stock_unit})
    price_list = selected_list.name if selected_list else None
    return {
        "item_code": item.name, "item_name": item.item_name, "stock_uom": stock_unit,
        "item_group": item.item_group, "brand": item.brand, "image": item.image,
        "can_edit_item": bool(item.has_permission("write")), "can_edit_prices": can_edit_prices,
        "price_list": price_list, "currency": selected_list.currency if selected_list else None,
        "units": [
            {"uom": unit, "factor": factor,
             "price": flt(row.price_list_rate) if row else None,
             "editable": bool(_item_price_doc(row, item_code, price_list, unit).has_permission(
                 "write" if row else "create")),
             "active_price": get_price_map([item_code], price_list,
                                           {item_code: stock_unit} if unit == stock_unit else None,
                                           exact_uom=unit if unit != stock_unit else None).get(item_code)}
            for unit, factor in factors.items()
            for row in [_standing_price(item_code, price_list, unit, stock_unit)]
        ] if selected_list else [],
    }


def _read_image(encoded):
    from PIL import Image

    if not isinstance(encoded, str) or len(encoded) > ((MAX_IMAGE_BYTES + 2) // 3) * 4:
        frappe.throw(_("Choose an image up to 5 MB."))
    try:
        content = base64.b64decode(encoded, validate=True)
        if len(content) > MAX_IMAGE_BYTES:
            frappe.throw(_("Choose an image up to 5 MB."))
        with Image.open(BytesIO(content)) as image:
            extensions = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
            if image.format not in extensions or image.width * image.height > 24_000_000:
                raise ValueError("Unsupported image")
            # Re-encode to discard hidden metadata and trailing data.
            output = BytesIO()
            image.save(output, format=image.format)
            if output.tell() > MAX_IMAGE_BYTES:
                frappe.throw(_("Choose an image up to 5 MB."))
            return extensions[image.format], output.getvalue()
    except (binascii.Error, OSError, ValueError, Image.DecompressionBombError):
        frappe.throw(_("Choose a valid JPEG, PNG or WebP product image."))


@frappe.whitelist()
def save_item(pos_profile: str, item_code: str, item_name: str | None = None, prices: list | str | None = None,
              price_list: str | None = None, image_content: str | None = None):
    profile = _profile(pos_profile)
    item = frappe.get_doc("Item", item_code)
    item.check_permission("read")
    if item.disabled or not item.is_sales_item or item.has_variants:
        frappe.throw(_("This item is unavailable for sale."))
    if prices is None:
        prices = []
    if isinstance(prices, str):
        prices = json.loads(prices)
    if not isinstance(prices, list) or not all(isinstance(row, dict) for row in prices):
        frappe.throw(_("Send a list of unit prices."))
    if prices and not _can_edit_prices():
        frappe.throw(_("You do not have permission to edit item selling prices."), frappe.PermissionError)
    selected_list = _selling_list(profile, price_list) if prices else None
    if prices and not selected_list:
        frappe.throw(_("Choose an enabled selling price list."))

    name = item.item_name if item_name is None else item_name.strip()
    if name != item.item_name or image_content:
        item.check_permission("write")
        if not name or len(name) > 140:
            frappe.throw(_("Enter an item name of 1 to 140 characters."))
    image = _read_image(image_content) if image_content else None
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
        price = _standing_price(item_code, selected_list.name, unit, item.stock_uom)
        doc = _item_price_doc(price, item_code, selected_list.name, unit)
        doc.check_permission("write" if price else "create")
        doc.price_list_rate = rate
        pending.append((doc, price.price_list_rate if price else None))
    for doc, _previous_rate in pending:
        doc.save()
    if image:
        from frappe.utils.file_manager import save_file

        extension, content = image
        attachment = save_file("product-image." + extension, content, "Item", item.name, df="image")
        item.image = attachment.file_url
    identity_changed = item.item_name != name or image is not None
    if identity_changed:
        item.item_name = name
        item.save()
    from esafepos.api import audit

    if identity_changed:
        audit.log("Item updated in POS", detail=item.name, reference_doctype="Item",
                  reference_name=item.name, pos_profile=profile.name)
    for doc, previous_rate in pending:
        audit.log("Item selling price updated in POS",
                  detail=f"{item.name} · {doc.price_list} · {doc.uom} · {previous_rate} → {doc.price_list_rate}",
                  reference_doctype="Item Price", reference_name=doc.name,
                  amount=doc.price_list_rate, pos_profile=profile.name)
    return item_details(pos_profile, item_code, price_list)
