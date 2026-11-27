# Customer display

Enable **Customer-facing display** in Settings, then select the monitor-shaped **Display** button on Sell. The customer display panel lets you choose content and open the second screen. Both windows use the same browser profile and site. Reopen the display from Sell after refreshing the cashier tab.

## Second monitor and content controls

Choose **Find monitors** and allow window placement, then choose a monitor under **Project to**. **Second monitor (automatic)** prefers a screen other than the cashier's current screen. **Open second display** opens or reuses this till tab's window. If the browser cannot detect/place monitors, or permission is denied, move the new window manually. Select **Full screen** on the customer window to fill the monitor. Connect the monitor in the operating system's extended-display mode before detecting it. Automatic placement follows the browser's [Window Management API](https://developer.chrome.com/docs/capabilities/web-apis/window-management).

Select a content button to switch the open customer window immediately:

| Content | Customer screen |
|---|---|
| Live sale | Existing membership, basket, checkout and completed receipt |
| Counter closed | Large closed-counter notice and your optional instructions; this does not close the register |
| Bank details | Configured receiving accounts matching this register and sale currency, with official bank QR when configured |
| Adverts | Ordered playlist of up to 20 local images/videos or supported online links |
| Social QR codes | Up to 12 labeled QR codes for social pages, WhatsApp, reviews, websites or other public HTTPS links |
| Custom message | Your heading and multiline notice |

Edit the selected content and choose **Save and show** to publish it. **Show live sale during a basket or payment** temporarily shows baskets, checkout and completed receipts, then returns to the selected content after the receipt is cleared. Turn it off to keep adverts, bank instructions, QR codes or a message visible while selling. **Counter closed** always stays visible until you switch it. **Ask for contact number** switches back to Live sale.

Choose **Default content when the till opens** and save. Content, default mode and monitor preference are saved per register in this browser. Selecting a different register loads its own defaults. The display window belongs to the cashier tab that opened it; other till tabs cannot overwrite it. These preferences are not site-wide settings and add no DocTypes or migration. Clearing the browser's site data removes these preferences and local media.

### Adverts and local files

Add public YouTube watch/Short links, full TikTok video links, or direct HTTPS PNG/JPEG/WebP/GIF/MP4/WebM/Ogg URLs. The POS uses the providers' official players for [YouTube](https://developers.google.com/youtube/player_parameters) and [TikTok](https://developers.tiktok.com/doc/embed-player/); private, removed or restricted videos may not play. Facebook/Instagram pages, TikTok shortened share URLs and arbitrary web pages cannot be played as videos; add those pages as Social QR codes or supply a direct media file instead. Online embeds also show a QR link so customers can open the source on their phones.

**Add local images or videos** accepts supported image/video files up to 100 MB each, within available browser storage. Files stay in IndexedDB on this workstation and are read directly by the customer window without being uploaded to ERPNext. Already loaded POS windows can show local adverts without an internet connection. Video codecs still depend on the browser. Remove files from the playlist and save to delete their stored copies; closing the editor discards new unsaved uploads.

Use the arrow controls in the editor to reorder adverts and set **Seconds per advert** between 5 and 300. Rotation applies to images and videos, including longer videos. Playback starts muted; the customer screen offers previous/next and pause/play. Pausing stops the rotation and local video; an online player is removed while paused. Online playback and automatic screen placement require browser/provider support and should be checked on the actual customer monitor.

### Social QR codes

Choose **Add QR code**, enter a label and public HTTPS link, then save. Codes are generated locally from the exact link, including non-English paths, without a remote QR service. Invalid links are rejected. The display lays out all configured codes and scrolls when needed. Social QR codes are separate from official bank-payment QR instructions.

`node display-content-check.mjs` checks the real Sell toolbar and app snapshot publisher, second-window fallback, content modes, register/currency-filtered bank details, links/QR validation, local IndexedDB media with the browser offline, saved defaults, register/terminal isolation and desktop/mobile layouts. [Desktop controls](screenshots/customer-display/controls-desktop.png), [mobile controls](screenshots/customer-display/controls-mobile.png), [social QR display](screenshots/customer-display/social-qr-desktop.png), [mobile QR display](screenshots/customer-display/social-qr-mobile.png).

## Live sale and membership

The welcome screen shows the shop name and a membership keypad. A customer can enter their contact number to select an existing ERPNext customer, or choose **Skip** to continue as a walk-in. During a basket, the cashier can reopen the keypad over the display using **Ask for contact number** on Sell. If lookup cannot find a match, the customer can retry, skip, or ask the cashier. Lookup requires a connection.

The live display highlights the most recently added item, including repeated scans that increase an existing line. It shows quantity, selling unit, price, line savings and the basket. Product photos take priority. The POS uses bundled Lucide icons based on item name or group when photos are missing or fail to load. Totals stay at the bottom through payment. The receipt and rewards stay visible until the next basket starts or the customer selects **Start next sale**. Phone numbers are cleared when the keypad closes.

Run `node display-check.mjs --display-only` from the frontend folder to check the catalog, membership keypad and customer display in Chrome. Omit the flag to include the separate Items editor checks. Set `DISPLAY_ARTIFACTS` to capture desktop and mobile screenshots.

## Bank transfer instructions during payment

After deployment, run `bench --site <site> migrate` for the new `EsafePOS Settings.bank_transfer_display` field. In **Settings → General → Customer bank display**, enable automatic bank details and add the receiving bank, account holder and account number. Account numbers retain leading zeroes. You can add up to 12 accounts, restrict each to a register and currency, choose a payment method, and enter branch/SWIFT codes and customer instructions. These are public receiving details intended for the customer monitor.

Upload a bank logo and the official bank payment QR as PNG, JPEG or WebP (up to 2 MB and 16 megapixels). Adjust their size with the sliders and check the customer preview before choosing **Save bank display settings**. An uploaded QR takes priority over an optional explicit QR payload supplied by the bank. The POS does not invent a bank-payment QR from an account number. Images are re-encoded and saved as public Frappe File attachments; upload only receiving details that should be shown to customers.

Checkout opens in a compact popup over the cashier's sale. The default bank-method trigger opens a separate popup over the customer's basket when **Bank Transfer**, **Bank Draft** or **Bank** is added to the payment. Leave an account's **Payment method** blank to use it for these bank methods, or enter an exact Mode of Payment name to restrict it to that method. Cash and card methods do not trigger an unrestricted bank account. Existing settings that explicitly show details when checkout opens remain supported; choose **When a bank transfer or bank draft is selected** to use the selection-only behavior.

The bank popup shows the receiving bank, account holder, account number, branch/currency, optional QR and **Amount to send**. This is the amount allocated to the selected bank method, in its receiving currency, rather than the remaining checkout balance. For example, LKR 2,500 cash plus LKR 10,000 Bank Transfer shows **LKR 10,000.00**, even though checkout now has no remaining balance. Repeated entries for the same method are combined. Accounts for other registers/payment currencies stay hidden, and customers can choose between matching accounts. The basket remains behind the popup. Customers can close the details and reopen them using **Bank transfer details**. Reduced-motion preferences turn off transitions. Removing the bank tender, closing payment, completing the sale, locking the till or starting the next sale clears the bank popup through the existing snapshot lifecycle.

Enable **Customer-facing display** under Features and open **Display** from Sell once, using the same browser profile on the customer monitor. No bank connection is implied: the cashier must verify the transfer in bank records and enter any required reference before completing the sale.

`node register-bank-check.mjs` checks the bank editor, checkout-to-display BroadcastChannel flow, method/account/currency routing, split-payment amounts, QR display, popup dismissal/reopening, tender removal, payment exit and receipt clearing, and desktop/mobile layouts against simulated APIs. Screenshots: cashier [desktop](screenshots/register-bank/payment-popup-desktop.png) / [phone](screenshots/register-bank/payment-popup-mobile.png), customer [desktop](screenshots/register-bank/bank-display-desktop.png) / [phone](screenshots/register-bank/bank-display-mobile.png).
