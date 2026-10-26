# Copyright (c) 2026 Lumen Solutions
# SPDX-License-Identifier: AGPL-3.0-only
# "LumenPOS" is a trademark of Lumen Solutions. See TRADEMARKS.md.
"""The Lumen Stock app on a LumenPOS site (0.68.0).

Lumen Stock is a phone app for stock work: counting a warehouse (alone or with
several phones at once), stock entries and purchase receipts. It first talked to
the Lumen Connector app; a LumenPOS site gets the same methods here, with the
same names, arguments and answers, so one app works with either
(`lumenpos.api.stock_app.ping` tells it LumenPOS is there).

Everything the app saves is an ordinary ERPNext document saved as the person on
the phone, so ERPNext's own permissions and validations apply. On top of them a
section of LumenPOS Settings (General, Lumen Stock app) switches the app and each
of its parts on or off, and the capability "Use the stock app" (open until a shop
names someone) says who may use it. Both are checked here, on the server.

A shared count: each phone keeps its own lines (POS Count Device) and replaces
them on every sync, so phones never overwrite each other. A supervisor merges
them into one Stock Reconciliation draft: quantities of the same item from
different phones are added, serial numbers combined. Only differences go into
the draft.

What LumenPOS adds to the connector's rules: a POS Invoice moves no stock until
its shift is closed (see catalog.pos_reserved_map). So the "system quantity" of
a count is what is on the shelf (the Bin less the sales not posted yet), and a
stock count is not submitted from the app while sales not yet posted hold any of
its items in its warehouse: closing the shift afterwards would take those goods
off a second time.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, get_fullname, now_datetime, nowdate

from lumenpos.api import permissions

CONFIG_VERSION = 1
SESSION_DT = "POS Count Session"
DEVICE_DT = "POS Count Device"
# Kept word for word from the connector: a count saved by the app carries this
# comment, whichever backend saved it, so the moved-stock check finds it.
APP_MARKER = "Created via the Lumen Stock mobile app"

STOCK_DOCTYPES = {
    "Stock Reconciliation": "count",
    "Stock Entry": "stock_entry",
    "Purchase Receipt": "purchase_receipt",
}

# feature key: (LumenPOS Settings field, default)
STOCK_FLAG_FIELDS = {
    "count": ("stock_allow_count", 1),
    "stock_entry": ("stock_allow_stock_entry", 1),
    "purchase_receipt": ("stock_allow_purchase_receipt", 1),
    "submit": ("stock_allow_submit", 1),
    "blind_count": ("stock_blind_count", 0),
    "shared_count": ("stock_allow_shared_count", 1),
    "link_barcode": ("stock_allow_link_barcode", 1),
    "export": ("stock_allow_export", 1),
    "warn_moved": ("stock_warn_moved", 1),
}
SWITCH = "enable_stock_app"
# Every field of the section, for Settings (get and save) and the install.
FIELDS = (SWITCH,) + tuple(field for field, _default in STOCK_FLAG_FIELDS.values())


def _stored():
    """The section as stored, field: value. A field never stored keeps its
    default (a site updated without its migrate has none of them yet)."""
    try:
        rows = frappe.db.sql(
            "select field, value from tabSingles where doctype=%s and field in %s",
            ("LumenPOS Settings", FIELDS),
        )
    except Exception:
        return {}
    return {field: value for field, value in rows}


def flags() -> dict:
    stored = _stored()

    def read(field, default):
        value = stored.get(field)
        return default if value in (None, "") else cint(value)

    out = {key: read(field, default) for key, (field, default) in STOCK_FLAG_FIELDS.items()}
    out["enabled"] = read(SWITCH, 1)
    return out


def settings_values() -> dict:
    """The section for the Settings screen, by field name."""
    f = flags()
    out = {SWITCH: f["enabled"]}
    for key, (field, _default) in STOCK_FLAG_FIELDS.items():
        out[field] = f[key]
    return out


def can_use(user=None) -> bool:
    return bool(flags()["enabled"]) and permissions.allowed(permissions.STOCK_APP, user)


def _guard(doctype, need=None):
    """Raise unless the app, this document type and (optionally) the switch
    `need` are all on for the person asking."""
    if doctype not in STOCK_DOCTYPES:
        frappe.throw(_("{0} is not handled by the Lumen Stock app.").format(doctype), frappe.PermissionError)
    f = flags()
    if not f["enabled"]:
        frappe.throw(_("The Lumen Stock app is turned off in LumenPOS Settings."), frappe.PermissionError)
    if not permissions.allowed(permissions.STOCK_APP):
        frappe.throw(_("You're not allowed to use the Lumen Stock app."), frappe.PermissionError)
    if not f[STOCK_DOCTYPES[doctype]]:
        frappe.throw(_("{0} is turned off for the Lumen Stock app.").format(_(doctype)), frappe.PermissionError)
    if need and not f[need]:
        if need == "submit":
            frappe.throw(
                _("Approving from the app is turned off. Ask a supervisor to approve it from the desk."),
                frappe.PermissionError,
            )
        if need == "link_barcode":
            frappe.throw(_("Linking barcodes from the app is turned off in LumenPOS Settings."), frappe.PermissionError)
        frappe.throw(_("Shared counting is turned off in LumenPOS Settings."), frappe.PermissionError)


def _has_workflow(doctype):
    from frappe.model.workflow import get_workflow_name

    return bool(get_workflow_name(doctype))


def _default_warehouse():
    """Stock Settings' default warehouse, as the connector answers. ERPNext 16
    dropped that field (reading it there raises), so there the person's own
    default warehouse stands in."""
    if frappe.get_meta("Stock Settings").has_field("default_warehouse"):
        return frappe.db.get_single_value("Stock Settings", "default_warehouse") or ""
    return frappe.defaults.get_user_default("Warehouse") or ""


@frappe.whitelist()
def ping():
    """A light probe: the app learns that LumenPOS serves it, and which version."""
    import lumenpos

    return {"ok": True, "version": CONFIG_VERSION, "backend": "lumenpos", "lumenpos": lumenpos.__version__}


@frappe.whitelist()
def stock_app_config():
    """What the app needs to decide what to show: the switches, ERPNext's own
    permissions, and which document types go through a workflow."""
    f = flags()
    allowed = permissions.allowed(permissions.STOCK_APP)
    reason = ""
    if not f["enabled"]:
        reason = _("The Lumen Stock app is turned off in LumenPOS Settings.")
    elif not allowed:
        reason = _("You're not allowed to use the Lumen Stock app.")
    perms = {}
    workflows = {}
    for doctype in STOCK_DOCTYPES:
        perms[doctype] = {}
        for ptype in ("read", "create", "write", "submit"):
            granted = frappe.has_permission(doctype, ptype)
            perms[doctype][ptype] = int(bool(granted))
        workflows[doctype] = int(_has_workflow(doctype))
    return {
        "version": CONFIG_VERSION,
        "backend": "lumenpos",
        "enabled": int(bool(f["enabled"] and allowed)),
        "reason": reason,
        "features": {key: f[key] for key in STOCK_FLAG_FIELDS},
        "permissions": perms,
        "workflows": workflows,
        "company": frappe.defaults.get_user_default("Company") or "",
        "default_warehouse": _default_warehouse(),
        "user": frappe.session.user,
        "full_name": get_fullname(frappe.session.user),
    }


@frappe.whitelist(methods=["POST"])
def stock_save(doc: str | dict):
    """Insert a new draft, or update an existing draft, of a stock document,
    with ERPNext's own validations and permission checks."""
    data = frappe.parse_json(doc) or {}
    doctype = data.get("doctype")
    _guard(doctype)
    name = data.get("name")
    if name and frappe.db.exists(doctype, name):
        target = frappe.get_doc(doctype, name)
        if target.docstatus != 0:
            frappe.throw(_("Only draft documents can be edited from the app."))
        target.check_permission("write")
        for key in ("docstatus", "owner", "creation", "modified", "modified_by", "name", "doctype"):
            data.pop(key, None)
        target.update(data)
        target.save()
    else:
        data.pop("name", None)
        data["docstatus"] = 0
        target = frappe.get_doc(data)
        target.insert()
        target.add_comment("Comment", APP_MARKER)
    return target.as_dict()


