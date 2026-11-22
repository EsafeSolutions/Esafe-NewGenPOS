"""Checkout credit endpoint authorization, runnable without a Frappe bench."""
import ast
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class CheckoutCreditTests(unittest.TestCase):
    def setUp(self):
        self.sales = ModuleType("esafepos.api.sales")
        self.sales._require_sell = Mock()
        self.walk_in = ModuleType("esafepos.walk_in")
        self.walk_in.billing_customer = Mock(return_value="NAMED")
        self.modules = patch.dict(sys.modules, {"esafepos.api.sales": self.sales, "esafepos.walk_in": self.walk_in})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.permissions = Mock(assert_outlet=Mock())
        self.frappe = Mock()
        self.frappe.get_cached_doc.return_value = SimpleNamespace(company="Shop")
        self.credit = Mock()
        tree = ast.parse(Path(__file__).with_name("credit.py").read_text(encoding="utf-8"))
        node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "checkout_credit")
        node.decorator_list = []
        namespace = dict(frappe=self.frappe, permissions=self.permissions, credit_sales=self.credit)
        exec(compile(ast.Module(body=[node], type_ignores=[]), "credit.py", "exec"), namespace)
        self.checkout = namespace["checkout_credit"]

    def test_facts_are_fresh_and_use_authorized_profile_company(self):
        self.credit.facts.return_value = dict(enabled=1, allowed=1, available=1000)
        self.assertEqual(self.checkout("Till", "NAMED")["available"], 1000)
        self.sales._require_sell.assert_called_once_with()
        self.permissions.assert_outlet.assert_called_once_with("Till")
        self.credit.facts.assert_called_once_with("NAMED", "Shop")

    def test_unauthorized_outlet_is_refused_before_customer_balance_lookup(self):
        self.permissions.assert_outlet.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            self.checkout("Other outlet", "NAMED")
        self.credit.facts.assert_not_called()
        self.frappe.get_cached_doc.assert_not_called()

    def test_disabled_credit_and_walk_in_refusal_are_returned(self):
        self.walk_in.billing_customer.return_value = "Walk-in"
        self.credit.facts.return_value = dict(enabled=0, allowed=0, reason="Sales on account are switched off.")
        self.assertEqual(self.checkout("Till")["allowed"], 0)
        self.credit.facts.assert_called_once_with("Walk-in", "Shop")


if __name__ == "__main__":
    unittest.main()
