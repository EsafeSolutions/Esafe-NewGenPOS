"""Native ERPNext item templates, attributes and variant creation for the POS."""
import json

import frappe
from frappe import _
from frappe.utils import cint

from esafepos.api.items import _profile, _require, _can_create, _json_list


@frappe.whitelist()
def options(pos_profile):
    _profile(pos_profile)
    attributes = []
    if frappe.has_permission("Item Attribute", "read"):
        for name in frappe.get_list("Item Attribute", pluck="name", order_by="name asc", limit_page_length=0):
            doc = frappe.get_doc("Item Attribute", name)
            doc.check_permission("read")
            attributes.append({"name": name, "numeric_values": bool(doc.numeric_values),
                               "from_range": doc.from_range, "to_range": doc.to_range, "increment": doc.increment,
                               "values": [row.attribute_value for row in doc.get("item_attribute_values") or []]})
    return {"attributes": attributes, "can_create": bool(_can_create()),
            "can_create_attribute": bool(_can_create() and frappe.has_permission("Item Attribute", "create"))}


@frappe.whitelist()
def template_details(pos_profile, item_code, start=0):
    _profile(pos_profile)
    template = frappe.get_doc("Item", item_code)
    template.check_permission("read")
    if not template.has_variants:
        frappe.throw(_("Choose an item template."))
    return {"item_code": template.name, "item_name": template.item_name, "disabled": bool(template.disabled),
            "variant_based_on": template.variant_based_on,
            "attributes": [row.attribute for row in template.get("attributes") or []],
            "variants": frappe.get_list("Item", filters={"variant_of": template.name},
                                        fields=["name", "item_name", "disabled", "stock_uom"],
                                        order_by="item_name asc, name asc", limit_start=max(0, cint(start)), limit_page_length=50)}


@frappe.whitelist(methods=["POST"])
def create_attribute(pos_profile, attribute_name, values):
    _profile(pos_profile)
    _require(_can_create() and frappe.has_permission("Item Attribute", "create"))
    if not isinstance(attribute_name, str) or not attribute_name.strip() or len(attribute_name) > 140:
        frappe.throw(_("Enter an attribute name of 1 to 140 characters."))
    rows = _json_list(values, "Send attribute values and abbreviations.")
    if not rows or len(rows) > 100:
        frappe.throw(_("Enter between 1 and 100 attribute values."))
    cleaned, names, abbreviations = [], set(), set()
    for row in rows:
        value, abbr = row.get("attribute_value"), row.get("abbr")
        if (not isinstance(value, str) or not isinstance(abbr, str) or not value.strip() or not abbr.strip()
                or len(value) > 140 or len(abbr) > 20 or value.strip().casefold() in names
                or abbr.strip().casefold() in abbreviations):
            frappe.throw(_("Use unique values and abbreviations (up to 140 and 20 characters)."))
        names.add(value.strip().casefold())
        abbreviations.add(abbr.strip().casefold())
        cleaned.append({"attribute_value": value.strip(), "abbr": abbr.strip()})
    doc = frappe.get_doc({"doctype": "Item Attribute", "attribute_name": attribute_name.strip(),
                          "numeric_values": 0, "item_attribute_values": cleaned})
    doc.check_permission("create")
    doc.insert()
    return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def create_template(pos_profile, item_code, item_name, item_group, stock_uom, attributes):
    profile = _profile(pos_profile)
    _require(_can_create())
    if any(not isinstance(value, str) or not value.strip() or len(value) > 140 for value in (item_code, item_name)):
        frappe.throw(_("Enter an item code and name of 1 to 140 characters."))
    rows = _json_list(attributes, "Choose template attributes.")
    names = [row.get("attribute") for row in rows]
    if not names or len(names) > 10 or any(not isinstance(name, str) or not name for name in names) or len(names) != len(set(names)):
        frappe.throw(_("Choose between 1 and 10 unique attributes."))
    template_attributes = []
    for name in names:
        attribute = frappe.get_doc("Item Attribute", name)
        attribute.check_permission("read")
        template_attributes.append({"attribute": name, "numeric_values": attribute.numeric_values,
                                    "from_range": attribute.from_range, "to_range": attribute.to_range,
                                    "increment": attribute.increment})
    group = frappe.get_doc("Item Group", item_group)
    group.check_permission("read")
    if group.is_group:
        frappe.throw(_("Choose a leaf item category."))
    frappe.get_doc("UOM", stock_uom).check_permission("read")
    doc = frappe.get_doc({"doctype": "Item", "item_code": item_code.strip(), "item_name": item_name.strip(),
                          "item_group": item_group, "stock_uom": stock_uom, "is_stock_item": 1,
                          "is_sales_item": 1, "is_purchase_item": 1, "has_variants": 1,
                          "variant_based_on": "Item Attribute", "attributes": template_attributes})
    doc.check_permission("create")
    doc.insert()
    _audit("Item template created in POS", doc.name, profile.name)
    return {"item_code": doc.name}


