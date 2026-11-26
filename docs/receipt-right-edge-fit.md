# Right-edge receipt clipping

The photographed failure cuts several unrelated fields at the same right edge: invoice identifier, customer code, amounts, net total and quantity. This is consistent with a document wider than the usable printer area. It is not evidence of incorrect sale amounts. The photograph alone cannot identify the deployed build, output path, selected queue or current driver form.

## Current behavior

New, unconfigured built-in receipts use a **72 mm page/printable box for an 80 mm roll**, or **48 mm for a 58 mm roll**. These are conservative starting widths for common thermal heads. Previously an unconfigured receipt used the whole physical roll width. Explicit saved/calibrated widths are preserved, including full-width printers.

Before browser output or silent HTML dispatch, the common print preparation now:

- Wraps long invoice/customer details, shop names, loyalty program names and footer text inside the content box.
- Reserves room for totals labels and their shared amount column, fitting oversized label text locally to avoid vertical fragments on narrow paper.
- Fits overflowing numeric values locally, retaining every digit on one line and the configured emphasis. It does not shrink the whole receipt image. Text is never reduced below 9 CSS pixels by this check.
- Checks actual text bounds, numeric cells, tables and images against the usable area after printer margins and design padding.
- Stops preparation with a useful setup error when the content still cannot fit. No browser print call or new native print job is sent for that attempt; the temporary frame is removed. Sale/payment/loyalty calculations and existing accepted intents remain unchanged.
- Measures page height after wrapping/fitting, including footer padding.

The geometry check cannot discover a driver secretly clipping a correctly prepared document. The SDK's supported-paper list is not the active Windows form or a hardware printable-area measurement. An explicit saved width can therefore still be wrong for the physical printer.

## Apply on an existing workstation

1. Deploy/rebuild the POS and refresh it. If deploying the preceding advanced receipt settings too, run the normal site migration.
2. Select the correct outlet and receipt queue in **Printing → Printers**. Use **Built-in receipt (HTML)** for the built-in designer. Raw ESC/POS and ERPNext PDF use separate layouts.
3. Under **Receipt paper and margins**, select the physical roll and click **Use safe thermal layout**. This changes the draft only. For the previously inspected Xprinter queue on USB002, Windows reported a 72 mm form and approximately 71.95 mm printable width at 203 DPI. The 72 mm starting layout with 3 mm margins keeps the ink within that measured width.
4. Match the actual Windows form and printable width, preview and print the synthetic browser margin test, then **Save workstation receipt layout**. Check the rightmost digits, both borders, invoice/customer identifiers and footer on paper. A verified printer with a wider usable area can retain or save its actual widths.
5. Choose the same exact queue/form in the browser dialog, zero browser margins and the appropriate fit setting. If the prepared PDF/native preview is complete but paper is clipped, check that queue's driver/form/scaling and the native spool path. Do not modify the invoice amount to make it fit.

This change is built locally. No live configuration was saved, no physical print was performed and no production deployment was made. The user was asked which output path produced the photo and whether the latest build was deployed; neither is assumed here.

## Verification and synthetic evidence

- `node receipt-silent-check.mjs`: 23 browser/actual-SDK export cases across both rolls and six templates. Includes long unbroken customer/program names, safe defaults, large fonts/totals, custom margins/design and full-width calibrated printers. An impossible layout is rejected both by browser preparation and direct `nativeReceipt`, before native dispatch and with frame cleanup.
- `node receipt-native-preview-check.mjs`: ten isolated one-page native previews on installed Print Manager 0.2.2, including the 72 mm default, 48 mm large-total case and long metadata. Zero jobs, drawer pulses or production trust changes.
- Existing `receipt-check.mjs`, `esafe-browser-check.mjs` and `esafe-check.mjs` passed: fitted PDF lengths, RTL, Unicode, offline/browser actions, printer/outlet isolation, idempotency and drawer submission gates.
- Production build and whitespace checks passed. Physical output remains to be qualified with the deployed build and actual driver.

Evidence: [72 mm starting layout](screenshots/printing/fit-80-Table-80-SAFE.png), [48 mm large-total fit](screenshots/printing/fit-58-Table-58-CUSTOM-SAFE.png), [long customer/program fields](screenshots/printing/fit-80-Retail-80-SAFE-LONG.png), [exact 72 mm SDK request](fixtures/receipts/80-Table-80-SAFE.request.json), [HTML](fixtures/receipts/80-Table-80-SAFE.html), [layout metrics](fixtures/receipts/right-edge-comparison.json), [native results](fixtures/receipts/right-edge-native-preview-result.json), [desktop controls](screenshots/printing/receipt-layout-desktop.png) and [mobile controls](screenshots/printing/receipt-layout-mobile.png).
