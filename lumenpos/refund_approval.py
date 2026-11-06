# Copyright (c) 2026 Esafe (PVT) LTD
# SPDX-License-Identifier: AGPL-3.0-only
# "ESAFEPOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
"""A supervisor's approval for a refund (0.63.0).

The Zimbabwe shop (Phillip, 2026-10-20): "when processing a refund is it
possible to enable supervisor authorization for the process to continue,
password or pin?". Built the way cash out is approved (lumenpos.cash_out).

LumenPOS Settings (General, Approvals and access, Refund approval):
- refund_approval: Off (the default, nothing changes) / Above an amount /
  Always.
- refund_approval_amount: Above an amount asks only past it, in the company
  currency (a sale in another currency valued at its own rate).

Only money handed back counts: the part of a return that pays for an
exchange's new items, or comes off what a customer owes on a sale on account,
leaves no drawer. A manager (LumenPOS or System Manager) needs nobody's
approval. The approval is a supervisor's passcode at the till (approver PINs or
the master passcode, as for discounts and cash out) or the SAME Return request
that clears a late or restricted return, approved for at least this amount.
Whoever approved is kept on the credit note and in the audit log."""

import frappe
from frappe import _
from frappe.utils import flt, fmt_money

SETTINGS = "LumenPOS Settings"
MODES = ("Off", "Above an amount", "Always")
EPSILON = 0.005


def _settings():
    return frappe.get_cached_doc(SETTINGS)


def mode():
    value = _settings().get("refund_approval") or "Off"
    return value if value in MODES else "Off"


def threshold():
    return max(flt(_settings().get("refund_approval_amount")), 0.0)


def client_facts():
    """What the till needs (bootstrap and get_settings)."""
    return {"refund_approval": mode(), "refund_approval_amount": threshold()}


def _is_manager(user=None):
    from lumenpos.api.permissions import is_manager

    return is_manager(user)


def needs_approval(amount, user=None):
    """Does handing back `amount` (company currency) need a supervisor's
    approval? Never for nothing handed back, never for a manager."""
    current = mode()
    if current == "Off" or flt(amount) <= EPSILON or _is_manager(user):
        return False
    if current == "Always":
        return True
    return flt(amount) > threshold() + EPSILON


def money(amount, company):
    from lumenpos import currency

    return fmt_money(flt(amount, 2), currency=currency.company_currency(company))


def approve(amount, company, invoice, passcode=None, request=None):
    """Who approved handing back `amount` (company currency) on a return of
    `invoice`: None when no approval is needed. Raises when one is needed and
    missing or wrong."""
    if not needs_approval(amount):
        return None
    if passcode:
        from lumenpos.api.settings import check_passcode

        result = check_passcode(passcode)
        if not result:
            frappe.throw(_("Wrong approver passcode."), title=_("Refund approval"))
        return result if isinstance(result, str) else _("the master passcode")
    if request:
        from lumenpos.api import approval_requests

        return approval_requests.validate_refund(request, invoice, amount, company)
    frappe.throw(
        _("Refunding {0} needs a supervisor's approval: their passcode, or a request they approve.").format(
            money(amount, company)
        ),
        title=_("Refund approval"),
    )
