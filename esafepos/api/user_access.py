"""Narrow administration of POS levels and custom profiles, without role grants."""
from __future__ import annotations

import json

import frappe
from frappe import _

from esafepos import user_access
from esafepos.api import permissions


def _require_admin():
    if not user_access.native_manager() or not frappe.has_permission("EsafePOS Settings", "write"):
        frappe.throw(_("An ERPNext System Manager or EsafePOS Manager with Settings write access must manage user access levels."), frappe.PermissionError)
    if not frappe.db.table_exists("EsafePOS User Access Level"):
        frappe.throw(_("Run the site migration to enable user access levels."))


def _check_user(user, require_enabled=True):
    if user in ("Guest", "Administrator"):
        frappe.throw(_("Administrator and Guest access are managed in ERPNext."))
    row = frappe.db.get_value("User", user, ["enabled", "user_type"], as_dict=True)
    if not row or (require_enabled and not row.enabled) or row.user_type != "System User":
        frappe.throw(_("Choose an enabled system user."))
    scope = permissions.allowed_companies()
    theirs = permissions.allowed_companies(user)
    if scope is not None and (theirs is None or not theirs <= scope):
        frappe.throw(_("This user has access outside your companies. Ask an unrestricted administrator to manage their POS level."), frappe.PermissionError)


@frappe.whitelist()
def get_access_management():
    _require_admin()
    users = []
    scope = permissions.allowed_companies()
    logins_supported = frappe.get_meta("User").has_field("simultaneous_sessions")
    for row in frappe.get_all("User", filters={"enabled": 1, "user_type": "System User", "name": ["not in", ["Guest", "Administrator"]]},
                              fields=["name", "full_name"] + (["simultaneous_sessions"] if logins_supported else []), order_by="full_name asc"):
        theirs = permissions.allowed_companies(row.name)
        if scope is None or (theirs is not None and theirs <= scope):
            users.append(row)
    settings = frappe.get_cached_doc("EsafePOS Settings")
    profiles = []
    for name in frappe.get_all("EsafePOS Access Profile", pluck="name", order_by="name asc"):
        doc = frappe.get_cached_doc("EsafePOS Access Profile", name)
        profiles.append({"name": doc.name, "base_level": doc.base_level, "modified": str(doc.modified),
                         "capabilities": [{"capability": r.capability, "allowed": r.allowed} for r in doc.get("capabilities") or []]})
    visible = {row.name for row in users}
    return {"users": users, "levels": user_access.LEVELS, "capabilities": user_access.CAPABILITIES,
            "can_manage_logins": logins_supported and bool(frappe.has_permission("User", "write")),
            "presets": {name: sorted(caps) for name, caps in user_access.PRESETS.items()}, "profiles": profiles,
            "assignments": [{"user": r.user, "access_level": r.access_level, "access_profile": r.get("access_profile") or ""}
                            for r in settings.get("user_access_levels") or [] if r.user in visible]}


@frappe.whitelist(methods=["POST"])
def save_login_limit(user: str, simultaneous_sessions: int | str):
    _require_admin()
    _check_user(user)
    if not frappe.has_permission("User", "write"):
        frappe.throw(_("ERPNext User write permission is required to change concurrent logins."), frappe.PermissionError)
    try:
        count = int(simultaneous_sessions)
        if str(count) != str(simultaneous_sessions) or not 1 <= count <= 20:
            raise ValueError()
    except (TypeError, ValueError):
        frappe.throw(_("Choose between 1 and 20 concurrent logins."))
    doc = frappe.get_doc("User", user)
    doc.check_permission("write")
    if not doc.meta.has_field("simultaneous_sessions"):
        frappe.throw(_("This Frappe version does not expose the concurrent login setting."))
    doc.simultaneous_sessions = count
    doc.save()
    from esafepos.api import audit
    audit.log("POS concurrent login limit changed", detail="{0}: {1}".format(user, count))
    return {"saved": True}


@frappe.whitelist(methods=["POST"])
def save_user_level(user: str, access_level: str, access_profile: str = ""):
    _require_admin()
    _check_user(user)
    if access_level not in user_access.LEVELS:
        frappe.throw(_("Choose a valid access level."))
    if access_level == "Custom" and not frappe.db.exists("EsafePOS Access Profile", access_profile):
        frappe.throw(_("Choose an existing custom access profile."))
    if user_access.native_manager(user) and access_level not in ("Manager", "Use existing roles"):
        frappe.throw(_("This user holds an ERPNext manager role. Change that role in ERPNext before assigning a lower POS level."))
    frappe.db.sql("select field from tabSingles where doctype=%s for update", "EsafePOS Settings")
    doc = frappe.get_doc("EsafePOS Settings")
    rows = list(doc.get("user_access_levels") or [])
    row = next((row for row in rows if row.user == user), None)
    if access_level == "Use existing roles":
        doc.set("user_access_levels", [r for r in rows if r.user != user])
    else:
        values = {"user": user, "access_level": access_level, "access_profile": access_profile if access_level == "Custom" else None}
        if row:
            row.update(values)
        else:
            doc.append("user_access_levels", values)
    doc.save()
    from esafepos.api import audit
    audit.log("POS user access changed", detail="{0}: {1} {2}".format(user, access_level, access_profile if access_level == "Custom" else ""))
    return {"saved": True}


@frappe.whitelist(methods=["POST"])
def save_access_profile(profile: dict | str):
    _require_admin()
    if isinstance(profile, str):
        profile = json.loads(profile)
    name = (profile.get("name") or "").strip()
    base = profile.get("base_level")
    if not name or len(name) > 100 or base not in user_access.PRESETS:
        frappe.throw(_("Enter a profile name and a valid base level."))
    caps, seen = [], set()
    for row in profile.get("capabilities") or []:
        capability = row.get("capability")
        if capability not in user_access.CAPABILITIES or capability in seen or row.get("allowed") not in (0, 1, False, True):
            frappe.throw(_("Each capability must appear once with an allowed or denied choice."))
        if base == "Reports only" and row.get("allowed") and capability not in user_access.REPORT_CAPABILITIES:
            frappe.throw(_("A reports-only profile cannot allow sales or cash operations."))
        seen.add(capability)
        caps.append({"capability": capability, "allowed": int(row.get("allowed"))})
    # Editing a shared profile can affect more users than the current screen.
    for row in frappe.get_cached_doc("EsafePOS Settings").get("user_access_levels") or []:
        if row.get("access_profile") == name:
            _check_user(row.user, require_enabled=False)
    if frappe.db.exists("EsafePOS Access Profile", name):
        doc = frappe.get_doc("EsafePOS Access Profile", name)
        if str(doc.modified) != profile.get("modified"):
            frappe.throw(_("This access profile changed. Reload it before saving."))
    else:
        doc = frappe.new_doc("EsafePOS Access Profile")
        doc.profile_name = name
    doc.base_level = base
    doc.set("capabilities", caps)
    doc.save()
    from esafepos.api import audit
    audit.log("POS access profile changed", detail=name)
    return {"saved": True, "name": doc.name}
