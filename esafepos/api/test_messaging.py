"""Messaging boundaries with mocked documents/provider; no real SMS is sent."""
import hashlib
import json
from pathlib import Path
import runpy
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch


class Doc(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__

    def check_permission(self, mode):
        if self.get("deny") == mode:
            raise PermissionError(mode)

    def set(self, key, value):
        self[key] = value

    def append(self, key, value):
        self.setdefault(key, []).append(Doc(value))

    def save(self):
        self.saved = True


class MessagingTests(unittest.TestCase):
    def setUp(self):
        self.frappe = ModuleType("frappe")
        f = self.frappe
        f._ = lambda value: value
        f.whitelist = lambda: lambda function: function
        f.PermissionError = PermissionError
        f.DuplicateEntryError = RuntimeError
        f.throw = lambda message, kind=ValueError: (_ for _ in ()).throw(kind(message))
        f.has_permission = Mock(return_value=True)
        f.session = Doc(user="cashier@example.test")
        f.get_roles = Mock(return_value=["EsafePOS Cashier"])
        f.clear_document_cache = Mock()
        f.clear_messages = Mock()
        f.db = Mock()
        f.db.table_exists.return_value = True
        f.db.exists.return_value = True
        f.db.get_single_value.return_value = "https://sms.example.test/send"
        self.events, self.logs = [], {}
        f.db.commit.side_effect = lambda: self.events.append("commit")
        f.db.get_value.side_effect = lambda dt, filters, field, **kw: next((name for name, row in self.logs.items() if row.request_key == filters["request_key"]), None)
        f.db.set_value.side_effect = lambda dt, name, values: self.logs[name].update(values)
        self.settings = Doc(customer_messaging_config="")
        self.customer = Doc(name="CUST", customer_name="A Rahman", mobile_no="0771234567")
        self.profile = Doc(name="Till", company="Shop")
        self.sms_settings = Doc(sms_gateway_url="https://sms.example.test/send", message_parameter="message", receiver_parameter="to", use_post=1,
                                parameters=[Doc(name="PARAM", parameter="token", value="PRIVATE", header=1)], allowed_roles=[Doc(role="EsafePOS Cashier")])
        self.sale = Doc(name="INV", doctype="POS Invoice", docstatus=1, pos_profile="Till", company="Shop", customer="CUST", currency="LKR", grand_total=500, posting_date="2026-11-26")

        def get_doc(doctype, name=None):
            if isinstance(doctype, dict):
                row = Doc(doctype, owner=f.session.user, name="MSG-" + str(len(self.logs) + 1))
                def insert(**kwargs):
                    self.logs[row.name] = row
                    self.events.append("insert")
                    return row
                row.insert = insert
                return row
            return {"EsafePOS Settings": self.settings, "SMS Settings": self.sms_settings, "Customer": self.customer,
                    "POS Invoice": self.sale, "POS Customer Message": self.logs.get(name)}[doctype]
        f.get_doc = Mock(side_effect=get_doc)
        f.get_cached_doc = Mock(side_effect=lambda dt, *args: self.settings if dt == "EsafePOS Settings" else self.profile)
        f.get_cached_value = Mock(return_value="LKR")
        f.get_meta = Mock(return_value=Mock(has_field=Mock(return_value=True)))
        f.get_all = Mock(return_value=["EsafePOS Cashier"])
        f.get_list = Mock(return_value=[])
        utils = ModuleType("frappe.utils")
        utils.cint = lambda value=0: int(value or 0)
        utils.flt = lambda value=0: float(value or 0)
        permissions = ModuleType("esafepos.api.permissions")
        permissions.assert_outlet = Mock()
        permissions.allowed_companies = Mock(return_value={"Shop"})
        permissions.is_manager = Mock(return_value=False)
        self.permissions = permissions
        digital = ModuleType("esafepos.digital_receipts")
        digital.invoice_doctype = lambda name: "POS Invoice"
        digital.share_details = lambda doc: dict(url="https://shop.example.test/einvoice?t=P&i=INV", mobile="0771234567")
        whatsapp = ModuleType("esafepos.whatsapp")
        whatsapp.configured = Mock(return_value=False)
        whatsapp.prepare = Mock(return_value={"type":"Text"})
        whatsapp.send = Mock(return_value={"status":"Submitted to WhatsApp","provider_id":"wamid.TEST"})
        self.whatsapp = whatsapp
        modules = patch.dict(sys.modules, {"frappe": f, "frappe.utils": utils, "esafepos.api.permissions": permissions, "esafepos.digital_receipts": digital, "esafepos.whatsapp": whatsapp})
        modules.start()
        self.addCleanup(modules.stop)
        import esafepos
        parent = patch.object(esafepos, "whatsapp", whatsapp, create=True)
        parent.start()
        self.addCleanup(parent.stop)
        self.api = runpy.run_path(str(Path(__file__).with_name("messaging.py")))
        self.provider = Mock()
        self.provider.send_sms.side_effect = lambda **kw: self.events.append("provider")
        self.api["_sms_module"].__globals__["_sms_module"] = lambda: self.provider

    def send(self, **changes):
        args = dict(channel="SMS", mobile="0771234567", message="Hello, your invoice is ready.", request_key="request_1234567890123456", pos_profile="Till", customer="CUST")
        args.update(changes)
        return self.api["send_message"](**args)

    def test_phone_normalizes_local_international_and_rejects_invalid(self):
        normalize = self.api["normalize_mobile"]
        for text in ("077 123-4567", "+94 (77) 1234567", "0094771234567", "94771234567"):
            self.assertEqual(normalize(text, "94"), "+94771234567")
        for text in ("", "hello", "+94&to=other", "12", "+" * 8):
            with self.assertRaises(ValueError): normalize(text, "94")

    def test_sms_recipient_format_matches_provider_configuration(self):
        for index, (number_format, expected) in enumerate((("As entered", "0771234567"), ("International digits", "94771234567"), ("International +", "+94771234567"))):
            self.settings.customer_messaging_config = json.dumps({"sms_number_format": number_format})
            result = self.send(mobile="077 123-4567", request_key="format_request_123456_" + str(index))
            self.assertEqual(self.provider.send_sms.call_args.kwargs["receiver_list"], [expected])
            self.assertEqual(result["mobile"], "+94771234567")

    def test_duplicate_sms_has_one_provider_call_and_durable_pending_record(self):
        first, second = self.send(), self.send()
        self.assertEqual(first["status"], "Submitted to gateway")
        self.assertTrue(second["duplicate"])
        self.provider.send_sms.assert_called_once()
        self.assertLess(self.events.index("commit"), self.events.index("provider"))
        self.assertEqual(self.provider.send_sms.call_args.kwargs["msg"], "Hello, your invoice is ready.")

    def test_reusing_key_for_different_body_is_rejected(self):
        self.send()
        with self.assertRaisesRegex(ValueError, "different message"):
            self.send(message="Changed body")
        self.provider.send_sms.assert_called_once()

    def test_gateway_timeout_is_unknown_and_retry_does_not_resend(self):
        self.provider.send_sms.side_effect = TimeoutError("PRIVATE credential URL")
        result = self.send()
        self.assertEqual(result["status"], "Outcome unknown")
        self.assertNotIn("PRIVATE", result["error"])
        self.assertTrue(self.send()["duplicate"])
        self.provider.send_sms.assert_called_once()
        self.frappe.clear_messages.assert_called_once()

    def test_whatsapp_is_only_a_draft_and_never_calls_sms_gateway(self):
        result = self.send(channel="WhatsApp")
        self.assertEqual(result["status"], "Opened in WhatsApp")
        self.provider.send_sms.assert_not_called()

    def test_customer_and_outlet_permissions_run_before_logging(self):
        self.customer.deny = "read"
        with self.assertRaises(PermissionError): self.send()
        self.assertFalse(self.logs)
        self.customer.deny = None
        self.permissions.assert_outlet.side_effect = PermissionError("outlet")
        with self.assertRaises(PermissionError): self.send()
        self.assertFalse(self.logs)

    def test_native_sms_role_denial_prevents_outbound_send(self):
        self.provider.check_sms_permission.side_effect = PermissionError("sender role")
        with self.assertRaises(PermissionError): self.send()
        self.assertFalse(self.logs)
        self.provider.send_sms.assert_not_called()

    def test_disabled_module_missing_gateway_and_long_sms_are_rejected(self):
        for override in (dict(enabled=0), dict(sms_enabled=0)):
            self.settings.customer_messaging_config = json.dumps(override)
            with self.assertRaises(PermissionError): self.send()
        self.settings.customer_messaging_config = ""
        self.frappe.db.get_single_value.return_value = ""
        with self.assertRaises(ValueError): self.send()
        self.frappe.db.get_single_value.return_value = "https://sms.example.test"
        with self.assertRaises(ValueError): self.send(message="x" * 1601)
        self.assertFalse(self.logs)

    def test_invoice_customer_company_and_submission_are_enforced(self):
        self.sale.docstatus = 2
        with self.assertRaises(ValueError): self.send(invoice="INV")
        self.sale.docstatus = 1
        self.sale.esafepos_receipt_customer = "SOMEONE-ELSE"
        with self.assertRaises(PermissionError): self.send(invoice="INV")
        self.sale.esafepos_receipt_customer = None
        self.sale.company = "Forbidden"
        with self.assertRaises(PermissionError): self.send(invoice="INV")
        self.assertFalse(self.logs)

    def test_history_is_outlet_scoped_and_cashier_owner_scoped(self):
        self.api["recent_messages"]("Till", "CUST")
        self.assertEqual(self.frappe.get_list.call_args.kwargs["filters"], {"pos_profile":"Till", "customer":"CUST", "owner":"cashier@example.test"})
        self.permissions.is_manager.return_value = True
        self.api["recent_messages"]("Till")
        self.assertNotIn("owner", self.frappe.get_list.call_args.kwargs["filters"])

    def test_gateway_read_masks_values_and_blank_save_preserves_them(self):
        response = self.api["get_messaging_settings"]()
        self.assertEqual(response["gateway"]["parameters"][0]["value"], "")
        self.assertTrue(response["gateway"]["parameters"][0]["has_value"])
        self.api["save_sms_gateway"](response["gateway"])
        self.assertEqual(self.sms_settings.parameters[0].value, "PRIVATE")
        self.assertTrue(self.sms_settings.saved)
        self.provider.send_sms.assert_not_called()

    def test_native_gateway_write_permission_cannot_be_bypassed(self):
        self.sms_settings.deny = "write"
        with self.assertRaises(PermissionError): self.api["save_sms_gateway"]({})
        self.assertFalse(self.sms_settings.saved)

    def test_templates_allow_only_documented_values_and_preserve_typed_text(self):
        config = dict(self.api["DEFAULTS"])
        config["invoice_template"] = "Hello {customer}: {invoice}\n{link}"
        self.api["save_messaging_settings"](config)
        self.assertTrue(self.settings.saved)
        self.assertEqual(self.api["compose"](invoice="INV")["message"], "Hello A Rahman: INV\nhttps://shop.example.test/einvoice?t=P&i=INV")
        config["invoice_template"] = "{customer.password}"
        with self.assertRaises(ValueError): self.api["save_messaging_settings"](config)

    def test_missing_migration_cannot_send_without_durable_log(self):
        self.frappe.db.table_exists.return_value = False
        with self.assertRaisesRegex(ValueError, "migration"):
            self.send()
        self.provider.send_sms.assert_not_called()

    def test_whatsapp_api_send_is_idempotent_and_records_provider_acceptance(self):
        self.whatsapp.configured.return_value = True
        result = self.send(channel="WhatsApp API", session_confirmed=1)
        self.assertEqual(result["status"], "Submitted to WhatsApp")
        self.assertTrue(self.send(channel="WhatsApp API", session_confirmed=1)["duplicate"])
        self.whatsapp.send.assert_called_once()
        self.assertEqual(next(iter(self.logs.values())).provider_id, "wamid.TEST")

    def test_whatsapp_api_sender_role_is_enforced(self):
        self.frappe.get_roles.return_value = ["Guest"]
        with self.assertRaises(PermissionError): self.send(channel="WhatsApp API", session_confirmed=1)
        self.whatsapp.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
