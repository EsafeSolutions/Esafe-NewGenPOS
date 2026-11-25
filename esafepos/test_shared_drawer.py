"""Shared-drawer transactions with Frappe document I/O mocked."""
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch


class Record(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__


class SharedDrawerTests(unittest.TestCase):
    def setUp(self):
        self.frappe = ModuleType("frappe")
        self.frappe._ = lambda value: value
        self.frappe._dict = Record
        self.frappe.whitelist = lambda: lambda fn: fn
        self.frappe.PermissionError = PermissionError
        self.frappe.throw = lambda message, *args, **kwargs: self.fail_request(message, *args)
        self.frappe.has_permission = Mock(return_value=True)
        self.frappe.utils = Record(get_fullname=lambda name: name)
        self.frappe.db = Mock()
        self.frappe.db.get_values.return_value = []
        self.frappe.get_meta = Mock(return_value=Record(has_field=lambda field: True))
        self.frappe.session = Record(user="manager")
        self.utils = ModuleType("frappe.utils")
        self.utils.flt = lambda n=0, p=None: round(float(n or 0), p) if p is not None else float(n or 0)
        self.permissions = ModuleType("esafepos.api.permissions")
        self.permissions.is_manager = Mock(return_value=True)
        self.permissions.assert_outlet = Mock()
        self.permissions.can_close_register = Mock(return_value=True)
        self.register = ModuleType("esafepos.api.register")
        for name in ("_stage_close", "_enqueue_consolidation", "_mark_closed", "_audit_register", "_maybe_alert_variance"):
            setattr(self.register, name, Mock())
        self.register._close_result = lambda doc, queued: {"name": doc.name, "queued": queued}
        self.variance = ModuleType("esafepos.variance")
        self.sales = ModuleType("esafepos.api.sales")
        self.sales._table_doctype = lambda profile: "POS Invoice"
        self.variance.apply = Mock(side_effect=lambda doc, reason, action, **kw: doc.update(variance_reason=reason, variance_action=action))
        self.modules = patch.dict(sys.modules, {"frappe": self.frappe, "frappe.utils": self.utils,
            "esafepos.api.permissions": self.permissions, "esafepos.api.register": self.register,
            "esafepos.variance": self.variance, "esafepos.api.sales": self.sales})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        # Keep package attribute imports deterministic even after other suites.
        import esafepos.api
        self.attrs = patch.multiple(esafepos.api, permissions=self.permissions, register=self.register, create=True)
        self.attrs.start()
        self.addCleanup(self.attrs.stop)
        spec = importlib.util.spec_from_file_location("shared_drawer_subject", Path(__file__).parent / "api" / "shared_drawer.py")
        self.subject = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.subject)
        self.docs = [Record(name=name, combined_drawer="A", status="Open", modified="now", pos_profile="Till", opened_by=name,
                            pos_opening_entry="OPEN-" + name, reload=Mock()) for name in ("A", "B")]
        self.subject._doc = Mock(side_effect=lambda name, **kwargs: next(d for d in self.docs if d.name == name))
        self.subject._members = Mock(return_value=self.docs)
        self.subject._signature = Mock(return_value=("Shop", "Cash", {}, [("Cash", "Cash - S")]))
        self.figures = [{"expected": [{"mode_of_payment": "Cash", "currency": "LKR", "expected_amount": n, "is_cash": 1}],
                         "company_currency": "LKR", "rates": {}, "sales_count": 1, "cash_movements": []} for n in (100, 200)]
        self.register.get_session_summary = Mock(side_effect=lambda name: self.figures[0 if name == "A" else 1])

    def fail_request(self, message, *args):
        raise PermissionError(message) if args and args[0] is PermissionError else ValueError(message)

    def test_summary_adds_floats_takings_and_moves_without_moving_sales(self):
        data = self.subject.summary("A")
        self.assertEqual(data["expected"][0]["expected_amount"], 300)
        self.assertEqual(data["sales_count"], 2)
        self.assertEqual([r["session"] for r in data["members"]], ["A", "B"])

    def test_snapshot_detects_cash_changes_even_when_sale_count_is_unchanged(self):
        first = self.subject.summary("A")["version"]
        self.figures[1]["cash_movements"].append({"amount": 10})
        self.assertNotEqual(first, self.subject.summary("A")["version"])

    def test_snapshot_checks_current_ledger_even_when_summary_read_is_old(self):
        first = self.subject.summary("A")["version"]
        self.frappe.db.get_values.return_value = [Record(name="SALE-NEW", modified="later")]
        with self.assertRaisesRegex(ValueError, "drawer changed"):
            self.subject.close("A", {"Cash": 300}, first)
        self.register._stage_close.assert_not_called()
        self.assertTrue(any(c.kwargs.get("for_update") for c in self.frappe.db.get_values.call_args_list))

    def test_stale_close_rejects_before_staging_or_committing(self):
        with self.assertRaisesRegex(ValueError, "drawer changed"):
            self.subject.close("A", {"Cash": 300}, "old")
        self.register._stage_close.assert_not_called()
        self.frappe.db.commit.assert_not_called()

    def test_close_locks_all_members_and_stages_before_single_commit(self):
        events = []
        self.register._stage_close.side_effect = lambda doc, *a, **kw: events.append("stage " + doc.name)
        self.frappe.db.commit.side_effect = lambda: events.append("commit")
        self.register._enqueue_consolidation.side_effect = lambda name: events.append("queue " + name)
        self.subject.close("A", {"Cash": 297}, self.subject.summary("A")["version"], variance_reason="Counted twice")
        self.assertEqual(events, ["stage A", "stage B", "commit", "queue A", "queue B"])
        self.assertEqual([call.args[1]["Cash"] for call in self.register._stage_close.call_args_list], [99, 198])
        self.assertEqual(json.loads(self.docs[0].combined_count)["counted"]["Cash"], 297)
        self.assertEqual(self.docs[0].combined_count, self.docs[1].combined_count)
        self.register._maybe_alert_variance.assert_called_once()
        locked = [c.args[1] for c in self.frappe.db.get_value.call_args_list if c.kwargs.get("for_update")]
        self.assertEqual(set(locked), {"A", "B"})

    def test_staging_failure_never_commits_or_queues_half_a_group(self):
        self.register._stage_close.side_effect = [None, ValueError("cannot save")]
        with self.assertRaisesRegex(ValueError, "cannot save"):
            self.subject.close("A", {"Cash": 300}, self.subject.summary("A")["version"])
        self.frappe.db.commit.assert_not_called()
        self.register._enqueue_consolidation.assert_not_called()

    def test_only_managers_can_combine_or_close_colleagues_shifts(self):
        self.permissions.is_manager.return_value = False
        for action in (lambda: self.subject.combine("A", "B"), lambda: self.subject.close("A", {"Cash": 300}, "old")):
            with self.assertRaises(PermissionError): action()

    def test_cashier_syncs_group_closure_without_other_outlet_figures(self):
        self.permissions.is_manager.return_value = False
        def query(fields=None, filters=None, **kwargs):
            self.assertEqual(filters, {"combined_drawer": "A"})
            return [Record(name="A", pos_profile="Till A", opened_by="A", status="Open"),
                    Record(name="B", pos_profile="Till B", opened_by="B", status="Closing")]
        # Frappe binds fields before filters. A positional filter plus fields=
        # must raise here exactly as it does on the real site.
        self.frappe.get_all = Mock(side_effect=lambda dt, *args, **kw: query(*args, **kw))
        result = self.subject.summary("A")
        self.assertEqual(result["group"], "A")
        self.assertFalse(result["all_open"])
        self.assertEqual(result["expected"], [])
        self.register.get_session_summary.assert_not_called()

    def test_candidates_bind_filters_without_colliding_with_fields(self):
        self.permissions.can_use_outlet = Mock(return_value=True)
        self.subject._members.return_value = [self.docs[0]]
        def query(fields=None, filters=None, **kwargs):
            self.assertEqual(filters, {"status": "Open"})
            self.assertEqual(fields, ["name", "pos_profile"])
            return self.docs
        self.frappe.get_all = Mock(side_effect=lambda dt, *args, **kw: query(*args, **kw))
        result = self.subject.candidates("A")
        self.assertEqual([row["session"] for row in result], ["B"])

    def test_incompatible_company_or_cash_accounts_are_rejected(self):
        for signature in (("Other", "Cash", {}, [("Cash", "Cash - S")]), ("Shop", "Cash", {}, [("Cash", "Other - S")])):
            self.subject._signature.side_effect = [("Shop", "Cash", {}, [("Cash", "Cash - S")]), signature]
            with self.assertRaisesRegex(ValueError, "same company"):
                self.subject._validate_members(self.docs)

    def test_every_linked_outlet_must_be_accessible(self):
        # Exercise the real loader, rather than the in-memory member fixture.
        self.frappe.get_doc = Mock(return_value=self.docs[0])
        self.permissions.assert_outlet.side_effect = PermissionError("outlet denied")
        loader = self.subject.__dict__["_doc"]
        # Re-load just this function so the class fixture's replacement does
        # not hide its outlet authorization contract.
        import ast
        tree = ast.parse((Path(__file__).parent / "api" / "shared_drawer.py").read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_doc")
        namespace = dict(frappe=self.frappe, permissions=self.permissions, _=lambda value: value)
        exec(compile(ast.Module(body=[node], type_ignores=[]), "shared_drawer.py", "exec"), namespace)
        with self.assertRaises(PermissionError): namespace["_doc"]("A")
        self.subject._doc = loader

    def test_closed_member_and_negative_cash_cannot_close(self):
        self.docs[1].status = "Closing"
        with self.assertRaisesRegex(ValueError, "Only open shifts"):
            self.subject.close("A", {"Cash": 300}, "old")
        self.docs[1].status = "Open"
        with self.assertRaisesRegex(ValueError, "non-negative"):
            self.subject.close("A", {"Cash": -1}, self.subject.summary("A")["version"])


if __name__ == "__main__":
    unittest.main()
