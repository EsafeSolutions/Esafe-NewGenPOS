# ESAFE B2B module

The **B2B** navigation entry opens a staff workspace at `/pos#/b2b`. Existing
`/pos#/invoices` bookmarks open its Invoices tab. Select a customer once, then
use Overview, Quotations, Sales Orders, Delivery Notes, Invoices, Payments,
Cheques and Customer Summary. Tabs follow feature switches and document access.

## Deploy and configure

1. Deploy the app and regenerated production frontend, then run `bench --site
   <site> migrate`. Reload the POS after migration. Migration creates the two
   operational DocTypes, document metadata, Delivery Notes setting, native
   permissions for managers, and the four ESAFE B2B print formats.
2. Enable **ESAFE B2B module and Sales Invoices** in Settings → Modules & Features.
   Independently enable Quotations, Sales Orders, Delivery Notes, Customer
   balances, Customer payment collection and Cheque tracking as needed. New
   order/delivery/cheque switches retain their default-off values; upgrading
   does not silently enable them. B2B progress is independent of Sales Rep Mode.
3. Configure the POS Profile's company, company-currency selling price list,
   warehouse and Cash/Bank payment modes with valid company-currency accounts.
   Customers may supply their own company-currency price lists. Native customer,
   tax, payment-term, income-account and accounting-dimension defaults apply.
4. Review role permissions. Documents require their native read/create/write/
   submit/print/cancel/amend permissions. Collections additionally require
   **Take customer payments** and Payment Entry read/create/submit. Applying
   advances requires Payment Reconciliation write and source voucher write;
   legacy Journal Entry advances also require access to that journal. Clearing
   cheques requires Payment Entry write, Bank Clearance write and bank-account
   read; bouncing a cleared cheque requires Payment Entry cancel. Complete
   statements require GL Entry read. Setup grants the relevant native manager
   permissions, and ordinary cashiers do not receive general accounting access.
5. Pilot a complete workflow on staging and reconcile its stock, GL, customer
   outstanding, bank and register totals before enabling production users.

Existing POS checkout, its selected pricing engine, till Journal Entry
collections and historical records retain their original posting routes.

## Draft, submit, deliver and print

- Choose a customer and create a document in its tab. Use the existing customer
  creation dialog without changing the Sell cart's selected customer. Customer
  account and Edit customer open the existing customer workspace/native form.
- Add items by name/code. Choose selling UOM, quantity and warehouse. Rates use
  ERPNext pricing rules; a permitted manual rate can be reset. **Line discount**
  accepts a percentage or an amount **per selling unit**, after the native rate.
  Recalculate shows server-confirmed net/tax/total values.
- Use Details, Items, Payments, Address & Contact, Terms and Connections to review
  the document. Address/contact choices belong to the selected customer. Discount
  permissions, profile rate-change policy and existing approval limits apply.
  **Get discount approval** reuses the POS passcode/request policy. Requests need
  an open register under that policy; an approval used for a B2B draft is consumed
  against that draft, with its approved percentage retained for subsequent review.
- **Save draft** creates no submitted sale, payment or stock movement and never
  automatically prints. Reopen drafts from the list. **Submit** is separate and
  requires a saved, unchanged draft and its reviewed total.
- Continue submitted quotations into orders, orders into deliveries/invoices,
  and deliveries into invoices through native ERPNext mappings. Edit the mapped
  draft to deliver or bill a partial quantity. Native references and agreed
  source prices remain linked; ERPNext validates remaining quantities on posting.
- Invoices default to separate delivery. Explicitly select **Deliver stock with
  this invoice** for direct stock sales. A Delivery Note-backed invoice cannot
  move the stock again. Native Selling Settings requiring an order or delivery
  remain enforced. Service-only documents need no delivery stage.
- **Print** opens the native print view or uses the configured Esafe document
  printer. Native draft-print permissions/settings apply. ESAFE B2B formats show
  item discounts, rates, taxes and totals. A matching outlet print format takes
  precedence. Printer failure does not undo the document or trigger another sale.
- **Cancel and amend** uses native cancellation and `amended_from` history. Linked
  payments/deliveries and frozen periods can block it. Resolve those dependencies
  through the native workflow; B2B does not cascade-cancel them. Pending cheques
  aimed at a subsequently cancelled invoice need allocation review at clearance.

The Overview follows one connected sales chain, with icons and stage states.
Delivery and billing progress use native fulfilment/billing percentages. Direct
flows skip optional stages. Payment is complete only when the connected invoices
have no positive outstanding and no cheque is still awaiting clearance. Restricted
or truncated graphs cannot show full completion.

## Customer settlements and advances

In Payments, settle oldest invoices first or select invoices and enter exact
allocations. Add cash, bank transfer and cheque rows for split settlement. Review
the allocation, excess and pending-cheque totals before **Confirm settlement**.
Use **Customer deposit / advance** to receive money before an invoice, or receive
an advance from a submitted Sales Order. Keeping excess as an advance is explicit.

