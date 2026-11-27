# Buying and supplier payments

The **Buying** workspace in the POS receives purchases, shows each supplier's invoices and balance, and records payments through ERPNext. An open till shift is not required. It requires an online connection.

## Setup

Deploy the rebuilt POS assets and run the normal site migration (`bench --site <site> migrate`). Migration adds the **Buying and supplier payments** Modules & Features switch and native document fields for request deduplication and outlet attribution. The feature is enabled by default, but **Manage buying and suppliers** is a manager-default capability. It can be assigned to a role or person under Settings → Permissions or in a custom POS access profile.

The EsafePOS Manager role receives native Supplier, Purchase Invoice and Payment Entry access, plus the reference/account reads needed by this workflow. Other staff also need ERPNext document permissions; a POS capability alone cannot grant them. Standard native user permissions and company/outlet restrictions still apply. Approval workflows, frozen dates, required purchase orders/receipts, mandatory accounting dimensions, and other ERPNext validation remain authoritative. Documents requiring an approval workflow must be entered through ERPNext.

Configure an enabled company warehouse, stock and payable accounts, a supplier group, expense accounts for additional costs, and enabled **Mode of Payment** records. Each payment mode needs a default Cash or Bank account for the selected company, in company currency. Use a Cash-type mode for cash and a Bank-type mode for transfers or cheques. Different Bank modes may share the same account.

## Scan an invoice with Gemini

After deploying this update, run `bench --site <site> migrate` to add the scanner settings. Open **Settings → General → Invoice scanning**, enter your Gemini API key, keep or update the model ID (default `gemini-3.5-flash-lite`), and enable scanning. The scanner also offers this setup directly to staff who can write EsafePOS Settings. This key is separate from product image search, stored in a Frappe encrypted Password field, and never returned by the configuration API. Leaving the key blank preserves it; removing it requires disabling the scanner. Google billing and quota apply.

1. Select **Scan supplier invoice** in Buying. A supplier can be selected before scanning or matched during review.
2. Choose a clear JPG, PNG, WebP or PDF up to 8 MB, then select **Read invoice**. This sends the document to Google Gemini. The app processes the bytes inline and does not create a Frappe File attachment or use Google's Files upload API.
3. Check the supplier, reference, dates, currency and every detected row. The server suggests permitted suppliers/products using exact item code, barcode, name or supplier tax ID; ambiguous products remain unselected. You can search for a different product, or add a supplier without rescanning.
4. Check quantities and costs in the selected product's **stock UOM**. Different or unknown printed units require explicit confirmation after correction; a bag or carton is never silently treated as one stock unit. Missing or unreadable values remain blank.
5. Select accounts for detected freight/handling and tax. Valuation costs use expense accounts and increase both payable and receipt valuation. **Tax only** uses an account of type Tax and increases payable without capitalization. Choose the correct accounting treatment before posting; complex localization and tax rules remain in ERPNext.
6. Reconcile the checked row total to the printed invoice total, review warnings, and acknowledge that you checked the original. Known duplicate references, a foreign currency, invoice-level discounts, unmatched products, uncertain UOMs, invalid amounts and mismatched totals prevent import. Invoice-level discounts and advanced buying documents use ERPNext.
7. Select **Fill purchase draft**. This performs no stock or accounting posting. Check the warehouse and draft, then use the existing **Submit purchase invoice** action. Replacing a nonempty supplier draft asks first.

Scanning requires online buying access, native Purchase Invoice create and Item read permissions. Settings require native EsafePOS Settings write permission. The API accepts only validated inline file bytes, verifies file signatures and size, uses a fixed Google host and validated model ID, disallows redirects and tools, rate-limits users to one attempt per 15 seconds, and rejects incomplete/malformed model output. Invoice text is explicitly treated as untrusted data. API keys, raw documents and provider error bodies are not written by the scanning code to app logs. No catalog is sent to Gemini; matching happens locally through permission-filtered queries.

The file/result live in the current browser component. Closing it or leaving the page discards them; this is not a document archive. OCR is a drafting aid and can misread invoices. A real Gemini scan still needs verification after you supply a key; automated checks use fixture responses rather than claiming OCR accuracy.

Screenshots: [desktop review](screenshots/buying-ocr/review-desktop.png), [phone product/UOM review](screenshots/buying-ocr/review-mobile.png), [phone draft summary with separate tax and valuation](screenshots/buying-ocr/draft-summary-mobile.png), [account retry state](screenshots/buying-ocr/account-retry-desktop.png).

## Receive a purchase

