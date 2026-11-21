# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "ESAFEPOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
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
import math

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, getdate

from esafepos.api import permissions

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
            "select value from tabSingles where doctype=%s and field=%s", ("EsafePOS Settings", SWITCH)
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
    from esafepos.api.layaway import _build_sale

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
    from esafepos import currency

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
    from esafepos.price_books import effective_prices

    order = []
    qty = {}
    for code, n in wanted:
        if not code:
            continue
        if code not in qty:
            order.append(code)
            qty[code] = 0
        qty[code] += max(0, cint(n))
    if len(order) > MAX_ITEMS:
        frappe.throw(_("Choose at most 500 different items per request."))
    if not order:
        return []
    items = {
        d.name: d
        for d in frappe.get_list(
            "Item",
            filters={"name": ["in", order]},
            fields=["name", "item_name", "stock_uom", "disabled", "is_sales_item", "brand", "has_serial_no"],
            limit_page_length=MAX_ITEMS,
        )
    }
    # A disabled item is not on sale, so no label: and ERPNext refuses it in the
    # invoice that works out the tax, which took the whole list down with it
    # (a price changed today on an item switched off, suite 54 on 2026-10-26).
    order = [c for c in order if c in items and not cint(items[c].disabled)]
    if not order:
        return []
    uom_map = {c: items[c].stock_uom for c in order}
    prices = effective_prices(profile, order, stock_uom_map=uom_map)
    factors = _tax_factors(profile, order, prices)
    barcodes = _barcodes(order)
    shown, outlet_rate = _equivalents(profile)
    from esafepos import currency

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
                "stock_uom": items[code].stock_uom,
                "has_serial_no": items[code].has_serial_no,
                "brand": items[code].brand or "",
                "barcode": barcodes.get(code) or "",
                "price": flt(price, 2),
                "price_with_tax": with_tax,
                "currency": ccy,
                "equivalents": [
                    {"currency": e["currency"], "amount": flt(with_tax * outlet_rate / e["rate"], 2)} for e in shown
                ],
                "qty": qty[code] or 1,
                "unpriced": not price,
            }
        )
    from esafepos.item_units import add_options
    add_options(out, profile.selling_price_list)
    barcode_fields = ["parent", "barcode"]
    has_uom = frappe.get_meta("Item Barcode").has_field("uom")
    if has_uom:
        barcode_fields.append("uom")
    barcode_options = frappe.get_all("Item Barcode", filters={"parenttype": "Item", "parent": ["in", order]},
                                     fields=barcode_fields, order_by="idx asc")
    for row in out:
        row["barcode_options"] = [{"barcode": b.barcode, "uom": b.get("uom") or row["uom"]}
                                  for b in barcode_options if b.parent == row["item_code"]]
        matching = [b["barcode"] for b in row["barcode_options"] if b["uom"] == row["uom"]]
        if row["barcode"] not in matching:
            row["barcode"] = matching[0] if matching else ""
    return out


def _parse(items):
    if isinstance(items, str):
        items = json.loads(items or "[]")
    return [(row.get("item_code"), row.get("qty", 1)) for row in items or [] if isinstance(row, dict)]


@frappe.whitelist()
def items(pos_profile: str, items: str | list | None = None):
    """Label rows for the items given ([{item_code, qty}])."""
    profile = _guard(pos_profile)
    choices = json.loads(items) if isinstance(items, str) else items
    if not isinstance(choices, list) or len(choices) > MAX_ITEMS or any(not isinstance(r, dict) for r in choices):
        frappe.throw(_("Choose at most 500 item rows."))
    base = {r["item_code"]: r for r in _rows(profile, _parse(choices))}
    result = []
    for choice in choices or []:
        if choice.get("item_code") in base:
            row = dict(base[choice["item_code"]])
            _choose_unit(profile, row, choice.get("uom"))
            row["qty"] = choice.get("qty", 1)
            result.append(row)
    return {"rows": result, "company": profile.company}