**Till collection** needs an open shift and today's date. Posted Payment Entries
enter that shift's existing payment tally exactly once. Advance allocation creates
no second cash movement. Pending cheques appear separately as custody records in
the register summary. Native cancellation of a till receipt is blocked after its
shift closes, preserving the closed shift's receipts.

**Back-office collection** posts into the configured company account without a
shift. Bank transfers require a reference and reference date. An entered reference
records the staff-confirmed receipt; it is not an automatic bank-feed verification.

**Apply advance** lists permitted native Payment Entry/Journal Entry advances.
Choose the amount and invoice allocations. Native Payment Reconciliation applies
the existing funds, including supported separate-advance accounts, without posting
another receipt. Different receivable accounts must be reconciled separately.
Existing POS clearing-journal debts remain available in the Customer account
workflow; the B2B invoice settlement selector lists ordinary Sales Invoices.

## Cheque dates and lifecycle

Cheque receipt requires a number, issuing bank, amount and cheque date. The
received date is separate. Future-dated cheques are supported. An active duplicate
bank/number for the same customer is rejected. Due-today, upcoming and overdue
filters operate on Received/Deposited cheques.

1. **Received:** operational custody only; no ledger effect or debt reduction.
2. **Deposit cheque:** record the actual deposit date; still no ledger effect.
3. **Clear cheque:** review current allocations and actual clearance date. The
   date cannot predate the cheque or deposit. B2B submits one native Payment Entry
   and updates clearance through the native Bank Clearance controller. Clearance
   is a back-office posting, so it does not change a previously closed shift.
4. **Mark bounced / Return / Cancel:** require a reason and valid transition/date.
   Before clearance these change custody only. Bouncing a cleared cheque cancels
   its Payment Entry using native permissions and dependency/period rules. A
   native cancellation outside B2B also cancels the associated cheque custody
   status. Bank charges remain separate native accounting entries.

Allocations shown on a pending cheque are intentions, not balance reservations.
If another payment settles the invoice first, clearing requires refreshed
allocations or explicit retention as an unallocated advance. Receipts distinguish
posted money, allocated advances, pending cheques and cancelled payments.

## Customer summary and limits

Customer Summary shows a selected-date-range party ledger with opening balance,
debits, credits, running balance and closing balance in company currency. Print/PDF
also includes current open invoices, permitted Payment Entry/Journal Entry
allocations and cheques awaiting clearance. Current balances/statuses carry a
refresh timestamp; the ledger date range and current open items are distinguished.
Pending cheques are excluded from ledger balances. Using actual party GL entries
avoids counting a consolidated POS sale a second time. Statements exceeding
10,000 ledger lines require a shorter date range.

The module creates/settles in company currency. Foreign-currency, POS and return
documents remain native ERPNext editing workflows; permitted foreign documents
can be viewed/printed. B2B does not queue financial mutations offline. Current
entries remain in the open editor for retry, and unsaved work blocks navigation,
refresh and automatic update. There is no customer login portal, payment gateway
or separate installment-scheduling feature in this release.

## Components and verification

`api/b2b.py` handles scoped native document editing/mapping and linked progress;
`api/b2b_payments.py` handles settlement, reconciliation and cheque transitions;
`api/b2b_reports.py` reads the party ledger and prepares statement PDFs.
`b2b_rules.py` contains standalone allocation, discount and progress rules.
`b2b_setup.py` installs metadata and print formats. `B2BView`,
`B2BDocumentEditor` and `B2BSettlementPanel` provide the interface.

`EsafePOS B2B Settlement` stores retry identity, receipt grouping and native
voucher references. `EsafePOS Customer Cheque` stores custody, intended allocations,
dates and transition history. Both are protected operational envelopes, not balance
ledgers. Native documents carry origin, retry/save hashes and approval snapshots;
Payment Entries additionally carry settlement and optional shift references.

Checks: `python -m unittest esafepos.api.test_b2b`, relevant existing customer/
buying/pricing/discount/register suites, `cd frontend && node b2b-browser-check.mjs`,
shared checkout/printing regressions, production build, schema and Python 3.7 grammar.
Browser APIs/native document I/O are fixtures; live Frappe migrations, actual
accounting/stock posting, bank clearance/reversal and physical printing require
the staging-site check above.

Screenshots: [invoice desktop](screenshots/b2b/invoice-desktop.png),
[invoice phone](screenshots/b2b/invoice-390.png),
[settlement](screenshots/b2b/settlement-desktop.png),
[cheques](screenshots/b2b/cheques-desktop.png),
[sales process](screenshots/b2b/process-desktop.png),
[process phone](screenshots/b2b/process-mobile.png).
