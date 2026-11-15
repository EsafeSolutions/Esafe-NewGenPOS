import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from esafepos import walk_in


class WalkInBillingTests(unittest.TestCase):
    def setUp(self):
        self.profile = SimpleNamespace(customer=None)
        self.db = Mock()
        self.db.get_single_value.return_value = 1
        self.db.get_value.return_value = walk_in.FALLBACK_CUSTOMER
        db_patch = patch.object(walk_in.frappe, "db", self.db)
        db_patch.start()
        self.addCleanup(db_patch.stop)

    def test_selected_customer_takes_precedence(self):
        self.profile.customer = "Outlet Walk-in"
        self.assertEqual(walk_in.billing_customer(self.profile, "Named Customer"), "Named Customer")
        self.db.get_value.assert_not_called()

    def test_outlet_default_takes_precedence(self):
        self.profile.customer = "Outlet Walk-in"
        self.assertEqual(walk_in.billing_customer(self.profile, None), "Outlet Walk-in")
        self.db.get_value.assert_not_called()

    def test_enabled_uses_shared_customer_without_an_outlet_default(self):
        self.assertEqual(walk_in.billing_customer(self.profile, None), walk_in.FALLBACK_CUSTOMER)
        self.db.get_value.assert_called_once_with(
            "Customer", {"name": walk_in.FALLBACK_CUSTOMER, "disabled": 0}
        )

    def test_disabled_requires_customer_when_outlet_has_no_default(self):
        self.db.get_single_value.return_value = 0
        with self.assertRaisesRegex(walk_in.frappe.ValidationError, "Select a customer"):
            walk_in.billing_customer(self.profile, None)
        self.db.get_value.assert_not_called()

    def test_enabled_with_missing_fallback_explains_how_to_restore_it(self):
        self.db.get_value.return_value = None
        with self.assertRaisesRegex(walk_in.frappe.ValidationError, "automatic walk-in customer is unavailable"):
            walk_in.billing_customer(self.profile, None)

    def test_only_enabled_anonymous_sales_receive_individual_receipt_codes(self):
        meta = SimpleNamespace(has_field=lambda field: field == "esafepos_walk_in_code")
        first = SimpleNamespace(meta=meta)
        second = SimpleNamespace(meta=meta)
        named = SimpleNamespace(meta=meta)
        with patch.object(walk_in.secrets, "token_hex", side_effect=["1" * 16, "2" * 16]):
            walk_in.assign_receipt_code(first, None)
            walk_in.assign_receipt_code(second, walk_in.FALLBACK_CUSTOMER)
            walk_in.assign_receipt_code(named, "Named Customer")
        self.assertEqual(first.esafepos_walk_in_code, "W-" + "1" * 16)
        self.assertEqual(second.esafepos_walk_in_code, "W-" + "2" * 16)
        self.assertFalse(hasattr(named, "esafepos_walk_in_code"))
        self.db.get_single_value.return_value = 0
        disabled = SimpleNamespace(meta=meta)
        walk_in.assign_receipt_code(disabled, None)
        self.assertFalse(hasattr(disabled, "esafepos_walk_in_code"))

    def test_provisioning_leaves_existing_customer_record_as_it_is(self):
        self.db.exists.return_value = walk_in.FALLBACK_CUSTOMER
        with patch.object(walk_in.frappe, "get_doc") as get_doc:
            walk_in.ensure_customer()
        get_doc.assert_not_called()

    def test_provisioning_creates_one_shared_customer_without_contact_details(self):
        self.db.exists.return_value = None
        customer = Mock(loyalty_program="Automatic loyalty", meta=SimpleNamespace(fields=[]))
        catalog = SimpleNamespace(_customer_group=lambda *_args: "Retail")
        settings = SimpleNamespace(customer_group="Retail", territory="Sri Lanka")
        with patch.dict(sys.modules, {"esafepos.api.catalog": catalog}), \
                patch.object(walk_in.frappe, "get_cached_doc", return_value=settings), \
                patch.object(walk_in.frappe, "get_doc", return_value=customer) as get_doc:
            walk_in.ensure_customer()
        get_doc.assert_called_once_with({
            "doctype": "Customer", "customer_name": walk_in.FALLBACK_CUSTOMER,
            "customer_type": "Individual", "customer_group": "Retail", "territory": "Sri Lanka",
        })
        customer.insert.assert_called_once_with(ignore_permissions=True, set_name=walk_in.FALLBACK_CUSTOMER)
        customer.db_set.assert_called_once_with({"loyalty_program": None, "loyalty_program_tier": None})
