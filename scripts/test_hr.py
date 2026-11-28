"""HR API authorization and posting tests with mocked Frappe I/O, not a live site."""
import importlib
import json
import pathlib
import sys
import types
import unittest
from datetime import date
from unittest.mock import Mock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
fake = types.ModuleType("frappe")
fake._ = lambda value: value
fake.whitelist = lambda *args, **kwargs: lambda fn: fn
fake.PermissionError = PermissionError
fake.throw = lambda message, exc=ValueError, **kwargs: (_ for _ in ()).throw(exc(message))
fake.session = types.SimpleNamespace(user="payroll@example.com")
fake.db = Mock()
fake.get_doc = Mock()
fake.new_doc = Mock()
fake.get_cached_value = Mock(return_value="LKR")
fake.get_cached_doc = Mock()
fake.get_roles = Mock(return_value=["Payroll Manager"])
fake.get_meta = Mock()
fake.get_list = Mock(return_value=[])
fake.get_all = Mock(return_value=[])
fake.has_permission = Mock(return_value=True)
fake.parse_json = json.loads
utils = types.ModuleType("frappe.utils")
utils.cint = lambda n: int(n or 0)
utils.flt = lambda n, *args: float(n or 0)
utils.getdate = lambda n: n if isinstance(n, date) else date.fromisoformat(str(n))
utils.nowdate = lambda: "2026-11-28"
utils.now = lambda: "2026-11-28 12:00:00"
sys.modules["frappe"] = fake
sys.modules["frappe.utils"] = utils
hr = importlib.import_module("esafepos.api.hr")


