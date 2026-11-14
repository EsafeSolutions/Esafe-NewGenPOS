# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "ESAFEPOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
from frappe.model.document import Document


class POSCashbackRule(Document):
    def on_update(self):
        # A rule saved outside EsafePOS's own screen lands with a daily window
        # nobody set. See promotions.loader.clear_accidental_window.
        from esafepos.promotions.loader import clear_accidental_window

        clear_accidental_window(self)
