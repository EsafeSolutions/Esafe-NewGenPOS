"""Catalogue permissions, complete paging and authoritative unit-offer checks."""
import importlib
import json
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class D(dict):
    __getattr__ = dict.get


fake = types.ModuleType("frappe")
fake._ = lambda value: value
fake._dict = D
fake.PermissionError = PermissionError
fake.whitelist = lambda *a, **kw: lambda fn: fn
fake.throw = lambda message, kind=ValueError: (_ for _ in ()).throw(kind(message))
utils = types.ModuleType("frappe.utils")
utils.flt = lambda value, precision=None: round(float(value or 0), precision) if precision is not None else float(value or 0)
utils.now_datetime = lambda: datetime(2026, 11, 27, 12)
sys.modules.update({"frappe": fake, "frappe.utils": utils})
permissions = types.ModuleType("esafepos.api.permissions")
permissions.PRINT_LABELS = "Print labels"
permissions.allowed = Mock(return_value=True)
permissions.assert_outlet = Mock()
sys.modules[permissions.__name__] = permissions
books = types.ModuleType("esafepos.price_books")
books.effective_prices = Mock()
books.standard_prices = Mock()
books.resolve_price_list = Mock(return_value="Retail price list")
sys.modules[books.__name__] = books
loader = types.ModuleType("esafepos.promotions.loader")
loader.get_active_promotions = Mock()
sys.modules[loader.__name__] = loader
catalog = types.ModuleType("esafepos.api.catalog")
catalog.internal_item_codes = lambda: {"INTERNAL"}
catalog.item_groups_under = lambda groups: ["Retail", "Retail Child"] if groups else None
sys.modules[catalog.__name__] = catalog
labels = types.ModuleType("esafepos.api.labels")
labels._tax_factors = Mock()
sys.modules[labels.__name__] = labels
features = types.ModuleType("esafepos.features")
features.enabled = Mock(return_value=False)
sys.modules[features.__name__] = features
currency = types.ModuleType("esafepos.currency")
currency.company_currency = lambda company: "LKR"
sys.modules[currency.__name__] = currency
native = types.ModuleType("erpnext.accounts.doctype.pricing_rule.pricing_rule")
native.get_pricing_rule_for_item = Mock()
sys.modules[native.__name__] = native
api = importlib.import_module("esafepos.api.print_catalogue")


