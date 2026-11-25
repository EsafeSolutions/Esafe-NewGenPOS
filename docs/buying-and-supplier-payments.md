# Buying and supplier payments

The **Buying** workspace in the POS receives purchases, shows each supplier's invoices and balance, and records payments through ERPNext. An open till shift is not required. It requires an online connection.

## Setup

Deploy the rebuilt POS assets and run the normal site migration (`bench --site <site> migrate`). Migration adds the **Buying and supplier payments** Modules & Features switch and native document fields for request deduplication and outlet attribution. The feature is enabled by default, but **Manage buying and suppliers** is a manager-default capability. It can be assigned to a role or person under Settings → Permissions or in a custom POS access profile.

The EsafePOS Manager role receives native Supplier, Purchase Invoice and Payment Entry access, plus the reference/account reads needed by this workflow. Other staff also need ERPNext document permissions; a POS capability alone cannot grant them. Standard native user permissions and company/outlet restrictions still apply. Approval workflows, frozen dates, required purchase orders/receipts, mandatory accounting dimensions, and other ERPNext validation remain authoritative. Documents requiring an approval workflow must be entered through ERPNext.

Configure an enabled company warehouse, stock and payable accounts, a supplier group, expense accounts for additional costs, and enabled **Mode of Payment** records. Each payment mode needs a default Cash or Bank account for the selected company, in company currency. Use a Cash-type mode for cash and a Bank-type mode for transfers or cheques. Different Bank modes may share the same account.

## Receive a purchase

1. Open **Buying** and choose a supplier, or use **Add supplier** to create one.
2. Open **New purchase invoice**. Enter the supplier's invoice reference/date, posting date, due date, and receiving warehouse.
3. Search for purchase items and enter quantities and unit costs. This simple entry uses each item's stock UOM. Serial, batch, asset, and template items use the full ERPNext buying workflow.
4. Add supplier-billed freight, handling, or other additional costs with their expense accounts.
5. Review **Supplier payable** and the estimated receipt cost per stock unit, then select **Submit purchase invoice**.

The server creates and submits an ERPNext **Purchase Invoice** with **Update Stock** enabled. It receives stock and records the supplier payable in one transaction. It does not create a second Purchase Receipt. Avoid entering goods that have already been received through a different document; invoice those from the receipt in ERPNext.

Additional costs are native **Purchase Taxes and Charges** rows with calculation type **Actual**, category **Valuation and Total**, and direction **Add**. ERPNext allocates them by item value and posts the stock/accounting effects. They increase the amount owed to this supplier. All invoice lines must be stock items when valuation costs are present.

For example, 10 units at LKR 100 plus LKR 100 freight creates LKR 1,100 payable and an estimated receipt valuation of LKR 110 per stock unit. The warehouse's resulting valuation depends on the item's ERPNext valuation method and existing stock. The POS never writes a Bin or Item valuation rate directly.

Costs billed by a separate carrier or discovered after submission must be booked separately and allocated through an ERPNext **Landed Cost Voucher**. They must not also be added to the goods supplier's payable. The simple POS form does not replace jurisdiction-specific tax entry, foreign-currency purchasing, alternate purchase UOMs, linked orders/receipts, returns, or later landed-cost adjustments.

Supplier-specific invoice drafts stay separate while the Buying page is open. Switching outlet resets the buying context and its drafts.

## Supplier balances and payments

**Supplier account** shows the company-currency net ledger balance, all visible unpaid invoices, paginated purchase history, and the latest 50 submitted Payment Entries. Invoice details show actual receipt valuation rates and the additional costs, with a link to the native invoice.

The net balance is supplier credits minus debits in the permitted company GL entries. A negative balance is supplier credit. It includes credits and advances; therefore it can differ from the sum of invoice outstandings. GL read permission is required to see this balance. Without that permission, the screen still shows the permitted invoices and states that ledger access is required. Credits/advances can be reconciled in ERPNext.

Select unpaid invoices and choose **Pay supplier**. Enter a full or partial amount and a payment date. The server allocates the payment to the selected invoices oldest first. Selected invoices must share the same company-currency payable account. Overpayments, stale/settled invoices, foreign-currency selections, and dates earlier than an allocated invoice are refused.

