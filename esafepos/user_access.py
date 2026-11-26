"""POS access presets and named custom profiles; ERPNext permissions still apply."""
import frappe

LEVELS = ("Use existing roles", "Cashier", "Supervisor", "Manager", "Reports only", "Custom")
CAPABILITIES = (
    "Edit price / discount", "Edit item selling prices", "Create items", "View warehouse stock",
    "Adjust warehouse stock", "Transfer warehouse stock", "Receive warehouse stock", "Make returns", "Return past the window", "Exchange goods", "Cash in",
    "Cash out", "Reprint a receipt", "Open the register", "Close the register", "Hold goods for a customer",
    "See sales by salesperson", "See the system check", "Sell on account", "Take customer payments",
    "Set a customer's credit", "See sales reports", "See cashier performance", "See profit", "Print labels",
    "Use the stock app",
    "Manage buying and suppliers",
    "Permanently delete sales",
)
REPORT_CAPABILITIES = {"See sales by salesperson", "See sales reports", "See cashier performance", "See profit"}
CASHIER = {"Make returns", "Exchange goods", "Cash in", "Reprint a receipt", "Open the register",
           "Close the register", "Hold goods for a customer", "Print labels"}
PRESETS = {
    "Cashier": CASHIER,
    "Supervisor": CASHIER | {"Edit price / discount", "Cash out", "Return past the window",
                             "View warehouse stock", "See sales reports", "See cashier performance",
                             "See sales by salesperson", "Take customer payments"},
    "Manager": set(CAPABILITIES),
    "Reports only": REPORT_CAPABILITIES,
}


def native_manager(user=None):
    return bool({"System Manager", "EsafePOS Manager"} & set(frappe.get_roles(user or frappe.session.user)))


def assignment(user=None):
    user = user or frappe.session.user
    if native_manager(user):
        return None
    if not getattr(frappe.db, "table_exists", lambda name: False)("EsafePOS User Access Level"):
        return None
    doc = frappe.get_cached_doc("EsafePOS Settings")
    row = next((row for row in doc.get("user_access_levels") or [] if row.user == user), None)
    if not row or row.access_level == "Use existing roles":
        return None
    level = row.access_level
    overrides = {}
    if level == "Custom":
        if not row.get("access_profile") or not frappe.db.exists("EsafePOS Access Profile", row.access_profile):
            return {"level": "Invalid", "profile": row.get("access_profile"), "capabilities": set()}
        profile = frappe.get_cached_doc("EsafePOS Access Profile", row.access_profile)
        level = profile.base_level
        overrides = {r.capability: bool(int(r.allowed or 0)) for r in profile.get("capabilities") or []}
    if level not in PRESETS:
        return {"level": "Invalid", "profile": row.get("access_profile"), "capabilities": set()}
    granted = set(PRESETS.get(level, set()))
    for capability, allow in overrides.items():
        if allow:
            granted.add(capability)
        else:
            granted.discard(capability)
    if level == "Reports only":
        granted &= REPORT_CAPABILITIES
    return {"level": level, "profile": row.get("access_profile"), "capabilities": granted}


def can_sell(user=None):
    access = assignment(user)
    return not access or access["level"] not in ("Reports only", "Invalid")


def reports_only(user=None):
    access = assignment(user)
    return bool(access and access["level"] == "Reports only")


def validate_assignments(doc):
    """Desk/API settings writes must use the same assignment boundaries."""
    before = doc.get_doc_before_save()
    old_rows = (before.get("user_access_levels") or []) if before else []
    rows = doc.get("user_access_levels") or []
    signature = lambda row: (row.get("user"), row.get("access_level"), row.get("access_profile") or "")
    if sorted(signature(row) for row in old_rows) == sorted(signature(row) for row in rows):
        return
    if not native_manager():
        frappe.throw(frappe._("An ERPNext manager must change POS user access levels."), frappe.PermissionError)
    from esafepos.api.user_access import _check_user
    old = {row.user: signature(row) for row in old_rows}
    current, seen = {}, set()
    for row in rows:
        if row.user in seen or row.access_level not in LEVELS:
            frappe.throw(frappe._("Choose one valid POS access level per user."))
        seen.add(row.user)
        current[row.user] = signature(row)
        if row.access_level == "Custom" and not frappe.db.exists("EsafePOS Access Profile", row.get("access_profile")):
            frappe.throw(frappe._("Choose an existing custom access profile."))
        if native_manager(row.user) and row.access_level not in ("Manager", "Use existing roles"):
            frappe.throw(frappe._("Change this user's ERPNext manager role before assigning a lower POS level."))
    for user in set(old) | set(current):
        if old.get(user) != current.get(user):
            _check_user(user, require_enabled=False)