@frappe.whitelist()
def stock_actions(doctype: str, name: str):
    """What the person may do next on a draft: the workflow actions open to
    them, or a plain Submit when the document type has no workflow."""
    _guard(doctype)
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    out = {"workflow": int(_has_workflow(doctype)), "state": "", "actions": [], "docstatus": doc.docstatus}
    if doc.docstatus != 0 or not flags()["submit"]:
        return out
    if out["workflow"]:
        from frappe.model.workflow import get_transitions, get_workflow

        out["state"] = doc.get(get_workflow(doctype).workflow_state_field) or ""
        out["actions"] = [{"action": t.get("action"), "next_state": t.get("next_state")} for t in get_transitions(doc)]
    elif frappe.has_permission(doctype, "submit", doc=doc):
        out["actions"] = [{"action": "Submit", "next_state": "Submitted"}]
    return out


@frappe.whitelist(methods=["POST"])
def stock_submit(doctype: str, name: str, action: str | None = None):
    """Apply a workflow action, or submit when the document type has none. A
    stock count waits while sales not yet posted hold any of its items."""
    _guard(doctype, need="submit")
    doc = frappe.get_doc(doctype, name)
    if doctype == "Stock Reconciliation":
        held = _unposted(doc)
        if held:
            frappe.throw(
                _(
                    "Close the open shifts first: {0} items of this count are in sales not posted yet ({1}). "
                    "Closing them afterwards would take those goods off again."
                ).format(len(held), ", ".join(sorted({n for h in held for n in h["invoices"]})[:5]))
            )
    if _has_workflow(doctype):
        from frappe.model.workflow import apply_workflow

        if not action:
            frappe.throw(_("Choose an approval action."))
        doc = apply_workflow(doc, action)
    else:
        doc.check_permission("submit")
        doc.submit()
    return doc.as_dict()


