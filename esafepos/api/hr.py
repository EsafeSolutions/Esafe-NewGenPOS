"""Online HR entry points and approved monthly payroll hand-off to Frappe HR.

The EsafePOS record holds commission approval snapshots, never a salary/payment
ledger. Daily salary uses the native Salary Slip controller and payroll rules.
"""
import hashlib
import json
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate, now

from esafepos import features
from esafepos.api import permissions
from esafepos.hr_payroll import monthly_period, commission_earnings, number

BATCH = "EsafePOS HR Payroll Batch"
HR_ROLES = {"HR Manager", "HR User"}
PAYROLL_ROLES = {"Payroll Manager", "Payroll User"}


def _roles(user=None):
    user = user or frappe.session.user
    return {"HR Manager", "Payroll Manager"} if user == "Administrator" else set(frappe.get_roles(user))


def can_payroll(user=None):
    return bool(_roles(user) & PAYROLL_ROLES)


def can_approve(user=None):
    return "Payroll Manager" in _roles(user)


def can_access():
    return bool(features.enabled("enable_hr_integration") and (
        _roles() & (HR_ROLES | PAYROLL_ROLES) or
        frappe.db.exists("Employee", {"user_id": frappe.session.user, "status": "Active"})))


def _require(kind, ptype="read"):
    if not frappe.has_permission(kind, ptype):
        frappe.throw(_("You are not permitted to {0} {1}.").format(ptype, kind), frappe.PermissionError)


def _guard(company, feature="enable_hr_integration", payroll=False, approve=False):
    if not features.enabled(feature) or not features.enabled("enable_hr_integration"):
        frappe.throw(_("This HR feature is turned off in Modules & Features."), frappe.PermissionError)
    if frappe.session.user == "Guest" or not can_access():
        frappe.throw(_("Your account does not have HR access."), frappe.PermissionError)
    if not frappe.db.exists("DocType", BATCH):
        frappe.throw(_("Run bench migrate before using the HR workspace."))
    if (payroll and not can_payroll()) or (approve and not can_approve()):
        frappe.throw(_("A payroll role is required for this action."), frappe.PermissionError)
    if not company:
        frappe.throw(_("Select a company."))
    allowed = permissions.allowed_companies()
    if allowed is not None and company not in allowed:
        frappe.throw(_("You cannot access this company."), frappe.PermissionError)
    frappe.get_doc("Company", company).check_permission("read")
    return frappe.get_cached_value("Company", company, "default_currency")


def _employee(company, employee, manager=False):
    doc = frappe.get_doc("Employee", employee)
    doc.check_permission("read")
    if doc.company != company:
        frappe.throw(_("The employee belongs to a different company."), frappe.PermissionError)
    if manager and "HR Manager" not in _roles():
        frappe.throw(_("An HR role is required to change attendance."), frappe.PermissionError)
    if not _roles() & (HR_ROLES | PAYROLL_ROLES) and doc.user_id != frappe.session.user:
        frappe.throw(_("You can only access your own employee records."), frappe.PermissionError)
    return doc


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def _lock(company):
    # Serializes native draft creation and commission periods across tills.
    frappe.db.sql("select name from `tabCompany` where name=%s for update", (company,))


def _save(doc):
    doc.flags.hr_operation = True
    return doc.save(ignore_permissions=True) if not doc.is_new() else doc.insert(ignore_permissions=True)


def _all(kind, filters, fields):
    """Fail on hidden records or oversized periods instead of underpaying staff."""
    _require(kind)
    rows = frappe.get_all(kind, filters=filters, fields=fields, limit_page_length=5001, order_by="name asc")
    if len(rows) > 5000:
        frappe.throw(_("This period has too many records. Review it in Frappe HR."))
    for row in rows:
        frappe.get_doc(kind, row.name).check_permission("read")
    return rows


