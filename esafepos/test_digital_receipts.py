"""Render the actual public template and validate signed receipt boundaries."""
from pathlib import Path
import runpy
import sys
import time
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

from esafepos.api.test_messaging import Doc


class DigitalReceiptTests(unittest.TestCase):
    def setUp(self):
        f = ModuleType("frappe")
        f._ = lambda value: value
        f.conf = Doc(encryption_key="test-key-never-used-on-a-site")
        f.throw = lambda message: (_ for _ in ()).throw(ValueError(message))
        f.db = Mock()
        f.db.exists.return_value = True
        f.db.get_default.return_value = "LKR"
        f.get_cached_value = Mock(return_value="")
        self.doc = Doc(name="INV-00303", doctype="POS Invoice", docstatus=1, company="Shop", pos_profile="Till", customer="CUST", customer_name="Customer",
                       posting_date="2026-11-26", posting_time="14:32:45", currency="LKR", net_total=500, grand_total=500,
                       items=[Doc(item_name="Dog food", item_code="FEED", price_list_rate=1000, rate=1000, qty=0.5, amount=500)], payments=[], taxes=[])
        f.get_doc = Mock(return_value=self.doc)
        utils = ModuleType("frappe.utils")
        utils.cint = lambda value=0: int(value or 0)
        utils.flt = lambda value=0: float(value or 0)
        utils.fmt_money = lambda value, currency: "{} {:.2f}".format(currency, value)
        utils.get_url = lambda: "https://shop.example.test"
        receipt_options = ModuleType("esafepos.receipt_options")
        receipt_options.receipt_footer = lambda settings: "Thank you"
        barcode = ModuleType("esafepos.receipt_barcode")
        barcode.invoice_svg_data = lambda name: {"width":100,"path":"M0 0h1v40H0z"}
        walk = ModuleType("esafepos.walk_in")
        walk.receipt_customer_name = lambda doc: doc.customer_name
        settings = ModuleType("esafepos.api.settings")
        settings.effective_receipt = lambda profile: {"receipt_template":"Table", "receipt_show_payments":1}
        credit = ModuleType("esafepos.credit_sales")
        credit.receipt_facts = lambda doc: {}
        modules = patch.dict(sys.modules, {"frappe":f,"frappe.utils":utils,"esafepos.receipt_options":receipt_options,
                    "esafepos.receipt_barcode":barcode,"esafepos.walk_in":walk,"esafepos.api.settings":settings,"esafepos.credit_sales":credit})
        modules.start()
        self.addCleanup(modules.stop)
        self.frappe = f
        self.api = runpy.run_path(str(Path(__file__).with_name("digital_receipts.py")))
        self.expiry = int(time.time()) + 3600
        self.signature = self.api["_signature"]("P", self.doc.name, self.expiry)

    def public(self, **kw):
        args = dict(type_code="P", invoice=self.doc.name, expires=self.expiry, signature=self.signature)
        args.update(kw)
        return self.api["public_receipt"](**args)

    def test_real_public_page_renders_dictionary_items_and_escaped_customer(self):
        from jinja2 import Environment, StrictUndefined
        self.doc.customer_name = '<script>alert("x")</script>'
        receipt = self.public()
        template = Path(__file__).parent / "www/einvoice.html"
        html = Environment(autoescape=True, undefined=StrictUndefined).from_string(template.read_text(encoding="utf-8")).render(valid=True, receipt=receipt, title=self.doc.name)
        self.assertIn("Dog food", html)
        self.assertIn("LKR 500.00", html)
        self.assertNotIn('<script>alert("x")</script>', html)
        self.assertIn("&lt;script&gt;", html)

    def test_old_item_attribute_lookup_reproduces_the_reported_error(self):
        from jinja2 import Environment
        with self.assertRaises(TypeError):
            Environment().from_string("{% for item in receipt.items %}{{item}}{% endfor %}").render(receipt={"items":[]})

    def test_tampered_expired_cancelled_and_missing_receipts_are_not_public(self):
        invalid = self.api["InvalidReceiptLink"]
        for changes in (dict(signature="bad"), dict(invoice="DIFFERENT"), dict(expires=int(time.time())-1), dict(type_code="X")):
            with self.assertRaises(invalid): self.public(**changes)
        self.doc.docstatus = 2
        with self.assertRaises(invalid): self.public()
        self.doc.docstatus = 1
        self.frappe.db.exists.return_value = False
        with self.assertRaises(invalid): self.public()

    def test_linked_customer_phone_is_available_for_walk_in_receipts(self):
        self.doc.esafepos_walk_in_code = "W-123"
        self.doc.esafepos_receipt_customer = "LINKED"
        self.frappe.db.get_value.return_value = "0771234567"
        details = self.api["share_details"](self.doc)
        self.assertEqual(details["mobile"], "0771234567")
        self.assertIn("/einvoice?", details["url"])


if __name__ == "__main__":
    unittest.main()
