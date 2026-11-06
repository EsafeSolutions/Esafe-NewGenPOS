# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
"""v0.2: printer fields on POS Profile (existing installs got the Sales
Invoice fields at install time; create_custom_fields is idempotent)."""

from lumenpos.install import make_custom_fields


def execute():
    make_custom_fields()
