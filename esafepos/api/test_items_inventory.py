"""Inventory API boundary tests runnable without a Frappe bench.

Execute the actual endpoint bodies with mocked document and database services.
"""
import ast
import json
import math
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.PermissionError = PermissionError
        self.frappe.throw.side_effect = lambda message, kind=ValueError: self.fail_request(message, kind)
        self.frappe.whitelist.side_effect = lambda **kw: lambda fn: fn
        self.profile = SimpleNamespace(company="Shop", name="Till")
        self.item = Mock(disabled=0, is_stock_item=1, has_variants=0, has_serial_no=0, has_batch_no=0)
        self.doc = Mock(doctype="Stock Reconciliation")
        self.doc.name = "REC-1"
        self.frappe.get_doc.return_value = self.doc
        self.frappe.db.sql.return_value = [(10,)]
        self.frappe.db.get_value.return_value = None
        self.stock_app = ModuleType("esafepos.api.stock_app")
        self.stock_app._has_workflow = Mock(return_value=False)
        self.stock_app._unposted = Mock(return_value=[])
        self.stock_app._refuse_unposted = Mock()
        self.audit = ModuleType("esafepos.api.audit")
        self.audit.log = Mock()
        self.modules = patch.dict(sys.modules, {"esafepos.api.stock_app": self.stock_app,
                                                "esafepos.api.audit": self.audit})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.ns = {"frappe": self.frappe, "_": lambda value: value, "math": math, "json": json, "flt": float, "cint": int,
                   "_profile": Mock(return_value=self.profile), "_can_adjust_stock": Mock(return_value=True),
                   "_can_create": Mock(return_value=True), "_stock_item": Mock(return_value=self.item),
                   "_warehouses": Mock(return_value=["Shelf"])}
        names = {"_require", "_number", "_json_list", "_clean_selling_units", "_clean_barcodes", "_save_prices", "adjust_stock", "create_item"}
        tree = ast.parse(Path(__file__).with_name("items.py").read_text(encoding="utf-8"))
        selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        exec(compile(ast.Module(body=selected, type_ignores=[]), "items.py", "exec"), self.ns)

    @staticmethod
    def fail_request(message, kind):
        raise kind(message)

    def adjust(self, **overrides):
        args = dict(pos_profile="Till", item_code="ITEM", warehouse="Shelf", qty=12,
                    expected_qty=10, reason="Shelf count")
        args.update(overrides)
        return self.ns["adjust_stock"](**args)

    def test_stock_permission_denied_before_read_or_write(self):
        self.ns["_can_adjust_stock"].return_value = False
        with self.assertRaises(PermissionError):
            self.adjust()
        self.ns["_stock_item"].assert_not_called()
        self.doc.insert.assert_not_called()

    def test_cross_company_or_inaccessible_warehouse_rejected(self):
        with self.assertRaises(PermissionError):
            self.adjust(warehouse="Other company")
        self.doc.insert.assert_not_called()

    def test_serial_and_batch_items_require_full_workflow(self):
        for field in ("has_serial_no", "has_batch_no"):
            setattr(self.item, field, 1)
            with self.assertRaises(ValueError):
                self.adjust()
            setattr(self.item, field, 0)
        self.doc.insert.assert_not_called()

    def test_invalid_quantities_and_missing_reason_rejected(self):
        for value in ("", None, "abc", "nan", "inf", -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.adjust(qty=value)
        with self.assertRaises(ValueError):
            self.adjust(reason=" ")
        self.doc.insert.assert_not_called()

    def test_stale_and_unchanged_counts_rejected(self):
        for values in ({"expected_qty": 9}, {"qty": 10}):
            with self.assertRaises(ValueError):
                self.adjust(**values)
        self.doc.insert.assert_not_called()

    def test_approval_workflow_cannot_be_bypassed(self):
        self.stock_app._has_workflow.return_value = True
        with self.assertRaises(ValueError):
            self.adjust()
        self.doc.insert.assert_not_called()

    def test_unposted_sales_block_reconciliation(self):
        self.stock_app._refuse_unposted.side_effect = ValueError("Close shifts")
        with self.assertRaises(ValueError):
            self.adjust()
        self.doc.insert.assert_not_called()

    def test_native_submit_permission_required(self):
        self.doc.check_permission.side_effect = [None, PermissionError]
        with self.assertRaises(PermissionError):
            self.adjust()
        self.doc.insert.assert_not_called()

    def test_success_submits_native_document_and_audits_reason(self):
        self.assertEqual(self.adjust(valuation_rate=25), {"name": "REC-1"})
        self.doc.check_permission.assert_any_call("submit")
        self.doc.insert.assert_called_once()
        self.doc.submit.assert_called_once()
        self.doc.add_comment.assert_called_once_with("Comment", "Shelf count")
        self.audit.log.assert_called_once()
        data = self.frappe.get_doc.call_args_list[-1].args[0]
        self.assertEqual(data["items"], [{"item_code": "ITEM", "warehouse": "Shelf", "qty": 12, "valuation_rate": 25}])

    def test_negative_existing_stock_can_be_corrected_to_zero(self):
        self.frappe.db.sql.return_value = [(-2,)]
        self.adjust(expected_qty=-2, qty=0)
        self.doc.submit.assert_called_once()

    def test_create_requires_separate_pos_permission(self):
        self.ns["_can_create"].return_value = False
        with self.assertRaises(PermissionError):
            self.ns["create_item"]("Till", "NEW", "New item", "Goods", "Nos")
        self.frappe.get_doc.assert_not_called()

    def test_create_checks_native_permission_and_linked_records(self):
        linked = Mock(is_group=0)
        self.frappe.get_doc.side_effect = [linked, linked, self.doc]
        result = self.ns["create_item"]("Till", "NEW", "New item", "Goods", "Nos", barcode="123")
        self.assertEqual(result, {"item_code": "REC-1"})
        linked.check_permission.assert_called_with("read")
        self.doc.check_permission.assert_called_once_with("create")
        self.doc.insert.assert_called_once()
        data = self.frappe.get_doc.call_args.args[0]
        self.assertEqual(data["is_purchase_item"], 1)
        self.assertEqual(data["is_stock_item"], 1)

    def prepare_item_price(self):
        linked = Mock(is_group=0)
        self.frappe.get_doc.side_effect = [linked, linked, self.doc]
        price_doc = Mock(price_list="Standard Selling", uom="Kg")
        self.ns.update({"_can_edit_prices": Mock(return_value=True),
                        "_selling_list": Mock(return_value=SimpleNamespace(name="Standard Selling")),
                        "_standing_price": Mock(return_value=None),
                        "_item_price_doc": Mock(return_value=price_doc)})
        return price_doc

    def test_create_saves_separate_standard_selling_price_in_stock_unit(self):
        price_doc = self.prepare_item_price()
        self.ns["create_item"]("Till", "NEW", "New item", "Goods", "Kg",
                               prices='[{"uom":"Kg","price":175.5}]', price_list="Standard Selling")
        self.ns["_selling_list"].assert_called_once_with(self.profile, "Standard Selling")
        self.ns["_item_price_doc"].assert_called_once_with(None, "REC-1", "Standard Selling", "Kg")
        price_doc.check_permission.assert_called_once_with("create")
        self.assertEqual(price_doc.price_list_rate, 175.5)
        price_doc.save.assert_called_once()

    def test_create_rejects_selling_price_without_pos_price_capability(self):
        price_doc = self.prepare_item_price()
        self.ns["_can_edit_prices"].return_value = False
        with self.assertRaises(PermissionError):
            self.ns["create_item"]("Till", "NEW", "New item", "Goods", "Kg",
                                   prices=[{"uom": "Kg", "price": 175.5}], price_list="Standard Selling")
        self.doc.insert.assert_not_called()
        price_doc.save.assert_not_called()

    def test_create_selling_price_requires_native_item_price_create_permission(self):
        price_doc = self.prepare_item_price()
        price_doc.check_permission.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            self.ns["create_item"]("Till", "NEW", "New item", "Goods", "Kg",
                                   prices=[{"uom": "Kg", "price": 175.5}], price_list="Standard Selling")
        price_doc.save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
