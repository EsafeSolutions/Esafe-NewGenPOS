"""Saved change rules/accounting with document I/O mocked; no Frappe bench needed."""
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


def getdate(value=None):
    return datetime.date.fromisoformat(str(value or "2026-11-23"))


class LoyaltyChangeTests(unittest.TestCase):
    def setUp(self):
        self.frappe = ModuleType("frappe")
        self.frappe._ = lambda value: value
        def throw(message, *args, **kwargs):
            raise ValueError(message)
        self.frappe.throw = throw
        for name in ("get_doc", "get_meta", "get_cached_value", "get_all", "delete_doc"):
            setattr(self.frappe, name, Mock())
        self.frappe.db = Mock()
        self.frappe.session = Record(user="cashier")
        self.frappe.flags = Record(ignore_account_permission=False)
        self.frappe.get_cached_value.side_effect = lambda dt, name, field: "LKR" if dt == "Company" else "Cash"
        self.frappe.get_meta.side_effect = lambda dt: Record(has_field=lambda name: dt != "Accounts Settings")
        self.account = Record(company="Shop", account_currency="LKR", is_group=0, disabled=0,
                              root_type="Expense", account_type="Cash")
        self.center = Record(company="Shop", is_group=0)
        def get_value(dt, name, fields, **kwargs):
            if dt == "Account": return self.account
            if dt == "Cost Center": return self.center
            if dt == "POS Register Session": return "Open"
            if dt == "Mode of Payment Account": return "Cash - S"
        self.frappe.db.get_value.side_effect = get_value
        self.utils = ModuleType("frappe.utils")
        self.utils.cint = lambda n: int(n or 0)
        self.utils.flt = lambda n=0, p=None: round(float(n or 0), p) if p is not None else float(n or 0)
        self.utils.getdate = getdate
        self.utils.add_days = lambda value, n: str(getdate(value) + datetime.timedelta(days=n))
        self.utils.now_datetime = lambda: "2026-11-23 10:00:00"
        self.compat = ModuleType("esafepos.erpnext_compat")
        self.details = Record(loyalty_program="Rewards", company="Shop", conversion_factor=1,
                              from_date="2026-01-01", to_date="2026-12-31", expense_account="Rewards - S",
                              cost_center="Main - S", expiry_duration=365, tier_name="Standard")
        self.compat.loyalty_details = Mock(return_value=self.details)
        self.credit = ModuleType("esafepos.credit_sales")
        self.credit._dimensions = lambda invoice: {"branch": "Colombo"}
        self.credit.post = Mock(return_value="JE-POINTS-1")
        self.register_api = ModuleType("esafepos.api.register")
        self.register_api._drawer_mode = Mock(return_value="Cash")
        self.modules = patch.dict(sys.modules, {"frappe": self.frappe, "frappe.utils": self.utils,
            "esafepos.erpnext_compat": self.compat, "esafepos.credit_sales": self.credit,
            "esafepos.api.register": self.register_api})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        spec = importlib.util.spec_from_file_location("loyalty_change_test_subject", Path(__file__).with_name("loyalty_change.py"))
        self.subject = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.subject)
        self.invoice = Record(doctype="POS Invoice", name="POS-1", customer="CUSTOMER", company="Shop",
            pos_profile="Till", esafepos_session="SHIFT", posting_date="2026-11-23", currency="LKR",
            conversion_rate=1, rounded_total=1602, grand_total=1602, change_amount=8,
            account_for_change_amount="Cash - S", payments=[Record(mode_of_payment="Cash", amount=1610)])
        self.invoice.db_set = Mock(side_effect=self.set_invoice)
        self.payload = {"customer": "CUSTOMER", "loyalty_change_amount": 8,
                        "payments": [{"mode_of_payment": "Cash", "amount": 1610}]}
        self.profile = Record(company="Shop")

    def set_invoice(self, key, value=None):
        self.invoice.update(key if isinstance(key, dict) else {key: value})

    def test_setup_uses_erpnext_program_at_one_rupee_per_point(self):
        self.assertTrue(self.subject.setup(self.details, "Shop")["enabled"])
        self.details.conversion_factor = 0.5
        self.assertIn("conversion factor to 1", self.subject.setup(self.details, "Shop")["reason"])

    def test_setup_rejects_missing_foreign_company_expired_or_future_program(self):
        self.assertFalse(self.subject.setup(None, "Shop")["enabled"])
        for changes in ({"company": "Other"}, {"from_date": "2027-01-01"},
                        {"to_date": "2026-11-22"}, {"expense_account": ""}, {"cost_center": ""}):
            with self.subTest(changes=changes):
                self.assertFalse(self.subject.setup(Record(self.details, **changes), "Shop")["enabled"])

    def test_setup_accepts_program_date_boundaries(self):
        for date in ("2026-01-01", "2026-12-31"):
            self.assertTrue(self.subject.setup(self.details, "Shop", date)["enabled"])

    def test_setup_rejects_invalid_account_and_cost_center(self):
        for key, value in (("company", "Other"), ("disabled", 1), ("is_group", 1),
                           ("account_currency", "USD"), ("root_type", "Liability")):
            original = self.account.copy()
            self.account[key] = value
            self.assertFalse(self.subject.setup(self.details, "Shop")["enabled"])
            self.account.update(original)
        self.center.company = "Other"
        self.assertFalse(self.subject.setup(self.details, "Shop")["enabled"])

    def test_setup_honors_accounts_settings_loyalty_switch_and_required_migration(self):
        self.frappe.get_meta.side_effect = lambda dt: Record(has_field=lambda name: True)
        self.frappe.db.get_single_value.return_value = 0
        self.assertIn("Enable", self.subject.setup(self.details, "Shop")["reason"])
        self.frappe.get_meta.side_effect = lambda dt: Record(has_field=lambda name: False)
        self.assertIn("migrate", self.subject.setup(self.details, "Shop")["reason"])

    def test_prepare_converts_example_eight_rupee_change(self):
        self.assertEqual(self.subject.prepare(self.invoice, self.profile, self.payload)["amount"], 8)
        self.frappe.db.sql.assert_called_once()

    def test_prepare_rejects_fractional_negative_and_nonfinite_amounts(self):
        for raw in (0.5, -1, "nan", "inf", "bad", True):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(ValueError, "whole LKR"):
                    self.subject.prepare(self.invoice, self.profile, dict(self.payload, loyalty_change_amount=raw))

    def test_prepare_cannot_exceed_authoritative_change_or_cash_tender(self):
        with self.assertRaisesRegex(ValueError, "cash change"):
            self.subject.prepare(self.invoice, self.profile, dict(self.payload, loyalty_change_amount=9))
        self.invoice.payments = [Record(mode_of_payment="Cash", amount=1), Record(mode_of_payment="Card", amount=1609)]
        self.frappe.get_cached_value.side_effect = lambda dt, name, field: "LKR" if dt == "Company" else name
        with self.assertRaisesRegex(ValueError, "cash change"):
            self.subject.prepare(self.invoice, self.profile, self.payload)

    def test_prepare_leaves_fractional_cash_change(self):
        self.invoice.rounded_total = self.invoice.grand_total = 1601.75
        self.assertEqual(self.subject.prepare(self.invoice, self.profile, self.payload)["amount"], 8)

    def test_prepare_requires_customer_connection_local_sale_and_no_exchange(self):
        for values in ({"customer": None}, {"queued_offline": 1}, {"is_exchange": 1}):
            with self.assertRaises(ValueError):
                self.subject.prepare(self.invoice, self.profile, dict(self.payload, **values))
        self.invoice.currency = "USD"
        with self.assertRaisesRegex(ValueError, "LKR"):
            self.subject.prepare(self.invoice, self.profile, self.payload)

    def test_prepare_rejects_credit_sale_and_unconfigured_program(self):
        with self.assertRaisesRegex(ValueError, "on account"):
            self.subject.prepare(self.invoice, self.profile, dict(self.payload, payments=[{"mode_of_payment": "Credit Sale", "amount": 1}]))
        self.details.conversion_factor = 2
        with self.assertRaisesRegex(ValueError, "conversion factor"):
            self.subject.prepare(self.invoice, self.profile, self.payload)

    def test_no_selection_has_no_side_effects(self):
        self.assertIsNone(self.subject.prepare(self.invoice, self.profile, {}))
        self.subject.book(self.invoice, None)
        self.frappe.get_doc.assert_not_called()

    def documents(self):
        self.docs = []
        self.register = Mock()
        self.register.cash_movements = [Record(loyalty_change_entry="JE-POINTS-1"), Record(reason="Float")]
        self.journal = Mock(flags=Record())
        def get_doc(value, name=None):
            if value == "POS Register Session": return self.register
            if value == "Journal Entry": return self.journal
            self.docs.append(value)
            return Mock()
        self.frappe.get_doc.side_effect = get_doc

    def test_book_funds_native_points_and_correct_drawer_without_extra_purchase_rewards(self):
        self.documents()
        self.subject.book(self.invoice, {"amount": 8, "details": self.details})
        journal, points = self.docs
        self.assertEqual(journal["accounts"][0]["account"], "Cash - S")
        self.assertEqual(journal["accounts"][0]["debit_in_account_currency"], 8)
        self.assertEqual(journal["accounts"][1]["account"], "Rewards - S")
        self.assertEqual(journal["accounts"][1]["credit_in_account_currency"], 8)
        self.assertEqual(journal["accounts"][1]["branch"], "Colombo")
        self.assertEqual(points["loyalty_points"], 8)
        self.assertEqual(points["purchase_amount"], 0)
        self.assertEqual(points["invoice_type"], "Journal Entry")
        self.assertEqual(points["expiry_date"], "2027-11-23")
        self.assertEqual(self.invoice.esafepos_loyalty_change_entry, "JE-POINTS-1")
        self.assertEqual(self.register.append.call_args.args[1]["amount"], 8)
        self.register.save.assert_called_once_with(ignore_permissions=True)

    def test_book_rechecks_final_change_and_drawer_mapping(self):
        self.invoice.change_amount = 7
        with self.assertRaisesRegex(ValueError, "final change"):
            self.subject.book(self.invoice, {"amount": 8, "details": self.details})
        self.invoice.change_amount = 8
        self.invoice.account_for_change_amount = "Other"
        with self.assertRaisesRegex(ValueError, "Account for Change"):
            self.subject.book(self.invoice, {"amount": 8, "details": self.details})

    def test_legacy_redemption_deducts_only_remaining_funded_points(self):
        self.documents()
        self.invoice.update(redeem_loyalty_points=1, loyalty_points=3, loyalty_program="Rewards")
        self.frappe.get_all.side_effect = [[], [Record(name="LOT", loyalty_points=8,
            expiry_date="2027-11-23", loyalty_program_tier="Standard")], [Record(loyalty_points=-5)]]
        self.subject.complete_redemption(self.invoice)
        self.assertEqual(self.docs[0]["loyalty_points"], -3)
        self.assertEqual(self.docs[0]["redeem_against"], "LOT")

    def test_redemption_does_not_duplicate_native_erpnext_entries(self):
        self.invoice.update(redeem_loyalty_points=1, loyalty_points=3)
        self.frappe.get_all.return_value = [Record(loyalty_points=-3)]
        self.subject.complete_redemption(self.invoice)
        self.frappe.get_doc.assert_not_called()

    def test_incomplete_native_redemption_refuses_sale(self):
        self.invoice.update(redeem_loyalty_points=1, loyalty_points=3)
        self.frappe.get_all.side_effect = [[], []]
        with self.assertRaisesRegex(ValueError, "could not deduct"):
            self.subject.complete_redemption(self.invoice)

    def test_cancel_removes_funding_points_and_drawer_movement_together(self):
        self.documents()
        self.invoice.esafepos_loyalty_change_entry = "JE-POINTS-1"
        self.frappe.get_all.return_value = ["LOT"]
        self.frappe.db.exists.return_value = False
        self.subject.cancel_invoice(self.invoice)
        self.frappe.delete_doc.assert_called_once_with("Loyalty Point Entry", "LOT", ignore_permissions=True)
        self.journal.cancel.assert_called_once()
        self.assertEqual(len(self.register.set.call_args.args[1]), 1)
        self.assertEqual(self.invoice.esafepos_loyalty_change_amount, 0)

    def test_cancel_cannot_remove_spent_points(self):
        self.invoice.esafepos_loyalty_change_entry = "JE-POINTS-1"
        self.frappe.get_all.return_value = ["LOT"]
        self.frappe.db.exists.return_value = True
        with self.assertRaisesRegex(ValueError, "spent this saved change"):
            self.subject.cancel_invoice(self.invoice)
        self.frappe.delete_doc.assert_not_called()

    def test_closed_register_cancellation_preserves_points_and_funding(self):
        self.invoice.esafepos_loyalty_change_entry = "JE-POINTS-1"
        self.frappe.db.get_value.side_effect = None
        self.frappe.db.get_value.return_value = "Closed"
        with self.assertRaisesRegex(ValueError, "register"):
            self.subject.cancel_invoice(self.invoice)
        self.frappe.delete_doc.assert_not_called()
        self.invoice.db_set.assert_not_called()

    def test_no_expiry_program_preserves_nonexpiring_saved_points(self):
        self.documents()
        self.details.expiry_duration = 0
        self.subject.book(self.invoice, {"amount": 8, "details": self.details})
        self.assertEqual(self.docs[1]["expiry_date"], "9999-12-31")

    def test_return_does_not_reverse_saved_cash(self):
        self.invoice.update(is_return=1, esafepos_loyalty_change_entry="JE-POINTS-1")
        self.subject.cancel_invoice(self.invoice)
        self.frappe.db.sql.assert_not_called()

    def test_direct_funding_cancellation_is_refused(self):
        self.frappe.db.exists.return_value = True
        with self.assertRaisesRegex(ValueError, "original POS sale"):
            self.subject.guard_funding_cancel(Record(name="JE-POINTS-1"))


if __name__ == "__main__":
    unittest.main()
