# Esafe Printer Manager integration

Implemented in the POS; site migration and workstation qualification are required before enabling it. The supplied **0.1.0 Windows installer is an unsigned development release**. No physical printer output or live ERPNext migration was observed in this workspace.

## What connects

The POS browser uses the actual private `@esafe/printer-manager` **0.1.0** SDK to connect to Esafe Printer Manager on that workstation. The SDK discovers **`wss://localhost:17651` through `17660`**, authenticates the browser identity and signs requests. The manager handles Windows queues, including installed USB, shared and IP-backed queues. Add/configure network printers in Windows or the native manager; this integration does not invent a browser IP discovery protocol.

The ERP server authorizes source documents, renders PDFs/raw receipts and stores print metadata. It never connects to its own loopback address to find cashier printers. Existing explicit server-network ESC/POS printing remains available with silent printing disabled.

This repository contains the Frappe app `esafepos`, the Vue 3/Pinia client and Vite assets built into `esafepos/public/pos`. It declares Frappe/ERPNext 13–16 compatibility. There is no bench/site configuration or installed Frappe runtime here, so actual site versions, installed custom apps and site-owned Print Formats cannot be established locally. Open **Printing → Printers → Installed ERP and printing versions** on the site to read its actual versions/apps. PDF rendering uses permission-checked `frappe.get_print(..., as_pdf=True)`, verified against the official [Frappe 13 implementation](https://raw.githubusercontent.com/frappe/frappe/version-13/frappe/__init__.py) and [Frappe 16 export](https://raw.githubusercontent.com/frappe/frappe/version-16/frappe/__init__.py). Qualify each deployed version and its PDF renderer on staging.

The independently supplied manager is a Rust/Tauri application. The earlier .NET bridge proposal is historical architecture, not the implementation contract. No native-manager source or Windows installation was modified by this POS change.

## Administrator deployment

1. Back up the site and record the previous app revision, POS Profile printer host/port, Print Format and receipt overrides. Use a restored staging site first.
2. Deploy source and the committed production assets together. The SDK is pinned to `frontend/vendor/esafe-printer-manager-0.1.0.tgz` with a relative `file:` dependency and npm lockfile. There is no public-registry lookup for this private package.
3. To reproduce assets, run `npm ci --offline --ignore-scripts --no-audit --no-fund` in `frontend` when the other locked dependencies are already cached, then `npm run build`. A normal connected `npm ci` also uses the vendored SDK.
4. Run `bench --site <site> migrate`, then clear site/browser asset caches using the normal deployment process. The repeatable custom-field setup adds five POS Profile defaults; Frappe synchronizes **EsafePOS Print Intent**. Existing invoice/payment/stock records and existing printer/format preferences are preserved. Repeat migration on staging and verify saved values survive.
5. Distribute the qualified native installer through your normal administrator channel. The 471 MB installer is not embedded in the POS bundle. The supplied installer `Esafe-Printer-Manager-0.1.0-windows-x64-setup.exe` has SHA-256 `515b6c4293ac71959593202f3f7ee21ce64f8ed5d82f871b4c6407bfc47bf45f`; its Authenticode status was `NotSigned`. Review the build/source and qualify drivers before production deployment.
6. Perform workstation setup below, verify measured paper output, then enable silent/automatic printing for the selected outlet. Both switches default **off**.

New POS Profile fields:

| Field | Default / purpose |
|---|---|
| `esafepos_silent_printing` | Off; choose the native route |
| `esafepos_auto_print_receipt` | Off; original receipt after successful checkout |
| `esafepos_receipt_output` | `html`; built-in HTML, ERPNext PDF or compatible ESC/POS raw |
| `esafepos_print_copies` | 1; validated 1–99 and checked against driver maximum |
| `esafepos_document_paper` | A4; A4 or Letter |

Editing business defaults and workstation roles requires the existing Settings and POS Profile write checks on the server. Cashiers can connect their browser, inspect their own local jobs and print permitted source documents; they cannot save administrative assignments through the UI/API. Clearing browser data removes local assignments/identity and requires fresh approval. Never use it as a routine recovery action for uncertain output.

## Cashier and workstation setup

1. Install/start Esafe Printer Manager for the Windows user who operates the till. Install the intended printer drivers and verify their Windows queues.
2. In the manager's **native Settings**, install its local certificate after reviewing the operating-system trust prompt. The POS neither uploads certificate private keys nor bypasses TLS errors.
3. In **Printing → Printers**, choose the outlet and click **Connect / reconnect**. Allow browser local-network access if requested. Approve this exact ERP website in the native manager.
4. The initial request is discovery only: `{ action: "printers.list", resources: ["printers"] }`. Choose exact installed queues for receipts, labels, invoices/A4 and reports/payment receipts. The Windows default is identified, never silently selected as a replacement.
5. Click **Approve and save workstation printers**, then approve the updated native request. Every update replaces scopes with discovery plus the union of exact printer IDs used by all saved outlet assignments in this browser. No wildcard print or unrelated device permission is requested.
6. Set **Printing → Receipt** to 58 mm or 80 mm, review the template/logo/taxes/payments and save its default or outlet override. Select an ERPNext Print Format in Printers if using PDF. Choose receipt output, copies, document size and advertised driver options.
7. Use **Preview test**, then **Silent test receipt**. Setup, preview, connection and test printing do not open the drawer or create a sale. Check actual width, length, cut behavior, Unicode, barcode readability and the correct queue.
8. Enable **Use Esafe silent printing for this outlet**. Enable **Automatically print the receipt after a successful sale** only after the test is satisfactory. Save defaults. Every workstation serving that outlet needs its own approved local assignments.

Assignments are IndexedDB records scoped by ERP origin, browser profile/workstation identity and POS Profile. A different browser, origin or Windows user has separate choices and may need approval again. Previously approved browsers resume connection; after disconnection there are at most three backoff attempts (1, 2.5 and 5 seconds), with no print replay. Use current Chrome/Edge with secure-context IndexedDB, WebCrypto and Web Locks support.

## Existing printing paths

| Existing action | Esafe behavior when enabled |
|---|---|
| Successful completed-sale receipt | Optional automatic original, after the successful checkout callback; repeated callbacks reuse its intent |
| Manual receipt / History reprint | Receipt role; existing reprint permission and audit checks; explicit new copy has a new intent |
| Standard Sales Invoice / Quotation creation | Existing transaction completes first; authorized ERPNext PDF to the document role; failure does not repost or reverse it |
| Labels and calibration | Existing authorized label snapshot/designer, all pages in one exact-size PDF intent, selected label role; PDF/ZPL/TSPL file exports remain |
| Mid-shift X-report | Existing summary rendered as self-contained thermal HTML to report role |
| Customer payment receipt | Existing Journal Entry receipt rendered as self-contained thermal HTML to report role; never collects payment again |
| Browser output | Explicit browser buttons; invoice/quotation fallback in Print jobs; no automatic second native/browser route after uncertainty |
| Kitchen/order tickets | No such dispatch workflow was found; no new ticket integration is claimed |
| Images | Existing receipt logos/barcodes are embedded; labels retain raster-PDF output. There was no independent image dispatch workflow to replace |

HTML embeds images/styles and uses installed system fonts with complex-script shaping; native rendering cannot fetch external assets or scripts. A logo that cannot be safely embedded produces an error. Qualify Windows Sinhala/Tamil fonts. Use HTML/PDF for Sinhala, Tamil and other complex scripts; ESC/POS raw is only for an encoding verified on the actual printer. Raw SDK options contain **copies only**; the existing byte renderer owns layout/cutting. ZPL/TSPL exports remain files; no new EPL or automatic command-language route is invented.

The existing server `print_receipt(open_drawer=...)` permission/byte path remains intact. No dedicated browser drawer-opening action was found, and its ordinary receipt call already defaults to no pulse. Esafe receipt rendering explicitly requests `open_drawer=0`; pairing, preview, recovery, tests and retries never add a pulse or request device permissions. If a site has a separate custom drawer workflow, qualify it separately before switching that site.

## Jobs, uncertainty and privacy

Open **Printing → Print jobs** for the current user's latest local intents. Queued, preparing, submitting, submitted, completed, failed, cancelled and unknown reflect observed state. Durable acceptance means Esafe accepted responsibility for the job; Windows completion does **not** confirm paper output. No exactly-once physical printing guarantee is made.

Each intent stores a UUID, exact bytes/options/title/printer and hash **before dispatch**. Web Locks and the shared browser journal prevent concurrent tabs, rapid callbacks, rerenders and reloads from dispatching another original. The server also enforces one registered original receipt identity across workstations. A new browser that cannot reconcile the old job must use an authorized reprint rather than fabricate another original.

After a lost reply, the service uses supported `jobs.list`/`jobs.get` and its unique intent title to recover the native job ID. It never resubmits unknown work automatically. **Retry identical intent** is explicit and retains every original byte, option and idempotency key. Accepted work is recovered by native job ID; **Reprint — new copy** uses a new key, authorization and linked audit record. Native reprints reuse the old title, so a lost reprint reply is deliberately not inferred from title matches. Inspect that case in the native manager before another copy. Cancellation is a request and cannot retract paper already emitted.

Receipts, labels, reports and payment receipts expose explicit browser fallback. Invoice/quotation references remain available under **Print jobs → Invoice and quotation browser fallback**, even if PDF preparation failed before native submission. Browser fallback is a separate operator decision; inspect the original printer/job first. It neither resolves an unknown intent nor changes its accounting state.

The POS limits each payload to 10 MiB, outstanding payloads to 1,000 intents and 64 MiB of base64 data, labels to 500 output pages per dispatch. Split larger jobs. Exact request bytes are removed once a native job ID is known; metadata tombstones remain to prevent another original. The UI shows at most 100 recent rows and 30 invoice/quotation fallback references. Local metadata is retained for deduplication; it is not synchronized as a complete cross-workstation job viewer. Use managed browser profiles and normal workstation data-retention controls. Clearing it can destroy recovery evidence. The server stores hashes, references, owner/workstation IDs and client-reported job outcomes, never full receipt bytes, credentials or browser private keys. Browser-reported print outcomes are separate from ERP transaction state.

Offline sales/receipts retain their existing browser path. Native printing is disabled while offline; the bridge does not make ERP rendering, permissions, label preparation or accounting available offline.

## Connection policy and troubleshooting

This repository does not set a POS response CSP. Inspect the site's actual response headers and proxy configuration. If a `connect-src` policy exists, append only these sources to that directive while preserving its existing values and every other directive:

```text
wss://localhost:17651 wss://localhost:17652 wss://localhost:17653
wss://localhost:17654 wss://localhost:17655 wss://localhost:17656
wss://localhost:17657 wss://localhost:17658 wss://localhost:17659
wss://localhost:17660
```

Do not replace CSP with a permissive policy, allow arbitrary WebSockets, disable browser security or suppress certificate validation. Recheck local-network permission and certificate trust after a browser/manager update.

| Symptom | Recovery |
|---|---|
| Unavailable / blocked | Start native app; check native certificate installation, browser local-network permission and the deployed CSP. Retry Connect |
| Approval missing/revoked | Explicit Connect; approve the exact origin and then selected printers again |
| Protocol differs | Install a compatible manager/SDK release; do not work around authentication |
| Missing/renamed queue | Refresh; administrator selects the actual queue, approves the complete scope set and retests |
| Unsupported copies/color/duplex | Choose options supported by the reported driver; raw supports copies only |
| Unknown output | Inspect printer/native jobs, refresh; choose identical retry only when appropriate. No automatic replay |
| Migration required | Run normal site migration and reload assets; do not bypass the authorization endpoint |

## Rollback and QZ retirement

Turn off automatic and silent printing on each enabled POS Profile before rolling back app/assets together. Existing IP/port, Print Format and browser routes resume. Preserve Esafe intent records and browser journals for unresolved jobs. Do not replay receipts, delete financial documents or drop the new audit DocType as a rollback shortcut. Restore a site backup only through the normal administrator recovery process after reconciling transactions.

QZ connector imports, signing APIs, credentials UI and dispatch were removed from this POS previously; no QZ connection/signing request is made here. The only new runtime QZ reference reads the old local receipt-printer name as a review hint. It never assigns a queue by name or connects to QZ. Legacy label profiles retain their existing normalization and require recalibration/explicit Esafe assignment. Historical docs/tests intentionally mention QZ. The separately supplied manager source contains its own maintained QZ compatibility adapter; it is outside this app, was not changed, and is not used by the POS SDK integration. No other installed workstation applications could be inventoried from this repository.

After qualifying Esafe, administrators should check whether any other workstation application still uses QZ. If none does, remove its startup entry and uninstall QZ through Windows Settings → Apps, following the organization's certificate-retirement policy. Browser JavaScript never uninstalls applications or deletes shared trust material.

## Verification and release gate

Automated checks use mocks only in tests. `esafe-browser-check.mjs` runs the actual vendored SDK in Chrome and test-only native/ERP responses; it verifies real authentication/signatures, scopes, role persistence, silent setup/receipt dispatch, Unicode HTML, automatic-original deduplication and deliberate new copies. `esafe-check.mjs` covers concurrency/reload, lost replies, manual identical retry, exact complete scope updates, revoked approval, bounded reconnect and missing queues. Python tests cover document access, metadata, original/reprint ownership and defaults. Existing checkout, receipt and label regressions and the production build are recorded in the project logbook.

Before production: migrate staging twice and verify preserved defaults; exercise the actual installed Frappe/ERPNext/PDF renderer; approve/revoke the real native app; verify original/reprint and printer removal/offline/restart behavior; print 58/80 mm receipts and A4/Letter documents; scan barcodes; inspect Sinhala/Tamil, logos, taxes and payments; calibrate labels; test cutter/drawer behavior under the site's policy; and qualify the unsigned installer/driver combination. No physical or live accounting result is implied by browser/API fixtures.
