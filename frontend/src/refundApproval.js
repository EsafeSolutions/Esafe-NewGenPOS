// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
// "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.

// Does handing back `amount` (company currency) need a supervisor's approval?
// The rule of lumenpos.refund_approval.needs_approval (0.63.0), for the one
// case the server cannot be asked: a refund made without a connection, which
// then waits for one. Online the till asks the server (sales.refund_check),
// which values the refund exactly as it will post.
export function refundNeedsApproval(settings, permissions, amount) {
  const mode = settings?.refund_approval || 'Off'
  if (mode === 'Off' || permissions?.is_manager || !(Number(amount) > 0.005)) return false
  if (mode === 'Always') return true
  return Number(amount) > (Number(settings?.refund_approval_amount) || 0) + 0.005
}
