"""Register admission and linked-close boundaries without a Frappe bench."""
import ast
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch


class RegisterClosingTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe._ = lambda value: value
        self.frappe.throw.side_effect = ValueError("blocked")
        self.frappe.db.get_value.return_value = None
        self.session = ModuleType("esafepos.api.session")
        self.session.shift_scope = Mock(return_value="Per cashier")
        self.permissions = ModuleType("esafepos.api.permissions")
        self.permissions.assert_outlet = Mock()
        self.patch = patch.dict(sys.modules, {"frappe": self.frappe, "esafepos.api.session": self.session,
                                              "esafepos.api.permissions": self.permissions})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        import esafepos.api
        self.attrs = patch.object(esafepos.api, "permissions", self.permissions, create=True)
        self.attrs.start()
        self.addCleanup(self.attrs.stop)

    def function(self, path, name):
        tree = ast.parse((Path(__file__).parent / path).read_text(encoding="utf-8"))
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
        node.decorator_list = []
        namespace = {"frappe": self.frappe, "_": lambda value: value}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
        return namespace[name]

    def test_per_cashier_admission_does_not_block_a_colleagues_shift(self):
        validate = self.function("esafepos/doctype/pos_register_session/pos_register_session.py", "validate")
        doc = Mock(status="Open", opened_by="cashier-A", pos_profile="Till")
        validate(doc)
        self.assertEqual(self.frappe.db.get_value.call_args.args[1]["opened_by"], "cashier-A")

    def test_per_outlet_admission_keeps_the_single_shift_guard(self):
        self.session.shift_scope.return_value = "Per outlet"
        validate = self.function("esafepos/doctype/pos_register_session/pos_register_session.py", "validate")
        validate(Mock(status="Open", opened_by="cashier-A", pos_profile="Till"))
        self.assertNotIn("opened_by", self.frappe.db.get_value.call_args.args[1])

    def test_individual_close_cannot_bypass_combined_reconciliation(self):
        close = self.function("api/register.py", "close_register")
        doc = Mock(pos_profile="Till")
        doc.get.return_value = "GROUP"
        self.frappe.get_doc.return_value = doc
        with self.assertRaises(ValueError): close("SHIFT", {"Cash": 100})
        self.assertIn("Close all linked shifts", self.frappe.throw.call_args.args[0])
        self.frappe.db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
