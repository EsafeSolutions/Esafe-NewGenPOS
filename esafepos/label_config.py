# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
"""Bounded, declarative label configuration. No Frappe dependency."""
import json
import math

MAX_LABELS = 10000
KINDS = ("Stock", "Design", "Printer", "Defaults")


def number(value, minimum, maximum, label):
    if isinstance(value, bool):
        raise ValueError("Invalid " + label)
    try:
        result = float(value)
    except (ValueError, TypeError):
        raise ValueError("Invalid " + label)
    if not math.isfinite(result) or result < minimum or result > maximum:
        raise ValueError("Invalid " + label)
    return result


def validate_configuration(config):
    if isinstance(config, str):
        if len(config) > 100000:
            raise ValueError("Label configuration is too large")
        config = json.loads(config)
    if not isinstance(config, dict) or len(json.dumps(config, allow_nan=False)) > 100000:
        raise ValueError("Invalid label configuration")
    for key in ("stock", "design", "printer"):
        if key in config and not isinstance(config[key], dict):
            raise ValueError("Invalid " + key + " configuration")
    stock = config.get("stock", {})
    if stock:
        for key in ("w", "h", "pageW", "pageH"):
            number(stock.get(key), 1, 2000, key)
        for key in ("columns", "rows"):
            n = number(stock.get(key), 1, 100, key)
            if n != int(n):
                raise ValueError("Rows and columns must be integers")
        for key in ("left", "right", "top", "bottom", "gapX", "gapY"):
            number(stock.get(key, 0), 0, 500, key)
        if stock.get("kind") not in ("roll", "sheet", "continuous", "black-mark"):
            raise ValueError("Invalid stock kind")
        used = float(stock["left"]) + float(stock["right"]) + float(stock["columns"]) * float(stock["w"]) + (float(stock["columns"]) - 1) * float(stock["gapX"])
        if (stock["kind"] == "sheet" or not stock.get("autoWidth")) and used > float(stock["pageW"]) + 0.0001:
            raise ValueError("Labels exceed the page width")
        if stock["kind"] == "sheet":
            height = float(stock["top"]) + float(stock["bottom"]) + float(stock["rows"]) * float(stock["h"]) + (float(stock["rows"]) - 1) * float(stock["gapY"])
            if height > float(stock["pageH"]) + 0.0001:
                raise ValueError("Labels exceed the sheet height")
    design = config.get("design", {})
    if design:
        number(design.get("scale", 100), 10, 300, "design scale")
        number(design.get("padding", 1.2), 0, 100, "padding")
        number(design.get("module", 0.33), 0.1, 2, "barcode width")
        if design.get("barcodeFormat", "AUTO") not in ("AUTO", "CODE128", "CODE93", "EAN13", "UPCA", "DATAMATRIX", "QRCODE"):
            raise ValueError("Unsupported barcode format")
        if "autoFit" in design and not isinstance(design["autoFit"], bool):
            raise ValueError("Barcode fitting must be enabled or disabled")
        elements = design.get("elements", [])
        if not isinstance(elements, list) or len(elements) > 80:
            raise ValueError("Use at most 80 design elements")
        for element in elements:
            if not isinstance(element, dict) or element.get("type") not in ("text", "static", "barcode", "qr", "image", "line", "box"):
                raise ValueError("Unsupported design element")
            for key in ("x", "y", "w", "h"):
                number(element.get(key), 0 if key in ("x", "y") else 0.01, 100, key)
            if float(element["x"]) + float(element["w"]) > 100.0001 or float(element["y"]) + float(element["h"]) > 100.0001:
                raise ValueError("A design element exceeds the label bounds")
            if element.get("rotation", 0) not in (0, 90, 180, 270):
                raise ValueError("Unsupported rotation")
    printer = config.get("printer", {})
    if printer:
        number(printer.get("dpi", 203.2), 100, 1200, "resolution")
        number(printer.get("maxWidth", 108), 1, 2000, "printer width")
        for key in ("offsetX", "offsetY"):
            number(printer.get(key, 0), -50, 50, key)
        for key in ("scaleX", "scaleY"):
            number(printer.get(key, 100), 90, 110, key)
        if printer.get("route", "browser") not in ("browser", "esafe"):
            raise ValueError("Unsupported output route")
    return config
