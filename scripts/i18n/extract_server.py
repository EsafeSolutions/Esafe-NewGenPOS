# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
"""Every string Frappe itself considers translatable in EsafePOS (DocType
labels, options and descriptions, Python _() calls), the way Frappe's own
get-untranslated lists them. Run with a site connected (frappe.init and
frappe.connect done, e.g. through the test benches' run-py16.sh); writes
/tmp/lumenpos_msgs.json, which prep.mjs reads as <work>/lumenpos_msgs.json."""

import json
from pathlib import Path

from frappe.translate import get_messages_for_app

rows = []
for row in get_messages_for_app("lumenpos"):
    # (path, message, context, line) on v15+, shorter tuples before: a third
    # item that is not text is a line number, not a context.
    context = row[2] if len(row) > 2 and isinstance(row[2], str) else ""
    rows.append({"path": row[0] or "", "message": row[1], "context": context or ""})
Path("/tmp/lumenpos_msgs.json").write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
print("strings", len(rows))
