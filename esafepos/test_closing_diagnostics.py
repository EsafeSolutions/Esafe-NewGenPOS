"""Root-cause summaries and system-check linking, without a Frappe site."""
import ast
import datetime
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from esafepos.closing_diagnostics import error_summary


CAUSE = "Valuation Rate for the Item flower bool, is required to do accounting entries for Sales Invoice ACC-SINV-2026-00037."
ADVICE = "Here are the options to proceed:If the item is transacting as a Zero Valuation Rate item, enable Allow Zero Valuation Rate."


class Record(dict):
    __getattr__ = dict.get


class ErrorSummaryTests(unittest.TestCase):
    def test_original_item_and_invoice_survive_followup_advice(self):
        self.assertEqual(error_summary(CAUSE + "\n\n" + ADVICE), CAUSE)

    def test_one_line_error_drops_followup_advice(self):
        self.assertEqual(error_summary(CAUSE + ADVICE), CAUSE)

    def test_traceback_keeps_actual_valuation_failure(self):
        self.assertEqual(error_summary("Traceback (most recent call last):\nValidationError: " + CAUSE + "\n" + ADVICE), "ValidationError: " + CAUSE)

    def test_other_traceback_keeps_final_exception_and_bounds_length(self):
        text = "Traceback:\n  file.py:12\nTypeError: DatabaseQuery.execute() got multiple values for argument 'fields'"
        self.assertEqual(error_summary(text), text.splitlines()[-1])
        self.assertEqual(error_summary(CAUSE, 30), CAUSE[:30])
        self.assertEqual(error_summary(None), "")


class SystemCheckShiftTests(unittest.TestCase):
    def setUp(self):
        self.frappe = SimpleNamespace(get_all=Mock(), db=SimpleNamespace(sql=Mock(return_value=[(0, None)])))
        self.stuck = Record(name="REG-0011", pos_profile="Default", closing_error=CAUSE + "\n" + ADVICE, closing_attempts=30)
        self.sessions = [Record(name="REG-0011", pos_opening_entry="POS-OPE-17", status="Closing")]
        self.openings = [Record(name="POS-OPE-17", pos_profile="Default", period_start_date="2026-11-23")]
        self.frappe.get_all.side_effect = self.query
        periods = ModuleType("esafepos.accounting_periods")
        periods.plain = lambda text: text
        register = ModuleType("esafepos.api.register")
        register._sessions_with_pending_days = lambda: []
        self.modules = patch.dict(sys.modules, {"esafepos.accounting_periods": periods, "esafepos.api.register": register})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        import esafepos.api
        attrs = patch.object(esafepos.api, "register", register, create=True)
        attrs.start()
        self.addCleanup(attrs.stop)
        now = datetime.datetime(2026, 11, 25, 14, 22)
        self.ns = {"frappe": self.frappe, "_": lambda text: text, "cint": lambda value: int(value or 0),
                   "PROBLEM": "problem", "WARN": "warn", "INFO": "info", "OK": "ok",
                   "erpnext_compat": SimpleNamespace(one_open_shift_per_outlet=lambda: True),
                   "now_datetime": lambda: now, "nowdate": lambda: str(now.date()),
                   "add_to_date": lambda date, **kw: date + datetime.timedelta(**kw),
                   "add_days": lambda date, days: now + datetime.timedelta(days=days),
                   "error_summary": error_summary, "_check_jobs": lambda since: []}
        tree = ast.parse((Path(__file__).parent / "api/system_check.py").read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in ("_row", "_check_shifts", "_check_errors"):
                exec(compile(ast.Module(body=[node], type_ignores=[]), "<system_check>", "exec"), self.ns)

    def query(self, doctype, *, filters=None, fields=None, **kwargs):
        if doctype == "POS Opening Entry":
            return self.openings
        if filters.get("status") == "Closing":
            return [self.stuck]
        if filters.get("status") == "Open":
            return []
        return self.sessions

    def test_report_names_missing_cost_and_paused_retry_count(self):
        rows = self.ns["_check_shifts"]()
        item = rows[0]["items"][0]
        self.assertIn("flower bool", item)
        self.assertIn("ACC-SINV-2026-00037", item)
        self.assertIn("30 attempts", item)
        self.assertNotIn("Here are the options", item)
        self.assertIn("correct the item cost", rows[0]["fix"])

    def test_linked_opening_is_same_issue_and_points_to_existing_shift(self):
        rows = self.ns["_check_shifts"]()
        linked = next(row for row in rows if "held by unfinished" in row["title"])
        self.assertEqual(linked["level"], "info")
        self.assertIn("POS-OPE-17, Default → REG-0011", linked["items"])
        self.assertFalse(any("from an earlier day blocking" in row["title"] for row in rows))

    def test_unlinked_opening_remains_blocking_and_open_shift_is_excluded(self):
        self.sessions.append(Record(name="OPEN", pos_opening_entry="LIVE-OPE", status="Open"))
        self.openings += [Record(name="EXTERNAL-OPE", pos_profile="Other", period_start_date="2026-11-21"),
                          Record(name="LIVE-OPE", pos_profile="Other", period_start_date="2026-11-21")]
        rows = self.ns["_check_shifts"]()
        external = next(row for row in rows if "from an earlier day blocking" in row["title"])
        self.assertEqual(external["level"], "problem")
        self.assertEqual(len(external["items"]), 1)
        self.assertTrue(external["items"][0].startswith("EXTERNAL-OPE"))

    def test_error_log_grouping_shows_cause_and_keeps_existing_records(self):
        self.frappe.db.sql.return_value = [Record(method="EsafePOS register stuck", error=CAUSE + "\n" + ADVICE)] * 2
        result = self.ns["_check_errors"]()[0]
        self.assertIn("2 x", result["items"][0])
        self.assertIn("flower bool", result["items"][0])
        self.assertNotIn("Here are the options", result["items"][0])
        self.assertIn("Existing entries remain after a fix", result["detail"])


if __name__ == "__main__":
    unittest.main()
