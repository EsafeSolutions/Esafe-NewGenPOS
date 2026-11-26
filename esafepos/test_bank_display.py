import ast
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

from esafepos.bank_display import clean_config, settings_value, client_config


class BankDisplayTests(unittest.TestCase):
    def account(self, **values):
        return dict(bank_name="Bank", holder="Shop", account_number="001234", **values)

    def test_account_number_and_explicit_qr_payload_preserved(self):
        config = clean_config({"enabled": True, "accounts": [self.account(currency="lkr", qr_payload="bank-payload")]})
        self.assertEqual(config["accounts"][0]["account_number"], "001234")
        self.assertEqual(config["accounts"][0]["currency"], "LKR")
        self.assertEqual(config["accounts"][0]["qr_payload"], "bank-payload")

    def test_incomplete_accounts_and_bank_trigger_without_method_rejected(self):
        for value in ({"enabled": True}, {"accounts": [{"bank_name": "Bank"}]},
                      {"trigger": "bank", "accounts": [self.account()]}):
            with self.assertRaises(ValueError):
                clean_config(value)

    def test_only_local_raster_images_accepted(self):
        for path in ("javascript:alert(1)", "https://example.com/logo.svg", "/files/../../image.png", "/files/a.svg", "/private/files/a.png"):
            with self.assertRaises(ValueError):
                clean_config({"accounts": [self.account(logo=path)]})
        self.assertEqual(clean_config({"accounts": [self.account(logo="/files/bank.png") ]})["accounts"][0]["logo"], "/files/bank.png")

    def test_currency_size_payload_and_account_limits(self):
        for value in ({"accounts": [self.account(currency="123")]}, {"accounts": [self.account(qr_size=float("nan"))]},
                      {"accounts": [self.account(qr_size=361)]}, {"accounts": [self.account(qr_payload="x" * 1501)]},
                      {"accounts": [self.account()] * 13}):
            with self.assertRaises(ValueError):
                clean_config(value)

    def test_unmigrated_or_corrupt_configuration_is_disabled(self):
        self.assertFalse(settings_value({})["enabled"])
        self.assertFalse(settings_value({"bank_transfer_display": "not-json"})["enabled"])

    def test_bootstrap_exposes_only_default_and_current_register_accounts(self):
        doc = {"bank_transfer_display": {"enabled": True, "accounts": [self.account(pos_profile="Till A"), self.account(pos_profile="Till B"), self.account()]}}
        self.assertEqual([row["pos_profile"] for row in client_config(doc, "Till A")["accounts"]], ["Till A", ""])

    def test_write_and_upload_require_settings_permission_before_processing(self):
        source = Path(__file__).parent / "api/bank_display.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        frappe = Mock()
        frappe.has_permission.return_value = False
        frappe.PermissionError = PermissionError
        frappe.throw.side_effect = PermissionError
        namespace = {"frappe": frappe, "_": lambda value: value}
        for name in ("_require_write", "save_settings", "upload_image"):
            node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            node.decorator_list = []
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
        with self.assertRaises(PermissionError): namespace["save_settings"]({})
        with self.assertRaises(PermissionError): namespace["upload_image"]("invalid")
        frappe.get_doc.assert_not_called()

    def test_image_upload_reencodes_and_attaches_public_file_and_rejects_bad_input(self):
        import base64
        import io
        from PIL import Image
        source = Path(__file__).parent / "api/bank_display.py"
        node = next(n for n in ast.parse(source.read_text(encoding="utf-8")).body if isinstance(n, ast.FunctionDef) and n.name == "upload_image")
        node.decorator_list = []
        frappe = Mock()
        frappe.throw.side_effect = ValueError
        file_manager = ModuleType("frappe.utils.file_manager")
        file_manager.save_file = Mock(return_value=Mock(file_url="/files/bank-logo.png"))
        namespace = {"frappe": frappe, "_": lambda v: v, "_require_write": lambda: None, "base64": base64, "io": io}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
        image_bytes = io.BytesIO()
        Image.new("RGB", (8, 8), color="white").save(image_bytes, format="JPEG")
        with patch.dict(sys.modules, {"frappe.utils.file_manager": file_manager}):
            result = namespace["upload_image"](base64.b64encode(image_bytes.getvalue()).decode("ascii"))
            self.assertEqual(result["file_url"], "/files/bank-logo.png")
            self.assertTrue(file_manager.save_file.call_args.args[1].startswith(b"\x89PNG"))
            self.assertEqual(file_manager.save_file.call_args.kwargs["is_private"], 0)
            self.assertEqual(file_manager.save_file.call_args.args[2:4], ("EsafePOS Settings", "EsafePOS Settings"))
            for value in ("not-base64", base64.b64encode(b"<svg/>").decode("ascii"), "a" * 2800001):
                with self.assertRaises(ValueError): namespace["upload_image"](value)
            self.assertEqual(file_manager.save_file.call_count, 1)


