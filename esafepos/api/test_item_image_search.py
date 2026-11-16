import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from esafepos.api import item_image_search, items


class ItemImageSearchTests(unittest.TestCase):
    def test_config_only_returns_flags(self):
        doc = Mock()
        doc.get.return_value = 1
        doc.get_password.return_value = "test-secret"
        with patch.object(item_image_search, "_settings", return_value=doc):
            result = item_image_search.get_config()
        doc.check_permission.assert_called_once_with("write")
        self.assertEqual(result, {"enabled": True, "configured": True})

    def test_refinement_sends_catalog_identifiers_and_no_search_tool(self):
        item = Mock(brand="Acme", item_name="Precision drill 18V", barcodes=[SimpleNamespace(barcode="0123456789")],
                    disabled=0, is_sales_item=1, has_variants=0)
        doc = Mock()
        doc.get.return_value = 1
        doc.get_password.return_value = "test-secret"
        response = Mock()
        response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "Acme drill 18V 0123456789"}]}}]}
        with patch.object(items, "_profile") as profile, patch.object(item_image_search, "_settings", return_value=doc), \
                patch.object(item_image_search.frappe, "get_doc", return_value=item), \
                patch.object(item_image_search.frappe, "cache"), \
                patch.object(item_image_search.frappe, "session", SimpleNamespace(user="editor")), \
                patch.object(item_image_search.requests, "post", return_value=response) as post:
            result = item_image_search.refine_search("Test Till", "DRILL")
        profile.assert_called_once_with("Test Till")
        item.check_permission.assert_any_call("write")
        self.assertEqual(result, {"query": "Acme drill 18V 0123456789"})
        request = post.call_args[1]
        self.assertNotIn("tools", request["json"])
        self.assertIn("Acme Precision drill 18V 0123456789", str(request["json"]))
        self.assertFalse(request["allow_redirects"])
