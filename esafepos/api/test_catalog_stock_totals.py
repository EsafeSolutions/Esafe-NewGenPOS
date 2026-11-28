"""POS display totals and scope boundaries, runnable without a Frappe bench."""
import ast
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class CatalogStockTotalsTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.PermissionError = PermissionError
        self.frappe.throw.side_effect = lambda message, kind=ValueError: self.raise_error(message, kind)
        self.frappe.has_permission.return_value = True
        self.profile = SimpleNamespace(name="Till", company="Shop", warehouse="Shelf")
        self.rules = []
        self.features = ModuleType("esafepos.features")
        self.features.enabled = Mock(return_value=True)
        self.permissions = ModuleType("esafepos.api.permissions")
        self.permissions.assert_outlet = Mock()
        native = ModuleType("frappe.core.doctype.user_permission.user_permission")
        native.get_user_permissions = lambda: {"Warehouse": self.rules}
        self.modules = patch.dict(sys.modules, {"esafepos.features": self.features,
                                                "esafepos.api.permissions": self.permissions,
                                                "frappe.core.doctype.user_permission.user_permission": native})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.held = {"Shelf": {"ITEM": 2}, "Stores": {"ITEM": -0.5}}
        self.ns = {"frappe": self.frappe, "_": lambda text: text,
                   "flt": lambda n, precision=None: round(float(n or 0), precision) if precision is not None else float(n or 0),
                   "pos_reserved_map": lambda name: self.held.get(name, {})}
        tree = ast.parse(Path(__file__).with_name("catalog.py").read_text(encoding="utf-8"))
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_total_stock_quantities"]
        exec(compile(ast.Module(body=functions, type_ignores=[]), "catalog.py", "exec"), self.ns)
        self.frappe.get_all.side_effect = lambda doctype, **kwargs: ["Shelf", "Stores"] if doctype == "Warehouse" else [SimpleNamespace(item_code="ITEM", actual_qty=30.25)]

    @staticmethod
    def raise_error(message, kind):
        raise kind(message)

    def total(self):
        return self.ns["_total_stock_quantities"](self.profile, ["ITEM", "MISSING"])

    def test_off_avoids_stock_queries(self):
        self.features.enabled.return_value = False
        self.assertEqual(self.total(), (None, False))
        self.frappe.get_all.assert_not_called()

    def test_total_uses_company_scope_and_pending_pos_sales_and_returns(self):
        self.assertEqual(self.total(), ({"ITEM": 28.75, "MISSING": 0}, True))
        self.permissions.assert_outlet.assert_called_once_with("Till")
        self.assertEqual(self.frappe.get_all.call_args_list[0].kwargs["filters"]["company"], "Shop")
        self.assertEqual(self.frappe.get_all.call_args.kwargs["filters"]["warehouse"], ["in", ["Shelf", "Stores"]])
        self.assertEqual(self.frappe.get_all.call_args.kwargs["limit_page_length"], 0)

    def test_warehouse_permissions_limit_the_aggregate(self):
        self.rules = [{"doc": "Stores", "applicable_for": "POS Invoice"}]
        self.total()
        self.assertEqual(self.frappe.get_all.call_args.kwargs["filters"]["warehouse"], ["in", ["Stores"]])
        self.assertFalse(self.total()[1])

    def test_rules_for_other_documents_do_not_restrict_pos_stock(self):
        self.rules = [{"doc": "Other", "applicable_for": "Purchase Order"}]
        self.assertTrue(self.total()[1])

    def test_no_permitted_warehouses_returns_zero_without_bin_query(self):
        self.rules = [{"doc": "Other company", "applicable_for": None}]
        self.assertEqual(self.total(), ({"ITEM": 0, "MISSING": 0}, False))
        self.assertEqual(self.frappe.get_all.call_count, 1)

    def test_missing_item_or_outlet_permission_denies_before_queries(self):
        self.frappe.has_permission.return_value = False
        with self.assertRaises(PermissionError):
            self.total()
        self.frappe.get_all.assert_not_called()
        self.frappe.has_permission.return_value = True
        self.permissions.assert_outlet.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            self.total()
        self.frappe.get_all.assert_not_called()


class FeatureConfigTests(unittest.TestCase):
    def setUp(self):
        fake = ModuleType("frappe")
        fake._ = lambda text: text
        fake.get_installed_apps = lambda: []
        utils = ModuleType("frappe.utils")
        utils.cint = lambda value: int(value or 0)
        modules = patch.dict(sys.modules, {"frappe": fake, "frappe.utils": utils})
        modules.start()
        self.addCleanup(modules.stop)
        spec = importlib.util.spec_from_file_location("stock_total_feature_rules", Path(__file__).parents[1] / "features.py")
        self.features = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.features)
        self.values = {}
        self.doc = SimpleNamespace(get=self.values.get, set=self.values.__setitem__)

    def test_missing_setting_defaults_off(self):
        self.assertEqual(self.features.client_facts(self.doc)["enable_item_stock_totals"], 0)

    def test_explicit_on_off_and_old_payload_preserve_choice(self):
        for value in (1, 0):
            self.features.save(self.doc, {"enable_item_stock_totals": value})
            self.assertEqual(self.features.client_facts(self.doc)["enable_item_stock_totals"], value)
            self.features.save(self.doc, {})
            self.assertEqual(self.values["enable_item_stock_totals"], value)


if __name__ == "__main__":
    unittest.main()