- **Cash:** choose a Cash mode. This pays from the company cash account. If the physical cash comes from the till drawer, also record its withdrawal through **Register → Cash out**, using the existing cash-out permissions and approval policy. Supplier payments do not automatically change shift drawer counts.
- **Bank Transfer:** choose a Bank mode and enter the transfer reference and date.
- **Cheque:** choose a Bank mode and enter the cheque number and date, including a future cheque date if applicable. Submitting records an issued cheque, not bank clearance. Clearance remains an ERPNext bank reconciliation operation.

Each settlement is a submitted **Payment Entry**, with `payment_type=Pay`, `party_type=Supplier`, and native Purchase Invoice references. No parallel supplier balance ledger is introduced. Payment links open the native voucher. Native reconciliation, cancellation, and refunds remain in ERPNext.

## Reliability and data model

Supplier, Purchase Invoice and Payment Entry receive `esafepos_buying_key` (unique, user-scoped hash) and `esafepos_buying_hash` (request fingerprint). Purchase Invoice and Payment Entry also retain `esafepos_buying_profile`; Payment Entry retains `esafepos_supplier_payment_method`. Supplier creation and posting APIs require POST. They use native document permissions without `ignore_permissions` or manual commits.

The client retains an unchanged request ID after a failed response. A lost response locks the posting form and offers **Check posting result**, which reuses the exact captured request even after balances refresh. The server checks for the original submitted document before reposting, compares request details, and refuses reuse for a changed or cancelled document. Supplier row locks serialize POS retries; settlement also locks selected invoice rows before reading fresh outstanding balances. Unique request keys are the final duplicate-posting guard. These operations do not use the offline sale queue. Request snapshots are retained while the page remains open; after closing/reloading it, review native invoice/payment history before recreating an uncertain posting.

Affected modules: `api/buying.py`, `BuyingView.vue`, route/navigation/title, feature and permission configuration, manager grants, migration custom fields, and generated POS assets. There are no new accounting DocTypes.

## Verification

- `python -m unittest esafepos.api.test_buying`: 28 focused tests pass against mocked Frappe services, including valuation charge mapping, stock-update submission, permissions/company/currency boundaries, workflows, dates, stale/excess allocations, decimals, bank references, supplier creation, and idempotency.
- `python -m unittest esafepos.api.test_buying esafepos.api.test_credit_checkout`: buying and checkout regression tests pass.
- `cd frontend && node buying-check.mjs`: Chrome fixture flows pass for purchase entry, separate supplier drafts, all three payment methods, partial/full settlement, overpayment prevention, a lost-response retry, supplier creation, offline/permission gates, and desktop/mobile overflow.
- `cd frontend && npm run build`: production assets rebuilt successfully. Python 3.7 grammar, settings/access JSON and whitespace checked.
- Existing `test_items_inventory` has an unrelated fixture error: the extracted `create_item` body calls `_clean_selling_units`, which the fixture does not load. That code/fixture was not changed for Buying.

Screenshots: [desktop purchase](screenshots/buying/purchase-desktop.png), [mobile purchase](screenshots/buying/purchase-mobile.png), [desktop supplier account](screenshots/buying/account-desktop.png), [mobile supplier account](screenshots/buying/account-mobile.png), [desktop cheque](screenshots/buying/cheque-desktop.png), [mobile cheque](screenshots/buying/cheque-mobile.png), [settled account](screenshots/buying/settled-desktop.png).

These tests do not execute live ERPNext stock or GL posting. After migration, validate a sample invoice, valuation charge, partial payment and bank reconciliation on the site's ERPNext version before production use.

ERPNext references: [Purchase Invoice](https://docs.frappe.io/erpnext/purchase-invoice), [valuation and payable charge categories](https://docs.frappe.io/erpnext/difference-in-total-and-valuation-in-tax-and-charges), [Landed Cost Voucher](https://docs.frappe.io/erpnext/stock-transactions-landed-cost-voucher).
