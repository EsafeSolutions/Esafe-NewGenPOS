"""Stock manager boundaries, executable without a live Frappe bench."""
import ast
import hashlib
import json
import math
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


def load_functions(filename, names, namespace):
    tree = ast.parse(Path(__file__).with_name(filename).read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    exec(compile(ast.Module(body=functions, type_ignores=[]), filename, "exec"), namespace)


class StockManagerTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.PermissionError = PermissionError
        self.frappe.throw.side_effect = lambda message, kind=ValueError: self.raise_error(message, kind)
        self.frappe.whitelist.side_effect = lambda **kwargs: lambda fn: fn
        self.frappe._dict.side_effect = lambda **kwargs: SimpleNamespace(**kwargs)
        self.frappe.session.user = "manager@example.com"
        self.frappe.db.exists.return_value = False
        self.frappe.db.get_value.return_value = None
        self.frappe.get_cached_value.return_value = 0
        self.frappe.db.sql.side_effect = lambda sql, args, **kwargs: [(10, 2)] if "tabBin" in sql else []
        self.profile = SimpleNamespace(name="Till", company="Shop")
        self.item = Mock(disabled=0, is_stock_item=1, has_variants=0, has_serial_no=0, has_batch_no=0, stock_uom="Nos")
        self.item.name = "ITEM"
        self.item.get.side_effect = {"disabled": 0, "item_group": "Goods", "brand": "", "description": ""}.get
        self.doc = Mock(company="Shop", docstatus=1)
        self.doc.name = "TRF-1"
        self.previous = None
        def get_doc(doctype, name=None, **kwargs):
            if isinstance(doctype, dict):
                self.document_data = doctype
                self.doc.remarks = doctype.get("remarks")
                return self.doc
            if doctype == "Item":
                return self.item
            if doctype == "Stock Entry":
                return self.previous
            return Mock(is_group=0)
        self.frappe.get_doc.side_effect = get_doc
        self.stock = ModuleType("esafepos.api.stock_app")
        self.stock._has_workflow = Mock(return_value=False)
        self.stock._unposted = Mock(return_value=[])
        self.stock._refuse_unposted = Mock()
        self.audit = ModuleType("esafepos.api.audit")
        self.audit.log = Mock()
        self.modules = patch.dict(sys.modules, {"esafepos.api.stock_app": self.stock, "esafepos.api.audit": self.audit})
        self.modules.start(); self.addCleanup(self.modules.stop)
        self.ns = {"frappe": self.frappe, "_": lambda value: value, "math": math, "hashlib": hashlib,
                   "json": json, "cint": int, "flt": lambda value: float(value or 0), "getdate": lambda value: value,
                   "_profile": Mock(return_value=self.profile), "_can_transfer_stock": Mock(return_value=True),
                   "_can_view_stock": Mock(return_value=True), "_warehouses": Mock(return_value=["Shelf", "Stores"])}
        load_functions("items.py", {"_require", "_number", "_json_list", "_stock_item", "transfer_stock", "_update_metadata", "stock_movements", "search_items"}, self.ns)

    @staticmethod
    def raise_error(message, kind):
        raise kind(message)

    def transfer(self, **kwargs):
        args = dict(pos_profile="Till", item_code="ITEM", source_warehouse="Shelf", target_warehouse="Stores",
                    qty=3, expected_qty=10, reason="Restock showroom", request_id="request-1")
        args.update(kwargs)
        return self.ns["transfer_stock"](**args)

    def test_transfer_requires_separate_pos_capability(self):
        self.ns["_can_transfer_stock"].return_value = False
        with self.assertRaises(PermissionError): self.transfer()
        self.frappe.get_doc.assert_not_called()

    def test_transfer_checks_both_warehouses(self):
        for field in ("source_warehouse", "target_warehouse"):
            with self.subTest(field=field), self.assertRaises(PermissionError): self.transfer(**{field: "Other company"})
        self.doc.insert.assert_not_called()

    def test_same_warehouse_rejected(self):
        with self.assertRaises(ValueError): self.transfer(target_warehouse="Shelf")
        self.doc.insert.assert_not_called()

    def test_invalid_and_nonfinite_quantities_rejected(self):
        for value in (0, -1, "nan", "inf", None, "abc"):
            with self.subTest(value=value), self.assertRaises(ValueError): self.transfer(qty=value)
        self.doc.insert.assert_not_called()

    def test_reason_and_request_identity_required(self):
        for args in ({"reason": " "}, {"request_id": ""}, {"reason": "x" * 501}):
            with self.subTest(args=args), self.assertRaises(ValueError): self.transfer(**args)
        self.doc.submit.assert_not_called()

    def test_disabled_template_and_service_cannot_transfer(self):
        for field, value in (("disabled", 1), ("has_variants", 1), ("is_stock_item", 0)):
            previous = getattr(self.item, field); setattr(self.item, field, value)
            with self.subTest(field=field), self.assertRaises(ValueError): self.transfer()
            setattr(self.item, field, previous)
        self.doc.insert.assert_not_called()

    def test_stale_stock_and_reservations_rejected(self):
        for args in ({"expected_qty": 9}, {"qty": 9}):
            with self.subTest(args=args), self.assertRaises(ValueError): self.transfer(**args)
        self.doc.submit.assert_not_called()

    def test_whole_stock_unit_required(self):
        self.frappe.get_cached_value.return_value = 1
        with self.assertRaises(ValueError): self.transfer(qty=1.5)

    def test_approval_workflow_is_respected(self):
        self.stock._has_workflow.return_value = True
        with self.assertRaises(ValueError): self.transfer()
        self.doc.insert.assert_not_called()

    def test_unposted_sales_block_transfer(self):
        self.stock._refuse_unposted.side_effect = ValueError("Close shift")
        with self.assertRaises(ValueError): self.transfer()
        self.doc.insert.assert_not_called()

    def test_native_submit_permission_cannot_be_bypassed(self):
        self.doc.check_permission.side_effect = [None, PermissionError]
        with self.assertRaises(PermissionError): self.transfer()
        self.doc.insert.assert_not_called()

    def test_native_transfer_is_submitted_and_audited(self):
        self.assertEqual(self.transfer(), {"name": "TRF-1", "replayed": False})
        self.assertEqual(self.document_data["stock_entry_type"], "Material Transfer")
        self.assertEqual(self.document_data["items"][0]["qty"], 3)
        self.assertEqual(self.document_data["items"][0]["t_warehouse"], "Stores")
        self.assertTrue(self.doc.insert.call_args.kwargs["set_name"].startswith("POS-TRF-"))
        self.doc.submit.assert_called_once(); self.audit.log.assert_called_once()

    def test_retry_returns_previous_document_even_if_stock_changed(self):
        self.transfer()
        self.previous = self.doc
        self.frappe.db.get_value.return_value = "TRF-1"
        self.assertTrue(self.transfer(expected_qty=1)["replayed"])
        self.assertTrue(self.frappe.db.get_value.call_args.kwargs["for_update"])
        self.doc.insert.assert_called_once(); self.doc.submit.assert_called_once()

    def test_retry_rejects_changed_details_and_cancelled_documents(self):
        self.transfer(); self.previous = self.doc; self.frappe.db.get_value.return_value = "TRF-1"
        with self.assertRaises(ValueError): self.transfer(qty=4)
        self.doc.docstatus = 2
        with self.assertRaises(ValueError): self.transfer()
        self.doc.submit.assert_called_once()

    def test_serials_must_match_quantity_and_be_unique(self):
        self.item.has_serial_no = 1
        for serials in ("", "S1\nS1\nS2", "S1\nS2"):
            with self.subTest(serials=serials), self.assertRaises(ValueError): self.transfer(serial_no=serials)
        self.transfer(serial_no="S1\nS2\nS3")
        self.assertEqual(self.document_data["items"][0]["serial_no"], "S1\nS2\nS3")

    def test_batch_required_and_native_tracking_fields_used(self):
        self.item.has_batch_no = 1
        with self.assertRaises(ValueError): self.transfer()
        self.transfer(batch_no="BATCH-1")
        self.assertEqual(self.document_data["items"][0]["batch_no"], "BATCH-1")
        self.assertEqual(self.document_data["items"][0]["use_serial_batch_fields"], 1)

    def test_untracked_item_rejects_tracking_details(self):
        with self.assertRaises(ValueError): self.transfer(serial_no="S1")
        with self.assertRaises(ValueError): self.transfer(batch_no="B1")

    def test_disabled_stock_can_be_read_for_inventory(self):
        self.item.disabled = 1
        self.assertIs(self.ns["_stock_item"]("ITEM", allow_disabled=True), self.item)
        with self.assertRaises(ValueError): self.ns["_stock_item"]("ITEM")

    def metadata(self, **kwargs):
        values = {key: None for key in ("disabled", "item_group", "brand", "description", "is_sales_item", "is_purchase_item")}
        values.update(kwargs)
        return self.ns["_update_metadata"](self.item, **values)

    def test_disabling_and_reenabling_need_native_item_write(self):
        for disabled in (0, 1):
            self.metadata(disabled=disabled)
            self.item.check_permission.assert_called_with("write")
        self.item.check_permission.side_effect = PermissionError
        with self.assertRaises(PermissionError): self.metadata(disabled=1)

    def test_metadata_validates_flags_links_and_description_length(self):
        for args in ({"disabled": "yes"}, {"item_group": ""}, {"description": "x" * 10001}):
            with self.subTest(args=args), self.assertRaises(ValueError): self.metadata(**args)
        self.item.update.assert_not_called()

    def test_stock_movements_are_company_and_warehouse_scoped(self):
        self.ns["stock_movements"]("Till", "ITEM", warehouse="Shelf", from_date="2026-01-01", to_date="2026-01-31")
        filters = self.frappe.get_list.call_args.kwargs["filters"]
        self.assertEqual(filters["company"], "Shop"); self.assertEqual(filters["warehouse"], ["in", ["Shelf"]])
        self.assertEqual(filters["posting_date"], ["between", ["2026-01-01", "2026-01-31"]])

    def test_stock_movements_reject_inaccessible_warehouse_and_dates(self):
        with self.assertRaises(PermissionError): self.ns["stock_movements"]("Till", "ITEM", warehouse="Other")
        with self.assertRaises(ValueError): self.ns["stock_movements"]("Till", "ITEM", from_date="2026-12-01", to_date="2026-01-01")

    def test_item_search_can_find_disabled_items_and_templates(self):
        catalog = ModuleType("esafepos.api.catalog")
        catalog.item_groups_under = Mock(return_value=[])
        self.frappe.db.get_value.return_value = None
        self.frappe.get_list.return_value = []
        with patch.dict(sys.modules, {"esafepos.api.catalog": catalog}):
            for status, expected in (("active", 0), ("disabled", 1), ("all", None)):
                self.ns["search_items"]("Till", "", status=status, item_type="template")
                filters = self.frappe.get_list.call_args.kwargs["filters"]
                self.assertEqual(filters.get("disabled"), expected)
                self.assertEqual(filters["has_variants"], 1)

    def test_inventory_summary_keeps_pending_return_availability(self):
        class Row(dict):
            __getattr__ = dict.get
        catalog = ModuleType("esafepos.api.catalog")
        catalog.item_groups_under = Mock(return_value=[])
        catalog.pos_reserved_map = lambda warehouse: {"ITEM": -2} if warehouse == "Shelf" else {}
        self.frappe.get_list.side_effect = [[Row(name="ITEM", is_stock_item=1, has_variants=0)],
                                          [SimpleNamespace(item_code="ITEM", actual_qty=10, reserved_qty=2)]]
        with patch.dict(sys.modules, {"esafepos.api.catalog": catalog}):
            result = self.ns["search_items"]("Till", "", include_stock=1)
        self.assertEqual(result[0]["actual_qty"], 10)
        self.assertEqual(result[0]["reserved_qty"], 2)
        self.assertEqual(result[0]["available_qty"], 10)

    def test_reenable_item_through_save_endpoint(self):
        load_functions("items.py", {"save_item"}, self.ns)
        self.item.disabled = 1; self.item.item_name = "Bouquet"
        self.item.get.side_effect = {"disabled": 1}.get
        self.item.update.side_effect = lambda values: [setattr(self.item, key, value) for key, value in values.items()]
        self.ns["item_details"] = Mock(return_value={"disabled": False})
        result = self.ns["save_item"]("Till", "ITEM", disabled=0)
        self.assertFalse(result["disabled"]); self.assertEqual(self.item.disabled, 0)
        self.item.save.assert_called_once(); self.item.check_permission.assert_any_call("write")

    def test_manager_gets_inventory_grants_without_granting_cashiers(self):
        tree = ast.parse(Path(__file__).parents[1].joinpath("install.py").read_text(encoding="utf-8"))
        assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id in ("CUSTOMER_GRANTS", "SALE_GRANTS", "CORE_GRANTS") for target in node.targets)]
        namespace = {}
        exec(compile(ast.Module(body=assignments, type_ignores=[]), "install.py", "exec"), namespace)
        manager = namespace["CORE_GRANTS"]["EsafePOS Manager"]
        self.assertIn("submit", manager["Stock Entry"])
        self.assertIn("create", manager["Item Attribute"])
        self.assertIn("write", manager["Item"])
        self.assertNotIn("Stock Entry", namespace["CORE_GRANTS"]["EsafePOS Cashier"])


