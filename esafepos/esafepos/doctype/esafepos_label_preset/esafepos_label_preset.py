from frappe.model.document import Document


class EsafePOSLabelPreset(Document):
    def validate(self):
        import frappe
        from esafepos.label_config import validate_configuration
        from esafepos.api import permissions

        if not permissions.is_manager():
            frappe.throw("Only a manager can save shared label presets.", frappe.PermissionError)
        permissions.assert_outlet(self.pos_profile)
        if frappe.db.get_value("POS Profile", self.pos_profile, "company") != self.company:
            frappe.throw("The label preset company does not match the outlet.")
        try:
            validate_configuration(self.configuration)
        except (ValueError, TypeError) as exc:
            frappe.throw(str(exc))
