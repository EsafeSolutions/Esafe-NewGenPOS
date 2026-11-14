# Customer display

Enable **Customer-facing display** in Settings, then select **Display** on the Sell screen and move the new window to the customer monitor. Both windows use the same browser profile and site. Reopen the display from the Sell screen after refreshing the cashier tab.

The read-only display shows each item, its selling unit, quantity, price and line savings. During checkout it shows the total, payment methods, amount paid, balance due or change. After checkout it shows the receipt number, date, cashier and terminal, item lines, tax, rounding, discounts and rewards where available. The receipt stays visible until the next basket starts. Customer records are selected or entered at the till.

Run `node display-check.mjs` from the frontend folder to check the catalog views, item editor and customer screen in Chrome. Set `DISPLAY_ARTIFACTS` to a folder to capture desktop and mobile screenshots.
