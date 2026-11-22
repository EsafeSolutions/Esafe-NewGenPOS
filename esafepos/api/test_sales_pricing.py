"""Checkout pricing regressions without a Frappe bench; document I/O is mocked."""
import ast
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from esafepos.api.discounts import discount_breakdown


def flt(value=0, precision=None):
    number = float(value or 0)
    return round(number, precision) if precision is not None else number


class Record(SimpleNamespace):
    def get(self, key, default=None):
        return getattr(self, key, default)

    def precision(self, field):
        return 6 if field in ("rate", "price_list_rate", "discount_percentage") else 2


class Invoice(Record):
    def __init__(self, native_discount=0, native_rate=None, native_rule=""):
        super().__init__(items=[], payments=[], flags=Record(), taxes=[],
                         native_discount=native_discount, native_rate=native_rate,
                         native_rule=native_rule, grand_total=0, rounded_total=0,
                         currency="LKR", conversion_rate=1, loyalty_amount=0)

    def update(self, values):
        self.__dict__.update(values)

    def append(self, table, values):
        row = Record(**values)
        getattr(self, table).append(row)

    def set_missing_values(self):
        # ERPNext fills list price / rule fields before totals resolve rate.
        for row in self.items:
            row.price_list_rate = 195
            row.rate = self.native_rate or 0
            row.discount_percentage = self.native_discount
            row.discount_amount = 0
            row.pricing_rules = self.native_rule
            row.is_free_item = 0

    def run_method(self, method):
        assert method == "calculate_taxes_and_totals"
        for row in self.items:
            if not row.rate:
                row.rate = flt(row.price_list_rate * (1 - row.discount_percentage / 100), 6)
            row.discount_amount = row.price_list_rate - row.rate
            row.amount = flt(row.qty * row.rate, 2)
        self.grand_total = flt(sum(row.amount for row in self.items), 2)
        self.rounded_total = self.grand_total
        self.net_total = self.grand_total
        self.total_taxes_and_charges = 0


class SalesPricingTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.throw.side_effect = lambda message, *args, **kwargs: (_ for _ in ()).throw(ValueError(message))
        self.profile = Record(name="Till", company="Shop", warehouse="Shop Stores", taxes_and_charges="")
        self.invoice = Invoice()
        self.erp = False
        self.ctx = Record(foreign=False, factor=1, currency="LKR")
        catalog = ModuleType("esafepos.api.catalog")
        catalog.internal_item_codes = lambda: set()
        catalog.blocked_payment_modes = lambda *args: {}
        features = ModuleType("esafepos.features")
        features.enabled = lambda name: self.erp
        self.modules = patch.dict(sys.modules, {"esafepos.api.catalog": catalog, "esafepos.features": features})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.credit = Mock(MODE_OF_PAYMENT="Credit Sale", EPSILON=0.005, assert_sale=Mock())
        self.credit.enabled.return_value = True
        self.credit.facts.return_value = dict(enabled=1, can_sell=1, available=10000)
        self.credit.on_account_part.side_effect = lambda doc: sum(
            row.amount for row in doc.payments if row.mode_of_payment == "Credit Sale")
        self.currency = Mock()
        self.currency.sale_context.side_effect = lambda *args: self.ctx
        self.currency.own_list_prices.return_value = {}
        self.currency.company_currency.return_value = "LKR"
        self.currency.public.return_value = dict(currency="LKR", rate=1)
        self.frappe.get_cached_doc.return_value = self.profile
        self.namespace = dict(
            frappe=self.frappe, _=lambda text: text, json=json, flt=flt, cint=lambda value: int(value or 0),
            currency=self.currency, credit_sales=self.credit,
            walk_in=Mock(billing_customer=Mock(return_value="CUSTOMER")),
            erpnext_compat=Mock(new_doc=Mock(side_effect=lambda *args: self.invoice)),
            resolve_price_list=Mock(return_value="Selling"),
            _resolve_delivery_app=Mock(return_value=None),
            _build_lines=lambda items, *args: [dict(item_code="POT", price=195, qty=row["qty"],
                                                  uom="Nos", stock_uom="Nos", conversion_factor=1) for row in items],
            _price_overrides=Mock(return_value=[]),
            _apply_bundles=lambda items, *args: ([0] * len(items), []),
            get_active_promotions=Mock(return_value=[]), coupons=Mock(),
            evaluate=lambda cart, *args: dict(line_discounts=[0] * len(cart["items"]), basket_discount=0, applied=[]),
            now_datetime=Mock(), _check_price_edit_permission=Mock(), _check_discount_passcode=Mock(),
            _ensure_ignore_pricing_rule=Mock(), _sale_doctype=Mock(return_value="POS Invoice"),
            _build_remarks=Mock(return_value=""), _set_custom=Mock(),
            _compute_return_groups=lambda items, *args: [None] * len(items),
            _validate_line_serials=Mock(return_value=[]), salespeople=Mock(for_sale=Mock(return_value=None)),
            _apply_service_charge=Mock(), discount_breakdown=discount_breakdown,
            _require_sell=Mock(), _quote_session=Mock(return_value=None), _cashback_estimate=Mock(return_value=0),
        )
        tree = ast.parse(Path(__file__).with_name("sales.py").read_text(encoding="utf-8"))
        names = {"_build_sale_invoice", "_discount_breakdown", "_reconcile_payment", "_assert_on_account", "_set_payment", "quote_sale"}
        selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        for node in selected:
            node.decorator_list = []
        exec(compile(ast.Module(body=selected, type_ignores=[]), "sales.py", "exec"), self.namespace)

    def build(self, qty=1, **discounts):
        payload = dict(items=[dict(item_code="POT", qty=qty, **discounts)])
        return self.namespace["_build_sale_invoice"](self.profile, payload)[0]

    def test_regular_item_keeps_full_price_and_no_savings(self):
        doc = self.build()
        self.assertEqual(doc.grand_total, 195)
        self.assertEqual(doc.items[0].discount_amount, 0)

    def test_quote_endpoint_returns_payable_credit_and_native_tax_breakdown(self):
        for erp in (False, True):
            with self.subTest(erp_pricing=erp):
                self.erp = erp
                self.invoice = Invoice()
                result = self.namespace["quote_sale"](dict(pos_profile="Till", items=[dict(item_code="POT", qty=1)]))
                self.assertEqual(result["payable"], 195)
                self.assertEqual(result["on_account"]["available"], 10000)
                self.assertEqual(result["erp_pricing"]["enabled"], erp)
                self.assertEqual(result["tax_breakdown"], dict(exclusive=[], included=[], exclusiveTotal=0) if erp else None)

    def test_erp_pricing_without_a_rule_does_not_make_every_item_free(self):
        self.erp = True
        doc = self.build(qty=2)
        self.assertEqual(doc.grand_total, 390)
        self.assertEqual(doc.items[0].discount_percentage, 0)
        self.assertEqual(doc.flags.esafepos_erp_pricing["discount_total"], 0)
        self.assertEqual([call[-1]["ignore"] for call in self.namespace["_ensure_ignore_pricing_rule"].call_args_list],
                         [False, True])

    def test_erp_percentage_rule_is_resolved_before_manual_discount(self):
        self.erp = True
        self.invoice = Invoice(native_discount=10, native_rule='["RULE"]')
        doc = self.build(qty=2, manual_discount_percent=20)
        self.assertEqual(doc.grand_total, 280.80)
        self.assertEqual(doc.flags.esafepos_erp_pricing["discount_total"], 39)
        self.assertEqual(doc.items[0].pricing_rules, "")
        self.assertEqual(doc.ignore_pricing_rule, 1)
        # Insert / submit recalculates totals: the frozen rate must survive.
        doc.run_method("calculate_taxes_and_totals")
        self.assertEqual(doc.grand_total, 280.80)

    def test_fixed_rule_rate_and_genuine_free_rule_are_preserved(self):
        self.erp = True
        for invoice, total in ((Invoice(native_rate=150, native_rule='["RULE"]'), 150),
                               (Invoice(native_discount=100, native_rule='["FREE"]'), 0)):
            with self.subTest(total=total):
                self.invoice = invoice
                self.assertEqual(self.build().grand_total, total)

    def test_manual_amount_discount_uses_quantity_and_sale_currency(self):
        self.ctx = Record(foreign=True, factor=0.5, currency="USD")
        doc = self.build(qty=2, manual_discount_method="amount", manual_discount_amount=10)
        self.assertEqual(doc.grand_total, 175)

    def test_full_and_split_account_sale_use_correct_total(self):
        self.erp = True
        for cash in (0, 50):
            with self.subTest(cash=cash):
                self.invoice = Invoice()
                doc = self.build()
                self.namespace["_set_payment"](doc, "Credit Sale", 195 - cash)
                if cash:
                    self.namespace["_set_payment"](doc, "Cash", cash)
                self.namespace["_reconcile_payment"](doc, self.profile)
                self.namespace["_assert_on_account"](doc, "CUSTOMER", self.profile)
                self.credit.assert_sale.assert_called_with("CUSTOMER", "Shop", 195 - cash, "LKR", "LKR")

    def test_account_sale_cannot_give_change_from_debt(self):
        doc = self.build()
        self.namespace["_set_payment"](doc, "Credit Sale", 195)
        self.namespace["_set_payment"](doc, "Cash", 1)
        with self.assertRaisesRegex(ValueError, "change out of a debt"):
            self.namespace["_assert_on_account"](doc, "CUSTOMER", self.profile)


if __name__ == "__main__":
    unittest.main()
