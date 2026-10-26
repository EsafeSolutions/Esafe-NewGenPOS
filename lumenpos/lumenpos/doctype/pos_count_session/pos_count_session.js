// Copyright (c) 2026 Lumen Solutions
// SPDX-License-Identifier: AGPL-3.0-only
// "LumenPOS" is a trademark of Lumen Solutions. See TRADEMARKS.md.
//
// A shared count in the desk: every phone, every item, each phone's quantity,
// the total and the quantity on the shelf. Loaded only when the form is opened
// or refreshed, so it costs nothing while the phones count.
frappe.ui.form.on("POS Count Session", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Refresh"), () => lumenpos_render_count(frm));
		frm.add_custom_button(__("Export to Excel"), () => {
			window.open(
				"/api/method/lumenpos.api.stock_app.count_session_export?session=" + encodeURIComponent(frm.doc.name)
			);
		});
		lumenpos_render_count(frm);
	},
});

function lumenpos_render_count(frm) {
	const $wrap = frm.get_field("progress_html").$wrapper;
	$wrap.html(`<div class="text-muted">${__("Loading...")}</div>`);
	frappe
		.call({ method: "lumenpos.api.stock_app.count_session_lines", args: { session: frm.doc.name } })
		.then((r) => {
			const d = r.message || {};
			const esc = frappe.utils.escape_html;
			const fmt = (v) => (v === null || v === undefined || v === "" ? "" : format_number(v, null, 0));
			const devices = d.devices || [];
			const items = d.items || [];
			const showSystem = !d.blind;
			let units = 0;
			items.forEach((it) => (units += it.total || 0));

			let html = `<div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:12px">
				<div><div class="text-muted small">${__("Devices")}</div><div class="h4">${devices.length}</div></div>
				<div><div class="text-muted small">${__("Items")}</div><div class="h4">${items.length}</div></div>
				<div><div class="text-muted small">${__("Units")}</div><div class="h4">${fmt(units)}</div></div>
				<div><div class="text-muted small">${__("Type")}</div><div class="h4">${d.full_count ? __("Full count") : __("Partial count")}</div></div>
			</div>`;

			html += `<table class="table table-bordered table-sm"><thead><tr>
				<th>${__("Device")}</th><th>${__("Counted By")}</th><th class="text-right">${__("Lines")}</th>
				<th class="text-right">${__("Units")}</th><th>${__("Last Sync")}</th></tr></thead><tbody>`;
			devices.forEach((dv) => {
				html += `<tr><td>${esc(dv.device_label || dv.device_id)}</td><td>${esc(dv.counted_by_name || "")}</td>
					<td class="text-right">${fmt(dv.lines)}</td><td class="text-right">${fmt(dv.units)}</td>
					<td>${esc((dv.last_sync || "").substring(0, 16))}</td></tr>`;
			});
			if (!devices.length) html += `<tr><td colspan="5" class="text-muted">${__("No phone has sent a count yet")}</td></tr>`;
			html += `</tbody></table>`;

			html += `<input type="text" class="form-control input-sm lumenpos-filter" placeholder="${__("Search items")}" style="margin:8px 0">`;
			html += `<div style="overflow-x:auto"><table class="table table-bordered table-sm lumenpos-items"><thead><tr><th>${__("Item")}</th>`;
			devices.forEach((dv) => (html += `<th class="text-right">${esc(dv.device_label || dv.device_id)}</th>`));
			html += `<th class="text-right">${__("Total")}</th>`;
			if (showSystem) html += `<th class="text-right">${__("On the shelf")}</th><th class="text-right">${__("Difference")}</th>`;
			html += `</tr></thead><tbody>`;
			items.forEach((it) => {
				const diff = (it.total || 0) - (it.system_qty || 0);
				const cls = !showSystem || diff === 0 ? "" : diff > 0 ? "text-primary" : "text-danger";
				html += `<tr data-q="${esc(((it.item_code || "") + " " + (it.item_name || "")).toLowerCase())}">
					<td>${esc(it.item_name || it.item_code)}<div class="text-muted small">${esc(it.item_code)}</div></td>`;
				devices.forEach((dv) => (html += `<td class="text-right">${fmt((it.by_device || {})[dv.device_id])}</td>`));
				html += `<td class="text-right"><b>${fmt(it.total)}</b></td>`;
				if (showSystem) html += `<td class="text-right">${fmt(it.system_qty)}</td><td class="text-right ${cls}">${fmt(diff)}</td>`;
				html += `</tr>`;
			});
			html += `</tbody></table></div>`;
			$wrap.html(html);
			$wrap.find(".lumenpos-filter").on("input", function () {
				const q = ($(this).val() || "").toLowerCase();
				$wrap.find(".lumenpos-items tbody tr").each(function () {
					$(this).toggle(!q || ($(this).attr("data-q") || "").includes(q));
				});
			});
		});
}
