# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "ESAFEPOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
"""The languages the till speaks, and which of them a shop offers.

A language is shipped when EsafePOS carries its server translations
(translations/<code>.csv, the file Frappe itself reads on v13 to v16); the
till's own texts for it sit in frontend/src/locales. The code is the ERPNext
Language code, so the till sends it as Frappe's `_lang` and every message,
EsafePOS's and ERPNext's, comes back in the language on the screen.

`till_languages` on EsafePOS Settings narrows the list, one code per line.
Empty means every shipped language, including ones a later release adds.
English is always offered: it is what a missing text falls back to."""

import os

import frappe


def shipped():
    """English, then every language EsafePOS carries translations for."""
    folder = frappe.get_app_path("esafepos", "translations")
    codes = []
    if os.path.isdir(folder):
        codes = sorted(name[:-4] for name in os.listdir(folder) if name.endswith(".csv"))
    return ["en"] + [code for code in codes if code != "en"]


def parse(value):
    """Codes from the stored text (or a list), known ones only, in order, no repeats."""
    if isinstance(value, str):
        value = value.replace(",", "\n").split("\n")
    known = set(shipped())
    out = []
    for code in value or []:
        code = str(code or "").strip()
        if code in known and code not in out:
            out.append(code)
    return out


def offered(doc=None):
    """The shop's choice as a list; [] = every shipped language."""
    doc = doc or frappe.get_cached_doc("EsafePOS Settings")
    codes = parse(doc.get("till_languages") or "")
    if not codes or set(shipped()) <= set(codes) | {"en"}:
        return []
    return ["en"] + [code for code in codes if code != "en"]


def store(value):
    """What save_settings writes: every language ticked is stored as empty, so a
    language added by a later release is offered without anyone ticking it."""
    codes = parse(value)
    if not codes or set(shipped()) <= set(codes) | {"en"}:
        return ""
    return "\n".join(["en"] + [code for code in codes if code != "en"])
