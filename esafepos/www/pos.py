# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
import hashlib
from functools import lru_cache
from pathlib import Path

import frappe

no_cache = 1


@lru_cache(maxsize=8)
def _hash_shell(files):
    digest = hashlib.sha256()
    for path, _mtime, _size in files:
        with path.open("rb") as asset:
            for block in iter(lambda: asset.read(65536), b""):
                digest.update(block)
    return digest.hexdigest()[:16]


def _shell_revision(version):
    folder = Path(frappe.get_app_path("esafepos", "public", "pos"))
    try:
        files = []
        for name in ("pos.js", "pos.css", "sw.js", "manifest.json"):
            path = folder / name
            stat = path.stat()
            files.append((path, stat.st_mtime_ns, stat.st_size))
        return version + "-" + _hash_shell(tuple(files))
    except OSError:
        return version


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/pos"
        raise frappe.Redirect
    context.csrf_token = frappe.sessions.get_csrf_token()
    # Keep the displayed release separate from the browser cache revision.
    from esafepos import __version__

    context.esafepos_version = __version__
    context.pos_shell_revision = _shell_revision(__version__)
    return context
