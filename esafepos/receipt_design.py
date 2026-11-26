# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
"""Validated, display-only receipt design, also used by outlet overrides."""
import json
import math

RANGES = {
    "fontSize": [
        9,
        16
    ],
    "totalSize": [
        12,
        24
    ],
    "lineHeight": [
        1,
        2
    ],
    "paddingTop": [
        0,
        10
    ],
    "paddingRight": [
        0,
        10
    ],
    "paddingBottom": [
        0,
        10
    ],
    "paddingLeft": [
        0,
        10
    ],
    "sectionGap": [
        0,
        10
    ],
    "itemPadding": [
        0,
        3
    ],
    "logoHeight": [
        16,
        100
    ],
    "barcodeHeight": [
        20,
        80
    ],
    "borderWidth": [
        0,
        2
    ]
}
ALIGNMENTS = ["headerAlign","footerAlign","itemAlign","labelAlign","valueAlign"]

def clean_receipt_design(value):
    if isinstance(value, str):
        if len(value) > 8192:
            raise ValueError("Receipt design is too large.")
        value = json.loads(value or "{}")
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError("Invalid receipt design.")
    result = {}
    for key, item in value.items():
        if key in ALIGNMENTS:
            if item not in ("left", "center", "right"):
                raise ValueError("Choose a valid receipt alignment.")
        else:
            limits = RANGES.get(key)
            if not limits or isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) or not limits[0] <= item <= limits[1]:
                raise ValueError("Receipt design value is outside its allowed range: " + key)
        result[key] = item
    return result
