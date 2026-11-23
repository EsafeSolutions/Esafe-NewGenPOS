import unittest
from esafepos.label_config import number, validate_configuration


class LabelConfigurationTests(unittest.TestCase):
    def test_compact_barcode_options_are_declarative(self):
        for name in ("AUTO", "CODE128", "CODE93", "EAN13", "UPCA", "DATAMATRIX", "QRCODE"):
            with self.subTest(name=name):
                config = validate_configuration({"design": {"barcodeFormat": name, "autoFit": True}})
                self.assertEqual(config["design"]["barcodeFormat"], name)
        for design in ({"barcodeFormat": "SCRIPT"}, {"autoFit": "false"}):
            with self.subTest(design=design), self.assertRaises(ValueError):
                validate_configuration({"design": design})

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

    def test_rejects_retired_and_unknown_printer_routes(self):
        for route in ("qz", "bridge", "tcp"):
            with self.subTest(route=route), self.assertRaises(ValueError):
                validate_configuration({"printer": {"route": route}})

    def test_accepts_browser_printer_configuration(self):
        config = {"printer": {"route": "browser", "dpi": 300, "offsetX": 2}}
        self.assertEqual(validate_configuration(config), config)


if __name__ == "__main__":
    unittest.main()
