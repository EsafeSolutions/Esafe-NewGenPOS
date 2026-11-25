import frappe
from frappe import _
from frappe.model.document import Document


class EsafePOSDeletedSale(Document):
    def validate(self):
        if not self.is_new():
            frappe.throw(_("Sale deletion audit records cannot be changed."))

    def on_trash(self):
        frappe.throw(_("Sale deletion audit records cannot be deleted."))