# ------------------------------------------------------------ shared counts --


def _shared_guard():
    _guard("Stock Reconciliation", need="shared_count")
    if not frappe.has_permission("Stock Reconciliation", "create"):
        frappe.throw(_("You're not allowed to create stock counts."), frappe.PermissionError)


def _count_session(name, must_be_open=True):
    if not name or not frappe.db.exists(SESSION_DT, name):
        frappe.throw(_("Count session {0} was not found.").format(name))
    doc = frappe.get_doc(SESSION_DT, name)
    if not frappe.has_permission("Warehouse", "read", doc=doc.warehouse):
        frappe.throw(_("You have no access to warehouse {0}.").format(doc.warehouse), frappe.PermissionError)
    if must_be_open and doc.status != "Open":
        frappe.throw(_("Count session {0} is already {1}.").format(name, _(doc.status)))
    return doc


def _device_lines(raw):
    data = frappe.parse_json(raw or "{}") or {}
    return data if isinstance(data, dict) else {}


def _merged_lines(session):
    """item_code: {qty, serials} added up over every phone of the session."""
    out = {}
    for row in frappe.get_all(DEVICE_DT, filters={"session": session}, fields=["data"]):
        for code, value in _device_lines(row.get("data")).items():
            line = out.setdefault(code, {"qty": 0.0, "serials": set()})
            serials = [s for s in ((value or {}).get("s") or []) if s]
            if serials:
                line["serials"].update(serials)
            else:
                line["qty"] += flt((value or {}).get("q"))
    for line in out.values():
        if line["serials"]:
            line["qty"] = float(len(line["serials"]))
    return out


def _shelf(warehouse):
    """item_code: what is on the shelf now, the Bin less the POS sales not
    posted yet (they leave the Bin only when their shift is closed)."""
    from lumenpos.api.catalog import pos_reserved_map

    held = pos_reserved_map(warehouse)
    return {
        b.get("item_code"): flt(b.get("actual_qty")) - flt(held.get(b.get("item_code")))
        for b in frappe.get_all("Bin", filters={"warehouse": warehouse}, fields=["item_code", "actual_qty"])
    }


