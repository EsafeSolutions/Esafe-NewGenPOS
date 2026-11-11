# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "ESAFEPOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
"""Weight-embedded (scale) barcode parsing.

In retail, deli and grocery stores, electronic computing scales print variable-weight
barcodes (usually EAN-13 or UPC-A) following standard in-store prefix ranges:
  - EAN-13: 2-digit prefix (20 to 29, or 02) + item PLU + weight (grams/decimals) + check digit
  - UPC-A: 1-digit prefix (2) + 5-digit PLU + 5-digit weight + check digit

This module parses a scanned barcode burst, extracts the item candidate keys and the
decimal weight (quantity), allowing the till to automatically price and sell weighed items.
"""
from __future__ import annotations

import re

# Standard in-store prefixes allocated by GS1 for internal / variable-measure use
DEFAULT_PREFIXES = ("20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "02")


def parse_scale_barcode(
    code: str | None,
    prefixes: tuple[str, ...] | list[str] | set[str] | None = None,
    plu_len: int = 5,
    decimals: int = 3,
) -> dict | None:
    """Parse a weight-embedded scale barcode.

    Returns dict with keys:
      - is_scale_barcode: True
      - prefix: str (e.g. "20")
      - plu: str (e.g. "01234")
      - weight: float (e.g. 1.5)
      - candidates: list[str] item lookup keys in priority order
      - check_digit: str
    Or None if the code does not match a valid scale barcode format.
    """
    raw = str(code or "").strip()
    if not raw or not raw.isdigit():
        return None

    # Supported lengths: 12 (UPC-A) or 13 (EAN-13)
    if len(raw) == 12:
        # Standard UPC-A price/weight starts with '2'. Normalize to 13 digits with leading '0'
        if raw.startswith("2"):
            raw = "0" + raw
        else:
            return None

    if len(raw) != 13:
        return None

    allowed_prefixes = (
        set(p.strip() for p in prefixes if str(p).strip())
        if prefixes is not None
        else set(DEFAULT_PREFIXES)
    )

    prefix = raw[:2]
    if prefix not in allowed_prefixes:
        return None

    plu_len = 4 if plu_len == 4 else 5
    decimals = 3 if decimals is None or decimals < 0 else int(decimals)

    if plu_len == 5:
        plu = raw[2:7]
        raw_weight = raw[7:12]
        check_digit = raw[12]
    else:  # plu_len == 4
        plu = raw[2:6]
        raw_weight = raw[6:12]
        check_digit = raw[12]

    try:
        weight_int = int(raw_weight)
    except ValueError:
        return None

    if weight_int <= 0:
        return None

    factor = 10 ** decimals
    weight = round(weight_int / float(factor), 4)

    # Candidate keys to search in Item Barcode / Item tables:
    candidates: list[str] = []

    def add_cand(val: str):
        val = str(val).strip()
        if val and val not in candidates:
            candidates.append(val)

    # Priority 1: Prefix + PLU (e.g. "2001234" or "2012345")
    add_cand(prefix + plu)
    # Priority 2: PLU as printed (e.g. "01234")
    add_cand(plu)
    # Priority 3: PLU without leading zeros (e.g. "1234")
    stripped = plu.lstrip("0")
    if stripped:
        add_cand(stripped)

    # If plu_len is 5, also generate 4-digit fallback candidates
    if plu_len == 5:
        plu4 = raw[2:6]
        add_cand(prefix + plu4)
        add_cand(plu4)
        stripped4 = plu4.lstrip("0")
        if stripped4:
            add_cand(stripped4)

    # Zero-padded 13-digit barcode (some catalogs register "2001234000000")
    if plu_len == 5:
        add_cand(f"{prefix}{plu}000000")

    return {
        "is_scale_barcode": True,
        "prefix": prefix,
        "plu": plu,
        "weight": weight,
        "candidates": candidates,
        "check_digit": check_digit,
    }


def scale_settings() -> dict:
    """Fetch scale barcode configuration from LumenPOS Settings or defaults."""
    defaults = {
        "enable_scale_barcodes": 1,
        "scale_barcode_prefixes": ",".join(DEFAULT_PREFIXES),
        "scale_barcode_plu_len": 5,
        "scale_barcode_weight_decimals": 3,
    }
    try:
        import frappe

        doc = frappe.get_cached_doc("LumenPOS Settings")
        enabled = doc.get("enable_scale_barcodes")
        if enabled is not None:
            defaults["enable_scale_barcodes"] = 1 if enabled else 0
        prefixes = doc.get("scale_barcode_prefixes")
        if prefixes:
            defaults["scale_barcode_prefixes"] = str(prefixes).strip()
        plu_len = doc.get("scale_barcode_plu_len")
        if plu_len:
            defaults["scale_barcode_plu_len"] = int(plu_len)
        weight_decimals = doc.get("scale_barcode_weight_decimals")
        if weight_decimals is not None:
            defaults["scale_barcode_weight_decimals"] = int(weight_decimals)
    except Exception:
        pass
    return defaults
