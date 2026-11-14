import json
import unittest
from pathlib import Path

from esafepos.api.discounts import discount_breakdown


class ManualDiscountTests(unittest.TestCase):
    def test_discount_boundaries_and_currency(self):
        fixtures = Path(__file__).resolve().parents[2] / "frontend" / "discount-scenarios.json"
        for case in json.loads(fixtures.read_text(encoding="utf-8")):
            with self.subTest(case=case["name"]):
                result = discount_breakdown(case["lines"], case["promo"], case["bundles"],
                                            case["order"], case.get("factor", 1))
                expected = case["expected"]
                for actual, wanted in zip(result["per_unit"], expected["perUnit"]):
                    self.assertAlmostEqual(actual, wanted)
                for actual, wanted in zip(result["manual"], expected["manual"]):
                    self.assertAlmostEqual(actual, wanted)
                self.assertAlmostEqual(result["order_total"], expected["orderTotal"])
                self.assertAlmostEqual(max(result["manual_percent"] + [result["order_percent"]]),
                                       expected["maxPercent"])

    def test_nonfinite_discounts_do_not_corrupt_totals(self):
        for value in (float("inf"), float("nan"), "invalid"):
            result = discount_breakdown(
                [dict(price=100, qty=2, manual_discount_method="amount", manual_discount_amount=value)],
                dict(line_discounts=[0]), [0], dict(enabled=True, method="amount", amount=value))
            self.assertEqual(result["per_unit"], [0])

    def test_basket_rounding_remainder_is_preserved(self):
        result = discount_breakdown([dict(price=10, qty=1) for _ in range(3)],
                                    dict(line_discounts=[0, 0, 0], basket_discount=1),
                                    [0, 0, 0], dict(enabled=False))
        self.assertAlmostEqual(sum(result["per_unit"]), 1)


if __name__ == "__main__":
    unittest.main()
