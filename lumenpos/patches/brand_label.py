# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
"""Give existing Desk records the public ESafe New Gen POS name.

The LumenPOS module, DocType and role identifiers deliberately stay unchanged:
they are stored in customers' ERPNext databases and are part of the app's API.
Only labels that a staff member sees are updated here.
"""

import frappe


BRAND = "ESafe New Gen POS"


def _get_doc(doctype, name):
    if not frappe.db.table_exists(doctype) or not frappe.db.exists(doctype, name):
        return None
    return frappe.get_doc(doctype, name)


def _update_fields(doctype, name, values):
    doc = _get_doc(doctype, name)
    if not doc:
        return
    for fieldname, value in values.items():
        if frappe.db.has_column(doctype, fieldname) and getattr(doc, fieldname, None) != value:
            doc.db_set(fieldname, value, update_modified=False)


def _update_item_titles(doctype, name, labels):
    doc = _get_doc(doctype, name)
    if not doc or not hasattr(doc, "items"):
        return
    changed = False
    for item in doc.items:
        label = getattr(item, "label", None)
        title = getattr(item, "title", None)
        if label in labels:
            item.label = labels[label]
            changed = True
        if title in labels:
            item.title = labels[title]
            changed = True
    if changed:
        doc.db_update()


def _update_workspace_content():
    workspace = _get_doc("Workspace", "LumenPOS")
    if not workspace:
        return

    changed = False
    old_header = "EsafePOS. Point of Sale"
    if old_header in (workspace.content or ""):
        workspace.content = workspace.content.replace(old_header, BRAND + ". Point of Sale")
        changed = True

    for shortcut in workspace.shortcuts or []:
        if shortcut.label == "EsafePOS Settings":
            shortcut.label = BRAND + " Settings"
            changed = True

    if changed:
        workspace.db_update()


def execute():
    _update_fields("Desktop Icon", "LumenPOS", {"label": BRAND})
    _update_fields("Workspace", "LumenPOS", {"label": BRAND, "title": BRAND})
    _update_fields("Workspace Sidebar", "LumenPOS", {"title": BRAND})
    _update_fields("Sidebar", "LumenPOS", {"title": BRAND})

    labels = {
        "EsafePOS": BRAND,
        "EsafePOS Settings": BRAND + " Settings",
        "EsafePOS Audit Log": BRAND + " Audit Log",
    }
    _update_item_titles("Workspace", "LumenPOS", labels)
    _update_item_titles("Workspace Sidebar", "LumenPOS", labels)
    _update_item_titles("Sidebar", "LumenPOS", labels)
    _update_item_titles("Dock", "lumenpos", labels)
    _update_workspace_content()
    frappe.clear_cache()
