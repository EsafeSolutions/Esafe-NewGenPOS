# Customer display

Enable **Customer-facing display** in Settings, then select the monitor-shaped **Display** icon in Sell's blue header. It expands an icon menu for switching screens, opening the second display, showing the mini preview and opening settings. Hover an icon to see its name. Both windows use the same browser profile and site. Reopen the display from Sell after refreshing the cashier tab.

## Second monitor and content controls

Open the display icon menu and select the settings/sliders icon to edit content and monitor preferences. Choose **Find monitors** and allow window placement, then choose a monitor under **Project to**. **Second monitor (automatic)** prefers a screen other than the cashier's current screen. **Open second display**, available in both the icon menu and settings, opens or reuses this till tab's window. If the browser cannot detect/place monitors, or permission is denied, move the new window manually. Select **Full screen** on the customer window to fill the monitor. Connect the monitor in the operating system's extended-display mode before detecting it. Automatic placement follows the browser's [Window Management API](https://developer.chrome.com/docs/capabilities/web-apis/window-management).

Adverts are the permanent background. Content buttons open popup layers over that background:

| Content | Customer screen |
|---|---|
| Live sale | Full customer-screen foreground for the basket, membership, checkout or receipt, automatically raised when items are added/scanned |
| Counter closed | Closed-counter popup with your instructions; this does not close the register |
| Bank details | Receiving-account popup matching this register and sale currency, with official bank QR when configured |
| Adverts | Background playlist of up to 20 local images/videos or supported links; hides popups until the next sale update |
| Social QR codes | Popup containing up to 12 labeled social, WhatsApp, review or website QR codes |
| Custom message | Popup with your heading and multiline notice |

Edit the selected content and choose **Save and show**. The advert player stays mounted and continues its playlist beneath the foreground. A new scan or changed basket quantity brings the live sale forward across the full customer screen for clear reading. The welcome/membership page also fills the available live area, with larger contact-number and keypad text. Bank details, QR codes, counter status and messages remain compact popups above it. Close a popup to see the layer beneath it. **Hide live sale** in the top control bar reveals adverts; the next sale update brings the full live view back. **Ask for contact number** switches back to the live view. **Start next sale** clears the completed receipt and returns to the advert background.

### Customer display icon menu and movable POS preview

Click the monitor icon in the blue header to expand a compact grid of icons: Adverts, Live sale, Counter closed, Bank details, Social QR codes, Custom message, Preview (eye), Open second display (monitor) and settings (sliders). The actions have tooltips and accessible names, with the active view highlighted. Selecting an action closes the menu. Click outside or press Escape to dismiss it; arrow keys, Home and End move between icons. Product search sits directly below the compact blue header.

**Open second display** also opens a small **Customer display** preview inside the POS. Drag its title bar to move it, or focus the title bar and use the arrow keys (Shift moves farther). Its position is remembered on this browser and kept inside the viewport when the screen size changes. Minimize, expand or close it; the eye icon (**Preview**) in the monitor menu brings it back. The mini screen stays available while checkout or the display editor is open.

The preview is read-only and follows the customer screen's popup visibility, bank-account selection, selected advert and playlist pause state. It cannot submit a contact number or activate a customer-screen control, and it does not take keyboard focus from the cashier. Video frames play separately in the two windows, so their playback timing may differ. **Customer screen connected** indicates that the projected window remains open. Locking the till hides the preview and clears sale/bank popups while the public advert background continues; unlocking restores the current sale and mini screen.

Choose **Default content when the till opens** and save. New configurations start with the advert background; a saved bank, status, social or message default opens that popup above it. Content, default layer and monitor preference are saved per register in this browser. Selecting a different register loads its own defaults. The display window belongs to the cashier tab that opened it; other till tabs cannot overwrite it. These preferences are not site-wide settings and add no DocTypes or migration. Clearing the browser's site data removes these preferences and local media. Saved bank, status, social and message modes use compact popups; Live sale uses the full foreground. The former optional live-sale priority switch is superseded by automatic sale display.

### Adverts and local files

Add public YouTube watch/Short links, full TikTok video links, or direct HTTPS PNG/JPEG/WebP/GIF/MP4/WebM/Ogg URLs. The POS uses the providers' official players for [YouTube](https://developers.google.com/youtube/player_parameters) and [TikTok](https://developers.tiktok.com/doc/embed-player/); private, removed or restricted videos may not play. Facebook/Instagram pages, TikTok shortened share URLs and arbitrary web pages cannot be played as videos; add those pages as Social QR codes or supply a direct media file instead. Online embeds also show a QR link so customers can open the source on their phones.

**Add local images or videos** accepts supported image/video files up to 100 MB each, within available browser storage. Files stay in IndexedDB on this workstation and are read directly by the customer window without being uploaded to ERPNext. Already loaded POS windows can show local adverts without an internet connection. Video codecs still depend on the browser. Remove files from the playlist and save to delete their stored copies; closing the editor discards new unsaved uploads.

Use the arrow controls in the editor to reorder adverts and set **Seconds per advert** between 5 and 300. Rotation applies to images and videos, including longer videos. Playback starts muted; the customer screen offers previous/next and pause/play. Pausing stops the rotation and local video; an online player is removed while paused. Online playback and automatic screen placement require browser/provider support and should be checked on the actual customer monitor.

### Social QR codes

Choose **Add QR code**, enter a label and public HTTPS link, then save. Codes are generated locally from the exact link, including non-English paths, without a remote QR service. Invalid links are rejected. The display lays out all configured codes and scrolls when needed. Social QR codes are separate from official bank-payment QR instructions.

`node display-content-check.mjs` checks the compact desktop header, icon-only menu and accessible names, keyboard/outside dismissal and mobile bounds, full-viewport live/membership geometry, compact popup layers, advert continuity, second-window fallback, synchronized mini screen, drag/keyboard movement, focus retention, bank register/currency filters, links/QR validation, offline media, saved defaults and terminal isolation. [Desktop icon menu](screenshots/customer-display/header-icon-menu-desktop.png), [mobile icon menu](screenshots/customer-display/header-icon-menu-mobile.png), [live display](screenshots/customer-display/layers-desktop.png), [full membership display](screenshots/customer-display/live-membership-desktop.png), [POS mini preview](screenshots/customer-display/pos-mini-preview-desktop.png).

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
