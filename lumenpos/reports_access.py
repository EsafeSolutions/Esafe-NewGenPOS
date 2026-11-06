# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "ESAFEPOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
"""The reports without a till (0.65.0).

Management reads the shop's figures but sells nothing and works no register. In
ERPNext that is a ROLE: whoever holds **LumenPOS Reports** opens LumenPOS on the
Insights reports alone, for every outlet of the companies ERPNext's User
Permissions allow them, with no POS Profile to be assigned to. Holding LumenPOS
Cashier or LumenPOS Manager as well gives them the whole till, as before, and the
reports of every outlet of their companies.

What they may see stays the shop's call: the reports of Who can do what (sales,
cashier performance, profit, sales by salesperson) pass for this role while a shop
names nobody for them, and once a shop names someone, the rows decide (name the
role there to keep it). A switch in Settings (General, Insights) takes the whole
access away. Everything here is checked on the server, by every report.
"""

from __future__ import annotations

import frappe
from frappe.utils import cint

ROLE = "LumenPOS Reports"
SWITCH = "reports_without_till"
# The till's roles: with one of them the person works the till as well.
TILL_ROLES = {"LumenPOS Cashier", "LumenPOS Manager", "System Manager"}


def enabled() -> bool:
    """On unless a shop switched it off. A site updated without its migrate has
    no such field yet: on, as it ships."""
    try:
        stored = frappe.db.sql(
            "select value from tabSingles where doctype=%s and field=%s",
            ("LumenPOS Settings", SWITCH),
        )
    except Exception:
        return True
    return bool(cint(stored[0][0])) if stored else True


def holds_role(user: str | None = None) -> bool:
    return ROLE in set(frappe.get_roles(user or frappe.session.user))


def is_viewer(user: str | None = None) -> bool:
    """Holds the role, and the shop lets the role in."""
    return holds_role(user) and enabled()


def reports_only(user: str | None = None) -> bool:
    """Opens LumenPOS on the reports alone: the role, and none of the till's."""
    user = user or frappe.session.user
    if user == "Administrator" or not is_viewer(user):
        return False
    return not (TILL_ROLES & set(frappe.get_roles(user)))


def companies(user: str | None = None) -> list:
    """The companies whose outlets a viewer reads: those ERPNext's User
    Permissions hold them to, else every company with an outlet."""
    from lumenpos.api import permissions

    allowed = permissions.allowed_companies(user)
    names = frappe.get_all("POS Profile", filters={"disabled": 0}, pluck="company")
    names = sorted({c for c in names if c})
    return [c for c in names if allowed is None or c in allowed]


def registers(user: str | None = None) -> list:
    """Every enabled register (POS Profile) of a viewer's companies, or [] for
    anyone else."""
    if not is_viewer(user):
        return []
    mine = companies(user)
    if not mine:
        return []
    return sorted(frappe.get_all("POS Profile", filters={"disabled": 0, "company": ["in", mine]}, pluck="name"))


def default_company(user: str | None = None) -> str | None:
    mine = companies(user)
    if not mine:
        return None
    preferred = frappe.defaults.get_user_default("Company", user=user or frappe.session.user)
    return preferred if preferred in mine else mine[0]
