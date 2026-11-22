import unittest
from esafepos.print_config import defaults, validate


class PrintDefaultsTests(unittest.TestCase):
    def test_upgrade_does_not_enable_silent_or_automatic_printing(self):
        self.assertEqual(defaults({}), {"silent": False, "automatic_receipt": False, "receipt_output": "html", "copies": 1, "document_paper": "A4"})

    def test_preserves_configured_defaults(self):
        self.assertEqual(defaults({"esafepos_silent_printing": 1, "esafepos_auto_print_receipt": 1, "esafepos_print_copies": 2})["copies"], 2)

    def test_rejects_unsupported_options(self):
        for value in ({"copies": 0}, {"copies": 100}, {"copies": True}, {"copies": 1.5}, {"receipt_output": "qz"}, {"document_paper": "arbitrary"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate(value)

    def test_ignores_unrelated_profile_fields(self):
        result = validate({"silent": True, "warehouse": "Unrelated", "copies": 1})
        self.assertNotIn("warehouse", result)
        self.assertEqual(result["silent"], 1)


if __name__ == "__main__":
    unittest.main()