@frappe.whitelist()
def count_sessions(warehouse: str | None = None):
    """Open shared counts the person can join (their warehouse permissions apply)."""
    _shared_guard()
    filters = {"status": "Open"}
    if warehouse:
        filters["warehouse"] = warehouse
    rows = frappe.get_list(
        SESSION_DT,
        filters=filters,
        fields=["name", "title", "warehouse", "company", "opened_by", "creation", "full_count"],
        order_by="creation desc",
        limit_page_length=50,
    )
    for row in rows:
        row["devices"] = frappe.db.count(DEVICE_DT, {"session": row["name"]})
        row["opened_by_name"] = get_fullname(row.get("opened_by"))
        row["creation"] = str(row.get("creation") or "")
    return rows


@frappe.whitelist(methods=["POST"])
def count_session_open(warehouse: str, title: str | None = None, full_count: int | str = 0):
    """Start a shared count of a warehouse. A full count sets the items with
    stock that nobody counted to zero when the session is merged."""
    _shared_guard()
    if not warehouse or not frappe.db.exists("Warehouse", warehouse):
        frappe.throw(_("Warehouse {0} was not found.").format(warehouse))
    if not frappe.has_permission("Warehouse", "read", doc=warehouse):
        frappe.throw(_("You have no access to warehouse {0}.").format(warehouse), frappe.PermissionError)
    doc = frappe.get_doc({
        "doctype": SESSION_DT,
        "title": title or warehouse,
        "warehouse": warehouse,
        "company": frappe.db.get_value("Warehouse", warehouse, "company"),
        "status": "Open",
        "full_count": 1 if cint(full_count) else 0,
        "opened_by": frappe.session.user,
    })
    doc.insert(ignore_permissions=True)
    return {
        "name": doc.name,
        "title": doc.title,
        "warehouse": doc.warehouse,
        "company": doc.company,
        "opened_by": doc.opened_by,
        "opened_by_name": get_fullname(doc.opened_by),
        "full_count": doc.full_count,
        "devices": 0,
    }


@frappe.whitelist(methods=["POST"])
def count_session_push(session: str, device_id: str, data: str | dict, device_label: str | None = None):
    """Replace this phone's lines in the session with what it holds now.
    data = {"item code": {"q": qty, "s": [serial numbers]}}"""
    _shared_guard()
    _count_session(session)
    if not device_id:
        frappe.throw(_("The device id is missing."))
    items = frappe.parse_json(data) if isinstance(data, str) else data
    if not isinstance(items, dict):
        frappe.throw(_("The count data is not valid."))
    lines = len(items)
    units = sum(flt((v or {}).get("q")) for v in items.values())
    values = {
        "counted_by": frappe.session.user,
        "device_label": (device_label or "")[:140],
        "lines": lines,
        "units": units,
        "data": frappe.as_json(items),
        "last_sync": now_datetime(),
    }
    name = frappe.db.get_value(DEVICE_DT, {"session": session, "device_id": device_id})
    if name:
        frappe.db.set_value(DEVICE_DT, name, values)
    else:
        frappe.get_doc({"doctype": DEVICE_DT, "session": session, "device_id": device_id, **values}).insert(
            ignore_permissions=True
        )
    return {"lines": lines, "units": units, "last_sync": str(values["last_sync"])}


@frappe.whitelist()
def count_session_status(session: str):
    """Progress of a shared count: every phone, and the merged totals."""
    _shared_guard()
    doc = _count_session(session, must_be_open=False)
    devices = frappe.get_all(
        DEVICE_DT,
        filters={"session": session},
        fields=["device_id", "device_label", "counted_by", "lines", "units", "last_sync"],
        order_by="last_sync desc",
    )
    for row in devices:
        row["counted_by_name"] = get_fullname(row.get("counted_by"))
        row["last_sync"] = str(row.get("last_sync") or "")
    merged = _merged_lines(session)
    return {
        "name": doc.name,
        "title": doc.title,
        "warehouse": doc.warehouse,
        "company": doc.company,
        "status": doc.status,
        "reconciliation": doc.reconciliation or "",
        "opened_by": doc.opened_by,
        "opened_by_name": get_fullname(doc.opened_by),
        "full_count": doc.full_count or 0,
        "devices": devices,
        "items": len(merged),
        "units": sum(line["qty"] for line in merged.values()),
    }


