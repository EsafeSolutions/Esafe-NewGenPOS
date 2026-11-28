"""HR configuration/approval envelope; native Frappe HR owns payroll."""
from frappe.model.document import Document
from esafepos.hr_setup import validate_record, prevent_delete


class EsafePOSHRPayrollBatch(Document):
    def validate(self):
        validate_record(self)

    def on_trash(self):
        prevent_delete(self)