1. Open **Buying** and choose a supplier, or use **Add supplier** to create one.
2. Open **New purchase invoice**. Enter the supplier's invoice reference/date, posting date, due date, and receiving warehouse.
3. Search for purchase items and enter quantities and unit costs. If a product is missing, choose **Emergency item entry**, or **Create missing item** after an empty search. This simple entry uses each item's stock UOM. Serial, batch, asset, and template items use the full ERPNext buying workflow.
4. Add supplier-billed freight, handling, or other additional costs with their expense accounts.
5. Review **Supplier payable** and the estimated receipt cost per stock unit, then select **Submit purchase invoice**.

The server creates and submits an ERPNext **Purchase Invoice** with **Update Stock** enabled. It receives stock and records the supplier payable in one transaction. It does not create a second Purchase Receipt. Avoid entering goods that have already been received through a different document; invoice those from the receipt in ERPNext.

Additional costs are native **Purchase Taxes and Charges** rows with calculation type **Actual**, category **Valuation and Total**, and direction **Add**. ERPNext allocates them by item value and posts the stock/accounting effects. They increase the amount owed to this supplier. All invoice lines must be stock items when valuation costs are present.

The **Charge type** control can also record a fixed **Tax only** amount against an account of type Tax, using native category **Total**. The summary separates this tax from valuation costs, so recoverable tax is not silently included in stock cost. It is not a replacement for regional tax templates or statutory validation.

For example, 10 units at LKR 100 plus LKR 100 freight creates LKR 1,100 payable and an estimated receipt valuation of LKR 110 per stock unit. The warehouse's resulting valuation depends on the item's ERPNext valuation method and existing stock. The POS never writes a Bin or Item valuation rate directly.

Costs billed by a separate carrier or discovered after submission must be booked separately and allocated through an ERPNext **Landed Cost Voucher**. They must not also be added to the goods supplier's payable. The simple POS form does not replace jurisdiction-specific tax entry, foreign-currency purchasing, alternate purchase UOMs, linked orders/receipts, returns, or later landed-cost adjustments.

Supplier-specific invoice drafts stay separate while the Buying page is open. Switching outlet resets the buying context and its drafts.

### Emergency item entry

Enter the missing item's name, a unique item code (or use **Generate item code**), an accessible leaf category, stock unit, quantity and unit cost. An optional barcode is saved against the stock unit. Choose **Create and add item** to save a normal stock/sales/purchase Item and add it to the current supplier's draft with that quantity and cost. The supplier, invoice references, dates, warehouse, existing lines and additional costs are retained. Quantities and costs must be greater than zero; fractional stock quantities are supported where the selected ERPNext UOM allows them.

**Standard selling price** is optional. Enter a positive price per stock unit to save an ERPNext **Item Price** in the outlet POS Profile's configured selling price list, usually **Standard Selling**. The form shows the list name and its currency; that currency can differ from the purchase currency. The selling price is entered independently of the supplier's unit cost. Leave it blank to create the Item without a selling price.

This action requires the separate **Create items** POS capability, native Item read/create access and Item Group/UOM read access. Native linked-record and barcode/code validation still apply. Users without this access can continue searching existing items and ask an authorized user to create the missing product. Item creation is online only and cannot be queued.

Setting the selling price additionally requires **Edit item selling prices**, native Item Price read/create and Price List read access. The configured list must be enabled, marked for selling and accessible to the user. The price field is disabled when access or setup is missing, and item-only creation remains available. The form does not silently select another list. The existing item-creation endpoint validates the list, stock unit, price and native Item Price create permission, then saves the Item and supplied price in the same transaction.

The Item and any entered selling price are saved immediately and remain if the purchase draft is discarded. Stock and supplier accounting update only after **Submit purchase invoice**. Further selling-price changes are available in **Items & stock**.

If an item save response is lost, the form blocks resubmission and offers **Find saved item**. Search the captured code before creating it again; an Item may already have been saved. Adding a found item uses the normal purchase line editor for quantity and cost. Cancelling or pressing Escape before saving leaves the invoice draft intact.

Screenshots: [desktop entry](screenshots/buying/emergency-item-desktop.png), [phone entry](screenshots/buying/emergency-item-mobile.png), [desktop draft](screenshots/buying/emergency-draft-desktop.png), [phone draft](screenshots/buying/emergency-draft-mobile.png).

## Supplier balances and payments

**Supplier account** shows the company-currency net ledger balance, all visible unpaid invoices, paginated purchase history, and the latest 50 submitted Payment Entries. Invoice details show actual receipt valuation rates and the additional costs, with a link to the native invoice.

