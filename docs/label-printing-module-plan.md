# Label Printing Module Plan

**Status:** Core module implemented in the repository. The original roadmap below also describes later integrations; it is not a claim that every proposed capability has shipped.

**Planning date:** 2026-11-20.

**Priority confirmed by the user:** Thermal roll printers first.

**Scope:** Product, price, shelf, batch and stock labels under **Printing → Labels** (`/printing`), with thermal rolls prioritized and basic sheet/PDF output included. The former `/labels` route redirects to this section.

**Workspace update — 2026-11-22:** Printing now also hosts the receipt editor previously in General Settings and the outlet's network printer/Print Format setup. Label drafts, presets and calibration retain their existing permissions and data model. Receipt/printer configuration requires Settings write access, with POS Profile write access for printer changes; no separate manager/connector is integrated yet.

## Printing integration update — 2026-11-22

QZ Tray setup, receipt/label dispatch, signing endpoints and bundled connector have been removed. Labels use the browser print window, exact-size PDF or native command-file downloads. Existing connector profiles are normalized to the browser route, with connector-specific alignment reset so it can be measured again. Integration with the separately developed Print Manager is deferred; see the [Print Manager integration plan](print-manager-and-windows-bridge-plan.md). The original roadmap below is updated to follow that boundary.

## Implementation status — 2026-11-20

Implemented: single/double/triple/custom columns, custom mm/inch sizes, explicit gaps/margins, continuous/black-mark driver setups, A4/A5/Letter/Legal/custom sheets, skipped slots, 15 designs, logo selection/upload, independent font/design scaling, positioned elements with rotation and undo/redo, full-copy previews, device alignment, browser printing, exact-size raster PDF and ZPL/TSPL bitmap-file export. Shape choices are guides for existing stock, not die cuts. Encoders are EAN-13, UPC-A, Code 128 and UTF-8 QR.

Document sources preserve batch/serial details, including bundle entries where present. Fractional stock quantities round up with a review notice. Configured alternate selling units resolve their own price/barcode. Preparation reloads authorized current data, validates identifiers, records a bounded snapshot, and asks the operator to review changed names/prices before dispatch. Browser dialog return does not prove physical output, and uncertain results do not trigger replay.

Persistence uses **two** new DocTypes rather than the five proposed in section 11: `EsafePOS Label Preset` stores outlet-scoped Stock/Design/Printer/complete setups, and `EsafePOS Label Print Job` stores private snapshots/results. Shared saving is manager-only; device-local saving is also available. Alignment is keyed to physical stock/printer settings. Shared setups are explicitly selected; automatic company/outlet default inheritance is not implemented.

Later scope includes metadata-driven custom field discovery, automatic offer labels, full variant/warehouse integration, GS1/Data Matrix/additional linear formats, variable-weight generation, automatic shared defaults, history/range-reprint UI, and designer grouping/snapping/revision browsing. Native exports are files rather than automatic raw dispatch. Model-specific cutters, peelers and sensor commands remain outside the generic driver path.