def _component(name, company):
    if not name:
        frappe.throw(_("Configure a payroll earning component first."))
    doc = frappe.get_doc("Salary Component", name)
    doc.check_permission("read")
    if doc.type != "Earning" or doc.get("disabled") or doc.get("depends_on_payment_days"):
        frappe.throw(_("Select an enabled earning component that does not depend on payment days."))
    if doc.get("is_payable") == 0 or doc.get("is_flexible_benefit") or doc.get("statistical_component"):
        frappe.throw(_("Select a payable, non-statistical earning component without flexible benefits."))
    if not any(row.company == company and (row.get("account") or row.get("default_account")) for row in doc.get("accounts") or []):
        frappe.throw(_("Map the salary component account for this company in Frappe HR."))
    return doc


@frappe.whitelist()
def get_context(company):
    currency = _guard(company)
    people_filters = {"company": company, "status": "Active"}
    if not _roles() & (HR_ROLES | PAYROLL_ROLES):
        people_filters["user_id"] = frappe.session.user
    people = frappe.get_list("Employee", filters=people_filters, fields=["name", "employee_name", "department"],
                             limit_page_length=1001, order_by="employee_name asc")
    if len(people) > 1000:
        frappe.throw(_("Use Frappe HR to manage more than 1,000 employees."))
    kinds = ("Attendance", "Expense Claim", "Additional Salary", "Salary Slip")
    available = {kind: {p: bool(frappe.has_permission(kind, p)) for p in ("read", "create", "submit")} for kind in kinds}
    installed = {}
    for app in ("frappe", "erpnext", "hrms"):
        try:
            installed[app] = getattr(frappe.get_module(app), "__version__", "unknown")
        except (ImportError, AttributeError):
            installed[app] = "unknown"
    payroll_settings = {}
    if can_payroll() and frappe.has_permission("Payroll Settings", "read"):
        settings = frappe.get_cached_doc("Payroll Settings")
        payroll_settings = {key: settings.get(key) for key in ("payroll_based_on", "daily_wages_fraction_for_half_day",
                            "include_holidays_in_total_working_days", "consider_unmarked_attendance_as")
                            if settings.meta.has_field(key)}
    return {"company": company, "currency": currency, "today": nowdate(), "versions": installed,
            "features": features.client_facts(), "employees": people, "permissions": available,
            "can_attendance": bool("HR Manager" in _roles() and available["Attendance"]["create"] and available["Attendance"]["submit"]),
            "can_payroll": can_payroll(), "can_approve": can_approve(), "payroll_settings": payroll_settings,
            "components": frappe.get_list("Salary Component", filters={"type": "Earning"}, pluck="name", limit_page_length=500)
                          if can_payroll() and features.enabled("enable_commission_payroll") and frappe.has_permission("Salary Component", "read") else [],
            "expense_types": frappe.get_list("Expense Claim Type", pluck="name", limit_page_length=500)
                             if features.enabled("enable_expense_claims") and available["Expense Claim"]["create"] else [],
            "schema_ready": all(frappe.get_meta(kind).has_field(field) for kind in ("Attendance", "Expense Claim", "Salary Slip")
                                for field in ("esafepos_hr_request", "esafepos_hr_hash")),
            "refreshed_at": now()}


def _request_key(company, employee, key):
    if not re.match(r"^[A-Za-z0-9-]{16,80}$", key or ""):
        frappe.throw(_("A valid request identity is required. Refresh and try again."))
    return _hash([frappe.session.user, company, employee, key])


def _existing(kind, identity, fingerprint):
    if not all(frappe.get_meta(kind).has_field(field) for field in ("esafepos_hr_request", "esafepos_hr_hash")):
        frappe.throw(_("Run bench migrate before recording HR actions."))
    name = frappe.db.get_value(kind, {"esafepos_hr_request": identity}, "name")
    if name:
        doc = frappe.get_doc(kind, name)
        doc.check_permission("read")
        if doc.get("esafepos_hr_hash") != fingerprint:
            frappe.throw(_("This request identity was already used for different details. Refresh and review the existing record."))
        return doc


@frappe.whitelist()
def list_attendance(company, employee, month):
    _guard(company, "enable_attendance")
    _employee(company, employee)
    start, end = monthly_period(month)
    return frappe.get_list("Attendance", filters={"company": company, "employee": employee,
                           "attendance_date": ["between", [start, end]]}, fields=["name", "attendance_date", "status", "docstatus"],
                           limit_page_length=100, order_by="attendance_date desc")