class VariantManagerTests(unittest.TestCase):
    # Reuse only the service fixture, not the transfer test methods.
    def setUp(self):
        StockManagerTests.setUp(self)
        self.ns.update({"_can_create": Mock(return_value=True), "_audit": Mock()})
        load_functions("item_variants.py", {"create_attribute", "create_template", "create_variant", "_current_variant"}, self.ns)
        self.item.has_variants = 1; self.item.variant_based_on = "Item Attribute"
        self.item.get.side_effect = lambda key: [SimpleNamespace(attribute="Color")] if key == "attributes" else None
        self.native = ModuleType("erpnext.controllers.item_variant")
        self.native.get_variant = Mock(return_value=None)
        self.native.create_variant = Mock(return_value=self.doc)
        modules = patch.dict(sys.modules, {"erpnext": ModuleType("erpnext"), "erpnext.controllers": ModuleType("erpnext.controllers"),
                                          "erpnext.controllers.item_variant": self.native})
        modules.start(); self.addCleanup(modules.stop)

    raise_error = staticmethod(StockManagerTests.raise_error)

    def test_variant_creation_requires_item_create_capability(self):
        self.ns["_can_create"].return_value = False
        with self.assertRaises(PermissionError): self.ns["create_variant"]("Till", "ITEM", {"Color": "Red"})
        self.native.create_variant.assert_not_called()

    def test_every_attribute_required_and_extra_fields_rejected(self):
        for values in ({}, {"Color": ""}, {"Color": "Red", "Size": "S"}, "bad json"):
            with self.subTest(values=values), self.assertRaises(ValueError): self.ns["create_variant"]("Till", "ITEM", values)
        self.native.create_variant.assert_not_called()

    def test_native_variant_creation_and_existing_combination(self):
        self.ns["create_variant"]("Till", "ITEM", {"Color": "Red"})
        self.native.create_variant.assert_called_once_with("ITEM", {"Color": "Red"}, use_template_image=True)
        self.doc.insert.assert_called_once()
        self.native.get_variant.return_value = "EXISTING"
        result = self.ns["create_variant"]("Till", "ITEM", {"Color": "Red"})
        self.assertTrue(result["existing"]); self.doc.insert.assert_called_once()

    def test_attribute_values_and_abbreviations_are_unique(self):
        for rows in ([], [{"attribute_value": "Red", "abbr": "R"}] * 2, [{"attribute_value": "Red", "abbr": ""}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError): self.ns["create_attribute"]("Till", "Color", rows)
        self.doc.insert.assert_not_called()

    def test_numeric_zero_attribute_is_preserved(self):
        self.ns["create_variant"]("Till", "ITEM", {"Color": 0})
        self.native.create_variant.assert_called_once_with("ITEM", {"Color": "0"}, use_template_image=True)

    def test_combination_committed_while_waiting_is_reused(self):
        self.frappe.db.sql.side_effect = lambda sql, args, **kwargs: [SimpleNamespace(name="EXISTING", attribute="Color", attribute_value="Red")] if "join" in sql else []
        result = self.ns["create_variant"]("Till", "ITEM", {"Color": "Red"})
        self.assertEqual(result, {"item_code": "EXISTING", "existing": True})
        self.native.create_variant.assert_not_called()
        self.native.get_variant.assert_not_called()

    def test_numeric_template_attributes_preserve_range_and_increment(self):
        attribute = Mock(numeric_values=1, from_range=0, to_range=100, increment=5)
        native_get_doc = self.frappe.get_doc.side_effect
        self.frappe.get_doc.side_effect = lambda doctype, name=None, **kwargs: attribute if doctype == "Item Attribute" else native_get_doc(doctype, name, **kwargs)
        self.ns["create_template"]("Till", "NEW", "New template", "Goods", "Nos", [{"attribute": "Length"}])
        self.assertEqual(self.document_data["attributes"], [{"attribute": "Length", "numeric_values": 1, "from_range": 0, "to_range": 100, "increment": 5}])


if __name__ == "__main__":
    unittest.main()
