"""Exercise recovery endpoint guards without a running Frappe bench."""
import ast
import pathlib
import sys
import types
import unittest
from unittest.mock import Mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class Row(dict):
    __getattr__ = dict.get


class ShiftRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.doc = Row(name="REG-1", status="Closing", closing_status="Failed", pos_profile="Till A")
        self.frappe = types.ModuleType("frappe")
        self.frappe.whitelist = lambda: lambda fn: fn
        self.frappe.PermissionError = PermissionError
        self.frappe.has_permission = Mock(return_value=True)
        self.frappe.get_doc = Mock(side_effect=lambda *a, **kw: self.doc)
        self.frappe.db = types.SimpleNamespace(get_value=Mock(), set_value=Mock())
        self.frappe.throw = self.throw
        self.permissions = types.ModuleType("esafepos.api.permissions")
        self.permissions.can_close_register = Mock(return_value=True)
        self.permissions.assert_outlet = Mock()
        self.api = types.ModuleType("esafepos.api")
        self.api.permissions = self.permissions
        self.saved = {name: sys.modules.get(name) for name in (
            "esafepos.api", "esafepos.api.permissions", "esafepos.api.register", "esafepos.erpnext_compat")}
        sys.modules["esafepos.api"] = self.api
        sys.modules["esafepos.api.permissions"] = self.permissions
        self.queue = Mock()
        self.ns = {"frappe": self.frappe, "_": lambda value: value, "_enqueue_consolidation": self.queue}
        tree = ast.parse((ROOT / "esafepos/api/register.py").read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in ("retry_closing", "_reconcile_session", "reconcile_stuck_closings"):
                exec(compile(ast.Module(body=[node], type_ignores=[]), "<register>", "exec"), self.ns)

    def tearDown(self):
        for name, value in self.saved.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value

    @staticmethod
    def throw(message, kind=ValueError):
        raise kind(message)

    def test_retry_marks_failed_shift_queued_and_keeps_saved_counts(self):
        self.assertTrue(self.ns["retry_closing"]("REG-1")["queued"])
        self.frappe.db.set_value.assert_called_once_with("POS Register Session", "REG-1", "closing_status", "Queued")
        self.queue.assert_called_once_with("REG-1")
        self.permissions.assert_outlet.assert_called_once_with("Till A")
        self.assertTrue(self.frappe.get_doc.call_args.kwargs["for_update"])

    def test_retry_is_idempotent_for_a_closed_shift(self):
        self.doc["status"] = "Closed"
        self.assertEqual(self.ns["retry_closing"]("REG-1")["status"], "Closed")
        self.queue.assert_not_called()
        self.frappe.db.set_value.assert_not_called()

    def test_retry_cannot_close_an_open_drawer(self):
        self.doc["status"] = "Open"
        with self.assertRaisesRegex(ValueError, "still open"):
            self.ns["retry_closing"]("REG-1")
        self.queue.assert_not_called()
        self.assertIsNone(self.ns["_reconcile_session"]("REG-1", {}))
        self.frappe.db.set_value.assert_not_called()

    def test_retry_requires_native_permission_capability_and_outlet_access(self):
        for blocked in ("native", "capability", "outlet"):
            with self.subTest(blocked=blocked):
                self.frappe.has_permission.return_value = blocked != "native"
                self.permissions.can_close_register.return_value = blocked != "capability"
                self.permissions.assert_outlet.side_effect = PermissionError("outlet") if blocked == "outlet" else None
                with self.assertRaises(PermissionError):
                    self.ns["retry_closing"]("REG-1")
                self.queue.assert_not_called()
                self.frappe.db.set_value.assert_not_called()

    def test_pending_close_distinguishes_erpnext_16_and_lightweight_shifts(self):
        register = types.ModuleType("esafepos.api.register")
        register._closing_hint = Mock(return_value=None)
        compat = types.ModuleType("esafepos.erpnext_compat")
        compat.one_open_shift_per_outlet = Mock()
        sys.modules[register.__name__] = register
        sys.modules[compat.__name__] = compat
        self.doc.update(closing_attempts=30, closing_error="Missing item cost")
        self.frappe.db.get_value.return_value = self.doc
        self.frappe.get_cached_doc = Mock()
        self.ns["cint"] = lambda value: int(value or 0)
        tree = ast.parse((ROOT / "esafepos/api/session.py").read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_pending_closing")
        exec(compile(ast.Module(body=[node], type_ignores=[]), "<session>", "exec"), self.ns)
        for one_open, mode, use_entries, blocked in (
            (True, "POS Invoice", 0, True), (False, "POS Invoice", 0, False),
            (True, "Sales Invoice", 0, False), (True, "Sales Invoice", 1, True),
        ):
            with self.subTest(one_open=one_open, mode=mode, use_entries=use_entries):
                compat.one_open_shift_per_outlet.return_value = one_open
                self.frappe.get_cached_doc.return_value = Row(esafepos_invoice_mode=mode, esafepos_si_opening_closing=use_entries)
                result = self.ns["_pending_closing"]("Till A")
                self.assertEqual(result["new_shift_blocked"], blocked)
                self.assertEqual(result["closing_attempts"], 30)

    def test_scheduler_does_not_repeat_logs_or_retries_for_capped_shifts(self):
        self.frappe.get_all = Mock(return_value=[Row(name="CAPPED", closing_attempts=30),
                                                 Row(name="RETRY", closing_attempts=29),
                                                 Row(name="LEGACY", closing_attempts=None)])
        self.frappe.log_error = Mock()
        build = Mock()
        self.ns.update(cint=lambda value: int(value or 0), build_closing_entry=build,
                       _sessions_with_pending_days=lambda: [], fill_pending_figures=Mock(), _alert_orphan_invoices=Mock())
        for _ in range(2):
            self.ns["reconcile_stuck_closings"]()
        self.assertEqual([call.args[0] for call in build.call_args_list], ["RETRY", "LEGACY"] * 2)
        self.frappe.log_error.assert_not_called()
        # Exclude capped shifts before the page limit, so 50 old failures cannot
        # hide a later shift that still has retries available.
        self.assertEqual(self.frappe.get_all.call_args.kwargs["or_filters"],
                         [["closing_attempts", "<", 30], ["closing_attempts", "is", "not set"]])


if __name__ == "__main__":
    unittest.main()
