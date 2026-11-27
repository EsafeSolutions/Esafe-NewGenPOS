"""Operational B2B envelope; financial posting stays in ERPNext."""
from frappe.model.document import Document
from esafepos.b2b_setup import validate_envelope


class EsafePOSCustomerCheque(Document):
    def validate(self):
        validate_envelope(self)