def _choose_unit(profile, row, unit):
    if not unit or unit == row["uom"]:
        return
    option = next((u for u in row.get("selling_units", []) if u["uom"] == unit), None)
    if not option:
        frappe.throw(_("This item has no configured selling price for that unit."))
    rate = flt(option["price"])
    factor = _tax_factors(profile, [row["item_code"]], {row["item_code"]: rate})[row["item_code"]]
    shown, outlet_rate = _equivalents(profile)
    taxed = flt(rate * factor, 2)
    matching = [b["barcode"] for b in row.get("barcode_options", []) if b["uom"] == unit]
    row.update(uom=unit, price=rate, price_with_tax=taxed, barcode=matching[0] if matching else row["item_code"],
               unpriced=False, equivalents=[{"currency": e["currency"], "amount": flt(taxed * outlet_rate / e["rate"], 2)} for e in shown])


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
    source = frappe.get_doc(doctype, name)
    source.check_permission("read")
    if doc.company != profile.company:
        frappe.throw(_("Choose a document from this outlet's company."), frappe.PermissionError)
    if doctype == "Purchase Invoice" and not cint(source.get("update_stock")):
        frappe.throw(_("Choose a Purchase Invoice that updates stock."))
    child = "Stock Entry Detail" if doctype == "Stock Entry" else doctype + " Item"
    qty_field = "transfer_qty" if doctype == "Stock Entry" else "stock_qty"
    trace_fields = [f for f in ("batch_no", "serial_no", "serial_and_batch_bundle") if frappe.get_meta(child).has_field(f)]
    lines = frappe.get_all(
        child,
        filters={"parent": name, "parenttype": doctype},
        fields=["item_code", qty_field, "idx"] + trace_fields,
        order_by="idx asc",
    )
    wanted = [(r.item_code, 1) for r in lines if flt(r.get(qty_field)) > 0]
    by_code = {r["item_code"]: r for r in _rows(profile, wanted)}
    result = []
    for line in lines:
        if flt(line.get(qty_field)) <= 0 or line.item_code not in by_code:
            continue
        parts = [{"qty": flt(line.get(qty_field)), "batch_no": line.get("batch_no"), "serial_no": line.get("serial_no")}]
        if line.get("serial_and_batch_bundle"):
            bundle = frappe.get_doc("Serial and Batch Bundle", line.serial_and_batch_bundle)
            bundle.check_permission("read")
            parts = [{"qty": abs(flt(e.qty)), "batch_no": e.get("batch_no"), "serial_no": e.get("serial_no")} for e in bundle.entries]
        for part in parts:
            serials = str(part.get("serial_no") or "").splitlines()
            for serial in serials or [""]:
                row = dict(by_code[line.item_code])
                row.update(qty=1 if serial else int(math.ceil(part["qty"])), batch_no=part.get("batch_no") or "", serial_no=serial)
                if row["batch_no"]:
                    batch = frappe.get_doc("Batch", row["batch_no"])
                    batch.check_permission("read")
                    row["expiry_date"] = str(batch.get("expiry_date") or "")
                result.append(row)
    return {"rows": result, "company": profile.company, "document": name,
            "quantity_note": _("Fractional stock quantities are rounded up. Review copies before printing.")}


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
    rows = frappe.get_list(
        doctype,
        filters=filters,
        or_filters=or_filters,
        fields=["name", "posting_date", party, "docstatus"],
        order_by="posting_date desc, creation desc",
        limit_page_length=20,
    )
    return [{"name": r.name, "date": str(r.posting_date), "party": r.get(party) or "", "draft": not cint(r.docstatus)} for r in rows]


PRESET = "EsafePOS Label Preset"
JOB = "EsafePOS Label Print Job"


def _require_tables():
    if not frappe.db.table_exists(PRESET) or not frappe.db.table_exists(JOB):
        frappe.throw(_("Run the site migration to save label presets and prepare print jobs."))


