"""Standalone Printing API boundary checks; Frappe I/O is mocked."""
import ast
import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
fake = types.ModuleType("frappe")
fake._ = lambda value: value
fake.whitelist = lambda *args, **kwargs: lambda fn: fn
fake.PermissionError = PermissionError
fake.throw = lambda message, kind=ValueError: (_ for _ in ()).throw(kind(message))
sys.modules["frappe"] = fake
permissions = types.ModuleType("esafepos.api.permissions")
permissions.assert_outlet = Mock()
permissions.can_use_outlet = Mock(return_value=True)
sys.modules[permissions.__name__] = permissions
settings = types.ModuleType("esafepos.api.settings")
# Use the real receipt normalizer and partial-update helper without importing
# unrelated ERPNext accounting integrations into this standalone test process.
tree = ast.parse((ROOT / "esafepos/api/settings.py").read_text(encoding="utf-8"))
names = {"RECEIPT_FIELDS", "_RECEIPT_BOOL", "_RECEIPT_BOOL_DEFAULTS", "receipt_config", "_apply_receipt_payload"}
nodes = [node for node in tree.body if getattr(node, "name", None) in names
         or isinstance(node, ast.Assign) and any(getattr(t, "id", None) in names for t in node.targets)]
exec(compile(ast.Module(body=nodes, type_ignores=[]), "receipt_helpers", "exec"), settings.__dict__)
settings._clean_custom_fields = lambda value: value or []
settings._global_custom_fields = lambda: []
sys.modules[settings.__name__] = settings
audit = types.ModuleType("esafepos.api.audit")
audit.SETTINGS_CHANGE = "Settings change"
audit.log = Mock()
sys.modules[audit.__name__] = audit
printing = types.ModuleType("esafepos.api.printing")
printing._send = Mock()
sys.modules[printing.__name__] = printing
api = importlib.import_module("esafepos.api.printing_settings")


class Doc(dict):
    def __init__(self, **values):
        super().__init__(values)
        self.name = values.get("name", "Till A")
        self.meta = types.SimpleNamespace(has_field=lambda field: True)
        self.check_permission = Mock()
        self.has_permission = Mock(return_value=True)
        self.save = Mock()

    def set(self, key, value):
        self[key] = value


class PrintingSettingsTests(unittest.TestCase):
    def setUp(self):
        fake.has_permission = Mock(return_value=True)
        self.doc = Doc(esafepos_invoice_mode="POS Invoice", esafepos_printer_ip="192.168.1.50", esafepos_printer_port=9100, warehouse="Keep warehouse")
        fake.get_doc = Mock(return_value=self.doc)
        fake.get_cached_doc = Mock(return_value=self.doc)
        fake.get_list = Mock(return_value=[])
        permissions.assert_outlet.reset_mock(side_effect=True)
        printing._send.reset_mock()
        audit.log.reset_mock()

    def test_cashier_cannot_read_or_change_setup(self):
        fake.has_permission.return_value = False
        for operation in (lambda: api.receipt_workspace(), lambda: api.get_printer_settings("Till A"),
                          lambda: api.save_receipt_defaults({}), lambda: api.save_printer_settings("Till A"), lambda: api.test_printer("Till A")):
            with self.assertRaises(PermissionError):
                operation()
        fake.get_doc.assert_not_called()
        printing._send.assert_not_called()

    def test_outlet_scope_is_checked(self):
        permissions.assert_outlet.side_effect = PermissionError("Other outlet")
        with self.assertRaises(PermissionError):
            api.get_printer_settings("Other")
        fake.get_doc.assert_not_called()

    def test_printer_save_requires_profile_write(self):
        self.doc.check_permission.side_effect = PermissionError("No profile write")
        with self.assertRaises(PermissionError):
            api.save_printer_settings("Till A", host="192.168.1.51")
        self.doc.check_permission.assert_called_with("write")
        self.doc.save.assert_not_called()

    def test_rejects_invalid_hosts_and_ports(self):
        for host in ("https://printer/path", "a..b", "bad;command", "a" * 64):
            with self.subTest(host=host), self.assertRaises(ValueError):
                api._destination(host, 9100)
        for port in (0, 65536, 1.5, True, "", "9100junk"):
            with self.subTest(port=port), self.assertRaises(ValueError):
                api._destination("printer.local", port)
        self.assertEqual(api._destination(" 192.168.1.10 ", "9100"), ("192.168.1.10", 9100))
        self.assertEqual(api._destination("::1", 9100), ("::1", 9100))

    def test_clear_printer_preserves_other_profile_fields(self):
        api.save_printer_settings("Till A", host="", port=9100)
        self.assertIsNone(self.doc["esafepos_printer_ip"])
        self.assertEqual(self.doc["warehouse"], "Keep warehouse")
        self.doc.save.assert_called_once()

    def test_rejects_wrong_or_disabled_print_format(self):
        for doctype, disabled in (("Sales Invoice", 0), ("POS Invoice", 1)):
            fmt = Doc(doc_type=doctype, disabled=disabled)
            fake.get_doc.side_effect = [self.doc, fmt]
            with self.subTest(doctype=doctype, disabled=disabled), self.assertRaises(ValueError):
                api.save_printer_settings("Till A", print_format="Wrong format")
        self.doc.save.assert_not_called()

    def test_default_receipt_save_does_not_change_other_settings(self):
        self.doc.update(receipt_footer="Old", receipt_show_cashier=1, shift_scope="Per outlet")
        api.save_receipt_defaults({"receipt_footer": "New", "shift_scope": "Wrong"})
        self.assertEqual(self.doc["receipt_footer"], "New")
        self.assertEqual(self.doc["receipt_show_cashier"], 1)
        self.assertEqual(self.doc["shift_scope"], "Per outlet")

    def test_general_settings_payload_preserves_receipt_when_absent(self):
        self.doc.update(receipt_footer="Keep footer", receipt_show_cashier=0, receipt_show_terminal=0, receipt_show_invoice_barcode=0)
        settings._apply_receipt_payload(self.doc, {"enable_labels": 1})
        self.assertEqual(self.doc["receipt_footer"], "Keep footer")
        self.assertEqual(self.doc["receipt_show_cashier"], 0)
        self.assertEqual(self.doc["receipt_show_terminal"], 0)
        self.assertEqual(self.doc["receipt_show_invoice_barcode"], 0)

    def test_diagnostic_does_not_open_drawer_or_post_a_document(self):
        self.assertEqual(api.test_printer("Till A"), {"submitted": True})
        host, port, data = printing._send.call_args.args
        self.assertEqual((host, port), ("192.168.1.50", 9100))
        self.assertLess(len(data), 200)
        self.assertNotIn(b"\x1bp", data)
        self.doc.save.assert_not_called()

    def test_diagnostic_requires_saved_destination(self):
        self.doc["esafepos_printer_ip"] = ""
        with self.assertRaises(ValueError):
            api.test_printer("Till A")
        printing._send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