The net balance is supplier credits minus debits in the permitted company GL entries. A negative balance is supplier credit. It includes credits and advances; therefore it can differ from the sum of invoice outstandings. GL read permission is required to see this balance. Without that permission, the screen still shows the permitted invoices and states that ledger access is required. Credits/advances can be reconciled in ERPNext.

Frappe 16 requires dictionary aggregate expressions; the compatibility helper now uses these while retaining legacy expressions on v13–v15. Both paths retain permission-aware `get_list` queries. The Buying page fills its flex parent, including large displays. Failed account loads show a retry action inside the panel while manual invoice entry stays available.

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

Emergency item verification (2026-11-27): `python -m unittest esafepos.api.test_buying esafepos.api.test_items_inventory esafepos.api.test_item_identifiers esafepos.api.test_purchase_ocr` passes 80 focused tests. `cd frontend && node buying-check.mjs` covers the actual emergency dialog, empty-search entry/prefill, generated codes, duplicate errors, quantity/cost/selling-price validation, stock-unit Item Price payload, independent purchase cost, optional-price and price-permission/setup/currency boundaries, barcode payload, draft retention, immediate Item versus deferred invoice/stock posting, lost-save lookup, cancellation, in-flight/offline/access gates and desktop/phone layouts/screenshots. Production assets rebuilt; Python 3.7 grammar and whitespace checked. These checks use mocked APIs and do not create live ERPNext Items, Item Prices or accounting documents.

Current scanner/compatibility verification: `python -m unittest esafepos.api.test_buying esafepos.api.test_purchase_ocr esafepos.api.test_credit_checkout` passes 52 focused tests; `cd frontend && node buying-check.mjs` and `node purchase-ocr-check.mjs` pass Chrome fixture workflows on desktop/phone. The latter covers setup/key masking, upload validation, Gemini failure/retry, item matching, explicit pack correction, tax/valuation separation, totals, duplicates, foreign currency, PDF upload, offline gating, account-error recovery and draft-only import. Production assets are rebuilt and Python 3.7 grammar/settings JSON/whitespace are checked. No live key was supplied, so Google extraction quality and live ERPNext postings remain unverified.

Original Buying implementation verification:

- `python -m unittest esafepos.api.test_buying`: 28 focused tests pass against mocked Frappe services, including valuation charge mapping, stock-update submission, permissions/company/currency boundaries, workflows, dates, stale/excess allocations, decimals, bank references, supplier creation, and idempotency.
- `python -m unittest esafepos.api.test_buying esafepos.api.test_credit_checkout`: buying and checkout regression tests pass.
- `cd frontend && node buying-check.mjs`: Chrome fixture flows pass for purchase entry, separate supplier drafts, all three payment methods, partial/full settlement, overpayment prevention, a lost-response retry, supplier creation, offline/permission gates, and desktop/mobile overflow.
- `cd frontend && npm run build`: production assets rebuilt successfully. Python 3.7 grammar, settings/access JSON and whitespace checked.
- Existing `test_items_inventory` has an unrelated fixture error: the extracted `create_item` body calls `_clean_selling_units`, which the fixture does not load. That code/fixture was not changed for Buying.

Screenshots: [desktop purchase](screenshots/buying/purchase-desktop.png), [mobile purchase](screenshots/buying/purchase-mobile.png), [desktop supplier account](screenshots/buying/account-desktop.png), [mobile supplier account](screenshots/buying/account-mobile.png), [desktop cheque](screenshots/buying/cheque-desktop.png), [mobile cheque](screenshots/buying/cheque-mobile.png), [settled account](screenshots/buying/settled-desktop.png).

These tests do not execute live ERPNext stock or GL posting. After migration, validate a sample invoice, valuation charge, partial payment and bank reconciliation on the site's ERPNext version before production use.

ERPNext references: [Purchase Invoice](https://docs.frappe.io/erpnext/purchase-invoice), [valuation and payable charge categories](https://docs.frappe.io/erpnext/difference-in-total-and-valuation-in-tax-and-charges), [Landed Cost Voucher](https://docs.frappe.io/erpnext/stock-transactions-landed-cost-voucher).

Scanner/compatibility references: [Frappe database API](https://docs.frappe.io/framework/user/en/api/database), [Frappe 16 aggregate parser](https://github.com/frappe/frappe/blob/version-16/frappe/database/query.py), [Gemini document understanding](https://ai.google.dev/gemini-api/docs/document-processing), [Gemini generateContent reference](https://ai.google.dev/api/generate-content), [Gemini models](https://ai.google.dev/gemini-api/docs/models).
