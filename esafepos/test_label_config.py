import unittest
from esafepos.label_config import number, validate_configuration


class LabelConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.stock = {"kind": "roll", "w": 32, "h": 25, "columns": 3, "rows": 1,
                      "gapX": 2, "gapY": 3, "left": 2, "right": 2, "top": 0, "bottom": 0,
                      "pageW": 104, "pageH": 25, "autoWidth": False}

    def test_accepts_exact_three_column_liner(self):
        self.assertEqual(validate_configuration({"stock": self.stock})["stock"]["pageW"], 104)

    def test_rejects_narrow_liner(self):
        self.stock["pageW"] = 100
        with self.assertRaises(ValueError):
            validate_configuration({"stock": self.stock})

    def test_rejects_fractional_columns(self):
        self.stock["columns"] = 2.5
        with self.assertRaises(ValueError):
            validate_configuration({"stock": self.stock})

    def test_rejects_nonfinite_and_boolean_dimensions(self):
        for value in (float("nan"), float("inf"), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                number(value, 1, 100, "size")

    def test_rejects_oversized_sheet(self):
        self.stock.update(kind="sheet", rows=10, pageH=250)
        with self.assertRaises(ValueError):
            validate_configuration({"stock": self.stock})

    def test_rejects_executable_template(self):
        for config in ({"design": {"elements": [{"type": "html", "text": "<script>"}]}},
                       {"stock": "html"}, {"design": []}, {"printer": None}):
            with self.subTest(config=config), self.assertRaises(ValueError):
                validate_configuration(config)

    def test_rejects_unbounded_elements(self):
        with self.assertRaises(ValueError):
            validate_configuration({"design": {"elements": [{}] * 81}})

    def test_keeps_exact_inch_measurements(self):
        self.stock.update(w=50.8, h=25.4, columns=1)
        result = validate_configuration({"stock": self.stock})
        self.assertEqual(result["stock"]["w"], 50.8)


if __name__ == "__main__":
    unittest.main()
