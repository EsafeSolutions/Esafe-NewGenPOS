// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
// "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
//
// One phone's lines as a table instead of raw JSON, from data the form has.
frappe.ui.form.on("POS Count Device", {
	refresh(frm) {
		let lines = {};
		try {
			lines = JSON.parse(frm.doc.data || "{}") || {};
		} catch (e) {
			lines = {};
		}
		const esc = frappe.utils.escape_html;
		const codes = Object.keys(lines).sort();
		let html = `<table class="table table-bordered table-sm"><thead><tr><th>${__("Item")}</th>
			<th class="text-right">${__("Qty")}</th><th>${__("Serial Numbers")}</th></tr></thead><tbody>`;
		codes.forEach((code) => {
			const v = lines[code] || {};
			html += `<tr><td>${esc(code)}</td><td class="text-right">${format_number(v.q || 0, null, 0)}</td>
				<td>${esc((v.s || []).join(", "))}</td></tr>`;
		});
		if (!codes.length) html += `<tr><td colspan="3" class="text-muted">${__("No lines")}</td></tr>`;
		html += `</tbody></table>`;
		frm.get_field("lines_html").$wrapper.html(html);
	},
});
