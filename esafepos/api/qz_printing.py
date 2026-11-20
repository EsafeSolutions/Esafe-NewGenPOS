# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
"""QZ Tray signing and receipt payload endpoints."""

from __future__ import annotations

import base64

import frappe
from frappe import _
from frappe.exceptions import ValidationError

DOCTYPE = "EsafePOS Settings"
CERTIFICATE_FIELD = "qz_signing_certificate"
PRIVATE_KEY_FIELD = "qz_signing_private_key"


def _settings():
    doc = frappe.get_doc(DOCTYPE)
    if not doc.meta.has_field(CERTIFICATE_FIELD) or not doc.meta.has_field(PRIVATE_KEY_FIELD):
        frappe.throw(_("Run the site migration before configuring QZ Tray."))
    return doc


def _validate_pair(certificate, private_key):
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        certificate_obj = x509.load_pem_x509_certificate(certificate.encode("utf-8"))
        private_obj = serialization.load_pem_private_key(private_key.encode("utf-8"), password=None)
        public_bytes = certificate_obj.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        private_public_bytes = private_obj.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        if public_bytes != private_public_bytes:
            frappe.throw(_("The QZ certificate and private key do not match."))
        if not isinstance(private_obj, rsa.RSAPrivateKey) or private_obj.key_size < 2048:
            frappe.throw(_("The QZ signing key must be at least 2048 bits."))
        return private_obj
    except ValidationError:
        raise
    except Exception:
        frappe.throw(_("Could not read the QZ certificate/private key pair. Use the PEM certificate and an unencrypted PKCS#8 PEM private key."))


@frappe.whitelist(methods=["POST"])
def get_signing_certificate():
    """Return only the public certificate; the signing key stays encrypted."""
    doc = _settings()
    certificate = (doc.get(CERTIFICATE_FIELD) or "").strip()
    private_key = doc.get_password(PRIVATE_KEY_FIELD, raise_exception=False)
    return {
        "certificate": certificate or None,
        "configured": bool(certificate and private_key),
    }


@frappe.whitelist(methods=["POST"])
def save_signing_config(certificate="", private_key="", clear=0):
    doc = _settings()
    doc.check_permission("write")
    if int(clear or 0):
        doc.set(CERTIFICATE_FIELD, "")
        doc.set(PRIVATE_KEY_FIELD, None)
        doc.save()
        return {"configured": False}

    certificate = (certificate or doc.get(CERTIFICATE_FIELD) or "").strip()
    private_key = (private_key or doc.get_password(PRIVATE_KEY_FIELD, raise_exception=False) or "").strip()
    if not certificate or not private_key:
        frappe.throw(_("Upload both a QZ digital certificate and its matching private key."))
    _validate_pair(certificate, private_key)
    doc.set(CERTIFICATE_FIELD, certificate)
    doc.set(PRIVATE_KEY_FIELD, private_key)
    doc.save()
    return {"configured": True}


@frappe.whitelist(methods=["POST"])
def sign_request(request: str):
    """Sign a QZ request on the server using the encrypted configured key."""
    if frappe.session.user == "Guest":
        frappe.throw(_("Sign in to print through QZ Tray."), frappe.PermissionError)
    if not frappe.has_permission("POS Invoice", "read") and not frappe.has_permission("Sales Invoice", "read"):
        frappe.throw(_("You are not permitted to print sales receipts."), frappe.PermissionError)
    request = request or ""
    if not isinstance(request, str) or not request or len(request) > 131072:
        frappe.throw(_("The QZ print request is invalid."))
    doc = _settings()
    private_key = doc.get_password(PRIVATE_KEY_FIELD, raise_exception=False)
    if not private_key or not doc.get(CERTIFICATE_FIELD):
        frappe.throw(_("Configure QZ signing credentials in Settings before silent printing."))
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        key = serialization.load_pem_private_key(private_key.encode("utf-8"), password=None)
        signature = key.sign(request.encode("utf-8"), padding.PKCS1v15(), hashes.SHA512())
    except Exception:
        frappe.throw(_("The QZ signing key could not sign this print request."))
    return base64.b64encode(signature).decode("ascii")


@frappe.whitelist(methods=["POST"])
def receipt_data(invoice: str, reprint=0):
    """Build the existing authorized ESC/POS receipt for the local QZ client."""
    from esafepos.api import permissions
    from esafepos.api.sales import get_receipt
    from esafepos.api.printing import build_receipt_bytes, _log_reprint

    if int(reprint or 0):
        if not permissions.can_reprint():
            frappe.throw(_("You are not allowed to reprint a receipt."), frappe.PermissionError)
        _log_reprint(invoice, _("{0} printed again through QZ Tray"))
    receipt = get_receipt(invoice)
    data = build_receipt_bytes(receipt, open_drawer=0)
    return {"data": base64.b64encode(data).decode("ascii")}