class HRAPITests(unittest.TestCase):
    def setUp(self):
        fake.get_doc.reset_mock(side_effect=True, return_value=True)
        fake.db.reset_mock(side_effect=True, return_value=True)
        fake.get_roles.return_value = ["Payroll Manager"]
        fake.has_permission.return_value = True
        fake.get_doc.return_value = Mock(company="Company", employee="EMP", user_id=fake.session.user)

    def batch(self, status="Approved"):
        doc = Mock(company="Company", employee="EMP", kind="Commission", month="2026-10", fingerprint="fresh", amount=1500,
                   currency="LKR", status=status, additional_salary="SAL1")
        doc.name = "BATCH1"
        doc.get.side_effect = lambda key: getattr(doc, key, None)
        doc.update.side_effect = lambda values: [setattr(doc, key, value) for key, value in values.items()]
        return doc

    def test_disabled_feature_blocks_server_action(self):
        with patch.object(hr.features, "enabled", return_value=False), self.assertRaises(PermissionError):
            hr._guard("Company", "enable_attendance")

    def test_pos_manager_is_not_a_payroll_approver(self):
        fake.get_roles.return_value = ["EsafePOS Manager", "System Manager"]
        self.assertFalse(hr.can_payroll())
        self.assertFalse(hr.can_approve())

    def test_payroll_user_cannot_approve(self):
        fake.get_roles.return_value = ["Payroll User"]
        with patch.object(hr.features, "enabled", return_value=True), self.assertRaises(PermissionError):
            hr._guard("Company", approve=True)

    def test_company_user_permission_is_enforced(self):
        with patch.object(hr.features, "enabled", return_value=True), patch.object(hr.permissions, "allowed_companies", return_value={"Other"}), self.assertRaises(PermissionError):
            hr._guard("Company")

    def test_employee_company_is_enforced(self):
        with self.assertRaises(PermissionError):
            hr._employee("Other", "EMP")

    def test_ordinary_cashier_cannot_mark_attendance(self):
        fake.get_roles.return_value = ["EsafePOS Cashier"]
        with self.assertRaises(PermissionError):
            hr._employee("Company", "EMP", manager=True)

    def test_staff_cannot_access_another_employee(self):
        fake.get_roles.return_value = ["Employee"]
        fake.get_doc.return_value.user_id = "other@example.com"
        with self.assertRaises(PermissionError):
            hr._employee("Company", "EMP")

    def test_hidden_payroll_source_blocks_incomplete_totals(self):
        row = types.SimpleNamespace(name="INV1")
        fake.get_all.return_value = [row]
        fake.get_doc.return_value.check_permission.side_effect = PermissionError("Hidden invoice")
        with self.assertRaises(PermissionError):
            hr._all("Sales Invoice", {}, ["name"])
        fake.get_doc.return_value.check_permission.side_effect = None

    def test_current_month_is_not_payable(self):
        with patch.object(hr, "_guard", return_value="LKR"), patch.object(hr, "_employee"), self.assertRaisesRegex(ValueError, "month has ended"):
            hr._calculate("Company", "EMP", "2026-11", "Commission")

    def test_retry_identity_rejects_different_claim_details(self):
        fake.get_meta.return_value.has_field.return_value = True
        fake.db.get_value.return_value = "CLAIM1"
        fake.get_doc.return_value.get.return_value = "old-hash"
        with self.assertRaisesRegex(ValueError, "different details"):
            hr._existing("Expense Claim", "identity", "new-hash")

    def test_attendance_retry_returns_existing_record(self):
        doc = Mock(docstatus=1)
        doc.name = "ATT1"
        with patch.object(hr, "_guard"), patch.object(hr, "_employee", return_value=Mock(status="Active")), \
             patch.object(hr, "_existing", return_value=doc):
            result = hr.mark_attendance("Company", "EMP", "2026-11-01", "Present", "Missed checkin", "a" * 20)
        self.assertEqual(result["name"], "ATT1")
        fake.get_doc.assert_not_called()

    def test_claim_retry_returns_existing_draft(self):
        doc = Mock(docstatus=0)
        doc.name = "CLAIM1"
        with patch.object(hr, "_guard"), patch.object(hr, "_employee"), patch.object(hr, "_existing", return_value=doc):
            result = hr.create_claim("Company", "EMP", "2026-11-01", "Travel", 100, "Bus", "a" * 20)
        self.assertEqual(result["name"], "CLAIM1")
        self.assertEqual(fake.get_doc.call_count, 1, "Only expense type is read; no second claim is created")

    def test_preview_never_creates_a_payroll_record(self):
        with patch.object(hr, "_calculate", return_value={"amount": 100}):
            self.assertEqual(hr.preview_payroll("Company", "EMP", "2026-10", "Commission")["amount"], 100)
        fake.get_doc.assert_not_called()

    def test_prepare_rejects_stale_preview(self):
        fake.db.get_value.return_value = None
        with patch.object(hr, "_guard"), patch.object(hr, "_calculate", return_value={"fingerprint": "changed"}), \
             patch.object(hr, "_save") as save, self.assertRaisesRegex(ValueError, "inputs changed"):
            hr.prepare_payroll("Company", "EMP", "2026-10", "Commission", "old")
        save.assert_not_called()

    def test_prepare_rejects_nonpositive_earnings(self):
        fake.db.get_value.return_value = None
        with patch.object(hr, "_guard"), patch.object(hr, "_calculate", return_value={"fingerprint": "fresh", "amount": -1}), self.assertRaisesRegex(ValueError, "positive earnings"):
            hr.prepare_payroll("Company", "EMP", "2026-10", "Commission", "fresh")

    def test_approved_period_retry_does_not_recreate_or_reprice(self):
        doc = self.batch()
        fake.db.get_value.return_value = "BATCH1"
        fake.get_doc.return_value = doc
        with patch.object(hr, "_guard"), patch.object(hr, "_calculate") as calculate:
            result = hr.prepare_payroll("Company", "EMP", "2026-10", "Commission", "stale")
        calculate.assert_not_called()
        self.assertEqual(result["name"], "BATCH1")

    def test_cross_company_batch_is_rejected(self):
        doc = self.batch()
        fake.get_doc.return_value = doc
        with patch.object(hr, "_guard"), self.assertRaises(PermissionError):
            hr._locked_batch("Other", "BATCH1")

    def test_post_requires_approval(self):
        with patch.object(hr, "_locked_batch", return_value=self.batch("Draft")), self.assertRaisesRegex(ValueError, "Approve"):
            hr.post_payroll("Company", "BATCH1")

    def test_post_retry_never_creates_another_salary(self):
        with patch.object(hr, "_locked_batch", return_value=self.batch("Posted")):
            result = hr.post_payroll("Company", "BATCH1")
        self.assertEqual(result["additional_salary"], "SAL1")
        fake.get_doc.assert_not_called()

    def test_changed_inputs_block_approval(self):
        doc = self.batch("Draft")
        with patch.object(hr, "_locked_batch", return_value=doc), patch.object(hr, "_calculate", return_value={"fingerprint": "changed"}), self.assertRaisesRegex(ValueError, "inputs changed"):
            hr.approve_payroll("Company", "BATCH1")
        self.assertEqual(doc.status, "Draft")

    def test_existing_salary_slip_blocks_late_earnings(self):
        fake.db.exists.return_value = True
        with patch.object(hr, "_locked_batch", return_value=self.batch()), patch.object(hr, "_fresh", return_value={"start": "2026-10-01", "end": "2026-10-31"}), self.assertRaisesRegex(ValueError, "Salary Slip already"):
            hr.post_payroll("Company", "BATCH1")
        fake.get_doc.assert_not_called()

    def test_native_additional_salary_is_submitted_once(self):
        doc = self.batch()
        fake.db.exists.return_value = False
        salary = Mock()
        salary.name = "ADS1"
        fake.get_doc.return_value = salary
        with patch.object(hr, "_locked_batch", return_value=doc), patch.object(hr, "_fresh", return_value={"start": "2026-10-01", "end": "2026-10-31", "component": "Sales Commission"}), patch.object(hr, "_save"):
            result = hr.post_payroll("Company", "BATCH1")
        salary.insert.assert_called_once_with()
        salary.submit.assert_called_once_with()
        payload = fake.get_doc.call_args.args[0]
        self.assertEqual(payload["ref_docname"], "BATCH1")
        self.assertEqual(payload["overwrite_salary_structure_amount"], 0)
        self.assertEqual(result["status"], "Posted")

    def test_posted_period_cannot_be_reopened(self):
        with patch.object(hr, "_locked_batch", return_value=self.batch("Posted")), self.assertRaisesRegex(ValueError, "stay locked"):
            hr.reopen_payroll("Company", "BATCH1")

    def test_native_salary_preview_rolls_back_controller_side_effects(self):
        doc = Mock()
        with patch.object(hr, "_new_salary_slip", return_value=doc), patch.object(hr, "_salary_data", return_value={"net_pay": 75000}), patch.object(hr, "_salary_fingerprint", return_value="native"):
            result = hr.preview_salary("Company", "EMP", "2026-10")
        self.assertEqual(result["net_pay"], 75000)
        fake.db.savepoint.assert_called_once_with("esafepos_hr_salary_preview")
        fake.db.rollback.assert_called_once_with(save_point="esafepos_hr_salary_preview")
        doc.insert.assert_not_called()
        doc.submit.assert_not_called()

    def test_commission_component_uses_native_account_field(self):
        account = types.SimpleNamespace(company="Company")
        account.get = lambda key: "Wages - CO" if key == "account" else None
        doc = Mock(type="Earning")
        doc.get.side_effect = lambda key: [account] if key == "accounts" else None
        fake.get_doc.return_value = doc
        self.assertIs(hr._component("Commission", "Company"), doc)

    def test_approved_month_blocks_reassigned_employee_or_changed_sources(self):
        fake.get_all.return_value = [types.SimpleNamespace(snapshot=json.dumps({"period_source_hash": "original"}))]
        with self.assertRaisesRegex(ValueError, "sources changed"):
            hr._assert_commission_period("Company", "2026-10", "reassigned")
        hr._assert_commission_period("Company", "2026-10", "original")

    def test_failed_native_salary_preview_also_rolls_back(self):
        with patch.object(hr, "_new_salary_slip", side_effect=ValueError("Native validation refused")), self.assertRaises(ValueError):
            hr.preview_salary("Company", "EMP", "2026-10")
        fake.db.rollback.assert_called_once_with(save_point="esafepos_hr_salary_preview")

    def test_native_salary_delegates_rules_to_salary_slip_controller(self):
        doc = Mock(salary_structure="Native Structure", start_date=date(2026, 10, 1), end_date=date(2026, 10, 31))
        fake.new_doc.return_value = doc
        with patch.object(hr, "_guard"), patch.object(hr, "_employee"):
            self.assertIs(hr._new_salary_slip("Company", "EMP", "2026-10"), doc)
        doc.run_method.assert_called_once_with("validate")
        payload = doc.update.call_args.args[0]
        self.assertEqual(payload["payroll_frequency"], "Monthly")
        self.assertNotIn("payment_days", payload)
        self.assertNotIn("daily_rate", payload)
        self.assertNotIn("earnings", payload)
        doc.insert.assert_not_called()

    def test_salary_draft_retry_returns_existing_without_recalculation(self):
        with patch.object(hr, "_guard"), patch.object(hr, "_employee"), patch.object(hr, "_existing", return_value=Mock()), patch.object(hr, "_salary_data", return_value={"name":"SLIP1"}), patch.object(hr, "_new_salary_slip") as calculate:
            result=hr.save_salary_draft("Company", "EMP", "2026-10", "native", "a"*20)
        calculate.assert_not_called()
        self.assertEqual(result["name"], "SLIP1")

    def test_salary_draft_rejects_overlapping_payroll(self):
        fake.db.exists.return_value = True
        with patch.object(hr, "_guard"), patch.object(hr, "_employee"), patch.object(hr, "_existing", return_value=None), self.assertRaisesRegex(ValueError, "already overlaps"):
            hr.save_salary_draft("Company", "EMP", "2026-10", "native", "a"*20)

    def test_salary_draft_rejects_changed_native_preview(self):
        fake.db.exists.return_value = False
        with patch.object(hr, "_guard"), patch.object(hr, "_employee"), patch.object(hr, "_existing", return_value=None), patch.object(hr, "_new_salary_slip"), patch.object(hr, "_salary_fingerprint", return_value="changed"), self.assertRaisesRegex(ValueError, "calculation changed"):
            hr.save_salary_draft("Company", "EMP", "2026-10", "native", "a"*20)

    def test_salary_draft_never_submits_or_pays(self):
        fake.db.exists.return_value = False
        doc=Mock()
        with patch.object(hr, "_guard"), patch.object(hr, "_employee"), patch.object(hr, "_existing", return_value=None), patch.object(hr, "_new_salary_slip", return_value=doc), patch.object(hr, "_salary_fingerprint", return_value="native"), patch.object(hr, "_salary_data", return_value={"name":"SLIP1"}):
            hr.save_salary_draft("Company", "EMP", "2026-10", "native", "a"*20)
        doc.insert.assert_called_once_with()
        doc.submit.assert_not_called()

    def test_feature_parent_dependency_and_hr_installation(self):
        data = {"enable_hr_integration": 1, "enable_attendance": 1, "enable_day_salary": 1}
        with patch.object(hr.features, "hrms_installed", return_value=True):
            self.assertTrue(hr.features.enabled("enable_day_salary", data))
            data["enable_attendance"] = 0
            self.assertFalse(hr.features.enabled("enable_day_salary", data))
        with patch.object(hr.features, "hrms_installed", return_value=False):
            self.assertFalse(hr.features.enabled("enable_hr_integration", data))


if __name__ == "__main__":
    unittest.main()
