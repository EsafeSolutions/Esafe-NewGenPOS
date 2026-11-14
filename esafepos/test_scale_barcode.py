# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "ESAFEPOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
from __future__ import annotations

import unittest
from esafepos.scale_barcode import parse_scale_barcode


class TestScaleBarcode(unittest.TestCase):
    def test_standard_ean13_scale_barcode(self):
        # EAN-13: prefix "20", PLU "01234", weight "01500" (1.500 kg), check digit "6"
        res = parse_scale_barcode("2001234015006")
        self.assertIsNotNone(res)
        self.assertTrue(res["is_scale_barcode"])
        self.assertEqual(res["prefix"], "20")
        self.assertEqual(res["plu"], "01234")
        self.assertEqual(res["weight"], 1.5)
        self.assertEqual(res["check_digit"], "6")
        self.assertIn("2001234", res["candidates"])
        self.assertIn("01234", res["candidates"])
        self.assertIn("1234", res["candidates"])

    def test_standard_ean13_fractional_weight(self):
        # EAN-13: prefix "21", PLU "00450", weight "00325" (0.325 kg), check digit "1"
        res = parse_scale_barcode("2100450003251")
        self.assertIsNotNone(res)
        self.assertEqual(res["prefix"], "21")
        self.assertEqual(res["plu"], "00450")
        self.assertEqual(res["weight"], 0.325)
        self.assertIn("2100450", res["candidates"])
        self.assertIn("00450", res["candidates"])
        self.assertIn("450", res["candidates"])

    def test_upca_12_digit_scale_barcode(self):
        # 12-digit UPC-A: starts with 2, PLU 01234, weight 01500, check 6
        res = parse_scale_barcode("201234015006")
        self.assertIsNotNone(res)
        self.assertEqual(res["prefix"], "02")
        self.assertEqual(res["plu"], "01234")
        self.assertEqual(res["weight"], 1.5)
        self.assertIn("0201234", res["candidates"])
        self.assertIn("01234", res["candidates"])

    def test_custom_plu_length_4(self):
        # Prefix "20", 4-digit PLU "1234", weight "015000" (15.000 kg or 1.500 with custom decimals)
        res = parse_scale_barcode("2012340150009", plu_len=4, decimals=3)
        self.assertIsNotNone(res)
        self.assertEqual(res["plu"], "1234")
        self.assertEqual(res["weight"], 15.0)
        self.assertIn("201234", res["candidates"])
        self.assertIn("1234", res["candidates"])

    def test_custom_prefix_filter(self):
        # If prefixes are restricted to ["20"], prefix "25" should return None
        res_allowed = parse_scale_barcode("2001234015006", prefixes=["20"])
        self.assertIsNotNone(res_allowed)

        res_rejected = parse_scale_barcode("2501234015006", prefixes=["20"])
        self.assertIsNone(res_rejected)

    def test_invalid_barcodes_ignored(self):
        self.assertIsNone(parse_scale_barcode(None))
        self.assertIsNone(parse_scale_barcode(""))
        self.assertIsNone(parse_scale_barcode("12345"))  # too short
        self.assertIsNone(parse_scale_barcode("6281000001237"))  # standard regular commercial barcode (prefix 62)
        self.assertIsNone(parse_scale_barcode("2001234000000"))  # zero weight
        self.assertIsNone(parse_scale_barcode("2001234ABCDE5"))  # non-numeric


if __name__ == "__main__":
    unittest.main()