@frappe.whitelist()
def workspace(pos_profile):
    profile = _guard(pos_profile)
    from esafepos.api.settings import effective_receipt

    migrated = frappe.db.table_exists(PRESET) and frappe.db.table_exists(JOB)
    presets = frappe.get_all(PRESET, filters={"company": profile.company, "pos_profile": pos_profile},
                             fields=["name", "title", "kind", "configuration", "modified"],
                             order_by="modified desc", limit_page_length=100) if migrated else []
    company_logo = frappe.db.get_value("Company", profile.company, "company_logo") if frappe.get_meta("Company").has_field("company_logo") else ""
    return {"presets": presets, "logo": effective_receipt(pos_profile).get("receipt_logo") or "", "company_logo": company_logo or "",
            "can_manage": permissions.is_manager(), "needs_migration": not migrated}


@frappe.whitelist()
def save_preset(pos_profile, title, kind, configuration, name=None, modified=None):
    profile = _guard(pos_profile)
    _require_tables()
    if not permissions.is_manager():
        frappe.throw(_("Only a manager can save shared label presets."), frappe.PermissionError)
    from esafepos.label_config import KINDS, validate_configuration

    if kind not in KINDS or not str(title or "").strip() or len(title) > 100:
        frappe.throw(_("Choose a preset kind and a name of at most 100 characters."))
    try:
        config = validate_configuration(configuration)
    except (ValueError, TypeError) as exc:
        frappe.throw(str(exc))
    if name:
        doc = frappe.get_doc(PRESET, name)
        if doc.pos_profile != pos_profile or doc.company != profile.company:
            frappe.throw(_("This preset belongs to another outlet."), frappe.PermissionError)
        if not modified or str(doc.modified) != str(modified):
            frappe.throw(_("This preset changed on another device. Reload before saving."))
    else:
        doc = frappe.new_doc(PRESET)
    doc.update({"title": title.strip(), "kind": kind, "pos_profile": pos_profile,
                "company": profile.company, "configuration": json.dumps(config, ensure_ascii=False, allow_nan=False)})
    doc.save()
    return {"name": doc.name, "modified": str(doc.modified)}


def _owned_job(pos_profile, name):
    profile = _guard(pos_profile)
    doc = frappe.get_doc(JOB, name)
    if doc.pos_profile != pos_profile or doc.company != profile.company or (doc.owner != frappe.session.user and not permissions.is_manager()):
        frappe.throw(_("You're not allowed to use this label job."), frappe.PermissionError)
    return doc


@frappe.whitelist()
def prepare_job(pos_profile, rows, configuration, request_id, reprint_of=None):
    profile = _guard(pos_profile)
    _require_tables()
    from esafepos.label_config import validate_configuration, number
    from frappe.utils import nowdate

    if not isinstance(request_id, str) or not 16 <= len(request_id) <= 80:
        frappe.throw(_("A valid label request identifier is required."))
    existing = frappe.db.get_value(JOB, {"request_id": request_id}, "name")
    if existing:
        job = _owned_job(pos_profile, existing)
        return {"name": job.name, "snapshot": json.loads(job.snapshot), "status": job.status}
    try:
        config = validate_configuration(configuration)
    except (ValueError, TypeError) as exc:
        frappe.throw(str(exc))
    if not config.get("stock") or not config.get("design"):
        frappe.throw(_("Choose label stock and a design."))
    if isinstance(rows, str):
        rows = json.loads(rows)
    if not isinstance(rows, list) or not rows or len(rows) > MAX_ITEMS:
        frappe.throw(_("Choose between 1 and 500 item rows."))
    wanted, total = [], 0
    for row in rows:
        if not isinstance(row, dict):
            frappe.throw(_("Invalid label row."))
        try:
            count = number(row.get("qty", 0), 0, 10000, "copies")
        except ValueError as exc:
            frappe.throw(str(exc))
        if count != int(count):
            frappe.throw(_("Label copies must be whole numbers."))
        total += int(count)
        if count:
            wanted.append((row.get("item_code"), 1))
    if not 1 <= total <= 10000:
        frappe.throw(_("Print between 1 and 10,000 labels per job."))
    fresh = {row["item_code"]: row for row in _rows(profile, wanted)}
    resolved = []
    for choice in rows:
        if not cint(choice.get("qty")):
            continue
        code = choice.get("item_code")
        if code not in fresh:
            frappe.throw(_("An item is disabled, missing or no longer readable. Reload the label queue."))
        row = dict(fresh[code])
        _choose_unit(profile, row, choice.get("uom"))
        barcode = choice.get("barcode") or row["barcode"] or code
        if barcode != code and not any(b["barcode"] == barcode and b["uom"] == row["uom"] for b in row.get("barcode_options", [])):
            frappe.throw(_("The selected barcode does not belong to this item."))
        row.update({"qty": cint(choice["qty"]), "barcode": barcode, "shop": profile.company,
                    "print_date": nowdate(), "note": str(choice.get("note") or "")[:500],
                    "qr": str(choice.get("qr") or "")[:1000]})
        if choice.get("batch_no"):
            batch = frappe.get_doc("Batch", choice["batch_no"])
            batch.check_permission("read")
            if batch.item != code:
                frappe.throw(_("The batch does not belong to this item."))
            row.update(batch_no=batch.name, expiry_date=str(batch.get("expiry_date") or ""))
        if choice.get("serial_no"):
            serial = frappe.get_doc("Serial No", choice["serial_no"])
            serial.check_permission("read")
            if serial.item_code != code or serial.get("company") not in (None, "", profile.company):
                frappe.throw(_("The serial number does not belong to this item/company."))
            row["serial_no"] = serial.name
        resolved.append(row)
    if reprint_of:
        _owned_job(pos_profile, reprint_of)
    snapshot = {"configuration": config, "rows": resolved}
    doc = frappe.get_doc({"doctype": JOB, "company": profile.company, "pos_profile": pos_profile,
                          "status": "Prepared", "label_count": total, "request_id": request_id,
                          "snapshot": json.dumps(snapshot, ensure_ascii=False, allow_nan=False), "reprint_of": reprint_of})
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "snapshot": snapshot, "status": doc.status}


