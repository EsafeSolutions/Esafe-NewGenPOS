# EsafePOS Project Logbook and Component Reference

**Project:** EsafePOS (Frappe app package: `lumenpos`)  
**Snapshot:** v0.69.0, based on the repository and product guide dated 2026-11-09  
**Purpose:** engineering overview of the product, its features, modules, data model, and release history.  
**Audience:** maintainers, integrators, reviewers, and technical stakeholders.

> This document describes the implementation visible in this repository. For cashier procedures and settings instructions, use the [user guide](user-guide.md) and [website guide](website-guide.md). The complete per-release history is maintained in [section 19 of the user guide](user-guide.md#19-changelog); this document summarizes its engineering milestones.

## 1. Project at a glance

EsafePOS is a browser-based point-of-sale application for ERPNext and Frappe. It is delivered as a Frappe app named `lumenpos`, with a Vue 3 single-page application served at `/pos`. It uses ERPNext's POS Profile, customer, item, stock, invoice, payment, and accounting records, and adds workflows for registers, promotions, returns, offline sales, outlet management, reporting, and stock counting.

| Area | Implementation |
|---|---|
| Server | Python, Frappe whitelisted APIs, ERPNext document APIs |
| Client | Vue 3, Vue Router hash routes, Pinia, Vite |
| Persistent business data | ERPNext invoices and stock/accounting documents plus EsafePOS DocTypes |
| Local/offline data | IndexedDB database `lumenpos`; service worker where supported |
| Supported framework line | Frappe / ERPNext 13 through 16; Python syntax remains compatible with 3.7 |
| Package | `lumenpos`; app title `ESafe New Gen POS` |
| License | AGPL-3.0-only; product name and logo are trademarks (see `license.txt` and `TRADEMARKS.md`) |

## 2. Product features

### 2.1 Till and checkout

- Product browsing by category and search, with barcode, weight-embedded scale barcode, and serial-number scanning.
- Cached catalog search, product stock availability, price check, and a cart with customer, channel, salesperson, note, coupon, and discount controls.
- Multiple payment methods, split tender, cash shortcuts, change due, payment references, and customer payment collection.
- Per-profile choice of POS Invoice (normally consolidated at shift close) or Sales Invoice (posted directly); both use standard ERPNext documents.
- Printable receipts, configurable receipt details, browser printing, ESC/POS network printing, reprints, and cash-drawer kick where configured.
- A second-screen customer display that mirrors the active cart and accepts customer contact details.

### 2.2 Pricing, promotions, and offers

- POS Promotion rules: simple discount, Buy X Get Y, Spend and Save, and Bundle Price.
- Promotion scheduling by dates, days, and daily time windows; eligibility by outlet and customer group; product matching and exclusions; coupon gating; and stacking controls.
- Client-side offer evaluation and suggestions for near-qualifying baskets, backed by authoritative server recalculation during submission.
- Price books for customer group/outlet pricing, delivery-app price lists, and controlled price edits.
- Product bundles, delivery app channels, order identifiers, and manual line/order discounts with configurable approval.

### 2.3 Customers and balances

- Customer search, creation, configurable required/optional/hidden form fields, company address capture, and customer reporting.
- ERPNext loyalty point display and redemption.
- Gift card issuance, tender, balance entries, and redemption.
- Store credit ledger and tender; customer credit/on-account sales and customer payment collection.
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
Frappe whitelisted endpoints (lumenpos/api)
  ├── permission and outlet checks
  ├── promotion, pricing, currency, return and register rules
  └── ERPNext documents + EsafePOS DocTypes
        ├── POS Invoice / Sales Invoice / Payment Entry
        ├── POS Opening/Closing Entry, Stock Reconciliation
        └── register, audit, promotion, balance and workflow records
```

Typical startup calls `lumenpos.api.session.get_bootstrap`, which supplies the selected POS Profile, register state, payments, currencies, settings, promotions, and catalog context. The client fetches/searches catalog data and updates the cart locally. On checkout, the client sends a sale request through `lumenpos.api.sales`; the server validates the cashier's access, profile, current register, prices, promotions, serials, payment rules, and other enabled safeguards before creating the ERPNext invoice. The client receives the posted invoice/receipt and refreshes local stock and shift summaries.

### Important boundaries

- `lumenpos/promotions/engine.py` is a pure Python rules engine. `frontend/src/promotions.js` mirrors it for immediate cart feedback. The server-side calculation is authoritative.
- ERPNext is the system of record for posted sales, returns, stock, and accounting. EsafePOS DocTypes retain workflow-specific state and audit details.
- `lumenpos/public/pos/` is generated by Vite. Edit `frontend/src/` and rebuild; do not make source edits directly in generated output.
- ERPNext-version-sensitive behavior belongs behind `lumenpos/erpnext_compat.py` where practical.

## 4. Frontend route and component catalog

### 4.1 Application shell and routes

`frontend/src/main.js` creates the Vue app, Pinia instance, and hash router. `frontend/src/App.vue` owns the shared shell, top bar, offline state, outlet switcher, help, lock overlay, and cross-screen navigation. The `/display` route intentionally renders without the normal till shell or bootstrap.

| Route | View | Responsibility |
|---|---|---|
| `/` | `SellView.vue` | Product search/grid, cart, customer and checkout actions |
| `/history` | `HistoryView.vue` | Search/browse posted sales; start refund, exchange, or reprint workflows |
| `/customers` | `CustomersView.vue` | Customer lookup, account balances, statements/reports, and customer-facing actions |
| `/holds` | `HoldsView.vue` | Find and manage layaways, installments, completion, and cancellation |
| `/register` | `RegisterView.vue` | Open, monitor, reconcile, and close a register session |
| `/insights` | `InsightsView.vue` | Management reports and scoped dashboards |
| `/settings` | `SettingsView.vue` | In-POS configuration and permissions-aware setup |
| `/labels` | `LabelsView.vue` | Build and print item/barcode/price labels |
| `/count` | `StockCountView.vue` | Count stock and coordinate with shared EsafePOS Stock sessions |
| `/display` | `CustomerDisplayView.vue` | Customer monitor, synchronized over `BroadcastChannel` |

### 4.2 Shared Vue components

| Component | Responsibility |
|---|---|
| `NavRail.vue` | Main navigation, theme toggle, current screen navigation |
| `Icon.vue` | Shared inline icon set |
| `ProductGrid.vue`, `ProductRows.vue`, `ProductsPanel.vue` | Product tile/list presentation and catalog selection |
| `CartPanel.vue`, `CartLine.vue` | Cart summary and editable line-level controls |
| `PaymentOverlay.vue`, `PaymentBrand.vue` | Tender entry, payment method display, split payments and checkout |
| `CustomerModal.vue`, `CustomerCredit.vue` | Customer selection/creation and account/credit operations |
| `SearchSelect.vue`, `LinkPicker.vue` | Reusable searchable selection controls |
| `SerialModal.vue` | Serial-number selection and validation UX |
| `PriceCheckModal.vue` | Price and stock lookup without completing a sale |
| `SellGiftCardModal.vue` | Gift card sale/issuance workflow |
| `HoldModal.vue`, `ParkedSalesModal.vue` | Create a hold and retrieve parked sales |
| `RefundModal.vue`, `RefundApproval.vue`, `ApprovalsModal.vue` | Return selection, approval state, and pending approval queue |
| `CashOutApproval.vue`, `PasscodeModal.vue` | Protected cash movement and supervisor PIN entry |
| `OpenRegisterOverlay.vue`, `XReportModal.vue`, `VarianceReason.vue` | Register opening prompt, mid-shift summary, and close variance reason |
| `ReceiptModal.vue`, `ReceiptView.vue` | Receipt preview, printing, and reprint presentation |
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
| `stores/catalog.js` | Catalog loading, cache-backed product lookup and stock updates |
| `stores/cart.js` | Current sale, lines, customer, coupon, discounts and totals |
| `stores/help.js` | Help panel and guided-tour state |
| `api.js` | Frappe method calls, request errors and offline-aware request handling |
| `offline.js` | IndexedDB schema, local queue, pending customer records, shift cache and sync locks |
| `promotions.js`, `discounts.js` | Client promotion evaluation/suggestions and discount breakdown helpers |
| `refund.js`, `refundApproval.js` | Return calculations, offline eligibility and approval policy helpers |
| `barcode.js`, `scanGuard.js`, `labels.js` | Barcode generation/handling, weight-embedded scale barcode parser, scanner input guard, and label layout data |
| `customerDisplay.js`, `displayCustomerEntry.js` | Customer display synchronization and input capture |
| `receiptPrint.js` | Browser print and receipt formatting helpers |
| `format.js` | Currency, date/time, number, and display formatting |
| `theme.js`, `i18n.js`, `messages.js`, `locales/` | Theme selection, locale/RTL initialization, translations |
| `help/content.js` | Screen-level help and tour content |

## 5. Backend modules and API domains

### 5.1 HTTP/API modules (`lumenpos/api/`)

| Module | Domain |
|---|---|
| `session.py` | Authentication checks, bootstrap, outlet/profile context, active shift access |
| `catalog.py` | Product catalog, search, stock/availability and price lookup |
| `sales.py` | Sale quote/submission, invoice creation, validation, receipt data and idempotency |
| `register.py` | Open/close, cash movements, counts, shift summaries, consolidation and recovery |
| `customers.py`, `credit.py`, `loyalty.py` | Customer lookup/details, credit operations and wallet balances |
| `discounts.py`, `approval_requests.py`, `pin.py` | Discount computations, supervisor approval requests and PIN operations |
| `exchanges.py`, `refund` logic in sales/register | Exchange quotes/submission and return/posting integration |
| `layaway.py` | Layaway quote/create, deposits, installments, complete, cancel and list |
| `settings.py`, `permissions.py` | Settings endpoints, capability checks and administrative configuration |
| `reports.py`, `insights.py`, `salespeople.py` | Sales and management reporting, dashboards, salesperson rollups |
| `printing.py`, `labels.py` | Receipt printing/reprints and label product/pricing data |
| `audit.py`, `help.py`, `system_check.py` | Audit history, help/tour state, configuration and operational diagnostics |
| `stock_app.py` | Shared stock count, devices, merge and reconciliation integration |

### 5.2 Business rule and integration modules (`lumenpos/`)

- **Offers and pricing:** `promotions/engine.py`, `promotions/loader.py`, `price_books.py`, `coupons.py`, `cashback_rules.py`, `cashback.py`, `scale_barcode.py`.
- **Money and customer balances:** `currency.py`, `store_credit.py`, `gift_cards.py`, `credit_sales.py`, `deposits.py`, `paid_in.py`.
- **Sales lifecycle:** `exchanges.py`, `refund_approval.py`, `return_restrictions.py`, `payment_restrictions.py`, `cash_out.py`, `variance.py`.
- **Scope and compatibility:** `scope.py`, `outlets.py`, `reports_access.py`, `erpnext_compat.py`, `accounting_periods.py`, `inter_company.py`, `internal_accounts.py`.
- **Setup and presentation:** `install.py`, `hooks.py`, `customer_form.py`, `receipt_options.py`, `digital_receipts.py`, `languages.py`, `service_worker.py`, `demo_data.py`.

### 5.3 Frappe hooks and scheduled work

`lumenpos/hooks.py` declares app registration, app-screen permission, website routing, the `/sw.js` page renderer, DocType hooks, installation/migration setup, and scheduled jobs. Current scheduled jobs include stuck register-close reconciliation, overdue-shift notification, cashback expiry/accrual, inter-company balance settlement, and daily automatic currency rates. `after_migrate` runs setup enforcement so roles and custom fields stay in place after updates.

## 6. Persistent data model

ERPNext standard documents remain central: `POS Invoice`, `Sales Invoice`, `POS Opening Entry`, `POS Closing Entry`, `Payment Entry`, `Stock Reconciliation`, `Stock Entry`, `Sales Order`, `Customer`, `Item`, and their standard child records. EsafePOS's DocTypes provide configuration and POS-specific workflow state.

The table below groups the DocTypes present under `lumenpos/lumenpos/doctype/`. Child DocTypes are marked where their purpose is clear from their names; actual parent links and fields are defined in the adjacent JSON schema files.

| Group | EsafePOS DocTypes | Purpose |
|---|---|---|
| Core configuration | `LumenPOS Settings`, `LumenPOS Company Setting`, `LumenPOS Profile Receipt`, `LumenPOS Payment Method Rule`, `POS Delivery App`, `POS Sale Currency`, `POS Customer Form Field` | Site/company settings, receipt configuration, tender policy, delivery channels, currencies, customer form schema |
| Registers and shifts | `POS Register Session`, `POS Register Payment Count`, `POS Cash Movement`, `POS Session Day`, `POS Session Float`, `POS Session Rate`, `POS Shift Invoice`, `POS Shift Schedule`, `POS Shift Schedule Slot`, `POS Variance Reason` | Shift lifecycle, counts, movements, multi-day/multi-currency context, schedule and close variance |
| Promotions and prices | `POS Promotion`, `POS Promotion Item`, `POS Promotion Profile`, `POS Promotion Customer Group`, `POS Coupon`, `POS Price Book`, `POS Price Book Item`, `POS Bundle`, `POS Bundle Item`, `POS Quick Key` | Offers, eligibility child rows, coupon references, price books, bundles and quick-key configuration |
| Sales workflows | `POS Parked Sale`, `POS Layaway`, `POS Layaway Item`, `POS Layaway Payment`, `POS Approval Request`, `POS Refund Rule`, `POS Return Restriction`, `POS Return Reason`, `POS Payment Restriction` | Parked carts, holds/deposits, approval queue, return and payment policy |
| Balances and benefits | `POS Gift Card`, `POS Gift Card Entry`, `POS Store Credit Entry`, `POS Cashback Rule`, `POS Cashback Rule Item`, `POS Cashback Rule Profile`, `POS Cashback Rule Customer Group`, `POS Cashback Entry`, `POS Inter Company Settlement` | Gift cards, store credit, cashback configuration/ledger and inter-company settlement state |
| Access, audit and stock count | `LumenPOS Audit Log`, `LumenPOS User PIN`, `POS Discount Approver`, `POS Capability Rule`, `POS Count Session`, `POS Count Device` | Audit trail, cashier PIN, approvers/capabilities, shared stock count sessions and participating devices |

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
- **Weight-embedded scale barcode reading:** Added support for variable-weight scale barcodes (EAN-13 and UPC-A using standard in-store prefixes `20`–`29`, `02`). The scanner automatically parses the item PLU/code and decimal weight, looks up the item (via prefix+PLU, PLU, or stripped PLU in `Item Barcode` and `Item`), and adds the item to the cart with the exact measured quantity. Supported both online (in `resolve_scan` and `price_check`) and offline (in IndexedDB `searchCatalog` and `SellView`). Configurable in `LumenPOS Settings` (enable/disable, custom prefixes, PLU length 4/5, decimal places).

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

| Date | Change | Impact |
|---|---|---|
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
python -m unittest lumenpos.promotions.test_engine
python scripts/test_shift_schedule.py
cd frontend
node parity-check.mjs
node barcode-check.mjs
node clock-check.mjs
```

Run the parity check when changing either promotion evaluator; run barcode/clock checks when changing those utilities. For UI changes, follow repository guidance to build and capture desktop/mobile screenshots. Do not edit `lumenpos/public/pos/` by hand.

## 10. Repository map

```text
docs/                         User, website, customer-display, and project documentation
frontend/src/App.vue           POS shell and application-level orchestration
frontend/src/views/            Route-level workflows
frontend/src/components/       Reusable Vue interface components
frontend/src/stores/           Pinia state stores
frontend/src/*.js               Client APIs, offline, pricing, scanning, receipts, i18n
lumenpos/api/                  Whitelisted backend endpoints and reports
lumenpos/promotions/            Pure promotion engine, loader, and tests
lumenpos/lumenpos/doctype/      Frappe DocType schemas and controllers
lumenpos/*.py                   Business rules, integrations, install and hooks
lumenpos/www/                   Frappe page serving the POS SPA
lumenpos/public/pos/            Generated production frontend bundle
scripts/                        Repository checks and localization utilities
artifacts/                      Captured project/browser artifacts
```

## 11. Maintenance notes

- Keep Python compatible with Python 3.7 and follow the repository's four-space Python / two-space JavaScript and Vue conventions.
- Keep endpoint functions narrowly scoped under `lumenpos.api.*`; put pure promotion rules in the promotion engine.
- Update source and generated assets together when frontend changes are intended for deployment.
- Add focused tests beside changed behavior and cover boundary cases such as permissions, currencies, dates, quantities, and offline submission.
- Treat `docs/user-guide.md` as the operational guide and its changelog as the canonical complete release record.
- Update this file in the same change for every project code, configuration, schema, dependency, asset, or version upgrade. Add an `Unreleased` entry until a release number exists; summarize it under the release when one is assigned. Keep this document's feature inventory, module/component catalog, architecture, and DocType list synchronized whenever those structures change.

