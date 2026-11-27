# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "ESAFEPOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
"""Independent Modules & Features switches (0.70.0)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint


FIELDS = (
    "enable_buying",
    "enable_regular_invoices",
    "enable_customer_balances",
    "enable_customer_payments",
    "enable_cheque_tracking",
    "enable_quotations",
    "enable_sales_orders",
    "enable_delivery_notes",
    "enable_hr_integration",
    "enable_attendance",
    "enable_expense_claims",
    "enable_day_salary",
    "enable_sales_commissions",
    "enable_commission_payroll",
    "enable_sales_rep_mode",
    "enable_erp_pricing_rules",
    "enable_customer_sales_progress",
)

# Existing workflows stay available by default. New HR and order workflows are
# opt-in until their site configuration and policy are complete.
DEFAULTS = {
    "enable_buying": 1,
    "enable_regular_invoices": 1,
    "enable_customer_balances": 1,
    "enable_customer_payments": 1,
    "enable_cheque_tracking": 0,
    "enable_quotations": 1,
    "enable_sales_orders": 0,
    "enable_delivery_notes": 0,
    "enable_hr_integration": 0,
    "enable_attendance": 0,
    "enable_expense_claims": 0,
    "enable_day_salary": 0,
    "enable_sales_commissions": 1,
    "enable_commission_payroll": 0,
    "enable_sales_rep_mode": 0,
    "enable_erp_pricing_rules": 0,
    "enable_customer_sales_progress": 0,
}

# These controls are staged until their workflows are connected. Keeping them
# visible makes the roadmap and dependencies clear without advertising a toggle
# that currently has no operational effect.
PENDING = {
    "enable_hr_integration",
    "enable_attendance",
    "enable_expense_claims",
    "enable_day_salary",
    "enable_commission_payroll",
}


DEPENDENCIES = {
    "enable_customer_payments": ("enable_customer_balances",),
    "enable_cheque_tracking": ("enable_customer_payments",),
    "enable_attendance": ("enable_hr_integration",),
    "enable_expense_claims": ("enable_hr_integration",),
    "enable_day_salary": ("enable_hr_integration", "enable_attendance"),
    "enable_commission_payroll": ("enable_hr_integration", "enable_sales_commissions"),
    "enable_erp_pricing_rules": ("enable_sales_rep_mode",),
    "enable_customer_sales_progress": ("enable_sales_rep_mode",),
}


def hrms_installed():
    try:
        return "hrms" in frappe.get_installed_apps()
    except Exception:
        return False


def configured(field, doc=None):
    if field not in DEFAULTS:
        return False
    try:
        if doc is None:
            doc = frappe.get_cached_doc("EsafePOS Settings")
        value = doc.get(field)
    except Exception:
        value = None
    return bool(cint(DEFAULTS[field] if value is None else value))


def enabled(field, doc=None):
    """True only when the feature and its required parent switches are on."""
    if field not in DEFAULTS or field in PENDING or not configured(field, doc):
        return False
    if field == "enable_hr_integration" and not hrms_installed():
        return False
    return all(enabled(parent, doc) for parent in DEPENDENCIES.get(field, ()))


def client_facts(doc=None):
    if doc is None:
        doc = frappe.get_cached_doc("EsafePOS Settings")
    return {
        **{field: 1 if enabled(field, doc) else 0 for field in FIELDS},
        "hrms_installed": 1 if hrms_installed() else 0,
    }


def save(doc, payload):
    """Save independent switches without letting an old client turn new ones off."""
    for field in FIELDS:
        if field in payload:
            if field in PENDING and cint(payload.get(field)):
                frappe.throw(
                    _("{0} is not available in this release yet.").format(field.replace("enable_", "").replace("_", " ").title()),
                    title=_("Modules & Features"),
                )
            doc.set(field, 1 if cint(payload.get(field)) else 0)

    if cint(doc.get("credit_sales_enabled")) and not configured("enable_customer_balances", doc):
        frappe.throw(
            _("Turn off Sales on account before disabling customer balances."),
            title=_("Modules & Features"),
        )

    if configured("enable_hr_integration", doc) and not hrms_installed():
        frappe.throw(
            _("Install Frappe HR before enabling HR integration."),
            title=_("Modules & Features"),
        )

    for field, parents in DEPENDENCIES.items():
        if configured(field, doc):
            missing = [parent for parent in parents if not configured(parent, doc)]
            if field == "enable_commission_payroll" and not hrms_installed():
                missing.append("Frappe HR")
            if missing:
                labels = ", ".join(missing)
                frappe.throw(
                    _("Enable {0} before enabling {1}.").format(labels, field.replace("enable_", "").replace("_", " ")),
                    title=_("Modules & Features"),
                )