Native files use raster graphics to preserve the scene across fonts and barcode implementations. ZPL graphic fields are split into bounded bands per the [Zebra graphic-field reference](https://docs.zebra.com/us/en/printers/software/zpl-pg/c-zpl-zpl-commands/r-zpl-gf.html); TSPL bitmap data follows the [TSC programming guide](https://fs.tscprinters.com/system/files/31-0000001-00_tspl_tspl2_programming_3_0.pdf). Actual firmware/media behavior still needs device testing.

Validation: production build, label geometry checks, barcode regression checks, 17 standalone Python configuration/permission/pricing tests, Python 3.7 grammar checks and mocked Chrome desktop/tablet/mobile/PDF/QZ checks. Independent ZXing decoding covers classic/left/right/rotated Code 128 and an isolated QR symbol. Real Frappe migration/pricing integration and physical printer/scanner calibration still require a site/device. Run `bench --site <site> migrate` before using shared presets and job APIs.

The existing receipt browser regression also passed. Its stale footer assertion was updated to the contact footer already present in the application. UI evidence: [desktop](screenshots/labels/desktop.png), [tablet](screenshots/labels/tablet.png), [mobile](screenshots/labels/mobile.png).

## 1. Product goal

Allow a shop to choose or measure its label stock, select a design, add items, preview the exact arrangement and print consistently. Support single, double, triple and custom numbers of labels across a roll, including gaps. Offer company logos, barcodes on either side, multiple designs, precise sizing and reusable printer calibration.

Cover label sizes through editable presets and custom dimensions. A finite preset list cannot cover every supplier's stock. Availability of a size, material, sensor mode or cutter must be validated against the selected printer and driver. Small labels can be supported without promising that every barcode and every design will fit them.

Keep four configurations separate:

| Configuration | What it controls | Example |
|---|---|---|
| Label stock | Physical label, liner or sheet, columns, rows, gaps and margins | Three 32 × 25 mm labels across a 104 mm liner |
| Label design | Content and arrangement inside one label | Company logo above the name, barcode on the right |
| Printer profile and device binding | Output method, resolution, usable width and alignment | A particular local thermal printer at its actual resolution |
| Print job | Item data snapshot, quantities, occupied slots and selected configuration revisions | Print 25 copies using stock revision 2 and design revision 4 |

Changing a logo or text size must not change the physical stock. Changing the stock must not silently change printer calibration or replace the design.

## 2. Baseline before the expansion

| Existing module | What exists today | Planned extension |
|---|---|---|
| `frontend/src/views/LabelsView.vue` | Scan/search, document sources, changed-price source, copies, field toggles, iframe preview and browser print | Structured setup, reusable designs, stock and printer selection, full job preview and calibration |
| `frontend/src/labels.js` | Four roll sizes, two A4 grids, custom size, one stacked design | General geometry, explicit gaps/margins, pagination and a versioned design renderer |
| `frontend/src/barcode.js` | SVG EAN-13, UPC-A and Code 128; shared with receipt printing and scan utilities | Explicit format selection, physical dimensions, format-specific quiet zones and rendering checks |
| `esafepos/api/labels.py` | Outlet-gated label rows, selling prices with tax, currency equivalents, document lists | Saved configuration, richer authorized bindings, UOM/batch-aware rows and print snapshots |
| Separate Print Manager integration | Deferred; no local connector currently bundled | Future label-specific bindings and authorized dispatch, sharing existing label snapshots |
| Settings/session receipt configuration | Global and POS Profile receipt logo and branding | Optional explicit reuse of branding plus separate label defaults |

Current constraints to remove or account for:

- Custom labels are clamped to 20–120 mm wide and 15–120 mm high. Replace those limits with stock/printer capability validation and bounded input validation.
- A4 presets have fixed grids and no explicit gap controls. Do not present them as a match for a supplier's die-cut sheet without measuring it.
- Roll printing treats each individual label as a page; a multi-column roll needs one physical row containing multiple label slots.
- The existing preview samples at most six items with one copy each. The expanded preview must also show real quantities, order and final incomplete rows.
- The current queue merges on item code. New UOM, barcode, batch and serial variations need distinct row identities.
- Current barcode SVG uses a fixed ten-module blank area on both sides and is stretched to the available box. Validate physical symbol dimensions and use the blank areas required by each format. In particular, EAN-13 needs a different left quiet zone. See the official [GS1 size guidance](https://gs1.se/en/guides/how-to-guides/size-guide/).
- Future manager label support needs a verified output adapter. Existing ESC/POS receipt bytes are not a generic label-printer format.

## 3. Stock formats and starter size catalog

### 3.1 Formats

| Format | Planned controls | Delivery |
|---|---|---|
| Single-column die-cut roll | Label width/height, liner width, edge margins and feed gap | First release |
| Double-column roll with gaps | Two labels across, horizontal gap, feed gap and edge margins | First release |
| Triple-column roll with gaps | Three labels across with independent horizontal/feed gaps | First release |
| Custom multi-column roll | Any positive column count that fits validated stock and printer limits | First release |
| Butt-cut or continuous stock | Zero gap or configured continuous repeat length; cutter only when supported | Basic geometry first; device actions after validation |
| Black-mark stock | Physical row dimensions, mark pitch/offset and compatible driver/sensor setting | Capability-dependent |
| A4, A5, Letter, Legal and custom sheets | Page dimensions, portrait/landscape, margins, columns, rows and gaps | Sheet phase |
| Round, oval and rounded-corner labels | Bounding box plus actual printable shape/safe-area guide | Later design phase |
| Jewelry/dumbbell, split and folded tags | Printable zones, nonprinting bridges, holes and fold guides | Later design phase |

The module prints into existing stock; shape previews do not create physical die cuts. Color is available only through a compatible color printer. Thermal monochrome output needs an explicit monochrome preview.

### 3.2 Proposed starter sizes

All sizes below are **width × height in millimetres for one label**, not the total liner width. These are editable starting points, not claims that a named printer or supplier supports them.

| Group | Starter sizes |
|---|---|
| Mini / code-only | 20 × 10, 22 × 12, 25 × 15, 30 × 15 |
| Compact retail | 30 × 20, 32 × 25, 35 × 25, 38 × 25, 40 × 20, 40 × 25, 40 × 30 |
| General product | 45 × 30, 50 × 25, 50 × 30, 50 × 40, 50 × 50 |
| Larger retail / shelf | 58 × 30, 58 × 40, 60 × 30, 60 × 40, 70 × 30, 70 × 40, 80 × 40, 80 × 50 |
| Large stock / carton | 100 × 50, 100 × 75, 100 × 100, 100 × 150 |
| Exact inch stock | 1 × 0.5 in, 1.25 × 1 in, 2 × 1 in, 2 × 1.25 in, 2 × 2 in, 4 × 2 in, 4 × 6 in |
| User-defined | Positive custom dimensions, subject to device and design validation |

Keep exact inch conversions: for example, 2 × 1 in is 50.8 × 25.4 mm. Do not merge it with a 50 × 25 mm preset. Provide mm/in input and store canonical decimal millimetres.

Retain existing preset keys through migration. Add a supplier/product reference field so shops can save their actual stock measurements and stock name. A preset should include validated design suggestions, not automatically enable all content fields.

### 3.3 Example multi-column configurations

These are measured-layout examples. Check both liner/media capacity and usable printhead width before enabling printing.

| Example | One label | Columns | Horizontal gap | Left/right liner margins | Required liner width |
|---|---|---|---|---|---|
| Single | 50 × 25 mm | 1 | 0 mm | 2 / 2 mm | 54 mm |
| Double | 38 × 25 mm | 2 | 2 mm | 2 / 2 mm | 82 mm |
| Triple | 30 × 20 mm | 3 | 2 mm | 2 / 2 mm | 98 mm |
| Triple | 32 × 25 mm | 3 | 2 mm | 2 / 2 mm | 104 mm |

```text
Double across                         Triple across
┌────────────┐  ┌────────────┐          ┌────────┐  ┌────────┐  ┌────────┐
│  Label 1   │  │  Label 2   │          │Label 1 │  │Label 2 │  │Label 3 │
└────────────┘  └────────────┘          └────────┘  └────────┘  └────────┘
             ↑ horizontal gap                    ↑ horizontal gaps
        feed gap before next row            feed gap before next row
```

For 25 mm-high die-cut stock with a 3 mm feed gap, the physical row pitch is 28 mm regardless of whether that row contains one, two or three labels.

## 4. Geometry and print placement

Stock fields:

- Media kind: die-cut roll, black-mark roll, continuous roll or sheet.
- Label width/height; orientation; optional shape and printable-zone mask.
- Roll liner width or sheet page width/height.
- Columns; sheet rows; horizontal and vertical gaps; left/right/top/bottom sheet margins.
- Roll left/right liner margins and feed gap; separate mark pitch/offset when relevant.
- Per-label safe padding, independent of the physical gap between labels.
- Fill direction, row-major/column-major ordering where supported, starting slot and skipped slots.

Use one coordinate system in millimetres, with a documented media origin and feed direction:

```text
required_width = margin_left + columns * label_width
                 + (columns - 1) * gap_x + margin_right

required_sheet_height = margin_top + rows * label_height
                        + (rows - 1) * gap_y + margin_bottom

slot_x(column) = margin_left + column * (label_width + gap_x)
slot_y(row) = margin_top + row * (label_height + gap_y)

roll_row_pitch = label_height + feed_gap
device_coordinate = round(absolute_mm_coordinate * actual_dots_per_mm)
```

Derive dots/mm from the device's actual resolution, or DPI/25.4 when that is the verified source. Calculate each slot from its absolute coordinate; repeatedly rounding and adding a rounded pitch can accumulate drift.

For gap-sensed rolls, the output adapter must document how printable page height maps to the driver form and sensor-controlled feed. Native output must configure label length and gap according to that printer language. Do not add an extra feed gap to a driver that already advances across it. Store the tested mode in the printer/stock calibration.

For a roll, one logical output row spans all columns. For a sheet, one output page spans the whole sheet. Keep unused slots blank, show them in preview and exclude them from the count of printed labels. Reject zero capacity, overlapping slots and layouts outside the media or usable print area. Do not silently shrink a layout to make it fit.

For the first thermal release, support starting column and leading/trailing empty slots within a row. Full occupied-slot editing belongs to the sheet phase. Resuming a roll always requires the operator to align the physical stock; a remembered slot is only a suggestion.

## 5. Design library

Ship the first six designs with the thermal foundation. Add the remaining designs with their supporting data/encoder capabilities. Every design has compatible size guidance, required fields and explicit overflow behavior.

| Design | Arrangement | Intended use |
|---|---|---|
| Classic | Name, price, barcode underneath | Existing behavior and migration default |
| Company logo | Logo/company header, name, price and barcode | Branded product labels |
| Barcode right | Name and price on left; barcode on right | The requested side-barcode layout |
| Barcode left | Barcode on left; name and price on right | Alternative side-barcode layout |
| Price first | Large price, short name, barcode | Fast shelf/product price checks |
| Minimal | Barcode with optional digits and item code | Compact identification labels |
| Rotated side barcode | Barcode rotated 90° or 270° beside content | Narrow/tall stock; validate full rotated bounds |
| Shelf strip | Name, selling price, UOM/unit price and optional barcode | Shelf edge labels |
| Promotion | Verified current offer, reference price and validity text | Explicitly supported promotion rules |
| Bilingual | Two name fields plus price and barcode | Local-language and English text |
| Batch / expiry | Name, price, batch, manufacture/expiry and barcode | Batch-controlled goods |
| Variant / serial | Name, size/color or other attributes, serial and barcode | Apparel and tracked stock |
| QR / dual code | QR beside product information; optional linear barcode | Product links or supported scan payloads |
| Jewelry / split tag | Content in separate printable zones | Small specialty stock |
| Carton / stock | Large identifier, quantity, location and optional image | Internal stock and packing identification |

Side placement and barcode rotation are independent options. Do not squeeze a barcode horizontally merely to fit a side panel. If a code is too long, show the required width and offer a different design/size.

Illustrative arrangements; these do not imply physical scale or that all content fits every stock size:

```text
Logo header                 Barcode on right            Barcode on left
┌────────────────────┐      ┌────────────────────┐      ┌────────────────────┐
│ [Logo] Company     │      │ Product     ||||| │      │ ||||| Product      │
│ Product name       │      │ LKR 450.00  ||||| │      │ ||||| LKR 450.00   │
│ LKR 450.00         │      │ Code        12345 │      │ 12345 Code         │
│ |||||||||| 12345   │      └────────────────────┘      └────────────────────┘
└────────────────────┘
```

## 6. Designer options

Provide a fast **Simple** mode with a design gallery and field toggles. An **Advanced** mode adds a positioned canvas and property panel using the existing POS controls, CSS variables and localization system.

Supported elements: text, bound field, barcode, QR code when available, logo/image, horizontal/vertical line, border and rectangle. Store declarative, versioned elements rather than executable templates.

Element controls:

- X/Y position and width/height in physical units, with numeric inputs as well as dragging.
- Alignment, snap/grid, guides, distribute/align, layer order, group, duplicate, lock and hide.
- Text font, supported weight, physical size, alignment, line spacing, maximum lines and wrap.
- Overflow choice: bounded shrink-to-fit, wrap, ellipsis or fail. Required identifiers/dates must remain complete; never shorten encoded values.
- Independent name, price, currency, digits and company-name font sizes.
- Padding, border thickness and black/white or supported color choices.
- Rotation at 0°, 90°, 180° and 270° for the initial renderer; any later arbitrary rotation must preserve barcode validation.
- Undo/redo, reset element, reset design, save as, duplicate and restore a previous saved revision.
- Preview with longest name, longest barcode, high price and missing-field examples.

For logos, allow company defaults, optional explicit reuse of effective receipt branding, an outlet override and a design-specific permitted image. Include show/hide, left/center/right alignment, width/height, preserve-aspect-ratio fit and monochrome threshold/dither preview. Never stretch the logo by default. Await image decoding and font loading before declaring a job ready. Report missing assets with a choice to fix them or omit optional content.

Phone/tablet users must be able to select, position and resize with form controls. Keep preview pan/zoom available without requiring desktop drag precision. Reuse the current RTL/localization behavior and isolate barcode payloads/digits as LTR.

## 7. Size and scale controls

| Control shown to the user | Effect | Rule |
|---|---|---|
| Label width/height | Changes the physical die-cut rectangle | Saved on stock; invalidates incompatible calibration |
| Page/liner size | Changes the output container | Does not change individual label dimensions |
| Design scale | Uniformly scales content around a visible anchor inside one label | Does not alter gaps, label count or stock; reruns fit checks |
| Element size | Adjusts only selected text, logo or other content | Preserve logo proportions and barcode rules |
| Barcode module width and height | Controls symbol size through its encoder | Quantize to device dots and enforce symbology requirements |
| Printer X/Y offset | Shifts the physical print origin | Saved for the matching device/output/stock configuration |
| Advanced X/Y correction | Corrects measured device output geometry | Small, explicit adjustment; regenerate and revalidate symbols |
| Preview zoom | Changes the screen view only | Never affects output dimensions |
| Driver/browser scale | External print-dialog setting | Use actual size/100%; provide clear setup instructions |

Always show the resulting physical dimensions beside scale percentages. Display both design bounds and the printable boundary. A visual zoom slider must never silently become a print scale slider.

Offer fit-within-safe-area for ordinary content. Barcode elements must be regenerated with valid modules/height rather than distorted with a generic CSS transform. Show blockers when the selected scale cannot produce a valid symbol.

## 8. Data fields and barcode formats

### 8.1 Content bindings

| Group | Fields | Source and conditions |
|---|---|---|
| Company/outlet | Company display name, logo, branch, address/contact | Authorized company/POS Profile plus label branding defaults |
| Product | Item name/code, barcode, description, brand, group, image | ERPNext Item and approved label-safe fields |
| Price | Tax-inclusive selling price, currency, equivalents, UOM and optional unit price | Existing server pricing path extended for selected UOM |
| Variant | Size, color and other configured attributes | Actual ERPNext variant data |
| Traceability | Batch, serial, manufacture/expiry, packed date | Explicit source row or operator selection with permission checks |
| Stock/job | Warehouse/bin where available, quantity, source document, print date, operator | Authorized records and the print-job snapshot |
| Custom | Approved Item/Company/POS Profile/custom fields and static text | Field metadata allowlist; no arbitrary database expressions |

Do not print cost/buying price through the default selling-price binding. Any future cost field must have a separate permission. Label setup must not grant Item Price edit rights. Keep tax/currency calculations on the existing server path.

Missing batch/serial/expiry data must not be guessed from the item. A document with multiple batches needs separate queue rows. Serial labels normally have one copy per selected serial; extra copies must be an explicit choice. Quantity conversion and fractional document quantities need an explicit policy such as one per source line, one per package or an operator-confirmed integer count.

### 8.2 Encoders

| Format | Delivery | Validation |
|---|---|---|
| EAN-13, UPC-A, Code 128 | Preserve and strengthen in first release | Correct payload, check digit where applicable, character set, quiet zones, minimum module width/height and readable text |
| EAN-8, UPC-E, Code 39, ITF | Later, when a concrete stock/customer use requires them | Format-specific encoder and independent reference/decoder tests |
| QR Code | Later encoder phase | Payload purpose, capacity, physical module size, clear border and supported POS scan behavior |
| Data Matrix, GS1 DataMatrix, GS1-128 / GS1 QR | Advanced integration | Verified application identifier/FNC1 or Digital Link handling as appropriate; ordinary Code 128/QR is not automatically GS1 |
| Variable-weight/price codes | Separate advanced workflow | Match the configured scale schema and POS parser before generating labels |

An explicit format selection must fail visibly for incompatible data. Auto mode must show the chosen format and any item-code fallback. Preserve leading zeroes and stored identifier values. Do not silently repair invalid EAN/UPC check digits, truncate data or claim that a newly generated internal code is an assigned retail GTIN.

Quiet zones belong inside the label design and cannot be replaced by the gap between stickers. Reserve symbol-specific quiet areas against nearby text, logos, borders and the die-cut edge. GS1 publishes distinct EAN/UPC dimensions and blank-area requirements; use the relevant application profile rather than one generic rule. See [GS1 General Specifications](https://ref.gs1.org/standards/genspecs/) and [GS1 size guidance](https://gs1.se/en/guides/how-to-guides/size-guide/).

Physical scanner tests are required even if SVG decoding passes. Screen decoding does not establish print-quality grading or standards certification. QR product links must be presented as links unless the actual POS/scanner supports their intended item-resolution format.

## 9. Queue, workflow and preview

Main workflow:

1. **Add items:** Scan/search or reuse Purchase Receipt, stock-updating Purchase Invoice, Stock Entry and changed-price sources.
2. **Choose stock:** Single/double/triple/custom, dimensions and measured gaps.
3. **Choose design:** Pick a compatible template; show/hide fields and optionally edit it.
4. **Set copies and order:** Per-row quantity, batch/UOM/barcode variant, sequence and starting slot.
5. **Choose printer:** A label-specific output/printer profile with the applicable calibration.
6. **Preview and validate:** Inspect one label and the actual roll rows/pages; resolve blockers.
7. **Print test or job:** A test row is useful for all columns; normal jobs preserve the frozen data snapshot.

The queue must support quantity presets, selected-row bulk edits, sorting/reordering and a clear total. Later add item-group/brand filters, stock/document action shortcuts and validated CSV import with an error review. Never silently drop rows above the current API limit; paginate source selection or reject an oversized request clearly.

Copy expansion uses composite row identity: item + UOM + selected barcode + batch/serial + relevant per-label data/design override. Provide sequential copies by default and an explicit repeat-across-row option; preview the resulting order. Avoid multiplying per-item quantities again through a driver's whole-job copy setting.

The preview has two levels:

- **Label view:** Design elements, physical ruler, safe area and quiet zones.
- **Media view:** All columns, gaps, liner edges or sheet margins, skipped slots, page breaks and final incomplete row.

Use the same validated geometry and data snapshot for preview and output. Preview large jobs in paginated/virtualized sections without creating thousands of hidden DOM labels. Show total labels, physical rows/pages, blank slots and estimated consumed length; identify any driver-dependent trailing feed separately.

## 10. Printer connections and calibration

### 10.1 Output routes

| Route | Role | Delivery |
|---|---|---|
| Browser print | Accessible fallback using an installed driver and actual-size media form | First release |
| Separate Print Manager | Future desktop convenience through verified adapters | Deferred until the external manager is ready |
| PDF export | Exact page-size output suitable for saving and printing through an installed driver | Implemented |
| ZPL, TSPL and optional EPL/CPCL | Native thermal adapters for verified models/languages | Later, one adapter at a time |

Use a separate label printer selection from the existing receipt selection. Printhead width, liner width, minimum label length, sensor support and firmware language belong to the capability record. Include presets for actual measured resolution, commonly around 203/300/600 DPI, with an exact dots/mm override when specified by the hardware.

Use matching custom page dimensions, no margins and actual-size scaling in the selected printer driver. Test the route on the real device before marking that combination supported. Future manager adapters must preserve the validated scene dimensions and explicitly document resolution and unit handling.

Choose a driver output representation after a thermal proof-of-concept. HTML text/font support varies across renderers. A fixed-resolution image needs barcode-safe device-dot rendering; PDF should preserve vector symbols where supported. Document the tested adapter behavior rather than claiming identical rendering from arbitrary HTML across all print stacks.

Native command adapters must be selected by actual supported language, with proper text escaping/encoding and image handling. A brand name alone is insufficient evidence of a printer language. Use the printer manufacturer's language reference and verified firmware/media settings.

### 10.2 Calibration wizard

1. Identify printer, driver, output route, actual resolution, stock and feed direction.
2. Configure the driver stock form and physical gap/black-mark sensor; run the device's media calibration when required.
3. Print one row with outlined printable bounds, numbered columns, horizontal/vertical rulers and a known test barcode.
4. Let the operator enter measured width/height and horizontal/vertical displacement. Apply X/Y offsets and only necessary geometric correction.
5. Print several rows to distinguish fixed origin error from pitch/feed drift. Fix the driver or stock pitch when that is the source.
6. Print a longer strip and scan the first/last labels and every column before saving the profile as verified.

Save calibration for the combination of device, local printer binding, driver/output route, resolution, stock revision and orientation. A design text change can keep calibration; changed stock geometry, resolution or route needs revalidation. Keep shared recommended printer settings separate from per-device measured offsets.

Density/darkness, speed, cut, peel and backfeed controls appear only when the chosen adapter supports them. Otherwise link to the printer's own setup; do not show nonfunctional switches.

## 11. Persistence, defaults and permissions

Proposed Frappe records, introduced only in their implementation phase:

| Record | Responsibility |
|---|---|
| `EsafePOS Label Stock` | Reusable media geometry, units, shape/safe zones, supplier reference, scope and schema revision |
| `EsafePOS Label Template` | Declarative design JSON, bindings, compatibility, branding choices and saved revisions |
| `EsafePOS Label Printer Profile` | Shared output capabilities and recommended settings; never connector private keys |
| `EsafePOS Label Outlet Settings` | POS Profile/company-scoped default stock, design, branding and permitted printer profiles |
| `EsafePOS Label Print Job` | Owner, outlet, frozen configuration/data, copies, source references, status, adapter result and explicit reprint links |

Device-local storage holds printer names/bindings, measured calibration and last-used choices. If cross-device calibration administration is later required, add a scoped device record instead of treating all tills as one printer. Job rows can use bounded structured JSON initially; use child rows if query/reporting needs justify them.

Shared default precedence: POS Profile override → company default → shipped default. A remembered device choice may override a default only when still permitted and compatible; show that effective selection. Label branding stays separate from receipt branding unless an operator explicitly chooses reuse.

Keep `enable_labels` and `Print labels`. Add manager-controlled capabilities for managing shared templates/stock and printer settings. Printing an approved design must not require design-management access. Ordinary per-job options can remain available within approved constraints.

Check feature switches, company/outlet scope, linked-document read access and record permissions on every relevant server call. Do not infer permission from visible dropdown choices. Custom fields and image files must be readable by the current user and safe for the selected output route; stored HTML/script and raw printer commands are not template content.

Future manager integration must authorize label operations separately from receipt operations, bind dispatch to validated jobs and limit payload sizes/quantities before any output. Do not reintroduce a generic request signer. The retired QZ signing endpoints and credentials are not part of that integration.

## 12. Job state, reprints and offline behavior

Job states should distinguish prepared, awaiting print dialog, submitted to connector/spooler, failed, canceled when observable and outcome unknown. Report physical completion only when reliable device feedback exists. Browser dialog return and a connector acknowledgement do not prove that labels emerged from the printer.

Disable repeated Print clicks during dispatch. Use stable job and part identifiers to avoid duplicate API job creation, but do not promise exactly-once physical printing. Never auto-replay a job after an uncertain connector failure or after reconnecting.

For partial output, let an operator choose the unprinted row/page/slot range and create a linked reprint. Show the last known connector state and retain the original quantities. Reprinting a historical price snapshot and creating a new job with current prices are separate explicit actions; highlight when current data differs.

First release should prepare fresh item/price jobs online. Cached designs can still be viewed offline. A later opt-in offline-print capability may use a previously authorized bounded snapshot, cached assets and an offline-capable adapter; display data age and honor the existing offline permission policy. Fresh job authorization and current prices cannot be promised offline. Do not queue automatic physical printing for later reconnection.

## 13. Implementation structure

Keep the existing route and API namespace. Suggested boundaries:

| Location | Planned responsibility |
|---|---|
| `frontend/src/views/LabelsView.vue` | Queue and workflow orchestration |
| `frontend/src/components/labels/` | Stock form, design gallery, designer, element properties, media preview, print summary and calibration wizard |
| `frontend/src/stores/labels.js` | Current job, selected configuration, dirty state and bounded draft persistence |
| `frontend/src/labels/stock.js` | Unit conversion, stock schema and geometry validation |
| `frontend/src/labels/layout.js` | Slot placement, quantity expansion, skips, pagination and absolute dot conversion |
| `frontend/src/labels/design.js` | Versioned element schema, bindings, text fit and symbol bounds |
| `frontend/src/labels/render.js` | Validated label scene and preview/browser output |
| `frontend/src/labels/printing.js` | Output adapters and job-part dispatch |
| `frontend/src/labels/presets.js` | Stable stock/design preset identities |
| `frontend/src/labels.js` | Compatibility facade during migration |
| `frontend/src/barcode.js` | Shared encoding; preserve receipt/scan compatibility when extending render options |
| Future manager adapter | Authorized connector transport, with separate receipt and label operations |
| `esafepos/api/labels.py` | Authorized product/source selection and narrow whitelisted label endpoints |
| `esafepos/labels/` | Pure stock/design/job validation helpers where server/client parity is required |
| `esafepos/esafepos/doctype/` | Saved label records and validation |
| Settings/session APIs and `SettingsView.vue` | Feature/capability configuration and effective defaults |

Proposed endpoint groups under `esafepos.api.labels.*`: list/load/save permitted stock/designs; fetch allowed bindings; resolve defaults; prepare job; get authorized job output/parts; record adapter result; create reprint. Keep persistence validation in the DocType/helper layer so Desk writes receive the same checks. Keep Python 3.7 syntax compatibility and avoid introducing modern-only union syntax in new code.

Initial job preparation should freeze authorized row data and referenced stock/design revisions. Future PDF/native output must consume that same scene specification. Server-side checks must reject malicious direct payloads even if the browser already validates them.

## 14. Phased delivery and completion gates

| Phase | Scope | Required completion evidence |
|---|---|---|
| 0. Thermal proof and schema | Measure actual target stock/printer, finalize stock/design/job schema, prove browser/driver geometry, decide image/HTML/PDF transport | Single/double/triple test row, exact resolution/driver details and measured output recorded |
| 1. Thermal foundation | Saved stock/templates/defaults/jobs; custom dimensions; 1/2/3/custom columns and gaps; first six designs; logo options; simple scale/field controls; browser output; preview and calibration | Correct counts and incomplete rows; every column aligned/scannable; independent receipt/label output choices; permission and migration checks pass |
| 2. Advanced designs and data | Positioned designer, revisions, richer bindings, UOM/batch/serial rows, rotated barcode, bilingual and specialty design zones | Long/missing values, languages, traceability and physical barcode tests pass |
| 3. Sheets and exports | A4/A5/Letter/Legal/custom sheet presets, margins/gaps, occupied slots, page ordering and PDF export; QR if validated | Measured full-sheet alignment; skipped slots, pagination and exact PDF dimensions verified |
| 4. Native/advanced thermal | ZPL/TSPL and other justified adapters, supported hardware actions, QR/GS1 integrations and optional variable-weight generation | Separate real-device/scanner support matrix for each enabled capability |

A phase is complete only when its documented capability works on the stated device/route. Keep later features marked planned; do not expose inactive toggles as working features.

## 15. Verification and acceptance scenarios

### Automated checks for implementation

- Add focused `frontend/label-layout-check.mjs` coverage for mm/in conversion, double/triple/custom columns, nonzero gaps, decimal dimensions, row/page counts, fill order, skipped slots, dot rounding and invalid geometry.
- Add focused `frontend/label-design-check.mjs` coverage for bounds, safe zones, long text, missing bindings/assets, barcode format selection, checksum errors and barcode size blockers.
- Extend `frontend/barcode-check.mjs` when changing encoding/rendering, using independent references and decoder checks. Verify existing receipt barcode and scale-parser behavior.
- Add `esafepos/api/test_labels.py` and pure-helper tests for permissions, document access, UOM/batch distinctions, source quantity policy, bounded job preparation, defaults and snapshots. Use bench-backed integration tests for ERPNext pricing and records that require Frappe.
- Verify that retired connector setups use browser output without connector calls and reset incompatible alignment. Add bounded dispatch, permission and uncertain-outcome checks when the separate manager is integrated.
- When production code changes, run `cd frontend && npm run build`, `cd frontend && node barcode-check.mjs` and the new label checks; run `cd frontend && node receipt-check.mjs` when shared barcode/printing/receipt code changes.
- Rebuild and commit `esafepos/public/pos/` with frontend source changes. Run `git diff --check`. Update this plan, the user guide and project logbook with implemented scope and actual verification.

### Physical and browser acceptance

| Scenario | Expected result |
|---|---|
| Triple stock, 25 labels | Nine physical rows; two blank final slots; no duplication or clipping |
| Double stock, seven labels | Four rows; one blank final slot; exact horizontal gap |
| 2 in stock compared with 50 mm stock | Remain distinct physical dimensions |
| Barcode too long for side panel | Clear width/size blocker with valid alternatives |
| Logo enabled/disabled and changed | Layout respects safe bounds; missing image is reported before dispatch |
| Mixed items, copies, UOM and batches | Preview and output preserve identity, order and correct per-UOM prices |
| Invalid EAN or leading-zero UPC | Invalid explicit format rejected; leading zero preserved |
| Hundreds of consecutive roll rows | No accumulating placement drift; first/last row and every column scan |
| Driver already handles feed gap | No extra blank feed or skipped physical row |
| Print canceled or connection lost | Honest observable status; no automatic duplicate print |
| 203-class and 300-class devices | Correct measured size and valid device-dot modules on each tested model |
| Long names, currencies, Arabic/Persian | Defined overflow; correct shaping/font support and LTR identifiers |
| Sheet starting at a used slot | Existing labels skipped; correct page count and order |
| Desktop, tablet and phone | Usable quantity/setup controls, preview navigation and accessible numeric editing |
| Feature disabled or wrong company | Server rejects protected configuration/job actions |
| Updated installation | Existing label choices migrate; receipt printing and labels remain usable |

Capture desktop/mobile screenshots for the future UI PR and keep measured sample output/scanner results with the device support matrix. Proposed first-device acceptance targets are at most 0.5 mm origin/size error and at most 0.5 mm additional drift over the tested long strip; adjust these targets only with recorded hardware limits and confirm that print remains inside the actual safe area. These are release targets, not current verified claims.

## 16. Migration and rollout

1. Seed stable built-in stock and design records idempotently; preserve edited copies.
2. Map existing local `esafepos-labels` size, custom dimensions and field toggles to the Classic design and matching stock. Do not automatically share device preferences across users/outlets.
3. Preserve existing roll and A4 choices while making their actual geometry visible. New measured stock definitions can replace inaccurate supplier assumptions.
4. Keep the existing feature switch and printing capability; give shared-edit controls only to the intended management roles.
5. Pilot browser output on a real single/double/triple thermal configuration, record verified profiles, then roll out to other devices. Run a separate pilot when the external Print Manager is integrated.
6. Publish setup steps and measured calibration guidance in `docs/user-guide.md` when behavior ships.

No stock movements, Item Price updates or accounting documents are created by preparing or printing labels.

## 17. Remaining deployment inputs

Planning can proceed with the thermal-first decision. Before claiming real-device support, collect printer model/firmware, driver name/version, actual resolution, usable print width, supported language and sensor mode; measure label width/height, liner width, horizontal gap and feed gap. Also collect the intended company logo and the scanner types used at the till.

These details select the first verified profiles; they do not prevent implementing the general geometry and design model. Avoid claiming universal printer compatibility from an editable size catalog.

## 18. Original planning validation

The original planning review covered the label view/renderer, barcode implementation/check script, label API, session/settings branding, capability checks, the then-present QZ path and project logbook. QZ was subsequently removed as recorded above. Barcode and device-output constraints were checked against the referenced standards/vendor documentation. The optional UI Skills CLI catalog was unavailable in the local offline package cache; the workflow follows the repository's existing Vue/POS patterns.

The original planning change was documentation-only. The implementation and its completed software checks are recorded in the status section above; physical site/device verification remains required.