@frappe.whitelist()
def mark_attendance(company, employee, attendance_date, status, reason, request_id):
    _guard(company, "enable_attendance")
    person = _employee(company, employee, manager=True)
    _require("Attendance", "create")
    _require("Attendance", "submit")
    day = getdate(attendance_date)
    if status not in ("Present", "Absent", "Half Day", "Work From Home") or day > getdate(nowdate()) or not str(reason or "").strip():
        frappe.throw(_("Choose a valid attendance status, a date through today and a reason. Record leave through Frappe HR."))
    if person.status != "Active":
        frappe.throw(_("Attendance can only be recorded for an active employee."))
    _lock(company)
    identity = _request_key(company, employee, request_id)
    fingerprint = _hash([company, employee, str(day), status, str(reason).strip()])
    doc = _existing("Attendance", identity, fingerprint)
    if doc:
        if doc.docstatus != 1:
            frappe.throw(_("This request was already used. Refresh attendance before retrying."))
        return {"name": doc.name}
    if frappe.db.exists("Attendance", {"employee": employee, "attendance_date": day, "docstatus": ["!=", 2]}):
        frappe.throw(_("Attendance already exists for this date. Review or amend it in Frappe HR."))
    doc = frappe.get_doc({"doctype": "Attendance", "employee": employee, "company": company,
                          "attendance_date": day, "status": status, "esafepos_hr_request": identity, "esafepos_hr_hash": fingerprint})
    doc.insert()
    doc.add_comment("Comment", text=_("POS attendance exception: {0}").format(frappe.utils.escape_html(reason)))
    doc.submit()
    return {"name": doc.name}


@frappe.whitelist()
def list_claims(company, employee):
    _guard(company, "enable_expense_claims")
    _employee(company, employee)
    return frappe.get_list("Expense Claim", filters={"company": company, "employee": employee},
                           fields=["name", "posting_date", "status", "approval_status", "total_claimed_amount",
                                   "total_sanctioned_amount", "total_amount_reimbursed", "docstatus"],
                           limit_page_length=100, order_by="posting_date desc, creation desc")


@frappe.whitelist()
def create_claim(company, employee, expense_date, expense_type, amount, description, request_id):
    _guard(company, "enable_expense_claims")
    _employee(company, employee)
    _require("Expense Claim", "create")
    if number(amount) <= 0 or getdate(expense_date) > getdate(nowdate()) or not str(description or "").strip():
        frappe.throw(_("Enter a positive amount, expense date through today and description."))
    frappe.get_doc("Expense Claim Type", expense_type).check_permission("read")
    _lock(company)
    fingerprint = _hash([company, employee, str(getdate(expense_date)), expense_type, str(number(amount)), description])
    doc = _existing("Expense Claim", _request_key(company, employee, request_id), fingerprint)
    if doc:
        return {"name": doc.name, "docstatus": doc.docstatus}
    doc = frappe.get_doc({"doctype": "Expense Claim", "company": company, "employee": employee, "posting_date": nowdate(),
                          "esafepos_hr_request": _request_key(company, employee, request_id),
                          "esafepos_hr_hash": fingerprint,
                          "expenses": [{"expense_date": expense_date, "expense_type": expense_type,
                                        "amount": flt(amount), "description": description}]})
    doc.insert()
    return {"name": doc.name, "docstatus": doc.docstatus}


def _precision(currency):
    units = cint(frappe.get_cached_value("Currency", currency, "fraction_units")) or 100
    return min(6, max(0, len(str(units)) - 1))


def _salary_data(doc):
    data = {key: doc.get(key) for key in ("name", "employee", "employee_name", "company", "currency", "salary_structure",
            "start_date", "end_date", "docstatus", "total_working_days", "payment_days", "absent_days", "leave_without_pay",
            "gross_pay", "total_deduction", "net_pay", "rounded_total")}
    for table in ("earnings", "deductions"):
        data[table] = [{"salary_component": row.salary_component, "amount": row.amount} for row in doc.get(table) or []]
    return data


