# Browser and silent receipt layout

Verified on 2026-11-26. The POS changes are built locally; deployment and physical printer qualification remain pending.

**2026-11-28 follow-up:** built-in receipt printing now defaults to automatic safe geometry and a POS-rendered fixed PDF. Old custom dimensions require explicit calibration opt-in; the manager no longer reflows built-in receipt HTML. [Current behavior and verification](receipt-right-edge-fit.md). The native measurements and HTML preview findings below remain historical evidence.

## Findings

The submitted HTML previously lost per-edge borders and `table-layout` during computed-style export. Browser receipts retained those rules. Amounts could wrap or clip in the fixed totals column. Native preview also removed the inline SVG invoice barcode. These are reproducible POS export defects, separate from paper feed.

The corrected paths share a dedicated receipt stylesheet and geometry. Exports preserve edge borders, fixed tables, local fonts, whole monetary values and branding. Rules print solid black. The barcode is an embedded vector image, without a screenshot or external asset dependency. The page is portrait with zero margins, fit scaling, and a measured content height plus a 1 mm allowance. Browser measurement waits for fonts and images. Accounting, receipt amounts, original/reprint identities, retries and drawer submission gates are unchanged.

The installed manager's Settings and executable both reported **0.2.2**. Its UI process and `--agent` child used the same installed executable; no older parallel agent was found. A newer sibling source package is not evidence of the running version. The POS uses the vendored **SDK 0.2.0**.

Read-only Windows measurements for **Xprinter XP-80(Copy 1)**:

| Setting | Observed value |
|---|---|
| Driver / port | Xprinter XP-80 / USB002 |
| Default Windows form | Custom 72 × 296.9 mm |
| Resolution / orientation | 203 × 203 DPI / portrait |
| Driver scaling | None |
| Printable and physical raster | 575 × 2373 pixels |
| Printable width / origin | Approximately 71.95 mm / zero offsets |

See [Windows measurements](fixtures/receipts/windows-measurements.json). An 80 mm physical roll does not imply an 80 mm Windows page or printable area. The manager advertises several supported forms, but the SDK does not identify the active Windows form or hardware printable area.

The inspected affected outlet currently selected **ESC/POS raw**. Raw uses a separate text/command renderer and cannot reproduce all HTML borders, fonts and layout. The photos alone do not identify which output path produced each receipt. Live settings were not changed.

## Long browser paper feed

The prepared document and Chrome PDF tests use a single page fitted to the receipt, including short receipts and receipts over one metre long. They do not contain a fixed 297 mm blank tail. Windows currently defaults to a 296.9 mm form, which can explain continued feed after a short browser receipt if that form is used. The browser print dialog and cutter settings were not verified: desktop inspection stopped when the user pressed Escape. No physical print was performed.

After deploying, use the same exact queue in both paths. Check the browser's selected paper, zero margins, portrait, headers/footers off and fit scaling. In Windows Printing preferences, check for a receipt/continuous-paper mode and cut-after-document setting supported by this driver. A long continuous form alone is not a guarantee of early cutting. CSS cannot force a driver to cut before the end of its selected form. If native preview is correct but paper output differs, investigate driver/media/scaling and the manager's spool path rather than changing invoice calculations.

## Receipt margin management

**Printing → Printers → Receipt paper and margins** now provides independent left, right, top and bottom margins from 0 to 20 mm. Left/right margins reduce the content width; top/bottom add whitespace to the measured page. At least 10 mm of content must remain. Start by matching the actual driver width, then increase the right margin if that edge clips. Older saved uniform insets become four equal margins without changing their spacing. Save still requires the existing Settings/POS Profile permission.

**Preview receipt margins** shows the actual prepared synthetic receipt with the current entries. **Browser margin test** opens its browser print dialog without saving or creating a transaction. **Reset margins to 3 mm** resets the draft only. Save after checking both edges. These controls apply to built-in HTML and browser receipts; ERPNext PDF and raw command layouts remain separate.

The [asymmetric-margin fixture](fixtures/receipts/80-Table-72-M3-7-1-6.html) uses left 3, right 7, top 1 and bottom 6 mm on a 72 mm page. Its [exact request](fixtures/receipts/80-Table-72-M3-7-1-6.request.json) and [native preview](screenshots/printing/after-80-Table-72-M3-7-1-6.png) demonstrate that all amounts fit. This is a test configuration, not a universal preset for every printer.

## Workstation setup

