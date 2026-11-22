# ESAFE POS Project Logbook and Component Reference

**Project:** ESAFE POS (Frappe app package `esafepos`)
**Snapshot:** v0.69.0, based on the repository and product guide dated 2026-11-09  
**Purpose:** engineering overview of the product, its features, modules, data model, and release history.  
**Audience:** maintainers, integrators, reviewers, and technical stakeholders.

> This document describes the implementation visible in this repository. For cashier procedures and settings instructions, use the [user guide](user-guide.md) and [website guide](website-guide.md). The complete per-release history is maintained in [section 19 of the user guide](user-guide.md#19-changelog); this document summarizes its engineering milestones.

## 1. Project at a glance

EsafePOS is a browser-based point-of-sale application for ERPNext and Frappe. It is delivered as a Frappe app named `esafepos`, with a Vue 3 single-page application served at `/pos`. It uses ERPNext's POS Profile, customer, item, stock, invoice, payment, and accounting records, and adds workflows for registers, promotions, returns, offline sales, outlet management, reporting, and stock counting.

| Area | Implementation |
|---|---|
| Server | Python, Frappe whitelisted APIs, ERPNext document APIs |
| Client | Vue 3, Vue Router hash routes, Pinia, Vite |
| Persistent business data | ERPNext invoices and stock/accounting documents plus EsafePOS DocTypes |
| Local/offline data | IndexedDB `esafepos`; service worker where supported; `esafepos-printing` stores workstation roles/intents, and the SDK owns its separate browser identity database |
| Supported framework line | Frappe / ERPNext 13 through 16; Python syntax remains compatible with 3.7 |
| Package | `esafepos`, app title `ESAFE POS` |
| License | AGPL-3.0-only; product name and logo are trademarks (see `license.txt` and `TRADEMARKS.md`) |

## 2. Product features

### Unreleased

- Repaired the checkout quote endpoint's undefined pricing flag, which caused the entire pricing/credit response to fail and silently hid **Put on account**. Checkout now checks credit independently, displays recoverable errors with **Retry**, and waits for a confirmed payable before adding debt. Added automatic deployed-build checks every 15 seconds and on focus/reconnect: idle tills update themselves, while carts, checkout, editing, sync and active printing defer reload. The release number need not change. Existing installations need to reopen once to load the updater; subsequent builds are detected after deployment, not from a Git push alone. No DocType changes. Verification and desktop/mobile screenshots are in the dated entry below.
- Integrated the supplied private **Esafe Printer Manager SDK 0.1.0** into Printing. The POS now supports explicit native connection/approval, exact installed-queue roles per browser/workstation/outlet, profile-level silent/automatic receipt defaults, HTML/PDF/raw receipts, PDF labels/A4 invoices/quotations, thermal reports/payment receipts and explicit browser fallback. Stable persisted intents, cross-tab locks, native job reconciliation, manual identical retry and authorized reprints keep print outcomes separate from sales/accounting. Added `EsafePOS Print Intent` metadata and five POS Profile defaults; both silent/automatic switches default off. The SDK is vendored with a relative dependency and lockfile. See [deployment, cashier setup, rollback and hardware qualification](esafe-print-manager.md) and the dated logbook entry.

- Consolidated receipt adjustment, label output and printer setup into **Printing** (`/printing`) with Labels, Receipt and Printers sections. Existing `/labels` bookmarks redirect to Labels. The extracted receipt editor retains global/outlet defaults, custom fields and live preview, adds sample preview printing, and persists all cashier/terminal/invoice-barcode switches. Printer setup edits the existing POS Profile host, port and compatible ERPNext Print Format and submits a bounded, drawer-free test receipt. Settings users can configure printing even when labels are disabled; label-only cashiers cannot open receipt/printer configuration. Narrow APIs and partial receipt updates prevent General Settings and the receipt editor from overwriting each other's configuration. The workspace consolidation preserves the existing label and receipt data model; the subsequent Esafe integration is recorded above. Verification and UI evidence are recorded in the dated logbook.
- Fixed checkout pricing that could turn every regular item into a full-value discount when ERPNext automatic discounts were enabled. Native rates resolve before they are frozen, and final rate/discount fields stay consistent so receipts show actual savings and account sales use the correct payable. Credit checkout refreshes customer eligibility/availability and refuses offline queuing after a connection failure. Affected: `api/sales.py`, cart store and `PaymentOverlay.vue`; no DocType change. Verification and screenshots are recorded in the 2026-11-22 logbook entry below.
- Removed QZ Tray from the POS before the Esafe integration described above. Receipt Settings no longer offers local discovery or certificate/key upload, and receipts use the existing server-network, ERPNext Print Format or browser routes. Labels retain browser printing, PDF and native-file exports; legacy connector profiles normalize to browser output and reset incompatible alignment. Removed connector code/assets, receipt and label signing endpoints, and the QZ settings fields. The receipt/label components, output helpers, label validation, settings schema, user guide and integration plans are affected; no replacement manager is bundled. Verification is recorded in the dated logbook entry below.
- Added editable **Packs / Bundles** quantities and percentage/direct **per-bundle discounts** in the cart. Repeated Add taps merge into the matching bundle group; component quantities, fixed prices and allocated shares scale together. The server validates positive whole counts, complete recipes and consistent group discounts, while existing cashier permissions and approval limits cover the effective discount on the bundle price. Single-product bundle cards now offer **Sell loose**, opening the same stock item's decimal quantity/selling-unit editor; alternate-unit choices show their Kg conversion and stock usage. Bundle details can load before the catalog cache finishes, and stock guards count loose and alternate-UOM lines together. Affected: cart store, CartLine, SellView, ItemDetailModal, catalog scanner resolution, sales bundle validation and mirrored manual-discount arithmetic. No DocType change: count/discount fields travel in cart/parked/offline payloads; ERPNext invoice quantities remain authoritative stock/selling UOM quantities. User guide includes 25 kg/50 kg purchase/sale UOM setup. Verification: production build; 53 standalone Python bundle/UOM, manual-discount and promotion tests; Python 3.7 grammar checks; 16 shared Python/JS discount fixtures; promotion parity; Chrome bundle and existing discount regression checks, covering concurrent Add, approval reset, permissions, fractional loose sales, pack conversion, aggregate stock boundaries, offline receipts and desktop/mobile layouts. Screenshots: [desktop](screenshots/bundles/bundle-1440.png), [mobile](screenshots/bundles/bundle-390.png). A live Frappe invoice/purchase receipt was not posted from this environment.
- Implemented the expanded **Labels** workspace: metric/inch presets, single/double/triple/custom columns, independent gaps/margins, sheet formats and skipped slots; 15 designs including side/rotated barcodes, company logos and QR; element editing, scaling, fonts, undo/redo and full-copy previews. Browser output, exact-size raster PDF, ZPL/TSPL file export and device calibration share one scene renderer. Added outlet-scoped `EsafePOS Label Preset` and private `EsafePOS Label Print Job`, manager-only shared saving, server repricing/identifier validation, alternate units and document batch/serial preservation. The initially included QZ signing/dispatch was removed on 2026-11-22 pending separate Print Manager integration. Verification: production build, label/barcode checks, 17 standalone Python tests, Python 3.7 grammar checks and mocked Chrome desktop/tablet/mobile/PDF/QZ checks, including partial failures and independent barcode/QR decoding. Site migration and physical printer/scanner verification remain required; later scope is identified in the [module plan](label-printing-module-plan.md).
- Added a [POS Print Manager and Windows Print Bridge plan](print-manager-and-windows-bridge-plan.md) for installed Windows printer discovery, local WebSocket printing and approved direct-IP output from the till. It covers independent receipt/label/document assignments, native site pairing and trusted local TLS, server-authorized jobs, durable duplicate detection and uncertain outcomes, proposed device/profile/binding/delivery records, migration from existing QZ/browser/server-network routes, offline boundaries and phased hardware acceptance. The plan reuses the in-progress label records rather than duplicating label snapshots. Verification: repository review, official Microsoft/Chrome documentation review, local documentation-link checks and diff whitespace checks; no runtime/schema/generated-asset change or physical printer validation.
- Added a [thermal-first Label Printing Module plan](label-printing-module-plan.md) covering custom dimensions, single/double/triple/custom columns with horizontal and feed gaps, multiple designs including side barcodes and company logos, independent design/page/label scaling, printer calibration, saved configuration, permissions, job snapshots and phased sheet/native-printer support. The plan separates proposed records and components from the current implementation and identifies the existing barcode sizing and QZ label-signing constraints. Verification: reviewed the current label, barcode, branding, permission and QZ code against official GS1/QZ documentation; documentation diff checks performed. No runtime behavior or schema changed; application tests and bundle rebuild were not run.
- Fixed the POS **Copy link** action in the E-invoice sharing card: if the asynchronous signed-link request causes browser clipboard activation to expire or the clipboard API is denied, the app tries a legacy copy operation and exposes a selectable read-only URL for manual copying. The recovery path is designed for phone and tablet browsers as well as desktop. Verification: frontend production build pending; tests not run.
- Added an online-only **Invoice** action to the POS cart and a dedicated **Invoices** screen for use without an open register. Both require a named customer and create a submitted, non-POS ERPNext Sales Invoice without upfront payment; the workspace accepts an optional due date and salesperson. The backend reuses server-side item pricing, discounts, taxes, serial, and stock validation; checks Sales Invoice create/submit permissions; enforces required salesperson selection; and uses idempotency keys. A read-only invoice-origin field ties the regular invoice to its source outlet, so customer purchase totals, management sales, and salesperson commission reports include it without counting consolidated invoices twice. Customer outstanding and the existing till payment collection flow then operate on the invoice through ERPNext's receivable ledger. The action and navigation entry are controlled by the Regular Sales Invoices switch, and layouts support mobile/tablet widths. Updated the implementation plan and user guide with shipped and staged scope. Verification: `cd frontend && npm run build` passed before the report/schema adjustment; Python syntax checking was unavailable in this environment; tests not run.
- Began implementation of the POS selling/HR feature-switch foundation: added independent site-wide switches for regular Sales Invoices, customer balances/payments, cheque tracking, quotations, Sales Orders, HR integration, attendance, expense claims, day salary, commissions, and commission payroll. Server gates now protect the existing direct Sales Invoice, quotation creation, customer balance/payment, and salesperson commission-report paths. Customer account balances can be shown when on-account selling is disabled. Added responsive Modules & Features cards and a phone-friendly customer list/detail layout. Cheque, Sales Order, HR, and payroll workflows are marked in development and cannot be enabled until their actions are implemented. Verification: frontend production build passed; settings DocType JSON parsed successfully; tests were not run.
- Added `docs/pos-selling-and-hr-implementation-plan.md`, a phased design for regular Sales Invoices, ERPNext customer balances and Payment Entries, quotation/order progression, cheque tracking, optional Frappe HR attendance and claims, day wages, employee commission payout, and individually configurable Modules & Features switches. The plan was checked against the existing sales, credit, customer, quotation, and salesperson modules and official ERPNext/Frappe HR documentation.
- Receipt branding and display controls: removed the currency code below the shop name, added a configurable shop contact number above the address, and appended ESAFE's default contact number beside `pos.esafe.lk` in the standard footer. Added independent switches for cashier name, terminal/user, and invoice barcode. These settings apply to the live preview, browser print, and network thermal receipts and persist globally or per POS Profile.
- Selling UOM variants: item detail now lists configured alternate UOM conversions with their prices. Unit-specific Item Prices take precedence; when absent, pack prices use the active stock-unit price multiplied by the ERPNext conversion factor. Sale validation uses the same fallback and still checks converted stock availability.
- Expanded the **Items** workspace to create and edit multiple selling UOMs with conversion factors and unit prices, manage multiple barcodes with per-UOM assignment, and generate barcodes. Item detail shows each configured unit and its active or calculated price; serial-tracked items remain stock-unit-only. The server validates unit conversions, price permissions, barcode uniqueness, and barcode-to-UOM references. Affected: `frontend/src/components/ItemCreateForm.vue`, `frontend/src/views/ItemsView.vue`, `frontend/src/itemUtilities.js`, and `esafepos/api/items.py`; no schema change. Verification: `cd frontend && npm run build` passed; tests not run.
- Affected modules: `frontend/src/components/ReceiptView.vue`, `frontend/src/views/SettingsView.vue`, session/settings APIs, ESC/POS receipt rendering, and the `EsafePOS Settings` DocType. Verification: `cd frontend && npm run build` passed; no tests run.

### 2.1 Till and checkout

- Product browsing by category and search, with barcode, weight-embedded scale barcode, and serial-number scanning.
- Sale of loose and packed quantities from one ERPNext item, with per-unit prices and a POS Items editor for standing prices, names and photos. Product images can be uploaded or assigned by direct HTTPS link. Saved price editing requires manager access or a rule backed by ERPNext permissions.
- Cached catalog search, product stock availability, price check, and a cart with customer, channel, salesperson, note, coupon, and discount controls.
- Multiple payment methods, split tender, cash shortcuts, change due, payment references, and customer payment collection.
- Per-profile choice of POS Invoice (normally consolidated at shift close) or Sales Invoice (posted directly); both use standard ERPNext documents.
- Named-customer standard Sales Invoice creation from the cart, plus an invoice workspace usable without opening a till register; submitted invoices remain receivables until paid through customer account collection.
- Printable receipts with a default ESAFE footer, configurable details and a lightly lined Table template. The invoice barcode opens the matching sale in History. Includes browser printing, ESC/POS network printing, reprints, and cash-drawer kick where configured.
- Three catalog views with quick Add, progressive loading and a tap-to-open item editor for quantity, stock unit, authorized price edits and discounts.
- A second-screen customer display with an optional membership keypad, latest-item highlight, automatic product icons, pinned totals and a completed receipt with rewards.

### 2.2 Pricing, promotions, and offers

- POS Promotion rules: simple discount, Buy X Get Y, Spend and Save, and Bundle Price.
- Promotion scheduling by dates, days, and daily time windows; eligibility by outlet and customer group; product matching and exclusions; coupon gating; and stacking controls.
- Client-side offer evaluation and suggestions for near-qualifying baskets, backed by authoritative server recalculation during submission.
- Price books for customer group/outlet pricing, delivery-app price lists, and controlled price edits.
- Product bundles with whole-pack/set quantity controls, percentage/direct per-bundle discounts and single-product loose-sale shortcuts; delivery app channels, order identifiers, and manual line/order discounts with configurable approval.

### 2.3 Customers and balances

- Customer search, creation, configurable required/optional/hidden form fields, company address capture, and customer reporting.
- ERPNext loyalty point display and redemption.
- Gift card issuance, tender, balance entries, and redemption.
- Store credit ledger and tender; customer credit/on-account sales and customer payment collection.
- When enabled separately, customer account balances and open invoices remain visible even if new POS on-account selling is turned off.
- Cashback rules, earned balances, redemption, expiry, and scheduled accounting.

### 2.4 Returns, exchanges, and holds

- Full and partial returns with per-line quantity selection, original-sale linkage, configurable reasons/restrictions, and optional supervisor approval.
- Refunds by payment method or store credit; exchange workflow that submits the return and replacement sale together and settles only the difference.
- Serialized item controls that bind quantities to selected serial numbers and validate on the server.
- Holds/layaways with deposits, reserved stock, installments, completion, cancellation, and refund handling.
- Parked sales for temporary retrieval, separate from long-running holds.

### 2.5 Registers and cash operations

- Register sessions with opening floats, multiple currency floats, cash in/out, payment-method counts, expected-versus-counted reconciliation, and shift summaries.
- X-report mid-shift view, closing/Z-report data, variance explanations, manager alerts, and audit events.
- Shift ownership by outlet or cashier, multiple outlets/registers, shift schedules, overdue alerts, and safeguards around concurrent or stuck closing operations.
- Supports ERPNext POS Opening/Closing Entries where appropriate, recovery of externally opened shifts, retryable consolidation, and direct Sales Invoice mode.

### 2.6 Offline and device workflows

- IndexedDB caches bootstrap/catalog data, stores queued sales and pending customer work, keeps a local shift sales view, and records sync status.
- Idempotency keys and serialized upload locks protect queue retries from duplicate postings.
- Service worker serves the POS shell offline on supported Frappe versions; queued submissions sync when connectivity returns.
- Serialized sales, live history, register open/close, customer balances, and other server-dependent operations have online requirements or explicit offline restrictions.
- EsafePOS Stock mobile/handheld app integration supports individual and shared counts; the till also supports stock count entry and merge.

### 2.7 Reporting, security, and administration

- Insights includes sales summary, cashiers, products, profit, customers, outlets, and salesperson reporting, with date and organizational scopes and CSV export where implemented.
- Settings screens configure features, permissions, outlets, payments, customer forms, languages, receipts, approvals, pricing, promotions, and stock tools.
- Modules & Features has independent switches for direct Sales Invoice mode, customer balances and payments, cheque tracking, Quotations, Sales Orders, optional Frappe HR functions, and salesperson commissions/payroll. Switches and dependencies are enforced by the server; Frappe HR controls require the separate app.
- Customer search/profile switches to a single-pane detail view on phones, keeps invoice tables horizontally scrollable, and uses a compact two-column layout for tablets.
- Capability rules may be assigned to roles or users. UI visibility is paired with server-side checks.
- PIN/passcode support, till locking, manager approval flows, audit log, and system checks support operational controls.
- Thirteen interface locales are present: English, Arabic, Spanish, German, Simplified Chinese, French, Thai, Indonesian, Vietnamese, Brazilian Portuguese, Persian, Russian, and Turkish. Arabic and Persian use RTL layout.

## 3. Architecture and request flow

```text
Browser
  /pos (Frappe page shell)
    └── Vue app (frontend/src)
         ├── Views and reusable components
         ├── Pinia stores: session, catalog, cart, help
         ├── API wrapper ───────────────┐
         ├── IndexedDB/offline queue     │
         └── Service worker (where supported)
                                        ▼
Frappe whitelisted endpoints (esafepos/api)
  ├── permission and outlet checks
  ├── promotion, pricing, currency, return and register rules
  └── ERPNext documents + EsafePOS DocTypes
        ├── POS Invoice / Sales Invoice / Payment Entry
        ├── POS Opening/Closing Entry, Stock Reconciliation
        └── register, audit, promotion, balance and workflow records
```

Typical startup calls `esafepos.api.session.get_bootstrap`, which supplies the selected POS Profile, register state, payments, currencies, settings, promotions, and catalog context. The client fetches/searches catalog data and updates the cart locally. On checkout, the client sends a sale request through `esafepos.api.sales`; the server validates the cashier's access, profile, current register, prices, promotions, serials, payment rules, and other enabled safeguards before creating the ERPNext invoice. The client receives the posted invoice/receipt and refreshes local stock and shift summaries.

### Important boundaries

- `esafepos/promotions/engine.py` is a pure Python rules engine. `frontend/src/promotions.js` mirrors it for immediate cart feedback. The server-side calculation is authoritative.
- ERPNext is the system of record for posted sales, returns, stock, and accounting. EsafePOS DocTypes retain workflow-specific state and audit details.
- `esafepos/public/pos/` is generated by Vite. Edit `frontend/src/` and rebuild; do not make source edits directly in generated output.
- ERPNext-version-sensitive behavior belongs behind `esafepos/erpnext_compat.py` where practical.

## 4. Frontend route and component catalog

### 4.1 Application shell and routes

`frontend/src/main.js` creates the Vue app, Pinia instance, and hash router. `frontend/src/App.vue` owns the shared shell, top bar, offline state, outlet switcher, help, lock overlay, and cross-screen navigation. The `/display` route intentionally renders without the normal till shell or bootstrap.

| Route | View | Responsibility |
|---|---|---|
| `/` | `SellView.vue` | Product search/grid, cart, customer and checkout actions |
| `/history` | `HistoryView.vue` | Search/browse posted sales; start refund, exchange, or reprint workflows |
| `/customers` | `CustomersView.vue` | Customer lookup, account balances, statements/reports, and customer-facing actions |
| `/invoices` | `InvoicesView.vue` | Build and submit a named-customer ERPNext Sales Invoice without a register session |
| `/holds` | `HoldsView.vue` | Find and manage layaways, installments, completion, and cancellation |
| `/register` | `RegisterView.vue` | Open, monitor, reconcile, and close a register session |
| `/insights` | `InsightsView.vue` | Management reports and scoped dashboards |
| `/settings` | `SettingsView.vue` | In-POS configuration and permissions-aware setup |
| `/printing` | `PrintingView.vue` | Permission-aware Labels, Receipt, Printers and Print jobs workspace; `/labels` redirects to its Labels section |
| `/count` | `StockCountView.vue` | Count stock and coordinate with shared EsafePOS Stock sessions |
| `/display` | `CustomerDisplayView.vue` | Customer monitor, synchronized over `BroadcastChannel` |

### 4.2 Shared Vue components

| Component | Responsibility |
|---|---|
| `NavRail.vue` | Main navigation, theme toggle, current screen navigation |
| `InvoicesView.vue` | Customer, item, quantity, and note entry for standard non-POS Sales Invoices |
| `Icon.vue` | Shared inline icon set |
| `ProductGrid.vue`, `ItemDetailModal.vue` | Three sell-screen layouts, progressive catalog rendering and item quantity, price and discount edits |
| `CartPanel.vue`, `CartLine.vue` | Cart summary, editable item controls, complete-bundle quantity and discount controls |
| `PaymentOverlay.vue`, `PaymentBrand.vue` | Tender entry, payment method display, split payments and checkout; independent fresh credit eligibility, visible retryable errors and confirmed-total gating |
| `CustomerModal.vue`, `CustomerCredit.vue` | Customer selection/creation and account/credit operations |
| `SearchSelect.vue`, `LinkPicker.vue` | Reusable searchable selection controls |
| `SerialModal.vue` | Serial-number selection and validation UX |
| `PriceCheckModal.vue` | Price and stock lookup without completing a sale |
| `SellGiftCardModal.vue` | Gift card sale/issuance workflow |
| `HoldModal.vue`, `ParkedSalesModal.vue` | Create a hold and retrieve parked sales |
| `RefundModal.vue`, `RefundApproval.vue`, `ApprovalsModal.vue` | Return selection, approval state, and pending approval queue |
| `CashOutApproval.vue`, `PasscodeModal.vue` | Protected cash movement and supervisor PIN entry |
| `OpenRegisterOverlay.vue`, `XReportModal.vue`, `VarianceReason.vue` | Register opening prompt, mid-shift summary, and close variance reason |
| `ReceiptModal.vue`, `ReceiptView.vue` | Receipt preview, optional post-checkout Esafe output, explicit browser/server-network/Print Format printing and permission-checked reprints |
| `printing/ReceiptSettings.vue`, `printing/PrinterSettings.vue` | Receipt defaults/outlet adjustments, preview/custom fields, POS Profile printer/format configuration and diagnostic printing inside Printing |
| `printing/EsafePrinterSetup.vue`, `printing/EsafeJobs.vue` | Native approval/discovery, per-outlet business defaults, workstation roles/driver options, diagnostic test/preview, recent intent recovery and explicit document browser fallback |
| `OfflineLogModal.vue`, `StorageWarning.vue` | Queue status/details and local storage warning |
| `LockOverlay.vue` | Till lock and unlock screen |
| `HelpPanel.vue`, `HelpCard.vue`, `TourOverlay.vue` | Context help, new-user guidance, and guided tours |
| `ReportFilters.vue`, `PeriodHint.vue` | Shared reporting date/scope controls and date guidance |
| `CashiersPanel.vue`, `OutletsPanel.vue`, `ProfitPanel.vue`, `CustomerReportPanel.vue`, `SalespeoplePanel.vue`, `SalespeopleTable.vue` | Insights report subpanels |
| `PriceListEditor.vue`, `ScopePicker.vue` | Price book editing and outlet/company scope selection |

### 4.3 Client state and utility modules

| File | Responsibility |
|---|---|
| `stores/session.js` | Bootstrap, identity, outlet/profile, shift, settings, permissions, connectivity and queued work |
| `stores/catalog.js` | Paginated live catalog browsing, offline cache lookup and stock updates |
| `stores/cart.js` | Current sale, lines, customer, coupon, discounts, totals and complete-bundle count/discount updates |
| `stores/help.js` | Help panel and guided-tour state |
| `api.js` | Frappe method calls, request errors and offline-aware request handling |
| `appUpdates.js` | Poll deployed shell revisions, validate updated page/assets, update the worker and reload only when current work is safe |
| `offline.js` | IndexedDB schema, local queue, pending customer records, shift cache and sync locks |
| `promotions.js`, `discounts.js` | Client promotion evaluation/suggestions and discount breakdown helpers |
| `refund.js`, `refundApproval.js` | Return calculations, offline eligibility and approval policy helpers |
| `barcode.js`, `scanGuard.js`, `labels.js` | Shared barcode/scale parsing and scanner guard; `labels.js` re-exports the modular label engine |
| `labels/stock.js`, `labels/design.js`, `labels/render.js`, `labels/printing.js`, `components/labels/LabelNumberField.vue` | Physical stock/slot geometry, editable designs, validated SVG scenes, PDF/browser/native-file output, retired-route normalization and unit-aware numeric controls |
| `customerDisplay.js`, `displayContact.js` | Per-till cart and receipt snapshots, scoped contact prompts and customer lookup lifecycle |
| `receiptPrint.js`, `receiptOptions.js` | Browser print sizing and shared POS receipt footer |
| `printing/esafe.js`, `printing/journal.js`, `printing/documents.js`, `printing/index.js` | Singleton SDK lifecycle/scopes, cross-tab immutable print intents, IndexedDB recovery/deduplication, self-contained Unicode HTML, authorized native receipt/document/report dispatch |
| `format.js` | Currency, date/time, number, and display formatting |
| `theme.js`, `i18n.js`, `messages.js`, `locales/` | Theme selection, locale/RTL initialization, translations |
| `help/content.js` | Screen-level help and tour content |

## 5. Backend modules and API domains

### 5.1 HTTP/API modules (`esafepos/api/`)

| Module | Domain |
|---|---|
| `session.py` | Authentication checks, bootstrap, outlet/profile context, active shift access |
| `catalog.py` | Product catalog, search, stock/availability and price lookup |
| `sales.py` | Sale quote/submission, resolved rate/discount freezing, invoice creation, validation, receipt data and idempotency |
| `register.py` | Open/close, cash movements, counts, shift summaries, consolidation and recovery |
| `customers.py`, `credit.py`, `loyalty.py` | Customer lookup/details, outlet-authorized checkout credit checks, credit operations and wallet balances |
| `discounts.py`, `approval_requests.py`, `pin.py` | Discount computations, supervisor approval requests and PIN operations |
| `exchanges.py`, `refund` logic in sales/register | Exchange quotes/submission and return/posting integration |
| `layaway.py` | Layaway quote/create, deposits, installments, complete, cancel and list |
| `settings.py`, `permissions.py` | Settings endpoints, capability checks and administrative configuration |
| `printing_settings.py` | Narrow receipt-default saves, scoped printer/format and Esafe business-default writes, workstation-setup permission gate and bounded diagnostic receipt submission |
| `esafe_printing.py` | Authorized PDF/raw preparation and browser print view, metadata-only original/reprint registration, owner-checked client outcome reporting and installed-version diagnostics; no transaction reposting |
| `reports.py`, `insights.py`, `salespeople.py` | Sales and management reporting, dashboards, salesperson rollups |
| `printing.py`, `labels.py` | Receipt printing/reprints and label product/pricing data |
| `audit.py`, `help.py`, `system_check.py` | Audit history, help/tour state, configuration and operational diagnostics |
| `stock_app.py` | Shared stock count, devices, merge and reconciliation integration |

### 5.2 Business rule and integration modules (`esafepos/`)

- **Offers and pricing:** `promotions/engine.py`, `promotions/loader.py`, `price_books.py`, `coupons.py`, `cashback_rules.py`, `cashback.py`, `scale_barcode.py`.
- **Money and customer balances:** `currency.py`, `store_credit.py`, `gift_cards.py`, `credit_sales.py`, `deposits.py`, `paid_in.py`.
- **Sales lifecycle:** `exchanges.py`, `refund_approval.py`, `return_restrictions.py`, `payment_restrictions.py`, `cash_out.py`, `variance.py`.
- **Scope and compatibility:** `scope.py`, `outlets.py`, `reports_access.py`, `erpnext_compat.py`, `accounting_periods.py`, `inter_company.py`, `internal_accounts.py`.
- **Setup and presentation:** `install.py`, `hooks.py`, `customer_form.py`, `receipt_options.py`, `digital_receipts.py`, `languages.py`, `service_worker.py`, `demo_data.py`.
- **App-name upgrade:** `site_upgrade.py` moves the site registration, POS roles, settings records, app-owned custom fields and scheduler references before the first migration to ESAFE POS.

### 5.3 Frappe hooks and scheduled work

`esafepos/hooks.py` declares app registration, app-screen permission, website routing, the `/sw.js` page renderer, DocType hooks, installation/migration setup, and scheduled jobs. Current scheduled jobs include stuck register-close reconciliation, overdue-shift notification, cashback expiry/accrual, inter-company balance settlement, and daily automatic currency rates. `after_migrate` runs setup enforcement so roles and custom fields stay in place after updates.

## 6. Persistent data model

ERPNext standard documents remain central: `POS Invoice`, `Sales Invoice`, `POS Opening Entry`, `POS Closing Entry`, `Payment Entry`, `Stock Reconciliation`, `Stock Entry`, `Sales Order`, `Customer`, `Item`, and their standard child records. EsafePOS's DocTypes provide configuration and POS-specific workflow state.

The table below groups the DocTypes present under `esafepos/esafepos/doctype/`. Child DocTypes are marked where their purpose is clear from their names; actual parent links and fields are defined in the adjacent JSON schema files.

| Group | EsafePOS DocTypes | Purpose |
|---|---|---|
| Core configuration | `EsafePOS Settings`, `EsafePOS Company Setting`, `EsafePOS Profile Receipt`, `EsafePOS Payment Method Rule`, `POS Delivery App`, `POS Sale Currency`, `POS Customer Form Field` | Site/company settings, receipt configuration, tender policy, delivery channels, currencies, customer form schema |
| Label printing | `EsafePOS Label Preset`, `EsafePOS Label Print Job` | Outlet-scoped stock/design/printer/setup configurations and private job snapshots/results; `label_config.py` validates bounded declarative configuration |
| Native printing audit | `EsafePOS Print Intent` | Source/owner/workstation, immutable payload hash, original identity, reported native job/state and reprint link; unique original receipt guard, no full payload/private keys. POS Profile holds five Esafe business defaults via repeatable custom-field setup |
| Registers and shifts | `POS Register Session`, `POS Register Payment Count`, `POS Cash Movement`, `POS Session Day`, `POS Session Float`, `POS Session Rate`, `POS Shift Invoice`, `POS Shift Schedule`, `POS Shift Schedule Slot`, `POS Variance Reason` | Shift lifecycle, counts, movements, multi-day/multi-currency context, schedule and close variance |
| Promotions and prices | `POS Promotion`, `POS Promotion Item`, `POS Promotion Profile`, `POS Promotion Customer Group`, `POS Coupon`, `POS Price Book`, `POS Price Book Item`, `POS Bundle`, `POS Bundle Item`, `POS Quick Key` | Offers, eligibility child rows, coupon references, price books, bundles and quick-key configuration |
| Sales workflows | `POS Parked Sale`, `POS Layaway`, `POS Layaway Item`, `POS Layaway Payment`, `POS Approval Request`, `POS Refund Rule`, `POS Return Restriction`, `POS Return Reason`, `POS Payment Restriction` | Parked carts, holds/deposits, approval queue, return and payment policy |
| Balances and benefits | `POS Gift Card`, `POS Gift Card Entry`, `POS Store Credit Entry`, `POS Cashback Rule`, `POS Cashback Rule Item`, `POS Cashback Rule Profile`, `POS Cashback Rule Customer Group`, `POS Cashback Entry`, `POS Inter Company Settlement` | Gift cards, store credit, cashback configuration/ledger and inter-company settlement state |
| Access, audit and stock count | `EsafePOS Audit Log`, `EsafePOS User PIN`, `POS Discount Approver`, `POS Capability Rule`, `POS Count Session`, `POS Count Device` | Audit trail, cashier PIN, approvers/capabilities, shared stock count sessions and participating devices |

> The source DocType JSON files are the schema authority. This grouped overview is descriptive; consult each DocType's JSON and controller before changing fields, permissions, autonames, or child-table relationships.

## 7. Feature lifecycle and integrity rules

1. **Authorize before acting.** Resolve the user and POS Profile, then apply role/capability, company, outlet, register ownership, and ERPNext DocType permission checks.
2. **Quote from current context.** Use the selected outlet's price list, customer group, channel, currency, and active shift rates.
3. **Treat local calculations as provisional.** Cart calculations improve speed and clarity; server submission repeats checks against current ERPNext state.
4. **Post using ERPNext documents.** Sales and returns flow through ERPNext invoice documents; stock and accounting changes are handled by ERPNext posting.
5. **Record POS workflow state and audit.** Shift ownership, expected cash, approvals, promotion detail, and operational events are held in EsafePOS records.
6. **Make offline retries safe.** Queue stable sale payloads with identifiers, serialize uploads where possible, and recognize duplicate submissions by idempotency key.
7. **Respect asynchronous close.** Consolidation may retry; a failed/unfinished close must remain diagnosable and recoverable rather than silently disappearing.

## 8. Project logbook / release milestones

Entries are summarized from the release notes. The [user guide changelog](user-guide.md#19-changelog) contains the full release-by-release wording and should be updated alongside each release.

### Unreleased
- **Sales Rep Mode:** Added a master switch and separate ERPNext automatic discount and customer-sales-progress switches. ERPNext Pricing Rules can be resolved in the shared POS, quotation and regular-invoice builder; the cart quote supplies the server-confirmed total and rule labels. A permission-scoped customer progress API and responsive panel show the ERPNext document path, outstanding, undelivered Sales Order quantities, receipts by tender/reference/date, and open customer ToDos. Customer profile totals now tolerate an uninstalled invoice-origin custom field, as shown in the live-site screenshot. The settings fields require site migration; live Pricing Rule and document reconciliation still need site verification.
- **Customer payment overages:** The cashier can opt to leave money above selected invoice balances as unallocated customer credit. The receipt records the full drawer movement, applies only the invoice amount, and leaves the remainder on the same receivable account for ERPNext Payment Reconciliation. `api/credit.py` computes and returns the unapplied amount; `CustomerCredit.vue` shows the available POS advance and receipt line. The customer payment form wraps for phone and tablet widths.
- **Printing integration:** QZ Tray was removed on 2026-11-22. Receipts use server-network, ERPNext Print Format or browser printing; labels use browser printing and file exports. The separate Print Manager will be integrated later. Retired connector setup/signing fields and endpoints are no longer available.
- **Receipt branding and Table layout:** Built-in receipts show `ESAFE ERP+POS - pos.esafe.lk` automatically. The Table template adds a light grid and can be selected for all outlets or saved as an outlet override.
- **Item price access:** System Managers and EsafePOS Managers can edit saved selling prices when their ERPNext permissions allow it. Managers can delegate the POS capability to a role or person under Approvals and permissions. Item name and photo edits use ERPNext Item permissions.
- **Items editor:** Added category and brand filters, product image upload and a selling price-list selector. Item photos are attached to ERPNext Item records and unit prices are saved to the selected ERPNext price list.
- **Product catalog paging:** Sell loads live item pages while online, even with a limited offline cache. The Items editor can load results beyond its first 50 products.
- **Customer display and membership keypad:** Added a welcome screen and cashier-triggered contact popup for exact customer lookup. A new number can be used as the receipt contact for a walk-in sale. The live display highlights the latest item with automatic offline icons and shows pinned totals, savings and rewards.
- **Shared stock for loose and packed sales:** Checkout uses ERPNext unit conversion and a separate selling price per alternate unit. The POS Items page edits standard item names and outlet price-list entries. Offline scale decoding honors the switch and format configured in General settings.
- **Walk-in customer codes:** The opt-in General setting lets cashiers complete sales without selecting a customer. ERPNext bills the customer configured on the POS Profile or the shared ESAFE POS Walk-in record. Each anonymous sale receives a receipt code. Staff with customer create or write access can open a submitted sale from History or Customers, save the contact number as the invoice display name, and add a name later.
- **Link walk-in receipts to customers:** An opt-in setting adds **Add customer to invoice** to unassigned, submitted POS receipts. The linked customer's POS transactions and purchase totals include the sale and its refunds.
- **Catalog views and customer display:** Added List, Images and Images and full descriptions modes, quick Add and a stock-unit-aware item editor. The customer display is read-only and shows live savings, checkout balance, receipt and rewards.
- **App rename:** ESAFE POS ships under the `esafepos` package and continues to open at `/pos`. Existing sites use the [one-time upgrade](esafepos-upgrade.md) and sync each till before switching browser databases.
- **Weight-embedded scale barcode reading:** Added support for variable-weight scale barcodes (EAN-13 and UPC-A using standard in-store prefixes `20`–`29`, `02`). The scanner automatically parses the item PLU/code and decimal weight, looks up the item (via prefix+PLU, PLU, or stripped PLU in `Item Barcode` and `Item`), and adds the item to the cart with the exact measured quantity. Supported both online (in `resolve_scan` and `price_check`) and offline (in IndexedDB `searchCatalog` and `SellView`). Configurable in `EsafePOS Settings` (enable/disable, custom prefixes, PLU length 4/5, decimal places).

| Release | Milestone |
|---|---|
| 0.69.0 | Added stock count from the till, including standalone reconciliation drafts and shared count integration with stock-app devices; open-shift stock holds guard saves and merges. |
| 0.68.x | Delivered the EsafePOS Stock app workflows for shared counts, stock documents, approvals and barcode linking; fixed open-shift holding behavior and count recovery. |
| 0.67.0 | Added roll/A4 barcode and price label printing from scans, documents, or changed prices. |
| 0.66.0 | Added payment reporting in each transaction currency and persisted the amount tendered in foreign currency. |
| 0.65.0 | Added reports-only access for management users without a cashier POS Profile. |
| 0.64.0 | Added outlet grouping across registers, outlet-scoped reporting, and register/outlet diagnostics. |
| 0.63.0 | Added refund approval policy, passcode/approval-tray paths, and server-side revalidation. |
| 0.62.0 | Added Insights sales summary, cashier, product, profit, customer, and outlet reports with permissions. |
| 0.61.x | Added app-screen/desk integration, stronger cash-out controls, shift-ownership defaults, customer debt/hold separation, and foreign-currency support improvements. |
| 0.60.x | Added sales on account, customer credit ledger interactions, and supporting shift behavior. |
| 0.58.x–0.59.x | Added contextual help, guided tours, update notices, and expanded till help workflows. |
| 0.57.x | Added configurable salesperson requirement/off behavior and salesperson reporting. |
| 0.55.x–0.56.x | Improved overnight shifts, recovery of offline refusals, cross-currency sales, price edits, and stock availability after same-shift returns. |
| 0.53.x–0.54.x | Expanded localized UI/server messages and currency/receipt handling; tightened serialized item validation and cart presentation. |
| 0.52.x | Improved Frappe/ERPNext 16 compatibility, permissions, register operation, and resilience. |
| 0.50.0 | Added layaway/holds, deposits, reserved stock, installments, hand-over, cancellation, and deposit accounting. |
| 0.49.x | Added full offline app-shell support so the till can reopen without a connection on supported versions. |
| 0.47.x–0.48.x | Added one-step exchanges, configurable role/user capabilities, and the first consolidated permission model. |
| 0.46.x | Improved live stock, network recovery, and Arabic/interface polish. |
| 0.4.x and earlier foundation | Established the Vue/Frappe till, POS Invoice/register flow, promotions engine, price books, channels, customer management, local-first catalog, salespeople attribution, and initial settings/workspace integration. |

### Unreleased logbook

Validation note for the 2026-11-22 account-checkout/app-update repair: Python 3.7 grammar and all frontend endpoint references pass, including both new endpoints. The full `scripts/check_endpoints.py` guard still reports 41 keyword-scan findings; an AST comparison verified that every flagged call also exists unchanged in `HEAD`. This general guard is not recorded as passing.

| Date | Change | Impact |
|---|---|---|
| 2026-11-22 | Restored the on-account option and added automatic app updates. | `sales.quote_sale` referenced `erp_pricing_rules` outside its scope, raising `NameError` with native discounts both enabled and disabled. It now reads resolved pricing flags from the invoice. `api/credit.checkout_credit` supplies fresh eligibility independently after sell/outlet authorization; `PaymentOverlay.vue` handles missing quote credit, stale bootstrap switches and failed checks with visible errors/Retry. `stores/cart.js` retains quote errors, and debt tender waits for a confirmed total. `api/session.app_revision` exposes the deployed content fingerprint; `www/pos.html` exposes the loaded revision and disables worker update HTTP caching. `appUpdates.js`/`App.vue` check every 15 seconds and on focus, visibility return or reconnect; they validate the new page/assets, update the worker, and reload idle tills. Current carts, checkout/dialogs, editable screens, sync and active printing defer reload with a banner. No business data/cache queue is cleared and no schema is added. Existing pre-updater apps need one reopening; deployment must serve the new assets/backend before automatic checks can see a Git change. Verified: 64 standalone Python pricing/quote, checkout-authorization, discount, bundle/UOM and promotion tests; `node update-check.mjs`; Chrome `checkout-check.mjs`, `update-browser-check.mjs`, `update-layout-check.mjs`; production build. Browser checks include full/split account sales, refusal/limits, missing facts, failed pricing/credit and retry, network-loss queue protection, two open windows updating within the same release, deferred reload, incomplete deployment retry, cache replacement and offline reopening. The actual App banner fits desktop/mobile and clearing the basket triggers reload. [Credit retry](screenshots/checkout/credit-retry-mobile.png), [update desktop](screenshots/updates/update-1440.png), [update mobile](screenshots/updates/update-390.png). Read-only live inspection confirmed enabled credit settings, a named customer with credit available, and the missing checkout option; no live accounting transaction was submitted. Browser testing uses local fixtures. Worker cache behavior follows the [browser registration API](https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerContainer/register). |
| 2026-11-23 | Connected Esafe Printer Manager and implemented silent printing. | Vendored/pinned the actual private SDK 0.1.0, one Vue service and browser journal; native discovery/approval requests only exact selected printer IDs across saved outlets. Added connection/role/default/driver/test/preview UI and Print jobs, five POS Profile defaults and metadata-only `EsafePOS Print Intent` with original/reprint ownership and source/outlet checks. Checkout receipts dispatch only after successful callbacks; PDF invoices/quotations, label PDFs, X-reports and payment receipts reuse existing authorized content. Persisted bytes/keys, Web Locks, native job reconciliation and explicit retries/new-copy reprints prevent implicit duplicate output. Uncertain native jobs never trigger automatic browser fallback; offline behavior is preserved. SDK browser identity/private keys stay local. Existing IP/format preferences remain; legacy printer name is a review hint. Added operational docs and updated architecture/inventory. Verification: clean `npm ci --ignore-scripts --no-audit --no-fund` and `npm run build`; SDK orchestration and actual-SDK Chrome checks (signed authentication, exact scopes, approval revocation, workstation/outlet isolation, 58/80 mm Unicode HTML, automatic dedupe, new-key reprint, PDF document dispatch/failure fallback); existing checkout, receipt, Printing workspace and label Chrome regressions; label geometry/barcodes; 44 standalone Python checks (13 Esafe API/migration, 4 defaults, 10 label configuration, 10 Printing API and 7 label permission); Python 3.7 grammar, DocType JSON, endpoint-reference, private dependency and no-QZ bundle scans. Offline-only npm installation lacked a cached public Vue Router package; the normal clean install succeeded and the private SDK stayed vendored. The repository-wide endpoint guard retains 41 existing name-based keyword findings elsewhere, with no missing new Printing endpoint. [Setup desktop](screenshots/printing/esafe-setup-desktop.png), [assignments](screenshots/printing/esafe-assignments-desktop.png), [mobile](screenshots/printing/esafe-setup-mobile.png), [jobs](screenshots/printing/esafe-jobs-desktop.png). Real Frappe migration/accounting, Windows certificate/pairing and physical output remain staging/hardware qualification. The supplied native installer is unsigned development software. |
| 2026-11-22 | Joined receipt adjustment, labels and printer setup in Printing. | Added `PrintingView.vue` and extracted the receipt editor into `components/printing/ReceiptSettings.vue`, alongside `PrinterSettings.vue`. Renamed navigation/title/help to Printing, retained the label engine/drafts/calibration under Labels, redirected `/labels`, and removed the Receipt group/form from General Settings. Added `api/printing_settings.py` for receipt-only default saves, authorized POS Profile host/port/compatible Print Format configuration and a bounded test without a cash-drawer pulse. General Settings preserves receipt fields when omitted, and outlet receipt saves include cashier/terminal/invoice-barcode controls. Existing Settings, label, outlet and POS Profile write permissions are enforced; no new DocType/schema. Verification: production build, label geometry/Chrome label/Chrome receipt checks, 10 standalone Printing API tests, Python 3.7 grammar, Printing endpoint-reference checks and diff checks passed. Chrome Printing checks cover legacy navigation, default/outlet receipt saves/reset, preview printing, preserved label drafts, printer save/test, permission isolation and desktop/tablet/mobile widths. [Receipt desktop](screenshots/printing/workspace-receipt-desktop.png), [receipt mobile](screenshots/printing/workspace-receipt-mobile.png), [printers desktop](screenshots/printing/workspace-printers-desktop.png), [printers mobile](screenshots/printing/workspace-printers-mobile.png). The repository-wide endpoint guard still reports 41 name-based keyword findings in other existing modules/tests; it reports no missing Printing endpoint. Live Frappe/profile persistence and physical printing remain unverified. |
| 2026-11-22 | Fixed full-value false discounts and account checkout. | `api/sales.py` enables the selected native pricing engine before ERPNext fills defaults, calculates native rates before reading them, then freezes consistent rate, discount amount and percentage fields. An unresolved zero rate can no longer become an unintended 100% discount; genuine free-item rules remain valid. This also restores the payable used to reconcile full/split account sales and prevents rejection as change from debt. The cart quote accepts a fresh-request option; `PaymentOverlay.vue` uses it for account checkout so cached basket quotes cannot supply stale credit facts. The cart refuses to queue an account sale after network failure and preserves the basket for retry. No schema change. Verification: 60 standalone Python sales-pricing, manual-discount, bundle/UOM and promotion tests; 23 browser/Python promotion parity scenarios; Chrome `checkout-check.mjs`, `discount-check.mjs` and `receipt-check.mjs`; production build; Python 3.7 grammar and diff whitespace checks. New checkout checks cover full/split account tenders, fresh limits, refusal, network loss without queuing, full-price and partial-discount receipts, and desktop/mobile layouts. Existing receipt checks cover thermal formats, printing, customer editing and history lookup. [Checkout desktop](screenshots/checkout/checkout-desktop.png), [checkout mobile](screenshots/checkout/checkout-mobile.png), [receipt desktop](screenshots/checkout/receipt-desktop.png), [receipt mobile](screenshots/checkout/receipt-mobile.png). Browser/API fixtures and mocked Python document I/O were used; live ERPNext posting and historical zero-total invoices need site verification/review. |
| 2026-11-22 | Removed QZ Tray pending separate Print Manager integration. | Removed the Receipt Settings setup/import, receipt/label connector dispatch, JavaScript connector source and rebuilt public asset, receipt/label signing APIs and QZ certificate/key DocFields. Labels retain browser/PDF/ZPL/TSPL output; saved local/shared connector printer profiles normalize to browser output with incompatible offsets/scaling reset. Existing server-network receipts, ERPNext Print Formats and reprint permission checks remain. Updated the guide, component inventory and both printing plans. Verification: `cd frontend && npm run build`, `node label-layout-check.mjs`, `node barcode-check.mjs`, `node label-browser-check.mjs`, `node receipt-check.mjs`, 10 label-configuration unit tests, 7 standalone label-permission tests, Python 3.7 grammar/settings JSON checks, retired connector/asset scans and diff whitespace checks passed. Mocked Chrome checks cover legacy profile load/application, browser label jobs without connector calls, Receipt Settings cleanup, desktop/mobile screenshots, PDF/native output and barcode/QR decoding. [Settings desktop](screenshots/printing/receipt-settings-desktop.png), [Settings mobile](screenshots/printing/receipt-settings-mobile.png), [label printer desktop](screenshots/printing/label-printer-desktop.png), [label printer mobile](screenshots/printing/label-printer-mobile.png). The Frappe-dependent `esafepos.api.test_printing` suite could not run because this workspace has no Frappe installation. Run site migration to synchronize removed settings fields; live printer/site testing remains outstanding. |
| 2026-11-20 | Built the thermal-first label designer and multi-column printing module. | Added stock/design/render/output modules and a responsive queue/preview/settings UI, metric/inch layouts and gaps, side/rotated/QR/logo designs, element editing, calibration, saved setups, server snapshots and label-specific QZ signing. New Label Preset/Print Job DocTypes require migration. Updated the user guide and module plan. Verified the production build, label/barcode checks, 17 standalone Python tests, Python 3.7 grammar and mocked Chrome/PDF/QZ/decoder checks. Physical device/live Frappe integration remain unverified. |
| 2026-11-20 | Planned POS Print Manager and a custom Windows bridge. | Added `docs/print-manager-and-windows-bridge-plan.md` with local Windows queue discovery, till-side direct-IP printing, purpose-specific bindings, recommended .NET tray architecture, trusted WSS and pairing lifecycle, bounded server-signed intents, durable delivery/reprint semantics, proposed records/API/component boundaries and phased receipt/label/document delivery. Existing QZ, browser and server-network routes remain migration adapters; label snapshots remain in the label module. Reviewed repository code and official Microsoft/Chrome references; documentation links and diff whitespace checked. Documentation only; no runtime tests, bundle rebuild, installer or physical printer checks. |
| 2026-11-20 | Planned the expanded Label Printing Module with thermal rolls prioritized. | Added `docs/label-printing-module-plan.md` with stock geometry and editable size presets, double/triple/custom columns and gaps, logo and side-barcode design options, separate scaling controls, printer calibration, proposed persistence/API boundaries, label-specific QZ authorization and payload limits, phased delivery and automated/physical acceptance checks. The plan was reviewed against the existing implementation and official GS1/QZ references. Documentation-only change; diff checks performed, with no runtime tests, generated-asset rebuild or real-device verification. |
| 2026-11-20 | Integrated QZ Tray for local Windows receipt printing. | Bundled the installed QZ Tray JavaScript connector and added `qz_printing.py` endpoints for receipt data, trusted certificate retrieval, private-key request signing and manager-only credential storage. `QzTraySetup.vue` connects to QZ Tray, discovers/chooses printers, prints a test, and uploads signing files through secure settings APIs. `ReceiptModal.vue` uses the selected local printer before network/browser printing when the built-in receipt is active. The QZ credential pair is validated and the private key is stored as an encrypted Password field. User guide updated. Production build and diff checks passed; site migration and live printer/signing verification remain required. |
| 2026-11-20 | Added Sales Rep Mode and ERPNext-backed customer sales progress. | `features.py`, EsafePOS Settings, and `SettingsView.vue` add an independent master switch with child switches. `sales.py` uses ERPNext Pricing Rules to resolve cart/invoice values when enabled, reports the server quote in the POS and prevents the EsafePOS automatic promotion engine from discounting the same items again. `customers.py` scopes Quotation, Sales Order, Delivery Note, Sales Invoice, Payment Entry, POS tender and ToDo data to the customer/company and permissions. `CustomerSalesProgress.vue` renders the pipeline and totals for desktop/tablet/phone. `customer_detail` checks whether the invoice-origin field exists before using it, removing the unknown-column failure on unmigrated sites. User and website guides and the implementation plan were updated. The production frontend build succeeded. Python compile was unavailable because this environment has no accessible Python executable; site migration and live accounting/Pricing Rule checks remain required. |
| 2026-11-20 | Added optional excess customer payment credit. | `api/credit.py` allocates up to the selected invoices and posts any opted-in remainder as an unallocated Customer receivable credit. The receipt states the credit amount and the Customers card shows the remaining POS advance. ERPNext Payment Reconciliation can apply it to a future invoice. Cashier still needs an open register and payment permission. Updated the guide and rebuilt the production bundle successfully. No live ERPNext posting was available in this workspace. |
| 2026-11-16 | Refresh the POS editor cache on changed builds. | Osaka's live JavaScript contained the new image-link editor, but older and newer builds shared an immutable URL. The POS page now versions its JavaScript, CSS and service worker with a content fingerprint alongside the release number. The worker uses the new revision for its offline shell cache. Verified the live asset contents and cache headers, the local build, unit tests for changed and missing assets, and a same-version update followed by an offline reload in Chrome. |
| 2026-11-16 | Added product image search and optional Gemini assistance. | POS Items opens Google Images with item name, brand and barcode, and the existing Link option saves the selected image. Settings → General → Product image search can enable Gemini to refine search terms. The key is stored in an encrypted Frappe Password field on EsafePOS Settings and write permissions guard configuration and Gemini requests. No paid grounding or image-generation calls are made. Verified the production build, 10 mocked backend tests, and Chrome checks for Settings and image search. Requires a site migration for the settings fields and a live Gemini check after setup. |
| 2026-11-16 | Added an image Link option to POS Items. | `ItemsView.vue` previews a direct HTTPS image link beside the existing device upload option. `items.py` validates the address and saves it to ERPNext's existing Item image field with the native Item write permission and existing audit trail. The server stores the URL without fetching the image. Verified the link and device flows in Chrome with mocked data and added tests for link validation and write permissions. |
| 2026-11-16 | Fixed the shop name overlapping header controls. | `App.vue` reserves a header column for the curved shop badge and wraps controls as space gets tight. Long names truncate with the full name available on hover. Verified the Sell header with a populated toolbar, an open shift and an outlet selector at seven Chrome viewport widths from 320 to 1908 pixels. |
| 2026-11-16 | Adopted the teal P and sparkle as the POS app icon. | The shared SVG is used in the POS navigation, browser tab, and Frappe app launcher. The install manifest includes the SVG and matching 192 px and 512 px PNGs, with a PNG for Apple home screens. The offline shell preloads the new assets. Verified Chrome rendering, the production build, and icon references. |
| 2026-11-16 | Stabilized cart overflow and checkout actions. | `CartPanel.vue` gives the cart a bounded height, keeps item rows in their own scroll region, limits the details and totals section, and reserves separated space for action and checkout buttons. Verified the production build and narrow-cart layout. |
| 2026-11-16 | Centered the shop name in a modern curved header badge. | `App.vue` keeps the company name visually centered across the desktop header with a softly bordered pill, while retaining a compact inline version on phones. Verified the production build and desktop and mobile Settings layouts. |
| 2026-11-16 | Moved the ESAFE logo to the top of the desktop navigation rail. | `NavRail.vue` and `App.vue` share `PosBrandMark.vue`. The mark stays beside the wordmark on phones, where navigation opens from a drawer. Verified the production build and Chrome checks for logo placement and navigation at desktop and phone widths. |
| 2026-11-16 | Moved Settings and Insights navigation into ERPNext-style left panes. | `NavRail.vue` uses a compact icon rail with labelled links in the phone drawer. `SettingsView.vue` nests General groups in the left pane and `InsightsView.vue` puts permitted reports there. Each pane has a section picker on phones. `App.vue` moves the theme switch and ERPNext shortcut to the top bar. Verified the production build and Chrome checks for desktop and phone navigation, General submenus, Insights selection, and permission-based visibility. |
| 2026-11-16 | Matched the cashier POS blue to the customer display. | `styles.css` shares the latest-item blue between the customer display, POS header, navigation rail and other surfaces that use those colors, including the payment header and lock screen. `App.vue`, `NavRail.vue` and `PaymentOverlay.vue` adjust foreground contrast for the new blue. Verified the production build and the header and navigation rail in light and dark mode and on phones in Chrome. |
| 2026-11-16 | Switched the customer display to the classic blue layout. | `CustomerDisplayView.vue` shows the welcome card in the left column and the large blue latest-item banner and two-column basket on the right. Available loyalty and payment details appear below the greeting. Subtotal, savings, total and balance or change stay at the bottom. `DisplayProductIcon.vue` uses blue for the default item icon. Verified the production build and Chrome checks with an 18-item desktop sale, a phone layout, and the receipt and contact flows. |
| 2026-11-16 | Put customer details and payment totals in the white display sidebar. | `CustomerDisplayView.vue` keeps the rotating shop and ESAFE branding at the top and shows customer name, loyalty points, payment methods and total paid below it. The shop frame shows the name alongside the configured logo. The sidebar stacks above the item list on phones. Verified the production build and Chrome checks for split cash and card tender, loyalty points, total paid, and the branding rotation. |
| 2026-11-16 | Added rotating shop and ESAFE branding to the customer display. | `CustomerDisplayView.vue` shows the shop's configured receipt logo or shop name in the left panel and crossfades to the ESAFE logo and ESAFE ERP POS wordmark every six seconds. The panel becomes a compact strip on phones. Reduced-motion mode shows both brands without animation. Verified the production build and Chrome checks for rotation, missing-logo fallback, reduced motion, and the customer display sale and contact flows. |
| 2026-11-16 | Matched the customer display to the POS palette and made room for more items. | `CustomerDisplayView.vue` uses POS navy and teal for the latest item, welcome screen and totals. Customer, loyalty and payment details sit in a compact strip, and the item grid spans the display. The highlighted line scrolls only as far as needed. `DisplayContactPad.vue` and `DisplayProductIcon.vue` also use POS colors. Verified the production build and Chrome display regression with a sample 18-item sale and desktop and phone layouts. |
| 2026-11-16 | Updated the header branding to ESAFE ERP POS. | `App.vue` puts the ESAFE logo in a rounded navy badge and sets the white Plus Jakarta Sans wordmark beside it, followed by the shop name. Verified the production build and the header at desktop and phone widths in Chrome with sample data. |
| 2026-11-16 | Widened the Sell cart and added a light teal background. | `CartPanel.vue` uses a responsive cart width up to 432 pixels on desktop and a theme-aware teal tint. On narrower screens the cart stacks below the catalog. Verified the production build, both themes, and checkout layout at desktop, tablet, and phone widths in Chrome with sample data. |
| 2026-11-16 | Added a hamburger menu for phone navigation. | `App.vue` adds the menu toggle and backdrop. At widths up to 700 pixels, `NavRail.vue` opens over the page and leaves the catalog full width when closed. Selecting a page, tapping outside, pressing Escape, or tapping the close button dismisses the rail. The desktop rail stays visible. Verified the production build and touch, keyboard, navigation, and desktop resize behavior in Chrome with sample data. |
| 2026-11-16 | Added a rounded ESAFE POS logo badge beside the shop name. | `App.vue` pairs the existing ESAFE mark with the uppercase wordmark. `NavRail.vue` moves the mark out of the navigation rail while keeping the menu positions. Verified the production build and the badge and shop name at desktop and phone widths in Chrome with sample data. |
| 2026-11-16 | Made more room for products on the Sell screen. | `App.vue` and `SellView.vue` place price check, customer display, and item view in the header, with brand and item group beside search. `ProductGrid.vue` uses compact cards and red plus buttons. `CartPanel.vue` moves sale retrieval, customer contact, and sale tools above cart items, shows the channel selector when delivery channels are available, and puts Pay and QT side by side. Icon controls have accessible labels and tooltips. Verified the production build, the catalog and customer display browser regression, and the Sell screen at 1908, 1024, and 390 pixels in Chrome with sample data. |
| 2026-11-16 | Put the shop name beside ESAFE POS in the header. | `App.vue` shows the current POS company's name prominently beside the uppercase ESAFE POS label. Long names can truncate on small screens. Verified the production build and desktop and mobile Chrome layouts. |
| 2026-11-16 | Updated catalog colors for price, stock and Add. | `ProductGrid.vue` uses a contrasting gold for prices, blue for positive stock and red for zero or negative stock. Add buttons have a red fill and white text across all three catalog modes. Verified the production build and both themes in Chrome. |
| 2026-11-16 | Added a translucent label behind item names in Images mode. | `ProductGrid.vue` places a theme-matched backing behind the product name, code and unit on photo cards. Verified the production build and Chrome checks for label opacity and placement in both themes and scope across photo cards, placeholders and all three modes. |
| 2026-11-16 | Added an option to link posted walk-in receipts to customer accounts. | `EsafePOS Settings` gates the action. `ReceiptModal.vue` and `CustomerModal.vue` let staff select or create a customer, with phone as an optional substitute for the individual's name. `sales.py` locks the invoice and saves the link in the indexed `POS Receipt Customer` field on POS Invoice and Sales Invoice. Customers and History attribute sales and their refunds to the linked account. ERPNext posting remains on the original billing customer. Verified the production build, 179 endpoint references, 73 Python tests, mocked linking and duplicate protection, and browser workflows for linking an existing and a new customer. Live ERPNext migration and saves still need verification. |
| 2026-11-16 | Added invoice barcodes to POS receipts and scan-to-open in History. | `ReceiptView.vue` renders the exact invoice ID in Code 128. `receipt_barcode.py` supplies the equivalent digital receipt SVG and raster output for network printers where the barcode fits the roll. `HistoryView.vue` focuses the search field and opens an exact invoice returned by the existing scoped search when Enter is pressed. Verified the build, endpoint resolution, 58 Python tests, parity across 101 IDs, and Chrome checks for 58 mm and 80 mm print output and the exact-match search. Live posting and physical scanner and printer checks remain pending. |
| 2026-11-16 | Accepted new contact numbers at the customer display. | `displayContact.js` keeps the membership lookup and accepts an unmatched number for an unassigned cart. The cashier can remove it, and the cart preserves it when parked or queued. `sales.py` and `walk_in.py` validate and save the number to the existing receipt contact and display name fields. The second screen omits the number after confirmation. Verified the production build, endpoint resolution, 63 Python tests and the browser workflow with simulated lookup and checkout. On the live Weerakoon Agro POS, a hard refresh of both screens restored phone-only entry. A fictional number appeared as Receipt contact on the cashier's cart and was cleared after verification. Live ERPNext invoice posting remains unverified. |
| 2026-11-16 | Kept contact-only invoice saves and added an optional customer name. | `ReceiptModal.vue` asks for the phone first and reveals a name field through **Add name**. `sales.py` and `walk_in.py` use the number as the default receipt name and preserve a saved name when only the phone changes. Customers, History and built-in receipts display the optional name while retaining the saved phone. Verified the production build, endpoint resolution, 65 Python tests, mocked save transitions and the browser workflow across both tabs. A read-only live check confirmed that a receipt with a saved name and contact number still appeared in the shared Walk-in customer's transactions. |
| 2026-11-16 | Added phone-only customer edits on submitted POS invoices. | `ReceiptModal.vue` exposes **Change customer name** after checkout and from Customers and History with one contact number field. `sales.py` and `walk_in.py` validate and store the number as the receipt display name in the existing invoice fields for POS Invoice and POS-origin Sales Invoice. ERPNext keeps the original billing customer. History shows and searches the saved number, the invoice contact field is indexed, and built-in print and digital receipts use the same display name. Verified the production build, API endpoint resolution, 50 existing tests, 15 walk-in and receipt tests, mocked authorization checks, and both browser entry points. Live ERPNext saves remain unverified. |
| 2026-11-16 | Fixed anonymous checkout at outlets with no default customer. | `walk_in.py` resolves selected, outlet default and shared billing customers in that order. Saving the enabled setting or migrating an enabled site provisions one shared ERPNext Customer. `sales.py`, `session.py` and `currency.py` use the same fallback for quotes, checkout and till startup. The shared customer is excluded from credit sales and loyalty redemption. Anonymous receipts retain individual `W-` codes. Verified the production build, 178 API references, 50 existing Python tests and eight mocked walk-in tests. Live ERPNext checkout is pending. |
| 2026-11-15 | Added the default ESAFE receipt footer and a lightly lined Table template. | `ReceiptView.vue`, `receiptOptions.js`, `receipt_options.py`, and the print and digital receipt renderers append the branded line once after any custom text. Customer payment receipts and the completed customer display also show the line. The Table template is selectable in `EsafePOS Settings` and in outlet overrides. Browser and digital receipts use thin borders, and ESC/POS uses a character grid on both roll widths. ERPNext Print Formats supply their own footer and layout. Verified the production build, 178 API references, 50 existing Python tests, three thermal and footer tests, and Chrome receipt PDFs at 58 mm and 80 mm and the customer display. Physical printer output and live ERPNext remain unverified. |
| 2026-11-15 | Restricted saved ERPNext price editing in POS. | Added the manager-default `Edit item selling prices` rule to `POS Capability Rule`, with role or person delegation in Settings. `api/items.py` and `ItemsView.vue` enforce price access separately from Item name and photo access and respect native Item Price create and write permissions. The delivery price-list endpoints apply the same POS rule and native permissions. Successful edits from Items record the unit, list, and old and new rates when POS audit logging is enabled. Verified the production build, 178 API references, 50 existing Python tests, five mocked authorization tests and the Chrome Items workflow. Live ERPNext permissions and saves still need verification. |
| 2026-11-15 | Expanded the POS Items editor with filters, images and price-list selection. | `ItemsView.vue` keeps category and brand filters beside item search and shows a photo preview in the editor. `api/items.py` applies filters to paginated item results, attaches validated images to ERPNext Items and saves standing per-unit prices to the selected enabled selling list. The POS refreshes the online and offline catalog after a save. Verified the production build, 178 API endpoint references, 50 Python tests, server image validation and the desktop/mobile Chrome workflow. Browser saves used simulated ERPNext responses. |
| 2026-11-15 | Fixed incomplete product lists on Sell and Items. | Sell reads live pages by outlet, group, brand and search while online. The offline cache is used during outages. Brand choices come from startup data as well as loaded products. The Items editor can request additional pages. The POS Profile's item groups, sellable-item checks and out-of-stock display setting still control what appears. Verified the production build, 177 API references, 50 Python tests, and Chrome checks for a second Sell page despite a limited cache, offline fallback, and Items results beyond 50. The browser used simulated ERPNext responses. |
| 2026-11-15 | Rebuilt the production POS bundle for the customer display update. | `npm run build` succeeded and regenerated the assets under `esafepos/public/pos/`. The bundle includes the welcome keypad with Skip, the cashier-triggered contact popup, automatic Lucide product icons, the latest-item highlight and pinned totals. The build is ready locally. Deployment and live ERPNext contact lookup remain pending. |
| 2026-11-15 | Added the customer welcome and refreshed the live display. | `CustomerDisplayView.vue` shows the latest item, basket, loyalty and pinned totals. `DisplayContactPad.vue` runs at the start or in a cashier-triggered popup. The catalog lookup matches existing customers by contact number with POS, outlet and customer permissions. `DisplayProductIcon.vue` bundles Lucide fallbacks. Verified the production build, 177 API endpoint references, 50 Python tests, and Chrome checks for contact lookup, skip, retry, terminal isolation, icons, repeat scans and responsive layout. The browser uses a simulated ERPNext lookup. |
| 2026-11-15 | Added priced selling units and the Items page. | `item_units.py`, the catalog and sale APIs resolve ERPNext UOM conversions and native Item Prices. The cart keeps a separate line per unit, checkout checks shared stock, and online returns identify loose and packed lines separately. `api/items.py` and `ItemsView.vue` edit display names and standing prices with ERPNext permissions. The existing scale switch and format now drive offline search. Verified the production build, API endpoint resolution, 50 Python tests, barcode and promotion parity checks, and Chrome tests for offline decoding, mixed-unit cart payloads and the item editor. Live ERPNext posting, consolidation and returns remain unverified. |
| 2026-11-15 | Added optional walk-in codes and later receipt editing. | `sales.py` assigns and searches codes on submitted POS and Sales Invoices. `install.py` adds the code, name, and phone as POS-owned invoice fields. General settings controls new assignments. History and the receipt editor support lookup and optional details, and built-in print and digital receipts show the code. Offline sales get a code when they post. Verified the production build, 173 API endpoints, 50 Python tests, and the Chrome receipt workflow with a simulated save response. Live ERPNext posting and migration remain unverified. |
| 2026-11-15 | Added three catalog modes, an item editor and a read-only customer display. | `SellView.vue`, `ProductGrid.vue`, `ItemDetailModal.vue` and the catalog store handle progressive loading and permitted cart edits. The catalog API exposes ERPNext stock units and whole-unit rules. `App.vue`, `PaymentOverlay.vue` and the receipt API supply line discounts, payments, tax, savings, change and rewards over the per-till display channel. Removed the contact entry flow. Verified the production build, endpoint resolution, 50 Python tests, and desktop/mobile browser checks for catalog, display, discounts and receipts. Browser checks use fixtures. |
| 2026-11-14 | Renamed the application to ESAFE POS and moved its Python package, six named DocType controllers, Desk definitions and built frontend to `esafepos`. | Updated API and asset paths, roles, POS-owned field names and browser storage. Added an [in-place site upgrade](esafepos-upgrade.md) for existing settings, permissions, audit logs and POS records. Verified the production build, Python 3.7 syntax, DocType metadata and controller discovery, 50 Python tests, endpoint resolution, scheduling, frontend parity, and browser checks for discounts, receipts and customer display. The site upgrade still needs verification on a restored ERPNext site. |
| 2026-11-09 | Established a standing project-documentation rule: every project change and upgrade updates this logbook in the same change. | Added the rule to the repository guidelines so it persists across future work. |

### Current engineering focus areas

- Maintain behavior parity between Python and JavaScript promotion evaluators.
- Preserve Frappe/ERPNext 13–16 compatibility, especially invoice consolidation, serial bundles, and register closing behavior.
- Keep offline queue semantics safe across retries, tabs, and service-worker updates.
- Keep user-facing permissions and server enforcement aligned.
- Update the user guide changelog when shipping a feature, then refresh this project snapshot if architecture or module ownership changes.

## 9. Build, development, and verification

From the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

The development server runs Vite on port 8080 and proxies API calls to a local Frappe bench on port 8000. Build committed production assets with:

```powershell
cd frontend
npm run build
```

Focused repository checks:

```powershell
python -m unittest esafepos.promotions.test_engine
python scripts/test_shift_schedule.py
cd frontend
node parity-check.mjs
node barcode-check.mjs
node clock-check.mjs
```

Run the parity check when changing either promotion evaluator; run barcode/clock checks when changing those utilities. For UI changes, follow repository guidance to build and capture desktop/mobile screenshots. Do not edit `esafepos/public/pos/` by hand.

## 10. Repository map

```text
docs/                         User, website, customer-display, and project documentation
frontend/src/App.vue           POS shell and application-level orchestration
frontend/src/views/            Route-level workflows
frontend/src/components/       Reusable Vue interface components
frontend/src/stores/           Pinia state stores
frontend/src/*.js               Client APIs, offline, pricing, scanning, receipts, i18n
esafepos/api/                  Whitelisted backend endpoints and reports
esafepos/promotions/            Pure promotion engine, loader, and tests
esafepos/esafepos/doctype/      Frappe DocType schemas and controllers
esafepos/*.py                   Business rules, integrations, install and hooks
esafepos/www/                   Frappe page serving the POS SPA
esafepos/public/pos/            Generated production frontend bundle
scripts/                        Repository checks and localization utilities
artifacts/                      Captured project/browser artifacts
```

## 11. Maintenance notes

- Keep Python compatible with Python 3.7 and follow the repository's four-space Python / two-space JavaScript and Vue conventions.
- Keep endpoint functions narrowly scoped under `esafepos.api.*`; put pure promotion rules in the promotion engine.
- Update source and generated assets together when frontend changes are intended for deployment.
- Add focused tests beside changed behavior and cover boundary cases such as permissions, currencies, dates, quantities, and offline submission.
- Treat `docs/user-guide.md` as the operational guide and its changelog as the canonical complete release record.
- Update this file in the same change for every project code, configuration, schema, dependency, asset, or version upgrade. Add an `Unreleased` entry until a release number exists; summarize it under the release when one is assigned. Keep this document's feature inventory, module/component catalog, architecture, and DocType list synchronized whenever those structures change.

