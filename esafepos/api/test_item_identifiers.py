"""Identifier generation checks runnable without a Frappe bench."""
import ast
import json
from pathlib import Path
from random import SystemRandom
import unittest
from unittest.mock import Mock, patch


class ItemIdentifierTests(unittest.TestCase):
    def setUp(self):
        self.frappe = Mock()
        self.frappe.PermissionError = PermissionError
        self.frappe.throw.side_effect = self.fail_request
        self.frappe.whitelist.side_effect = lambda **kwargs: lambda fn: fn
        self.frappe.db.exists.return_value = False
        self.ns = {
            "frappe": self.frappe, "_": lambda value: value, "json": json,
            "IDENTIFIER_RANDOM": SystemRandom(), "_profile": Mock(),
            "_can_create": Mock(return_value=True),
        }
        tree = ast.parse(Path(__file__).with_name("items.py").read_text(encoding="utf-8"))
        names = {"_require", "_identifier_candidate", "generate_identifier"}
        selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        exec(compile(ast.Module(body=selected, type_ignores=[]), "items.py", "exec"), self.ns)

    @staticmethod
    def fail_request(message, kind=ValueError):
        raise kind(message)

    def generate(self, **kwargs):
        return self.ns["generate_identifier"]("Till A", **kwargs)["value"]

    def test_five_digit_numeric_default_and_leading_zeroes(self):
        random = Mock()
        random.choice.side_effect = list("00123")
        self.ns["IDENTIFIER_RANDOM"] = random
        self.assertEqual(self.generate(), "00123")
        self.ns["_profile"].assert_called_once_with("Till A")

    def test_numeric_lengths_preserve_exact_width(self):
        for length in (1, 5, 12, 140, "5"):
            with self.subTest(length=length):
                value = self.generate(length=length)
                self.assertRegex(value, r"^[0-9]+$")
                self.assertEqual(len(value), int(length))

    def test_mixed_codes_always_include_a_letter_and_a_digit(self):
        for length in (2, 5, 140):
            for _attempt in range(10):
                value = self.generate(character_type="alphanumeric", length=length)
                self.assertEqual(len(value), length)
                self.assertRegex(value, r"^[A-Z0-9]+$")
                self.assertRegex(value, r"[A-Z]")
                self.assertRegex(value, r"[0-9]")

    def test_invalid_lengths_and_formats_rejected_before_database_lookup(self):
        cases = [{"length": value} for value in (0, -1, 141, 5.5, 5.0, True, None, "", "abc", "5.0", "²", "9999")]
        cases += [{"character_type": "alphanumeric", "length": 1},
                  {"character_type": "letters"}, {"target": "customer"}]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.generate(**args)
        self.frappe.db.exists.assert_not_called()

    def test_retries_existing_item_names_codes_barcodes_and_unsaved_values(self):
        def exists(doctype, filters):
            return (doctype == "Item" and filters == "10000"
                    or doctype == "Item" and filters == {"item_code": "20000"}
                    or doctype == "Item Barcode" and filters == {"barcode": "30000"})
        self.frappe.db.exists.side_effect = exists
        candidate = Mock(side_effect=["10000", "20000", "30000", "40000", "50000"])
        with patch.dict(self.ns, {"_identifier_candidate": candidate}):
            self.assertEqual(self.generate(exclude='["40000"]'), "50000")
        self.assertEqual(candidate.call_count, 5)

    def test_unsaved_exclusions_are_case_insensitive(self):
        with patch.dict(self.ns, {"_identifier_candidate": Mock(side_effect=["A1234", "B1234"])}):
            self.assertEqual(self.generate(character_type="alphanumeric", exclude=[" a1234 "]), "B1234")

    def test_exhaustion_has_a_bounded_retry_and_actionable_message(self):
        self.frappe.db.exists.return_value = True
        candidate = Mock(return_value="00000")
        with patch.dict(self.ns, {"_identifier_candidate": candidate}), \
                self.assertRaisesRegex(ValueError, "Increase the length"):
            self.generate()
        self.assertEqual(candidate.call_count, 100)

    def test_exclusion_payload_is_validated(self):
        for value in ("bad json", "{}", 1, [1], ["a" * 141], [""] * 1001):
            with self.subTest(value=str(value)[:30]), self.assertRaises(ValueError):
                self.generate(exclude=value)
        self.frappe.db.exists.assert_not_called()

    def test_creation_permissions_required_for_new_item_and_barcode(self):
        self.ns["_can_create"].return_value = False
        for target in ("item_code", "barcode"):
            with self.subTest(target=target), self.assertRaises(PermissionError):
                self.generate(target=target)
        self.frappe.db.exists.assert_not_called()

    def test_existing_barcode_requires_document_read_and_write(self):
        self.ns["_can_create"].return_value = False
        self.generate(target="barcode", item_code="ITEM-A")
        item = self.frappe.get_doc.return_value
        self.assertEqual(item.check_permission.call_args_list, [(("read",),), (("write",),)])
        item.check_permission.side_effect = PermissionError
        self.frappe.db.exists.reset_mock()
        with self.assertRaises(PermissionError):
            self.generate(target="barcode", item_code="ITEM-A")
        self.frappe.db.exists.assert_not_called()

    def test_outlet_access_checked_before_generation(self):
        self.ns["_profile"].side_effect = PermissionError
        with self.assertRaises(PermissionError):
            self.generate()
        self.frappe.db.exists.assert_not_called()


if __name__ == "__main__":
    unittest.main()
