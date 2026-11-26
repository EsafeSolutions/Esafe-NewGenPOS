import qrcode from 'qrcode-generator'
qrcode.stringToBytes = value => Array.from(new TextEncoder().encode(value))

export function bankAccounts(config, profile, currency, selectedMode = '') {
  if (!config?.enabled) return []
  const accounts = (config.accounts || []).filter(row =>
    (!row.pos_profile || row.pos_profile === profile) && (!row.currency || row.currency === currency))
  const matching = config.trigger === 'bank'
    ? selectedMode ? accounts.filter(row => row.payment_mode === selectedMode) : []
    : accounts
  // BroadcastChannel cannot clone Vue proxies. All account fields are scalar;
  // copy each account before it joins the payment snapshot.
  return matching.map(row => ({ ...row }))
}

// Only the explicit payload entered by the manager becomes a QR. Bank account
// numbers alone are not a bank-compatible payment QR specification.
export function bankQrSource(account) {
  if (account?.qr_image?.startsWith('/files/')) return account.qr_image
  if (!account?.qr_payload) return ''
  try {
    const qr = qrcode(0, 'M')
    qr.addData(account.qr_payload, 'Byte')
    qr.make()
    return qr.createDataURL(5, 20)
  } catch { return '' }
}
