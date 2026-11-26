"""Read-only deployed release history. Update installation stays with the existing consent flow."""
import json
from pathlib import Path

import frappe


@frappe.whitelist()
def get_updates():
    from esafepos import __version__
    from esafepos.www.pos import _shell_revision

    path = Path(frappe.get_app_path("esafepos", "release_notes.json"))
    catalog = json.loads(path.read_text(encoding="utf-8"))
    return {"version": __version__, "revision": _shell_revision(__version__), "catalog": catalog}
