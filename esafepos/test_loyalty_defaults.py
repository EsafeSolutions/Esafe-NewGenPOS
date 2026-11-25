"""Automatic enrollment and provisioning without a running ERPNext site."""
import datetime
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch


class Record(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__


class LoyaltyDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.frappe = ModuleType("frappe")
        self.frappe.db = Mock()
        self.frappe.db.get_default.return_value = None
        self.frappe.db.get_value.return_value = None
        self.frappe.get_all = Mock(return_value=[])
        self.frappe.get_cached_value = Mock(side_effect=lambda dt, name, field: "LKR" if field == "default_currency" else "Main - S")
        self.frappe.get_doc = Mock()
        self.frappe.get_single = Mock()
        self.frappe.get_meta = Mock(return_value=Record(has_field=lambda name: True))
        self.frappe.log_error = Mock()
        self.frappe.get_traceback = Mock(return_value="test error")
        self.utils = ModuleType("frappe.utils")
        self.utils.getdate = lambda value: datetime.date.fromisoformat(str(value))
        self.utils.nowdate = lambda: "2026-11-23"
        self.settings = ModuleType("esafepos.api.settings")
        self.settings._loyalty_expense_account = Mock(return_value="Loyalty Expense - S")
        self.patch = patch.dict(sys.modules, {"frappe": self.frappe, "frappe.utils": self.utils, "esafepos.api.settings": self.settings})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        spec = importlib.util.spec_from_file_location("loyalty_defaults_subject", Path(__file__).with_name("loyalty_defaults.py"))
        self.subject = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.subject)

    def program(self, **values):
        return Record(name="Rewards", from_date="2026-11-23", to_date="2026-11-23",
                      customer_group=None, customer_territory=None, conversion_factor=1, **values)

    def test_existing_and_new_customers_resolve_default_company_program(self):
        self.frappe.get_all.return_value = [self.program()]
        self.assertEqual(self.subject.program_for_customer("Existing", "Shop"), "Rewards")
        self.assertEqual(self.subject.program_for_customer("New", "Shop"), "Rewards")
        self.assertEqual(self.frappe.get_all.call_args.kwargs["filters"], {"company": "Shop", "auto_opt_in": 1})
        self.frappe.db.set_value.assert_not_called()

    def test_explicit_memberships_are_preserved_and_foreign_points_not_moved(self):
        self.frappe.db.get_value.side_effect = ["VIP", "Shop"]
        self.assertEqual(self.subject.program_for_customer("Existing", "Shop"), "VIP")
        self.frappe.db.get_value.side_effect = ["VIP", "Other"]
        self.assertIsNone(self.subject.program_for_customer("Existing", "Shop"))
        self.frappe.get_all.assert_not_called()

    def test_date_boundaries_territory_groups_and_one_to_one_preference(self):
        valid = self.program()
        for changes in ({"from_date": "2026-11-24"}, {"to_date": "2026-11-22"}, {"customer_group": "VIP"}, {"customer_territory": "North"}):
            self.frappe.get_all.return_value = [Record(valid, **changes)]
            self.assertIsNone(self.subject.default_program("Shop"))
        self.frappe.get_all.return_value = [Record(valid, name="Other rate", conversion_factor=0.5), valid]
        self.assertEqual(self.subject.default_program("Shop"), "Rewards")

    def test_migrate_creates_funded_auto_program_when_missing(self):
        self.frappe.get_all.side_effect = lambda dt, *a, **kw: ["Shop"] if dt == "POS Profile" else []
        self.subject.ensure_setup()
        program = self.frappe.get_doc.call_args.args[0]
        self.assertEqual(program["company"], "Shop")
        self.assertEqual(program["auto_opt_in"], 1)
        self.assertEqual(program["conversion_factor"], 1)
        self.assertEqual(program["expiry_duration"], 365)
        self.assertEqual(program["expense_account"], "Loyalty Expense - S")
        self.assertEqual(self.frappe.get_single.return_value.enable_loyalty_point_program, 1)
        self.frappe.db.set_default.assert_called_once_with("esafepos_default_loyalty_Shop", "1")

    def test_migrate_reuses_general_program_without_changing_rates(self):
        row = self.program()
        def query(fields=None, filters=None, pluck=None, **kwargs):
            if pluck == "company":
                self.assertEqual(filters, {"disabled": 0})
                return ["Shop"]
            if filters.get("conversion_factor") == 1:
                return [row]
            return []
        self.frappe.get_all.side_effect = lambda dt, *args, **kw: query(*args, **kw)
        self.subject.ensure_setup()
        self.frappe.db.set_value.assert_called_once_with("Loyalty Program", "Rewards", "auto_opt_in", 1)
        self.frappe.get_doc.assert_not_called()

    def test_later_migrations_preserve_administrators_switches(self):
        self.frappe.get_all.return_value = ["Shop"]
        self.frappe.db.get_default.return_value = "1"
        self.subject.ensure_setup()
        self.frappe.get_single.assert_not_called()
        self.frappe.get_doc.assert_not_called()

    def test_missing_program_setup_is_rolled_back_without_marking_complete(self):
        self.frappe.get_all.side_effect = lambda dt, *a, **kw: ["Shop"] if dt == "POS Profile" else []
        self.frappe.get_cached_value.side_effect = lambda dt, name, field: "LKR" if field == "default_currency" else None
        self.subject.ensure_setup()
        self.frappe.db.rollback.assert_called_once_with(save_point="esafepos_default_loyalty")
        self.frappe.db.set_default.assert_not_called()
        self.frappe.log_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
