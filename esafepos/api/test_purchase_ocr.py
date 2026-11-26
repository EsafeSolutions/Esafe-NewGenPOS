"""Invoice scanning contracts, security boundaries and untrusted output checks."""
import base64
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class Refused(Exception):
    pass


class PurchaseOcrTests(unittest.TestCase):
    def setUp(self):
        from datetime import date
        self.frappe = ModuleType("frappe")
        self.frappe._ = lambda text: text
        self.frappe.whitelist = lambda **kwargs: lambda fn: fn
        self.frappe.throw = Mock(side_effect=lambda message, *args: self.refuse(message))
        self.frappe.session = SimpleNamespace(user="buyer@example.com")
        self.frappe.has_permission = Mock(return_value=True)
        self.frappe.get_meta = Mock(return_value=SimpleNamespace(has_field=lambda field: True))
        self.cache = Mock()
        self.cache.make_key.side_effect = lambda key: key
        self.cache.set.return_value = True
        self.frappe.cache = lambda: self.cache
        self.values = {"purchase_ocr_enabled": 1, "purchase_ocr_gemini_key": "test-key-never-returned", "purchase_ocr_model": "gemini-3.5-flash-lite"}
        self.settings = SimpleNamespace(name="EsafePOS Settings", meta=SimpleNamespace(has_field=lambda field: True),
            check_permission=Mock(), get=lambda key: self.values.get(key), set=lambda key, value: self.values.update({key: value}),
            get_password=Mock(side_effect=lambda field, **kwargs: self.values.get(field)), save=Mock())
        self.frappe.get_doc = Mock(return_value=self.settings)
        self.frappe.get_list = Mock(return_value=[])
        self.native = ModuleType("esafepos.api.buying")
        self.native._context = Mock(return_value=(SimpleNamespace(company="Shop"), "LKR"))
        self.native._require = Mock()
        utils = ModuleType("frappe.utils")
        utils.cint = lambda number: int(number or 0)
        utils.getdate = lambda value: date.fromisoformat(value)
        password = ModuleType("frappe.utils.password")
        password.remove_encrypted_password = Mock()
        self.password = password
        requests = ModuleType("requests")
        requests.RequestException = type("RequestException", (Exception,), {})
        requests.Timeout = type("Timeout", (requests.RequestException,), {})
        requests.post = Mock()
        self.patcher = patch.dict(sys.modules, {"frappe": self.frappe, "frappe.utils": utils,
            "frappe.utils.password": password, "esafepos.api.buying": self.native, "requests": requests})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        spec = importlib.util.spec_from_file_location("ocr_under_test", Path(__file__).with_name("purchase_ocr.py"))
        self.api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.api)
        self.response = Mock(status_code=200)
        self.response.json.side_effect = lambda: {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(self.result)}]}}]}
        self.post_patch = patch.object(self.api.requests, "post", return_value=self.response)
        self.post = self.post_patch.start()
        self.addCleanup(self.post_patch.stop)
        self.result = {"supplier_name": "Green Supplies", "invoice_number": "B-100", "invoice_date": "2026-11-25",
            "due_date": "2026-12-25", "currency": "LKR", "total": 1180, "tax_amount": 180, "discount_amount": 0,
            "items": [{"description": "Rice", "item_code": "RICE", "barcode": "000123", "quantity": 10, "unit_price": 100, "amount": 1000, "unit": "Kg"}],
            "additional_costs": [], "warnings": []}

    @staticmethod
    def refuse(message):
        raise Refused(message)

    def scan(self, **overrides):
        args = dict(pos_profile="Till", file_data=base64.b64encode(b"%PDF-1.7\ninvoice fixture").decode(),
                    mime_type="application/pdf", file_name="invoice.pdf")
        args.update(overrides)
        return self.api.scan_invoice(**args)

    def test_scan_returns_review_data_without_creating_any_documents(self):
        result = self.scan()
        self.assertEqual(result["total"], 1180)
        self.assertEqual(result["items"][0]["barcode"], "000123")
        self.assertEqual(result["tax_amount"], 180)
        self.settings.save.assert_not_called()
        self.frappe.get_doc.assert_called_once_with("EsafePOS Settings")
        self.native._require.assert_any_call("Purchase Invoice", "create")

    def test_key_is_only_in_upstream_header_not_browser_result_or_url(self):
        result = self.scan()
        args, kwargs = self.post.call_args
        self.assertNotIn(self.values["purchase_ocr_gemini_key"], args[0])
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], self.values["purchase_ocr_gemini_key"])
        self.assertNotIn(self.values["purchase_ocr_gemini_key"], json.dumps(result))
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["timeout"], (5, 60))
        self.assertEqual(kwargs["json"]["generationConfig"]["responseMimeType"], "application/json")
        self.assertNotIn("tools", kwargs["json"])

    def test_scan_permissions_checked_before_document_decode_or_external_call(self):
        for check in (self.native._context, self.native._require):
            check.side_effect = PermissionError
            with self.assertRaises(PermissionError):
                self.scan()
            check.side_effect = None
        self.post.assert_not_called()

    def test_disabled_missing_key_and_invalid_model_never_call_google(self):
        for field, value in (("purchase_ocr_enabled", 0), ("purchase_ocr_gemini_key", ""), ("purchase_ocr_model", "https://malicious.example/key")):
            old = self.values[field]
            self.values[field] = value
            with self.subTest(field=field), self.assertRaises(Refused):
                self.scan()
            self.values[field] = old
        self.post.assert_not_called()

    def test_decode_rejects_spoofed_types_invalid_base64_and_oversize(self):
        for changes in ({"mime_type": "text/html"}, {"file_data": "!invalid"}, {"file_data": ""},
                        {"mime_type": "image/png"}, {"file_data": "A" * (12 * 1024 * 1024)}):
            with self.subTest(changes=list(changes)), self.assertRaises(Refused):
                self.scan(**changes)
        self.post.assert_not_called()

    def test_rate_limit_includes_failed_attempts(self):
        self.cache.set.return_value = False
        with self.assertRaisesRegex(Refused, "15 seconds"):
            self.scan()
        self.post.assert_not_called()
        self.assertIn("buyer@example.com", self.cache.set.call_args.args[0])

    def test_api_errors_are_actionable_without_leaking_response_or_key(self):
        for code, text in ((401, "API key"), (403, "API key"), (429, "quota"), (404, "model")):
            self.response.status_code = code
            with self.subTest(code=code), self.assertRaisesRegex(Refused, text) as caught:
                self.scan()
            self.assertNotIn(self.values["purchase_ocr_gemini_key"], str(caught.exception))

    def test_timeout_and_incomplete_output_are_not_imported(self):
        self.post.side_effect = self.api.requests.Timeout("upstream secret")
        with self.assertRaises(Refused) as caught:
            self.scan()
        self.assertNotIn("upstream secret", str(caught.exception))
        self.post.side_effect = None
        self.response.json.return_value = {}
        self.response.json.side_effect = lambda: {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{}"}]}}]}
        with self.assertRaises(Refused):
            self.scan()

    def test_unknowns_negative_nonfinite_and_bad_dates_remain_unfilled(self):
        self.result.update(invoice_date="tomorrow", due_date="2026-99-99", currency="rupees", total=float("nan"))
        self.result["items"][0].update(quantity=-1, unit_price=float("inf"))
        result = self.scan()
        self.assertEqual(result["invoice_date"], "")
        self.assertEqual(result["currency"], "")
        self.assertIsNone(result["total"])
        self.assertIsNone(result["items"][0]["quantity"])
        self.assertIsNone(result["items"][0]["unit_price"])

    def test_empty_oversized_or_malformed_rows_rejected(self):
        for rows in ([], [None], [{}] * 101):
            self.result["items"] = rows
            with self.assertRaises(Refused):
                self.scan()

    def test_exact_product_match_keeps_stock_unit_and_fractional_quantity(self):
        item = SimpleNamespace(name="RICE", item_name="Rice", stock_uom="Kg", is_stock_item=1)
        self.frappe.get_list.side_effect = lambda dt, **kwargs: [item] if dt == "Item" else []
        self.result["items"][0]["quantity"] = .5
        result = self.scan()["items"][0]
        self.assertEqual(result["matched_item"], "RICE")
        self.assertEqual(result["quantity"], .5)
        self.assertEqual(result["candidates"][0].stock_uom, "Kg")

    def test_fuzzy_single_candidate_is_not_auto_matched_by_an_unfound_barcode(self):
        row = {"item_code": "", "barcode": "bad-code", "description": "rice"}
        suggested = SimpleNamespace(name="OTHER", item_name="Rice flour", stock_uom="Kg", is_stock_item=1)
        self.frappe.get_list.side_effect = [[], [suggested]]
        candidates, match = self.api._item_candidates(row)
        self.assertEqual(candidates, [suggested])
        self.assertEqual(match, "")

    def test_supplier_and_duplicate_checks_use_permission_filtered_lists(self):
        supplier = SimpleNamespace(name="SUP", supplier_name="Green Supplies", supplier_group="Local")
        duplicate = SimpleNamespace(name="PINV-1", docstatus=1)
        self.frappe.get_list.side_effect = lambda dt, **kwargs: [supplier] if dt == "Supplier" else [duplicate] if dt == "Purchase Invoice" else []
        result = self.scan()
        self.assertEqual(result["matched_supplier"], "SUP")
        self.assertEqual(result["duplicate_invoices"], [duplicate])
        for call in self.frappe.get_list.call_args_list:
            self.assertNotIn("ignore_permissions", call.kwargs)

    def test_unique_tax_id_matches_a_supplier_with_a_different_printed_name(self):
        self.result["supplier_tax_id"] = "TAX-001"
        supplier = SimpleNamespace(name="SUP", supplier_name="Greenfield Holdings", supplier_group="Local")
        self.frappe.get_list.side_effect = lambda dt, **kwargs: [supplier] if dt == "Supplier" and kwargs["filters"].get("tax_id") == "TAX-001" else []
        self.assertEqual(self.scan()["matched_supplier"], "SUP")

    def test_config_requires_settings_write_and_never_returns_key(self):
        result = self.api.get_config()
        self.settings.check_permission.assert_called_with("write")
        self.assertTrue(result["configured"])
        self.assertNotIn("api_key", result)
        self.assertNotIn("test-key", json.dumps(result))
        self.settings.check_permission.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            self.api.save_config(1, "another-secret-key")
        self.settings.save.assert_not_called()

    def test_save_preserves_blank_key_and_validates_model(self):
        self.api.save_config(1, "", "gemini-3.5-flash-lite")
        self.assertEqual(self.values["purchase_ocr_gemini_key"], "test-key-never-returned")
        for model in ("../key", "gemini-x:generateContent?key=oops", "https://example.com"):
            with self.assertRaises(Refused):
                self.api.save_config(1, "", model)

    def test_clear_key_removes_only_the_invoice_scanning_password(self):
        self.api.save_config(0, "", clear_key=1)
        self.password.remove_encrypted_password.assert_called_once_with("EsafePOS Settings", "EsafePOS Settings", "purchase_ocr_gemini_key")
        with self.assertRaises(Refused):
            self.api.save_config(1, "", clear_key=1)


if __name__ == "__main__":
    unittest.main()
