# Customer display

Enable **Customer display** in Settings, then use the display button on the Sell screen. Move the new window to the customer monitor. The two windows must use the same browser profile and site; a separate device does not share this connection. Reopen the display with the button after refreshing the cashier tab.

The display uses a white background with the existing POS typography and teal controls, independently of the cashier's light/dark preference. It retains the configured receipt logo, company, items, quantities, savings and total. On smaller screens the customer form appears below the order summary.

During a sale, customers can enter their **Customer name** and **Contact number**, then select **Save details**. The cashier's existing customer API matches the mobile number or creates a customer and selects it for the sale. Existing records are reused without renaming them. Online creation still follows the site's customer permissions and required fields. Errors appear on the form so the cashier can assist.

Offline entry reuses a cached customer with the same contact number or saves a pending customer through the existing offline queue. If the shop requires additional customer fields, the cashier must collect those before an offline customer can be created. Details clear when the sale ends; delayed replies cannot attach the previous customer's details to a new sale. A display opened from one till ignores other till tabs.

## Verification

- `node display-check.mjs`: two real browser windows, light theme isolation, contact validation, online save with mocked ERP responses, offline matching, server error feedback, till isolation and delayed-response protection.
- `node discount-check.mjs`: discount controls, price edits, permission restrictions, approval resets, offline receipts and desktop/mobile geometry.
- `npm run build`: rebuild the production bundle.

The browser scripts accept `PLAYWRIGHT_MODULE` and `CHROME_PATH`; use `DISPLAY_ARTIFACTS` or `DISCOUNT_ARTIFACTS` to save screenshots. Local preview: `node display-check.mjs --serve`.

Visual review compared the supplied display screenshot with local renders at 1896 × 940 and 390 × 940: company/header alignment retained; item and total hierarchy retained; existing typography retained; dark fallback background replaced with white; existing teal accent retained; name/contact form added as requested and stacked on mobile. The test fixture has no receipt logo; the existing configured-logo rendering remains in place. No generated concept was needed for this change within the existing design system.

Screenshots are in `artifacts/customer-display/`. The in-app browser timed out on the local URL, so local Playwright Chrome supplied the renders. Live ERP customer creation and invoice posting require a deployed Frappe site and were not exercised by these isolated browser tests.
