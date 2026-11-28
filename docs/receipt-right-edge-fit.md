# Right-edge receipt clipping

The photographed failure cuts several unrelated fields at the same right edge: invoice identifier, customer code, amounts, net total and quantity. This is consistent with a document wider than the usable printer area. It is not evidence of incorrect sale amounts. The photograph alone cannot identify the deployed build, output path, selected queue or current driver form.

## Current behavior

**Automatic safe fitting is now the default for existing and new workstations.** Built-in receipts use a **72 mm page for an 80 mm roll**, or **48 mm for a 58 mm roll**, with 3 mm margins. Older saved widths/margins are ignored at preparation time unless the operator explicitly enabled **Use calibrated measurements (advanced)**. The saved legacy record is retained rather than deleted. Automatic mode also caps extra horizontal design padding at 1 mm per side, fits normal company headings to one line where readable, and fits metadata labels before they break into letter fragments.

Automatic spacing uses a 1.2 line height, 1.5 mm section gaps and 0.35 mm item-cell padding, removes extra top/bottom designer padding, and tightens heading/contact/terms spacing. These defaults replace excessive legacy spacing in automatic mode; explicit calibrated mode retains the custom design spacing. Financial values and visible sections are unchanged.

Browser output and the fixed-PDF Esafe receipt share this preparation:

- Wraps long invoice/customer details, shop names, loyalty program names and footer text inside the content box.
- Keeps quantity numeric and wraps alternate units such as **150 kg Pack** separately. Automatic mode places unit text under the product name, using the full name width instead of a narrow quantity column. Previously the whole quantity/unit cell was forced onto one line and treated as an overflowing number, causing the photographed “Receipt content does not fit” error on otherwise valid receipts.
- Allocates item columns from measured heading and numeric widths while retaining the template proportions where space permits. If the columns cannot all remain readable at the minimum font size, prints labelled quantity/MRP/discount/amount details beneath the product instead of squeezing or clipping a five-column row. Headings follow the active receipt fields and translations.
- Reserves room for totals labels and their shared amount column, fitting oversized label text locally to avoid vertical fragments on narrow paper.
- Fits overflowing numeric values locally, retaining every digit on one line and the configured emphasis. It does not shrink the whole receipt image. Text is never reduced below 9 CSS pixels by this check.
- Checks actual text bounds, numeric cells, tables and images against the usable area after printer margins and design padding.
- Stops preparation with a useful setup error when the content still cannot fit. No browser print call or new native print job is sent for that attempt; the temporary frame is removed. Sale/payment/loyalty calculations and existing accepted intents remain unchanged.
- Measures page height after wrapping/fitting, including footer padding.

The geometry check cannot discover a driver secretly clipping a correctly prepared document. The SDK's supported-paper list is not the active Windows form or a hardware printable-area measurement. An explicit saved width can therefore still be wrong for the physical printer.

## Apply on an existing workstation

1. Deploy the app source and rebuilt POS assets together, then refresh each till. This update adds no schema or migration.
2. Keep the assigned receipt queue and the existing 58/80 mm receipt roll setting. **Built-in receipt (safe PDF)** uses the current designer; its persisted setting value remains `html` for compatibility. No manual width/margin tuning or clearing workstation storage is needed to activate the new default.
3. Automatic mode ignores unverified legacy dimensions and sends portrait, monochrome, single-sided, fit-to-page graphics settings. Each receipt is a single content-height PDF frozen at 203.2 DPI by the POS, including images, local fonts, Unicode, borders and every amount. The manager prints the PDF rather than laying out the HTML again. Rasterized PDF text is not searchable. Preparation has a 20-million-pixel/30,000-pixel height limit; an unusually long receipt stops before submission rather than exporting partial content.
4. **Silent test receipt** and **Preview test** use the same fixed-PDF path. No sale or drawer pulse is included. Browser print uses the shared safe layout; the browser dialog still chooses its printer/form and should use zero extra margins and fit scaling.
5. Only an operator who has verified unusual printer measurements should enable **Use calibrated measurements (advanced)** and save custom widths/margins. These remain separate for each queue, outlet, workstation and roll. ERPNext Print Format PDF and raw ESC/POS retain their separate explicit layouts.

