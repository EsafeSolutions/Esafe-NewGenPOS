"""Keep existing multi-computer tills working when the new switch is installed."""
import frappe


def execute():
    stored = frappe.db.sql(
        "select value from tabSingles where doctype=%s and field=%s",
        ("EsafePOS Settings", "shift_multiple_computers"),
    )
    if stored:
        return
    frappe.db.sql(
        "insert into tabSingles (doctype, field, value) values (%s, %s, %s)",
        ("EsafePOS Settings", "shift_multiple_computers", "1"),
    )
    frappe.clear_cache(doctype="EsafePOS Settings")