1. Under **Printing → Receipt**, choose the template and physical 58 mm or 80 mm roll for the applicable outlet.
2. Under **Printing → Printers**, assign the exact receipt queue. Choose **Built-in receipt (HTML)** to reproduce the built-in designer. ERPNext PDF uses its own Print Format; raw uses the existing command renderer.
3. Under **Receipt paper on this workstation**, select the physical roll and enter the Windows paper width, printable width and margins. For the inspected queue the paper width is 72 mm; printable width is approximately 71.95 mm (71.9 mm is a conservative entry). Start with 3 mm margins on each side. Do not apply a second driver margin. The synthetic fixture uses the nominal 72 mm width with a 3 mm inset, keeping all ink within the measured printable area.
4. Save the layout. Measurements are separate for 58/80 mm, browser/workstation, ERP origin, outlet and assigned queue. Saving the same queue preserves them; changing the receipt queue resets them. Existing Settings/POS Profile authorization protects the save. No Frappe schema migration is added.
5. Compare the browser receipt with the manager preview using identical HTML/options, then qualify one synthetic physical receipt and its cut. The setup's generic **Preview test** is a connection diagnostic, not the full receipt designer fixture below.

## Exact example and evidence

The [72 mm SDK request](fixtures/receipts/80-Table-72.request.json) contains the actual captured test request, including its base64 document. Its decoded document is [self-contained HTML](fixtures/receipts/80-Table-72.html). The corresponding [browser document](fixtures/receipts/80-Table-72.browser.html) and [one-page PDF](fixtures/receipts/80-Table-72.pdf) use the same geometry. The exact options are:

```json
{
  "copies": 1,
  "size": { "width": 72, "height": 195 },
  "margins": 0,
  "orientation": "portrait",
  "scale": "fit"
}
```

Height is measured per receipt, not a fixed setting. Dispatch remains `client.print({printerId, format: 'html', data, options, title, idempotencyKey})`; SDK wire serialization uses `dataBase64`. Preview validation calls `client.preview` with that identical document/options. [58 mm HTML](fixtures/receipts/58-Table-58.html), [request](fixtures/receipts/58-Table-58.request.json) and [PDF](fixtures/receipts/58-Table-58.pdf) are also included.

Evidence contains synthetic sales only. Compare [before native preview](screenshots/printing/before-80-Table-80.png), [corrected 80 mm preview](screenshots/printing/after-80-Table-80.png), [72 mm driver-width preview](screenshots/printing/after-80-Table-72.png) and [58 mm preview](screenshots/printing/after-58-Table-58.png). Browser/export metrics are recorded [before](fixtures/receipts/before-comparison.json) and [after](fixtures/receipts/after-comparison.json). Setup screenshots: [desktop](screenshots/printing/receipt-layout-desktop.png), [mobile](screenshots/printing/receipt-layout-mobile.png).

## Verification

- `node receipt-silent-check.mjs`: 17 synthetic cases across six templates, 58/80 mm and narrower driver forms. Checks equal borders, fonts, dimensions, complete monetary glyph bounds, footer, self-contained assets and exact SDK options. Actual SDK with a test-only transport; never physical printing.
- `node receipt-native-preview-check.mjs`: actual installed 0.2.2 executable and SDK, isolated data/IPC/TLS identity, baseline and corrected 58/80/72 mm documents, including an asymmetric-margin case. All six previews were one page. Zero native jobs; no printer output, drawer pulse or Windows trust changes. See [native results](fixtures/receipts/native-preview-result.json). Requires the installed manager/runtime and its development `ws` dependency; override `ESAFE_TEST_EXECUTABLE`, `ESAFE_TEST_RUNTIME_DIR` and `ESAFE_TEST_SOURCE` for another workstation.
- `node receipt-check.mjs`: existing browser receipt/PDF, offline reprint, cleanup and customer/history checks passed. PDF assertions verify a single page with no long blank tail. Requires Playwright/Chrome; set `PLAYWRIGHT_MODULE` and `CHROME_PATH` as needed.
- `node esafe-browser-check.mjs`: actual SDK authentication, setup permissions, width validation, per-roll/outlet/workstation isolation, desktop/mobile controls, automatic-original dedupe, reprints, PDF fallback and drawer gate checks passed with a test transport.
- `node esafe-check.mjs`, `node drawer-check.mjs`: orchestration, layout validation/storage, authorization and unchanged drawer/idempotency checks passed.
- `npm run build`: regenerated production POS assets. Physical paper feed, cut, scan quality and live deployment remain unverified.

See [right-edge protection and conservative initial widths](receipt-right-edge-fit.md) for the subsequent clipping fix.
