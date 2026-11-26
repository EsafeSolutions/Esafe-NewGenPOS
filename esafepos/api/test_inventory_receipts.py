"""Native Material Receipt and committed catalog-sync boundaries, without a bench."""
import sys
import json
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from esafepos.api import test_stock_manager as fixtures

load_functions = fixtures.load_functions


class MaterialReceiptTests(unittest.TestCase):
    raise_error = staticmethod(fixtures.StockManagerTests.raise_error)

    def setUp(self):
        fixtures.StockManagerTests.setUp(self)
        self.ns["_can_receive_stock"] = Mock(return_value=True)
        self.ns["warehouse_stock"] = Mock(return_value={"rows": [{"warehouse": "Shelf", "actual_qty": 13}]})
        self.doc.purpose = "Material Receipt"
        load_functions("inventory.py", {"receive_stock", "_result"}, self.ns)

    def receive(self, **kwargs):
        args = dict(pos_profile="Till", item_code="ITEM", warehouse="Shelf", qty=3,
                    valuation_rate=25, reason="Delivery REF-1", request_id="receipt-1")
        args.update(kwargs)
        return self.ns["receive_stock"](**args)

    def test_requires_separate_receiving_capability(self):
        self.ns["_can_receive_stock"].return_value = False
        with self.assertRaises(PermissionError): self.receive()
        self.frappe.get_doc.assert_not_called()

    def test_inaccessible_warehouse_refused(self):
        with self.assertRaises(PermissionError): self.receive(warehouse="Other company")
        self.doc.insert.assert_not_called()

    def test_positive_finite_quantity_and_cost_required(self):
        for field in ("qty", "valuation_rate"):
            for value in (0, -1, "nan", "inf", "", None):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError): self.receive(**{field: value})
        self.doc.submit.assert_not_called()

    def test_reason_and_identity_required(self):
        for args in ({"reason": " "}, {"request_id": ""}, {"reason": "x" * 501}):
            with self.assertRaises(ValueError): self.receive(**args)
        self.doc.insert.assert_not_called()

    def test_native_receipt_adds_instead_of_overwriting_quantity(self):
        result = self.receive()
        self.assertEqual(self.document_data["purpose"], "Material Receipt")
        row = self.document_data["items"][0]
        self.assertEqual(row["qty"], 3); self.assertEqual(row["basic_rate"], 25)
        self.assertEqual(row["t_warehouse"], "Shelf"); self.assertNotIn("s_warehouse", row)
        self.assertEqual(result["stock"]["rows"][0]["actual_qty"], 13)
        self.doc.submit.assert_called_once(); self.audit.log.assert_called_once()

    def test_receipt_does_not_replace_or_refuse_unposted_sales(self):
        self.stock._unposted.return_value = [{"item_code": "ITEM", "qty": 4}]
        self.receive()
        self.stock._refuse_unposted.assert_not_called()
        self.doc.submit.assert_called_once()

    def test_workflow_and_native_submit_permissions_apply(self):
        self.stock._has_workflow.return_value = True
        with self.assertRaises(ValueError): self.receive()
        self.doc.insert.assert_not_called()
        self.stock._has_workflow.return_value = False
        self.doc.check_permission.side_effect = [None, PermissionError]
        with self.assertRaises(PermissionError): self.receive()
        self.doc.insert.assert_not_called()

    def test_retry_returns_existing_receipt_once(self):
        self.receive(); self.previous = self.doc; self.frappe.db.get_value.return_value = "TRF-1"
        result = self.receive()
        self.assertTrue(result["replayed"]); self.doc.insert.assert_called_once()
        self.assertTrue(self.frappe.db.get_value.call_args.kwargs["for_update"])
        with self.assertRaises(ValueError): self.receive(qty=4)

    def test_cancelled_receipt_cannot_be_replayed(self):
        self.receive(); self.previous = self.doc; self.frappe.db.get_value.return_value = "TRF-1"
        self.doc.docstatus = 2
        with self.assertRaises(ValueError): self.receive()

    def test_receipt_requires_enabled_stock_leaf(self):
        for field, value in (("disabled", 1), ("has_variants", 1), ("is_stock_item", 0)):
            original = getattr(self.item, field); setattr(self.item, field, value)
            with self.assertRaises(ValueError): self.receive()
            setattr(self.item, field, original)
        self.doc.submit.assert_not_called()

    def test_whole_unit_and_unique_serial_quantities(self):
        self.frappe.get_cached_value.return_value = 1
        with self.assertRaises(ValueError): self.receive(qty=1.5)
        self.item.has_serial_no = 1
        with self.assertRaises(ValueError): self.receive(serial_no="S1\nS1\nS2")
        self.receive(serial_no="S1\nS2\nS3")
        self.assertEqual(self.document_data["items"][0]["serial_no"], "S1\nS2\nS3")

    def test_batch_tracking_is_required_only_when_configured(self):
        with self.assertRaises(ValueError): self.receive(batch_no="B1")
        self.item.has_batch_no = 1
        with self.assertRaises(ValueError): self.receive()
        self.receive(batch_no="B1")
        self.assertEqual(self.document_data["items"][0]["batch_no"], "B1")

    def test_standing_price_is_saved_to_native_item_price(self):
        load_functions("items.py", {"save_item", "_save_prices"}, self.ns)
        price = Mock(price_list_rate=100); price.name = "PRICE-1"
        price_doc = Mock(price_list="Retail", uom="Nos"); price_doc.name = "PRICE-1"
        self.ns.update({"_can_edit_prices": Mock(return_value=True), "_selling_list": Mock(return_value=SimpleNamespace(name="Retail")),
                        "_standing_price": Mock(return_value=price), "_item_price_doc": Mock(return_value=price_doc),
                        "item_details": Mock(return_value={"saved": True})})
        self.ns["save_item"]("Till", "ITEM", prices=[{"uom": "Nos", "price": 125}])
        self.assertEqual(price_doc.price_list_rate, 125); price_doc.save.assert_called_once()


class CatalogCommitTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock(); self.frappe.local = SimpleNamespace()
        self.commits, self.rollbacks, self.values = [], [], {}
        self.frappe.db.after_commit = SimpleNamespace(add=self.commits.append)
        self.frappe.db.after_rollback = SimpleNamespace(add=self.rollbacks.append)
        self.cache = Mock()
        self.cache.get_value.side_effect = self.values.get
        self.cache.set_value.side_effect = self.values.__setitem__
        self.frappe.cache.return_value = self.cache
        self.frappe.whitelist.side_effect = lambda **kwargs: lambda fn: fn
        self.ns = {"frappe": self.frappe, "uuid4": uuid4, "REVISION_KEY": "revision", "_context": Mock()}
        load_functions("catalog_sync.py", {"_reset", "_invalidate", "changed", "revision"}, self.ns)

    def test_coalesces_events_and_does_not_publish_uncommitted_changes(self):
        for _ in range(10): self.ns["changed"]()
        self.assertEqual(len(self.commits), 1); self.cache.set_value.assert_not_called()
        self.commits[0]()
        self.assertIn("revision", self.values)

    def test_rollback_does_not_publish_and_allows_later_transaction(self):
        self.ns["changed"](); self.rollbacks[0]()
        self.cache.set_value.assert_not_called()
        self.ns["changed"](); self.assertEqual(len(self.commits), 2)

    def test_old_frappe_and_cache_failure_use_direct_polling(self):
        self.frappe.db.after_commit = None
        self.ns["changed"](); self.assertEqual(self.commits, [])
        self.assertTrue(self.ns["revision"]("Till")["direct_poll"])
        self.cache.get_value.side_effect = RuntimeError("Redis unavailable")
        self.assertTrue(self.ns["revision"]("Till")["direct_poll"])

    def test_cache_failure_cannot_fail_a_committed_posting(self):
        self.cache.set_value.side_effect = RuntimeError("Redis unavailable")
        self.ns["changed"](); self.commits[0]()
        self.assertFalse(self.frappe.local.esafepos_catalog_change_scheduled)

    def test_revision_requires_item_read_before_outlet_access(self):
        self.ns.update({"_": lambda value: value, "assert_outlet": Mock()})
        self.frappe.PermissionError = PermissionError
        self.frappe.throw.side_effect = PermissionError
        self.frappe.has_permission.return_value = False
        load_functions("catalog_sync.py", {"_context"}, self.ns)
        with self.assertRaises(PermissionError): self.ns["revision"]("Other till")
        self.ns["assert_outlet"].assert_not_called()

    def test_live_item_code_payload_is_bounded_and_validated(self):
        self.ns.update({"_": lambda value: value, "json": json})
        self.frappe.throw.side_effect = ValueError
        load_functions("items.py", {"_json_list_codes"}, self.ns)
        for value in (["ITEM"] * 501, [None], [""], "bad json", {"item": "ITEM"}):
            with self.subTest(value=value), self.assertRaises(ValueError): self.ns["_json_list_codes"](value)
        self.assertEqual(self.ns["_json_list_codes"]('["ITEM", "ITEM", "OTHER"]'), ["ITEM", "OTHER"])


if __name__ == "__main__":
    unittest.main()