def _new_salary_slip(company, employee, month):
    _guard(company, "enable_day_salary", payroll=True)
    _employee(company, employee)
    _require("Salary Slip", "read")
    _require("Salary Slip", "create")
    start, end = monthly_period(month)
    if end >= getdate(nowdate()):
        frappe.throw(_("Prepare salary after the month has ended."))
    doc = frappe.new_doc("Salary Slip")
    doc.update({"company": company, "employee": employee, "start_date": start, "end_date": end,
                "posting_date": end, "payroll_frequency": "Monthly"})
    doc.check_permission("create")
    if not callable(getattr(doc, "get_emp_and_working_day_details", None)):
        frappe.throw(_("This HRMS version does not provide the native Salary Slip calculator. Use Frappe HR."))
    # Native validation loads Salary Structure/Assignment and applies Payroll
    # Settings, holidays, attendance/leave, component formulas and deductions.
    # Never calculate a second day rate or payment-day count in EsafePOS.
    doc.run_method("validate")
    if not doc.salary_structure:
        frappe.throw(_("Configure a submitted Salary Structure Assignment in Frappe HR first."))
    if getdate(doc.start_date) != start or getdate(doc.end_date) != end:
        frappe.throw(_("The native payroll period differs from this month. Continue in Frappe HR."))
    return doc


def _salary_fingerprint(doc):
    data = _salary_data(doc)
    data.pop("name", None)
    return _hash(data)


@frappe.whitelist()
def preview_salary(company, employee, month):
    # Native loan/payroll hooks may write derived records while calculating.
    # Roll back the entire simulation, including on validation failure.
    frappe.db.savepoint("esafepos_hr_salary_preview")
    try:
        doc = _new_salary_slip(company, employee, month)
        return dict(_salary_data(doc), fingerprint=_salary_fingerprint(doc))
    finally:
        frappe.db.rollback(save_point="esafepos_hr_salary_preview")


@frappe.whitelist()
def list_salary_slips(company, employee, month):
    _guard(company, "enable_day_salary", payroll=True)
    _employee(company, employee)
    start, end = monthly_period(month)
    return frappe.get_list("Salary Slip", filters={"company": company, "employee": employee,
                           "start_date": ["<=", end], "end_date": [">=", start]},
                           fields=["name", "start_date", "end_date", "docstatus", "currency", "net_pay"],
                           limit_page_length=100, order_by="creation desc")


@frappe.whitelist()
def save_salary_draft(company, employee, month, fingerprint, request_id):
    _guard(company, "enable_day_salary", payroll=True)
    _employee(company, employee)
    _require("Salary Slip", "create")
    _lock(company)
    start, end = monthly_period(month)
    identity = _request_key(company, employee, request_id)
    request_hash = _hash([company, employee, month])
    existing = _existing("Salary Slip", identity, request_hash)
    if existing:
        return _salary_data(existing)
    if frappe.db.exists("Salary Slip", {"company": company, "employee": employee, "docstatus": ["!=", 2],
                        "start_date": ["<=", end], "end_date": [">=", start]}):
        frappe.throw(_("A Salary Slip already overlaps this month. Review the existing slip in Frappe HR."))
    doc = _new_salary_slip(company, employee, month)
    if _salary_fingerprint(doc) != fingerprint:
        frappe.throw(_("Native salary calculation changed. Refresh the preview before saving."))
    doc.esafepos_hr_request = identity
    doc.esafepos_hr_hash = request_hash
    doc.insert()
    # HR workflow approval, submission, GL and payment remain native actions.
    return _salary_data(doc)


def _assert_commission_period(company, month, source_hash):
    # A salesperson/Employee reassignment after posting must not make the same
    # source sales payable again under another employee's otherwise unique key.
    # Freeze the company/month's source set at first approval; later invoice,
    # return or mapping changes require reopening approvals/native adjustments.
    rows = frappe.get_all(BATCH, filters={"company": company, "month": month, "status": ["in", ["Approved", "Posted"]]},
                          fields=["snapshot"], limit_page_length=0)
    for row in rows:
        saved = json.loads(row.snapshot or "{}")
        if saved.get("period_source_hash") != source_hash:
            frappe.throw(_("Commission sources changed after this company/month was approved. Reopen unposted approvals or review posted earnings and adjustments in Frappe HR."))


