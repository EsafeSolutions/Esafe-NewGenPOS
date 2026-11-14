# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
"""Move an existing site's POS records to the ESAFE POS namespace."""

import json
import re
from pathlib import Path

import frappe


APP = "esafepos"
MODULE = "EsafePOS"
DOCTYPES = (
    "Settings",
    "Company Setting",
    "Payment Method Rule",
    "Profile Receipt",
    "Audit Log",
    "User PIN",
)
ROLES = ("Cashier", "Manager", "Reports")
DESK_RECORDS = ("Workspace", "Workspace Sidebar", "Desktop Icon", "Sidebar")


def _rename(doctype, old, new):
    if frappe.db.exists(doctype, old):
        frappe.rename_doc(
            doctype, old, new, force=True, ignore_permissions=True,
            show_alert=False, rebuild_search=False,
        )


def _require_free_name(doctype, old, new):
    if frappe.db.exists(doctype, old) and frappe.db.exists(doctype, new):
        raise RuntimeError("Both {} records exist in {}: {} and {}".format(doctype, frappe.local.site, old, new))


def _custom_fields(previous_app):
    fields = frappe.get_all(
        "Custom Field", filters={"fieldname": ("like", previous_app + "_%")},
        fields=["name", "dt", "fieldname", "fieldtype", "options"],
    )
    return [field for field in fields if field.fieldname.startswith(previous_app + "_")]


def _new_fieldname(old, previous_app):
    return APP + old[len(previous_app):]


def _rename_column(doctype, old, new):
    if hasattr(frappe.db, "rename_column"):
        frappe.db.rename_column(doctype, old, new)
        return

    # Older MariaDB adapters lack rename_column and need the existing definition.
    # The identifiers come from Custom Field metadata, so escape them as SQL identifiers.
    table = "tab" + doctype.replace("`", "``")
    if not all(re.fullmatch(r"[a-z0-9_]+", fieldname) for fieldname in (old, new)):
        raise ValueError("Invalid POS column name")
    ddl = frappe.db.sql("SHOW CREATE TABLE `{}`".format(table))[0][1]
    prefix = "`" + old + "` "
    definition = next(line.strip()[len(prefix):].rstrip(",") for line in ddl.splitlines()
                      if line.strip().startswith(prefix))
    frappe.db.sql_ddl(
        "ALTER TABLE `{}` CHANGE COLUMN `{}` `{}` {}".format(table, old, new, definition)
    )


def _rename_custom_field(field, previous_app):
    old = field.fieldname
    new = _new_fieldname(old, previous_app)
    doctype = field.dt
    if frappe.db.has_column(doctype, old):
        _rename_column(doctype, old, new)

    if field.fieldtype in ("Table", "Table MultiSelect"):
        frappe.db.set_value(
            field.options, {"parenttype": doctype, "parentfield": old}, "parentfield", new,
            update_modified=False,
        )
    if frappe.get_meta(doctype).issingle:
        frappe.db.sql(
            "UPDATE `tabSingles` SET field=%s WHERE doctype=%s AND field=%s", (new, doctype, old)
        )
    if field.fieldtype == "Password":
        frappe.db.sql(
            "UPDATE `__Auth` SET fieldname=%s WHERE doctype=%s AND fieldname=%s", (new, doctype, old)
        )

    _rename("Custom Field", field.name, doctype + "-" + new)
    frappe.db.set_value("Custom Field", doctype + "-" + new, "fieldname", new, update_modified=False)
    frappe.db.set_value("Custom Field", {"dt": doctype, "insert_after": old}, "insert_after", new,
                        update_modified=False)
    frappe.db.set_value("Property Setter", {"doc_type": doctype, "field_name": old}, "field_name", new,
                        update_modified=False)
    frappe.db.set_value("Custom Field", {"dt": doctype, "options": old}, "options", new,
                        update_modified=False)
    frappe.clear_cache(doctype=doctype)
    frappe.db.commit()