def item(code="A", **extra):
    return D(name=code, item_name="Synthetic item " + code, item_group="Retail", brand="Example brand",
             stock_uom="Nos", description="<p>Full description தமிழ் සිංහල</p>", image="/files/item.png", **extra)


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        permissions.allowed.return_value = True
        permissions.assert_outlet.reset_mock(side_effect=True)
        fake.has_permission = Mock(return_value=True)
        self.profile = D(name="Till A", company="Synthetic company", currency="LKR", customer="Walk-in", selling_price_list="Retail", warehouse="Outlet warehouse", item_groups=[])
        fake.get_cached_doc = Mock(return_value=self.profile)
        fake.get_cached_value = Mock(return_value="Retail")
        fake.get_list = Mock(return_value=[item()])
        books.effective_prices.side_effect = lambda profile, codes, *a, **kw: {code: 100 for code in codes}
        books.standard_prices.side_effect = lambda profile, codes, **kw: {code: 120 for code in codes}
        labels._tax_factors.side_effect = lambda profile, codes, prices: {code: 1.15 for code in codes}
        loader.get_active_promotions.return_value = []
        features.enabled.return_value = False
        native.get_pricing_rule_for_item.reset_mock()
        native.get_pricing_rule_for_item.return_value = {}

    def test_capability_and_native_item_permission_both_required(self):
        for capability, read in ((False, True), (True, False)):
            permissions.allowed.return_value = capability
            fake.has_permission.return_value = read
            with self.assertRaises(PermissionError):
                api.page("Till A")
        fake.get_list.assert_not_called()

    def test_outlet_access_and_disabled_profile(self):
        permissions.assert_outlet.side_effect = PermissionError("Denied")
        with self.assertRaises(PermissionError):
            api.page("Other outlet")
        fake.get_list.assert_not_called()
        permissions.assert_outlet.side_effect = None
        self.profile.disabled = True
        self.profile["disabled"] = 1
        with self.assertRaises(ValueError):
            api.page("Till A")

    def test_keyset_pages_return_every_item_without_offset_truncation(self):
        table = [item("I%04d" % i) for i in range(431)]
        fake.get_list.side_effect = lambda doctype, **kw: [row for row in table if row.name > next((f[2] for f in kw["filters"] if f[:2] == ["name", ">"]), "")][:kw["limit_page_length"]]
        codes, after = [], ""
        while True:
            data = api.page("Till A", after)
            codes += [row["item_code"] for row in data["items"]]
            if not data["has_more"]:
                break
            after = data["next"]
        self.assertEqual(codes, [row.name for row in table])
        self.assertEqual(len(codes), len(set(codes)))

    def test_item_and_outlet_group_restrictions_are_in_permission_aware_query(self):
        self.profile["item_groups"] = [D(item_group="Retail")]
        api.page("Till A", "LAST")
        filters = fake.get_list.call_args.kwargs["filters"]
        for expected in (["disabled", "=", 0], ["is_sales_item", "=", 1], ["has_variants", "=", 0],
                         ["name", ">", "LAST"], ["name", "not in", ["INTERNAL"]], ["item_group", "in", ["Retail", "Retail Child"]]):
            self.assertIn(expected, filters)

    def test_single_unit_discount_price_book_reference_and_tax(self):
        loader.get_active_promotions.return_value = [{"name": "AUTO", "title": "Ten percent", "promotion_type": "Simple Discount", "apply_on_all": 1, "discount_type": "Percentage", "discount_value": 10}]
        row = api.page("Till A")["items"][0]
        self.assertEqual(row["price"], 103.5)
        self.assertEqual(row["regular_price"], 138)
        self.assertEqual(row["offers"], ["Ten percent"])
        loader.get_active_promotions.assert_called_with("Till A")

    def test_conditional_offer_is_labelled_not_advertised_as_unit_discount(self):
        loader.get_active_promotions.return_value = [{"name": "BASKET", "title": "Spend 1000", "promotion_type": "Spend and Save", "apply_on_all": 1, "min_spend": 1000, "basket_discount_type": "Percentage", "basket_discount_value": 10}]
        row = api.page("Till A")["items"][0]
        self.assertEqual(row["price"], 115)
        self.assertEqual(row["offers"], ["Spend 1000 (conditions apply)"])

    def test_coupon_and_expired_discounts_do_not_leak(self):
        loader.get_active_promotions.return_value = [{"name": "LOCKED", "title": "Secret deal", "promotion_type": "Simple Discount", "apply_on_all": 1, "requires_coupon": 1, "coupon_code": "SECRET", "discount_type": "Percentage", "discount_value": 100},
                                                   {"name": "OLD", "title": "Expired", "promotion_type": "Simple Discount", "apply_on_all": 1, "end_date": "2025-01-01", "discount_type": "Percentage", "discount_value": 100}]
        data = api.page("Till A")
        self.assertEqual(data["items"][0]["price"], 115)
        self.assertNotIn("SECRET", json.dumps(data))
        self.assertEqual(data["items"][0]["offers"], [])

    def test_no_price_and_free_promotion_are_distinct(self):
        books.effective_prices.side_effect = lambda *a, **kw: {}
        self.assertTrue(api.page("Till A")["items"][0]["unpriced"])
        books.effective_prices.side_effect = lambda *a, **kw: {"A": 100}
        loader.get_active_promotions.return_value = [{"name": "FREE", "title": "Free today", "promotion_type": "Simple Discount", "apply_on_all": 1, "discount_type": "Percentage", "discount_value": 100}]
        row = api.page("Till A")["items"][0]
        self.assertFalse(row["unpriced"])
        self.assertEqual(row["price"], 0)

    def test_native_rules_use_single_unit_default_customer_without_double_promos(self):
        features.enabled.return_value = True
        native.get_pricing_rule_for_item.return_value = {"discount_percentage": 20, "has_pricing_rule": 1}
        row = api.page("Till A")["items"][0]
        self.assertEqual(row["price"], 92)
        args = native.get_pricing_rule_for_item.call_args.args[0]
        self.assertEqual((args.qty, args.customer, args.company), (1, "Walk-in", "Synthetic company"))
        self.assertEqual(args.price_list, "Retail price list")
        self.assertEqual((args.parenttype, args.pos_profile, args.warehouse), ("POS Invoice", "Till A", "Outlet warehouse"))

    def test_native_flat_discount_not_counted_twice_with_percentage(self):
        features.enabled.return_value = True
        native.get_pricing_rule_for_item.return_value = {"price_list_rate": 100, "discount_percentage": 10, "discount_amount": 10}
        self.assertEqual(api.page("Till A")["items"][0]["price"], 103.5)

    def test_native_margin_and_rate_rule_preserve_pre_discount_reference(self):
        features.enabled.return_value = True
        native.get_pricing_rule_for_item.return_value = {"price_list_rate": 150, "margin_type": "Amount", "margin_rate_or_amount": 20, "discount_amount": 10}
        row = api.page("Till A")["items"][0]
        self.assertEqual(row["price"], 184)
        self.assertEqual(row["regular_price"], 195.5)

    def test_description_keeps_full_safe_unicode_text(self):
        self.assertEqual(api.description_text('<p>தமிழ் &amp; සිංහල</p><script>secret()</script><p>Next<br>line</p>'), "தமிழ் & සිංහල\nNext\nline")


if __name__ == "__main__":
    unittest.main()