@frappe.whitelist()
def count_session_lines(session: str):
    """Every item of a shared count with each phone's quantity, the total and
    the quantity on the shelf. Worked out only when someone asks (the desk form
    or the app's export), so it costs nothing while the phones count."""
    if not frappe.has_permission(SESSION_DT, "read"):
        frappe.throw(_("You're not allowed to see count sessions."), frappe.PermissionError)
    doc = _count_session(session, must_be_open=False)
    devices = frappe.get_all(
        DEVICE_DT,
        filters={"session": session},
        fields=["device_id", "device_label", "counted_by", "lines", "units", "last_sync", "data"],
        order_by="creation asc",
    )
    items = {}
    for dev in devices:
        for code, value in _device_lines(dev.get("data")).items():
            row = items.setdefault(code, {"item_code": code, "by_device": {}, "serials": set()})
            serials = [s for s in ((value or {}).get("s") or []) if s]
            row["serials"].update(serials)
            row["by_device"][dev["device_id"]] = float(len(serials)) if serials else flt((value or {}).get("q"))
    shelf = _shelf(doc.warehouse)
    if doc.full_count:
        # A full count also shows what will be set to zero.
        for code, qty in shelf.items():
            if qty > 0 and code not in items:
                items[code] = {"item_code": code, "by_device": {}, "serials": set()}
    names = {}
    codes = list(items)
    for start in range(0, len(codes), 500):
        for it in frappe.get_all("Item", filters={"name": ["in", codes[start:start + 500]]}, fields=["name", "item_name"]):
            names[it.get("name")] = it.get("item_name")
    blind = flags()["blind_count"]
    out = []
    for code, row in items.items():
        total = float(len(row["serials"])) if row["serials"] else sum(row["by_device"].values())
        out.append({
            "item_code": code,
            "item_name": names.get(code) or code,
            "by_device": row["by_device"],
            "total": total,
            "system_qty": None if blind else shelf.get(code, 0.0),
            "serials": sorted(row["serials"]),
        })
    out.sort(key=lambda r: (r["item_name"] or "").lower())
    return {
        "name": doc.name,
        "warehouse": doc.warehouse,
        "status": doc.status,
        "full_count": doc.full_count or 0,
        "blind": blind,
        "devices": [
            {
                "device_id": dev["device_id"],
                "device_label": dev.get("device_label") or "",
                "counted_by": dev.get("counted_by"),
                "counted_by_name": get_fullname(dev.get("counted_by")),
                "lines": dev.get("lines") or 0,
                "units": dev.get("units") or 0,
                "last_sync": str(dev.get("last_sync") or ""),
            }
            for dev in devices
        ],
        "items": out,
    }


def _system_stock(warehouse, merged):
    """item_code: {qty, serials} on the shelf now, plus the serial numbers of
    the serialised items that were counted."""
    out = {code: {"qty": qty, "serials": set()} for code, qty in _shelf(warehouse).items()}
    serialised = [code for code, line in merged.items() if line["serials"]]
    for start in range(0, len(serialised), 500):
        for sn in frappe.get_all(
            "Serial No",
            filters={"warehouse": warehouse, "item_code": ["in", serialised[start:start + 500]]},
            fields=["name", "item_code"],
        ):
            out.setdefault(sn.get("item_code"), {"qty": 0.0, "serials": set()})["serials"].add(sn.get("name"))
    return out


def _same_count(line, current):
    if line["serials"] or current["serials"]:
        return line["serials"] == current["serials"]
    return abs(line["qty"] - current["qty"]) < 1e-9