@frappe.whitelist()
def job_result(pos_profile, name, status, detail=""):
    doc = _owned_job(pos_profile, name)
    if status not in ("Dialog opened", "Submitted", "Outcome unknown", "Exported", "Canceled"):
        frappe.throw(_("Invalid label print status."))
    if doc.status != "Prepared" and status != "Outcome unknown":
        frappe.throw(_("This label job was already dispatched. Create a new job to print again."))
    doc.db_set({"status": status, "result_detail": str(detail or "")[:1000]})
    return {"status": status}


@frappe.whitelist()
def sign_request(pos_profile, request, job=None):
    """Label-only QZ signer. Never accepts receipt/raw/device-control commands."""
    _guard(pos_profile)
    if not isinstance(request, str) or not request or len(request) > 131072:
        frappe.throw(_("The label print request is too large or invalid."))
    try:
        message = json.loads(request)
    except (ValueError, TypeError):
        frappe.throw(_("Invalid QZ label request."))
    if not isinstance(message, dict):
        frappe.throw(_("Invalid QZ label request."))
    method = message.get("call")
    if method not in ("printers.find", "printers.details", "print"):
        frappe.throw(_("This QZ operation is not permitted for label printing."), frappe.PermissionError)
    if method == "print":
        record = _owned_job(pos_profile, job)
        params = message.get("params") or {}
        if not isinstance(params, dict):
            frappe.throw(_("Invalid QZ label parameters."))
        data, printer = params.get("data"), params.get("printer") or {}
        options = params.get("options") or {}
        if not isinstance(options, dict):
            frappe.throw(_("Invalid QZ label options."))
        if record.status != "Prepared" or options.get("jobName") != "Labels:" + record.name:
            frappe.throw(_("Prepare a new label job before printing."))
        if not isinstance(printer, dict) or not printer.get("name") or any(k in printer for k in ("host", "file", "port")):
            frappe.throw(_("Choose an installed local label printer."))
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict) or data[0].get("type") != "pixel" or data[0].get("format") != "pdf" or data[0].get("flavor") != "base64":
            frappe.throw(_("Label signing accepts only a bounded PDF page."))
        import base64
        try:
            raw = base64.b64decode(data[0]["data"], validate=True)
            if not raw.startswith(b"%PDF-"):
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            frappe.throw(_("Invalid label PDF data."))
    from esafepos.api.qz_printing import _sign
    return _sign(request)
