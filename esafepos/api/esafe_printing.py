# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
"""Authorized print preparation and metadata-only client-reported audit."""
import base64
import hashlib
import json
import re
from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.utils import cint

DOCTYPE = "EsafePOS Print Intent"
STATES = ("prepared", "queued", "preparing", "submitting", "submitted", "completed", "failed", "cancelled", "unknown")


def _source(pos_profile, reference, role=None):
    from esafepos.api import permissions

    if frappe.session.user == "Guest":
        frappe.throw(_("Sign in before printing."), frappe.PermissionError)
    permissions.assert_outlet(pos_profile)
    if not isinstance(reference, dict):
        frappe.throw(_("Invalid print reference."))
    doctype, name = reference.get("doctype"), reference.get("name")
    if doctype in ("POS Invoice", "Sales Invoice"):
        from esafepos.api.sales import get_receipt

        get_receipt(name)
        doc = frappe.get_doc(doctype, name)
        doc.check_permission("read")
        if role == "receipt" and cint(reference.get("reprint")) and not permissions.can_reprint():
            frappe.throw(_("You are not allowed to reprint a receipt."), frappe.PermissionError)
    elif doctype == "EsafePOS Label Print Job":
        from esafepos.api.labels import _owned_job

        doc = _owned_job(pos_profile, name)
    elif doctype == "POS Register Session":
        if role != "drawer":
            from esafepos.api.register import get_session_summary
            get_session_summary(name)
        doc = frappe.get_doc(doctype, name)
        doc.check_permission("read")
    elif doctype == "Journal Entry":
        from esafepos.api.credit import payment_receipt

        payment = payment_receipt(name)
        if payment.get("pos_profile") and payment["pos_profile"] != pos_profile:
            frappe.throw(_("This payment belongs to another outlet."), frappe.PermissionError)
        doc = frappe.get_doc(doctype, name)
    elif doctype == "Quotation":
        doc = frappe.get_doc(doctype, name)
        doc.check_permission("read")
    elif doctype == "POS Profile" and name == pos_profile:
        from esafepos.api.printing_settings import _profile

        if reference.get("test_label"):
            from esafepos.api.labels import _guard

            doc = _guard(name)
        else:
            doc = _profile(name, write=True)
    else:
        frappe.throw(_("This document is not supported for POS printing."), frappe.PermissionError)
    profile = doc.get("pos_profile") or doc.get("esafepos_pos_profile")
    if profile and profile != pos_profile:
        frappe.throw(_("The print document belongs to another outlet."), frappe.PermissionError)
    company = doc.get("company")
    if company and company != frappe.get_cached_value("POS Profile", pos_profile, "company"):
        frappe.throw(_("The print document belongs to another company."), frappe.PermissionError)
    return doc


@frappe.whitelist()
def receipt_output(invoice, output="raw", reprint=0):
    from esafepos.api.sales import get_receipt, _doctype_of
    from esafepos.api import permissions

    if cint(reprint) and not permissions.can_reprint():
        frappe.throw(_("You are not allowed to reprint a receipt."), frappe.PermissionError)
    receipt = get_receipt(invoice)
    if output == "raw":
        from esafepos.api.printing import build_receipt_bytes

        return {"format": "raw", "data": base64.b64encode(build_receipt_bytes(receipt, open_drawer=0)).decode("ascii")}
    if output != "pdf":
        frappe.throw(_("Choose raw receipt bytes or an ERPNext PDF."))
    return document_pdf(_doctype_of(invoice), invoice)


@frappe.whitelist()
def document_pdf(doctype, name):
    doc, fmt = _print_document(doctype, name)
    data = frappe.get_print(doctype, name, print_format=fmt or None, as_pdf=True)
    if not isinstance(data, bytes) or len(data) > 10 * 1024 * 1024:
        frappe.throw(_("The rendered document is too large or invalid."))
    return {"format": "pdf", "data": base64.b64encode(data).decode("ascii")}


def _print_document(doctype, name):
    if doctype not in ("POS Invoice", "Sales Invoice", "Quotation"):
        frappe.throw(_("Unsupported print document."), frappe.PermissionError)
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    doc.check_permission("print")
    from esafepos.api import permissions

    profile = doc.get("pos_profile") or doc.get("esafepos_pos_profile")
    if profile:
        permissions.assert_outlet(profile)
    fmt = frappe.db.get_value("POS Profile", profile, "print_format") if profile else None
    if fmt and frappe.db.get_value("Print Format", fmt, "doc_type") != doctype:
        fmt = None
    return doc, fmt


@frappe.whitelist()
def document_printview(doctype, name):
    doc, fmt = _print_document(doctype, name)
    return {"url": "/printview?" + urlencode({"doctype": doctype, "name": name, "format": fmt or "Standard"})}


