# POS Selling, Customer Accounts, and HR Implementation Plan

**Status:** B2B selling, native document draft/submit/mapping, customer settlements, advances, cheque lifecycle and statements are implemented in the repository; see [B2B deployment, behavior and verification](b2b-module.md). The optional HR workspace now implements attendance exceptions, Expense Claim draft/submission entry points and native Salary Slip preview/drafts and monthly commission review, approval and native payroll hand-off; see [HR setup, policy, verification and limits](hr-module.md). Site migration and live accounting, stock and payroll acceptance remain rollout requirements.
**Scope:** EsafePOS checkout and invoicing, ERPNext Selling documents, customer balances and receipts, and optional Frappe HR integration.

## 1. Goal and system of record

Keep ERPNext as the source of truth for sales, receivables, payments, employee records, attendance, expenses, and payroll. EsafePOS should provide a till-friendly way to create and act on those ERPNext documents. It should not create a parallel invoice, balance, payment, or salary ledger.

Use the standard ERPNext documents wherever they fit:

| Business record | ERPNext record |
|---|---|
| Quote | Quotation |
| Confirmed customer order | Sales Order |
| Final bill / receivable | Sales Invoice |
| Customer receipt or allocation | Payment Entry (Receive) |
| Employee and salesperson link | Employee and Sales Person |
| Attendance | Attendance, optionally Employee Checkin and Auto Attendance |
| Employee reimbursement | Expense Claim |
| Salary and incentive payout | Salary Slip / Payroll Entry, with a controlled Additional Salary or commission payout workflow |

