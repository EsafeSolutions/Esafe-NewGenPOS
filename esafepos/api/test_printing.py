import unittest

from esafepos.api.printing import build_receipt_bytes
from esafepos.receipt_options import RECEIPT_BRAND, receipt_footer


class ReceiptPrintingTests(unittest.TestCase):
    def setUp(self):
        self.receipt = {
            "name": "POS-001",
            "company": "Esafe Retail",
            "posting_date": "2026-11-15",
            "posting_time": "14:05:00",
            "customer_name": "Walk-in",
            "currency": "LKR",
            "grand_total": 240.0,
            "items": [{
                "item_name": "Wholegrain crackers family pack",
                "qty": 2, "rate": 120, "price_list_rate": 125,
                "line_discount_amount": 10, "amount": 240,
            }],
        }

    def test_footer_preserves_shop_message_and_adds_one_brand_line(self):
        custom = {"receipt_footer": "Visit again!\r\n  " + RECEIPT_BRAND}
        self.assertEqual(receipt_footer(custom), "Visit again!\n" + RECEIPT_BRAND)
        self.assertEqual(receipt_footer({}), RECEIPT_BRAND)

    def test_all_thermal_templates_print_the_invoice_barcode_before_cutting(self):
        for template in ("Retail", "Compact", "Standard", "Detailed", "Table"):
            with self.subTest(template=template):
                self.receipt["receipt_settings"] = {"receipt_template": template, "receipt_paper_width": "58mm"}
                output = build_receipt_bytes(self.receipt)
                self.assertIn(b"\x1dv0\x00", output)
                self.assertEqual(output.count(self.receipt["name"].encode("ascii")), 2)

    def test_contact_used_as_customer_name_prints_once_with_walk_in_code(self):
        self.receipt.update(walk_in_code="W-1234", customer_name="0771234567", customer_phone="0771234567")
        for template in ("Retail", "Standard", "Table"):
            with self.subTest(template=template):
                self.receipt["receipt_settings"] = {"receipt_template": template}
                output = build_receipt_bytes(self.receipt)
                self.assertIn(b"W-1234", output)
                self.assertEqual(output.count(b"0771234567"), 1)

    def test_thermal_footer_on_all_templates(self):
        for template in ("Retail", "Compact", "Standard", "Detailed", "Table"):
            with self.subTest(template=template):
                self.receipt["receipt_settings"] = {
                    "receipt_template": template, "receipt_paper_width": "58mm",
                    "receipt_footer": "Visit again!\n" + RECEIPT_BRAND,
                }
                output = build_receipt_bytes(self.receipt)
                self.assertEqual(output.count(RECEIPT_BRAND.encode("ascii")), 1)
                self.assertIn(b"Visit again!\n" + RECEIPT_BRAND.encode("ascii") + b"\n", output)

    def test_table_grid_fits_both_rolls_and_preserves_long_cells(self):
        self.receipt["items"][0].update(qty=1234567, amount=123456789.12)
        for paper, width in (("58mm", 32), ("80mm", 42)):
            with self.subTest(paper=paper):
                self.receipt["receipt_settings"] = {"receipt_template": "Table", "receipt_paper_width": paper}
                lines = build_receipt_bytes(self.receipt).splitlines()
                grid = [line for line in lines if line.startswith((b"|", b"+"))]
                self.assertEqual(sum(line.startswith(b"+") for line in grid), 3)
                self.assertTrue(all(len(line) == width for line in grid))
                self.assertIn(b"AMOUNT", grid[1])
                self.assertIn(b"crackers", b" ".join(grid))
                values = grid[3:-1]
                price = b"".join(line.split(b"|")[-2].strip() for line in values if line.count(b"|") == 5)
                self.assertEqual(price, b"123,456,789.12")
