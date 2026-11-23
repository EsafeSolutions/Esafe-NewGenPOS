import json
import unittest

from esafepos.cash_count import allocate_count, clean_counts


class CashCountTests(unittest.TestCase):
    def breakdown(self, currency="LKR", rows=None):
        return {"Cash": {"currency": currency, "rows": rows or [
            {"kind": "notes", "value": 1000, "quantity": 2},
            {"kind": "coins", "value": 0.25, "quantity": 3}]}}

    def test_notes_and_coins_use_exact_decimal_arithmetic(self):
        result = clean_counts(json.dumps(self.breakdown()), {"Cash": 2000.75}, {"Cash": "LKR"})
        self.assertEqual(result["Cash"]["total"], 2000.75)

    def test_note_and_coin_may_have_same_value(self):
        raw = self.breakdown(rows=[{"kind": kind, "value": 10, "quantity": 1} for kind in ("notes", "coins")])
        self.assertEqual(clean_counts(raw, {"Cash": 20}, {"Cash": "LKR"})["Cash"]["total"], 20)

    def test_quantities_must_be_whole_nonnegative_and_finite(self):
        for qty in (-1, 0.5, "nan", "inf", "bad", True, 10000001):
            with self.subTest(qty=qty), self.assertRaises(ValueError):
                clean_counts(self.breakdown(rows=[{"kind": "notes", "value": 100, "quantity": qty}]), {"Cash": 0}, {"Cash": "LKR"})

    def test_rejects_mismatched_totals_currency_and_non_cash(self):
        for counted, currencies in (({"Cash": 2000}, {"Cash": "LKR"}), ({"Cash": 2000.75}, {"Cash": "USD"}), ({"Cash": 2000.75}, {})):
            with self.assertRaises(ValueError):
                clean_counts(self.breakdown(), counted, currencies)

    def test_rejects_invalid_duplicate_or_unbounded_denominations(self):
        for value in (-1, 0, "nan", "inf", "bad", 0.0001, 1000000001):
            with self.subTest(value=value), self.assertRaises(ValueError):
                clean_counts(self.breakdown(rows=[{"kind": "coins", "value": value, "quantity": 0}]), {"Cash": 0}, {"Cash": "LKR"})
        with self.assertRaises(ValueError):
            clean_counts(self.breakdown(rows=[{"kind": "notes", "value": 10, "quantity": 0}] * 2), {"Cash": 0}, {"Cash": "LKR"})

    def test_unknown_currency_accepts_custom_denominations(self):
        raw = self.breakdown("XYZ", [{"kind": "coins", "value": 0.005, "quantity": 20}])
        self.assertEqual(clean_counts(raw, {"Cash": 0.1}, {"Cash": "XYZ"})["Cash"]["total"], 0.1)

    def test_empty_breakdown_keeps_manual_count_available(self):
        self.assertEqual(clean_counts(None, {"Cash": 123}, {}), {})

    def test_allocation_preserves_total_and_nonnegative_cash(self):
        self.assertEqual(allocate_count(297, [100, 200]), [99, 198])
        self.assertEqual(allocate_count(5, [-10, 20]), [0, 5])
        for total, expected in ((0.01, [1] * 20), (0.10, [1] * 20), (100, [0, 0]), (1.23, [7, 11, 13])):
            parts = allocate_count(total, expected)
            self.assertAlmostEqual(sum(parts), total)
            self.assertTrue(all(v >= 0 for v in parts))

    def test_signed_non_cash_balances_keep_each_shift_expected_amount(self):
        self.assertEqual(allocate_count(-3690, [-1000, -2690], allow_negative=True), [-1000, -2690])
        self.assertEqual(allocate_count(50, [-100, 150], allow_negative=True), [-100, 150])


if __name__ == "__main__":
    unittest.main()
