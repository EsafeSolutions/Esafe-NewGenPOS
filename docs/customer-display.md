# Customer display

Enable **Customer-facing display** in Settings, then select **Display** on the Sell screen and move the new window to the customer monitor. Both windows use the same browser profile and site. Reopen the display from the Sell screen after refreshing the cashier tab.

The welcome screen shows the shop name and a membership keypad. A customer can enter their contact number to select an existing ERPNext customer, or choose **Skip** to continue as a walk-in. During a basket, the cashier can reopen the keypad over the display using **Ask for contact number** on Sell. If lookup cannot find a match, the customer can retry, skip, or ask the cashier. Lookup requires a connection.

The live display highlights the most recently added item, including repeated scans that increase an existing line. It shows quantity, selling unit, price, line savings and the basket. Product photos take priority. The POS uses bundled Lucide icons based on item name or group when photos are missing or fail to load. Totals stay at the bottom through payment. The receipt and rewards stay visible until the next basket starts or the customer selects **Start next sale**. Phone numbers are cleared when the keypad closes.

Run `node display-check.mjs` from the frontend folder to check the catalog, membership keypad and customer display in Chrome. Set `DISPLAY_ARTIFACTS` to capture desktop and mobile screenshots.
