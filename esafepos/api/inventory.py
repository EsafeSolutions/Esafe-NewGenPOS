"""Add incoming goods with a native, auditable ERPNext Material Receipt."""
import hashlib
import json

import frappe
from frappe import _

from esafepos.api.items import _profile, _require, _can_receive_stock, _warehouses, _number, warehouse_stock


@frappe.whitelist(methods=["POST"])
def receive_stock(pos_profile, item_code, warehouse, qty, valuation_rate, reason, request_id, serial_no="", batch_no=""):
    profile = _profile(pos_profile)
    _require(_can_receive_stock())
    item = frappe.get_doc("Item", item_code)
    item.check_permission("read")
    _require(warehouse in _warehouses(profile))
    frappe.get_doc("Warehouse", warehouse).check_permission("read")
    qty = _number(qty, "Enter a received quantity greater than zero.")
    rate = _number(valuation_rate, "Enter a unit cost greater than zero.")
    if qty <= 0 or rate <= 0:
        frappe.throw(_("Enter a received quantity and unit cost greater than zero."))
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        frappe.throw(_("Enter a receipt reason of 1 to 500 characters."))
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 100:
        frappe.throw(_("A receipt request ID is required. Reopen the form."))
    if not isinstance(serial_no, str) or not isinstance(batch_no, str) or len(batch_no) > 140:
        frappe.throw(_("Enter valid serial and batch numbers."))
    serials = [value.strip() for value in serial_no.splitlines() if value.strip()]
    payload = [item_code, warehouse, qty, rate, reason.strip(), sorted(serials), batch_no]
    fingerprint = hashlib.sha256(json.dumps(payload, ensure_ascii=True).encode()).hexdigest()
    identity = hashlib.sha256((frappe.session.user + ":" + profile.name + ":" + request_id).encode()).hexdigest()[:32]
    name = "POS-RCV-" + identity
    remarks = "EsafePOS receipt " + fingerprint + "\n" + reason.strip()
    frappe.db.sql("select name from `tabItem` where name=%s for update", (item_code,))
    if frappe.db.get_value("Stock Entry", name, "name", for_update=True):
        previous = frappe.get_doc("Stock Entry", name, for_update=True)
        previous.check_permission("read")
        if (previous.docstatus != 1 or previous.company != profile.company
                or previous.purpose != "Material Receipt" or previous.remarks != remarks):
            frappe.throw(_("This request was already used. Review the earlier Material Receipt in ERPNext."))
        return _result(profile, item_code, previous.name, True)
    item = frappe.get_doc("Item", item_code, for_update=True)
    item.check_permission("read")
    if item.disabled or not item.is_stock_item or item.has_variants:
        frappe.throw(_("Choose an enabled stock item or individual variant."))
    if frappe.get_cached_value("UOM", item.stock_uom, "must_be_whole_number") and qty != int(qty):
        frappe.throw(_("This stock unit requires a whole received quantity."))
    if item.has_serial_no and (qty != len(serials) or len(serials) != len(set(serials))):
        frappe.throw(_("Enter one unique serial number for each received unit."))
    if item.has_batch_no and not batch_no:
        frappe.throw(_("Enter the batch number to receive."))
    if (not item.has_serial_no and serials) or (not item.has_batch_no and batch_no):
        frappe.throw(_("Tracking details do not match this item."))
    from esafepos.api.stock_app import _has_workflow

    if _has_workflow("Stock Entry"):
        frappe.throw(_("This site requires stock approval. Create the Material Receipt in ERPNext."))
    row = {"item_code": item_code, "t_warehouse": warehouse, "qty": qty, "uom": item.stock_uom,
           "stock_uom": item.stock_uom, "conversion_factor": 1, "basic_rate": rate}
    detail_meta = frappe.get_meta("Stock Entry Detail")
    if detail_meta.has_field("set_basic_rate_manually"):
        row["set_basic_rate_manually"] = 1
    if serials:
        row["serial_no"] = "\n".join(serials)
    if batch_no:
        row["batch_no"] = batch_no
    if (serials or batch_no) and detail_meta.has_field("use_serial_batch_fields"):
        row["use_serial_batch_fields"] = 1
    doc = frappe.get_doc({"doctype": "Stock Entry", "company": profile.company, "stock_entry_type": "Material Receipt",
                          "purpose": "Material Receipt", "to_warehouse": warehouse, "remarks": remarks, "items": [row]})
    doc.check_permission("create")
    doc.check_permission("submit")
    doc.insert(set_name=name)
    doc.submit()
    from esafepos.api import audit

    audit.log("Stock received in POS", detail="{}: {} {} into {}. {}".format(item_code, qty, item.stock_uom, warehouse, reason.strip()),
              reference_doctype="Stock Entry", reference_name=doc.name, pos_profile=profile.name)
    return _result(profile, item_code, doc.name, False)


def _result(profile, item_code, name, replayed):
    frappe.local.esafepos_pos_reserved = {}
    return {"name": name, "replayed": replayed, "stock": warehouse_stock(profile.name, item_code)}
