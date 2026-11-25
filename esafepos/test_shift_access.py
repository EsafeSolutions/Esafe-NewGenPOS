"""Browser binding, shared ownership and shift lookup using real decision code."""
import ast
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

from esafepos.test_user_access import Record, load_module


def functions_from(file, names, context):
    tree = ast.parse((Path(__file__).parent / file).read_text(encoding="utf-8"))
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    for node in selected:
        node.decorator_list = []
    module = ast.Module(body=selected, type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(file), "exec"), context)


class ShiftAccessTests(unittest.TestCase):
    def setUp(self):
        import esafepos
        import esafepos.api
        self.settings = Record(shift_scope="Per cashier", shift_multiple_computers=1, shared_shift_management=0)
        self.header, self.bound, self.status = "computer-1111111111", "computer-1111111111", "Open"
        self.session = Record(name="REG-A", pos_profile="Till", opened_by="cashier", opened_at="today", opening_float=100,
                              workstation_id=self.bound, meta=Record(has_field=lambda field: True))
        self.frappe = ModuleType("frappe")
        f = self.frappe
        f._ = lambda text: text
        f.PermissionError = PermissionError
        f.throw = lambda text, kind=ValueError: (_ for _ in ()).throw(kind(text))
        f.session = Record(user="cashier")
        f.get_cached_doc = lambda *args: self.settings
        f.get_doc = lambda *args, **kwargs: self.session
        f.get_request_header = lambda name: self.header
        f.has_permission = Mock(return_value=True)
        f.db = Record(get_value=Mock(side_effect=self.get_value), set_value=Mock(side_effect=self.set_value),
                      exists=Mock(return_value=False), get_single_value=lambda dt, field: self.settings.get(field))
        self.permissions = ModuleType("esafepos.api.permissions")
        self.permissions.is_manager = Mock(return_value=False)
        self.permissions.assert_outlet = Mock()
        self.audit = ModuleType("esafepos.api.audit")
        self.audit.log = Mock()
        self.add_patch(patch.dict(sys.modules, {"frappe": f, "esafepos.api.permissions": self.permissions, "esafepos.api.audit": self.audit}))
        self.add_patch(patch.object(esafepos.api, "permissions", self.permissions, create=True))
        self.add_patch(patch.object(esafepos.api, "audit", self.audit, create=True))
        self.subject = load_module("shift_access_subject", "shift_access.py")
        self.add_patch(patch.object(esafepos, "shift_access", self.subject, create=True))
        self.add_patch(patch.dict(sys.modules, {"esafepos.shift_access": self.subject}))
        self.context = {"frappe": f, "_": f._, "_is_manager": self.permissions.is_manager}
        functions_from("api/register.py", {"_assert_owner_or_manager", "move_shift_to_this_computer"}, self.context)
        functions_from("api/session.py", {"shift_scope", "get_open_session"}, self.context)

    def add_patch(self, patcher):
        patcher.start()
        self.addCleanup(patcher.stop)

    def get_value(self, dt, name, field, **kwargs):
        if field == "workstation_id":
            self.assertTrue(kwargs.get("for_update"), "binding must use a current row lock")
            return self.bound
        if field == "status":
            return self.status
        if field == "name":
            if name.get("opened_by") and name["opened_by"] != self.session.opened_by:
                return None
            return self.session.name

    def set_value(self, dt, name, field, value, **kwargs):
        self.bound = value

    def test_multiple_computers_enabled_and_unmigrated_preserve_access(self):
        self.header = "computer-2222222222"
        self.subject.assert_workstation(self.session)
        self.assertTrue(self.subject.allowed_here(self.session))
        self.settings.shift_multiple_computers = None
        self.subject.assert_workstation(self.session)
        self.frappe.db.set_value.assert_not_called()

    def test_single_computer_accepts_original_and_rejects_second(self):
        self.settings.shift_multiple_computers = 0
        self.subject.assert_workstation(self.session)
        self.header = "computer-2222222222"
        self.assertFalse(self.subject.allowed_here(self.session))
        with self.assertRaisesRegex(ValueError, "another computer"):
            self.subject.assert_workstation(self.session)

    def test_existing_unbound_shift_claimed_once_under_lock(self):
        self.settings.shift_multiple_computers = 0
        self.bound = None
        self.subject.assert_workstation(self.session)
        self.assertEqual(self.bound, self.header)
        self.header = "computer-2222222222"
        with self.assertRaises(ValueError):
            self.subject.assert_workstation(self.session)

    def test_missing_invalid_or_oversized_header_rejected_when_restricted(self):
        self.settings.shift_multiple_computers = 0
        for value in [None, "short", "a" * 81, "../../unsafe-value", "computer with spaces"]:
            self.header = value
            with self.assertRaises(ValueError):
                self.subject.assert_workstation(self.session)

    def test_new_opening_is_tagged_and_migration_is_required_for_restriction(self):
        self.subject.tag_opening(self.session)
        self.assertEqual(self.session.workstation_id, self.header)
        self.session.meta.has_field = lambda field: False
        self.settings.shift_multiple_computers = 0
        with self.assertRaisesRegex(ValueError, "migration"):
            self.subject.tag_opening(self.session)

    def test_per_cashier_same_user_sees_same_shift_on_both_computers(self):
        lookup = self.context["get_open_session"]
        for header in ["computer-1111111111", "computer-2222222222"]:
            self.header = header
            self.assertEqual(lookup("Till")["name"], "REG-A")
            self.assertTrue(lookup("Till")["workstation_allowed"])
        self.assertIsNone(lookup("Till", "other"))

    def test_per_outlet_different_users_resolve_the_same_shift(self):
        self.settings.shift_scope = "Per outlet"
        for user in ["cashier", "other"]:
            self.assertEqual(self.context["get_open_session"]("Till", user)["name"], "REG-A")

    def test_shared_selling_does_not_automatically_grant_drawer_management(self):
        self.settings.shift_scope = "Per outlet"
        self.frappe.session.user = "other"
        check = self.context["_assert_owner_or_manager"]
        with self.assertRaises(PermissionError):
            check(self.session)
        self.settings.shared_shift_management = 1
        check(self.session)
        self.permissions.assert_outlet.assert_called_with("Till")
        self.settings.shift_scope = "Per cashier"
        with self.assertRaises(PermissionError):
            check(self.session)

    def test_manager_must_also_use_bound_computer(self):
        self.permissions.is_manager.return_value = True
        self.settings.shift_multiple_computers = 0
        self.header = "computer-2222222222"
        with self.assertRaises(ValueError):
            self.context["_assert_owner_or_manager"](self.session)

    def test_move_requires_manager_native_write_outlet_and_open_shift(self):
        move = self.context["move_shift_to_this_computer"]
        with self.assertRaises(PermissionError):
            move("REG-A")
        self.permissions.is_manager.return_value = True
        self.frappe.has_permission.return_value = False
        with self.assertRaises(PermissionError):
            move("REG-A")
        self.frappe.has_permission.return_value = True
        self.status = "Closing"
        with self.assertRaises(ValueError):
            move("REG-A")
        self.status = "Open"
        self.header = "computer-2222222222"
        self.assertEqual(move("REG-A"), {"moved": True})
        self.assertEqual(self.bound, self.header)
        self.permissions.assert_outlet.assert_called_with("Till")
        self.audit.log.assert_called_once()
        self.permissions.assert_outlet.side_effect = PermissionError("other outlet")
        with self.assertRaises(PermissionError):
            move("REG-A")

    def test_sharing_mode_cannot_merge_live_drawers(self):
        self.frappe.db.exists.return_value = True
        with self.assertRaisesRegex(ValueError, "Close the open shifts"):
            self.subject.apply_settings(self.settings, {"shift_scope": "Per outlet"})
        self.subject.apply_settings(self.settings, {"shift_scope": "Per cashier"})
        self.frappe.db.exists.return_value = False
        self.subject.apply_settings(self.settings, {"shift_scope": "Per outlet", "shift_multiple_computers": 0, "shared_shift_management": 1})
        self.assertEqual(self.settings.shift_scope, "Per outlet")
        self.assertEqual(self.settings.shift_multiple_computers, 0)
        self.assertTrue(self.subject.shared_management())

    def test_old_settings_saves_keep_new_choices_and_reject_bad_values(self):
        self.settings.shift_multiple_computers = 0
        self.subject.apply_settings(self.settings, {})
        self.assertEqual(self.settings.shift_multiple_computers, 0)
        for payload in [{"shift_scope": "All"}, {"shift_multiple_computers": "0"}, {"shared_shift_management": 3}]:
            with self.assertRaises(ValueError):
                self.subject.apply_settings(self.settings, payload)

    def test_migration_defaults_missing_setting_and_preserves_stored_choice(self):
        self.frappe.db.sql = Mock(return_value=[])
        self.frappe.clear_cache = Mock()
        migration = load_module("shift_defaults_subject", "patches/shift_sharing_defaults.py")
        migration.execute()
        self.assertEqual(self.frappe.db.sql.call_count, 2)
        self.assertEqual(self.frappe.db.sql.call_args.args[1][-1], "1")
        for stored in [[["0"]], [["1"]]]:
            self.frappe.db.sql.reset_mock()
            self.frappe.db.sql.return_value = stored
            migration.execute()
            self.frappe.db.sql.assert_called_once()


if __name__ == "__main__":
    unittest.main()
