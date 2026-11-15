import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from esafepos.api import items, permissions


class ItemPriceAccessTests(unittest.TestCase):
    def test_cashier_needs_a_separate_rule_for_saved_prices(self):
        with patch.object(permissions, "_roles", return_value={"EsafePOS Cashier"}), \
                patch.object(permissions, "_rules", return_value=[]):
            self.assertTrue(permissions.can_edit_price("cashier@example.com"))
            self.assertFalse(permissions.allowed(permissions.ITEM_PRICE_EDIT, "cashier@example.com"))

    def test_manager_or_matching_rule_grants_pos_price_access(self):
        capability = permissions.ITEM_PRICE_EDIT
        with patch.object(permissions, "_roles", return_value={"EsafePOS Manager"}):
            self.assertTrue(permissions.allowed(capability, "manager@example.com"))
        for rule in ({"role": "Pricing Clerk"}, {"user": "clerk@example.com"}):
            with patch.object(permissions, "_roles", return_value={"Pricing Clerk"}), \
                    patch.object(permissions, "_rules", return_value=[rule]):
                self.assertTrue(permissions.allowed(capability, "clerk@example.com"))

    def test_erpnext_permissions_apply_even_with_pos_price_access(self):
        grants = {("Item", "read"), ("Price List", "read"), ("Item Price", "read")}
        with patch.object(items, "allowed", return_value=True), \
                patch.object(items.frappe, "has_permission", side_effect=lambda dt, mode: (dt, mode) in grants):
            self.assertFalse(items.can_edit())
            grants.add(("Item Price", "write"))
            self.assertTrue(items.can_edit())

    def test_direct_price_write_is_rejected_before_changing_item(self):
        item = Mock(disabled=0, is_sales_item=1, has_variants=0)
        with patch.object(items, "_profile"), patch.object(items, "_can_edit_prices", return_value=False), \
                patch.object(items.frappe, "get_doc", return_value=item), \
                patch.object(items.frappe, "throw", side_effect=items.frappe.PermissionError), \
                patch.object(items, "_selling_list") as selling_list:
            with self.assertRaises(items.frappe.PermissionError):
                items.save_item("Test Till", "ITEM-1", "New name", [{"uom": "Kg", "price": 125}])
        selling_list.assert_not_called()
        item.check_permission.assert_called_once_with("read")
        item.save.assert_not_called()

    def test_each_native_price_permission_is_checked_before_any_save(self):
        item = Mock(disabled=0, is_sales_item=1, has_variants=0, has_serial_no=0, stock_uom="Kg")
        existing = SimpleNamespace(name="PRICE-1", price_list_rate=100)
        old_price = Mock()
        new_price = Mock()
        new_price.check_permission.side_effect = items.frappe.PermissionError
        with patch.object(items, "_profile"), patch.object(items, "_can_edit_prices", return_value=True), \
                patch.object(items.frappe, "get_doc", return_value=item), \
                patch.object(items, "_selling_list", return_value=SimpleNamespace(name="Standard Selling")), \
                patch.object(items, "conversions", return_value={("ITEM-1", "Pack"): 0.5}), \
                patch.object(items, "_standing_price", side_effect=[existing, None]), \
                patch.object(items, "_item_price_doc", side_effect=[old_price, new_price]):
            with self.assertRaises(items.frappe.PermissionError):
                items.save_item("Test Till", "ITEM-1", prices=[{"uom": "Kg", "price": 125}, {"uom": "Pack", "price": 80}])
        old_price.check_permission.assert_called_once_with("write")
        new_price.check_permission.assert_called_once_with("create")
        old_price.save.assert_not_called()
        new_price.save.assert_not_called()
