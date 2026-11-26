# Customer display

Enable **Customer-facing display** in Settings, then select **Display** on the Sell screen and move the new window to the customer monitor. Both windows use the same browser profile and site. Reopen the display from the Sell screen after refreshing the cashier tab.

The welcome screen shows the shop name and a membership keypad. A customer can enter their contact number to select an existing ERPNext customer, or choose **Skip** to continue as a walk-in. During a basket, the cashier can reopen the keypad over the display using **Ask for contact number** on Sell. If lookup cannot find a match, the customer can retry, skip, or ask the cashier. Lookup requires a connection.

The live display highlights the most recently added item, including repeated scans that increase an existing line. It shows quantity, selling unit, price, line savings and the basket. Product photos take priority. The POS uses bundled Lucide icons based on item name or group when photos are missing or fail to load. Totals stay at the bottom through payment. The receipt and rewards stay visible until the next basket starts or the customer selects **Start next sale**. Phone numbers are cleared when the keypad closes.

Run `node display-check.mjs --display-only` from the frontend folder to check the catalog, membership keypad and customer display in Chrome. Omit the flag to include the separate Items editor checks. Set `DISPLAY_ARTIFACTS` to capture desktop and mobile screenshots.

## Bank transfer instructions during payment

After deployment, run `bench --site <site> migrate` for the new `EsafePOS Settings.bank_transfer_display` field. In **Settings → General → Customer bank display**, enable automatic bank details and add the receiving bank, account holder and account number. Account numbers retain leading zeroes. You can add up to 12 accounts, restrict each to a register and currency, choose a payment method, and enter branch/SWIFT codes and customer instructions. These are public receiving details intended for the customer monitor.

Upload a bank logo and the official bank payment QR as PNG, JPEG or WebP (up to 2 MB and 16 megapixels). Adjust their size with the sliders and check the customer preview before choosing **Save bank display settings**. An uploaded QR takes priority over an optional explicit QR payload supplied by the bank. The POS does not invent a bank-payment QR from an account number. Images are re-encoded and saved as public Frappe File attachments; upload only receiving details that should be shown to customers.

The default trigger shows the bank panel as soon as the payment page opens. Alternatively, select the bank-method trigger and configure an exact Mode of Payment name for every account; the panel then appears after that method is added to the payment. Accounts for other registers/currencies stay hidden. Customers can choose between matching accounts. The account, QR, remaining amount and transfer steps share the existing customer display; sale totals remain visible. Reduced-motion preferences turn off transitions. Closing payment, completing the sale, locking the till or starting the next sale clears the bank panel through the existing snapshot lifecycle.

Enable **Customer-facing display** under Features and open **Display** from Sell once, using the same browser profile on the customer monitor. No bank connection is implied: the cashier must verify the transfer in bank records and enter any required reference before completing the sale.

`node register-bank-check.mjs` checks the bank editor, checkout-to-display BroadcastChannel flow, routing, QR display, payment exit and receipt clearing, and desktop/mobile layouts against simulated APIs. Screenshots are in [register-bank](screenshots/register-bank/).
