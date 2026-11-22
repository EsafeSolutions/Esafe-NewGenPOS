"""Metadata and rendering authorization tests, with no live Frappe or printer."""
import base64
import ast
import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
fake = types.ModuleType("frappe")
fake._ = lambda value: value
fake.whitelist = lambda *a, **kw: lambda fn: fn
fake.PermissionError = PermissionError
fake.throw = lambda message, kind=ValueError: (_ for _ in ()).throw(kind(message))
fake.session = types.SimpleNamespace(user="cashier")
utils = types.ModuleType("frappe.utils")
utils.cint = lambda value: int(value or 0)
sys.modules["frappe"] = fake
sys.modules["frappe.utils"] = utils
permissions = types.ModuleType("esafepos.api.permissions")
permissions.assert_outlet = Mock()
permissions.can_reprint = Mock(return_value=True)
sys.modules[permissions.__name__] = permissions
sales = types.ModuleType("esafepos.api.sales")
sales.get_receipt = Mock(return_value={"name": "INV-1"})
sales._doctype_of = lambda value: "POS Invoice"
sys.modules[sales.__name__] = sales
printing = types.ModuleType("esafepos.api.printing")
printing.build_receipt_bytes = Mock(return_value=b"receipt bytes")
sys.modules[printing.__name__] = printing
audit = types.ModuleType("esafepos.api.audit")
audit.REPRINT = "Reprint"
audit.log = Mock()
sys.modules[audit.__name__] = audit
api = importlib.import_module("esafepos.api.esafe_printing")


class Doc(dict):
    def __getattr__(self, key):
        return self.get(key)

    def check_permission(self, action):
        if self.get("deny"):
            raise PermissionError("Denied")

    def insert(self, **kwargs):
        self["name"] = self["request_id"]
        self["owner"] = fake.session.user
        STORE[self.name] = self

    def db_set(self, values):
        self.update(values)


STORE = {}
ID = "11111111-1111-4111-8111-111111111111"
DEVICE = "22222222-2222-4222-8222-222222222222"


