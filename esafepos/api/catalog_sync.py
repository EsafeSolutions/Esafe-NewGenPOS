"""Small committed-change markers for live POS catalogs; no inventory cache."""
from uuid import uuid4

import frappe
from frappe import _

from esafepos.api.permissions import assert_outlet

REVISION_KEY = "esafepos:catalog:revision"


def _reset():
    frappe.local.esafepos_catalog_change_scheduled = False


def _invalidate():
    _reset()
    try:
        frappe.cache().set_value(REVISION_KEY, uuid4().hex)
    except Exception:
        # SQL has already committed. Cache availability must never fail a posting.
        pass


def changed(doc=None, method=None):
    """Coalesce a transaction's document events and publish only after commit."""
    callbacks = getattr(frappe.db, "after_commit", None)
    if not callbacks or not callable(getattr(callbacks, "add", None)):
        return  # Older Frappe versions use the endpoint's direct polling mode.
    if getattr(frappe.local, "esafepos_catalog_change_scheduled", False):
        return
    frappe.local.esafepos_catalog_change_scheduled = True
    callbacks.add(_invalidate)
    rollback = getattr(frappe.db, "after_rollback", None)
    if rollback and callable(getattr(rollback, "add", None)):
        rollback.add(_reset)


def _context(pos_profile):
    if not frappe.has_permission("Item", "read"):
        frappe.throw(_("You do not have access to the item catalog."), frappe.PermissionError)
    assert_outlet(pos_profile)


@frappe.whitelist()
def revision(pos_profile):
    _context(pos_profile)
    try:
        value = frappe.cache().get_value(REVISION_KEY)
        if not value:
            value = uuid4().hex
            frappe.cache().set_value(REVISION_KEY, value)
        if isinstance(value, bytes):
            value = value.decode()
        direct = not callable(getattr(getattr(frappe.db, "after_commit", None), "add", None))
        return {"revision": value, "direct_poll": direct}
    except Exception:
        return {"revision": "", "direct_poll": True}


@frappe.whitelist()
def item_updates(pos_profile, item_codes):
    """Current authoritative rows for loaded tiles/cart items, bounded to 500."""
    _context(pos_profile)
    from esafepos.api.items import _json_list_codes
    from esafepos.api.catalog import get_items

    codes = _json_list_codes(item_codes)
    if not codes:
        return {"items": [], "removed": []}
    rows = get_items(pos_profile, limit=500, item_codes=codes)["items"]
    found = {row["item_code"] for row in rows}
    return {"items": rows, "removed": [code for code in codes if code not in found]}