@frappe.whitelist(methods=["POST"])
def count_session_merge(session: str, zero_uncounted: int | str | None = None):
    """Merge every phone's count into one Stock Reconciliation draft. Items not
    counted are set to zero for a full count (or when asked)."""
    _shared_guard()
    doc = _count_session(session)
    if zero_uncounted is None:
        zero_uncounted = doc.full_count
    merged = _merged_lines(session)
    if not merged:
        frappe.throw(_("Nothing has been counted in this session yet."))
    system = _system_stock(doc.warehouse, merged)
    serial_fields = frappe.get_meta("Stock Reconciliation Item").has_field("use_serial_batch_fields")
    rows = []
    unchanged = 0
    for code, line in merged.items():
        current = system.get(code) or {"qty": 0.0, "serials": set()}
        if _same_count(line, current):
            # Only differences go into the count. ERPNext drops such rows too,
            # but compares serial numbers as one text, so a serialised item
            # counted in another order was kept as if it had changed.
            unchanged += 1
            continue
        row = {"item_code": code, "warehouse": doc.warehouse, "qty": line["qty"]}
        if line["serials"]:
            row["serial_no"] = "\n".join(sorted(line["serials"]))
            if serial_fields:
                row["use_serial_batch_fields"] = 1
        rows.append(row)
    if cint(zero_uncounted):
        for code, current in system.items():
            if code not in merged and current["qty"] > 0:
                rows.append({"item_code": code, "warehouse": doc.warehouse, "qty": 0})
    if not rows:
        frappe.throw(_("Every counted item matches the quantity on the shelf. There is nothing to adjust."))
    devices = frappe.db.count(DEVICE_DT, {"session": session})
    reco = frappe.get_doc({
        "doctype": "Stock Reconciliation",
        "purpose": "Stock Reconciliation",
        "company": doc.company,
        "posting_date": nowdate(),
        "items": rows,
    })
    if reco.meta.has_field("set_warehouse"):
        reco.set_warehouse = doc.warehouse
    reco.insert()
    reco.add_comment(
        "Comment",
        _("Merged from shared count {0} ({1} devices). {2} items matched the shelf and were left out. {3}").format(
            doc.name, devices, unchanged, APP_MARKER
        ),
    )
    doc.db_set({"status": "Merged", "reconciliation": reco.name, "merged_on": now_datetime()})
    return {"reconciliation": reco.name, "rows": len(reco.get("items") or []), "devices": devices, "unchanged": unchanged}


@frappe.whitelist(methods=["POST"])
def count_session_close(session: str):
    """Close a shared count without making anything."""
    _shared_guard()
    doc = _count_session(session)
    doc.db_set("status", "Cancelled")
    return {"name": doc.name, "status": "Cancelled"}


# ----------------------------------------------- before a count is submitted --


def _unposted(reco):
    """The items of a stock count that POS sales not posted yet still hold in
    its warehouses: [{item_code, qty, warehouse, invoices}]. Submitting the
    count now would set them to the counted quantity, and closing the shift
    afterwards would take those sales off again."""
    pairs = {(r.get("item_code"), r.get("warehouse") or reco.get("set_warehouse")) for r in (reco.get("items") or [])}
    pairs = {p for p in pairs if p[0] and p[1]}
    if not pairs:
        return []
    codes = tuple(sorted({p[0] for p in pairs}))
    warehouses = tuple(sorted({p[1] for p in pairs}))
    found = frappe.db.sql(
        """
        select pii.item_code as item_code, pii.warehouse as warehouse, pi.name as invoice, pii.stock_qty as qty, pi.is_return as is_return
        from `tabPOS Invoice Item` pii
        inner join `tabPOS Invoice` pi on pi.name = pii.parent
        where pi.docstatus = 1 and ifnull(pi.consolidated_invoice, '') = ''
          and pii.item_code in %(codes)s and pii.warehouse in %(warehouses)s
        union all
        select pk.item_code as item_code, pk.warehouse as warehouse, pi.name as invoice, pk.qty as qty, pi.is_return as is_return
        from `tabPacked Item` pk
        inner join `tabPOS Invoice` pi on pi.name = pk.parent
        where pk.parenttype = 'POS Invoice' and pi.docstatus = 1 and ifnull(pi.consolidated_invoice, '') = ''
          and pk.item_code in %(codes)s and pk.warehouse in %(warehouses)s
        """,
        {"codes": codes, "warehouses": warehouses},
        as_dict=True,
    )
    out = {}
    for r in found:
        if (r.item_code, r.warehouse) not in pairs:
            continue
        line = out.setdefault((r.item_code, r.warehouse), {"item_code": r.item_code, "warehouse": r.warehouse, "qty": 0.0, "invoices": []})
        line["qty"] += flt(r.qty)
        if r.invoice not in line["invoices"]:
            line["invoices"].append(r.invoice)
    return sorted(out.values(), key=lambda x: (x["item_code"], x["warehouse"]))


