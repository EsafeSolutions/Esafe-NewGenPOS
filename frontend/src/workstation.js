import { kvSet } from './offline'

let identity
export function workstationId() {
  if (identity) return identity
  try { identity = localStorage.getItem('esafepos-shift-workstation') } catch { /* session fallback */ }
  if (!/^[A-Za-z0-9-]{16,80}$/.test(identity || '')) {
    identity = globalThis.crypto?.randomUUID?.() || `pos-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`
    try { localStorage.setItem('esafepos-shift-workstation', identity) } catch { /* browser memory */ }
  }
  kvSet('shift-workstation', identity).catch(() => {})
  return identity
}
