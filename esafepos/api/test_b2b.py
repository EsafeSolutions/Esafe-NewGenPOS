"""B2B financial boundaries with native document I/O injected at the edge.

Run with python -m unittest esafepos.api.test_b2b; no Frappe bench required.
Native GL/stock posting is deliberately a separate staging-site acceptance test.
"""
import ast
from datetime import date, datetime
import importlib
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from esafepos.b2b_rules import allocate, cheque_transition, line_discount, number, progress


class Doc:
    def __init__(self, **values):
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "meta", SimpleNamespace(has_field=lambda field: True, get_table_fields=lambda: []))
        object.__setattr__(self, "flags", DocFlags())
        object.__setattr__(self, "check_permission", Mock())
        object.__setattr__(self, "has_permission", Mock(return_value=True))
        object.__setattr__(self, "insert", Mock(side_effect=lambda **kwargs: self))
        object.__setattr__(self, "save", Mock(side_effect=lambda **kwargs: self))
        object.__setattr__(self, "submit", Mock(side_effect=lambda: self.set("docstatus", 1)))
        object.__setattr__(self, "cancel", Mock(side_effect=lambda: self.set("docstatus", 2)))

    def __getattr__(self, key):
        return self.values.get(key)

    def __setattr__(self, key, value):
        self.values[key] = value

    def get(self, key, default=None):
        return self.values.get(key, default)

    def __getitem__(self, key):
        return self.values[key]

    def keys(self):
        return self.values.keys()

    def set(self, key, value):
        self.values[key] = value
        return self

    def append(self, key, value):
        child = Doc(**value)
        self.values.setdefault(key, []).append(child)
        return child

    def as_dict(self):
        return self.values.copy()

    def run_method(self, method):
        if method == "set_missing_values":
            for row in self.get("items") or []:
                row.rate, row.price_list_rate, row.item_name = 80, 100, "Feed"
        if method == "calculate_taxes_and_totals":
            for row in self.get("items") or []:
                row.amount = row.rate * row.qty
            self.net_total = self.grand_total = sum(row.amount for row in self.get("items") or [])
            self.total_taxes_and_charges = 0


class DocFlags:
    def get(self, name):
        return getattr(self, name, None)


