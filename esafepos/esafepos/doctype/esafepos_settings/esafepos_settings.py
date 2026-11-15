# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "ESAFEPOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
from frappe.model.document import Document


class EsafePOSSettings(Document):
    def validate(self):
        from frappe.utils import cint

        if cint(self.get("enable_walk_in_codes")):
            from esafepos.walk_in import ensure_customer

            ensure_customer()
