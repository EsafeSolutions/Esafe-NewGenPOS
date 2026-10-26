# Copyright (c) 2026 Lumen Solutions
# SPDX-License-Identifier: AGPL-3.0-only
# "LumenPOS" is a trademark of Lumen Solutions. See TRADEMARKS.md.
app_name = "lumenpos"
app_title = "LumenPOS"
app_publisher = "Lumen Solutions"
app_description = "Professional, multi-business Point of Sale for ERPNext / Frappe"
app_email = "hello@lumen-solutions.co"
app_license = "AGPL-3.0-only"

required_apps = ["erpnext"]

# Frappe's apps screen (/apps, Frappe 15 and 16) and the Frappe 16 desk list an
# app only when it declares itself here. Shown to whoever may open the till.
# The Frappe 16 desk tile and sidebar are the files in desktop_icon/ and
# workspace_sidebar/, which Frappe 16 imports on every migrate.
add_to_apps_screen = [
    {
        "name": app_name,
        "logo": "/assets/lumenpos/pos/icon-192.png",
        "title": app_title,
        "route": "/pos",
        "has_permission": "lumenpos.api.session.can_open_till",
    }
]

after_install = "lumenpos.install.after_install"

# The Lumen Stock app (0.68.0): before a stock count is submitted in the desk,
# what moved after it was counted and what open shifts still hold.
doctype_js = {"Stock Reconciliation": "public/js/stock_reconciliation.js"}
# Runs on every app update (Frappe Cloud deploy), keeps the LumenPOS roles and
# custom fields in place on existing sites without shell access.
after_migrate = "lumenpos.install.ensure_setup"

# Self-healer: re-drive any register shift stuck in "Closing" (a consolidation
# that timed out or failed) toward "Closed", serialized so it never collides
# with a live close. This is the backstop that guarantees no shift is ever left
# half-closed for the next cashier to stumble into.
scheduler_events = {
    "cron": {
        "*/10 * * * *": [
            "lumenpos.api.register.reconcile_stuck_closings",
        ],
        # Forgotten-shift alert. Hourly is enough, it emails once per shift
        # (de-duped by the session's overdue_notified flag) and never closes a
        # till, so it can't race anything.
        "0 * * * *": [
            "lumenpos.api.register.notify_overdue_sessions",
        ],
        # Cashback, once a day and in this order: write off what expired, then
        # book the days that have ended to the accounts (one summary Journal
        # Entry per company, day and outlet cost center). One job so the two
        # steps can never run out of order.
        "30 0 * * *": [
            "lumenpos.cashback.nightly",
        ],
        # Customer balances spent across companies of a group: yesterday's
        # lines booked as Inter Company Journal Entry pairs (one per day, pair
        # of companies and kind of balance).
        "45 0 * * *": [
            "lumenpos.inter_company.nightly",
        ],
        # Other currencies set to Automatic: the day's published rate, less the
        # shop's margin, saved as ERPNext Currency Exchange.
        "15 0 * * *": [
            "lumenpos.currency.daily_rates",
        ],
    },
}

# Demo builder only (lumenpos/demo_data.py). Dates the documents of a demo
# history through Frappe's own hook instead of patching the framework at
# runtime. It returns at once unless a demo run has set
# frappe.flags.lumenpos_demo_stamp, so a real sale is never touched.
doc_events = {
    "POS Invoice": {
        "before_insert": "lumenpos.demo_data.apply_demo_stamp",
        # ERPNext 16 leaves loyalty points owing on a POS Invoice (see there).
        "before_submit": "lumenpos.erpnext_compat.settle_points_outstanding",
    },
    "Sales Invoice": {
        "before_insert": [
            "lumenpos.demo_data.apply_demo_stamp",
            # The close's merged invoice keeps no "paid in" figures (lumenpos.paid_in).
            "lumenpos.paid_in.clear_on_merged",
        ],
    },
    "Stock Entry": {"before_insert": "lumenpos.demo_data.apply_demo_stamp"},
    "POS Opening Entry": {"before_insert": "lumenpos.demo_data.apply_demo_stamp"},
    "POS Closing Entry": {"before_insert": "lumenpos.demo_data.apply_demo_stamp"},
    "Payment Entry": {"before_insert": "lumenpos.demo_data.apply_demo_stamp"},
}

# The till's service worker has to come from the site ROOT to be allowed to
# control /pos, and Frappe never serves a .js file from an app's www folder.
# This renderer answers /sw.js and nothing else (see lumenpos/service_worker.py).
# v13 has no page_renderer hook, so the till there stays online-only.
page_renderer = ["lumenpos.service_worker.ServiceWorkerPage"]

# The POS single-page app is served at /pos (see lumenpos/www/pos.py).
# All sub-paths resolve to the same page; the frontend uses a hash router.
website_route_rules = [
    {"from_route": "/pos/<path:app_path>", "to_route": "pos"},
]