class RulesTests(unittest.TestCase):
    def test_money_is_allocated_without_float_drift(self):
        rows = [dict(name="A", outstanding_amount="0.1", currency="LKR", debit_to="Debtors"),
                dict(name="B", outstanding_amount="0.2", currency="LKR", debit_to="Debtors")]
        refs, excess = allocate(rows, "0.30")
        self.assertEqual([row["allocated_amount"] for row in refs], [0.1, 0.2])
        self.assertEqual(excess, 0)

    def test_selected_amounts_and_opted_in_excess(self):
        rows = [dict(name="A", outstanding_amount=100)]
        refs, excess = allocate(rows, 80, [{"name": "A", "amount": 50}], allow_advance=True)
        self.assertEqual(refs[0]["allocated_amount"], 50)
        self.assertEqual(excess, 30)
        with self.assertRaises(ValueError):
            allocate(rows, 80, [{"name": "A", "amount": 50}])

    def test_invalid_money_and_quantity(self):
        for value in ("NaN", "Infinity", "-Infinity", "1e9999", -1, None, "garbage"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                number(value)
        with self.assertRaises(ValueError):
            number(0, positive=True)

    def test_stale_duplicate_and_overallocated_invoices(self):
        rows = [dict(name="A", outstanding_amount=10)]
        for selected in ([{"name": "MISSING"}], [{"name": "A"}, {"name": "A"}], [{"name": "A", "amount": 11}]):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                allocate(rows, 20, selected, True)

    def test_mixed_receivable_accounts_are_rejected(self):
        with self.assertRaises(ValueError):
            allocate([dict(name="A", outstanding_amount=10, debit_to="One"), dict(name="B", outstanding_amount=10, debit_to="Two")], 20)

    def test_deposit_without_invoices(self):
        self.assertEqual(allocate([], 50, allow_advance=True), ([], 50))
        with self.assertRaises(ValueError):
            allocate([], 50)

    def test_percent_and_per_unit_amount_are_equivalent(self):
        self.assertEqual(line_discount(80, "Percent", 25), line_discount(80, "Amount", 20))
        self.assertEqual(line_discount(0, "Percent", 100)["rate"], 0)
        for method, value in (("Percent", 101), ("Amount", 81), ("Unknown", 10)):
            with self.assertRaises(ValueError):
                line_discount(80, method, value)

    def test_cheque_state_machine_and_terminal_states(self):
        self.assertEqual(cheque_transition("Received", "deposit"), "Deposited")
        self.assertEqual(cheque_transition("Deposited", "clear"), "Cleared")
        self.assertEqual(cheque_transition("Cleared", "bounce"), "Bounced")
        for state, action in (("Received", "clear"), ("Cleared", "clear"), ("Bounced", "deposit"), ("Cancelled", "clear")):
            with self.assertRaises(ValueError):
                cheque_transition(state, action)

    def test_direct_paid_stock_invoice_completes_without_quote_or_order(self):
        result = progress([dict(doctype="Sales Invoice", docstatus=1, update_stock=1, has_stock_items=True)], 0)
        self.assertTrue(result["complete"])
        self.assertEqual(result["stages"][0]["state"], "Skipped")

    def test_pending_cheque_and_partial_delivery_prevent_completion(self):
        docs = [dict(doctype="Sales Order", docstatus=1, has_stock_items=True, per_delivered=50, per_billed=100),
                dict(doctype="Sales Invoice", docstatus=1, has_stock_items=True)]
        result = progress(docs, 0, pending_cheques=1)
        self.assertFalse(result["complete"])
        self.assertEqual(result["stages"][2]["state"], "In progress")
        self.assertEqual(result["stages"][-1]["state"], "In progress")

    def test_stock_invoice_without_delivery_is_incomplete(self):
        self.assertFalse(progress([dict(doctype="Sales Invoice", docstatus=1, has_stock_items=True)], 0)["complete"])

    def test_draft_and_cancelled_documents_do_not_complete_sales(self):
        for status in (0, 2):
            self.assertFalse(progress([dict(doctype="Sales Invoice", docstatus=status)], 0)["complete"])


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.frappe = ModuleType("frappe")
        self.frappe._ = lambda text: text
        self.frappe.whitelist = lambda *args, **kwargs: lambda function: function
        self.frappe.PermissionError = PermissionError
        self.frappe.throw = Mock(side_effect=lambda message, error=ValueError, **kwargs: self.raise_error(message, error))
        self.frappe.db = Mock()
        self.frappe.db.get_value.return_value = None
        self.frappe.db.exists.return_value = False
        self.frappe.session = SimpleNamespace(user="Manager")
        self.frappe.has_permission = Mock(return_value=True)
        self.frappe.get_meta = Mock(return_value=SimpleNamespace(has_field=lambda field: True))
        self.frappe.get_list = Mock(return_value=[])
        self.frappe.get_all = Mock(return_value=[])
        utils = ModuleType("frappe.utils")
        utils.cint = lambda value: int(value or 0)
        utils.flt = lambda value, precision=None: round(float(value or 0), precision) if precision is not None else float(value or 0)
        utils.getdate = lambda value=None: date.fromisoformat(str(value or "2026-11-27")[:10])
        utils.nowdate = lambda: "2026-11-27"
        utils.now_datetime = lambda: datetime(2026, 11, 27, 12)
        permission = ModuleType("esafepos.api.permissions")
        permission.assert_outlet = Mock()
        permission.can_use_outlet = Mock(return_value=True)
        permission.can_take_customer_payments = Mock(return_value=True)
        permission.can_edit_price = Mock(return_value=True)
        permission.allowed_companies = Mock(return_value=None)
        feature = ModuleType("esafepos.features")
        feature.enabled = Mock(return_value=True)
        self.permission, self.feature = permission, feature
        modules = {"frappe": self.frappe, "frappe.utils": utils, "esafepos.api.permissions": permission, "esafepos.features": feature}
        self.patcher = patch.dict(sys.modules, modules)
        self.patcher.start()
        import esafepos.api as api
        self.api_permissions = getattr(api, "permissions", None)
        api.permissions = permission
        importlib.reload(importlib.import_module("esafepos.erpnext_compat"))
        self.b2b = importlib.reload(importlib.import_module("esafepos.api.b2b"))
        self.payments = importlib.reload(importlib.import_module("esafepos.api.b2b_payments"))
        self.profile = Doc(name="Outlet", company="Company", warehouse="Stores", selling_price_list="Retail", allow_rate_change=1)
        self.context = patch.object(self.b2b, "context", return_value=(self.profile, "LKR"))
        self.context.start()
        self.pay_context = patch.object(self.payments, "context", return_value=(self.profile, "LKR"))
        self.pay_context.start()
        self.precision = patch.object(self.payments, "_precision", return_value=2)
        self.precision.start()

    @staticmethod
    def raise_error(message, error):
        raise error(message)

    def tearDown(self):
        self.context.stop()
        self.pay_context.stop()
        self.precision.stop()
        self.patcher.stop()
        import esafepos.api as api
        if self.api_permissions is None:
            if hasattr(api, "permissions"):
                del api.permissions
        else:
            api.permissions = self.api_permissions

    def test_document_company_and_outlet_boundaries(self):
        invoice = Doc(doctype="Sales Invoice", name="INV", company="Other", customer="Customer", currency="LKR")
        self.frappe.get_doc = Mock(return_value=invoice)
        with self.assertRaises(PermissionError):
            self.b2b.document("Outlet", "Sales Invoice", "INV")
        invoice.company, invoice.esafepos_b2b_profile = "Company", "Other outlet"
        with patch.object(self.b2b, "customer_doc", return_value=Doc()):
            with self.assertRaises(ValueError):
                self.b2b.document("Outlet", "Sales Invoice", "INV", "write")
            self.b2b.document("Outlet", "Sales Invoice", "INV")
        self.permission.assert_outlet.assert_called_with("Other outlet")

    def test_foreign_pos_and_return_documents_are_view_only(self):
        for values in ({"currency": "USD"}, {"is_pos": 1}, {"is_return": 1}):
            invoice = Doc(doctype="Sales Invoice", company="Company", customer="C", currency="LKR")
            invoice.values.update(values)
            self.frappe.get_doc = Mock(return_value=invoice)
            with patch.object(self.b2b, "customer_doc", return_value=Doc()), self.assertRaises(ValueError):
                self.b2b.document("Outlet", "Sales Invoice", "INV", "write")
            with patch.object(self.b2b, "document", return_value=invoice), self.assertRaises(ValueError):
                self.b2b.convert_document("Outlet", "Sales Invoice", "INV", "Delivery Note", "retry-identity-12345")

    def test_disabled_document_types_cannot_be_opened(self):
        self.frappe.get_doc = Mock(return_value=Doc(name="DISABLED", disabled=1))
        self.assertEqual(self.b2b.customer_doc("DISABLED").name, "DISABLED")
        with self.assertRaises(ValueError):
            self.b2b.customer_doc("DISABLED", for_sale=True)
        self.feature.enabled.return_value = False
        with self.assertRaises(PermissionError):
            self.b2b.document("Outlet", "Sales Order", "SO")

    def test_submit_detects_stale_draft_and_reviewed_total(self):
        rounded = self.b2b.serialize(Doc(doctype="Sales Invoice", items=[], taxes=[], grand_total=100.02, rounded_total=100,
                                        rounding_adjustment=-0.02, disable_rounded_total=0))
        self.assertEqual(rounded["payable_total"], 100)
        self.assertEqual(rounded["rounding_adjustment"], -0.02)
        invoice = Doc(docstatus=0, modified="new", grand_total=100)
        with patch.object(self.b2b, "document", return_value=invoice):
            with self.assertRaises(ValueError):
                self.b2b.submit_document("Outlet", "Sales Invoice", "INV", "old", 100)
            with self.assertRaises(ValueError):
                self.b2b.submit_document("Outlet", "Sales Invoice", "INV", "new", 99)
        invoice.submit.assert_not_called()

    def test_submit_retry_does_not_submit_again(self):
        invoice = Doc(docstatus=1)
        with patch.object(self.b2b, "document", return_value=invoice), patch.object(self.b2b, "serialize", return_value={"name": "INV"}):
            self.assertEqual(self.b2b.submit_document("Outlet", "Sales Invoice", "INV", "old", 100), {"name": "INV"})
        invoice.submit.assert_not_called()

    def test_creation_retry_returns_existing_document_before_building(self):
        with patch.object(self.b2b, "lock_customer"), patch.object(self.b2b, "previous", return_value=Doc()), patch.object(self.b2b, "serialize", return_value={"name": "INV"}), patch.object(self.b2b, "_prepare") as build:
            self.assertEqual(self.b2b.save_document("Outlet", {"doctype": "Sales Invoice", "customer": "C", "items": []}, "retry-identity-12345"), {"name": "INV"})
            build.assert_not_called()

    def test_draft_update_retry_returns_saved_result_despite_old_timestamp(self):
        payload = {"doctype": "Sales Invoice", "name": "INV", "customer": "C", "modified": "old", "items": []}
        key, fingerprint = self.b2b.identity("retry-identity-12345", payload)
        doc = Doc(esafepos_b2b_last_key=key, esafepos_b2b_last_hash=fingerprint, modified="new")
        with patch.object(self.b2b, "lock_customer"), patch.object(self.b2b, "document", return_value=doc), patch.object(self.b2b, "serialize", return_value={"name": "INV"}), patch.object(self.b2b, "_prepare") as prepare:
            self.assertEqual(self.b2b.save_document("Outlet", payload, "retry-identity-12345"), {"name": "INV"})
            prepare.assert_not_called()

    def test_payment_permissions_and_currency_precision_are_enforced(self):
        self.frappe.has_permission.return_value = False
        with self.assertRaises(PermissionError):
            self.payments._pay_context("Outlet")
        with self.assertRaises(ValueError):
            self.payments._amount("1.001", "LKR")
        self.assertEqual(self.payments._amount("1.20", "LKR"), 1.2)

    def test_expired_quotation_cannot_convert(self):
        source = Doc(name="QUOTE", docstatus=1, currency="LKR", valid_till="2026-11-20")
        with patch.object(self.b2b, "document", return_value=source), patch.object(self.b2b, "previous", return_value=None), self.assertRaises(ValueError):
            self.b2b.convert_document("Outlet", "Quotation", "QUOTE", "Sales Order", "retry-identity-12345")

    def test_partial_delivery_mapping_uses_delivery_item_reference(self):
        source = Doc(name="DN", docstatus=1, currency="LKR")
        mapped = Doc(doctype="Sales Invoice", name="DRAFT", items=[Doc(qty=6, rate=100, dn_detail="DN-LINE", so_detail="SO-LINE")])
        mapper = Mock(return_value=mapped)
        with patch.object(self.b2b, "document", return_value=source), patch.object(self.b2b, "previous", return_value=None), patch.object(self.b2b.importlib, "import_module", return_value=SimpleNamespace(make_sales_invoice=mapper)), patch.object(self.b2b, "serialize", return_value={}), patch.object(self.b2b, "audit"):
            self.b2b.convert_document("Outlet", "Delivery Note", "DN", "Sales Invoice", "retry-identity-12345", [{"name": "DN-LINE", "qty": 2}])
        self.assertEqual(mapped.items[0].qty, 2)
        self.assertEqual(mapped.items[0].dn_detail, "DN-LINE")
        self.assertEqual(mapped.update_stock, 0)
        mapped.insert.assert_called_once()

    def test_amendment_does_not_bypass_native_payment_dependency(self):
        invoice = Doc(docstatus=1, modified="new")
        invoice.cancel.side_effect = ValueError("Cancel linked payment first")
        self.frappe.copy_doc = Mock()
        with patch.object(self.b2b, "document", return_value=invoice), patch.object(self.b2b, "previous", return_value=None), self.assertRaises(ValueError):
            self.b2b.cancel_and_amend("Outlet", "Sales Invoice", "INV", "new", "retry-identity-12345")
        self.frappe.copy_doc.assert_not_called()

    def test_idempotency_hash_is_canonical_and_payload_sensitive(self):
        first = self.b2b.identity("retry-identity-12345", {"a": 1, "b": 2})
        self.assertEqual(first, self.b2b.identity("retry-identity-12345", {"b": 2, "a": 1}))
        self.assertNotEqual(first[1], self.b2b.identity("retry-identity-12345", {"a": 2})[1])

    def test_native_prices_plus_manual_discount_are_frozen_once(self):
        self.frappe.new_doc = Mock(side_effect=lambda kind: Doc(doctype=kind, docstatus=0, items=[], sales_team=[], taxes=[]))
        customer = Doc(name="C")
        item = Doc(name="FEED", stock_uom="Kg", is_sales_item=1, is_stock_item=1, disabled=0, has_variants=0)
        warehouse = Doc(company="Company", is_group=0, disabled=0)
        self.frappe.get_doc = Mock(return_value=warehouse)
        self.frappe.get_cached_doc = Mock(return_value=item)
        self.frappe.get_cached_value = Mock(side_effect=lambda kind, name, field: "LKR" if kind == "Price List" else None)
        sales = ModuleType("esafepos.api.sales")
        sales._check_price_edit_permission, sales._check_discount_passcode = Mock(), Mock(return_value=None)
        with patch.dict(sys.modules, {"esafepos.api.sales": sales}), patch.object(self.b2b, "customer_doc", return_value=customer):
            doc = self.b2b._prepare("Outlet", {"doctype": "Sales Invoice", "customer": "C", "items": [{"item_code": "FEED", "qty": 2, "discount_method": "Percent", "discount_value": 10}]})
        self.assertEqual(doc.items[0].rate, 72)
        self.assertEqual(doc.items[0].discount_amount, 28)
        self.assertEqual(doc.grand_total, 144)
        self.assertEqual(doc.ignore_pricing_rule, 1)
        self.assertEqual(json.loads(doc.esafepos_b2b_manual)[0]["base_rate"], 80)

    def prepare_linked_draft(self, manual=False):
        source = Doc(doctype="Sales Invoice", name="DRAFT", company="Company", currency="LKR", customer="C", docstatus=0,
                     modified="old", items=[Doc(name="LINE", item_code="FEED", rate=63 if manual else 70, price_list_rate=100,
                                               sales_order="SO", so_detail="SO-LINE")], taxes=[])
        if manual:
            source.esafepos_b2b_manual = json.dumps([{"item_code": "FEED", "native_rate": 70, "base_rate": 70, "discount_value": 10}])
        item = Doc(name="FEED", stock_uom="Kg", is_sales_item=1, is_stock_item=1, disabled=0, has_variants=0)
        self.frappe.get_doc = Mock(return_value=Doc(company="Company", is_group=0, disabled=0))
        self.frappe.get_cached_doc = Mock(return_value=item)
        self.frappe.get_cached_value = Mock(return_value=None)
        sales = ModuleType("esafepos.api.sales")
        sales._check_price_edit_permission, sales._check_discount_passcode = Mock(), Mock(return_value=None)
        with patch.dict(sys.modules, {"esafepos.api.sales": sales}), patch.object(self.b2b, "customer_doc", return_value=Doc(name="C")), patch.object(self.b2b, "document", return_value=source):
            return self.b2b._prepare("Outlet", {"doctype": "Sales Invoice", "name": "DRAFT", "modified": "old", "customer": "C", "grand_total": 999999,
                "items": [{"name": "LINE", "item_code": "FEED", "qty": 2, "discount_value": 10 if manual else 0, "discount_method": "Percent"}]})

    def test_mapped_agreed_price_and_source_link_survive_draft_edit(self):
        doc = self.prepare_linked_draft()
        self.assertEqual(doc.items[0].rate, 70)
        self.assertEqual(doc.items[0].so_detail, "SO-LINE")
        self.assertEqual(doc.grand_total, 140)

    def test_saved_linked_discount_is_not_applied_twice(self):
        self.assertEqual(self.prepare_linked_draft(manual=True).items[0].rate, 63)

    def test_manual_discount_permission_is_checked_before_save(self):
        self.permission.can_edit_price.return_value = False
        with self.assertRaises(PermissionError):
            self.prepare_linked_draft(manual=True)

    def test_settlement_retry_survives_closed_register(self):
        with patch.object(self.payments, "_pay_context", return_value=(self.profile, "LKR")), patch.object(self.payments, "customer_doc", return_value=Doc(name="C")), patch.object(self.payments, "_prior", return_value=Doc()), patch.object(self.payments, "_receipt", return_value={"name": "RECEIPT"}), patch.object(self.payments, "_session") as session:
            result = self.payments.receive_settlement("Outlet", {"customer": "C"}, "retry-identity-12345")
            self.assertEqual(result["name"], "RECEIPT")
            session.assert_not_called()

    def test_cheque_receipt_creates_no_payment_or_ledger_posting(self):
        created = []
        def record(kind, values):
            doc = Doc(doctype=kind, name="CUSTODY" if kind == self.payments.CHEQUE else "RECEIPT", **values)
            created.append(doc)
            return doc
        rows = [Doc(name="INV", outstanding_amount=100, debit_to="Debtors", currency="LKR")]
        payload = {"customer": "C", "collection_context": "Back office", "tenders": [{"method": "Cheque", "amount": 100, "bank": "Test Bank", "mode_of_payment": "Cheque", "reference_no": "000123", "reference_date": "2026-12-01"}]}
        with patch.object(self.payments, "_pay_context", return_value=(self.profile, "LKR")), patch.object(self.payments, "customer_doc", return_value=Doc(name="C")), patch.object(self.payments, "_prior", return_value=None), patch.object(self.payments, "_session", return_value=None), patch.object(self.payments, "lock_customer"), patch.object(self.payments, "_open_invoices", return_value=rows), patch.object(self.payments, "_mode"), patch.object(self.payments, "_record", side_effect=record), patch.object(self.payments, "_save"), patch.object(self.payments, "_receipt", return_value={}), patch.object(self.payments, "audit"), patch.object(self.payments, "_post_payment") as post:
            self.payments.receive_settlement("Outlet", payload, "retry-identity-12345")
        post.assert_not_called()
        self.assertEqual(created[1].status, "Received")
        self.assertEqual(created[1].reference_no, "000123")
        self.assertEqual(created[1].cheque_date, "2026-12-01")

    def test_stale_cheque_cannot_clear(self):
        cheque = Doc(company="Company", pos_profile="Outlet", customer="C", modified="new", status="Deposited")
        self.frappe.get_doc = Mock(return_value=cheque)
        with patch.object(self.payments, "_pay_context", return_value=(self.profile, "LKR")), patch.object(self.payments, "customer_doc"), patch.object(self.payments, "_post_payment") as post:
            with self.assertRaises(ValueError):
                self.payments.transition_cheque("Outlet", "CHEQUE", "clear", "old")
            post.assert_not_called()

    def test_duplicate_cheques_in_same_settlement_fail_before_recording(self):
        tender = {"method": "Cheque", "amount": 100, "bank": "Bank", "mode_of_payment": "Cheque", "reference_no": "0001", "reference_date": "2026-12-01"}
        payload = {"customer": "C", "collection_context": "Back office", "tenders": [tender, dict(tender, bank=" Bank ", reference_no=" 0001 ")]}
        with patch.object(self.payments, "_pay_context", return_value=(self.profile, "LKR")), patch.object(self.payments, "customer_doc", return_value=Doc(name="C")), patch.object(self.payments, "_prior", return_value=None), patch.object(self.payments, "_session"), patch.object(self.payments, "lock_customer"), patch.object(self.payments, "_mode"), patch.object(self.payments, "_record") as record, self.assertRaises(ValueError):
            self.payments.receive_settlement("Outlet", payload, "retry-identity-12345")
        record.assert_not_called()

    def test_explicit_cheque_advance_does_not_allocate_to_another_invoice(self):
        cheque = Doc(name="CHEQUE", company="Company", pos_profile="Outlet", customer="C", modified="new", status="Deposited", amount=100,
                     received_date="2026-11-20", deposit_date="2026-11-22", cheque_date="2026-11-23", mode_of_payment="Cheque", reference_no="0001", settlement="SETTLEMENT", history="[]")
        self.frappe.get_doc = Mock(return_value=cheque)
        with patch.object(self.payments, "_pay_context", return_value=(self.profile, "LKR")), patch.object(self.payments, "customer_doc"), patch.object(self.payments, "lock_customer"), patch.object(self.payments, "_open_invoices", return_value=[Doc(name="OTHER", outstanding_amount=100)]), patch.object(self.payments, "_post_payment", return_value=Doc(name="PAY")) as post, patch("esafepos.erpnext_compat.set_payment_clearance"), patch.object(self.payments, "_save"), patch.object(self.payments, "audit"):
            self.payments.transition_cheque("Outlet", "CHEQUE", "clear", "new", allocations=[], keep_advance=1)
        self.assertEqual(post.call_args.args[4], [])

    def test_cheque_retry_returns_recorded_outcome_without_second_posting(self):
        key, fingerprint = self.b2b.identity("retry-identity-12345", {"action": "clear", "event_date": None, "reason": None, "allocations": None, "keep_advance": None})
        cheque = Doc(name="CHEQUE", company="Company", pos_profile="Outlet", customer="C", modified="new", status="Cleared", payment_entry="PAY", history=json.dumps([{"request_id": key, "request_hash": fingerprint}]))
        self.frappe.get_doc = Mock(return_value=cheque)
        with patch.object(self.payments, "_pay_context", return_value=(self.profile, "LKR")), patch.object(self.payments, "customer_doc"), patch.object(self.payments, "_post_payment") as post:
            result = self.payments.transition_cheque("Outlet", "CHEQUE", "clear", "old", idempotency_key="retry-identity-12345")
            self.assertEqual(result["payment_entry"], "PAY")
            post.assert_not_called()

    def test_changed_invoice_allocations_block_clearance_before_posting(self):
        cheque = Doc(company="Company", pos_profile="Outlet", customer="C", modified="new", status="Deposited", amount=100,
                     received_date="2026-11-20", deposit_date="2026-11-22", cheque_date="2026-11-23", allocations=json.dumps([{"name": "INV", "amount": 100}]), keep_advance=0)
        self.frappe.get_doc = Mock(return_value=cheque)
        with patch.object(self.payments, "_pay_context", return_value=(self.profile, "LKR")), patch.object(self.payments, "customer_doc"), patch.object(self.payments, "lock_customer"), patch.object(self.payments, "_open_invoices", return_value=[Doc(name="INV", outstanding_amount=50)]), patch.object(self.payments, "_post_payment") as post:
            with self.assertRaises(ValueError):
                self.payments.transition_cheque("Outlet", "CHEQUE", "clear", "new")
            post.assert_not_called()

    def test_native_cancellation_blocker_leaves_cheque_cleared(self):
        cheque = Doc(company="Company", pos_profile="Outlet", customer="C", modified="new", status="Cleared", received_date="2026-11-20", payment_entry="PAY")
        payment = Doc()
        payment.cancel.side_effect = ValueError("Accounting period is closed")
        self.frappe.get_doc = Mock(side_effect=lambda kind, name: cheque if kind == self.payments.CHEQUE else payment)
        with patch.object(self.payments, "_pay_context", return_value=(self.profile, "LKR")), patch.object(self.payments, "customer_doc"), patch.object(self.payments, "_save") as save:
            with self.assertRaises(ValueError):
                self.payments.transition_cheque("Outlet", "CHEQUE", "bounce", "new", reason="Dishonoured")
            save.assert_not_called()
        self.assertEqual(cheque.status, "Cleared")

    def test_shift_counts_native_and_legacy_collections_once(self):
        path = Path(__file__).with_name("register.py")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_customer_payments")
        self.frappe.get_all = Mock(side_effect=lambda kind, **kwargs: [Doc(name="JE", mode_of_payment="Cash", total_debit=10, esafepos_credit_customer="C", creation="today")] if kind == "Journal Entry" else [Doc(name="PE", mode_of_payment="Cash", received_amount=20, party="C", creation="today")])
        namespace = {"frappe": self.frappe, "flt": lambda value, precision=2: round(float(value or 0), precision), "_in_window": lambda *args: True}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
        modes, rows = namespace["_customer_payments"]("SHIFT")
        self.assertEqual(modes, {"Cash": 30})
        self.assertEqual(len(rows), 2)
        self.assertEqual(self.frappe.get_all.call_args_list[1].kwargs["filters"]["esafepos_b2b_session"], "SHIFT")

    def test_statement_uses_posted_party_ledger_for_opening_and_closing(self):
        reports = importlib.reload(importlib.import_module("esafepos.api.b2b_reports"))
        def entries(kind, **kwargs):
            if kind != "GL Entry":
                return []
            if kwargs["filters"]["posting_date"][0] == "<":
                return [dict(debit=50, credit=10)]
            return [Doc(posting_date="2026-11-10", voucher_type="Sales Invoice", voucher_no="INV", account="Debtors", debit=100, credit=0),
                    Doc(posting_date="2026-11-20", voucher_type="Journal Entry", voucher_no="JE", account="Debtors", debit=0, credit=20)]
        self.frappe.get_list.side_effect = entries
        self.frappe.get_doc = Mock(return_value=Doc(name="JE", posting_date="2026-11-20", accounts=[]))
        with patch.object(reports, "authorize", return_value=(self.profile, "LKR", Doc(customer_name="Customer"))):
            result = reports.customer_statement("Outlet", "C", "2026-11-01", "2026-11-27")
        self.assertEqual(result["opening"], 40)
        self.assertEqual(result["closing"], 120)
        self.assertEqual([row["balance"] for row in result["rows"]], [140, 120])
        for call in self.frappe.get_list.call_args_list:
            if call.args[0] == "GL Entry":
                self.assertEqual(call.kwargs["filters"]["party"], "C")
                self.assertEqual(call.kwargs["filters"]["company"], "Company")

    def test_statement_without_general_ledger_permission_is_refused(self):
        reports = importlib.reload(importlib.import_module("esafepos.api.b2b_reports"))
        self.frappe.has_permission.return_value = False
        with patch.object(reports, "context", return_value=(self.profile, "LKR")), patch.object(reports, "customer_doc", return_value=Doc()), self.assertRaises(PermissionError):
            reports.customer_statement("Outlet", "C")
        self.frappe.get_list.assert_not_called()

    def test_bank_clearance_adapter_supports_native_old_and_new_tables(self):
        compat = importlib.reload(importlib.import_module("esafepos.erpnext_compat"))
        for table in ("payment_entries", "journal_entries"):
            tool = Doc()
            tool.meta.has_field = lambda name: name == table
            tool.update_clearance_date = Mock()
            self.frappe.get_doc = Mock(return_value=Doc(name="PAY", paid_to="Bank", posting_date="2026-11-27"))
            self.frappe.new_doc = Mock(return_value=tool)
            compat.set_payment_clearance("PAY", "2026-11-27")
            self.assertEqual(tool.get(table)[0].payment_entry, "PAY")
            tool.update_clearance_date.assert_called_once()


if __name__ == "__main__":
    unittest.main()
