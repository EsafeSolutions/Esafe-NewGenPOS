"""Company-scoped auto enrollment for existing and future POS customers.

ERPNext's auto opt-in is resolved at checkout, without rewriting the global
Customer.loyalty_program link or moving anyone's existing points.
"""
import frappe
from frappe.utils import getdate, nowdate


def default_program(company):
    programs = frappe.get_all("Loyalty Program", filters={"company": company, "auto_opt_in": 1},
                              fields=["name", "from_date", "to_date", "customer_group", "customer_territory", "conversion_factor"],
                              order_by="creation asc")
    today = getdate(nowdate())
    programs = [p for p in programs if not p.customer_group and not p.customer_territory
                and (not p.from_date or getdate(p.from_date) <= today)
                and (not p.to_date or getdate(p.to_date) >= today)]
    programs.sort(key=lambda p: p.conversion_factor != 1)
    return programs[0].name if programs else None


def program_for_customer(customer, company):
    explicit = frappe.db.get_value("Customer", customer, "loyalty_program")
    if explicit:
        owner = frappe.db.get_value("Loyalty Program", explicit, "company")
        return explicit if owner in (None, "", company) else None
    return default_program(company)


def ensure_setup():
    """Provision a general program once per company; preserve admin edits later."""
    companies = sorted(set(frappe.get_all("POS Profile", filters={"disabled": 0}, pluck="company")) - {None, ""})
    for company in companies:
        flag = "esafepos_default_loyalty_" + company
        if frappe.db.get_default(flag):
            continue
        frappe.db.savepoint("esafepos_default_loyalty")
        try:
            program = default_program(company)
            needs_one_to_one = frappe.get_cached_value("Company", company, "default_currency") == "LKR"
            if program and needs_one_to_one and frappe.db.get_value("Loyalty Program", program, "conversion_factor") != 1:
                program = None
            if not program:
                # Reuse an active unrestricted 1:1 program, even when its old
                # configuration required staff to enroll customers individually.
                available = frappe.get_all("Loyalty Program", filters={"company": company, "conversion_factor": 1},
                    fields=["name", "from_date", "to_date", "customer_group", "customer_territory"], order_by="creation asc")
                today = getdate(nowdate())
                available = [p for p in available if not p.customer_group and not p.customer_territory
                    and (not p.from_date or getdate(p.from_date) <= today) and (not p.to_date or getdate(p.to_date) >= today)]
                if available:
                    program = available[0].name
                    frappe.db.set_value("Loyalty Program", program, "auto_opt_in", 1)
            if not program:
                from esafepos.api.settings import _loyalty_expense_account
                center = frappe.get_cached_value("Company", company, "cost_center")
                if not center:
                    center = frappe.db.get_value("Cost Center", {"company": company, "is_group": 0}, "name")
                if not center:
                    raise ValueError("Set a cost center for {0} to enable default loyalty.".format(company))
                frappe.get_doc({
                    "doctype": "Loyalty Program", "loyalty_program_name": "EsafePOS Rewards - " + company,
                    "loyalty_program_type": "Single Tier Program", "company": company, "auto_opt_in": 1,
                    "conversion_factor": 1, "expiry_duration": 365,
                    "from_date": nowdate(), "expense_account": _loyalty_expense_account(company), "cost_center": center,
                    # Saving change is explicitly funded; regular purchase rewards
                    # use a conservative starter rate, adjustable in ERPNext.
                    "collection_rules": [{"tier_name": "Standard", "collection_factor": 100, "min_spent": 0}],
                }).insert(ignore_permissions=True)
            if frappe.get_meta("Accounts Settings").has_field("enable_loyalty_point_program"):
                settings = frappe.get_single("Accounts Settings")
                settings.enable_loyalty_point_program = 1
                settings.save(ignore_permissions=True)
            frappe.db.set_default(flag, "1")
        except Exception:
            frappe.db.rollback(save_point="esafepos_default_loyalty")
            frappe.log_error(title="EsafePOS: default loyalty setup", message=frappe.get_traceback())