@frappe.whitelist(methods=["POST"])
def register_intent(pos_profile, request_id, workstation, payload_hash, reference, role, output, reprint_of="", automatic=0, printer_id="", drawer=None):
    if isinstance(reference, str):
        reference = json.loads(reference)
    source = _source(pos_profile, reference, role=role)
    if not re.match(r"^[a-f0-9-]{36}$", str(request_id)) or not re.match(r"^[a-f0-9-]{36}$", str(workstation)):
        frappe.throw(_("Invalid print intent identity."))
    if not re.match(r"^[A-Za-z0-9+/]{43}=$", str(payload_hash)):
        frappe.throw(_("Invalid print payload hash."))
    if role not in ("receipt", "labels", "document", "report", "drawer") or output not in ("raw", "html", "pdf", "image"):
        frappe.throw(_("Invalid print purpose or output."))
    allowed = {"receipt": ("POS Invoice", "Sales Invoice", "POS Profile"), "labels": ("EsafePOS Label Print Job", "POS Profile"),
               "document": ("POS Invoice", "Sales Invoice", "Quotation"), "report": ("POS Register Session", "Journal Entry"),
               "drawer": ("POS Profile", "POS Register Session", "POS Invoice", "Sales Invoice")}
    if source.doctype not in allowed[role]:
        frappe.throw(_("The source document does not match this print purpose."), frappe.PermissionError)
    if role == "document":
        source.check_permission("print")
    if cint(automatic) and role != "drawer" and (role != "receipt" or source.get("docstatus") != 1 or cint(reference.get("reprint"))):
        frappe.throw(_("Automatic receipts require a successfully submitted sale."), frappe.PermissionError)
    if not frappe.db.exists("DocType", DOCTYPE):
        frappe.throw(_("Run the site migration before using silent printing."))
    original_key = None
    if role == "receipt" and source.doctype in ("POS Invoice", "Sales Invoice") and not cint(reference.get("reprint")):
        original_key = hashlib.sha256((source.doctype + ":" + source.name + ":receipt").encode("utf-8")).hexdigest()
    drawer_fields = {}
    if role == "drawer":
        from esafepos.api.cash_drawer import authorize
        drawer = json.loads(drawer) if isinstance(drawer, str) else drawer
        if output != "raw" or reprint_of or reference.get("reprint") or not isinstance(drawer, dict):
            frappe.throw(_("A drawer opening requires its own pulse-only raw intent."), frappe.PermissionError)
        already = frappe.db.get_value(DOCTYPE, {"request_id": request_id}, "name")
        drawer_fields = authorize(pos_profile, workstation, printer_id, source, drawer, existing=bool(already))
        if drawer_fields["drawer_mode"] == "payment":
            original_key = hashlib.sha256((source.doctype + ":" + source.name + ":drawer").encode("utf-8")).hexdigest()
    existing = frappe.db.get_value(DOCTYPE, {"request_id": request_id}, "name")
    if not existing and original_key:
        existing = frappe.db.get_value(DOCTYPE, {"original_key": original_key}, "name")
    if existing:
        old = frappe.get_doc(DOCTYPE, existing)
        if (old.workstation != workstation or old.owner != frappe.session.user or old.request_id != request_id or old.payload_hash != payload_hash
                or old.role != role or old.pos_profile != pos_profile or old.get("printer_id", "") != printer_id
                or old.reference_doctype != source.doctype or old.reference_name != source.name or old.output != output
                or old.get("original_key") != original_key or (old.get("reprint_of") or "") != (reprint_of or "")
                or any(old.get(key) != value for key, value in drawer_fields.items())):
            frappe.throw(_("An original print intent already exists. Reconcile it or create an authorized reprint."), frappe.PermissionError)
        return {"name": old.name}
    if reprint_of:
        original = frappe.get_doc(DOCTYPE, reprint_of)
        if original.role == "drawer" or original.role != role:
            frappe.throw(_("Drawer intents cannot be reprinted or reused as another print purpose."), frappe.PermissionError)
        if original.reference_doctype != source.doctype or original.reference_name != source.name:
            frappe.throw(_("The reprint must reference the same document."), frappe.PermissionError)
    doc = frappe.get_doc({"doctype": DOCTYPE, "request_id": request_id, "original_key": original_key,
                          "workstation": workstation, "payload_hash": payload_hash, "pos_profile": pos_profile,
                          "company": source.get("company") or frappe.get_cached_value("POS Profile", pos_profile, "company"),
                          "reference_doctype": source.doctype, "reference_name": source.name,
                          "role": role, "output": output, "state": "prepared", "printer_id": printer_id,
                          "reprint_of": reprint_of or None, **drawer_fields})
    doc.insert(ignore_permissions=True)
    if role == "drawer":
        from esafepos.api import audit
        audit.log("Cash drawer pulse", reference_doctype=source.doctype, reference_name=source.name, pos_profile=pos_profile,
                  detail="Intent {0}; workstation {1}; printer {2}; {3}".format(doc.name, workstation, printer_id, json.dumps(drawer_fields)))
    if cint(reference.get("reprint")):
        from esafepos.api import audit

        audit.log(audit.REPRINT, reference_doctype=source.doctype, reference_name=source.name,
                  pos_profile=pos_profile, detail="Esafe print intent {0}; original intent {1}".format(doc.name, reprint_of or "historical receipt"))
    return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def record_event(request_id, state, job_id="", certainty="", detail=""):
    if state not in STATES:
        frappe.throw(_("Invalid reported print state."))
    doc = frappe.get_doc(DOCTYPE, frappe.db.get_value(DOCTYPE, {"request_id": request_id}, "name"))
    if doc.owner != frappe.session.user:
        frappe.throw(_("You cannot update another user's print intent."), frappe.PermissionError)
    _source(doc.pos_profile, {"doctype": doc.reference_doctype, "name": doc.reference_name,
                              "test_label": doc.role == "labels" and doc.reference_doctype == "POS Profile"}, role=doc.role)
    doc.db_set({"state": state, "agent_job_id": str(job_id or "")[:140],
                "certainty": str(certainty or "")[:140], "result_detail": str(detail or "")[:500]})
    return {"ok": True}


@frappe.whitelist()
def environment():
    from esafepos.api.printing_settings import _require_manager
    from esafepos import __version__
    _require_manager()
    import erpnext

    return {"frappe": frappe.__version__, "erpnext": erpnext.__version__, "esafepos": __version__,
            "installed_apps": frappe.get_installed_apps(), "sdk": "0.2.0", "protocol": 1}
