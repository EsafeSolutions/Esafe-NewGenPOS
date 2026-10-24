# Copyright (c) 2026 Lumen Solutions
# SPDX-License-Identifier: AGPL-3.0-only
# "LumenPOS" is a trademark of Lumen Solutions. See TRADEMARKS.md.
"""Outlets and their registers (0.64.0).

A POS Profile is a REGISTER: one till, with its own shift and drawer. ERPNext 16
holds one open shift per POS Profile (POS Opening Entry.check_open_pos_exists),
so a shop where each cashier counts their own drawer has a register per
cashier. An OUTLET is the shop those registers stand in, the way Vend,
Lightspeed and Shopify POS group registers under an outlet.

The Zimbabwe shop (Phillip, 2026-10-23): three cashiers, each on their own POS
Profile, all selling from one warehouse, showed as three outlets. The owner
asked for the best practice for every shop, not for one, so:

- Registers that sell from the same WAREHOUSE are one outlet, with nothing to
  set up: the warehouse is where ERPNext keeps a shop's stock.
- POS Profile.lumenpos_outlet names the outlet a register belongs to, for the
  rare shop that splits one warehouse between outlets (or spreads one outlet
  over warehouses). Registers carrying the same name are one outlet, whatever
  their warehouse.
- An outlet's name is that field, else the register's own name when it stands
  alone, else its warehouse without the company abbreviation.

Outlets never cross companies: a key carries its company."""

import frappe

FIELD = "lumenpos_outlet"


def _has_field():
    try:
        return frappe.get_meta("POS Profile").has_field(FIELD)
    except Exception:
        return False


def _short(warehouse, company):
    """"Stores - FB" reads "Stores": the company's abbreviation is noise here."""
    abbr = frappe.get_cached_value("Company", company, "abbr") if company else None
    suffix = " - " + abbr if abbr else None
    if suffix and warehouse.endswith(suffix):
        return warehouse[: -len(suffix)]
    return warehouse


def groups(profiles=None, company=None):
    """The outlets of these registers (all enabled ones when None), each
    {outlet: key, name, company, registers: [POS Profile], warehouses: [...]},
    by name. A disabled register is left out."""
    filters = {"disabled": 0}
    if company:
        filters["company"] = company
    if profiles is not None:
        filters["name"] = ["in", list(profiles) or [""]]
    fields = ["name", "warehouse", "company"] + ([FIELD] if _has_field() else [])
    by = {}
    for row in frappe.get_all("POS Profile", filters=filters, fields=fields, order_by="name asc"):
        named = (row.get(FIELD) or "").strip()
        if named:
            key, name = "%s::outlet::%s" % (row.company, named.casefold()), named
        elif row.warehouse:
            key, name = "%s::warehouse::%s" % (row.company, row.warehouse), None
        else:
            key, name = "%s::register::%s" % (row.company, row.name), row.name
        group = by.setdefault(key, {"outlet": key, "name": name, "company": row.company, "registers": [], "warehouses": []})
        group["registers"].append(row.name)
        if row.warehouse and row.warehouse not in group["warehouses"]:
            group["warehouses"].append(row.warehouse)
    for group in by.values():
        if not group["name"]:
            alone = len(group["registers"]) == 1
            group["name"] = group["registers"][0] if alone else _short(group["warehouses"][0], group["company"])
    return sorted(by.values(), key=lambda g: (g["name"].casefold(), g["outlet"]))


def registers_of(outlet, company=None):
    """The registers of one outlet (by its key), or None when no outlet has
    that key."""
    for group in groups(company=company):
        if group["outlet"] == outlet:
            return group["registers"]
    return None


def outlet_of(pos_profile):
    """The outlet a register stands in, or None for a disabled or unknown one."""
    company = frappe.get_cached_value("POS Profile", pos_profile, "company")
    for group in groups(company=company):
        if pos_profile in group["registers"]:
            return group
    return None


def for_registers(registers):
    """The outlets these registers stand in, named as for everyone (the outlet
    of three registers keeps its warehouse name for a cashier who works at only
    one of them), each listing only these registers. For the till."""
    mine = set(registers or [])
    out = []
    for group in groups():
        shown = [r for r in group["registers"] if r in mine]
        if shown:
            out.append({**group, "registers": shown, "size": len(group["registers"])})
    return out