class EsafePrintingTests(unittest.TestCase):
    def setUp(self):
        STORE.clear()
        fake.session.user = "cashier"
        permissions.can_reprint.return_value = True
        permissions.assert_outlet.reset_mock(side_effect=True)
        self.invoice = Doc(doctype="POS Invoice", name="INV-1", company="Company", pos_profile="Till")
        fake.get_doc = lambda doctype, name=None: Doc(doctype) if isinstance(doctype, dict) else self.invoice if doctype == "POS Invoice" else STORE[name]
        fake.get_cached_value = lambda *args: "Company"
        fake.get_print = Mock(return_value=b"%PDF-1.4\nfixture")
        fake.db = types.SimpleNamespace(exists=lambda *args: True, get_value=self.value)
        audit.log.reset_mock()

    def value(self, doctype, filters, field):
        if doctype != api.DOCTYPE:
            return None
        return next((key for key, row in STORE.items() if all(row.get(f) == v for f, v in filters.items())), None)

    def register(self, **values):
        payload = dict(pos_profile="Till", request_id=ID, workstation=DEVICE, payload_hash=base64.b64encode(b"x" * 32).decode(),
                       reference={"doctype": "POS Invoice", "name": "INV-1"}, role="receipt", output="html")
        payload.update(values)
        return api.register_intent(**payload)

    def test_original_intent_is_idempotent(self):
        first = self.register()
        self.assertEqual(self.register(), first)
        self.assertEqual(len(STORE), 1)

    def test_another_browser_cannot_create_a_second_original(self):
        self.register()
        with self.assertRaises(PermissionError):
            self.register(request_id="33333333-3333-4333-8333-333333333333", workstation="44444444-4444-4444-8444-444444444444")

    def test_changed_payload_is_rejected_for_same_intent(self):
        self.register()
        with self.assertRaises(PermissionError):
            self.register(payload_hash=base64.b64encode(b"y" * 32).decode())

    def test_reprint_requires_existing_capability(self):
        permissions.can_reprint.return_value = False
        with self.assertRaises(PermissionError):
            self.register(reference={"doctype": "POS Invoice", "name": "INV-1", "reprint": 1})

    def test_reprint_links_a_new_intent_and_audits_it(self):
        self.register()
        result = self.register(request_id="33333333-3333-4333-8333-333333333333", reference={"doctype": "POS Invoice", "name": "INV-1", "reprint": 1}, reprint_of=ID)
        self.assertNotEqual(result["name"], ID)
        self.assertEqual(STORE[result["name"]].reprint_of, ID)
        audit.log.assert_called_once()

    def test_wrong_outlet_and_source_permission_are_rejected(self):
        with self.assertRaises(PermissionError):
            self.register(pos_profile="Other")
        self.invoice["deny"] = True
        with self.assertRaises(PermissionError):
            self.register()

    def test_rendering_checks_both_read_and_print(self):
        self.assertTrue(api.document_pdf("POS Invoice", "INV-1")["data"])
        self.invoice["deny"] = True
        with self.assertRaises(PermissionError):
            api.document_pdf("POS Invoice", "INV-1")

    def test_raw_receipt_never_adds_drawer_pulse(self):
        api.receipt_output("INV-1", output="raw")
        printing.build_receipt_bytes.assert_called_with(sales.get_receipt.return_value, open_drawer=0)

    def test_automatic_receipt_requires_submitted_original_sale(self):
        with self.assertRaises(PermissionError):
            self.register(automatic=1)
        self.invoice["docstatus"] = 1
        self.register(automatic=1)
        with self.assertRaises(PermissionError):
            self.register(request_id="33333333-3333-4333-8333-333333333333", automatic=1,
                          reference={"doctype": "POS Invoice", "name": "INV-1", "reprint": 1})

    def test_manual_printview_checks_document_access(self):
        self.assertIn("doctype=POS+Invoice", api.document_printview("POS Invoice", "INV-1")["url"])
        self.invoice["deny"] = True
        with self.assertRaises(PermissionError):
            api.document_printview("POS Invoice", "INV-1")

    def test_repeatable_field_setup_preserves_business_and_saved_values(self):
        tree = ast.parse((Path(__file__).resolve().parent.parent / "esafepos/install.py").read_text(encoding="utf-8"))
        node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "make_custom_fields")
        definitions = {}
        stored = {"esafepos_printer_ip": "192.168.1.8", "print_format": "Shop format", "esafepos_print_copies": 2}
        before = dict(stored)
        def sync(values, **kwargs):
            for doctype, fields in values.items():
                for field in fields:
                    definitions[(doctype, field["fieldname"])] = field
        namespace = {"create_custom_fields": sync}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "custom_field_setup", "exec"), namespace)
        namespace["make_custom_fields"]()
        once = dict(definitions)
        namespace["make_custom_fields"]()
        self.assertEqual(definitions, once)
        self.assertEqual(stored, before)
        self.assertEqual(definitions[("POS Profile", "esafepos_silent_printing")]["default"], "0")

    def test_metadata_never_contains_receipt_bytes_or_private_keys(self):
        self.register()
        self.assertNotIn("payload", STORE[ID])
        self.assertNotIn("data", STORE[ID])
        self.assertNotIn("private_key", STORE[ID])

    def test_reported_states_do_not_mutate_sale(self):
        self.register()
        before = dict(self.invoice)
        api.record_event(ID, "unknown", job_id="native-job", certainty="uncertain")
        self.assertEqual(dict(self.invoice), before)
        self.assertEqual(STORE[ID].state, "unknown")
        fake.session.user = "another"
        with self.assertRaises(PermissionError):
            api.record_event(ID, "completed")


if __name__ == "__main__":
    unittest.main()
