# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
import frappe
from frappe import _
from frappe.model.document import Document


class POSReturnRestriction(Document):
    def validate(self):
        target = {
            "Item": self.item_code,
            "Item Group": self.item_group,
            "Brand": self.brand,
            "Tag": self.tag,
        }.get(self.applies_to or "Item Group")
        if not target:
            frappe.throw(_("Choose the {0} this rule applies to").format(_(self.applies_to or "Item Group")))
