# Receipt sections and advanced design

Open **Printing → Receipt**. Choose **All outlets (default)** or a specific outlet before editing. The existing default/outlet save buttons apply all section switches and advanced design together. Setup requires the existing Settings and outlet permissions; changes require an ERP connection.

The **Hide/Show loyalty points section** button controls the earned/redeemed/balance summary. The matching **Loyalty points section** checkbox stays in sync. Hiding that summary does not remove loyalty money used as payment or saved change from the totals, and does not change points balances or calculations.

**Show all optional sections** and **Hide optional sections** control the display checkboxes together. Individual controls include loyalty, MRP, line/total discounts, gross total, savings, counts, customer details, date/time, header/phone/footer, tax breakdown, change, custom fields and the existing payment, barcode, address, terms and note switches. Invoice identity, item lines, net total and relevant credit/redemption accounting facts remain visible. Hiding optional sections does not change the transaction.

Expand **Advanced custom receipt editor** for:

- Header, footer, item-name, totals-label and amount alignment.
- Body/net-total font sizes and line height.
- Top/right/bottom/left design padding, section spacing and item-row padding.
- Border thickness, logo maximum height and invoice-barcode height.

Blank values use the selected template. **Reset advanced design** clears only the current design draft; save to apply it. The live preview uses the same built-in receipt renderer as browser and silent HTML receipts. Larger text or padding can wrap content; check the print preview and actual paper before using a changed design at a till.

Design padding belongs to the shared/outlet design and adds to the printer margins configured in **Printing → Printers → Receipt paper and margins**. For example, 3 mm workstation right margin plus 1 mm design right padding leaves 4 mm on that side. Print preparation rejects a combined horizontal space that leaves less than 10 mm for receipt content. Page height is measured after the design is applied, including top/bottom padding. Receipt-manager Print preview also uses the selected outlet's saved workstation geometry.

Layout editing applies to browser and silent **Built-in receipt (HTML)** output. Raw ESC/POS supports applicable section switches, including loyalty, prices, discounts and counts, but uses its own command layout. ERPNext PDF uses the selected ERPNext Print Format. The public e-invoice renderer is separate. No arbitrary HTML, CSS, script or network font is accepted by this editor.

## Deployment and storage

Run the normal site migration (`bench --site <site> migrate`) after deploying. New Check fields and the `receipt_design` JSON Code field belong to **EsafePOS Settings**. Existing receipt designs retain their template because unset design properties add no styling; newly introduced visibility switches default on. Outlet overrides keep the normalized design object in the existing profile receipt JSON. Global settings store it as validated JSON text. Existing workstation margin records remain separate. No new DocType or ledger is added.

## Verification

- `scripts/test_printing_settings.py`: 12 permission, persistence, partial-update and design validation checks.
- `scripts/test_receipt_design.py`: eight design/raw-rendering checks, including existing thermal regressions. Existing tests now account for wrapped footers and exclude raster barcode bytes from text-grid assertions; both failures were reproduced against HEAD before correction.
- `frontend/printing-check.mjs`: loyalty button, bulk visibility, required totals, invalid design rejection, save/override/reset workflow and desktop/mobile controls.
- `frontend/receipt-silent-check.mjs`: 18 exact browser/SDK document cases, including custom alignment, padding, font, border and hidden-section export.
- `frontend/receipt-native-preview-check.mjs`: seven one-page previews through installed Print Manager 0.2.2, including the custom document. Isolated data/identity, zero native jobs and no production trust changes.
- `frontend/esafe-browser-check.mjs`: actual SDK with a test transport, dispatch/idempotency, margin calibration and drawer submission checks.
- Production bundle build, Python 3.7 grammar, JSON and whitespace checks. No live ERPNext save, physical printer output or deployment was performed.

Evidence: [desktop editor](screenshots/printing/advanced-editor-desktop.png), [mobile editor](screenshots/printing/advanced-editor-mobile.png), [custom native preview](screenshots/printing/after-80-Table-72-CUSTOM.png), [self-contained HTML](fixtures/receipts/80-Table-72-CUSTOM.html), [exact SDK request](fixtures/receipts/80-Table-72-CUSTOM.request.json), [PDF](fixtures/receipts/80-Table-72-CUSTOM.pdf), [layout metrics](fixtures/receipts/advanced-comparison.json) and [native results](fixtures/receipts/advanced-native-preview-result.json).

See [right-edge protection and conservative initial widths](receipt-right-edge-fit.md) for the subsequent clipping fix.
