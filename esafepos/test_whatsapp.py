"""Meta transport fixtures; never contacts Meta or sends a real message."""
import base64
from pathlib import Path
import runpy
import struct
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch
from esafepos.api.test_messaging import Doc


class WhatsAppTests(unittest.TestCase):
    def setUp(self):
        f = ModuleType("frappe")
        f._ = lambda value: value
        f.throw = lambda message: (_ for _ in ()).throw(ValueError(message))
        self.doc = Doc(whatsapp_phone_number_id="123456789", whatsapp_api_version="v27.0")
        self.doc.get_password = Mock(return_value="SECRET-TOKEN")
        f.get_cached_doc = Mock(return_value=self.doc)
        utils = ModuleType("frappe.utils")
        utils.cint = lambda value=0: int(value or 0)
        modules = patch.dict(sys.modules, {"frappe":f,"frappe.utils":utils})
        modules.start()
        self.addCleanup(modules.stop)
        self.api = runpy.run_path(str(Path(__file__).with_name("whatsapp.py")))
        self.post = Mock(return_value=Mock(status_code=200, json=lambda: {"messages":[{"id":"wamid.SENT"}]}))
        self.api["send"].__globals__["_post"] = self.post
        self.context = {"values":{"customer":"A Rahman","invoice":"INV","total":"500.00","link":"https://shop.example.test/einvoice?signature=TEST"}}
        self.settings = {"whatsapp_template_name":"pos_receipt","whatsapp_template_language":"en","whatsapp_template_parameters":"customer,invoice,total,link"}

    def prepare(self, kind="Text", **kw):
        return self.api["prepare"](self.context, self.settings, "Hello, your invoice is ready.", delivery_type=kind, **kw)

    def test_text_uses_exact_typed_body_and_server_only_bearer_token(self):
        result = self.api["send"]("+94771234567", self.prepare(session_confirmed=1))
        self.assertEqual(result["status"], "Submitted to WhatsApp")
        args, kw = self.post.call_args
        self.assertEqual(args[0], "https://graph.facebook.com/v27.0/123456789/messages")
        self.assertEqual(kw["headers"]["Authorization"], "Bearer SECRET-TOKEN")
        self.assertEqual(kw["json"]["to"], "94771234567")
        self.assertEqual(kw["json"]["text"]["body"], "Hello, your invoice is ready.")

    def test_text_and_images_require_confirmation_of_the_service_window(self):
        for kind in ("Text", "Image"):
            with self.assertRaisesRegex(ValueError, "24 hours"): self.prepare(kind)
        self.post.assert_not_called()

    def test_template_parameters_use_approved_order_without_session_confirmation(self):
        prepared = self.prepare("Template")
        result = self.api["send"]("+94771234567", prepared)
        self.assertEqual(result["status"], "Submitted to WhatsApp")
        values = self.post.call_args.kwargs["json"]["template"]["components"][0]["parameters"]
        self.assertEqual([row["text"] for row in values], list(self.context["values"].values()))
        self.assertIn("Template: pos_receipt", prepared["display_message"])

    def test_image_upload_then_message_references_returned_media_id(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 10, 20) + b"\x00" * 16
        prepared = self.prepare("Image", session_confirmed=1, image_data="data:image/png;base64," + base64.b64encode(png).decode())
        self.post.side_effect = [Mock(status_code=200,json=lambda:{"id":"MEDIA"}), Mock(status_code=200,json=lambda:{"messages":[{"id":"wamid.IMAGE"}]})]
        self.assertEqual(self.api["send"]("+94771234567", prepared)["provider_id"], "wamid.IMAGE")
        self.assertTrue(self.post.call_args_list[0].args[0].endswith('/media'))
        self.assertEqual(self.post.call_args_list[1].kwargs["json"]["image"]["id"], "MEDIA")

    def test_rejection_timeout_and_missing_ack_are_never_reported_as_delivered(self):
        prepared = self.prepare(session_confirmed=1)
        self.post.return_value = Mock(status_code=400,json=lambda:{"error":{"code":131047}})
        self.assertEqual(self.api["send"]("+94771234567", prepared)["status"], "Rejected")
        self.assertIn("approved", self.api["send"]("+94771234567", prepared)["error"])
        self.post.side_effect = TimeoutError("SECRET-TOKEN")
        result = self.api["send"]("+94771234567", prepared)
        self.assertEqual(result["status"], "Outcome unknown")
        self.assertNotIn("SECRET", result["error"])
        self.post.side_effect = None
        self.post.return_value = Mock(status_code=200,json=lambda:{})
        self.assertEqual(self.api["send"]("+94771234567", prepared)["status"], "Outcome unknown")

    def test_approved_image_header_template_works_without_service_window(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 10, 20) + b"\x00" * 16
        self.settings["whatsapp_template_image"] = 1
        prepared = self.prepare("Template", image_data="data:image/png;base64," + base64.b64encode(png).decode())
        self.post.side_effect = [Mock(status_code=200,json=lambda:{"id":"MEDIA"}), Mock(status_code=200,json=lambda:{"messages":[{"id":"wamid.TEMPLATE"}]})]
        self.api["send"]("+94771234567", prepared)
        components = self.post.call_args.kwargs["json"]["template"]["components"]
        self.assertEqual(components[0], {"type":"header","parameters":[{"type":"image","image":{"id":"MEDIA"}}]})
        self.assertEqual(components[1]["type"], "body")

    def test_bad_credentials_paths_and_oversized_or_invalid_images_stop_before_transport(self):
        self.doc.whatsapp_phone_number_id = "../other"
        with self.assertRaises(ValueError): self.prepare(session_confirmed=1)
        self.doc.whatsapp_phone_number_id = "123456789"
        for data in ("data:text/html;base64,aGVsbG8=", "data:image/png;base64,NOT-PNG", "data:image/png;base64," + "A" * 5600001):
            with self.assertRaises(ValueError): self.prepare("Image", session_confirmed=1, image_data=data)
        self.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
