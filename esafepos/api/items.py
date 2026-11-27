"""Edit items and standing selling prices for the active outlet."""

from __future__ import annotations

import base64
import binascii
import json
import hashlib
import math
from io import BytesIO
from random import SystemRandom
from urllib.parse import urlsplit

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from esafepos.api.permissions import ITEM_PRICE_EDIT, ITEM_CREATE, ITEM_STOCK_VIEW, ITEM_STOCK_ADJUST, ITEM_STOCK_TRANSFER, ITEM_STOCK_RECEIVE, allowed, assert_outlet
from esafepos.item_units import conversions
from esafepos.price_books import get_price_map

MAX_IMAGE_BYTES = 5 * 1024 * 1024
IDENTIFIER_RANDOM = SystemRandom()


def _require(granted):
    if not granted:
        frappe.throw(_("Your account does not have access to this action."), frappe.PermissionError)


def _stock_item(item_code, allow_disabled=False):
    item = frappe.get_doc("Item", item_code)
    item.check_permission("read")
    if (item.disabled and not allow_disabled) or not item.is_stock_item or item.has_variants:
        frappe.throw(_("Choose an enabled stock item without variants."))
    return item


def _warehouses(profile):
    return frappe.get_list("Warehouse", filters={"company": profile.company, "is_group": 0, "disabled": 0},
                           pluck="name", order_by="name asc", limit_page_length=0)


@frappe.whitelist()
def warehouse_stock(pos_profile, item_code):
    profile = _profile(pos_profile)
    _require(_can_view_stock())
    item = _stock_item(item_code, allow_disabled=True)
    warehouses = _warehouses(profile)
    bins = frappe.get_list("Bin", filters={"item_code": item_code, "warehouse": ["in", warehouses]},
                           fields=["warehouse", "actual_qty", "reserved_qty"], limit_page_length=0) if warehouses else []
    by_warehouse = {row.warehouse: row for row in bins}
    from esafepos.api.catalog import pos_reserved_map

    rows = []
    for warehouse in warehouses:
        row = by_warehouse.get(warehouse)
        actual = flt(row.actual_qty) if row else 0
        reserved = flt(row.reserved_qty) if row else 0
        held = pos_reserved_map(warehouse).get(item_code, 0)
        rows.append({"warehouse": warehouse, "actual_qty": actual,
                     "reserved_qty": reserved + max(held, 0), "available_qty": actual - reserved - held})
    return {"stock_uom": item.stock_uom, "rows": rows,
            "currency": frappe.get_cached_value("Company", profile.company, "default_currency"),
            "has_serial_no": bool(item.has_serial_no), "has_batch_no": bool(item.has_batch_no),
            "can_transfer": bool(_can_transfer_stock() and not item.disabled),
            "can_receive": bool(_can_receive_stock() and not item.disabled),
            "can_view_movements": bool(frappe.has_permission("Stock Ledger Entry", "read")),
            "can_adjust": bool(_can_adjust_stock() and not item.disabled and not item.has_serial_no and not item.has_batch_no)}


def _number(value, message, allow_negative=False):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        frappe.throw(_(message))
    if not math.isfinite(number) or (number < 0 and not allow_negative):
        frappe.throw(_(message))
    return number


def _json_list(value, message):
    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            frappe.throw(_(message))
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        frappe.throw(_(message))
    return value


