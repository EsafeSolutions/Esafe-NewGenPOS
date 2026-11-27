"""Buying boundaries against mocked Frappe services; runnable without a bench."""
import importlib.util
import ast
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class Document(SimpleNamespace):
    def __init__(self, **values):
        super().__init__(**values)
        self.check_permission = Mock()
        self.insert = Mock()
        self.submit = Mock()
        self.run_method = Mock()

    def get(self, key, default=None):
        return getattr(self, key, default)

    def set(self, key, value):
        setattr(self, key, value)


class BuyingTests(unittest.TestCase):
    def setUp(self):
        from datetime import date
        self.frappe = ModuleType("frappe")
        self.frappe._ = lambda value: value
        self.frappe.PermissionError = PermissionError
        self.frappe.session = SimpleNamespace(user="buyer@example.com")
        self.frappe.whitelist = lambda **kwargs: lambda fn: fn
        self.frappe.throw = Mock(side_effect=lambda text, kind=ValueError: self.raise_error(text, kind))
        self.frappe.has_permission = Mock(return_value=True)
        self.frappe.get_meta = Mock(return_value=SimpleNamespace(has_field=lambda name: True))
        self.frappe.db = SimpleNamespace(sql=Mock(), get_value=Mock(return_value=None))
        self.profile = Document(name="Till", company="Shop", warehouse="Stores", cost_center="Main - S")
        self.frappe.get_cached_doc = Mock(return_value=self.profile)
        self.frappe.get_cached_value = Mock(return_value="LKR")
        self.frappe.get_list = Mock(return_value=[])
        self.frappe.__version__ = "15.0.0"
        self.supplier = Document(name="SUP", supplier_name="Green Supplies", supplier_group="Local", disabled=0)
        self.warehouse = Document(name="Stores", company="Shop", is_group=0, disabled=0)
        self.item = Document(name="RICE", stock_uom="Kg", disabled=0, is_purchase_item=1, has_variants=0,
                             is_fixed_asset=0, has_serial_no=0, has_batch_no=0, is_stock_item=1)
        self.accounts = {
            "Freight": Document(name="Freight", company="Shop", is_group=0, disabled=0, account_currency="LKR", account_type="Expenses Included In Valuation", root_type="Expense"),
            "Cash": Document(name="Cash", company="Shop", is_group=0, disabled=0, account_currency="LKR", account_type="Cash", root_type="Asset"),
            "Bank": Document(name="Bank", company="Shop", is_group=0, disabled=0, account_currency="LKR", account_type="Bank", root_type="Asset"),
            "Payable": Document(name="Payable", company="Shop", is_group=0, disabled=0, account_currency="LKR", account_type="Payable", root_type="Liability"),
        }
        self.mode = Document(name="Cash", enabled=1, type="Cash")
        self.created = []
        self.native_invoice = Document(name="INV-1", posting_date="2026-11-26")
        self.frappe.get_doc = Mock(side_effect=self.get_doc)
        utils = ModuleType("frappe.utils")
        utils.cint = lambda n: int(n or 0)
        utils.flt = lambda n=0, precision=None: round(float(n or 0), precision) if precision is not None else float(n or 0)
        utils.getdate = lambda value: date.fromisoformat(str(value))
        utils.nowdate = lambda: "2026-11-26"
        self.permissions = ModuleType("esafepos.api.permissions")
        self.permissions.allowed = Mock(return_value=True)
        self.permissions.ITEM_CREATE = "Create items"
        self.permissions.ITEM_PRICE_EDIT = "Edit item selling prices"
        self.permissions.assert_outlet = Mock()
        self.features = ModuleType("esafepos.features")
        self.features.enabled = Mock(return_value=True)
        self.stock = ModuleType("esafepos.api.stock_app")
        self.stock._has_workflow = Mock(return_value=False)
        party = ModuleType("erpnext.accounts.party")
        party.get_party_account = Mock(return_value="Payable")
        self.patcher = patch.dict(sys.modules, {"frappe": self.frappe, "frappe.utils": utils,
            "esafepos.api.permissions": self.permissions, "esafepos.features": self.features,
            "esafepos.api.stock_app": self.stock, "erpnext.accounts.party": party})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        import esafepos.api
        self.package_patch = patch.object(esafepos.api, "permissions", self.permissions, create=True)
        self.package_patch.start()
        self.addCleanup(self.package_patch.stop)
        compat = ModuleType("esafepos.erpnext_compat")
        compat.__dict__.update(frappe=self.frappe, cint=utils.cint)
        tree = ast.parse(Path(__file__).parents[1].joinpath("erpnext_compat.py").read_text(encoding="utf-8"))
        selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "sum_fields"]
        exec(compile(ast.Module(body=selected, type_ignores=[]), "erpnext_compat.py", "exec"), compat.__dict__)
        compat_patch = patch.dict(sys.modules, {"esafepos.erpnext_compat": compat})
        compat_patch.start()
        self.addCleanup(compat_patch.stop)
        spec = importlib.util.spec_from_file_location("buying_under_test", Path(__file__).with_name("buying.py"))
        self.api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.api)

    @staticmethod
    def raise_error(message, kind):
        raise kind(message)

    def get_doc(self, doctype, name=None):
        if isinstance(doctype, dict):
            doc = Document(**{"name": "NEW-1", "docstatus": 0, **doctype})
            self.created.append(doc)
            return doc
        if doctype == "Supplier":
            return self.supplier
        if doctype == "Warehouse":
            return self.warehouse
        if doctype == "Item":
            return self.item
        if doctype == "Account":
            return self.accounts[name]
        if doctype == "Mode of Payment":
            return self.mode
        if doctype == "Purchase Invoice":
            return self.native_invoice
        if doctype == "Supplier Group":
            return Document(name="Local", is_group=0)
        raise AssertionError((doctype, name))

    def invoice(self, **overrides):
        args = dict(pos_profile="Till", supplier="SUP", items=[{"item_code": "RICE", "qty": 10, "rate": 100}],
                    warehouse="Stores", idempotency_key="invoice-request", posting_date="2026-11-26", due_date="2026-12-26")
        args.update(overrides)
        return self.api.create_invoice(**args)

    def open_invoices(self):
        return [Document(name="INV-1", currency="LKR", credit_to="Payable", outstanding_amount=100),
                Document(name="INV-2", currency="LKR", credit_to="Payable", outstanding_amount=200)]

    def payment(self, **overrides):
        self.frappe.db.get_value.side_effect = lambda dt, filters, field: self.mode.type if dt == "Mode of Payment Account" else None
        self.api._invoice_rows = Mock(return_value=self.open_invoices())
        args = dict(pos_profile="Till", supplier="SUP", invoices=[{"name": "INV-2"}, {"name": "INV-1"}], amount=150,
                    payment_method="Cash", mode_of_payment="Cash", idempotency_key="payment-request")
        args.update(overrides)
        return self.api.pay_supplier(**args)

    def test_feature_capability_and_native_read_are_all_required(self):
        for check in (self.features.enabled, self.permissions.allowed, self.frappe.has_permission):
            check.return_value = False
            with self.assertRaises(PermissionError):
                self.invoice()
            check.return_value = True
        self.frappe.get_doc.assert_not_called()

    def test_outlet_permission_checked_before_linked_records(self):
        self.permissions.assert_outlet.side_effect = PermissionError("Other outlet")
        with self.assertRaises(PermissionError):
            self.invoice()
        self.frappe.get_doc.assert_not_called()

    def test_native_create_and_submit_permissions_are_required(self):
        for action in ("create", "submit"):
            self.frappe.has_permission.side_effect = lambda dt, kind: kind != action
            with self.assertRaises(PermissionError):
                self.invoice()
        self.assertFalse(self.created)

    def test_disabled_supplier_and_cross_company_warehouse_refused(self):
        self.supplier.disabled = 1
        with self.assertRaises(ValueError):
            self.invoice()
        self.supplier.disabled = 0
        self.warehouse.company = "Other"
        with self.assertRaises(ValueError):
            self.invoice()
        self.assertFalse(self.created)

    def test_native_item_and_warehouse_record_permissions_apply(self):
        for doc in (self.warehouse, self.item):
            doc.check_permission.side_effect = PermissionError
            with self.assertRaises(PermissionError):
                self.invoice()
            doc.check_permission.side_effect = None

    def test_quantity_and_rate_reject_nonfinite_or_nonpositive_values(self):
        for field in ("qty", "rate"):
            for value in (None, "", "nan", "inf", -1, 0):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.invoice(items=[{"item_code": "RICE", "qty": 1, "rate": 100, field: value}])
        self.assertFalse(self.created)

    def test_dates_and_row_limits_validated(self):
        for args in ({"due_date": "2026-11-25"}, {"posting_date": "bad"}, {"bill_date": "bad"},
                     {"items": []}, {"items": [None]}, {"items": "bad"}, {"items": [{}] * 201}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.invoice(**args)

    def test_serial_batch_asset_and_template_items_refused(self):
        for flag in ("disabled", "has_serial_no", "has_batch_no", "is_fixed_asset", "has_variants"):
            setattr(self.item, flag, 1)
            with self.assertRaises(ValueError):
                self.invoice()
            setattr(self.item, flag, 0)
        self.item.is_purchase_item = 0
        with self.assertRaises(ValueError):
            self.invoice()

    def test_additional_costs_use_native_valuation_and_total(self):
        result = self.invoice(costs=[{"description": "Freight", "account": "Freight", "amount": 100}])
        doc = self.created[-1]
        self.assertEqual(result["name"], "NEW-1")
        self.assertEqual(doc.update_stock, 1)
        self.assertEqual(doc.currency, "LKR")
        self.assertEqual(doc.conversion_rate, 1)
        self.assertEqual(doc.credit_to, "Payable")
        self.assertEqual(doc.items[0]["conversion_factor"], 1)
        self.assertNotIn("valuation_rate", doc.items[0])
        self.assertEqual(doc.taxes[0]["category"], "Valuation and Total")
        self.assertEqual(doc.taxes[0]["charge_type"], "Actual")
        self.assertEqual(doc.taxes[0]["tax_amount"], 100)
        self.assertEqual(doc.esafepos_buying_profile, "Till")
        doc.insert.assert_called_once_with()
        doc.submit.assert_called_once_with()
        doc.check_permission.assert_any_call("create")
        doc.check_permission.assert_any_call("submit")

    def test_nonstock_lines_cannot_absorb_valuation_costs(self):
        self.item.is_stock_item = 0
        with self.assertRaises(ValueError):
            self.invoice(costs=[{"description": "Freight", "account": "Freight", "amount": 100}])

    def test_cost_accounts_and_amounts_validated(self):
        for field, value in (("company", "Other"), ("account_currency", "USD"), ("is_group", 1),
                             ("disabled", 1), ("root_type", "Asset")):
            account = self.accounts["Freight"]
            old = getattr(account, field)
            setattr(account, field, value)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.invoice(costs=[{"description": "Freight", "account": "Freight", "amount": 100}])
            setattr(account, field, old)
        for values in ({"amount": -1}, {"amount": "nan"}, {"description": " "}):
            with self.assertRaises(ValueError):
                self.invoice(costs=[{"description": "Freight", "account": "Freight", "amount": 100, **values}])

    def test_workflows_are_not_bypassed(self):
        self.stock._has_workflow.return_value = True
        with self.assertRaises(ValueError):
            self.invoice()
        self.created[-1].insert.assert_not_called()
        with self.assertRaises(ValueError):
            self.payment()
        self.created[-1].insert.assert_not_called()

    def test_request_identity_binds_user_and_payload(self):
        identity, fingerprint = self.api._identity("Purchase Invoice", "request", {"qty": 1})
        self.assertEqual((identity, fingerprint), self.api._identity("Purchase Invoice", "request", {"qty": 1}))
        self.assertNotEqual(fingerprint, self.api._identity("Purchase Invoice", "request", {"qty": 2})[1])
        self.frappe.session.user = "other@example.com"
        self.assertNotEqual(identity, self.api._identity("Purchase Invoice", "request", {"qty": 1})[0])
        with self.assertRaises(ValueError):
            self.api._identity("Purchase Invoice", "", {})

    def test_missing_migration_fails_before_insert(self):
        self.frappe.get_meta.return_value.has_field = lambda name: False
        with self.assertRaisesRegex(ValueError, "migration"):
            self.invoice()
        self.assertFalse(self.created)

    def test_retries_return_original_document_and_reject_changed_or_cancelled_requests(self):
        prior = Document(name="INV-1", company="Shop", esafepos_buying_hash="hash", docstatus=1)
        self.frappe.db.get_value.return_value = prior.name
        self.frappe.get_doc = Mock(return_value=prior)
        self.assertIs(self.api._previous("Purchase Invoice", "id", "hash", "Shop"), prior)
        for fingerprint, company in (("changed", "Shop"), ("hash", "Other")):
            with self.assertRaises(ValueError):
                self.api._previous("Purchase Invoice", "id", fingerprint, company)
        prior.docstatus = 2
        with self.assertRaises(ValueError):
            self.api._previous("Purchase Invoice", "id", "hash", "Shop")
        prior.check_permission.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            self.api._previous("Purchase Invoice", "id", "hash", "Shop")

    def test_invoice_retry_does_not_receive_stock_again(self):
        prior = Document(name="INV-1", doctype="Purchase Invoice", docstatus=1, grand_total=1100)
        self.api._previous = Mock(return_value=prior)
        self.assertEqual(self.invoice()["name"], "INV-1")
        self.assertFalse(self.created)

    def test_partial_payment_allocates_oldest_first(self):
        payable, refs = self.api._allocate(self.open_invoices(), ["INV-2", "INV-1"], 150, "LKR")
        self.assertEqual(payable, "Payable")
        self.assertEqual([(r["reference_name"], r["allocated_amount"]) for r in refs], [("INV-1", 100), ("INV-2", 50)])

    def test_allocation_decimal_boundary_does_not_reject_full_settlement(self):
        rows = self.open_invoices()
        rows[0].outstanding_amount = .3
        rows[1].outstanding_amount = .6
        refs = self.api._allocate(rows, ["INV-1", "INV-2"], .9, "LKR")[1]
        self.assertEqual([r["allocated_amount"] for r in refs], [.3, .6])

    def test_stale_excess_cross_supplier_or_foreign_currency_selections_refused(self):
        for names, amount in (([], 100), (["OTHER"], 100), (["INV-1"], 101), (["INV-1", "INV-2"], 301)):
            with self.assertRaises(ValueError):
                self.api._allocate(self.open_invoices(), names, amount, "LKR")
        rows = self.open_invoices()
        rows[0].currency = "USD"
        with self.assertRaises(ValueError):
            self.api._allocate(rows, ["INV-1"], 1, "LKR")
        rows = self.open_invoices()
        rows[0].credit_to = "Other"
        with self.assertRaises(ValueError):
            self.api._allocate(rows, ["INV-1", "INV-2"], 1, "LKR")

    def test_native_cash_payment_and_row_locks(self):
        self.payment()
        doc = self.created[-1]
        self.assertEqual((doc.payment_type, doc.party_type, doc.party), ("Pay", "Supplier", "SUP"))
        self.assertEqual((doc.paid_from, doc.paid_to), ("Cash", "Payable"))
        self.assertEqual((doc.paid_amount, doc.received_amount), (150, 150))
        self.assertEqual(doc.esafepos_supplier_payment_method, "Cash")
        self.assertEqual(len(doc.references), 2)
        self.assertEqual(self.frappe.db.sql.call_count, 3)
        doc.submit.assert_called_once()

    def test_cheque_and_transfer_require_bank_mode_number_and_date(self):
        self.mode.type = "Bank"
        for method in ("Cheque", "Bank Transfer"):
            for missing in ({"reference_no": None}, {"reference_date": None}):
                with self.assertRaises(ValueError):
                    self.payment(**{"payment_method": method, "reference_no": "REF-1", "reference_date": "2026-11-26", **missing})
            self.payment(payment_method=method, reference_no="REF-1", reference_date="2026-12-01")
            doc = self.created[-1]
            self.assertEqual((doc.paid_from, doc.reference_no, doc.reference_date), ("Bank", "REF-1", "2026-12-01"))
            self.assertEqual(doc.esafepos_supplier_payment_method, method)

    def test_wrong_mode_duplicates_and_payment_before_invoice_refused(self):
        for args in ({"payment_method": "Card"}, {"payment_method": "Cheque"},
                     {"invoices": [{"name": "INV-1"}, {"name": "INV-1"}]},
                     {"invoices": [{"name": None}]}, {"amount": "inf"}, {"posting_date": "2026-11-25"}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.payment(**args)

    def test_payment_retry_returns_original_without_posting_again(self):
        prior = Document(name="PAY-1", doctype="Payment Entry", docstatus=1, paid_amount=150)
        self.api._previous = Mock(return_value=prior)
        self.assertEqual(self.payment()["name"], "PAY-1")
        self.assertFalse(self.created)
        self.api._invoice_rows.assert_not_called()

    def test_supplier_creation_uses_native_document_and_request_identity(self):
        result = self.api.create_supplier("Till", " New supplier ", "Local", "supplier-request")
        self.assertEqual(result["supplier_name"], "New supplier")
        doc = self.created[-1]
        self.assertEqual(len(doc.esafepos_buying_key), 64)
        doc.insert.assert_called_once_with()

    def test_invoice_details_cannot_cross_company(self):
        self.native_invoice.company = "Other"
        with self.assertRaises(PermissionError):
            self.api.invoice_details("Till", "INV-1")

    def test_balance_uses_permission_filtered_company_ledger(self):
        self.api._invoice_rows = Mock(return_value=[])
        self.frappe.get_list.side_effect = lambda dt, **kw: [Document(credit=1500, debit=500)] if dt == "GL Entry" else []
        result = self.api.supplier_account("Till", "SUP")
        self.assertEqual(result["balance"], 1000)
        ledger = self.frappe.get_list.call_args_list[0].kwargs
        self.assertEqual(ledger["filters"], {"company": "Shop", "party_type": "Supplier", "party": "SUP", "is_cancelled": 0})
        self.frappe.has_permission.side_effect = lambda dt, action: dt != "GL Entry"
        self.assertIsNone(self.api.supplier_account("Till", "SUP")["balance"])

    def test_read_only_buyers_do_not_need_setup_record_permissions(self):
        self.frappe.has_permission.side_effect = lambda dt, action: dt in ("Supplier", "Purchase Invoice") and action == "read"
        result = self.api.options("Till")
        self.assertFalse(result["can_create_invoice"])
        self.assertFalse(result["can_create_supplier"])
        self.assertFalse(result["can_pay"])
        self.assertFalse(result["can_create_item"])
        self.assertFalse(result["can_edit_prices"])
        self.assertIsNone(result["selling_price_list"])
        self.assertEqual(result["item_groups"], [])
        self.assertEqual(result["stock_uoms"], [])
        self.assertEqual(result["warehouses"], [])
        self.assertEqual(result["payment_modes"], [])
        self.frappe.get_list.assert_not_called()

    def test_emergency_item_options_require_capability_and_native_permissions(self):
        for denied in (("Item", "create"), ("Item", "read"), ("Item Group", "read"), ("UOM", "read")):
            with self.subTest(denied=denied):
                self.frappe.has_permission.side_effect = lambda dt, action: (dt, action) != denied
                self.frappe.get_list.reset_mock()
                result = self.api.options("Till")
                self.assertFalse(result["can_create_item"])
                self.assertEqual(result["item_groups"], [])
                self.assertEqual(result["stock_uoms"], [])
                self.assertFalse(any(call.args[0] in ("Item Group", "UOM")
                                     for call in self.frappe.get_list.call_args_list))
        self.frappe.has_permission.side_effect = None
        self.permissions.allowed.side_effect = lambda capability: capability != "Create items"
        self.assertFalse(self.api.options("Till")["can_create_item"])

    def test_emergency_item_options_use_permission_scoped_leaf_categories_and_units(self):
        self.frappe.get_list.side_effect = lambda dt, **kw: {"Item Group": ["Goods"], "UOM": ["Kg", "Nos"]}.get(dt, [])
        result = self.api.options("Till")
        self.assertTrue(result["can_create_item"])
        self.assertEqual(result["item_groups"], ["Goods"])
        self.assertEqual(result["stock_uoms"], ["Kg", "Nos"])
        self.frappe.get_list.assert_any_call("Item Group", filters={"is_group": 0}, pluck="name", order_by="name", limit_page_length=0)
        for call in self.frappe.get_list.call_args_list:
            self.assertNotIn("ignore_permissions", call.kwargs)

    def test_emergency_selling_price_requires_price_capability_and_native_create_access(self):
        self.profile.selling_price_list = "Standard Selling"
        for denied in (("Item Price", "create"), ("Item Price", "read"), ("Price List", "read")):
            with self.subTest(denied=denied):
                self.frappe.has_permission.side_effect = lambda dt, action: (dt, action) != denied
                self.frappe.get_list.reset_mock()
                result = self.api.options("Till")
                self.assertTrue(result["can_create_item"])
                self.assertFalse(result["can_edit_prices"])
                self.assertIsNone(result["selling_price_list"])
                self.assertFalse(any(call.args[0] == "Price List" for call in self.frappe.get_list.call_args_list))
        self.frappe.has_permission.side_effect = None
        self.permissions.allowed.side_effect = lambda capability: capability != "Edit item selling prices"
        self.assertFalse(self.api.options("Till")["can_edit_prices"])

    def test_emergency_selling_price_uses_outlet_list_and_its_currency(self):
        self.profile.selling_price_list = "Retail USD"
        self.frappe.get_list.side_effect = lambda dt, **kw: [{"name": "Retail USD", "currency": "USD"}] if dt == "Price List" else []
        result = self.api.options("Till")
        self.assertTrue(result["can_edit_prices"])
        self.assertEqual(result["selling_price_list"], {"name": "Retail USD", "currency": "USD"})
        self.frappe.get_list.assert_any_call("Price List", filters={"name": "Retail USD", "enabled": 1, "selling": 1},
                                           fields=["name", "currency"], limit_page_length=1)

    def test_emergency_selling_price_has_no_fallback_for_missing_or_inaccessible_outlet_list(self):
        self.assertIsNone(self.api.options("Till")["selling_price_list"])
        self.profile.selling_price_list = "Disabled or inaccessible"
        self.assertIsNone(self.api.options("Till")["selling_price_list"])

    def test_frappe_16_balance_uses_dictionary_aggregates_and_keeps_permissions(self):
        self.frappe.__version__ = "16.60.2"
        self.api._invoice_rows = Mock(return_value=[])
        def strict_get_list(doctype, **kwargs):
            if doctype == "GL Entry":
                self.assertEqual(kwargs["fields"], [{"SUM": "credit", "as": "credit"}, {"SUM": "debit", "as": "debit"}])
                self.assertNotIn("ignore_permissions", kwargs)
                return [Document(credit=500, debit=700)]
            return []
        self.frappe.get_list.side_effect = strict_get_list
        self.assertEqual(self.api.supplier_account("Till", "SUP")["balance"], -200)

    def test_legacy_balance_uses_supported_string_aggregates(self):
        self.api._invoice_rows = Mock(return_value=[])
        self.api.supplier_account("Till", "SUP")
        self.assertEqual(self.frappe.get_list.call_args_list[0].kwargs["fields"], ["sum(credit) as credit", "sum(debit) as debit"])

    def test_tax_only_charges_do_not_increase_stock_valuation(self):
        self.accounts["Input tax"] = Document(name="Input tax", company="Shop", is_group=0, disabled=0,
                                               account_currency="LKR", account_type="Tax", root_type="Asset")
        self.invoice(costs=[{"kind": "tax", "description": "Input tax", "account": "Input tax", "amount": 180}])
        self.assertEqual(self.created[-1].taxes[0]["category"], "Total")
        with self.assertRaises(ValueError):
            self.invoice(costs=[{"kind": "tax", "description": "Not tax", "account": "Freight", "amount": 180}])

    def test_duplicate_supplier_reference_is_refused_before_receiving_stock(self):
        self.frappe.get_list.return_value = [Document(name="EXISTING", docstatus=1)]
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.invoice(bill_no="SUP-BILL-1")
        self.assertFalse(self.created)

    def test_options_exclude_foreign_and_incompatible_payment_accounts(self):
        modes = [Document(name="Cash", type="Cash"), Document(name="Foreign", type="Bank"), Document(name="Wrong type", type="Bank")]
        accounts = list(self.accounts.values()) + [Document(name="Foreign account", account_currency="USD", account_type="Bank", root_type="Asset")]
        self.frappe.get_list.side_effect = lambda dt, **kw: accounts if dt == "Account" else modes if dt == "Mode of Payment" else []
        mapping = {"Cash": "Cash", "Foreign": "Foreign account", "Wrong type": "Payable"}
        self.frappe.db.get_value.side_effect = lambda dt, filters, field: mapping[filters["parent"]]
        self.assertEqual(self.api.options("Till")["payment_modes"], [{"name": "Cash", "type": "Cash", "account": "Cash"}])


if __name__ == "__main__":
    unittest.main()