def _update_owned_records(previous_app, previous_module):
    old_settings = previous_module + " Settings"
    settings = MODULE + " Settings"
    schema_path = Path(__file__).parent / APP / "doctype" / "esafepos_settings" / "esafepos_settings.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    for field in schema["fields"]:
        if field["fieldtype"] not in ("Table", "Table MultiSelect"):
            continue
        doctype = field["options"]
        if frappe.db.table_exists(doctype):
            frappe.db.set_value(
                doctype, {"parenttype": settings, "parent": old_settings}, "parent", settings,
                update_modified=False,
            )
    frappe.db.sql("UPDATE `__Auth` SET doctype=%s, name=%s WHERE doctype=%s AND name=%s",
                  (settings, settings, old_settings, old_settings))
    for suffix in DOCTYPES:
        old = previous_module + " " + suffix
        new = MODULE + " " + suffix
        frappe.db.sql("UPDATE `__Auth` SET doctype=%s WHERE doctype=%s", (new, old))

    for doctype in ("Workspace Sidebar", "Desktop Icon", "Sidebar", "Dock"):
        if frappe.db.table_exists(doctype) and frappe.db.has_column(doctype, "app"):
            frappe.db.set_value(
                doctype, {"app": previous_app}, "app", APP, update_modified=False,
            )
    for doctype in ("Workspace Sidebar Item", "Sidebar Item", "Dock Item", "Desktop Icon",
                    "Workspace Link", "Workspace Shortcut"):
        if not frappe.db.table_exists(doctype) or not frappe.db.has_column(doctype, "link_to"):
            continue
        for old, new in ((previous_module, MODULE), (old_settings, settings),
                         (previous_module + " Audit Log", MODULE + " Audit Log")):
            frappe.db.set_value(doctype, {"link_to": old}, "link_to", new, update_modified=False)

    for key in ("help_seen_version", "help_tours_done"):
        frappe.db.set_value("DefaultValue", {"defkey": previous_app + "_" + key}, "defkey", APP + "_" + key,
                            update_modified=False)
    for patch in frappe.get_all("Patch Log", filters={"patch": ("like", previous_app + ".patches.%")},
                                fields=["name", "patch"]):
        frappe.db.set_value("Patch Log", patch.name, "patch", APP + patch.patch[len(previous_app):],
                            update_modified=False)
    if frappe.db.table_exists("Scheduled Job Type"):
        for job in frappe.get_all("Scheduled Job Type", filters={"method": ("like", previous_app + ".%")},
                                  fields=["name", "method"]):
            frappe.db.set_value("Scheduled Job Type", job.name, "method", APP + job.method[len(previous_app):],
                                update_modified=False)


def execute(previous_app):
    """Run from the site's Bench console before the first migration to ESAFE POS."""
    if not re.fullmatch(r"[a-z][a-z0-9_]*", previous_app) or previous_app == APP:
        raise ValueError("Provide the previous POS app ID from the site's installed apps.")
    installed = json.loads(frappe.db.get_global("installed_apps") or "[]")
    if previous_app not in installed:
        if APP in installed:
            return
        raise RuntimeError("The previous app is missing from this site's installed apps.")
    if APP in installed or APP not in frappe.get_all_apps():
        raise RuntimeError("Add ESAFE POS to this Bench before upgrading the site.")
    previous_module = frappe.db.get_value("Module Def", {"app_name": previous_app}, "name")
    if not previous_module and frappe.db.exists("Module Def", MODULE):
        # A previous attempt may have moved the module before a later step failed.
        previous_module = frappe.get_module_list(previous_app)[0]
    register_module = frappe.db.get_value("DocType", "POS Register Session", "module")
    if not previous_module or register_module not in (previous_module, MODULE):
        raise RuntimeError("The previous app does not own POS Register Session on this site.")

    pairs = [("Module Def", previous_module, MODULE)]
    pairs.extend(("DocType", previous_module + " " + name, MODULE + " " + name) for name in DOCTYPES)
    pairs.extend(("Role", previous_module + " " + role, MODULE + " " + role) for role in ROLES)
    pairs.extend((doctype, previous_module, MODULE) for doctype in DESK_RECORDS
                 if frappe.db.table_exists(doctype))
    if frappe.db.table_exists("Dock"):
        pairs.append(("Dock", previous_app, APP))
    pairs.append(("Item", previous_app.upper() + "-DEPOSIT", APP.upper() + "-DEPOSIT"))
    for doctype, old, new in pairs:
        _require_free_name(doctype, old, new)
    for field in _custom_fields(previous_app):
        new = _new_fieldname(field.fieldname, previous_app)
        _require_free_name("Custom Field", field.name, field.dt + "-" + new)
        if frappe.db.has_column(field.dt, field.fieldname) and frappe.db.has_column(field.dt, new):
            raise RuntimeError("Both POS columns already exist on {}: {} and {}".format(field.dt, field.fieldname, new))

    # A patch may rename standard DocTypes without trying to move source files.
    previous_in_patch = frappe.flags.in_patch
    previous_developer_mode = frappe.conf.developer_mode
    frappe.flags.in_patch = True
    frappe.conf.developer_mode = 0
    frappe.local.module_app[APP] = APP
    try:
        # Newer Desk controllers resolve their files through the record's app.
        if frappe.db.table_exists("Desktop Icon") and frappe.db.has_column("Desktop Icon", "app"):
            frappe.db.set_value("Desktop Icon", {"app": previous_app}, "app", APP, update_modified=False)
        for doctype, old, new in pairs:
            _rename(doctype, old, new)
        frappe.db.set_value("Module Def", MODULE, "app_name", APP, update_modified=False)
        for field in _custom_fields(previous_app):
            _rename_custom_field(field, previous_app)
        _update_owned_records(previous_app, previous_module)
        from esafepos.patches.brand_label import execute as update_desk_labels

        update_desk_labels()
        frappe.db.set_global(
            "installed_apps", json.dumps([APP if app == previous_app else app for app in installed])
        )
        frappe.db.commit()
        frappe.clear_cache()
    finally:
        frappe.flags.in_patch = previous_in_patch
        frappe.conf.developer_mode = previous_developer_mode
