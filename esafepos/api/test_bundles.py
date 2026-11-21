"""Bundle checkout boundaries, runnable without a Frappe bench."""
import ast
import datetime
import math
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class Record(SimpleNamespace):
    def get(self, key, default=None):
        return getattr(self, key, default)


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.throw.side_effect = ValueError
        self.bundle = Record(name="PACK50", title="Feed 50 kg pack", status="Active",
                             bundle_price=8750, pos_profiles=[],
                             items=[Record(item_code="FEED", qty=50, allocated_amount=0)])
        self.frappe.get_doc.return_value = self.bundle
        utils = ModuleType("frappe.utils")
        utils.getdate = lambda value: datetime.date.fromisoformat(value)
        utils.nowdate = lambda: "2026-11-20"
        scope = ModuleType("esafepos.scope")
        scope.applies_to = Mock(return_value=True)
        self.scope = scope
        self.modules = patch.dict(sys.modules, {"frappe.utils": utils, "esafepos.scope": scope})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        tree = ast.parse(Path(__file__).with_name("sales.py").read_text(encoding="utf-8"))
        selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_apply_bundles"]
        namespace = dict(frappe=self.frappe, math=math, _=lambda message: message,
                         flt=lambda value=0, precision=None: round(float(value or 0), precision)
                         if precision is not None else float(value or 0))
        exec(compile(ast.Module(body=selected, type_ignores=[]), "sales.py", "exec"), namespace)
        self.apply = namespace["_apply_bundles"]

    def price(self, count=1, qty=None, **fields):
        payload = [dict(item_code="FEED", bundle_key="PACK50#1", bundle_qty=count, **fields)]
        return self.apply(payload, [dict(item_code="FEED", price=1000, qty=qty if qty is not None else count * 50)], "Till")

    def test_multiple_packs_scale_price_and_stock_quantity(self):
        discounts, applied = self.price(3)
        self.assertEqual(discounts, [123750])
        self.assertEqual(150000 - discounts[0], 26250)
        self.assertEqual(applied[0]["savings"], 123750)

    def test_legacy_cart_defaults_to_one_pack(self):
        result = self.apply([dict(bundle_key="PACK50#old")], [dict(item_code="FEED", price=1000, qty=50)], "Till")
        self.assertEqual(result[0], [41250])

    def test_rejects_partial_zero_negative_nonfinite_or_fractional_packs(self):
        for count in (0, -1, 0.5, 1.5, float("inf"), float("nan")):
            with self.subTest(count=count), self.assertRaises(ValueError):
                self.price(count, qty=50)
        with self.assertRaises(ValueError):
            self.price(2, qty=50)

    def test_allocated_shares_scale_with_bundle_count(self):
        self.bundle.bundle_price = 100
        self.bundle.items = [Record(item_code="A", qty=1, allocated_amount=30),
                             Record(item_code="B", qty=2, allocated_amount=70)]
        payload = [dict(bundle_key="SET#1", bundle_qty=3) for _ in range(2)]
        lines = [dict(item_code="A", price=20, qty=3), dict(item_code="B", price=50, qty=6)]
        discounts, _ = self.apply(payload, lines, "Till")
        self.assertEqual(discounts, [-30, 90])
        self.assertEqual(sum(row["price"] * row["qty"] - discount for row, discount in zip(lines, discounts)), 300)

    def test_rejects_inconsistent_count_or_discount_and_duplicate_rows(self):
        lines = [dict(item_code="FEED", price=1000, qty=50), dict(item_code="FEED", price=1000, qty=50)]
        for overrides in ({"bundle_qty": 1}, {"bundle_discount_amount": 20}, {}):
            payload = [dict(bundle_key="PACK50#1", bundle_qty=2),
                       dict(bundle_key="PACK50#1", bundle_qty=2)]
            payload[1].update(overrides)
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.apply(payload, lines, "Till")

    def test_expiry_outlet_and_status_still_apply(self):
        self.bundle.valid_to = "2026-11-19"
        with self.assertRaises(ValueError):
            self.price(2)
        self.bundle.valid_to = None
        self.scope.applies_to.return_value = False
        with self.assertRaises(ValueError):
            self.price(2)
        self.scope.applies_to.return_value = True
        self.bundle.status = "Inactive"
        with self.assertRaises(ValueError):
            self.price(2)


class SellingUnitTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.throw.side_effect = ValueError
        self.frappe.db.get_single_value.return_value = 0
        self.frappe.get_cached_value.return_value = 1
        detail = Record(name="FEED", item_name="Loose feed", item_group="Feed", brand=None,
                        stock_uom="Kg", has_serial_no=0)
        self.frappe.get_all.side_effect = lambda doctype, **kw: [detail] if doctype == "Item" else ["25 kg Pack", "50 kg Pack"]
        units = ModuleType("esafepos.item_units")
        units.conversions = Mock(return_value={("FEED", "25 kg Pack"): 25, ("FEED", "50 kg Pack"): 50})
        units.prices_by_unit = Mock(return_value={("FEED", "25 kg Pack"): 4500, ("FEED", "50 kg Pack"): 8750})
        catalog = ModuleType("esafepos.api.catalog")
        catalog.stock_levels = Mock(return_value={"FEED": 101.25})
        self.modules = patch.dict(sys.modules, {"esafepos.item_units": units, "esafepos.api.catalog": catalog})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.namespace = dict(frappe=self.frappe, _=lambda message: message, cint=int,
                              flt=lambda value=0, precision=None: round(float(value or 0), precision)
                              if precision is not None else float(value or 0),
                              effective_prices=Mock(return_value={"FEED": 1000}),
                              standard_prices=Mock(return_value={"FEED": 1000}), _split_tags=lambda value: [])
        tree = ast.parse(Path(__file__).with_name("sales.py").read_text(encoding="utf-8"))
        selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name in ("_build_lines", "_assert_alternate_unit_stock")]
        exec(compile(ast.Module(body=selected, type_ignores=[]), "sales.py", "exec"), self.namespace)
        self.profile = Record(selling_price_list="Standard Selling", warehouse="Shelf")

    def test_server_prices_pack_and_loose_units_and_uses_stock_conversions(self):
        lines = self.namespace["_build_lines"]([
            dict(item_code="FEED", qty=2, uom="50 kg Pack", price=1),
            dict(item_code="FEED", qty=1.25),
            dict(item_code="FEED", qty=1, uom="25 kg Pack"),
        ], self.profile)
        self.assertEqual([(row["uom"], row["price"], row["conversion_factor"]) for row in lines],
                         [("50 kg Pack", 8750, 50), ("Kg", 1000, 1), ("25 kg Pack", 4500, 25)])
        self.assertEqual(sum(row["qty"] * row["conversion_factor"] for row in lines), 126.25)

    def test_rejects_fractional_pack_and_unknown_unit(self):
        for unit, qty in (("50 kg Pack", 1.5), ("Unknown pack", 1)):
            with self.subTest(unit=unit), self.assertRaises(ValueError):
                self.namespace["_build_lines"]([dict(item_code="FEED", qty=qty, uom=unit)], self.profile)

    def test_stock_boundary_counts_packs_loose_and_bundle_components_together(self):
        invoice = Record(items=[Record(item_code="FEED", qty=1, uom="50 kg Pack", stock_uom="Kg", conversion_factor=50),
                                Record(item_code="FEED", qty=50, uom="Kg", stock_uom="Kg", conversion_factor=1),
                                Record(item_code="FEED", qty=1.25, uom="Kg", stock_uom="Kg", conversion_factor=1)])
        self.namespace["_assert_alternate_unit_stock"](invoice, self.profile)
        invoice.items[-1].qty = 1.2501
        with self.assertRaises(ValueError):
            self.namespace["_assert_alternate_unit_stock"](invoice, self.profile)


if __name__ == "__main__":
    unittest.main()