def _calculate(company, employee, month, kind, component=None):
    currency = _guard(company, "enable_commission_payroll", payroll=True)
    person = _employee(company, employee)
    start, end = monthly_period(month)
    if end >= getdate(nowdate()):
        frappe.throw(_("Prepare payroll after the month has ended."))
    earning_component = _component(component, company)
    assignments = _all("Salary Structure Assignment", {"employee": employee, "company": company, "docstatus": 1,
                       "from_date": ["<=", end]}, ["name", "from_date", "currency", "salary_structure", "modified"])
    if not assignments:
        frappe.throw(_("Configure a submitted Salary Structure Assignment for this employee first."))
    assignment = max(assignments, key=lambda row: getdate(row.from_date))
    if assignment.currency != currency:
        frappe.throw(_("Commission hand-off requires salary and company currencies to match. Use native HR payroll for currency conversion."))
    structure = frappe.get_doc("Salary Structure", assignment.salary_structure)
    structure.check_permission("read")
    for row in structure.get("earnings") or []:
        if row.salary_component == component and (flt(row.amount) or row.get("formula") or row.get("amount_based_on_formula")):
            frappe.throw(_("The selected earning component already pays through the Salary Structure. Use a dedicated commission component."))
    invoices = []
    if not frappe.get_meta("Sales Invoice").has_field("is_consolidated"):
        frappe.throw(_("This ERPNext version cannot safely distinguish consolidated invoices. Review commissions in ERPNext."))
    for doctype in ("POS Invoice", "Sales Invoice"):
        filters = {"company": company, "docstatus": 1, "posting_date": ["between", [start, end]]}
        if doctype == "Sales Invoice":
            filters["is_consolidated"] = 0
        for row in _all(doctype, filters, ["name"]):
            inv = frappe.get_doc(doctype, row.name)
            invoices.append({"doctype": doctype, "name": inv.name, "docstatus": inv.docstatus, "is_return": inv.is_return,
                             "is_consolidated": inv.get("is_consolidated"), "modified": str(inv.modified),
                             "base_net_total": inv.base_net_total, "sales_team": [r.as_dict() for r in inv.sales_team]})
    people = {}
    for name in {r["sales_person"] for inv in invoices for r in inv["sales_team"]}:
        sales_person = frappe.get_doc("Sales Person", name)
        sales_person.check_permission("read")
        target = sales_person.get("employee")
        if target:
            _employee(company, target)
        people[name] = target
    result = commission_earnings(invoices, people, _precision(currency)).get(employee, {"amount": 0, "sources": []})
    period_source_hash = _hash({"invoices": invoices, "employee_links": people})
    _assert_commission_period(company, month, period_source_hash)
    result["warning"] = "ERPNext's stored Sales Team incentives on submitted company invoices, net of returns; consolidated invoices excluded. Negative totals require a reviewed native payroll adjustment."
    result.update({"company": company, "employee": employee, "employee_name": person.employee_name, "month": month,
                   "kind": "Commission", "currency": currency, "component": component, "start": str(start), "end": str(end),
                   "assignment": assignment.name, "assignment_modified": str(assignment.modified),
                   "component_modified": str(earning_component.modified), "structure_modified": str(structure.modified),
                   "period_source_hash": period_source_hash})
    result["fingerprint"] = _hash(result)
    return result


def _kind(kind):
    if kind != "Commission":
        frappe.throw(_("Select Commission."))
    return "enable_commission_payroll"


@frappe.whitelist()
def preview_payroll(company, employee, month, kind="Commission", component=None):
    _kind(kind)
    return _calculate(company, employee, month, kind, component)


def _batch_data(doc):
    return {key: str(doc.get(key) or "") if key in ("month", "modified") else doc.get(key)
            for key in ("name", "company", "employee", "month", "kind", "amount", "currency", "status", "approved_by", "additional_salary", "modified")}


