"""Customer filters and price assignments, runnable without a Frappe bench.

The advanced filters execute their actual SQL against SQLite fixtures; document
services and Frappe permission conditions are injected at the API boundary.
"""
import ast
from datetime import date, timedelta
from pathlib import Path
import re
import sqlite3
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch


class Record(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__


def load_functions(path, namespace, names=None):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and (not names or node.name in names)]
    for node in selected:
        node.decorator_list = []
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)


class CustomerTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.PermissionError = PermissionError
        self.frappe.throw.side_effect = lambda message, kind=ValueError: self.reject(message, kind)
        self.permissions = ModuleType("esafepos.api.permissions")
        self.permissions.allowed_companies = Mock(return_value={"Shop"})
        self.permissions.assert_outlet = Mock()
        self.features = ModuleType("esafepos.features")
        self.features.enabled = Mock(return_value=True)
        db_query = ModuleType("frappe.model.db_query")
        self.match = Mock(conditions=[], build_match_conditions=Mock(return_value="`tabCustomer`.name != 'HIDDEN'"))
        db_query.DatabaseQuery = Mock(return_value=self.match)
        walk_in = ModuleType("esafepos.walk_in")
        walk_ns = {"frappe": self.frappe, "RECEIPT_CUSTOMER_FIELD": "esafepos_receipt_customer"}
        load_functions(Path(__file__).parents[1] / "walk_in.py", walk_ns, {"customer_attribution_sql"})
        walk_in.customer_attribution_sql = walk_ns["customer_attribution_sql"]
        self.frappe.db.has_column.return_value = True
        modules = patch.dict(sys.modules, {"esafepos.api.permissions": self.permissions,
                                          "esafepos.features": self.features,
                                          "frappe.model.db_query": db_query, "esafepos.walk_in": walk_in})
        modules.start()
        self.addCleanup(modules.stop)
        self.fields = ["name", "customer_name", "customer_group", "customer_type", "mobile_no", "email_id",
                       "tax_id", "default_currency", "default_price_list", "creation"]
        self.ns = {"frappe": self.frappe, "_": lambda value: value, "cint": lambda value=0: int(value or 0),
                   "flt": lambda value=0, precision=2: round(float(value or 0), precision),
                   "nowdate": lambda: "2026-11-25", "getdate": lambda value: date.fromisoformat(str(value)[:10]),
                   "add_days": lambda value, days: date.fromisoformat(str(value)[:10]) + timedelta(days=days),
                   "CUSTOMER_FIELDS": self.fields}
        load_functions(Path(__file__).with_name("customers.py"), self.ns)
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.db.execute("create table `tabCustomer` (" + ", ".join(field + " text" for field in self.fields) + ", disabled integer default 0)")
        for doctype in ("POS Invoice", "Sales Invoice"):
            self.db.execute("create table `tab" + doctype + "` (name text, customer text, company text, docstatus integer, "
                            "is_return integer, posting_date text, is_consolidated integer default 0, "
                            "esafepos_receipt_customer text, return_against text)")
        self.db.execute("create table `tabGL Entry` (party text, company text, party_type text, is_cancelled integer, debit real, credit real)")
        self.frappe.db.sql.side_effect = self.sql
        self.frappe.get_cached_value.return_value = "LKR"

    @staticmethod
    def reject(message, kind):
        raise kind(message)

    def sql(self, query, values, **kwargs):
        query = re.sub(r"%\((\w+)\)s", r":\1", query).replace("%%", "%")
        return [Record(row) for row in self.db.execute(query, values).fetchall()]

    def customer(self, name, created="2026-11-24 23:59:59", group="Individual"):
        self.db.execute("insert into `tabCustomer` (name, customer_name, creation, customer_group) values (?, ?, ?, ?)",
                        (name, name, created, group))

    def ledger(self, name, debit=100, credit=0, company="Shop", cancelled=0):
        self.db.execute("insert into `tabGL Entry` values (?, ?, 'Customer', ?, ?, ?)", (name, company, cancelled, debit, credit))

    def invoice(self, customer, doctype="POS Invoice", day="2026-11-25", returned=0, status=1,
                company="Shop", consolidated=0, linked=None):
        self.db.execute("insert into `tab" + doctype + "` values ('INV', ?, ?, ?, ?, ?, ?, ?, null)",
                        (customer, company, status, returned, day, consolidated, linked))

    def search(self, **kwargs):
        return self.ns["search_customers"](company="Shop", **kwargs)

    def test_owes_uses_net_company_ledger_and_filters_before_pagination(self):
        for number in range(36):
            name = "Customer {:02d}".format(number)
            self.customer(name)
            self.ledger(name)
        for name in ("Settled", "Advance", "Cancelled", "Other company", "Hold only", "HIDDEN"):
            self.customer(name)
        self.ledger("Settled", credit=100)
        self.ledger("Advance", credit=150)
        self.ledger("Cancelled", cancelled=1)
        self.ledger("Other company", company="Elsewhere")
        self.ledger("HIDDEN")
        page = self.search(still_owes=1, start=30, limit=5)
        self.assertEqual([row.name for row in page["items"]], ["Customer {:02d}".format(n) for n in range(30, 35)])
        self.assertTrue(page["has_more"])
        self.assertEqual(page["currency"], "LKR")
        self.assertEqual(page["items"][0].outstanding, 100)
        self.assertFalse(self.search(still_owes=1, start=35)["has_more"])

    def test_payment_and_fractional_balance_boundaries(self):
        for name, debit in (("Zero", 0), ("Tiny", 0.004), ("Cent", 0.01), ("Paid", 40)):
            self.customer(name)
            self.ledger(name, debit=debit)
        self.ledger("Paid", debit=0, credit=40)
        self.assertEqual([row.name for row in self.search(still_owes=1)["items"]], ["Cent"])

    def test_purchases_include_both_invoice_types_and_receipt_links_once(self):
        for name in ("POS", "Invoice", "Linked", "Walk-in", "Return", "Draft", "Cancelled", "Merged", "Other", "Yesterday"):
            self.customer(name)
        self.invoice("POS")
        self.invoice("POS")
        self.invoice("Invoice", doctype="Sales Invoice")
        self.invoice("Walk-in", linked="Linked")
        self.invoice("Return", returned=1)
        self.invoice("Draft", status=0)
        self.invoice("Cancelled", status=2)
        self.invoice("Merged", doctype="Sales Invoice", consolidated=1)
        self.invoice("Other", company="Elsewhere")
        self.invoice("Yesterday", day="2026-11-24")
        self.assertEqual([row.name for row in self.search(activity="purchased_today")["items"]], ["Invoice", "Linked", "POS"])
        self.assertEqual([row.name for row in self.search(activity="purchased_yesterday")["items"]], ["Yesterday"])

    def test_combined_group_text_creation_and_debt_filters(self):
        for name, created, group in (("New customer", "2026-11-24 23:59:59", "Retail"),
                                     ("Old customer", "2026-11-23 23:59:59", "Retail"),
                                     ("New group", "2026-11-24 10:00:00", "Other"),
                                     ("Today customer", "2026-11-25 00:00:00", "Retail")):
            self.customer(name, created, group)
            self.ledger(name)
        result = self.search(still_owes=1, activity="new_yesterday", search="customer", customer_group="Retail")
        self.assertEqual([row.name for row in result["items"]], ["New customer"])
        self.assertEqual(self.search(still_owes=1, search="' OR 1=1 --")["items"], [])

    def test_site_date_windows_cross_month_and_leap_day(self):
        self.ns["nowdate"] = lambda: "2024-03-01"
        self.assertEqual(self.ns["_activity_window"]("new_yesterday"), ("2024-02-29", "2024-03-01"))
        self.assertEqual(self.ns["_activity_window"]("new_week"), ("2024-02-24", "2024-03-02"))
        self.assertEqual(self.ns["_activity_window"]("purchased_date", "2026-01-31"), ("2026-01-31", "2026-02-01"))
        for activity in ("unknown", "purchased_date"):
            with self.assertRaises(ValueError):
                self.ns["_activity_window"](activity)

    def test_new_customers_use_permission_aware_half_open_creation_range(self):
        self.frappe.get_list.return_value = []
        self.search(activity="new_yesterday", start=-10, limit=10000)
        args = self.frappe.get_list.call_args.kwargs
        self.assertIn(["Customer", "creation", ">=", "2026-11-24"], args["filters"])
        self.assertIn(["Customer", "creation", "<", "2026-11-25"], args["filters"])
        self.assertEqual((args["limit_start"], args["limit_page_length"]), (0, 101))

    def test_customer_company_and_feature_permissions_apply_before_queries(self):
        self.frappe.has_permission.return_value = False
        with self.assertRaises(PermissionError):
            self.search(still_owes=1)
        self.frappe.has_permission.return_value = True
        self.features.enabled.return_value = False
        with self.assertRaises(PermissionError):
            self.search(still_owes=1)
        self.features.enabled.return_value = True
        with self.assertRaises(PermissionError):
            self.ns["search_customers"](company="Forbidden", activity="purchased_today")
        self.frappe.db.sql.assert_not_called()

    def test_shared_only_customer_permission_condition_is_preserved(self):
        self.customer("Visible")
        self.customer("Other")
        self.ledger("Visible")
        self.ledger("Other")
        self.match.conditions = ["`tabCustomer`.name = 'Visible'"]
        self.assertEqual([row.name for row in self.search(still_owes=1)["items"]], ["Visible"])

    def setup_price_list(self, **overrides):
        customer = Mock(default_currency=None)
        customer.name = "CUSTOMER"
        customer.get.side_effect = lambda key: {"default_currency": None}.get(key)
        selected = Record(enabled=1, selling=1, currency="LKR", **overrides)
        selected.check_permission = Mock()
        self.frappe.get_doc.side_effect = lambda doctype, name: customer if doctype == "Customer" else selected
        self.frappe.get_cached_doc.return_value = Record(selling_price_list="Retail")
        return customer, selected

    def test_assign_and_clear_native_customer_price_list(self):
        customer, _ = self.setup_price_list()
        result = self.ns["set_customer_price_list"]("CUSTOMER", "Till", "Wholesale")
        self.assertEqual(result["default_price_list"], "Wholesale")
        customer.check_permission.assert_any_call("write")
        customer.save.assert_called_once_with()
        self.frappe.clear_document_cache.assert_called_once_with("Customer", "CUSTOMER")
        result = self.ns["set_customer_price_list"]("CUSTOMER", "Till", "")
        self.assertIsNone(result["default_price_list"])

    def test_price_assignment_rejects_write_access_disabled_buying_and_currency(self):
        for field, value in (("enabled", 0), ("selling", 0), ("currency", "USD")):
            customer, selected = self.setup_price_list()
            selected[field] = value
            with self.assertRaises(ValueError):
                self.ns["set_customer_price_list"]("CUSTOMER", "Till", "Wrong")
            customer.save.assert_not_called()
        customer, _ = self.setup_price_list()
        customer.check_permission.side_effect = [None, PermissionError("No write access")]
        with self.assertRaises(PermissionError):
            self.ns["set_customer_price_list"]("CUSTOMER", "Till", "Wholesale")
        customer.save.assert_not_called()

    def test_price_list_options_follow_billing_currency(self):
        customer, _ = self.setup_price_list()
        customer.get.side_effect = lambda key: "USD" if key == "default_currency" else None
        self.ns["customer_price_lists"]("CUSTOMER", "Till")
        self.assertEqual(self.frappe.get_list.call_args.kwargs["filters"], {"enabled": 1, "selling": 1, "currency": "USD"})


class CustomerPricingTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.profile = Record(selling_price_list="Retail")
        self.row = Record(enabled=1, selling=1, currency="LKR")
        self.frappe.get_cached_value.side_effect = lambda dt, name, fields, **kw: (
            "Wholesale" if dt == "Customer" else self.row if isinstance(fields, list) else "LKR")
        self.ns = {"frappe": self.frappe, "cint": lambda value: int(value or 0)}
        load_functions(Path(__file__).parents[1] / "price_books.py", self.ns, {"resolve_price_list", "effective_prices"})
        self.prices = {"Retail": {"A": 100, "B": 200}, "Wholesale": {"A": 80}, "Delivery": {"A": 120}}
        self.ns["get_price_map"] = lambda codes, name, *args: {code: rate for code, rate in self.prices[name].items() if code in codes}
        self.ns["book_overrides"] = Mock(return_value={"A": 90})

    def test_customer_list_overrides_books_and_missing_prices_use_outlet(self):
        prices = self.ns["effective_prices"](self.profile, ["A", "B"], customer="CUST")
        self.assertEqual(prices, {"A": 80, "B": 200})
        self.ns["book_overrides"].assert_not_called()
        self.assertEqual(self.ns["resolve_price_list"](self.profile, customer="CUST"), "Wholesale")

    def test_delivery_app_takes_priority_and_clearing_customer_restores_books(self):
        self.assertEqual(self.ns["effective_prices"](self.profile, ["A", "B"], app_price_list="Delivery", customer="CUST"), {"A": 120, "B": 200})
        self.assertEqual(self.ns["effective_prices"](self.profile, ["A", "B"]), {"A": 90, "B": 200})

    def test_disabled_buying_or_foreign_list_does_not_change_outlet_currency(self):
        for field, value in (("enabled", "0"), ("selling", 0), ("currency", "USD")):
            original = self.row[field]
            self.row[field] = value
            self.assertEqual(self.ns["resolve_price_list"](self.profile, customer="CUST"), "Retail")
            self.row[field] = original


if __name__ == "__main__":
    unittest.main()
