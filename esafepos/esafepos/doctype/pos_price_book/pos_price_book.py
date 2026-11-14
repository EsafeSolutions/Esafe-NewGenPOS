# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
import frappe
from frappe import _
from frappe.model.document import Document


class POSPriceBook(Document):
    def validate(self):
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            frappe.throw(_("Valid To cannot be before Valid From"))
