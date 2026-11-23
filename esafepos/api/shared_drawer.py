"""Optional physical drawer pooling; invoices never move between cashiers."""
import hashlib
import json

import frappe
from frappe import _
from frappe.utils import flt

from esafepos.api import permissions, register
from esafepos.cash_count import allocate_count, clean_counts, decimal_number


def _require_manager():
    if not permissions.is_manager() or not frappe.has_permission("POS Register Session", "write"):
        frappe.throw(_("A manager must combine or close shared cash drawers."), frappe.PermissionError)


def _doc(name, for_update=False):
    if not frappe.has_permission("POS Register Session", "read"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    doc = frappe.get_doc("POS Register Session", name, for_update=for_update)
    permissions.assert_outlet(doc.pos_profile)
    return doc


def _members(doc, for_update=False):
    if not doc.get("combined_drawer"):
        return [doc]
    rows = frappe.db.get_values("POS Register Session", {"combined_drawer": doc.combined_drawer}, ["name"],
                                as_dict=True, for_update=for_update, order_by="name asc")
    return [_doc(row.name, for_update=for_update) for row in rows]


def _signature(doc):
    profile = frappe.get_cached_doc("POS Profile", doc.pos_profile)
    cash = [register._drawer_mode(profile.name)] + sorted(register._foreign_drawers(profile.name))
    # Matching ledger accounts are required: moving cash between different bank
    # accounts requires accounting transfers, not an operational drawer link.
    accounts = [(mode, frappe.db.get_value("Mode of Payment Account", {
        "parent": mode, "company": profile.company,
    }, "default_account")) for mode in cash if mode]
    return (profile.company, register._drawer_mode(profile.name), register._foreign_drawers(profile.name), accounts)


def _validate_members(docs):
    signature = _signature(docs[0])
    if not signature[1] or any(not account for mode, account in signature[3]):
        frappe.throw(_("Configure a cash drawer and its company account before combining shifts."))
    if len(docs) > 20:
        frappe.throw(_("Combine at most 20 open shifts in one cash drawer."))
    for doc in docs:
        if doc.status != "Open":
            frappe.throw(_("Only open shifts can be combined. Refresh the drawer."))
        if _signature(doc) != signature:
            frappe.throw(_("Combined shifts must use the same company, cash payment methods, currencies and cash accounts."))


def _member_row(doc):
    return {"session": doc.name, "pos_profile": doc.pos_profile, "opened_by": doc.opened_by,
            "opened_by_name": frappe.utils.get_fullname(doc.opened_by), "status": doc.status}


@frappe.whitelist()
def candidates(session):
    _require_manager()
    doc = _doc(session)
    if not frappe.get_meta("POS Register Session").has_field("combined_drawer"):
        frappe.throw(_("Run bench migrate to enable combined cash drawers."))
    current = {d.name for d in _members(doc)}
    signature = _signature(doc)
    rows = frappe.get_all("POS Register Session", {"status": "Open"}, fields=["name", "pos_profile"], order_by="opened_at asc")
    result = []
    for row in rows:
        if row.name in current or not permissions.can_use_outlet(row.pos_profile):
            continue
        target = _doc(row.name)
        if _signature(target) == signature:
            result.append(_member_row(target))
    return result


@frappe.whitelist()
def combine(session, target):
    _require_manager()
    first, second = _doc(session), _doc(target)
    roots = sorted({first.get("combined_drawer") or first.name, second.get("combined_drawer") or second.name})
    for name in roots:
        frappe.db.get_value("POS Register Session", name, "status", for_update=True)
    first, second = _doc(session, for_update=True), _doc(target, for_update=True)
    if sorted({first.get("combined_drawer") or first.name, second.get("combined_drawer") or second.name}) != roots:
        frappe.throw(_("The drawer changed. Refresh and try again."))
    docs = {d.name: d for d in _members(first, for_update=True) + _members(second, for_update=True)}
    if len(docs) < 2:
        frappe.throw(_("Select another open shift to combine."))
    for name in sorted(docs):
        frappe.db.get_value("POS Register Session", name, "status", for_update=True)
        docs[name] = _doc(name, for_update=True)
    _validate_members(list(docs.values()))
    root = roots[0]
    for doc in docs.values():
        doc.db_set("combined_drawer", root)
    from esafepos.api import audit
    audit.log("Combined cash drawer", detail=", ".join(sorted(docs)), reference_doctype="POS Register Session",
              reference_name=root, pos_profile=first.pos_profile)
    return summary(first.name)


def _ledger_versions(docs, for_update=False):
    """Current-read invoice/receipt identities catch commits while locks waited.

    In repeatable-read databases, a regular summary SELECT can still see the
    request's earlier snapshot after acquiring a shift lock. Comparing these
    locking reads with the displayed version rejects that stale close too.
    """
    from esafepos.api.sales import _table_doctype
    ledger = []
    for doc in docs:
        sales = frappe.db.get_values(_table_doctype(doc.pos_profile),
            {"esafepos_session": doc.name, "docstatus": 1}, ["name", "modified"],
            as_dict=True, for_update=for_update, order_by="name asc")
        receipts = []
        if frappe.get_meta("Journal Entry").has_field("esafepos_session"):
            receipts = frappe.db.get_values("Journal Entry",
                {"esafepos_session": doc.name, "docstatus": 1, "esafepos_credit_kind": "Payment"}, ["name", "modified"],
                as_dict=True, for_update=for_update, order_by="name asc")
        ledger.append({"session": doc.name, "sales": sales, "receipts": receipts})
    return ledger


def _summarize(docs, for_update=False):
    ledger = _ledger_versions(docs, for_update=for_update)
    figures = [register.get_session_summary(d.name) for d in docs]
    expected = {}
    for figure in figures:
        for row in figure["expected"]:
            mode = row["mode_of_payment"]
            if mode in expected and expected[mode]["currency"] != row["currency"]:
                frappe.throw(_("The linked drawers no longer use matching payment currencies."))
            merged = expected.setdefault(mode, dict(row, expected_amount=0))
            merged["expected_amount"] = flt(merged["expected_amount"] + row["expected_amount"], 2)
    # Includes cash movements and customer payments, not just the invoice count.
    fingerprint = [{"session": d.name, "modified": str(d.modified), "status": d.status,
                    "group": d.get("combined_drawer"), "figures": f} for d, f in zip(docs, figures)]
    version = hashlib.sha256(json.dumps({"figures": fingerprint, "ledger": ledger}, sort_keys=True, default=str).encode()).hexdigest()
    return {"group": docs[0].get("combined_drawer"), "members": [_member_row(d) for d in docs],
            "expected": list(expected.values()), "company_currency": figures[0]["company_currency"],
            "rates": figures[0]["rates"], "version": version, "all_open": all(d.status == "Open" for d in docs),
            "sales_count": sum(f["sales_count"] for f in figures)}, figures


@frappe.whitelist()
def summary(session):
    doc = _doc(session)
    if doc.get("combined_drawer") and not permissions.is_manager():
        # A linked cashier may be assigned only to their own POS Profile.
        # Synchronize group membership/closure without granting access to
        # another outlet's detailed sales or financial summaries.
        rows = frappe.get_all("POS Register Session", {"combined_drawer": doc.combined_drawer},
                              fields=["name", "pos_profile", "opened_by", "status"], order_by="name asc")
        return {"group": doc.combined_drawer, "members": [_member_row(r) for r in rows],
                "all_open": all(r.status == "Open" for r in rows), "expected": [], "version": None}
    return _summarize(_members(doc))[0]


@frappe.whitelist()
def close(session, counted, version, denomination_counts=None, closing_note=None, variance_reason=None, variance_action=None):
    """Freeze every member before reading totals, then commit the whole group.

    Each member retains its normal, independently retryable ERPNext closing.
    No intermediate commit can close only part of the physical drawer.
    """
    _require_manager()
    doc = _doc(session)
    root = doc.get("combined_drawer")
    if not root:
        frappe.throw(_("This shift is not using a combined cash drawer."))
    frappe.db.get_value("POS Register Session", root, "status", for_update=True)
    doc = _doc(session, for_update=True)
    if doc.get("combined_drawer") != root:
        frappe.throw(_("The drawer changed. Refresh and try again."))
    docs = sorted(_members(doc, for_update=True), key=lambda d: d.name)
    for index, member in enumerate(docs):
        frappe.db.get_value("POS Register Session", member.name, "status", for_update=True)
        member = docs[index] = _doc(member.name, for_update=True)
        needed = "POS Closing Entry" if member.get("pos_opening_entry") else "POS Register Session"
        if not permissions.can_close_register() or not frappe.has_permission(needed, "create"):
            frappe.throw(_("You are not permitted to close these shifts."), frappe.PermissionError)
    _validate_members(docs)
    current, figures = _summarize(docs, for_update=True)
    if current["version"] != version:
        frappe.throw(_("The combined drawer changed. Refresh, re-check the cash, then close again."))
    if isinstance(counted, str):
        counted = json.loads(counted)
    rows = {r["mode_of_payment"]: r for r in current["expected"]}
    if not isinstance(counted, dict) or set(counted) != set(rows):
        frappe.throw(_("Enter a count for every payment method in the combined drawer."))
    try:
        for mode, amount in counted.items():
            number = decimal_number(amount)
            if abs(number) > 1000000000000 or (rows[mode].get("is_cash") and number < 0):
                raise ValueError("Enter a valid non-negative cash count.")
        breakdown = clean_counts(denomination_counts, counted, {
            mode: r["currency"] for mode, r in rows.items() if r.get("is_cash")
        })
    except (ValueError, TypeError, AttributeError) as exc:
        frappe.throw(str(exc))
    allocations = [{} for d in docs]
    for mode in rows:
        expected = [next((r["expected_amount"] for r in f["expected"] if r["mode_of_payment"] == mode), 0) for f in figures]
        for allocation, amount in zip(allocations, allocate_count(counted[mode], expected, allow_negative=not rows[mode].get("is_cash"))):
            allocation[mode] = amount
    snapshot = json.dumps({"members": [d.name for d in docs], "counted": counted, "denominations": breakdown,
                           "expected": current["expected"], "allocations": dict(zip([d.name for d in docs], allocations)),
                           "counted_by": frappe.session.user, "version": version})
    # First validate the aggregate variance, including the site's threshold.
    from esafepos import variance
    check = frappe._dict(name=root, opened_by=doc.opened_by, pos_profile=doc.pos_profile, currency_rates=doc.get("currency_rates"), payment_counts=[
        frappe._dict(mode_of_payment=mode, expected_amount=r["expected_amount"], counted_amount=flt(counted[mode]),
                     difference=flt(flt(counted[mode]) - r["expected_amount"], 2), currency=r["currency"])
        for mode, r in rows.items()
    ])
    variance.apply(check, variance_reason, variance_action, figures_known=True)
    for member, allocation, figure in zip(docs, allocations, figures):
        member.combined_count = snapshot
        # A shared breakdown belongs to the physical group, not each allocation.
        register._stage_close(member, allocation, figure, closing_note, check.variance_reason, check.variance_action, variance_applied=True)
    frappe.db.commit()  # All members become unsellable together.
    results = []
    for member in docs:
        if member.get("pos_opening_entry"):
            register._enqueue_consolidation(member.name)
        else:
            register._mark_closed(member.name, None)
            member.status = "Closed"
        register._audit_register("close", member.name, member.pos_profile, member.total_sales,
                                 detail="Combined cash drawer {0}; allocated physical count".format(root))
        results.append(register._close_result(member, queued=bool(member.get("pos_opening_entry"))))
    register._maybe_alert_variance(check)
    return {"group": root, "sessions": results, "counted": counted}
