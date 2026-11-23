# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
"""Narrow configuration endpoints for the POS Printing workspace."""
import ipaddress
import json
import re

import frappe
from frappe import _


def _require_manager():
    if not frappe.has_permission("EsafePOS Settings", "write"):
        frappe.throw(_("You are not permitted to change printing settings."), frappe.PermissionError)


def _profile(name, write=False):
    from esafepos.api import permissions

    _require_manager()
    if not name:
        frappe.throw(_("Select an outlet."))
    permissions.assert_outlet(name)
    doc = frappe.get_doc("POS Profile", name)
    doc.check_permission("write" if write else "read")
    return doc


@frappe.whitelist()
def receipt_workspace():
    from esafepos.api import permissions, settings

    _require_manager()
    doc = frappe.get_cached_doc("EsafePOS Settings")
    profiles = frappe.get_list("POS Profile", filters={"disabled": 0}, fields=["name", "print_format"], order_by="name", limit_page_length=0)
    profiles = [p for p in profiles if permissions.can_use_outlet(p.name)]
    return {
        "config": settings.receipt_config(doc),
        "custom_fields": settings._global_custom_fields(),
        "profiles": [p.name for p in profiles],
        "print_formats": {p.name: p.get("print_format") or "" for p in profiles},
        "overrides": [r.pos_profile for r in (doc.get("profile_receipts") or [])],
    }


@frappe.whitelist(methods=["POST"])
def save_receipt_defaults(config, custom_fields=None):
    """Save receipt fields only, without rewriting unrelated general settings."""
    from esafepos.api import audit, settings

    _require_manager()
    if isinstance(config, str):
        config = json.loads(config)
    if not isinstance(config, dict):
        frappe.throw(_("Invalid receipt configuration."))
    doc = frappe.get_doc("EsafePOS Settings")
    merged = settings.receipt_config(doc)
    merged.update({key: config[key] for key in settings.RECEIPT_FIELDS if key in config})
    for key, value in settings.receipt_config(merged).items():
        doc.set(key, value)
    if custom_fields is not None:
        doc.set("receipt_custom_fields", json.dumps(settings._clean_custom_fields(custom_fields)))
    doc.save()
    audit.log(audit.SETTINGS_CHANGE, detail="Default receipt updated from Printing")
    return {"ok": True}


@frappe.whitelist()
def get_printer_settings(pos_profile):
    doc = _profile(pos_profile)
    from esafepos.print_config import defaults, FIELDS
    from esafepos.drawer_config import FIELD as DRAWER_FIELD
    doctype = doc.get("esafepos_invoice_mode") or "POS Invoice"
    formats = frappe.get_list("Print Format", filters={"doc_type": doctype, "disabled": 0}, pluck="name", order_by="name", limit_page_length=0)
    return {
        "pos_profile": doc.name,
        "host": doc.get("esafepos_printer_ip") or "",
        "port": doc.get("esafepos_printer_port") or 9100,
        "print_format": doc.get("print_format") or "",
        "formats": formats,
        "invoice_doctype": doctype,
        "can_write": bool(doc.has_permission("write")),
        "needs_migration": not all(doc.meta.has_field(f) for f in ("esafepos_printer_ip", "esafepos_printer_port")),
        "esafe": defaults(doc),
        "esafe_needs_migration": not all(doc.meta.has_field(f) for f in list(FIELDS.values()) + [DRAWER_FIELD]),
    }


@frappe.whitelist(methods=["POST"])
def save_esafe_defaults(pos_profile, values):
    from esafepos.print_config import FIELDS, validate
    from esafepos.api import audit

    doc = _profile(pos_profile, write=True)
    if not all(doc.meta.has_field(f) for f in FIELDS.values()):
        frappe.throw(_("Run the site migration before enabling Esafe silent printing."))
    if isinstance(values, str):
        values = json.loads(values)
    try:
        config = validate(values)
    except ValueError as error:
        frappe.throw(_(str(error)))
    for key, field in FIELDS.items():
        doc.set(field, config[key])
    doc.save()
    audit.log(audit.SETTINGS_CHANGE, detail="Esafe silent-printing defaults updated", pos_profile=pos_profile)
    return config


@frappe.whitelist(methods=["POST"])
def authorize_workstation_setup(pos_profile):
    _profile(pos_profile, write=True)
    return {"allowed": True}


def _destination(host, port):
    if not isinstance(host, str):
        frappe.throw(_("Enter a valid printer IP address or hostname."))
    host = host.strip()
    if host:
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if len(host) > 253 or not all(re.match(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$", label) for label in host.split(".")):
                frappe.throw(_("Enter a valid printer IP address or hostname."))
    if isinstance(port, bool) or not re.match(r"^[0-9]{1,5}$", str(port)) or not 1 <= int(port) <= 65535:
        frappe.throw(_("Printer port must be a whole number between 1 and 65535."))
    return host, int(port)


@frappe.whitelist(methods=["POST"])
def save_printer_settings(pos_profile, host="", port=9100, print_format=""):
    from esafepos.api import audit

    doc = _profile(pos_profile, write=True)
    host, port = _destination(host, port)
    if not all(doc.meta.has_field(f) for f in ("esafepos_printer_ip", "esafepos_printer_port")):
        frappe.throw(_("Run the site migration before changing printer settings."))
    if not isinstance(print_format, str):
        frappe.throw(_("Choose a valid Print Format."))
    print_format = print_format.strip()
    if print_format:
        fmt = frappe.get_doc("Print Format", print_format)
        fmt.check_permission("read")
        if fmt.get("disabled") or fmt.get("doc_type") != (doc.get("esafepos_invoice_mode") or "POS Invoice"):
            frappe.throw(_("Choose an enabled Print Format for this outlet's sale document type."))
    doc.set("esafepos_printer_ip", host or None)
    doc.set("esafepos_printer_port", port)
    doc.set("print_format", print_format or None)
    doc.save()
    audit.log(audit.SETTINGS_CHANGE, detail="Printer settings updated for {0}".format(pos_profile), pos_profile=pos_profile)
    return get_printer_settings(pos_profile)


@frappe.whitelist(methods=["POST"])
def test_printer(pos_profile):
    """A bounded diagnostic only, never a drawer pulse or a business document."""
    from esafepos.api.printing import _send

    doc = _profile(pos_profile, write=True)
    host, port = _destination(doc.get("esafepos_printer_ip") or "", doc.get("esafepos_printer_port") or 9100)
    if not host:
        frappe.throw(_("Save a network printer address before printing a test."))
    _send(host, port, b"\x1b@ESAFE POS printer test\nPrinter connection test.\n\n\n\n\x1dVB\x00")
    return {"submitted": True}
