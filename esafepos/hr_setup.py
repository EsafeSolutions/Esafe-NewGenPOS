"""Optional HR schema and scoped permissions; safe on sites without HRMS."""
import frappe


def setup():
    from esafepos.features import hrms_installed
    if not hrms_installed():
        return
    # Older HRMS releases use HR User for native payroll permissions. These
    # approval roles add POS separation; native permissions are still required.
    for role in ("Payroll User", "Payroll Manager"):
        if not frappe.db.exists("Role", role):
            frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    additions = {}
    for kind in ("Attendance", "Expense Claim", "Salary Slip"):
        additions[kind] = []
        if not frappe.get_meta(kind).has_field("esafepos_hr_request"):
            additions[kind].append(dict(fieldname="esafepos_hr_request", label="POS HR Request", fieldtype="Data",
                                        unique=1, hidden=1, read_only=1, no_copy=1))
        if not frappe.get_meta(kind).has_field("esafepos_hr_hash"):
            additions[kind].append(dict(fieldname="esafepos_hr_hash", label="POS HR Request Hash", fieldtype="Data",
                                        hidden=1, read_only=1, no_copy=1))
    create_custom_fields(additions, update=True)


def validate_record(doc):
    if not doc.flags.get("hr_operation"):
        frappe.throw("Use the HR workspace to change this record.", frappe.PermissionError)


def prevent_delete(doc):
    frappe.throw("Commission payroll periods retain their audit history and cannot be deleted.", frappe.PermissionError)


def has_permission(doc, user=None, permission_type=None, **kwargs):
    from esafepos.api.hr import can_payroll
    from esafepos.features import enabled
    from esafepos.api.permissions import allowed_companies
    allowed = allowed_companies(user)
    return bool(permission_type in (None, "read", "print") and enabled("enable_hr_integration")
                and can_payroll(user) and enabled("enable_commission_payroll")
                and frappe.has_permission("Employee", "read", doc=doc.employee, user=user)
                and (allowed is None or doc.company in allowed)
                and frappe.has_permission("Company", "read", doc=doc.company, user=user))


def query_conditions(user=None):
    from esafepos.api.hr import can_payroll
    from esafepos.api.permissions import allowed_companies
    from esafepos.features import enabled
    if not enabled("enable_hr_integration") or not can_payroll(user):
        return "1=0"
    companies = allowed_companies(user)
    employee_names = frappe.get_list("Employee", pluck="name", limit_page_length=0, user=user)
    if not employee_names:
        return "1=0"
    clauses = ["employee in ({0})".format(",".join(frappe.db.escape(e) for e in employee_names))]
    kinds = []
    if enabled("enable_commission_payroll"):
        kinds.append("Commission")
    clauses.append("kind in ({0})".format(",".join(frappe.db.escape(k) for k in kinds)) if kinds else "1=0")
    if companies is not None:
        clauses.append("company in ({0})".format(",".join(frappe.db.escape(c) for c in companies)) if companies else "1=0")
    return " and ".join(clauses)


