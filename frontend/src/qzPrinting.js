// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
// QZ Tray's separately licensed connector is bundled from its installed demo
// directory. See the upstream LGPL notice at the top of public/qz-tray.js.
import { call } from './api'

const PRINTER_KEY = 'esafepos.qz-printer.v1'
let scriptPromise = null

function loadQz() {
  if (window.qz) return Promise.resolve(window.qz)
  if (scriptPromise) return scriptPromise

  scriptPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = import.meta.env.DEV ? '/qz-tray.js' : `${import.meta.env.BASE_URL}qz-tray.js`
    script.async = true
    script.onload = () => {
      if (window.qz) resolve(window.qz)
      else {
        scriptPromise = null
        reject(new Error('QZ Tray connector did not load'))
      }
    }
    script.onerror = () => {
      scriptPromise = null
      reject(new Error('Could not load the QZ Tray connector'))
    }
    document.head.appendChild(script)
  })
  return scriptPromise
}

async function configureSigning(qz) {
  let config = null
  try {
    config = await call('esafepos.api.qz_printing.get_signing_certificate')
  } catch {
    // QZ remains usable with its normal trust prompt when signing is not set up.
  }
  if (!config?.certificate || !config?.configured) return false

  qz.security.setCertificatePromise((resolve, reject) => {
    resolve(config.certificate)
  })
  qz.security.setSignatureAlgorithm('SHA512')
  qz.security.setSignaturePromise((toSign) => (resolve, reject) => {
    call('esafepos.api.qz_printing.sign_request', { request: toSign })
      .then(resolve)
      .catch(reject)
  })
  return true
}

export function selectedQzPrinter() {
  try {
    return localStorage.getItem(PRINTER_KEY) || ''
  } catch {
    return ''
  }
}

export function saveSelectedQzPrinter(printer) {
  try {
    if (printer) localStorage.setItem(PRINTER_KEY, printer)
    else localStorage.removeItem(PRINTER_KEY)
  } catch {
    // Private browsing can disable storage. The active screen still works.
  }
}

export async function connectQz() {
  const qz = await loadQz()
  const signed = await configureSigning(qz)
  if (!qz.websocket.isActive()) {
    await qz.websocket.connect({ retries: 2, delay: 1 })
  }
  return { qz, signed }
}

export async function findQzPrinters() {
  const { qz, signed } = await connectQz()
  const printers = await qz.printers.find()
  return { printers, signed }
}

function base64Ascii(value) {
  return btoa(value)
}

export async function printQzTest(printer) {
  if (!printer) throw new Error('Select a printer first')
  const { qz, signed } = await connectQz()
  const config = qz.configs.create(printer)
  const data = [{
    type: 'raw',
    format: 'command',
    flavor: 'base64',
    data: base64Ascii('\x1b@ESAFE POS test print\nQZ Tray is connected.\n\n\n'),
  }]
  await qz.print(config, data)
  return { signed }
}

export async function printQzReceipt(printer, base64Data) {
  if (!printer) throw new Error('Select a QZ Tray printer in Settings')
  if (!base64Data) throw new Error('The receipt print data is empty')
  const { qz, signed } = await connectQz()
  const config = qz.configs.create(printer)
  await qz.print(config, [{
    type: 'raw',
    format: 'command',
    flavor: 'base64',
    data: base64Data,
  }])
  return { signed }
}
