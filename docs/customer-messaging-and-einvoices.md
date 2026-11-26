# Customer messaging and e-invoices

ESAFE POS supplies the customer `/einvoice` page using the existing ERPNext POS
Invoice or Sales Invoice. This customer invoice page does not require another
ERPNext module. The reported **500: error building this page** was reproduced:
Jinja interpreted `receipt.items` as a dictionary method. The template now uses
`receipt['items']`; signed-link, expiry, submitted-document and cancellation
checks remain in place.

Deploy the updated app, run `bench --site <site> migrate`, and restart/clear
website caches as required by the hosting provider. The migration adds the
messaging configuration, encrypted WhatsApp token fields and **POS Customer
Message** history. Accept the available POS update to load the new interface.
The supplied live link continues to use its existing signature after deployment.

## Open a customer or receipt

- The POS **Customer messaging** section searches customers, prepares messages
  and shows recent records from the selected outlet. Cashiers see their own
  records; managers retain the normal company/outlet and document permissions.
- **Customers → select customer → SMS / WhatsApp** opens the same composer.
- A named or linked receipt has **Customer profile** to open that existing
  customer's profile, account and transactions.
- **Receipt → Send e-invoice** prepares editable text with the signed invoice
  link, a link preview, copy actions and receipt-image sharing. Walk-in receipt
  contacts and linked-customer phone numbers are used when available.

The recipient is editable. WhatsApp and history normalize a local number such as
`0771234567` using the configured country calling code, initially `94`. SMS uses
the provider's selected number format. Review the number before submitting.
No message is sent automatically after checkout.

## POS settings

Open **Settings → General → Customer messaging**, or **Messaging settings** from
the messaging section. This module has independent SMS, WhatsApp and receipt
image switches, a country calling code, draft templates, sender roles and popup
preferences. Draft placeholders are `{customer}`, `{invoice}`, `{company}`,
`{currency}`, `{total}`, `{date}`, `{link}` and `{document}`. Returns use
“credit note” for `{document}`.

### WhatsApp Business API

1. Prepare a Meta WhatsApp Business account and business phone number. Create a
   suitable access token with the WhatsApp messaging permissions, and management
   access for the saved-connection check. The API setup uses the **phone number
   ID**, not the phone number or WhatsApp Business Account ID.
2. Enter the phone number ID, Graph API version and access token in **WhatsApp
   Business API integration**. The token uses Frappe's encrypted Password storage.
   It is never returned to the browser; a blank token field keeps the saved one.
   This connection applies to the POS site and its outlets.
3. **Check saved connection** reads the business phone's display number/name;
   it sends no test message. Saving connection/settings also sends no message.
4. Choose the roles permitted to use **Send via WhatsApp API**. System Manager
   and EsafePOS Manager retain manager access. Existing customer, invoice and
   outlet permissions are checked independently on every request.
5. For **Typed text and invoice link** or **Receipt image and caption**, confirm
   the customer messaged this business within the last 24 hours. Meta enforces
   its service window. Image captions are limited to 1024 characters.
6. Outside that window, use **Approved Meta template**. Create and approve the
   exact template/language in WhatsApp Manager, then configure its name and body
   parameter order in POS. For example, `customer,invoice,total,link` fills its
   four numbered body variables in that order. The template controls the wording;
   POS shows the parameter values for review.
7. If the approved template has an **image header**, enable that setting and
   prepare the receipt image before sending. POS uploads the PNG privately to
   Meta and references its media ID. The receipt image is not made into a public
   File attachment. Image-header templates are used from an invoice receipt.

**Submitted to WhatsApp** means Meta returned a message ID. It does not mean
delivered or read. This module provides outbound messages and local history;
delivery/read tracking and inbound chat synchronization require Meta webhooks
and are not implemented here. API details follow Meta's
[message endpoint](https://developers.facebook.com/documentation/business-messaging/whatsapp/reference/whatsapp-business-phone-number/message-api)
and [media-template examples](https://www.postman.com/meta/whatsapp-business-platform/request/2qbotrb/send-message-template-media).

### SMS gateway

The SMS integration edits ERPNext's existing **SMS Settings**. A user needs native
SMS Settings read/write permissions as well as POS Settings write permission to
configure it here. Enter the provider's gateway URL, message/recipient parameter
names, GET/POST choice, static parameters and HTTP headers. Existing parameter
values are masked and preserved when left blank. Remove a row to remove that
parameter. Select roles allowed to send paid SMS; Frappe's native sender-role
check remains authoritative.

Choose **SMS recipient number format** to match the provider. **As entered**
preserves local or international digits (removing spaces, brackets and hyphens).
**International digits** sends `94771234567`; **International with +** sends
`+94771234567`. This lets an existing local-number gateway keep its format.

SMS sends the edited text and link. Ordinary SMS cannot attach the receipt PNG.
Messages may use multiple paid segments, especially with Unicode text. The POS
supports a single recipient per action, with a maximum of 1600 text characters.
**Submitted to gateway** does not establish final delivery. See Frappe's
[SMS Settings implementation](https://github.com/frappe/frappe/blob/version-15/frappe/core/doctype/sms_settings/sms_settings.py).

## Images and the WhatsApp popup

**Prepare receipt image** captures the rendered receipt, including its configured
layout, totals and barcode, as a PNG. It can be sent with WhatsApp API, downloaded,
copied when supported, or passed to the device's **Share image…** menu. Long
receipts that exceed safe image bounds should use the e-invoice link. Meta uploads
are limited here to a PNG smaller than 4 MB. Logos/images must be loadable by the
browser; a sharing failure leaves the link and download alternatives available.

The **WhatsApp popup** is a separate browser window with the selected number and
edited text ready. The user signs into WhatsApp and presses Send there. The POS
does not embed or read WhatsApp Web chats, and a popup cannot automatically attach
the generated file. Download/copy it and attach/paste it, or use WhatsApp API/device
file sharing. The link format follows WhatsApp's
[click-to-chat documentation](https://faq.whatsapp.com/5913398998672934).

## History, retries and verification

A unique per-action request is committed to **POS Customer Message** before any
gateway call. Repeated requests with that key return the previous outcome and
do not submit again. Text, recipient, format and image changes create a separate
request. Network timeouts, malformed acknowledgements and provider 5xx outcomes
are recorded as **Outcome unknown**. Check the provider before starting another
message. A **Preparing** record can also need investigation after a process crash.
Explicit Meta 4xx refusals are **Rejected**. Popup activity is **Opened in
WhatsApp**, never “sent” or “delivered”. Invoice names are audit Data fields, so
message history does not add a native document-link block to authorized sale
deletion; a deleted/cancelled invoice's public link stops working.

Verification uses mocked Frappe document/provider boundaries, actual Jinja
rendering, real Vue browser flows and PNG export. No live SMS or Meta message was
sent. Live credentials, provider receipts, deployment/migration and the customer
link on the hosted site still need validation after deployment.

Screenshots: [dashboard](screenshots/messaging/messages-desktop.png), receipt
sharing [desktop](screenshots/messaging/receipt-messaging-desktop.png) /
[phone](screenshots/messaging/receipt-messaging-mobile.png), settings
[desktop](screenshots/messaging/settings-desktop.png) /
[phone](screenshots/messaging/settings-mobile.png), and the exported
[receipt PNG](screenshots/messaging/receipt-share.png).
