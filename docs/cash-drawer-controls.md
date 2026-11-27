# Cash drawer controls

Implemented with the supplied **SDK 0.2.0** from **Esafe-POS-Cash-Drawer-Kit-0.2.1.zip**. Manager 0.2.1 has its own native drawer controls; the SDK helper also works with manager 0.2.0 using the existing protocol-1 raw-print path. The kit does not install the native manager. No physical drawer was opened or live ERP site deployed during implementation.

## Workstation setup

1. Deploy the matching app source and rebuilt assets, then run `bench --site <site> migrate`. This adds the profile's authorized workstation registry, offline-origin invoice marker and drawer metadata fields on Print Intent. The repeatable patch only synchronizes custom fields; existing settings, receipts and financial records remain intact.
2. In **Printing → Printers**, connect and approve the ERP site. **Approve and save workstation printers**, including the exact receipt queue. Existing browsers upgrading from SDK 0.1.0 should approve/save again so the POS records its exact print grants. Other roles/outlets remain in the complete permission request.
3. Open **Cash drawer**. It shows the saved receipt queue; no independent or fallback queue is selected. Enable cash drawer (default **off**), choose **Pin 2 / drawer 1** (SDK pin 0) or **Pin 5 / drawer 2** (SDK pin 1), and set ON/OFF times. Defaults are **100/500 ms**. Both values must be even whole milliseconds from **2 to 510**, enforced in the browser and server.
4. Save settings. A permission-only HTML preview checks the exact queue's print grant; it creates no spooler job and sends no pulse. Saving also requires Settings/POS Profile write access and outlet access on the ERP server. The saved settings are mirrored in browser-origin IndexedDB and in an authorized registry keyed by POS Profile and workstation UUID. Updating one workstation preserves others. Native manager settings are independent and are never assumed to synchronize with the POS.
5. Click **Test / open cash drawer** and confirm the physical action. This uses a separate, journaled five-byte raw intent with exactly one copy. It sends no initialization, receipt, cut or feed command. Ordinary printer tests, preview, connection and pairing remain pulse-free.
6. Optionally enable **Open after a successful cash payment**, default **off**, and save. Qualify the real drawer/printer first. Disable Windows driver/native automatic drawer triggers that could duplicate the POS pulse.

The controls require an online connection, migrated fields, an approved/matching queue and setup permission. Missing queues or grants disable opening. No USB, HID, serial, socket or file permission is requested; the drawer must connect to a compatible receipt printer's drawer port.

## Cashier opening and automatic policy

An enabled workstation shows **Open cash drawer** in its open Register and receipt screen to users with the existing **Cash out** capability. Clicking it opens the drawer without asking for a reason. An open authorized session, session write access and the existing owner-or-manager check still apply. The server records **Manual cash drawer opening** automatically; older clients may still supply an optional note up to 140 characters. This physical action records an intent; it does not create a cash movement. Record actual cash in/out through the usual Register workflow, including its separate reason/approval policy.

Automatic opening uses only the successful new-sale receipt boundary. The server reloads the invoice and its real tender rows and verifies:

- Authenticated sale owner and allowed outlet/current open register; submitted POS Invoice or POS-mode Sales Invoice.
- Positive total and at least one positive Mode of Payment of ERP type **Cash**. Fully paid cash/card splits are supported.
- No outstanding amount, Credit Sale tender or on-account entry; no draft, cancellation, return or submitted refund against the invoice.
- No offline-origin invoice; the new metadata must be migrated. New automatic intents must reference a sale created within five minutes. Historical/reprint screens do not initiate this flow.
- The saved workstation configuration is enabled and its automatic policy is enabled.

When automatic native receipt printing is enabled, the drawer intent references the original receipt intent and the same printer. The service persists the pulse intent and waits at most 20 seconds during that active checkout flow for native **submitted/completed**. Events give immediate updates; a read every 500 ms also recovers missed events or an event resync. Confirmed status is reported successfully to ERP before requesting drawer authorization; a transient report failure is retried once, without resending receipt bytes or the pulse. **Queued** acceptance alone is insufficient. Failed preparation/submission, cancellation, uncertainty, lost connection or timeout stop the attached pulse. The server independently requires the linked original receipt to be submitted/completed on that exact queue. Reprint intents cannot satisfy it.

When no automatic receipt is requested, an eligible successful cash payment can authorize a pulse-only intent. No extra receipt is forced. Failure never repeats, changes or reverses the sale/payment. Cashiers may use a separate, explicitly authorized manual opening when needed.

