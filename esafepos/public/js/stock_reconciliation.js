// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
// "ESAFEPOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
//
// Before a stock count is submitted in the desk (0.68.0, esafepos.api.stock_app):
// the items still held by POS sales whose shift is not closed yet (closing it
// after the count would take them off again), and, for a count made with the
// Lumen Stock app, the counted items that moved after they were counted. One
// call, only on a draft.
frappe.ui.form.on("Stock Reconciliation", {
	refresh(frm) {
		frm.__esafepos_check = null;
		if (frm.is_new() || frm.doc.docstatus !== 0) return;
		esafepos_count_check(frm).then((r) => {
			if (r.unposted.length) {
				frm.dashboard.set_headline_alert(
					__("{0} items of this count are in sales of a shift not closed yet. Close the shift before submitting.", [r.unposted.length]),
					"red"
				);
			} else if (r.items.length) {
				frm.dashboard.set_headline_alert(
					__("{0} counted items moved after they were counted. Check them before submitting.", [r.items.length]),
					"orange"
				);
			}
		});
	},
	before_submit(frm) {
		return esafepos_count_check(frm, true).then(
			(r) =>
				new Promise((resolve) => {
					if (!r.unposted.length && !r.items.length) return resolve();
					frappe.confirm(
						esafepos_count_html(r),
						() => resolve(),
						() => {
							frappe.validated = false;
							resolve();
						}
					);
				})
		);
	},
});

function esafepos_count_check(frm, fresh) {
	if (frm.__esafepos_check && !fresh) return Promise.resolve(frm.__esafepos_check);
	const connector = !!(frappe.boot.versions || {}).lumen_connector;
	return frappe
		.call({ method: "esafepos.api.stock_app.stock_count_moved", args: { reconciliation: frm.doc.name }, freeze: !!fresh })
		.then((r) => {
			const m = r.message || {};
			// With the Lumen Connector installed too, its own script lists the moved items.
			frm.__esafepos_check = { unposted: m.unposted || [], items: connector ? [] : m.items || [] };
			return frm.__esafepos_check;
		})
		.catch(() => ({ unposted: [], items: [] }));
}

function esafepos_count_html(r) {
	const esc = frappe.utils.escape_html;
	const fmt = (v) => format_number(v, null, 0);
	let html = "";
	if (r.unposted.length) {
		html += `<p>${__("These items are in sales of a shift that is not closed yet. Their stock moves only when the shift is closed, so closing it after this count would take them off again. Close the shift first.")}</p>`;
		html += `<table class="table table-bordered table-sm"><thead><tr><th>${__("Item")}</th><th>${__("Warehouse")}</th><th class="text-right">${__("Qty")}</th><th>${__("POS Invoice")}</th></tr></thead><tbody>`;
		r.unposted.slice(0, 30).forEach((u) => {
			html += `<tr><td>${esc(u.item_code)}</td><td>${esc(u.warehouse)}</td><td class="text-right">${fmt(u.qty)}</td><td class="small">${(u.invoices || []).slice(0, 5).map(esc).join("<br>")}</td></tr>`;
		});
		html += `</tbody></table>`;
	}
	if (r.items.length) {
		html += `<p>${__("These items moved after they were counted. Submitting sets them to the counted quantity and overwrites the movements below.")}</p>`;
		html += `<table class="table table-bordered table-sm"><thead><tr><th>${__("Item")}</th><th class="text-right">${__("Counted")}</th><th class="text-right">${__("Moved")}</th><th>${__("Movements")}</th></tr></thead><tbody>`;
		r.items.slice(0, 30).forEach((it) => {
			const v = (it.vouchers || []).map((x) => `${esc(x.voucher_no)} (${fmt(x.qty)}, ${esc(x.posting_datetime)})`).join("<br>");
			html += `<tr><td>${esc(it.item_name)}${it.in_reconciliation ? "" : `<div class="text-muted small">${__("Not in this count: it matched the system")}</div>`}</td>
				<td class="text-right">${fmt(it.counted)}</td><td class="text-right">${fmt(it.moved)}</td><td class="small">${v}</td></tr>`;
		});
		html += `</tbody></table>`;
		if (r.items.length > 30) html += `<p class="text-muted">${__("And {0} more.", [r.items.length - 30])}</p>`;
	}
	html += `<p><b>${__("Submit anyway?")}</b></p>`;
	return html;
}