def _counted_since(reconciliation, reco):
    """item_code: {qty, serials, since} for a count made with the app, or
    (None, {}) for one made in the desk. `since` is when it was counted: for a
    shared count the last sync of the phone that counted it (the earliest when
    several did), for a count saved from the app when the draft was made."""
    rows = reco.get("items") or []
    counted = {}
    session = frappe.db.get_value(SESSION_DT, {"reconciliation": reconciliation}, "name")
    if session:
        devices = frappe.get_all(DEVICE_DT, filters={"session": session}, fields=["data", "last_sync"])
        synced = [get_datetime(d.get("last_sync")) for d in devices if d.get("last_sync")]
        if not synced:
            return session, {}
        first = min(synced)
        for dev in devices:
            since = get_datetime(dev.get("last_sync")) if dev.get("last_sync") else first
            for code, value in _device_lines(dev.get("data")).items():
                line = counted.setdefault(code, {"qty": 0.0, "serials": set(), "since": since})
                serials = [x for x in ((value or {}).get("s") or []) if x]
                line["serials"].update(serials)
                line["qty"] += 0 if serials else flt((value or {}).get("q"))
                line["since"] = min(line["since"], since)
        for line in counted.values():
            if line["serials"]:
                line["qty"] = float(len(line["serials"]))
        for r in rows:
            # Set to zero by a full count: "counted" as nothing when the first phone synced.
            counted.setdefault(r.get("item_code"), {"qty": flt(r.get("qty")), "serials": set(), "since": first})
        return session, counted
    if frappe.db.exists(
        "Comment",
        {"reference_doctype": "Stock Reconciliation", "reference_name": reconciliation, "content": ["like", f"%{APP_MARKER}%"]},
    ):
        since = get_datetime(reco.creation)
        for r in rows:
            counted[r.get("item_code")] = {"qty": flt(r.get("qty")), "serials": set(), "since": since}
        return "app", counted
    return None, {}


@frappe.whitelist()
def stock_count_moved(reconciliation: str):
    """Before a stock count is submitted: the counted items that moved (a sale,
    a transfer, a receipt) after they were counted, since the count is posted
    when it is submitted and overwrites those movements; and, for any stock
    count, the items still held by POS sales not posted yet (`unposted`).

    Moved: counts made with the app only (the desk keeps no count time). One
    query on the warehouses' ledger, only when asked. Times are compared as
    datetimes (posting_time is a timedelta: as text 9:57 sorts after 10:03)."""
    empty = {"source": None, "items": [], "unposted": []}
    if not frappe.has_permission("Stock Reconciliation", "read", doc=reconciliation):
        frappe.throw(_("You're not allowed to see {0}.").format(reconciliation), frappe.PermissionError)
    reco = frappe.get_doc("Stock Reconciliation", reconciliation)
    if reco.docstatus != 0:
        return empty
    unposted = _unposted(reco)
    if not flags()["warn_moved"]:
        return {"source": None, "items": [], "unposted": unposted}
    rows = reco.get("items") or []
    warehouses = sorted(
        {r.get("warehouse") for r in rows if r.get("warehouse")} | ({reco.set_warehouse} if reco.get("set_warehouse") else set())
    )
    source, counted = _counted_since(reconciliation, reco)
    if not source or not counted or not warehouses:
        return {"source": source, "items": [], "unposted": unposted}
    in_reco = {r.get("item_code") for r in rows}
    codes = list(counted)
    earliest = min(c["since"] for c in counted.values())
    moved = {}
    for start in range(0, len(codes), 1000):
        for e in frappe.db.sql(
            """
            select item_code, actual_qty, voucher_type, voucher_no, timestamp(posting_date, posting_time) as moment
            from `tabStock Ledger Entry`
            where is_cancelled = 0 and warehouse in %(warehouses)s and item_code in %(codes)s
              and timestamp(posting_date, posting_time) > %(since)s
            order by moment asc, creation asc
            """,
            {"warehouses": tuple(warehouses), "codes": tuple(codes[start:start + 1000]), "since": earliest},
            as_dict=True,
        ):
            code = e.item_code
            when = get_datetime(e.moment)
            if e.voucher_no == reconciliation or when <= counted[code]["since"]:
                continue
            m = moved.setdefault(code, {"qty": 0.0, "vouchers": []})
            m["qty"] += flt(e.actual_qty)
            m["vouchers"].append({
                "voucher_type": e.voucher_type,
                "voucher_no": e.voucher_no,
                "qty": flt(e.actual_qty),
                "posting_datetime": when.strftime("%Y-%m-%d %H:%M"),
            })
    names = {}
    if moved:
        for it in frappe.get_all("Item", filters={"name": ["in", list(moved)]}, fields=["name", "item_name"]):
            names[it.get("name")] = it.get("item_name")
    items = [
        {
            "item_code": code,
            "item_name": names.get(code) or code,
            "counted": counted[code]["qty"],
            "counted_at": counted[code]["since"].strftime("%Y-%m-%d %H:%M"),
            "moved": m["qty"],
            "in_reconciliation": 1 if code in in_reco else 0,
            "vouchers": m["vouchers"][:5],
        }
        for code, m in moved.items()
    ]
    items.sort(key=lambda r: (r["item_name"] or "").lower())
    return {"source": source, "items": items, "unposted": unposted}


