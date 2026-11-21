"""Standalone label API authorization tests. Frappe I/O is mocked, not a live site."""
import importlib
import json
import pathlib
import sys
import types
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
fake = types.ModuleType("frappe")
fake._ = lambda value: value
fake.whitelist = lambda *args, **kwargs: lambda fn: fn
fake.PermissionError = PermissionError
fake.throw = lambda message, *args: (_ for _ in ()).throw(args[0](message) if args else ValueError(message))
fake.session = types.SimpleNamespace(user="cashier@example.com")
fake.db = Mock()
fake.get_doc = Mock()
fake.get_cached_doc = Mock()
utils = types.ModuleType("frappe.utils")
utils.cint = lambda n: int(n or 0)
utils.flt = lambda n, *args: float(n or 0)
utils.get_datetime = utils.getdate = lambda n: n
utils.nowdate = lambda: "2026-11-20"
sys.modules["frappe"] = fake
sys.modules["frappe.utils"] = utils
labels = importlib.import_module("esafepos.api.labels")


class LabelPermissionTests(unittest.TestCase):
    def test_preparation_reprices_instead_of_trusting_client_price(self):
        class Job:
            def __init__(self, data):
                self.__dict__.update(data)
                self.name = "JOB"
            def insert(self, **kwargs):
                return self
        fresh = {"item_code": "LP1", "qty": 1, "uom": "Nos", "price_with_tax": 450, "barcode": "LP1"}
        stock = {"kind": "roll", "w": 58, "h": 40, "columns": 1, "rows": 1, "pageW": 58,
                 "pageH": 40, "gapX": 2, "gapY": 3, "left": 0, "right": 0, "top": 0, "bottom": 0, "autoWidth": True}
        with patch.object(labels, "_guard", return_value=types.SimpleNamespace(company="Company")), \
                patch.object(labels, "_require_tables"), patch.object(labels, "_rows", return_value=[fresh]), \
                patch.object(fake.db, "get_value", return_value=None), patch.object(fake, "get_doc", side_effect=Job):
            result = labels.prepare_job("Main", [{"item_code": "LP1", "qty": 2, "price_with_tax": 1}],
                                        {"stock": stock, "design": {"scale": 100}}, "a" * 16)
        self.assertEqual(result["snapshot"]["rows"][0]["price_with_tax"], 450)
        self.assertEqual(result["snapshot"]["rows"][0]["qty"], 2)

    def test_alternate_unit_requires_a_configured_price(self):
        row = {"item_code": "LP1", "uom": "Nos", "selling_units": []}
        with self.assertRaises(ValueError):
            labels._choose_unit(None, row, "Box")

    def test_alternate_unit_recomputes_tax_and_uses_its_barcode(self):
        row = {"item_code": "LP1", "uom": "Nos", "selling_units": [{"uom": "Box", "price": 500}],
               "barcode_options": [{"uom": "Box", "barcode": "BOX1"}]}
        with patch.object(labels, "_tax_factors", return_value={"LP1": 1.1}), \
                patch.object(labels, "_equivalents", return_value=([], 1)):
            labels._choose_unit(None, row, "Box")
        self.assertEqual(row["barcode"], "BOX1")
        self.assertEqual(row["price_with_tax"], 550)

    def test_feature_gate_is_applied_to_workspace(self):
        with patch.object(labels, "can_print_labels", return_value=False):
            with self.assertRaises(PermissionError):
                labels.workspace("Other outlet")

    def test_owned_job_rejects_another_user(self):
        doc = types.SimpleNamespace(pos_profile="Main", company="Company", owner="other@example.com")
        with patch.object(labels, "_guard", return_value=types.SimpleNamespace(company="Company")), \
                patch.object(fake, "get_doc", return_value=doc), \
                patch.object(labels.permissions, "is_manager", return_value=False):
            with self.assertRaises(PermissionError):
                labels._owned_job("Main", "JOB")

    def test_owned_job_rejects_another_outlet_even_for_manager(self):
        doc = types.SimpleNamespace(pos_profile="Other", company="Company", owner=fake.session.user)
        with patch.object(labels, "_guard", return_value=types.SimpleNamespace(company="Company")), \
                patch.object(fake, "get_doc", return_value=doc):
            with self.assertRaises(PermissionError):
                labels._owned_job("Main", "JOB")

    def test_cashier_cannot_save_shared_presets(self):
        with patch.object(labels, "_guard"), patch.object(labels, "_require_tables"), \
                patch.object(labels.permissions, "is_manager", return_value=False):
            with self.assertRaises(PermissionError):
                labels.save_preset("Main", "My stock", "Stock", {})

    def test_label_signer_rejects_raw_and_remote_destinations(self):
        job = types.SimpleNamespace(name="JOB", status="Prepared")
        for params in ({"printer": {"host": "example.com"}},
                       {"printer": {"name": "Thermal"}, "data": [{"type": "raw", "format": "command"}]}):
            params["options"] = {"jobName": "Labels:JOB"}
            with self.subTest(params=params), patch.object(labels, "_guard"), \
                    patch.object(labels, "_owned_job", return_value=job), self.assertRaises(ValueError):
                labels.sign_request("Main", json.dumps({"call": "print", "params": params}), "JOB")

    def test_label_signer_rejects_device_control_and_oversized_requests(self):
        with patch.object(labels, "_guard"):
            with self.assertRaises(PermissionError):
                labels.sign_request("Main", '{"call":"serial.sendData"}')
            with self.assertRaises(ValueError):
                labels.sign_request("Main", "x" * 131073)


if __name__ == "__main__":
    unittest.main()
