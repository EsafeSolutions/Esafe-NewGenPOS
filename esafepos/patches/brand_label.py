# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
"""Update the public labels on the app's Desk records."""

import frappe


BRAND = "ESAFE POS"
PREVIOUS_LABELS = ("EsafePOS", "ESafe New Gen POS")


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
    for item in doc.items:
        for fieldname in ("label", "title"):
            value = item.get(fieldname)
            if value in labels:
                item.db_set(fieldname, labels[value], update_modified=False)


def _update_workspace_content():
    workspace = _get_doc("Workspace", "EsafePOS")
    if not workspace:
        return

    changed = False
    content = workspace.content or ""
    for label in PREVIOUS_LABELS:
        content = content.replace(label + ". Point of Sale", BRAND + ". Point of Sale")
        content = content.replace(label + " Settings", BRAND + " Settings")
    if content != (workspace.content or ""):
        workspace.content = content
        changed = True

    for shortcut in workspace.shortcuts or []:
        for label in PREVIOUS_LABELS:
            if shortcut.label == label + " Settings":
                shortcut.db_set("label", BRAND + " Settings", update_modified=False)
                break

    if changed:
        workspace.db_update()


def execute():
    _update_fields("Desktop Icon", "EsafePOS", {"label": BRAND})
    _update_fields("Workspace", "EsafePOS", {"label": BRAND, "title": BRAND})
    _update_fields("Workspace Sidebar", "EsafePOS", {"title": BRAND})
    _update_fields("Sidebar", "EsafePOS", {"title": BRAND})

    labels = {label + suffix: BRAND + suffix for label in PREVIOUS_LABELS
              for suffix in ("", " Settings", " Audit Log")}
    _update_item_titles("Workspace", "EsafePOS", labels)
    _update_item_titles("Workspace Sidebar", "EsafePOS", labels)
    _update_item_titles("Sidebar", "EsafePOS", labels)
    _update_item_titles("Dock", "esafepos", labels)
    _update_workspace_content()
    frappe.clear_cache()