The ERPNext documentation describes the standard selling progression as Quotation -> Sales Order -> Delivery Note (when needed) -> Sales Invoice -> Payment Entry. A Quotation is not a posted sale and must not change stock, cash, or customer debt. See the official [Selling overview](https://docs.frappe.io/erpnext/selling), [Sales Order](https://docs.frappe.io/erpnext/sales-order), and [Quotation](https://docs.frappe.io/erpnext/quotation) documentation.

## 2. What the repository already supports

- A POS Profile can use POS Invoice, normally consolidated at register close, or direct Sales Invoice mode.
- The till can make a named-customer sale partly or fully on account, check the credit limit, show open sale balances, collect a customer payment, allocate it to selected or oldest sales, and print a payment receipt.
- Customer profiles show POS purchase totals and wallet balances. The current profile response does not yet expose the full ERPNext receivable ledger and invoice-by-invoice balance as a general account statement.
- The till can create a server-priced ERPNext Quotation and open its print view. It does not yet provide a complete quote-to-order-to-invoice workspace in the POS.
- Salespeople can be attached to sales, and current POS reporting reads ERPNext's Sales Team commission values. This is sales attribution and reporting; it is not a complete employee payroll payout workflow.
- No EsafePOS-owned Employee, Attendance, Expense Claim, or Salary Slip data model exists. Those should remain in Frappe HR if that app is installed.

Relevant existing modules include `esafepos/api/sales.py`, `esafepos/api/credit.py`, `esafepos/credit_sales.py`, `esafepos/api/customers.py`, `esafepos/api/salespeople.py`, `frontend/src/views/SellView.vue`, and `frontend/src/components/CustomerCredit.vue`.

## 3. Recommended user experience

### Sales Rep Mode (new scoped module)

Add a master **Sales Rep Mode** switch in Modules & Features. Keep its child
features independently switchable and default them off until the customer,
pricing, and payment views have been verified on the target ERPNext site:

| Child feature | POS behavior | Customer profile behavior |
|---|---|---|
| ERPNext auto discounts | Detect matching ERPNext Pricing Rules using the selected customer, price list, company, transaction date, item, quantity and UOM. Show the rule and savings before checkout; use ERPNext's calculated values as the submitted document values. Keep EsafePOS promotions separate and prevent both engines from discounting the same line twice. | Not applicable. |
| Customer sales progress | Use the ERPNext quotation, Sales Order, Delivery Note, Sales Invoice and Payment Entry records as one read-only customer timeline. Include outstanding totals, paid-to-date, payment method/reference/date, undelivered quantities, and open customer-linked ToDos. | Show the timeline with a company/currency selector, stage totals and drill-through links. On phones and tablets, use stacked stage cards and horizontally scrollable detail tables. |

Turning Sales Rep Mode off hides and rejects both child features without
changing ERPNext records. The default POS mode keeps the existing EsafePOS
promotion engine and transaction behavior. Apply the pricing-rule child to
both `/pos` checkout/quotation creation and regular Sales Invoice creation, so
the displayed pre-sale amount and submitted ERPNext document agree.

Implementation order: (1) write the switch/dependency and document-source plan;
(2) add the independently gated server settings and fix missing-custom-field
compatibility in customer profiles; (3) add a permission-scoped, read-only
customer sales-progress endpoint and responsive profile section; (4) add an
ERPNext Pricing Rule preview in the cart and feed its validated result into
POS invoice, quotation and regular Sales Invoice builders; (5) verify desktop,
tablet and phone layouts and record the live-site prerequisites. Customer
progress is informational; payment, delivery and order changes continue in
their ERPNext documents unless a later workflow explicitly adds those actions.

### Modules and Features switches

Add a **Modules & Features** area in Settings. Every listed capability must have its own on/off switch; enabling the whole Sales or HR area must not automatically turn on every feature inside it. Show whether a feature is available, enabled, and correctly configured, and explain unmet dependencies beside its switch.

Recommended controls:

| Switch | What it controls | Dependency / scope |
|---|---|---|
| POS Quick Sales | Existing counter checkout | POS Profile; preserve the current default. |
| Regular Sales Invoices | Create and manage regular Sales Invoices from POS | Company enable; optionally restrict to selected POS Profiles. |
| Customer Balances | Show receivable totals and open invoices | Company enable; read permissions still apply. Can operate independently from POS credit selling. |
| Customer Credit Sales | Sell on account and enforce customer credit limits | Depends on customer balances and a configured credit policy; retain its existing setting/permissions. |
| Customer Payment Collection | Receive payments and allocate them to outstanding invoices | Company and POS Profile; requires payment modes/accounts. |
| Cheque Tracking | Capture due dates and manage cheque state | Depends on customer payment collection and cheque account configuration. |
| Quotations | Create, view, and print quotations from POS | Company enable; ERPNext Selling availability. |
| Sales Orders | Find and continue Sales Orders | Company enable; does not require POS Quotation creation. |
| Frappe HR Integration | Show EsafePOS entry points to HR records | Site-level availability; requires Frappe HR installed and configured. |
| Attendance | POS-side attendance review/actions | Depends on HR Integration; manager role and policy required. |
| Expense Claims | POS-side claim status/submission entry points | Depends on HR Integration; Frappe HR approval remains authoritative. |
| Day Salary | Calculate daily-paid earnings through payroll | Depends on HR Integration and agreed day/attendance rules. |
| Sales Commissions | Calculate and review salesperson incentives | Can show sales reports without HR; payroll payout separately depends on HR Integration, Employee links, and payroll configuration. |

The first implementation uses site-wide switches in Settings, matching the existing EsafePOS feature settings. POS Profile invoice mode still chooses POS Invoice or direct Sales Invoice; the site-wide Regular Sales Invoices switch gates the direct mode. Frappe HR availability is detected separately. Enforce switches and permissions on the server as well as in the UI. Turning a switch off hides its menus/actions and rejects its API actions, but keeps existing ERPNext records intact. Do not auto-delete or cancel records. If a dependency is turned off, block or warn before saving and explain which dependent feature will stop working; do not silently change unrelated switches.

Design every new settings and account workflow for desktop, tablet, and phone. On narrow screens use single-column settings cards, large touch targets, stacked customer details, and horizontally scrollable invoice tables instead of shrinking accounting columns until they become unreadable.

### A. One sales area with three clear actions

1. **Quick POS sale:** Keep the current fast checkout, shift, cash drawer, split tender, and offline rules. A paid POS Invoice remains the normal walk-in flow.
2. **Customer invoice:** Add a connected, named-customer invoice flow that creates a standard Sales Invoice. It should support draft/submit according to the cashier's capability, payment terms, due date, salesperson, and a payment now / balance later choice. This can reuse the existing direct Sales Invoice mode where appropriate, but should be separable from POS shift settlement when the business needs a regular invoice outside the till.
3. **Quotation / order:** Keep creating ERPNext Quotations from the POS cart, then add search/open/continue actions for existing quotations and Sales Orders. ERPNext should perform the official conversion and preserve source links, statuses, and remaining quantities.

Do not silently turn a quotation into a paid sale. Show its status and current validity, retrieve the source document from the server, and revalidate price, taxes, stock, customer, and discounts before submitting an invoice. If the quote has expired or its terms have changed, show the change and require a user with the right permission to proceed.

### B. Customer account and balances

Add an **Account** section on the customer profile with company and currency context:

- ERPNext outstanding receivable total, credit limit, available credit, and overdue amount if ERPNext can calculate it for the selected company.
- Open Sales Invoices with invoice number, date, due date, total, paid, outstanding, and status.
- Recent receipts and their allocations, plus open/unallocated advances where supported.
- A printable or downloadable customer statement sourced from ERPNext ledger data.
- A clear refresh timestamp; never present a cached amount as real-time.

On the POS customer selector, show the customer outstanding and credit status before allowing an on-account sale. Keep credit checks server-side at final submission to prevent two tills from both spending the same available limit.

### C. Customer payments and cheque tracking

Use ERPNext Payment Entry for standard customer receipts and invoice allocation. It natively supports partial and multi-invoice allocation and updates invoice outstanding balances. See the official [Payment Entry](https://docs.frappe.io/erpnext/payment-entry) documentation.

For a till receipt, preserve the current shift/register accounting and manager controls, but use a backend adapter to create or safely queue the corresponding ERPNext accounting document. The adapter must not book a second receipt when the current credit-sale clearing workflow has already booked it. Choose one canonical posting route per sale/profile and test the register-close interaction before rollout.

For cheque tenders, capture the cheque/reference number, bank, received date, and cheque due date where the ERPNext version and payment workflow support them. If a dedicated due-date field is absent, add a small custom field to the Payment Entry/reference record rather than hiding the due date in free text. Track pending, deposited/cleared, bounced, and returned cheques through a controlled status workflow; a cheque received should not be treated as cleared bank cash until the configured accounting policy says so.

## 4. HR and payroll scope

Install and configure **Frappe HR** as a separate app on the site if HR records and payroll are required; EsafePOS should integrate with it through supported document APIs and hide HR screens when the app is not installed. Frappe HR provides Employee, Attendance, Expense Claim, Salary Slip, and payroll workflows. See the official [Frappe HR overview](https://docs.frappe.io/erpnext/v13/user/manual/en/human-resources), [Expense Claim](https://docs.frappe.io/hr/expense-claim), and [Salary Slip](https://docs.frappe.io/hr/salary-slip) documentation.

### Attendance and salary

- Configure Employee, holiday lists, shifts, leave, and attendance policy in Frappe HR first.
- Add a role-protected POS action for an authorized manager to review attendance or mark an attendance exception; do not let ordinary cashiers change payroll inputs.
- Attendance should feed salary calculation through the HR payroll rules. Salary Slip supports attendance-based working days and absent/half-day handling, subject to the site's configured policy.
- Implement **day salary** as an agreed salary basis inside payroll, not as a cash-out or a POS tender. For example, calculate payable days × daily rate, then apply approved leave, half-days, overtime, and advances/deductions through payroll. Confirm whether day rate uses calendar days, scheduled workdays, or actual attendance before coding.
- Use Salary Structure / Assignment and Salary Component configuration for earnings and deductions, with payroll liability and expense accounts mapped in ERPNext.

### Employee expense claims

Use Frappe HR Expense Claim for employee-paid business expenses, including attachments, expense types, approval, and reimbursement. Keep approval separate from payment and salary; a reimbursement should not be added to salary by default. Frappe HR's [Expense Claim documentation](https://docs.frappe.io/hr/expense-claim) warns against clubbing reimbursed claims into salary because it may affect tax treatment.

### Salesperson incentives and commission

- Link each eligible ERPNext Sales Person to the corresponding Employee. Keep Sales Person as the sales attribution record.
- Record one or multiple contributors on the Sales Team table. Confirm allocation percentages total 100% where full allocation is expected. ERPNext's Sales Team contribution and commission values do not, by themselves, create a payroll payment. See the official [Sales Person](https://docs.frappe.io/erpnext/sales-person) documentation.
- Define the policy before building the payout: eligible invoice states; basis (net sales before tax, collected cash, or margin); returns/cancellations; shared sales; exclusions; rate tiers; payment date; and whether incentives are paid monthly through payroll.
- Create a monthly commission preview/statement from submitted eligible POS invoices and regular Sales Invoices, net of returns, with drill-through to source invoices. Avoid counting a consolidated Sales Invoice as a second sale when its source POS Invoices are already counted.
- Require approval and lock the approved period against duplicate payout. Post the approved amount through the configured payroll earning workflow (for example, Additional Salary/Sales Commission component) or the site's commission payout process. Store source period and invoice references for audit. ERPNext/Frappe HR commission payout behavior varies by version and configuration, so the installed release must be checked before selecting the exact posting document.

## 5. Implementation phases

| Phase | Deliverables | Completion gate |
|---|---|---|
| 0. Configuration and rules | Confirm ERPNext/Frappe HR versions; companies, POS Profiles, selling price lists, payment terms, credit policy, cheque accounting, tax settings, HR app status, attendance and commission policies. | A signed-off configuration matrix and sample customer/employee scenarios. |
| 1. Customer ledger in POS | Server API for permission-scoped outstanding and open invoice data; customer profile account section; refresh behavior; customer statement entry point. | POS totals reconcile to ERPNext's customer ledger for each test customer and company. |
| 2. Regular invoice flow | Named-customer Sales Invoice creation, draft/submit permissions, due date/payment terms, sales team, partial payment and print/reprint; separate till/register posting rules. | Invoice, stock, GL, tax, receivable, and shift totals match the ERPNext documents with no duplicate posting. |
| 3. Quotation and order lifecycle | Search/open existing quotation, convert through ERPNext to Sales Order or Sales Invoice, show quote/order status, revalidate changed terms, preserve source links. | One quote can be progressed once; cancelled/expired/partially ordered documents behave correctly. |
| 4. Payments and cheques | Payment Entry allocation workflow, receipt/reprint, cheque reference/due-date tracking, clear/bounce/return handling and reconciliation reports. | Partial, split, advance, multi-invoice, cheque and reversal cases reconcile to receivables and bank/cash ledgers. |
| 5. Frappe HR setup | Install/configure HR app; Employee, attendance, leave, salary structure, payroll roles, claims, expense approval. | Payroll test run matches approved attendance and HR policy, with access controls reviewed. |
| 6. Day wages and commission | Payroll-based day salary; Sales Person ↔ Employee mapping; period commission preview, approval, returns and payroll posting. | Re-running a period cannot duplicate earnings; approved totals reconcile to invoice detail and payroll. |
| 7. Rollout | Pilot one company/outlet, train users, reconcile opening balances, then enable by role/profile and expand. | Manager sign-off after a full invoice/payment cycle and one payroll cycle. |

## 6. Security, accounting, and reliability requirements

- Enforce permissions on every API, not only by hiding buttons. Separate invoice create, submit, discount override, credit-limit change, payment receipt, cheque status, attendance edit, expense approval, and payroll approval capabilities.
- Each module/feature switch is an availability gate, not a replacement for role permissions. A feature must be both enabled in its scope and permitted for the current user.
- Use ERPNext document validation and ledger APIs. Do not update invoice outstanding, GL rows, salary totals, or payment allocations with direct database writes.
- Make submit/receipt endpoints idempotent so retries cannot duplicate invoices or customer receipts.
- Keep company, currency, cost center, warehouse, tax, payment terms, and POS Profile validation server-side.
- Make customer balance, payment, quote continuation, cheque tracking, and payroll actions online-only. Keep the current supported offline POS sale path independent.
- Log who created, submitted, edited, approved, reversed, and paid each record. Cancellation/reversal must follow ERPNext's linked-document rules.
- Update `docs/project-logbook-and-component-details.md` for each implementation phase, including affected modules, data flow, and verification.

## 7. Decisions needed before implementation

1. Should regular customer invoices be allowed outside an open POS register, or must every invoice belong to a cashier shift?
2. Should POS invoices default to draft for review, or be submitted immediately by authorized staff?
3. For day wages, what defines a payable day and how should half-days, public holidays, leave, and overtime work?
4. Is salesperson commission based on submitted net sales, collected payments, or gross profit? How are returns and shared sales handled?
5. Which payment instruments are needed at launch, and what accounting states should a received cheque pass through?
6. Which ERPNext and Frappe HR versions are installed on the production sites? Confirm exact document fields and HR commission payout support on those versions before implementation.
7. Should company-level feature switches have an outlet/POS Profile override for every switch, or only for features used directly at the till? The plan assumes company enablement plus POS Profile exposure where relevant.

## 8. Suggested first release

Start with Phase 0 and Phase 1, then Phase 2. This delivers reliable ERPNext customer balances and standard named-customer invoices before payroll complexity is introduced. Keep current POS credit-sale behavior available during rollout, with a company/profile setting to choose which invoice/payment route is active. Add quote progression and cheque handling next; start HR only after its attendance, day-wage, and commission policies are agreed.

## 9. Implementation progress

- **Feature switches and existing customer accounts:** Implemented as independent site-wide controls. Customer balances, open invoice balances, and till receipt collection are already connected to ERPNext records.
- **Named-customer invoice:** Implemented as online-only actions from the cart and a dedicated Invoices screen. They create and submit a standard non-POS ERPNext Sales Invoice, require a named customer and an authorized Sales Invoice create/submit role, use server-side outlet pricing/tax/discount/stock rules, support an optional due date and salesperson, and do not require an open register or immediate payment. A read-only origin marker includes these sales in outlet/customer and salesperson reports without including consolidated shift invoices twice. The invoice is available for later payment through the customer account workflow.
- **ESAFE B2B workspace:** Replaces the standalone invoice page with customer-oriented tabs, native ERPNext pricing, editable drafts, explicit submission/printing, native quotation/order/delivery/invoice mapping, source-preserving partial fulfilment and linked-chain progress. Existing invoice bookmarks redirect. Safe amendments use native cancellation and preserve history without cascading linked-document cancellation.
- **Payments and cheques:** Native Payment Entries support till/back-office, split/partial receipts and order/customer advances. Native Payment Reconciliation applies existing advances. Operational settlement/cheque records add retry identities and custody history, not financial ledgers. Cheques affect accounting only on clearance; closed-shift receipts remain protected. Customer statements use actual party GL entries and authorized voucher allocations.
- **HR integration:** Implemented at `/pos#/hr`, with optional HRMS detection, native employee/document permissions and company scope, manager-only attendance exceptions, Expense Claim drafts linked to native attachments/submission/approval, independent feature switches and online-only actions. Existing salesperson commission reports remain available independently of HR.
- **Day salary:** Per the selected implementation policy, the existing Frappe HR rules are the only salary authority. The POS invokes the native Salary Slip controller for a completed-month preview, rolls back preview calculation writes, displays native payment days/components/gross/deductions/net, and saves an idempotent native draft for approval/submission/payment in Frappe HR. There are no POS daily rates, half-day weights, holiday/leave rules or wage-policy records. Native payroll settings and salary assignments control earnings and deductions.
- **Commission payroll:** Uses native stored Sales Team incentives net of returns, submitted POS Invoices/non-consolidated Sales Invoices counted once, native employee links, salary assignments and a selected native earning component/account. Preview → saved source period → approval → submitted Additional Salary retains audit/source detail and checks stale inputs/duplicate periods. Claims remain separate from salary. Existing salesperson reports remain independent. Native configuration and staging payroll acceptance are required before enabling rollout.
- **Still staged:** A customer login portal, foreign-currency B2B transaction entry and separate installment tracking. Orders, deliveries, cheque and HR child features remain independently configurable. The original POS checkout and Journal Entry collection routes remain intact.
