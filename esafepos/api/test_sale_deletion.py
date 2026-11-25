"""Native sale deletion orchestration with transactional document I/O simulated."""
import ast
import datetime
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class Record(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__


class SaleDeletionTests(unittest.TestCase):
    def setUp(self):
        self.events, self.records, self.links = [], [], set()
        self.alive, self.shift_status, self.series = True, "Open", 37
        self.doc = Record(doctype="POS Invoice", name="ACC-PSINV-2026-00037", docstatus=1,
            pos_profile="Till", company="Shop", esafepos_session="REG-A", currency="LKR",
            rounded_total=1500, grand_total=1500, modified="2026-11-25 16:00:00",
            naming_series="ACC-PSINV-.YYYY.-.#####", meta=Record(autoname="naming_series:"),
            esafepos_idempotency_key="sale-upload-key", check_permission=Mock())
        self.doc.cancel = Mock(side_effect=self.cancel)
        self.frappe = ModuleType("frappe")
        self.frappe.whitelist = lambda **kwargs: lambda fn: fn
        self.frappe._ = lambda text: text
        self.frappe.PermissionError = PermissionError
        self.frappe.UniqueValidationError = type("UniqueValidationError", (Exception,), {})
        self.frappe.DuplicateEntryError = type("DuplicateEntryError", (Exception,), {})
        self.frappe.throw = lambda message, kind=ValueError: (_ for _ in ()).throw(kind(message))
        self.frappe.has_permission = Mock(return_value=True)
        self.frappe.session = Record(user="manager")
        self.frappe.clear_document_cache = Mock()
        self.frappe.get_meta = Mock(return_value=Record(has_field=lambda field: False))
        self.frappe.get_doc = Mock(side_effect=self.get_doc)
        self.frappe.delete_doc = Mock(side_effect=self.delete_doc)
        self.frappe.db = SimpleNamespace(table_exists=Mock(return_value=True), get_value=Mock(side_effect=self.get_value),
            get_values=Mock(return_value=[]), exists=Mock(side_effect=lambda dt, filters: dt in self.links),
            savepoint=Mock(side_effect=self.savepoint), rollback=Mock(side_effect=self.rollback),
            sql=Mock(side_effect=self.sql))
        self.utils = ModuleType("frappe.utils")
        self.utils.cint = lambda value: int(value or 0)
        self.utils.flt = lambda value: float(value or 0)
        self.utils.now_datetime = lambda: datetime.datetime(2026, 11, 25, 16, 0)
        self.permissions = ModuleType("esafepos.api.permissions")
        self.permissions.is_manager = Mock(return_value=True)
        self.permissions.can_delete_sales = lambda: self.permissions.is_manager()
        self.permissions.assert_outlet = Mock()
        self.permissions.allowed_companies = Mock(return_value=None)
        self.modules = patch.dict(sys.modules, {"frappe": self.frappe, "frappe.utils": self.utils,
                                               "esafepos.api.permissions": self.permissions})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        import esafepos.api
        attrs = patch.object(esafepos.api, "permissions", self.permissions, create=True)
        attrs.start()
        self.addCleanup(attrs.stop)
        spec = importlib.util.spec_from_file_location("sale_deletion_subject", Path(__file__).with_name("sale_deletion.py"))
        self.subject = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.subject)
        replay = patch.dict(sys.modules, {"esafepos.api.sale_deletion": self.subject})
        replay.start()
        self.addCleanup(replay.stop)

    def get_doc(self, doctype, *args, **kwargs):
        if isinstance(doctype, str):
            return self.doc
        row = Record(doctype)
        def insert(**kw):
            if row.doctype == "EsafePOS Audit Log" and getattr(self, "audit_fails", False):
                raise ValueError("audit unavailable")
            self.records.append(row)
            self.events.append("marker" if row.doctype == self.subject.AUDIT else "audit")
            return row
        row.insert = Mock(side_effect=insert)
        return row

    def get_value(self, doctype, filters, field=None, **kwargs):
        if doctype == "POS Register Session":
            return self.shift_status
        if doctype == "EsafePOS Deleted Sale":
            for row in self.records:
                if row.doctype != doctype:
                    continue
                if isinstance(filters, str) and row.deletion_key == filters:
                    return row
                if isinstance(filters, dict) and row.idempotency_key_hash == filters.get("idempotency_key_hash"):
                    return row.deletion_key
            return None
        if isinstance(filters, str) and doctype in ("POS Invoice", "Sales Invoice"):
            return self.doc.docstatus if self.alive else None
        return "LINK" if doctype in self.links else None

    def cancel(self):
        self.events.append("cancel")
        self.doc.docstatus = 2

    def delete_doc(self, doctype, name, **kwargs):
        self.assertEqual(self.doc.docstatus, 2)
        self.assertEqual(kwargs, {"delete_permanently": True, "ignore_missing": False})
        self.events.append("delete")
        self.alive = False
        if self.series == 37:
            self.series -= 1

    def sql(self, query, args):
        if query.startswith("select current"):
            return [(self.series,)]
        self.assertEqual(args[1], "ACC-PSINV-2026-")
        self.series = max(self.series, args[0])
        self.events.append("reserve number")

    def savepoint(self, name):
        self.saved = (self.alive, self.doc.docstatus, self.series, list(self.records))

    def rollback(self, **kwargs):
        self.alive, self.doc.docstatus, self.series, self.records = self.saved

    def remove(self, **changes):
        args = dict(invoice=self.doc.name, doctype=self.doc.doctype, reason="Mistaken duplicate sale",
                    confirm_invoice=self.doc.name, expected_modified=self.doc.modified, payment_handled=1)
        args.update(changes)
        return self.subject.permanently_delete_sale(**args)

    def test_submitted_sale_is_cancelled_deleted_and_audited_without_number_reuse(self):
        self.assertTrue(self.remove()["deleted"])
        self.assertFalse(self.alive)
        self.assertEqual(self.events, ["cancel", "marker", "delete", "reserve number", "audit"])
        self.assertEqual(self.series, 37)
        marker = self.records[0]
        self.assertEqual(marker.invoice_name, self.doc.name)
        self.assertEqual(marker.deleted_by, "manager")
        self.assertNotIn("items", marker)
        self.assertNotIn("customer", marker)
        self.assertEqual(len(marker.idempotency_key_hash), 64)
        self.assertTrue(any(call.kwargs.get("for_update") for call in self.frappe.get_doc.call_args_list))

    def test_sales_invoice_and_previously_cancelled_sale_use_native_delete(self):
        self.doc.doctype = "Sales Invoice"
        self.doc.docstatus = 2
        self.assertTrue(self.remove()["deleted"])
        self.doc.cancel.assert_not_called()

    def test_manager_and_native_permissions_company_and_outlet_are_required(self):
        self.permissions.is_manager.return_value = False
        with self.assertRaises(PermissionError): self.remove()
        self.permissions.is_manager.return_value = True
        self.frappe.has_permission.return_value = False
        with self.assertRaises(PermissionError): self.remove()
        self.frappe.has_permission.return_value = True
        self.permissions.allowed_companies.return_value = {"Other"}
        with self.assertRaises(PermissionError): self.remove()
        self.permissions.allowed_companies.return_value = None
        self.permissions.assert_outlet.side_effect = PermissionError("outlet")
        with self.assertRaises(PermissionError): self.remove()
        self.doc.cancel.assert_not_called()
        self.frappe.delete_doc.assert_not_called()

    def test_confirmation_reason_payment_and_stale_version_reject_before_cancel(self):
        for changes in ({"confirm_invoice": "wrong"}, {"reason": ""}, {"reason": "x" * 501},
                        {"payment_handled": 0}, {"expected_modified": "old"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): self.remove(**changes)
        self.doc.cancel.assert_not_called()

    def test_closed_or_closing_shift_cannot_change_saved_counts(self):
        for status in ("Closing", "Closed", None):
            self.shift_status = status
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, "closing or closed"): self.remove()
        self.doc.cancel.assert_not_called()

    def test_consolidation_returns_exchange_and_custom_entries_block_deletion(self):
        for fields in ({"consolidated_invoice": "MERGED"}, {"is_consolidated": 1}, {"is_return": 1},
                       {"esafepos_credit_entry": "CREDIT"}, {"esafepos_loyalty_change_entry": "CHANGE"},
                       {"custom_is_exchange": "Yes"}):
            saved = dict(self.doc)
            self.doc.update(fields)
            with self.subTest(fields=fields), self.assertRaises(ValueError): self.remove()
            self.doc.clear()
            self.doc.update(saved)
        self.doc.cancel.assert_not_called()

    def test_return_wallet_gift_coupon_and_hold_links_are_checked_with_current_reads(self):
        for doctype in ("POS Invoice", "Sales Invoice", "POS Store Credit Entry", "POS Cashback Entry",
                        "POS Gift Card Entry", "POS Gift Card", "POS Layaway Payment", "POS Layaway", "POS Coupon"):
            self.links = {doctype}
            with self.subTest(doctype=doctype), self.assertRaises(ValueError): self.remove()
        self.doc.cancel.assert_not_called()
        self.assertTrue(any(call.kwargs.get("for_update") for call in self.frappe.db.get_value.call_args_list))

    def test_unfinished_print_jobs_block_but_completed_audit_can_remain(self):
        self.links = {"EsafePOS Print Intent"}
        with self.assertRaisesRegex(ValueError, "pending print jobs"): self.remove()
        self.links.clear()
        self.assertTrue(self.remove()["deleted"])

    def test_coupon_promotion_usage_is_checked_even_after_its_last_invoice_changed(self):
        self.doc.esafepos_promotions = '[{"name": "COUPON-PROMO"}]'
        def current_value(dt, filters, field=None, **kwargs):
            if dt == "POS Coupon" and isinstance(filters, dict) and "promotion" in filters:
                self.assertEqual(filters["promotion"], ["in", ["COUPON-PROMO"]])
                return "USED-COUPON"
            return self.get_value(dt, filters, field, **kwargs)
        self.frappe.db.get_value.side_effect = current_value
        with self.assertRaisesRegex(ValueError, "redemption history"): self.remove()
        self.doc.cancel.assert_not_called()

    def test_unused_native_loyalty_can_cancel_but_spent_or_remaining_points_cannot(self):
        self.frappe.db.get_values.return_value = [Record(name="LOT")]
        self.links = {"Loyalty Point Entry"}
        with self.assertRaisesRegex(ValueError, "Points earned"): self.remove()
        self.frappe.db.get_values.return_value = []
        with self.assertRaisesRegex(ValueError, "reverse all loyalty"): self.remove()
        self.assertTrue(self.alive)
        self.assertEqual(self.doc.docstatus, 1)

    def test_loyalty_customer_locks_before_drawer_and_invoice(self):
        self.doc.update(customer="CUSTOMER", loyalty_program="Rewards")
        self.remove()
        locks = [call.args[0] for call in self.frappe.db.get_value.call_args_list if call.kwargs.get("for_update")]
        self.assertEqual(locks[:2], ["Customer", "POS Register Session"])

    def test_native_link_failure_or_audit_failure_rolls_back_cancel_and_marker(self):
        self.frappe.delete_doc.side_effect = ValueError("ERPNext linked document")
        with self.assertRaisesRegex(ValueError, "linked document"): self.remove()
        self.assertTrue(self.alive)
        self.assertEqual(self.doc.docstatus, 1)
        self.assertEqual(self.records, [])
        self.frappe.delete_doc.side_effect = self.delete_doc
        self.audit_fails = True
        with self.assertRaisesRegex(ValueError, "audit unavailable"): self.remove()
        self.assertTrue(self.alive)
        self.assertEqual(self.doc.docstatus, 1)
        self.assertEqual(self.records, [])
        self.assertEqual(self.series, 37)

    def test_repeated_request_is_idempotent_and_old_upload_is_refused(self):
        self.remove()
        self.assertTrue(self.subject.check_sale_deletion(self.doc.name, self.doc.doctype)["deleted"])
        self.assertTrue(self.remove()["already_deleted"])
        self.assertEqual(self.frappe.delete_doc.call_count, 1)
        with self.assertRaisesRegex(ValueError, "old upload key"):
            self.subject.assert_not_deleted_key("sale-upload-key", for_update=True)

    def test_concurrent_deletion_is_detected_after_waiting_for_the_drawer(self):
        def current_value(dt, filters, field=None, **kwargs):
            if dt == "POS Register Session" and kwargs.get("for_update") and not self.records:
                self.records.append(Record(doctype=self.subject.AUDIT,
                    deletion_key=self.subject._identity(self.doc.doctype, self.doc.name),
                    pos_profile="Till", company="Shop"))
                self.alive = False
            return self.get_value(dt, filters, field, **kwargs)
        self.frappe.db.get_value.side_effect = current_value
        self.assertTrue(self.remove()["already_deleted"])
        self.doc.cancel.assert_not_called()
        self.frappe.delete_doc.assert_not_called()

    def test_migration_and_custom_numbering_fail_before_cancel(self):
        self.frappe.db.table_exists.return_value = False
        with self.assertRaisesRegex(ValueError, "migration"): self.remove()
        self.frappe.db.table_exists.return_value = True
        self.doc.naming_series = "SINV-.#####.-2026"
        with self.assertRaisesRegex(ValueError, "custom invoice naming"): self.remove()
        self.doc.cancel.assert_not_called()

    def test_final_insert_guard_refuses_deleted_upload_and_deleted_return_original(self):
        ns = {"frappe": self.frappe, "_": lambda text: text}
        tree = ast.parse(Path(__file__).with_name("sales.py").read_text(encoding="utf-8"))
        node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_insert_once")
        exec(compile(ast.Module(body=[node], type_ignores=[]), "<sales>", "exec"), ns)
        self.remove()
        incoming = Record(doctype="POS Invoice", insert=Mock())
        with self.assertRaisesRegex(ValueError, "old upload key"): ns["_insert_once"](incoming, "sale-upload-key")
        incoming.update(is_return=1, return_against=self.doc.name)
        with self.assertRaisesRegex(ValueError, "original sale"): ns["_insert_once"](incoming, "different-key")
        incoming.insert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
