import frappe
from frappe import _
from frappe.model.document import Document
from esafepos import user_access


class EsafePOSAccessProfile(Document):
    def validate(self):
        if not user_access.native_manager():
            frappe.throw(_("An ERPNext manager must edit POS access profiles."), frappe.PermissionError)
        seen = set()
        for row in self.capabilities or []:
            if row.capability not in user_access.CAPABILITIES or row.capability in seen:
                frappe.throw(_("Choose each valid capability only once."))
            seen.add(row.capability)
            if self.base_level == "Reports only" and row.allowed and row.capability not in user_access.REPORT_CAPABILITIES:
                frappe.throw(_("A reports-only profile cannot allow sales or cash operations."))