def _json_list_codes(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            frappe.throw(_("Send a list of item codes."))
    if (not isinstance(value, list) or len(value) > 500
            or any(not isinstance(code, str) or not code or len(code) > 140 for code in value)):
        frappe.throw(_("Send at most 500 valid item codes."))
    return list(dict.fromkeys(value))


def _clean_selling_units(rows, stock_uom):
    units = []
    seen = set()
    for row in rows:
        unit = row.get("uom")
        factor = _number(row.get("factor"), "Enter a valid conversion factor greater than zero.")
        if (not isinstance(unit, str) or not unit or unit == stock_uom or unit in seen
                or not frappe.db.exists("UOM", unit) or factor <= 0):
            frappe.throw(_("Choose a unique alternate UOM and a conversion factor greater than zero."))
        frappe.get_doc("UOM", unit).check_permission("read")
        seen.add(unit)
        units.append({"uom": unit, "conversion_factor": factor})
    return units


def _clean_barcodes(rows, item_code, allowed_units):
    cleaned = []
    seen = set()
    for row in rows:
        value = (row.get("barcode") or "").strip()
        unit = row.get("uom") or None
        if not value:
            continue
        if len(value) > 140 or value in seen or (unit and unit not in allowed_units):
            frappe.throw(_("Enter unique barcodes up to 140 characters and choose a configured unit."))
        owner = frappe.db.get_value("Item Barcode", {"barcode": value}, "parent")
        if owner and owner != item_code:
            frappe.throw(_("Barcode {0} already belongs to item {1}.").format(value, owner))
        seen.add(value)
        cleaned.append({"barcode": value, "uom": unit})
    return cleaned


def _save_prices(item_code, selected_list, prices, allowed_units):
    pending = []
    seen = set()
    stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
    for row in prices:
        unit = row.get("uom")
        rate = flt(row.get("price"))
        if unit not in allowed_units or unit in seen or not math.isfinite(rate) or rate <= 0:
            frappe.throw(_("Use a configured unit and a price greater than zero."))
        seen.add(unit)
        price = _standing_price(item_code, selected_list.name, unit, stock_uom)
        doc = _item_price_doc(price, item_code, selected_list.name, unit)
        doc.check_permission("write" if price else "create")
        doc.price_list_rate = rate
        pending.append((doc, price.price_list_rate if price else None))
    return pending


@frappe.whitelist(methods=["POST"])
def adjust_stock(pos_profile, item_code, warehouse, qty, expected_qty, reason, valuation_rate=None, include_snapshot=0):
    profile = _profile(pos_profile)
    _require(_can_adjust_stock())
    item = _stock_item(item_code)
    if item.has_serial_no or item.has_batch_no:
        frappe.throw(_("Use ERPNext to adjust serial or batch tracked items."))
    if warehouse not in _warehouses(profile):
        frappe.throw(_("Choose an accessible warehouse in this outlet's company."), frappe.PermissionError)
    frappe.get_doc("Warehouse", warehouse).check_permission("read")
    qty = _number(qty, "Enter a non-negative stock quantity.")
    expected = _number(expected_qty, "Refresh warehouse stock before adjusting it.", allow_negative=True)
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        frappe.throw(_("Enter a reason of 1 to 500 characters."))
    # Lock an existing bin until the reconciliation is submitted in this transaction.
    current = frappe.db.sql("select actual_qty from `tabBin` where item_code=%s and warehouse=%s for update",
                            (item_code, warehouse))
    actual = flt(current[0][0]) if current else 0
    if abs(actual - expected) > 0.000001:
        frappe.throw(_("Stock changed. Refresh warehouse stock and try again."))
    if abs(qty - actual) < 0.000001:
        frappe.throw(_("The new quantity matches current stock."))
    from esafepos.api.stock_app import _has_workflow, _refuse_unposted, _unposted

    if _has_workflow("Stock Reconciliation"):
        frappe.throw(_("This site requires stock approval. Create the reconciliation in ERPNext."))
    row = {"item_code": item_code, "warehouse": warehouse, "qty": qty}
    if valuation_rate not in (None, ""):
        rate = _number(valuation_rate, "Enter a valuation rate greater than zero.")
        if rate <= 0:
            frappe.throw(_("Enter a valuation rate greater than zero."))
        row["valuation_rate"] = rate
    doc = frappe.get_doc({"doctype": "Stock Reconciliation", "company": profile.company,
                          "purpose": "Stock Reconciliation", "items": [row]})
    doc.check_permission("create")
    doc.check_permission("submit")
    _refuse_unposted(_unposted(doc))
    doc.insert()
    doc.add_comment("Comment", reason.strip())
    doc.submit()
    from esafepos.api import audit

    audit.log("Warehouse stock adjusted in POS", detail="{}: {} → {}. {}".format(warehouse, actual, qty, reason.strip()),
              reference_doctype=doc.doctype, reference_name=doc.name, pos_profile=profile.name)
    result = {"name": doc.name}
    if cint(include_snapshot):
        frappe.local.esafepos_pos_reserved = {}
        result["stock"] = warehouse_stock(pos_profile, item_code)
    return result


def _identifier_candidate(character_type, length):
    digits = "0123456789"
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if character_type == "numeric":
        return "".join(IDENTIFIER_RANDOM.choice(digits) for _index in range(length))
    characters = [IDENTIFIER_RANDOM.choice(letters), IDENTIFIER_RANDOM.choice(digits)]
    characters.extend(IDENTIFIER_RANDOM.choice(letters + digits) for _index in range(length - 2))
    IDENTIFIER_RANDOM.shuffle(characters)
    return "".join(characters)


@frappe.whitelist(methods=["POST"])
def generate_identifier(pos_profile, target="item_code", character_type="numeric", length=5,
                        item_code=None, exclude=None):
    """Suggest an unused identifier; normal Item validation still applies on save."""
    _profile(pos_profile)
    if target not in ("item_code", "barcode"):
        frappe.throw(_("Choose an item code or barcode to generate."))
    if target == "barcode" and item_code:
        item = frappe.get_doc("Item", item_code)
        item.check_permission("read")
        item.check_permission("write")
    else:
        _require(_can_create())
    if character_type not in ("numeric", "alphanumeric"):
        frappe.throw(_("Choose numbers only or letters and numbers."))
    if (isinstance(length, bool) or not isinstance(length, (int, str))
            or len(str(length)) > 3 or not str(length).isascii() or not str(length).isdigit()):
        frappe.throw(_("Enter a whole code length from 1 to 140."))
    length = int(length)
    if not 1 <= length <= 140 or (character_type == "alphanumeric" and length < 2):
        frappe.throw(_("Use 1 to 140 digits, or 2 to 140 characters for letters and numbers."))
    if isinstance(exclude, str):
        try:
            exclude = json.loads(exclude)
        except (TypeError, ValueError):
            frappe.throw(_("Send a list of codes to exclude."))
    if exclude is None:
        exclude = []
    if (not isinstance(exclude, list) or len(exclude) > 1000
            or any(not isinstance(value, str) or len(value) > 140 for value in exclude)):
        frappe.throw(_("Send up to 1000 codes to exclude, each up to 140 characters."))
    excluded = {value.strip().upper() for value in exclude}
    for _attempt in range(100):
        value = _identifier_candidate(character_type, length)
        if (value not in excluded and not frappe.db.exists("Item", value)
                and not frappe.db.exists("Item", {"item_code": value})
                and not frappe.db.exists("Item Barcode", {"barcode": value})):
            return {"value": value}
    frappe.throw(_("No unused code was found at this length. Increase the length or try again."))


@frappe.whitelist(methods=["POST"])
def create_item(pos_profile, item_code, item_name, item_group, stock_uom, barcode="", brand="",
                selling_units=None, prices=None, price_list=None, barcodes=None):
    profile = _profile(pos_profile)
    _require(_can_create())
    for value in (item_code, item_name):
        if not isinstance(value, str) or not value.strip() or len(value) > 140:
            frappe.throw(_("Enter an item code and name of 1 to 140 characters."))
    for doctype, value in (("Item Group", item_group), ("UOM", stock_uom), ("Brand", brand)):
        if doctype == "Brand" and not value:
            continue
        linked = frappe.get_doc(doctype, value)
        linked.check_permission("read")
        if doctype == "Item Group" and linked.is_group:
            frappe.throw(_("Choose a leaf item category."))
    if barcode and (not isinstance(barcode, str) or len(barcode) > 140):
        frappe.throw(_("Enter a barcode up to 140 characters."))
    units = _clean_selling_units(_json_list(selling_units, "Send a list of alternate selling units."), stock_uom)
    prices = _json_list(prices, "Send a list of unit prices.")
    if prices and not _can_edit_prices():
        frappe.throw(_("You do not have permission to edit item selling prices."), frappe.PermissionError)
    selected_list = _selling_list(profile, price_list) if prices else None
    if prices and not selected_list:
        frappe.throw(_("Choose an enabled selling price list."))
    allowed_units = {stock_uom} | {row["uom"] for row in units}
    submitted_barcodes = _json_list(barcodes, "Send a list of item barcodes.")
    if not submitted_barcodes and barcode and barcode.strip():
        submitted_barcodes = [{"barcode": barcode.strip(), "uom": stock_uom}]
    cleaned_barcodes = _clean_barcodes(submitted_barcodes, item_code.strip(), allowed_units)
    doc = frappe.get_doc({"doctype": "Item", "item_code": item_code.strip(), "item_name": item_name.strip(),
                          "item_group": item_group, "stock_uom": stock_uom, "brand": brand or None,
                          "is_stock_item": 1, "is_sales_item": 1, "is_purchase_item": 1,
                          "uoms": units, "barcodes": cleaned_barcodes})
    doc.check_permission("create")
    doc.insert()
    pending = _save_prices(doc.name, selected_list, prices, allowed_units) if prices else []
    for price_doc, _previous_rate in pending:
        price_doc.save()
    from esafepos.api import audit

    audit.log("Item created in POS", detail=doc.name, reference_doctype="Item",
              reference_name=doc.name, pos_profile=profile.name)
    for price_doc, _previous_rate in pending:
        audit.log("Item selling price created in POS",
                  detail="{} · {} · {} · {}".format(doc.name, price_doc.price_list,
                                                     price_doc.uom, price_doc.price_list_rate),
                  reference_doctype="Item Price", reference_name=price_doc.name,
                  amount=price_doc.price_list_rate, pos_profile=profile.name)
    return {"item_code": doc.name}


def _can_edit_prices():
    return (
        allowed(ITEM_PRICE_EDIT)
        and frappe.has_permission("Price List", "read")
        and frappe.has_permission("Item Price", "read")
        and (frappe.has_permission("Item Price", "write") or frappe.has_permission("Item Price", "create"))
    )


def can_edit():
    return frappe.has_permission("Item", "read") and (
        frappe.has_permission("Item", "write") or _can_edit_prices()
        or _can_create() or _can_view_stock())


def _can_create():
    return allowed(ITEM_CREATE) and frappe.has_permission("Item", "create")


def _can_view_stock():
    return (allowed(ITEM_STOCK_VIEW) and frappe.has_permission("Warehouse", "read")
            and frappe.has_permission("Bin", "read"))


def _can_adjust_stock():
    return (_can_view_stock() and allowed(ITEM_STOCK_ADJUST)
            and frappe.has_permission("Stock Reconciliation", "create")
            and frappe.has_permission("Stock Reconciliation", "submit"))


def _can_transfer_stock():
    return (_can_view_stock() and allowed(ITEM_STOCK_TRANSFER)
            and frappe.has_permission("Stock Entry", "create")
            and frappe.has_permission("Stock Entry", "submit")
            and frappe.has_permission("Stock Entry", "read"))


def _can_receive_stock():
    return (_can_view_stock() and allowed(ITEM_STOCK_RECEIVE)
            and frappe.has_permission("Stock Entry", "read")
            and frappe.has_permission("Stock Entry", "create")
            and frappe.has_permission("Stock Entry", "submit"))


def _profile(pos_profile):
    if not pos_profile or not can_edit():
        frappe.throw(_("You do not have access to the Items editor."), frappe.PermissionError)
    assert_outlet(pos_profile)
    return frappe.get_cached_doc("POS Profile", pos_profile)


@frappe.whitelist()
def editor_options(pos_profile: str):
    profile = _profile(pos_profile)
    settings = frappe.get_cached_doc("EsafePOS Settings")
    return {
        "item_groups": _filter_names("Item Group"),
        "brands": _filter_names("Brand"),
        "price_lists": _selling_lists() if _can_edit_prices() else [],
        "default_price_list": profile.selling_price_list,
        "can_edit_prices": bool(_can_edit_prices()),
        "uoms": _filter_names("UOM"),
        "gemini_image_search": bool(settings.get("item_image_gemini_enabled")),
        "can_create_items": bool(_can_create()),
        "can_view_stock": bool(_can_view_stock()),
        "can_adjust_stock": bool(_can_adjust_stock()),
        "can_transfer_stock": bool(_can_transfer_stock()),
        "can_receive_stock": bool(_can_receive_stock()),
        "warehouses": _warehouses(profile) if _can_view_stock() else [],
        "stock_uoms": _filter_names("UOM") if _can_create() else [],
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
                 item_group: str = "", brand: str = "", status="active", item_type="",
                 include_stock=0, warehouse=""):
    profile = _profile(pos_profile)
    from esafepos.api.catalog import item_groups_under

    term = (search or "").strip()
    item_code = frappe.db.get_value("Item Barcode", {"barcode": term}, "parent") if term else None
    if status not in ("active", "disabled", "all") or item_type not in ("", "stock", "service", "template", "variant"):
        frappe.throw(_("Choose a valid item status and type."))
    filters = {}
    if status != "all":
        filters["disabled"] = int(status == "disabled")
    if item_type in ("stock", "service"):
        filters.update({"is_stock_item": int(item_type == "stock"), "has_variants": 0})
    elif item_type == "template":
        filters["has_variants"] = 1
    elif item_type == "variant":
        filters["variant_of"] = ["is", "set"]
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
    rows = frappe.get_list("Item", filters=filters, or_filters=conditions,
                           fields=["name", "item_name", "stock_uom", "item_group", "brand", "image",
                                   "disabled", "has_variants", "variant_of", "is_stock_item"],
                           order_by="item_name asc, name asc", limit_start=max(0, cint(start)),
                           limit_page_length=min(100, max(1, cint(limit))))
    if cint(include_stock):
        _require(_can_view_stock())
        warehouses = _warehouses(profile)
        if warehouse:
            _require(warehouse in warehouses)
            warehouses = [warehouse]
        codes = [row.name for row in rows if row.is_stock_item and not row.has_variants]
        totals = {code: {"actual_qty": 0, "reserved_qty": 0, "available_qty": 0} for code in codes}
        bins = frappe.get_list("Bin", filters={"item_code": ["in", codes], "warehouse": ["in", warehouses]},
                               fields=["item_code", "warehouse", "actual_qty", "reserved_qty"],
                               limit_page_length=0) if codes and warehouses else []
        from esafepos.api.catalog import pos_reserved_map

        for row in bins:
            totals[row.item_code]["actual_qty"] += flt(row.actual_qty)
            totals[row.item_code]["reserved_qty"] += flt(row.reserved_qty)
            totals[row.item_code]["available_qty"] += flt(row.actual_qty) - flt(row.reserved_qty)
        for name in warehouses:
            for code, held in pos_reserved_map(name).items():
                if code in totals:
                    totals[code]["reserved_qty"] += max(flt(held), 0)
                    totals[code]["available_qty"] -= flt(held)
        for row in rows:
            if row.name in totals:
                stock = totals[row.name]
                row.update(stock)
    return rows


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
    can_edit_prices = _can_edit_prices()
    selected_list = _selling_list(profile, price_list) if can_edit_prices and not item.has_variants else None
    stock_unit = item.stock_uom
    factors = {stock_unit: 1}
    if not item.has_serial_no:
        factors.update({unit: factor for (_, unit), factor in conversions([item_code]).items() if unit != stock_unit})
    price_list = selected_list.name if selected_list else None
    base_price = get_price_map([item_code], price_list, {item_code: stock_unit}).get(item_code, 0) if price_list else 0
    units = []
    for unit, factor in factors.items():
        row = _standing_price(item_code, price_list, unit, stock_unit) if price_list else None
        active = get_price_map([item_code], price_list,
                               {item_code: stock_unit} if unit == stock_unit else None,
                               exact_uom=unit if unit != stock_unit else None).get(item_code) if price_list else None
        shown_price = flt(row.price_list_rate) if row else (flt(active) if active else flt(base_price) * factor)
        price_doc = _item_price_doc(row, item_code, price_list, unit) if price_list else None
        units.append({
            "uom": unit, "factor": factor, "price": shown_price,
            "editable": bool(price_doc and price_doc.has_permission("write" if row else "create")),
            "active_price": flt(active) if active else (flt(base_price) * factor if base_price else None),
            "has_explicit_price": bool(row),
        })
    return {
        "item_code": item.name, "item_name": item.item_name, "stock_uom": stock_unit,
        "item_group": item.item_group, "brand": item.brand, "image": item.image,
        "description": item.get("description") or "", "disabled": bool(item.disabled),
        "is_stock_item": bool(item.is_stock_item), "is_sales_item": bool(item.is_sales_item),
        "is_purchase_item": bool(item.is_purchase_item), "has_variants": bool(item.has_variants),
        "variant_of": item.variant_of, "has_batch_no": bool(item.has_batch_no),
        "barcode": item.barcodes[0].barcode if item.barcodes else "",
        "barcodes": [{"barcode": row.barcode, "uom": row.uom or stock_unit}
                     for row in (item.get("barcodes") or [])],
        "selling_units": ([] if item.has_serial_no else [
            {"uom": row.uom, "factor": flt(row.conversion_factor)}
            for row in (item.get("uoms") or []) if row.uom != stock_unit
        ]),
        "has_serial_no": bool(item.has_serial_no),
        "can_edit_item": bool(item.has_permission("write")), "can_edit_prices": can_edit_prices,
        "price_list": price_list, "currency": selected_list.currency if selected_list else None,
        "units": units,
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


def _image_link(value):
    error = _("Enter a valid HTTPS image link.")
    if not isinstance(value, str):
        frappe.throw(error)
    value = value.strip()
    if len(value) > 2048 or any(c.isspace() or ord(c) < 32 or c in '\\<>"' for c in value):
        frappe.throw(error)
    try:
        url = urlsplit(value)
        valid = url.scheme == "https" and url.hostname and url.username is None and url.port != 0
    except ValueError:
        valid = False
    if not valid:
        frappe.throw(error)
    return value


def _update_metadata(item, disabled, item_group, brand, description, is_sales_item, is_purchase_item):
    values = {key: value for key, value in {
        "disabled": disabled, "item_group": item_group, "brand": brand, "description": description,
        "is_sales_item": is_sales_item, "is_purchase_item": is_purchase_item,
    }.items() if value is not None}
    if not values:
        return False
    item.check_permission("write")
    for key in ("disabled", "is_sales_item", "is_purchase_item"):
        if key in values:
            if values[key] not in (0, 1, "0", "1", False, True):
                frappe.throw(_("Choose a valid item setting."))
            values[key] = cint(values[key])
    for key, doctype in (("item_group", "Item Group"), ("brand", "Brand")):
        if key not in values:
            continue
        if not isinstance(values[key], str) or len(values[key]) > 140 or (key == "item_group" and not values[key]):
            frappe.throw(_("Choose a valid category and brand."))
        if values[key]:
            linked = frappe.get_doc(doctype, values[key])
            linked.check_permission("read")
            if key == "item_group" and linked.is_group:
                frappe.throw(_("Choose a leaf item category."))
    if "description" in values:
        if not isinstance(values["description"], str) or len(values["description"]) > 10000:
            frappe.throw(_("Keep the description within 10,000 characters."))
        values["description"] = frappe.utils.sanitize_html(values["description"])
    changed = any(item.get(key) != value for key, value in values.items())
    item.update(values)
    return changed


@frappe.whitelist(methods=["POST"])
def save_item(pos_profile: str, item_code: str, item_name: str | None = None, prices: list | str | None = None,
              price_list: str | None = None, image_content: str | None = None, image_url: str | None = None,
              selling_units: list | str | None = None, barcodes: list | str | None = None,
              disabled=None, item_group=None, brand=None, description=None, is_sales_item=None, is_purchase_item=None,
              include_catalog=0):
    profile = _profile(pos_profile)
    item = frappe.get_doc("Item", item_code)
    item.check_permission("read")
    prices = _json_list(prices, "Send a list of unit prices.")
    if prices and item.has_variants:
        frappe.throw(_("Set selling prices on individual variants."))
    if prices and not _can_edit_prices():
        frappe.throw(_("You do not have permission to edit item selling prices."), frappe.PermissionError)
    selected_list = _selling_list(profile, price_list) if prices else None
    if prices and not selected_list:
        frappe.throw(_("Choose an enabled selling price list."))

    name = item.item_name if item_name is None else item_name.strip()
    if name != item.item_name or image_content or image_url is not None:
        item.check_permission("write")
        if not name or len(name) > 140:
            frappe.throw(_("Enter an item name of 1 to 140 characters."))
    if image_content and image_url is not None:
        frappe.throw(_("Choose either a device image or an image link."))
    link = _image_link(image_url) if image_url is not None else None
    image = _read_image(image_content) if image_content else None
    old_units = [{"uom": row.uom, "conversion_factor": flt(row.conversion_factor)}
                 for row in (item.get("uoms") or []) if row.uom != item.stock_uom]
    units_supplied = selling_units is not None
    if units_supplied:
        item.check_permission("write")
        clean_units = _clean_selling_units(_json_list(selling_units, "Send a list of alternate selling units."), item.stock_uom)
        if item.has_serial_no and clean_units:
            frappe.throw(_("Serialized items must be sold in their stock unit."))
        new_names = {row["uom"] for row in clean_units}
        for fieldname in ("default_sales_unit", "default_purchase_unit"):
            default_unit = item.get(fieldname)
            if default_unit and default_unit != item.stock_uom and default_unit not in new_names:
                frappe.throw(_("Keep {0}, which is set as this item's default {1} unit.").format(
                    default_unit, fieldname.replace("default_", "").replace("_unit", "")
                ))
        units_changed = sorted(old_units, key=lambda row: row["uom"]) != sorted(clean_units, key=lambda row: row["uom"])
        if units_changed:
            item.set("uoms", clean_units)
    else:
        clean_units = old_units
        units_changed = False
    allowed_units = {item.stock_uom} | {row["uom"] for row in clean_units}
    if units_changed and barcodes is None and any(
            row.uom and row.uom not in allowed_units for row in (item.get("barcodes") or [])):
        frappe.throw(_("Update or remove barcodes assigned to a selling unit before removing that unit."))
    barcodes_changed = False
    if barcodes is not None:
        item.check_permission("write")
        cleaned_barcodes = _clean_barcodes(
            _json_list(barcodes, "Send a list of item barcodes."), item_code, allowed_units
        )
        current_barcodes = [{"barcode": row.barcode, "uom": row.uom or item.stock_uom}
                            for row in (item.get("barcodes") or [])]
        barcodes_changed = current_barcodes != cleaned_barcodes
        if barcodes_changed:
            item.set("barcodes", cleaned_barcodes)
    pending = _save_prices(item_code, selected_list, prices, allowed_units) if prices else []
    if image:
        from frappe.utils.file_manager import save_file

        extension, content = image
        attachment = save_file("product-image." + extension, content, "Item", item.name, df="image")
        item.image = attachment.file_url
    metadata_changed = _update_metadata(item, disabled, item_group, brand, description, is_sales_item, is_purchase_item)
    identity_changed = (metadata_changed or item.item_name != name or image is not None or
                        (link is not None and link != item.image) or units_changed or barcodes_changed)
    if identity_changed:
        if link is not None:
            # ERPNext and POS use the same image field. Keep the URL as a reference
            # so saving an item never needs to fetch external content on the server.
            item.image = link
        item.item_name = name
        item.save()
    for doc, _previous_rate in pending:
        doc.save()
    from esafepos.api import audit

    if identity_changed:
        audit.log("Item updated in POS", detail=item.name, reference_doctype="Item",
                  reference_name=item.name, pos_profile=profile.name)
    for doc, previous_rate in pending:
        audit.log("Item selling price updated in POS",
                  detail=f"{item.name} · {doc.price_list} · {doc.uom} · {previous_rate} → {doc.price_list_rate}",
                  reference_doctype="Item Price", reference_name=doc.name,
                  amount=doc.price_list_rate, pos_profile=profile.name)
    result = item_details(pos_profile, item_code, price_list)
    if cint(include_catalog):
        from esafepos.api.catalog_sync import item_updates

        result["catalog"] = item_updates(pos_profile, [item_code])
    return result


@frappe.whitelist(methods=["POST"])
def transfer_stock(pos_profile, item_code, source_warehouse, target_warehouse, qty, expected_qty,
                   reason, request_id, serial_no="", batch_no="", include_snapshot=0):
    """Submit one native Material Transfer; stable names make uncertain retries safe."""
    profile = _profile(pos_profile)
    _require(_can_transfer_stock())
    item = frappe.get_doc("Item", item_code)
    item.check_permission("read")
    qty = _number(qty, "Enter a transfer quantity greater than zero.")
    expected = _number(expected_qty, "Refresh stock before transferring.", allow_negative=True)
    if qty <= 0 or not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        frappe.throw(_("Enter a positive quantity and a reason of 1 to 500 characters."))
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 100:
        frappe.throw(_("A transfer request ID is required. Reopen the transfer form."))
    warehouses = _warehouses(profile)
    _require(source_warehouse in warehouses and target_warehouse in warehouses)
    if source_warehouse == target_warehouse:
        frappe.throw(_("Choose different source and destination warehouses."))
    for warehouse in (source_warehouse, target_warehouse):
        frappe.get_doc("Warehouse", warehouse).check_permission("read")
    serials = [value.strip() for value in str(serial_no or "").splitlines() if value.strip()]
    payload = [item_code, source_warehouse, target_warehouse, qty, reason.strip(), sorted(serials), batch_no or ""]
    fingerprint = hashlib.sha256(json.dumps(payload, ensure_ascii=True).encode()).hexdigest()
    identity = hashlib.sha256((frappe.session.user + ":" + profile.name + ":" + request_id).encode()).hexdigest()[:32]
    name = "POS-TRF-" + identity
    marker = "EsafePOS transfer " + fingerprint
    # Also serializes competing transfers for this item, including an empty destination Bin.
    frappe.db.sql("select name from `tabItem` where name=%s for update", (item_code,))
    # Current reads are essential after waiting for another request's commit:
    # a normal exists/get_doc could still see the request's older SQL snapshot.
    item = frappe.get_doc("Item", item_code, for_update=True)
    item.check_permission("read")
    if frappe.db.get_value("Stock Entry", name, "name", for_update=True):
        previous = frappe.get_doc("Stock Entry", name, for_update=True)
        previous.check_permission("read")
        if previous.docstatus != 1 or previous.company != profile.company or previous.remarks != marker + "\n" + reason.strip():
            frappe.throw(_("This transfer request was already used. Review the earlier Stock Entry in ERPNext."))
        result = {"name": previous.name, "replayed": True}
        if cint(include_snapshot):
            result["stock"] = warehouse_stock(pos_profile, item_code)
        return result
    if item.disabled or not item.is_stock_item or item.has_variants:
        frappe.throw(_("Choose an enabled stock item without variants."))
    if item.has_serial_no and (qty != len(serials) or len(serials) != len(set(serials))):
        frappe.throw(_("Enter one unique serial number for each transferred unit."))
    if item.has_batch_no and not batch_no:
        frappe.throw(_("Choose the batch to transfer."))
    if not item.has_serial_no and serials or not item.has_batch_no and batch_no:
        frappe.throw(_("Tracking details do not match this item."))
    if frappe.get_cached_value("UOM", item.stock_uom, "must_be_whole_number") and qty != int(qty):
        frappe.throw(_("This stock unit requires a whole transfer quantity."))
    from esafepos.api.stock_app import _has_workflow, _refuse_unposted, _unposted

    if _has_workflow("Stock Entry"):
        frappe.throw(_("This site requires stock approval. Create the transfer in ERPNext."))
    current = frappe.db.sql("select actual_qty, reserved_qty from `tabBin` where item_code=%s and warehouse=%s for update",
                            (item_code, source_warehouse))
    actual, reserved = (flt(current[0][0]), flt(current[0][1])) if current else (0, 0)
    if abs(actual - expected) > 0.000001:
        frappe.throw(_("Stock changed. Refresh warehouse stock and try again."))
    if qty > actual - max(reserved, 0) + 0.000001:
        frappe.throw(_("The transfer exceeds available stock after reservations."))
    _refuse_unposted(_unposted(frappe._dict(items=[{"item_code": item_code, "warehouse": source_warehouse}])))
    row = {"item_code": item_code, "s_warehouse": source_warehouse, "t_warehouse": target_warehouse,
           "qty": qty, "uom": item.stock_uom, "stock_uom": item.stock_uom, "conversion_factor": 1}
    if serials:
        row["serial_no"] = "\n".join(serials)
    if batch_no:
        row["batch_no"] = batch_no
    if (serials or batch_no) and frappe.get_meta("Stock Entry Detail").has_field("use_serial_batch_fields"):
        row["use_serial_batch_fields"] = 1
    doc = frappe.get_doc({"doctype": "Stock Entry", "company": profile.company,
                          "stock_entry_type": "Material Transfer", "purpose": "Material Transfer",
                          "from_warehouse": source_warehouse, "to_warehouse": target_warehouse,
                          "remarks": marker + "\n" + reason.strip(), "items": [row]})
    doc.check_permission("create")
    doc.check_permission("submit")
    doc.insert(set_name=name)
    doc.submit()
    from esafepos.api import audit

    audit.log("Warehouse stock transferred in POS", detail="{}: {} → {}. {}".format(item_code, source_warehouse, target_warehouse, reason.strip()),
              reference_doctype="Stock Entry", reference_name=doc.name, pos_profile=profile.name)
    result = {"name": doc.name, "replayed": False}
    if cint(include_snapshot):
        frappe.local.esafepos_pos_reserved = {}
        result["stock"] = warehouse_stock(pos_profile, item_code)
    return result


@frappe.whitelist()
def stock_movements(pos_profile, item_code, warehouse="", start=0, from_date=None, to_date=None):
    profile = _profile(pos_profile)
    _require(_can_view_stock() and frappe.has_permission("Stock Ledger Entry", "read"))
    _stock_item(item_code, allow_disabled=True)
    warehouses = _warehouses(profile)
    if warehouse:
        _require(warehouse in warehouses)
        warehouses = [warehouse]
    if not warehouses:
        return []
    filters = {"item_code": item_code, "company": profile.company, "warehouse": ["in", warehouses], "is_cancelled": 0}
    if from_date and to_date:
        if getdate(from_date) > getdate(to_date):
            frappe.throw(_("The start date must be before the end date."))
        filters["posting_date"] = ["between", [getdate(from_date), getdate(to_date)]]
    elif from_date:
        filters["posting_date"] = [">=", getdate(from_date)]
    elif to_date:
        filters["posting_date"] = ["<=", getdate(to_date)]
    return frappe.get_list("Stock Ledger Entry", filters=filters,
                           fields=["name", "posting_date", "posting_time", "warehouse", "actual_qty",
                                   "qty_after_transaction", "voucher_type", "voucher_no"],
                           order_by="posting_date desc, posting_time desc, creation desc",
                           limit_start=max(0, cint(start)), limit_page_length=50)
