import sqlite3
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from esafepos import walk_in


class ReceiptContactTests(unittest.TestCase):
    def test_sale_contact_sets_phone_and_display_name_for_walk_in(self):
        invoice = {"customer": walk_in.FALLBACK_CUSTOMER}
        walk_in.apply_sale_contact(invoice, None, "077-123 4567")
        self.assertEqual(invoice, {
            "customer": walk_in.FALLBACK_CUSTOMER,
            "esafepos_walk_in_name": "0771234567",
            "esafepos_walk_in_phone": "0771234567",
        })

    def test_sale_contact_does_not_override_selected_customer(self):
        invoice = {"customer": "Example Customer"}
        walk_in.apply_sale_contact(invoice, "Example Customer", "0771234567")
        self.assertEqual(invoice, {"customer": "Example Customer"})

    def test_accepts_formatted_phone_and_preserves_leading_zero_or_country_code(self):
        self.assertEqual(walk_in.contact_number(" 077-123 4567 "), "0771234567")
        self.assertEqual(walk_in.contact_number("+94 (77) 123 4567"), "+94771234567")

    def test_rejects_missing_or_invalid_contact_number(self):
        for value in ("", "07712", "077CALLNOW", "0771234\n567", "0" * 16):
            with self.subTest(value=value):
                self.assertEqual(walk_in.contact_number(value), "")

    def test_receipt_uses_phone_until_someone_saves_a_name(self):
        doc = {"customer_name": "Customer"}
        self.assertEqual(walk_in.receipt_customer_name(doc), "Customer")
        doc["esafepos_walk_in_code"] = "W-1234"
        self.assertEqual(walk_in.receipt_customer_name(doc), "W-1234")
        doc.update(esafepos_walk_in_name="0771234567", esafepos_walk_in_phone="0771234567")
        self.assertEqual(walk_in.receipt_customer_name(doc), "0771234567")
        self.assertEqual(walk_in.receipt_custom_name(doc), "")
        doc["esafepos_walk_in_name"] = "Customer entered later"
        self.assertEqual(walk_in.receipt_customer_name(doc), "Customer entered later")
        doc.pop("esafepos_walk_in_code")
        self.assertEqual(walk_in.receipt_customer_name(doc), "Customer entered later")
        self.assertEqual(walk_in.receipt_custom_name(doc), "Customer entered later")


class ReceiptCustomerAttributionTests(unittest.TestCase):
    def test_linked_sale_and_refund_move_between_pos_customer_profiles_once(self):
        with sqlite3.connect(":memory:") as db:
            db.execute("""create table `tabPOS Invoice` (
                name text primary key, customer text, esafepos_receipt_customer text,
                is_return int, return_against text
            )""")
            db.executemany("insert into `tabPOS Invoice` values (?, ?, ?, ?, ?)", [
                ("sale", "Walk-in", "Member", 0, None),
                ("refund", "Walk-in", None, 1, "sale"),
                ("anonymous", "Walk-in", "", 0, None),
                ("named", "Member", None, 0, None),
            ])
            with patch.object(walk_in.frappe, "db", Mock()):
                join, _, predicate = walk_in.customer_attribution_sql("POS Invoice")
            query = (f"select pi.name from `tabPOS Invoice` pi {join} where {predicate}"
                     .replace("%(customer)s", ":customer"))
            self.assertEqual({r[0] for r in db.execute(query, {"customer": "Member"})}, {"sale", "refund", "named"})
            self.assertEqual({r[0] for r in db.execute(query, {"customer": "Walk-in"})}, {"anonymous"})

    def test_reporting_uses_billing_customer_when_link_field_is_missing(self):
        db = Mock()
        db.has_column.return_value = False
        with patch.object(walk_in.frappe, "db", db):
            self.assertEqual(walk_in.customer_attribution_sql("Sales Invoice"),
                             ("", "null", "pi.customer = %(customer)s"))


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