# ------------------------------------------------------------------ export --


def _xlsx_rows(data):
    """Header and rows of a shared count, the same columns as the app's export."""
    devices = data["devices"]
    show_system = not data["blind"]

    def label(dev):
        parts = [p for p in (dev.get("device_label"), dev.get("counted_by_name")) if p]
        return " - ".join(dict.fromkeys(parts)) or dev["device_id"]

    header = [_("Item Code"), _("Item Name")] + [label(d) for d in devices] + [_("Total")]
    if show_system:
        header += [_("System Qty"), _("Difference")]
    header.append(_("Serial Numbers"))
    rows = [header]
    for it in data["items"]:
        row = [it["item_code"], it["item_name"]] + [it["by_device"].get(d["device_id"]) for d in devices] + [it["total"]]
        if show_system:
            system = it["system_qty"] or 0
            row += [system, it["total"] - system]
        row.append(", ".join(it["serials"]))
        rows.append(row)
    return rows


@frappe.whitelist()
def count_session_export(session: str):
    """An Excel file of a shared count (the desk button): every item, each
    phone's quantity, the total, the quantity on the shelf and the difference."""
    if not flags()["export"]:
        frappe.throw(_("Export to Excel is turned off in LumenPOS Settings."), frappe.PermissionError)
    data = count_session_lines(session)
    from frappe.utils.xlsxutils import make_xlsx

    xlsx = make_xlsx(_xlsx_rows(data), session[:31])
    frappe.response["filename"] = f"{session}.xlsx"
    frappe.response["filecontent"] = xlsx.getvalue()
    frappe.response["type"] = "binary"


@frappe.whitelist(methods=["POST"])
def stock_link_barcode(item_code: str, barcode: str):
    """Add a barcode found on a box to the item's barcodes, so every phone and
    till knows it from then on. A barcode another item already has is refused."""
    _guard("Stock Reconciliation", need="link_barcode")
    barcode = (barcode or "").strip()
    if not barcode:
        frappe.throw(_("The barcode is empty."))
    if not item_code or not frappe.db.exists("Item", item_code):
        frappe.throw(_("Item {0} was not found.").format(item_code))
    if not frappe.has_permission("Item", "write", doc=item_code):
        frappe.throw(_("You're not allowed to change item {0}.").format(item_code), frappe.PermissionError)
    owner = frappe.db.get_value("Item Barcode", {"barcode": barcode}, "parent")
    if owner == item_code:
        return {"item_code": item_code, "barcode": barcode, "added": 0}
    if owner:
        frappe.throw(_("Barcode {0} already belongs to item {1}.").format(barcode, owner))
    item = frappe.get_doc("Item", item_code)
    item.append("barcodes", {"barcode": barcode})
    item.save()
    item.add_comment("Comment", _("Barcode {0} linked from the Lumen Stock app.").format(barcode))
    return {"item_code": item_code, "barcode": barcode, "added": 1}
