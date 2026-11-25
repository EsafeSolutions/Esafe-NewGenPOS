"""Access decisions and administration boundaries without a running bench."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch


class Record(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__

    def set(self, key, value):
        self[key] = value

    def append(self, key, value):
        self.setdefault(key, []).append(Record(value))


def load_module(name, file):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AccessTests(unittest.TestCase):
    def setUp(self):
        import esafepos
        import esafepos.api
        self.roles = {"cashier": ["Sales User"], "other": ["Sales User"], "admin": ["System Manager"]}
        self.settings = Record(user_access_levels=[], capability_rules=[], save=Mock())
        self.profiles, self.companies = {}, {}
        self.native_write = True
        self.frappe = ModuleType("frappe")
        f = self.frappe
        f._ = lambda text: text
        f._dict = Record
        f.PermissionError = PermissionError
        f.throw = lambda text, kind=ValueError: (_ for _ in ()).throw(kind(text))
        f.whitelist = lambda **kwargs: lambda fn: fn
        f.session = Record(user="cashier")
        f.get_roles = lambda user=None: self.roles.get(user or f.session.user, [])
        f.get_cached_doc = lambda dt, name=None: self.settings if dt == "EsafePOS Settings" else self.profiles[name]
        f.has_permission = lambda *args: self.native_write
        f.get_meta = lambda dt: Record(has_field=lambda field: True)
        f.get_all = lambda dt, **kwargs: list(self.companies.get(kwargs.get("filters", {}).get("user"), []))
        f.db = Record(table_exists=Mock(return_value=True), get_single_value=Mock(return_value=None),
                      exists=Mock(side_effect=lambda dt, name: name in self.profiles), sql=Mock(return_value=[]),
                      get_value=Mock(return_value=Record(enabled=1, user_type="System User")))
        utils = ModuleType("frappe.utils")
        utils.cint = lambda value: int(value or 0)
        self.user_doc = Record(meta=Record(has_field=lambda field: True), check_permission=Mock(), save=Mock())
        f.get_doc = lambda dt, name=None: self.settings if dt == "EsafePOS Settings" else self.profiles.get(name, self.user_doc)
        self.audit = ModuleType("esafepos.api.audit")
        self.audit.log = Mock()
        self.add_patch(patch.dict(sys.modules, {"frappe": f, "frappe.utils": utils, "esafepos.api.audit": self.audit}))
        self.add_patch(patch.object(esafepos.api, "audit", self.audit, create=True))
        self.access = load_module("access_subject", "user_access.py")
        self.add_patch(patch.object(esafepos, "user_access", self.access, create=True))
        self.add_patch(patch.dict(sys.modules, {"esafepos.user_access": self.access}))
        self.reports = load_module("reports_access_subject", "reports_access.py")
        self.add_patch(patch.object(esafepos, "reports_access", self.reports, create=True))
        self.permissions = load_module("permission_subject", "api/permissions.py")
        self.add_patch(patch.object(esafepos.api, "permissions", self.permissions, create=True))
        self.add_patch(patch.dict(sys.modules, {"esafepos.api.permissions": self.permissions}))
        self.api = load_module("access_api_subject", "api/user_access.py")
        self.add_patch(patch.dict(sys.modules, {"esafepos.api.user_access": self.api}))

    def add_patch(self, patcher):
        patcher.start()
        self.addCleanup(patcher.stop)

    def assign(self, level, profile="", user="cashier"):
        self.settings.user_access_levels = [Record(user=user, access_level=level, access_profile=profile)]

    def admin(self):
        self.frappe.session.user = "admin"

    def test_unassigned_and_unmigrated_keep_existing_rules(self):
        self.assertIsNone(self.access.assignment())
        self.assertTrue(self.permissions.can_edit_price())
        self.assertFalse(self.permissions.can_see_profit())
        self.assign("Cashier")
        self.frappe.db.table_exists.return_value = False
        self.assertIsNone(self.access.assignment())

    def test_cashier_preset_restricts_sensitive_actions(self):
        self.assign("Cashier")
        self.assertTrue(self.access.can_sell())
        self.assertTrue(self.permissions.can_open_register())
        self.assertTrue(self.permissions.can_cash_in())
        self.assertFalse(self.permissions.can_cash_out())
        self.assertFalse(self.permissions.can_edit_price())
        self.assertFalse(self.permissions.can_see_profit())
        self.assertFalse(self.permissions.can_delete_sales())

    def test_supervisor_has_cash_out_but_no_management_or_deletion(self):
        self.assign("Supervisor")
        self.assertTrue(self.permissions.can_cash_out())
        self.assertTrue(self.permissions.can_see_sales_reports())
        self.assertFalse(self.permissions.is_manager())
        self.assertFalse(self.permissions.can_delete_sales())

    def test_custom_manager_can_deny_permanent_deletion(self):
        self.profiles["Duty manager"] = Record(base_level="Manager", capabilities=[Record(capability="Permanently delete sales", allowed=0)])
        self.assign("Custom", "Duty manager")
        self.assertTrue(self.permissions.is_manager())
        self.assertFalse(self.permissions.can_delete_sales())
        self.assertTrue(self.permissions.can_close_register())

    def test_custom_overrides_and_global_rules_intersect(self):
        self.profiles["Counter"] = Record(base_level="Cashier", capabilities=[Record(capability="Cash out", allowed=1)])
        self.assign("Custom", "Counter")
        self.assertTrue(self.permissions.can_cash_out())
        self.settings.capability_rules = [Record(capability="Cash out", user="other")]
        self.assertFalse(self.permissions.can_cash_out())
        self.settings.capability_rules[0].user = "cashier"
        self.assertTrue(self.permissions.can_cash_out())
        self.settings.capability_rules = [Record(capability="See profit", user="cashier")]
        self.assertFalse(self.permissions.can_see_profit())

    def test_legacy_cash_rules_still_restrict_presets(self):
        self.assign("Supervisor")
        self.settings.capability_rules = [Record(capability="Cash in / out", user="other")]
        self.assertFalse(self.permissions.can_cash_out())
        self.settings.capability_rules[0].user = "cashier"
        self.assertTrue(self.permissions.can_cash_out())

    def test_reports_only_cannot_sell_or_grant_cash_even_with_bad_profile_data(self):
        self.profiles["Reports"] = Record(base_level="Reports only", capabilities=[Record(capability="Cash out", allowed=1)])
        self.assign("Custom", "Reports")
        self.assertTrue(self.access.reports_only())
        self.assertFalse(self.access.can_sell())
        self.assertFalse(self.permissions.can_cash_out())
        self.assertTrue(self.permissions.can_see_profit())
        self.assertTrue(self.reports.reports_only())
        self.assertTrue(self.reports.is_viewer())
        self.frappe.db.sql.return_value = [["0"]]
        self.assertFalse(self.reports.is_viewer(), "site reports switch remains authoritative")

    def test_missing_or_invalid_profile_fails_closed(self):
        for level, name in [("Custom", "Deleted"), ("Unknown", "")]:
            self.assign(level, name)
            self.assertFalse(self.access.can_sell())
            self.assertFalse(self.permissions.can_open_register())

    def test_native_managers_remain_authoritative(self):
        self.assign("Reports only", user="admin")
        self.assertIsNone(self.access.assignment("admin"))
        self.assertTrue(self.permissions.can_delete_sales("admin"))

    def test_app_manager_cannot_administer_user_levels(self):
        self.assign("Manager")
        self.assertTrue(self.permissions.is_manager())
        with self.assertRaises(PermissionError):
            self.api.save_user_level("other", "Cashier")

    def test_assignment_requires_native_settings_write(self):
        self.admin()
        self.native_write = False
        with self.assertRaises(PermissionError):
            self.api.save_user_level("other", "Cashier")

    def test_assignment_blocks_users_outside_company_scope(self):
        self.admin()
        self.companies = {"admin": {"A"}, "other": {"A", "B"}}
        with self.assertRaises(PermissionError):
            self.api.save_user_level("other", "Cashier")
        self.companies["other"] = set()
        with self.assertRaises(PermissionError):
            self.api.save_user_level("other", "Cashier")

    def test_assignment_preserves_other_users_and_other_settings(self):
        self.admin()
        self.assign("Cashier")
        self.settings.shift_multiple_computers = 0
        self.api.save_user_level("other", "Supervisor")
        self.assertEqual([r.user for r in self.settings.user_access_levels], ["cashier", "other"])
        self.assertEqual(self.settings.shift_multiple_computers, 0)
        self.api.save_user_level("other", "Use existing roles")
        self.assertEqual([r.user for r in self.settings.user_access_levels], ["cashier"])
        self.frappe.db.sql.assert_called_with("select field from tabSingles where doctype=%s for update", "EsafePOS Settings")

    def test_assignment_rejects_bad_level_profile_and_native_manager_downgrade(self):
        self.admin()
        for user, level, profile in [("other", "Root", ""), ("other", "Custom", "Missing"), ("admin", "Cashier", "")]:
            with self.assertRaises(ValueError):
                self.api.save_user_level(user, level, profile)

    def test_assignment_rejects_guest_disabled_and_website_users(self):
        self.admin()
        with self.assertRaises(ValueError):
            self.api.save_user_level("Guest", "Manager")
        for row in [Record(enabled=0, user_type="System User"), Record(enabled=1, user_type="Website User")]:
            self.frappe.db.get_value.return_value = row
            with self.assertRaises(ValueError):
                self.api.save_user_level("other", "Manager")

    def test_login_limit_only_changes_native_session_count(self):
        self.admin()
        self.api.save_login_limit("other", 2)
        self.assertEqual(self.user_doc.simultaneous_sessions, 2)
        self.user_doc.check_permission.assert_called_once_with("write")
        self.user_doc.save.assert_called_once_with()
        self.assertEqual(self.settings.user_access_levels, [])

    def test_login_limit_boundaries(self):
        self.admin()
        for value in [0, 21, -1, "two", 2.5, "2.0", None]:
            with self.assertRaises(ValueError):
                self.api.save_login_limit("other", value)
        self.api.save_login_limit("other", "20")
        self.assertEqual(self.user_doc.simultaneous_sessions, 20)

    def test_login_limit_requires_native_user_write(self):
        self.admin()
        self.frappe.has_permission = lambda dt, action: dt != "User"
        with self.assertRaises(PermissionError):
            self.api.save_login_limit("other", 2)

    def test_profile_rejects_duplicate_unknown_and_reports_write_capabilities(self):
        self.admin()
        for caps, base in [([{"capability": "Fake", "allowed": 1}], "Cashier"),
                           ([{"capability": "Cash in", "allowed": 1}] * 2, "Cashier"),
                           ([{"capability": "Cash in", "allowed": 1}], "Reports only")]:
            with self.assertRaises(ValueError):
                self.api.save_access_profile({"name": "Desk", "base_level": base, "capabilities": caps})

    def test_editing_shared_profile_checks_every_assigned_users_companies(self):
        self.admin()
        self.companies = {"admin": {"A"}, "cashier": {"B"}}
        self.assign("Custom", "Desk")
        with self.assertRaises(PermissionError):
            self.api.save_access_profile({"name": "Desk", "base_level": "Cashier", "capabilities": []})

    def test_profile_stale_editor_is_rejected(self):
        self.admin()
        self.profiles["Desk"] = Record(modified="new")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.api.save_access_profile({"name": "Desk", "base_level": "Cashier", "modified": "old", "capabilities": []})

    def test_profile_save_valid_overrides(self):
        self.admin()
        self.profiles["Desk"] = Record(modified="now", name="Desk", save=Mock())
        result = self.api.save_access_profile({"name": "Desk", "base_level": "Supervisor", "modified": "now",
                                               "capabilities": [{"capability": "Cash out", "allowed": 0}]})
        self.assertEqual(result, {"saved": True, "name": "Desk"})
        self.assertEqual(self.profiles["Desk"].capabilities, [{"capability": "Cash out", "allowed": 0}])

    def test_direct_settings_write_cannot_self_promote(self):
        self.settings.get_doc_before_save = lambda: Record(user_access_levels=[])
        self.assign("Manager")
        with self.assertRaises(PermissionError):
            self.access.validate_assignments(self.settings)

    def test_other_settings_save_preserves_levels_without_requiring_admin(self):
        self.assign("Cashier")
        self.settings.get_doc_before_save = lambda: Record(user_access_levels=list(self.settings.user_access_levels))
        self.access.validate_assignments(self.settings)

    def test_direct_settings_assignment_validates_company_scope_and_duplicates(self):
        self.admin()
        self.settings.get_doc_before_save = lambda: Record(user_access_levels=[])
        self.assign("Cashier")
        self.companies = {"admin": {"A"}, "cashier": {"B"}}
        with self.assertRaises(PermissionError):
            self.access.validate_assignments(self.settings)
        self.companies = {}
        self.settings.user_access_levels *= 2
        with self.assertRaisesRegex(ValueError, "one valid"):
            self.access.validate_assignments(self.settings)


if __name__ == "__main__":
    unittest.main()