@frappe.whitelist()
def prepare_payroll(company, employee, month, kind, fingerprint, component=None):
    _guard(company, _kind(kind), payroll=True)
    _lock(company)
    start, end = monthly_period(month)
    month = start.strftime("%Y-%m")
    key = _hash([company, employee, month, kind])
    existing = frappe.db.get_value(BATCH, {"period_key": key}, "name")
    if existing:
        doc = frappe.get_doc(BATCH, existing)
        doc.check_permission("read")
        if doc.status != "Draft":
            return _batch_data(doc)
    else:
        doc = frappe.get_doc({"doctype": BATCH, "company": company, "employee": employee, "month": month,
                              "kind": kind, "period_key": key, "status": "Draft"})
    result = _calculate(company, employee, month, kind, component)
    if result["fingerprint"] != fingerprint:
        frappe.throw(_("Payroll inputs changed. Refresh the preview before saving."))
    if number(result["amount"]) <= 0:
        frappe.throw(_("Only positive earnings can be handed to payroll. Review zero or negative adjustments in Frappe HR."))
    doc.update({"amount": result["amount"], "currency": result["currency"], "snapshot": json.dumps(result, default=str),
                "fingerprint": fingerprint, "salary_component": result["component"], "prepared_by": frappe.session.user})
    _save(doc)
    return _batch_data(doc)


@frappe.whitelist()
def list_payroll(company, employee, month):
    _guard(company, payroll=True)
    _employee(company, employee)
    start, end = monthly_period(month)
    rows = frappe.get_list(BATCH, filters={"company": company, "employee": employee, "month": start.strftime("%Y-%m")},
                           fields=["name"], limit_page_length=10)
    return [_batch_data(frappe.get_doc(BATCH, row.name)) for row in rows
            if features.enabled(_kind(frappe.get_doc(BATCH, row.name).kind))]


def _locked_batch(company, name):
    _guard(company, payroll=True, approve=True)
    _lock(company)
    doc = frappe.get_doc(BATCH, name)
    doc.check_permission("read")
    if doc.company != company:
        frappe.throw(_("This payroll period belongs to a different company."), frappe.PermissionError)
    _guard(company, _kind(doc.kind), payroll=True, approve=True)
    _employee(company, doc.employee)
    return doc


def _fresh(doc):
    current = _calculate(doc.company, doc.employee, doc.month, doc.kind, doc.salary_component)
    if current["fingerprint"] != doc.fingerprint:
        frappe.throw(_("Payroll inputs changed after preparation. Refresh and prepare this period again before approval/posting."))
    return current


@frappe.whitelist()
def approve_payroll(company, name):
    doc = _locked_batch(company, name)
    _require("Additional Salary", "submit")
    if doc.status != "Draft":
        return _batch_data(doc)
    _fresh(doc)
    doc.update({"status": "Approved", "approved_by": frappe.session.user, "approved_at": now()})
    _save(doc)
    return _batch_data(doc)


@frappe.whitelist()
def reopen_payroll(company, name):
    doc = _locked_batch(company, name)
    if doc.status == "Posted":
        frappe.throw(_("Posted periods stay locked. Use native HR cancellation/adjustment procedures."))
    doc.update({"status": "Draft", "approved_by": None, "approved_at": None})
    _save(doc)
    return _batch_data(doc)


@frappe.whitelist()
def post_payroll(company, name):
    doc = _locked_batch(company, name)
    _require("Additional Salary", "create")
    _require("Additional Salary", "submit")
    if doc.status == "Posted":
        return _batch_data(doc)
    if doc.status != "Approved":
        frappe.throw(_("Approve this period before posting it to payroll."))
    result = _fresh(doc)
    end = getdate(result["end"])
    if frappe.db.exists("Salary Slip", {"employee": doc.employee, "company": company, "docstatus": ["!=", 2],
                        "start_date": ["<=", end], "end_date": [">=", getdate(result["start"])]}):
        frappe.throw(_("A Salary Slip already covers this period. Resolve it in Frappe HR before adding earnings."))
    earning = frappe.get_doc({"doctype": "Additional Salary", "company": company, "employee": doc.employee,
                              "salary_component": result["component"], "currency": doc.currency, "amount": doc.amount,
                              "payroll_date": end, "is_recurring": 0, "overwrite_salary_structure_amount": 0,
                              "ref_doctype": BATCH, "ref_docname": doc.name})
    earning.insert()
    earning.submit()
    doc.update({"status": "Posted", "additional_salary": earning.name, "posted_by": frappe.session.user, "posted_at": now()})
    _save(doc)
    return _batch_data(doc)
