# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
"""v0.4: POS Invoice migration, create the custom fields on POS Invoice
(idempotent for the rest)."""

from esafepos.install import make_custom_fields


def execute():
    make_custom_fields()