@frappe.whitelist(methods=["POST"])
def create_variant(pos_profile, template_code, values):
    profile = _profile(pos_profile)
    _require(_can_create())
    template = frappe.get_doc("Item", template_code)
    template.check_permission("read")
    if not template.has_variants or template.disabled or template.variant_based_on != "Item Attribute":
        frappe.throw(_("Choose an enabled template based on item attributes."))
    if isinstance(values, str):
        try:
            values = json.loads(values)
        except ValueError:
            frappe.throw(_("Choose a value for every template attribute."))
    names = [row.attribute for row in template.get("attributes") or []]
    if (not isinstance(values, dict) or not names or set(values) != set(names)
            or any(not isinstance(value, (str, int, float)) or isinstance(value, bool)
                   or not str(value).strip() or len(str(value)) > 140 for value in values.values())):
        frappe.throw(_("Choose a value for every template attribute."))
    for name in names:
        frappe.get_doc("Item Attribute", name).check_permission("read")
    values = {name: str(value).strip() for name, value in values.items()}
    # Prevent two tills creating the same combination simultaneously.
    frappe.db.sql("select name from `tabItem` where name=%s for update", (template_code,))
    template = frappe.get_doc("Item", template_code, for_update=True)
    template.check_permission("read")
    if (template.disabled or not template.has_variants or template.variant_based_on != "Item Attribute"
            or set(values) != {row.attribute for row in template.get("attributes") or []}):
        frappe.throw(_("The template changed. Refresh it before creating a variant."))
    from erpnext.controllers.item_variant import get_variant, create_variant as native_create_variant

    existing = _current_variant(template_code, values) or get_variant(template_code, args=values)
    if existing:
        frappe.get_doc("Item", existing, for_update=True).check_permission("read")
        return {"item_code": existing, "existing": True}
    doc = native_create_variant(template_code, values, use_template_image=True)
    doc.check_permission("create")
    doc.insert()
    _audit("Item variant created in POS", doc.name, profile.name)
    return {"item_code": doc.name, "existing": False}


def _current_variant(template_code, values):
    """See combinations committed while this request waited for the template lock."""
    rows = frappe.db.sql(
        """select i.name, a.attribute, a.attribute_value
        from `tabItem` i inner join `tabItem Variant Attribute` a on a.parent=i.name and a.parenttype='Item'
        where i.variant_of=%s order by i.name, a.idx for update""", (template_code,), as_dict=True)
    combinations = {}
    for row in rows:
        combinations.setdefault(row.name, {})[row.attribute] = str(row.attribute_value)
    return next((name for name, attributes in combinations.items() if attributes == values), None)


def _audit(action, item_code, pos_profile):
    from esafepos.api import audit

    audit.log(action, detail=item_code, reference_doctype="Item", reference_name=item_code, pos_profile=pos_profile)
