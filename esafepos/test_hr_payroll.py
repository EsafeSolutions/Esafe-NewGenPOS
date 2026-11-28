"""Standalone earnings rules; no Frappe installation required."""
import unittest
from esafepos.hr_payroll import monthly_period, commission_earnings, number


class HRPayrollRulesTests(unittest.TestCase):
    def test_month_requires_canonical_calendar_period(self):
        self.assertEqual(str(monthly_period("2024-02")[1]), "2024-02-29")
        for value in ("2026-2", "2026-13", "2026-11-01", "0000-01", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                monthly_period(value)

    def test_invalid_and_infinite_amounts_are_rejected(self):
        for value in ("NaN", "Infinity", "abc", float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                number(value)

    def invoice(self, name="INV1", incentive=100, **extra):
        result = {"doctype": "Sales Invoice", "name": name, "docstatus": 1, "base_net_total": 1000,
                  "sales_team": [{"sales_person": "Seller", "allocated_percentage": 100, "incentives": incentive}]}
        result.update(extra)
        return result

    def test_returns_and_consolidated_invoices_do_not_duplicate_sales(self):
        sale = self.invoice(doctype="POS Invoice")
        rows = [sale, dict(sale), self.invoice("MERGED", is_consolidated=1),
                self.invoice("RET", incentive=-40, is_return=1), self.invoice("DRAFT", docstatus=0), self.invoice("CANCEL", docstatus=2)]
        result = commission_earnings(rows, {"Seller": "EMP1"})
        self.assertEqual(result["EMP1"]["amount"], 60)
        self.assertEqual(len(result["EMP1"]["sources"]), 2)

    def test_commission_currency_rounding(self):
        for precision, expected in ((0, 12), (2, 12.35), (3, 12.345)):
            result = commission_earnings([self.invoice(incentive="12.345")], {"Seller": "EMP1"}, precision=precision)
            self.assertEqual(result["EMP1"]["amount"], expected)

    def test_shared_sale_uses_native_incentives(self):
        row = self.invoice(sales_team=[{"sales_person": "A", "allocated_percentage": 70, "incentives": 140},
                                      {"sales_person": "B", "allocated_percentage": 30, "incentives": 30}])
        result = commission_earnings([row], {"A": "EMP1", "B": "EMP2"})
        self.assertEqual(result["EMP1"]["amount"], 140)
        self.assertEqual(result["EMP2"]["amount"], 30)

    def test_missing_employee_link_blocks_commission(self):
        with self.assertRaisesRegex(ValueError, "Link salesperson"):
            commission_earnings([self.invoice()], {})

    def test_invalid_team_allocation_blocks_commission(self):
        row = self.invoice()
        row["sales_team"][0]["allocated_percentage"] = 50
        with self.assertRaisesRegex(ValueError, "total 100%"):
            commission_earnings([row], {"Seller": "EMP1"})

    def test_negative_commission_is_retained_for_review(self):
        result = commission_earnings([self.invoice(incentive=-100)], {"Seller": "EMP1"})
        self.assertEqual(result["EMP1"]["amount"], -100)


if __name__ == "__main__":
    unittest.main()
