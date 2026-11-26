"""Standalone design and raw visibility checks; no ERP or printer connection."""
import importlib
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from esafepos.receipt_design import clean_receipt_design

fake = types.ModuleType("frappe")
fake._ = lambda value: value
fake.whitelist = lambda *a, **kw: lambda fn: fn
utils = types.ModuleType("frappe.utils")
utils.cint = lambda value: int(value or 0)
utils.flt = lambda value: float(value or 0)
sales = types.ModuleType("esafepos.api.sales")
sales.get_receipt = lambda *a, **kw: None
sys.modules.update({"frappe": fake, "frappe.utils": utils, "esafepos.api.sales": sales})
printing = importlib.import_module("esafepos.api.printing")


class ReceiptDesignTests(unittest.TestCase):
    def test_design_roundtrip_and_zero_values(self):
        value = {"headerAlign": "right", "paddingRight": 2, "paddingTop": 0, "borderWidth": 0}
        self.assertEqual(clean_receipt_design(value), value)
        self.assertEqual(clean_receipt_design('{"paddingLeft":0}'), {"paddingLeft": 0})
        self.assertEqual(clean_receipt_design(None), {})

    def test_reject_unsafe_invalid_and_excessive_values(self):
        for value in ({"css": "url(x)"}, {"headerAlign": "justify"}, {"fontSize": 100}, {"fontSize": True},
                      {"paddingRight": -1}, {"lineHeight": float("nan")}, [], "[1]"):
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                clean_receipt_design(value)

    def test_raw_section_switches_keep_financial_totals_and_redemption(self):
        for template in ("Retail", "Table"):
            for roll in ("58mm", "80mm"):
                receipt = {"name": "TEST-DESIGN", "company": "Synthetic shop", "posting_date": "2026-11-26",
                           "posting_time": "12:00:00", "customer_name": "Synthetic", "currency": "LKR",
                           "grand_total": 120, "gross_total": 125, "loyalty_amount": 10,
                           "loyalty_points_earned": 5, "loyalty": {"balance": 20},
                           "items": [{"item_name": "Test item", "qty": 1, "rate": 120, "amount": 120}],
                           "receipt_settings": {"receipt_template": template, "receipt_paper_width": roll,
                                                "receipt_show_loyalty": 0, "receipt_show_mrp": 0,
                                                "receipt_show_line_discount": 0, "receipt_show_gross_total": 0,
                                                "receipt_show_item_count": 0, "receipt_show_total_qty": 0,
                                                "receipt_show_footer": 0, "receipt_show_invoice_barcode": 0}}
                data = printing.build_receipt_bytes(receipt)
                for hidden in (b"MRP", b"GROSS TOTAL", b"POINTS BALANCE", b"LOYALTY POINTS", b"ITEMS", b"TOTAL QTY", b"Thank you!"):
                    self.assertNotIn(hidden, data)
                self.assertIn(b"NET TOTAL", data)
                self.assertIn(b"120.00", data)
                self.assertIn(b"LOYALTY REDEEMED", data)
                self.assertNotIn(b"\x1bp", data)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReceiptDesignTests)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromName("esafepos.api.test_printing"))
    result = unittest.TextTestRunner().run(suite)
    sys.exit(not result.wasSuccessful())
