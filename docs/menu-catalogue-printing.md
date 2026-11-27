# Menu and catalogue printing

Open **Printing → Menu & catalogue**. This is independent of the Labels feature switch. Access uses the existing **Print labels** capability plus native **Item read** permission and the selected outlet's access scope. Reports-only sessions do not show the selling catalogue tab. The new `print_catalogue` bootstrap flag supplies the combined permission; the endpoint checks it again on every page.

1. Choose the outlet. The tab loads **all permitted active selling items**, including out-of-stock items and services. Disabled items, variant templates, purchase-only items, internal gift-card/deposit placeholders and items outside the outlet's configured item groups are excluded. Native Item user permissions remain enforced.
2. Keep all categories/brands selected for a complete catalogue, or choose filters/search. Choose **Product catalogue** or **Compact menu**, A4 or Letter, and **Category, then brand** or **Brand, then category**.
3. Set the document title and choose whether images, full descriptions and discount/offer details should appear. The displayed selling price always stays the resolved price; hiding offer details does not recalculate it.
4. Click **Prepare complete document**. It includes every selected item in one paginated document. Long descriptions continue on the next page, with the product identified again. Images are embedded in colour; missing/unavailable images use an explicit placeholder and a visible warning.
5. **Print catalogue** opens the browser print dialog for all prepared pages. Choose the same A4/Letter paper, no extra browser margins/headers/footers and appropriate scaling. **Export one PDF** saves every page in a single file, not one file per item/category.

Refreshing, switching outlets or changing a filter/design invalidates the prepared document. A cancelled, failed or incomplete item load cannot be prepared or exported. A prepared snapshot can still be exported/printed offline because its images and document are already embedded. Refresh all items online when prices, rules or products have changed.

## Prices and automatic discounts

Prices are for **one stock unit**, using the outlet's default customer context and current selling list/customer-list fallback/price books. The document names its outlet, price list and the last data-check time. It never uses manually edited cart prices or creates a sale to calculate a catalogue.

- With normal EsafePOS pricing, the existing Python promotion engine evaluates each product individually at quantity one. It retains priority/stacking, price basis, dates/time windows, item/group/brand/tag targeting and customer-group eligibility. Coupon-locked promotions are not loaded. Related offers that do not apply at one unit are labelled **conditions apply** rather than deducted as a guaranteed unit discount.
- With **ERPNext automatic pricing rules** enabled, the native single-item rule resolver supplies the quantity-one price in the outlet's company, warehouse, customer, price-list, date and invoice-type context. Rate, margin, percentage and flat discounts are handled without stacking the EsafePOS engine a second time. The implementation uses ERPNext's [native rule resolver](https://github.com/frappe/erpnext/blob/version-15/erpnext/accounts/doctype/pricing_rule/pricing_rule.py#L405); actual site/version qualification remains necessary. Rules requiring a different quantity, basket, coupon or document context can change the checkout result.
- Configured item-tax factors reuse the existing label-tax helper. Fixed transaction-level charges are excluded. The explanatory note is printed on the document. A catalogue is a dated pricing snapshot, not a guaranteed future checkout quote.
- Regular prices can be shown struck through with a calculated saving. Currency display follows standard currency precision (including JPY and KWD), with a two-decimal fallback for custom currency codes. Very small savings use an amount rather than a misleading `0% off`. Unpriced items say **Price on request**; a legitimately free promotion stays distinct from a missing price.

No invoice, payment, stock movement, price-list edit, rule change, printer assignment or cash-drawer job is created. The normal sale calculation and promotion parity files are unchanged.

## Images and PDF behavior

Images load in the browser with same-origin credentials only. External HTTPS images require their host's CORS permission; the server does not fetch arbitrary image URLs. Assets are decoded, resized and embedded so the print/PDF document has no external image dependency. HTTP external URLs and unsupported/oversized assets become reported placeholders. Existing item descriptions are converted to plain text; scripts/styles are omitted and all generated document text is escaped.

The preview and browser print use SVG pages. The PDF embeds full-colour 180 DPI page images, preserving the browser's Unicode shaping and exact pagination. PDF text is rasterized rather than searchable/selectable. Desktop Chrome/Edge can choose a file and write pages progressively into that single PDF; cancellation/errors abort the writable stream. Other browsers use a regular download, with an explicit 150 MB memory-buffer limit. For a larger complete document, use direct file saving or browser Print to PDF; no truncated PDF is exported.

## Components and deployment

- `api/print_catalogue.py`: read-only, permission-aware 200-item keyset pages, outlet/group restrictions, price resolution, tax factors, promotion/native-rule evaluation and safe descriptions.
- `PrintCatalogueView.vue`: complete-load state, outlet/filter/layout controls, image warnings, preparation and explicit print/PDF actions. Existing default Printing tabs and legacy links are preserved.
- `catalogue/document.js`: category/brand ordering, readable page layout, full descriptions, continuations and currency-aware price rendering.
- `catalogue/output.js`: safe asset preparation, self-contained browser print, colour PDF generation and bounded-memory file streaming.
- `session.py`, `PrintingView.vue`, `NavRail.vue` and screen help: permission flag, tab/navigation and instructions.

Deploy the backend and rebuilt POS assets together, then refresh the app. **No DocType/schema migration or new package dependency is introduced by this feature.** No live ERPNext catalogue, physical print or production deployment was performed during development.

## Verification

- `python scripts/test_print_catalogue.py`: 12 standalone tests covering permission/outlet guards, 431 items across keyset pages, item/group restrictions, description sanitization, real promotion-engine behavior, coupon/expiry exclusion, missing/free prices, tax/reference prices and native-rule context/discount/margin handling with native I/O mocked.
- `cd frontend && node catalogue-check.mjs`: 235 synthetic items loaded over three API pages, one **50-page colour PDF**, complete identifiers/descriptions, long-description continuation, images/placeholders, grouping/filter invalidation, A4/Letter, browser printing, partial-load failure, denied access, Unicode, currency precision, tiny savings and identical streamed/downloaded PDF bytes. No physical print.
- Existing `node printing-check.mjs` passed for legacy navigation, receipt/outlet saves and printer permission flows.
- PDF structure/page counts/DeviceRGB/A4/Letter bounds checked with pypdf; first, last, menu and long-description pages rendered with Poppler and visually inspected. Production build, Python 3.7 grammar and whitespace checks passed.

Evidence: [desktop](screenshots/catalogue/desktop.png), [mobile controls](screenshots/catalogue/mobile.png), [mobile preview](screenshots/catalogue/mobile-preview.png), [catalogue page](screenshots/catalogue/catalogue-page.png), [menu page](screenshots/catalogue/menu-page.png), [continued description](screenshots/catalogue/description-end.png), [complete 12-item synthetic catalogue](fixtures/catalogue/sample-catalogue.pdf), [12-item synthetic menu](fixtures/catalogue/sample-menu.pdf) and [test manifest](fixtures/catalogue/verification.json). The full 235-item PDF remains a local test artifact rather than real customer data.