The layout is verified locally, including the actual PDF bytes generated before dispatch. It cannot identify a misconfigured physical printer, wrong roll, driver fault or an older deployed POS/manager. No live configuration was saved, no physical output was sent and no production deployment was made.

## Verification and synthetic evidence

- `node receipt-silent-check.mjs`: 35 browser/actual-SDK export cases across both rolls and six templates. Includes long unbroken customer/program names, safe defaults, large fonts/totals, custom margins/design and full-width calibrated printers, plus **150 kg Pack** on Table/Retail at both roll sizes and four long-unit/large-number reflow cases. Adds four automatic-mode cases that start with old full-width pages, shifted 12 mm left margins and oversized design padding/fonts, then verify safe defaults and a one-line normal shop heading. Checks complete unit names/amounts, prepared HTML geometry, fixed-PDF requests and page dimensions. An impossible layout is still rejected both by browser preparation and direct `nativeReceipt`, before native dispatch and with frame cleanup.
- Historical HTML-path qualification (2026-11-26): `node receipt-native-preview-check.mjs` produced ten isolated one-page native previews on installed Print Manager 0.2.2, including the 72 mm default, 48 mm large-total case and long metadata. Zero jobs, drawer pulses or production trust changes.
- `esafe-browser-check.mjs`, `esafe-check.mjs` and `drawer-check.mjs` passed for fixed-PDF submission, setup permissions, calibration opt-in, original/reprint deduplication and drawer gates. The added automatic-mode save/screenshots and final compact-spacing visual reruns remain pending: automatic approval review hit a usage limit. The broader `receipt-check.mjs` rerun first timed out during unrelated workspace hot reload; its fixture now disables HMR, but that rerun was also blocked by the review limit. Earlier browser receipt regressions remain recorded as historical verification.
- Production build and whitespace checks passed. Physical output remains to be qualified with the deployed build and actual driver.

Evidence: [72 mm starting layout](screenshots/printing/fit-80-Table-80-SAFE.png), [48 mm large-total fit](screenshots/printing/fit-58-Table-58-CUSTOM-SAFE.png), [long customer/program fields](screenshots/printing/fit-80-Retail-80-SAFE-LONG.png), [exact 72 mm SDK request](fixtures/receipts/80-Table-80-SAFE.request.json), [HTML](fixtures/receipts/80-Table-80-SAFE.html), [layout metrics](fixtures/receipts/right-edge-comparison.json), [native results](fixtures/receipts/right-edge-native-preview-result.json), [desktop controls](screenshots/printing/receipt-layout-desktop.png) and [mobile controls](screenshots/printing/receipt-layout-mobile.png).

Pack-unit/reflow evidence (synthetic receipts): [80 mm pack unit](screenshots/printing/receipt-pack/pack-80.png), [58 mm pack unit](screenshots/printing/receipt-pack/pack-58.png), [large-number reflow](screenshots/printing/receipt-pack/reflow-58.png), [desktop](screenshots/printing/receipt-pack/desktop.png), [mobile](screenshots/printing/receipt-pack/mobile.png), [current metrics](fixtures/receipts/pack-unit-fit.json).

Automatic default evidence, captured before the compact-spacing follow-up: [80 mm fixed receipt](screenshots/printing/receipt-default/receipt-80.png), [58 mm fixed receipt](screenshots/printing/receipt-default/receipt-58.png), [advanced desktop controls](screenshots/printing/receipt-default/advanced-desktop.png), [advanced mobile controls](screenshots/printing/receipt-default/advanced-mobile.png), [verification](fixtures/receipts/automatic-default-fit.json). All 35 generated PDFs have one fitted page; all four automatic-mode PDFs retain white side borders around the ink. The installed-manager preview above predates this fixed-PDF update; native physical output and final spacing visuals remain unverified.