## Print response time

Normal accepted prints no longer wait for a scan of historical jobs or ERP audit responses. The accepted job is persisted and appears in Print jobs immediately; ordered audit updates run in the background. Printer discovery and capabilities are reused for up to 30 seconds, invalidated on reconnect, disconnect or submission errors. Explicit printer refresh remains immediate. The manager still validates the actual printer and current print permission; a missing queue never switches to another printer.

Receipt rendering, ERP authorization, the native manager, the Windows driver and printer mechanics still determine physical print speed. No fixed output speed is promised by the software checks. Existing raw ESC/POS output can avoid HTML/PDF rendering where its receipt layout fits the shop's needs; it is not selected automatically because it produces a different receipt layout. No changes to the separately installed manager or driver are included in this POS update.

## Recovery and audit

Each opening has its own stable UUID, exact five bytes/title/options, source and printer in the existing durable journal before native dispatch. Browser Web Locks and a server unique original-drawer identity prevent duplicate checkout callbacks, tabs and workstations from opening again for the same sale. Receipt copies and rendered format never multiply the pulse. Each intentional test/manual opening gets a new key.

Resume, reconnection, status refresh, preview, ordinary test receipts and receipt reprints never start pulses. A drawer intent cannot use the generic native **Reprint** action. Inspect **Printing → Print jobs** after uncertain output. **Retry identical intent** is an explicit operator action, preserving the original bytes/title/options/key and repeating current server authorization; it is never automatic. A changed/disabled configuration or revoked permission can refuse retry. Use a separate deliberate manual opening only after inspecting the actual drawer/native queue. There is no exactly-once physical-opening guarantee.

Print Intent retains the initiating user (standard owner), workstation, printer, source sale/session/outlet, reason, pin/timings, stable ID, optional receipt link, native job ID and reported outcome. The audit log records the opening request where enabled. Neither durable acceptance nor Windows completion proves the drawer physically opened. Client-reported outcomes remain separate from accounting state; no receipt payload or browser private key is logged.

UI evidence: [desktop](screenshots/printing/cash-drawer-desktop.png), [mobile](screenshots/printing/cash-drawer-mobile.png).

Reason-free cashier opening: [desktop](screenshots/printing/manual-drawer-desktop.png), [mobile](screenshots/printing/manual-drawer-mobile.png). These screenshots use synthetic receipts and simulated native output.

## Build, rollback and qualification

The private package is pinned to `file:vendor/esafe-printer-manager-0.2.0.tgz` with the lockfile. SHA-256: `808e3066a5bf32a3fa548ab4812de706581752766a490ec580685b3f2da97143`. Build with the existing `npm ci` / `npm run build` process; no public private-package registry or development-machine dependency path is needed. Settings diagnostics report SDK 0.2.0 and protocol 1.

Before rollback, disable automatic opening and the drawer on every configured workstation, save, then revert source/assets together. Preserve intent records and unresolved journals. New fields can remain for audit; do not drop financial records or replay pulses. Reverting only browser state does not revoke the server registry or native site's print grants.

Software verification: `node esafe-check.mjs` verifies acceptance while ERP reporting is blocked, absence of historical scans on successful dispatch, discovery/capability cache expiry and explicit refresh, and stale-event ordering. `node drawer-check.mjs` uses the actual SDK encoder and tests default-off settings, both pin vectors/timing limits, single-copy output after a three-copy receipt, callback/tab/reload deduplication, lost acknowledgements and explicit retries, failed receipts, preview/resume/status, blocked pulse reprints, missed-event polling/resync, audit recovery, timeout and disconnect. `scripts/test_cash_drawer.py` mocks ERP I/O to verify authoritative cash/card/split/credit/refund/offline rules, setup/manual permissions, reason-free opening with an audit label, outlet/workstation isolation, linked receipt submission, metadata and preserved business preferences. The actual-SDK Chrome integration check covers drawer controls, invalid timing, confirmed test pulse bytes, automatic receipt submission/audit gate, reason-free manual opening and desktop/mobile screenshots. Existing Esafe, checkout and Printing regression results are recorded in the project logbook.

Hardware qualification remains separate: verify the installed manager build/certificate, exact queue, correct connector pin, manufacturer-approved timings, driver automation disabled, physical latch behavior, paid cash/card split, receipt render failure and network/restart/unknown behavior on a staging till. The supplied kit contains no installer and establishes no publisher-signing or physical hardware certification for manager 0.2.1. Do not deploy to a live ERP site without deployment authority.