class RegisterOverviewTests(unittest.TestCase):
    def function(self, name, namespace):
        source = Path(__file__).parent / "api/register.py"
        node = next(n for n in ast.parse(source.read_text(encoding="utf-8")).body if isinstance(n, ast.FunctionDef) and n.name == name)
        node.decorator_list = []
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
        return namespace[name]

    def test_strict_close_snapshot_rejects_movement_currency_and_missing_summary(self):
        import json
        frappe = Mock()
        frappe.throw.side_effect = ValueError
        check = self.function("_assert_expected_tallies", {"frappe": frappe, "_": lambda v: v, "json": json})
        summary = {"expected": [{"mode_of_payment": "Cash", "expected_amount": 500, "currency": "LKR"}]}
        check({"Cash": {"amount": 500, "currency": "LKR"}}, summary)
        for value, current in (({"Cash": {"amount": 501, "currency": "LKR"}}, summary),
                               ({"Cash": {"amount": 500, "currency": "USD"}}, summary), ({}, None)):
            with self.assertRaises(ValueError): check(value, current)

    def test_activity_separates_returns_and_uses_parameterized_company_values(self):
        frappe = Mock()
        frappe.get_meta.return_value.has_field.side_effect = lambda field: field != "esafepos_loyalty_change_amount"
        frappe.db.table_exists.return_value = True
        frappe.db.sql.side_effect = [[{"sales": 2500, "returns": 300, "sale_count": 2, "return_count": 1,
                                      "loyalty_points": 20, "loyalty_amount": 20}], [(12,)]]
        activity = self.function("_session_activity", {"frappe": frappe, "_": lambda v: v, "flt": lambda v, precision=2: round(float(v or 0), precision), "cint": lambda v: int(v or 0)})
        result = activity("SHIFT-1", "POS Invoice")
        self.assertEqual((result["sale_count"], result["return_count"], result["returns"], result["earned_points"]), (2, 1, 300, 12))
        self.assertEqual(result["esafepos_loyalty_change_amount"], 0)
        self.assertEqual(frappe.db.sql.call_args_list[0].args[1], "SHIFT-1")
        self.assertIn("conversion_rate", frappe.db.sql.call_args_list[0].args[0])
        frappe.throw.side_effect = ValueError
        with self.assertRaises(ValueError): activity("SHIFT-1", "bad table")

    def test_directory_limits_cashiers_to_their_own_authorized_profiles(self):
        import esafepos.api
        frappe = Mock()
        frappe.session.user = "cashier"
        frappe.get_all.return_value = []
        permissions = ModuleType("esafepos.api.permissions")
        permissions.is_manager = Mock(return_value=False)
        session = ModuleType("esafepos.api.session")
        session._user_profiles = Mock(return_value=["Allowed till"])
        with patch.dict(sys.modules, {"esafepos.api.permissions": permissions, "esafepos.api.session": session}), patch.object(esafepos.api, "permissions", permissions, create=True):
            directory = self.function("all_registers", {"frappe": frappe, "_": lambda v: v})
            self.assertEqual(directory(), [])
            filters = frappe.get_all.call_args.kwargs["filters"]
            self.assertEqual(filters["opened_by"], "cashier")
            self.assertEqual(filters["pos_profile"], ["in", ["Allowed till"]])
            permissions.is_manager.return_value = True
            directory()
            self.assertNotIn("opened_by", frappe.get_all.call_args.kwargs["filters"])

    def test_actual_activity_sql_excludes_cancelled_sales_and_converts_redemption(self):
        import sqlite3
        database = sqlite3.connect(":memory:")
        self.addCleanup(database.close)
        database.execute("""create table `tabPOS Invoice` (name text, esafepos_session text, docstatus integer, is_return integer,
                         base_grand_total real, conversion_rate real, loyalty_points integer, loyalty_amount real,
                         esafepos_loyalty_change_amount real)""")
        database.executemany("insert into `tabPOS Invoice` values (?,?,?,?,?,?,?,?,?)",
                             [("S1", "REG", 1, 0, 1000, 1, 10, 10, 8), ("S2", "REG", 1, 0, 600, 2, 20, 10, 0),
                              ("R1", "REG", 1, 1, -200, 1, 0, 0, 0), ("C1", "REG", 2, 0, 9999, 1, 0, 0, 0),
                              ("OTHER", "ELSE", 1, 0, 8888, 1, 0, 0, 0)])
        database.execute("create table `tabLoyalty Point Entry` (invoice text, invoice_type text, loyalty_points integer)")
        database.executemany("insert into `tabLoyalty Point Entry` values (?,?,?)", [("S1", "POS Invoice", 12), ("S2", "POS Invoice", 6), ("S1", "Sales Invoice", 100), ("S2", "POS Invoice", -20)])
        frappe = Mock()
        frappe.get_meta.return_value.has_field.return_value = True
        frappe.db.table_exists.return_value = True
        def sql(query, params, as_dict=False):
            cursor = database.execute(query.replace("%s", "?"), (params,) if isinstance(params, str) else params)
            rows = cursor.fetchall()
            return [dict(zip([column[0] for column in cursor.description], row)) for row in rows] if as_dict else rows
        frappe.db.sql.side_effect = sql
        activity = self.function("_session_activity", {"frappe": frappe, "_": lambda v: v, "flt": lambda v, precision=2: round(float(v or 0), precision), "cint": lambda v: int(v or 0)})
        result = activity("REG", "POS Invoice")
        self.assertEqual((result["sales"], result["returns"], result["sale_count"], result["return_count"]), (1600, 200, 2, 1))
        self.assertEqual((result["loyalty_amount"], result["esafepos_loyalty_change_amount"], result["earned_points"]), (30, 8, 18))


if __name__ == "__main__":
    unittest.main()
