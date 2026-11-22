import { reactive } from 'vue'
import { EsafeClient, toBase64, fromBase64 } from '@esafe/printer-manager'
import { printJournal, workstationId } from './journal.js'

const DISCOVERY = { action: 'printers.list', resources: ['printers'] }
const TERMINAL = new Set(['completed', 'failed', 'cancelled'])
const REFRESH_ERRORS = new Set(['PERMISSION_DENIED', 'UNAUTHORIZED', 'AUTH_REQUIRED', 'PAIRING_DENIED'])
const MAX_PAYLOAD = 10 * 1024 * 1024
export function recoveryMessage(error) {
  const code = error?.code || ''
  if (REFRESH_ERRORS.has(code)) return 'Approval is missing or was revoked. Connect and approve this website again in Esafe Printer Manager.'
  if (code === 'PROTOCOL_MISMATCH' || /PROTOCOL_MISMATCH|compatible protocol/i.test(error?.message || '')) return 'The manager and SDK protocols differ. Install a compatible Esafe Printer Manager release.'
  return error?.message || 'Could not connect. Start Esafe Printer Manager, install its certificate in native Settings, allow browser local-network access, and approve this website.'
}

export function createEsafeService({ client = new EsafeClient(), journal = printJournal, device = workstationId,
  lock = (key, action) => {
    if (!navigator.locks) throw new Error('Silent printing requires Web Locks. Use current Chrome or Edge.')
    return navigator.locks.request(key, action)
  }, authorize = async () => {}, report = async () => {}, now = () => Date.now(), wait = (ms) => new Promise((r) => setTimeout(r, ms)) } = {}) {
  const state = reactive({ connection: 'disconnected', error: '', printers: [], defaultPrinter: null, capabilities: {}, jobs: [], documents: [], port: null, busy: false })
  let connecting, reconnecting = false, stopped = false, pairing = false, initialized = false
  const off = []
  const busyKeys = new Map()
  const bindingKey = (profile) => `binding:${profile}`
  async function binding(profile) { return await journal.setting(bindingKey(profile)) || { profile, receipt: '', labels: '', document: '', report: '' } }
  async function rememberDocument(value) {
    await lock('esafepos-print-documents', async () => {
      const rows = await journal.setting('document-fallbacks') || []
      state.documents = [value, ...rows.filter((r) => r.key !== value.key)].slice(0, 30)
      await journal.saveSetting('document-fallbacks', JSON.parse(JSON.stringify(state.documents)))
    })
  }
  async function scopes(extra) {
    const bindings = (await journal.settings()).filter((v) => v && typeof v === 'object' && v.profile)
    if (extra) bindings.push(extra)
    const ids = [...new Set(bindings.flatMap((b) => ['receipt', 'labels', 'document', 'report'].map((role) => b[role]).filter(Boolean)))].sort()
    return [DISCOVERY, ...(ids.length ? [{ action: 'print', resources: ids }] : [])]
  }
  async function connect({ explicit = false } = {}) {
    if (connecting) return connecting
    const repair = explicit && state.connection === 'approval-required'
    if (client.isConnected && client.isPaired && !repair) {
      try { return await refreshPrinters() }
      catch (error) { if (!explicit || !REFRESH_ERRORS.has(error.code)) throw error }
    }
    if (!explicit && !await journal.setting('approved')) { state.connection = 'approval-required'; return }
    stopped = false
    connecting = (async () => {
      state.connection = 'connecting'; state.error = ''
      try {
        if (client.isConnected) client.disconnect()
        const result = await client.connect({ timeoutMs: 1800 })
        state.port = result.port
        if (!result.paired || repair) {
          await journal.saveSetting('approved', false)
          state.connection = 'approval-required'
          if (!explicit) return
          pairing = true; state.connection = 'approving'
          await client.pair(await scopes(), { timeoutMs: 120000 })
        }
        await journal.saveSetting('approved', true)
        state.connection = 'connected'
        try { await refreshPrinters() }
        catch (error) {
          if (!explicit || !REFRESH_ERRORS.has(error.code)) throw error
          pairing = true; state.connection = 'approving'
          await client.pair(await scopes(), { timeoutMs: 120000 })
          state.connection = 'connected'; await refreshPrinters()
        }
        await refreshJobs()
      } catch (error) {
        state.error = recoveryMessage(error); state.connection = REFRESH_ERRORS.has(error.code) ? 'approval-required' : 'disconnected'
        if (REFRESH_ERRORS.has(error.code)) await journal.saveSetting('approved', false)
        throw error
      } finally { pairing = false; connecting = null }
    })()
    return connecting
  }
  async function refreshPrinters() {
    if (!client.isConnected || !client.isPaired) throw new Error('Connect and approve this website before choosing printers.')
    try {
      const [printers, defaultPrinter] = await Promise.all([client.printers.list(), client.printers.getDefault()])
      state.printers = printers; state.defaultPrinter = defaultPrinter; state.error = ''
      if (state.connection !== 'approval-required') state.connection = 'connected'
      return printers
    } catch (error) {
      state.error = recoveryMessage(error)
      if (REFRESH_ERRORS.has(error.code)) { state.connection = 'approval-required'; await journal.saveSetting('approved', false) }
      throw error
    }
  }
  async function capabilities(id) {
    if (!id) return null
    const info = await client.printers.capabilities(id)
    state.capabilities[id] = info
    return info
  }
  async function saveBinding(profile, selected, guard) {
    await guard() // Settings/POS Profile write checked by the server, before pairing.
    const value = { profile, ...Object.fromEntries(['receipt', 'labels', 'document', 'report'].map((role) => [role, String(selected[role] || '')])), options: {} }
    for (const role of ['receipt', 'document', 'report']) {
      const chosen = selected.options?.[role] || {}, validated = {}
      if (chosen.orientation && !['portrait', 'landscape'].includes(chosen.orientation)) throw new Error('Choose portrait or landscape orientation.')
      if (chosen.duplex && !['none', 'long-edge', 'short-edge'].includes(chosen.duplex)) throw new Error('Choose a supported duplex setting.')
      if (chosen.color !== undefined && typeof chosen.color !== 'boolean') throw new Error('Choose color or monochrome output.')
      for (const key of ['orientation', 'duplex', 'color']) if (chosen[key] !== undefined) validated[key] = chosen[key]
      value.options[role] = validated
    }
    await refreshPrinters()
    const ids = ['receipt', 'labels', 'document', 'report'].map((role) => value[role]).filter(Boolean)
    if (ids.some((id) => !state.printers.some((p) => p.id === id))) throw new Error('A selected printer is missing. Refresh and choose it again.')
    pairing = true; state.busy = true; state.connection = 'approving'
    try {
      // pair() REPLACES scopes. Include every assignment in every outlet.
      const existing = (await journal.settings()).filter((b) => b?.profile && b.profile !== profile)
      const all = [...existing, value]
      const selectedIds = [...new Set(all.flatMap((b) => ['receipt', 'labels', 'document', 'report'].map((r) => b[r]).filter(Boolean)))].sort()
      await client.pair([DISCOVERY, ...(selectedIds.length ? [{ action: 'print', resources: selectedIds }] : [])], { timeoutMs: 120000 })
      await journal.saveSetting(bindingKey(profile), value)
      await journal.saveSetting('approved', true)
      state.connection = 'connected'; state.error = ''
      return value
    } catch (error) {
      state.error = recoveryMessage(error); state.connection = REFRESH_ERRORS.has(error.code) ? 'approval-required' : 'disconnected'
      if (REFRESH_ERRORS.has(error.code)) await journal.saveSetting('approved', false)
      throw error
    }
    finally { pairing = false; state.busy = false }
  }
  async function observe(record, job) {
    const updated = { ...record, state: job.state, agentJobId: job.id, certainty: job.certainty, error: job.error || '', updatedAt: now() }
    // A known native job is recovered/reprinted by ID. Retain bytes only until acceptance
    // is resolved; keep the metadata tombstone to prevent another original dispatch.
    if (job.id || TERMINAL.has(job.state)) delete updated.request
    await journal.put(updated)
    try { await report(updated) } catch { /* Print acceptance never depends on ERP audit availability. */ }
    return updated
  }
  async function refreshJobs() {
    const local = await journal.list()
    state.jobs = local.sort((a, b) => b.createdAt - a.createdAt).slice(0, 100)
    if (!client.isConnected || !client.isPaired) return state.jobs
    const jobs = await client.jobs.list()
    for (const record of local) {
      if (record.state === 'prepared' || TERMINAL.has(record.state)) continue
      const matches = jobs.filter((j) => record.agentJobId ? j.id === record.agentJobId : !record.nativeReprint && j.title === record.title && j.printerId === record.printerId && j.format === record.format)
      if (record.agentJobId || matches.length === 1) {
        try {
          const job = await client.jobs.get(record.agentJobId || matches[0].id)
          if (!job?.id) throw new Error('The native manager no longer returned this job.')
          await observe(record, job)
        } catch (error) {
          await journal.put({ ...record, state: 'unknown', error: `Could not refresh the native job. Check the manager before another copy. ${recoveryMessage(error)}` })
        }
      }
      else if (record.state === 'submitting') await journal.put({ ...record, state: 'unknown', error: 'Acceptance was not confirmed. Refresh status or explicitly retry the identical intent.' })
    }
    state.jobs = (await journal.list()).sort((a, b) => b.createdAt - a.createdAt).slice(0, 100)
    return state.jobs
  }
  async function dispatch({ key, profile, role, format, data, options = {}, title, reference, user, reprintOf = '', automatic = false }) {
    if (busyKeys.has(key)) return busyKeys.get(key)
    const pending = lock(`esafepos-print:${key}`, async () => {
      const existing = await journal.get(key)
      if (existing) { await refreshJobs(); return await journal.get(key) }
      if (!client.isConnected || !client.isPaired) await connect()
      if (!client.isConnected || !client.isPaired) throw new Error('Approve this website in Esafe Printer Manager first.')
      const selected = await binding(profile), printerId = selected[role]
      if (!printerId) throw new Error(`Choose a ${role} printer in Printing → Printers.`)
      await refreshPrinters()
      if (!state.printers.some((p) => p.id === printerId)) throw new Error('The assigned printer is missing or renamed. Choose a printer again; no other queue was selected.')
      const limits = await capabilities(printerId)
      options = { ...(format === 'raw' ? {} : selected.options?.[role] || {}), ...options }
      if (format !== 'raw' && (options.color === true && !limits?.color || options.duplex && options.duplex !== 'none' && !limits?.duplex)) throw new Error('The selected printer does not support these color/duplex options.')
      const copies = options.copies ?? 1
      if (!Number.isInteger(copies) || copies < 1 || copies > Math.min(limits?.maxCopies || 999, 999)) throw new Error('The requested copy count is not supported by this printer.')
      const bytes = typeof data === 'string' ? new TextEncoder().encode(data) : data instanceof Blob ? new Uint8Array(await data.arrayBuffer()) : new Uint8Array(data)
      if (bytes.length > MAX_PAYLOAD) throw new Error('Split the print job: this POS allows at most 10 MiB per intent.')
      const records = await journal.list()
      if (records.filter((r) => r.request).length >= 1000) throw new Error('Resolve outstanding print intents before adding more documents.')
      const resident = records.reduce((n, r) => n + (r.request?.dataBase64?.length || 0), 0)
      if (resident + bytes.length * 4 / 3 > 64 * 1024 * 1024) throw new Error('Resolve outstanding print jobs before adding more documents.')
      const intentId = crypto.randomUUID(), jobTitle = `${String(title || reference?.name || 'POS print').slice(0, 190)} [POS:${intentId}]`
      const request = { printerId, format, options: format === 'raw' ? { copies } : options, title: jobTitle, idempotencyKey: intentId, dataBase64: toBase64(bytes) }
      const digest = toBase64(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(request)))))
      const record = { key, intentId, title: jobTitle, profile, role, printerId, format, reference, user, reprintOf, automatic, workstation: await device(), payloadHash: digest, request, state: 'prepared', createdAt: now(), updatedAt: now() }
      await journal.put(record) // Durable request and key BEFORE calling the bridge.
      try { await authorize(record) }
      catch (error) { await journal.put({ ...record, state: 'failed', error: error.message }); await refreshJobs().catch(() => {}); throw error }
      return submit(record)
    }).finally(() => busyKeys.delete(key))
    busyKeys.set(key, pending)
    return pending
  }
  async function submit(record) {
    if (!record.request) throw new Error('The original payload is no longer retained. Create an authorized reprint.')
    const sending = { ...record, state: 'submitting', updatedAt: now() }
    await journal.put(sending)
    try {
      const { dataBase64, ...request } = record.request
      const job = await client.print({ ...request, data: fromBase64(dataBase64) })
      const updated = await observe(sending, job)
      await refreshJobs()
      return updated
    } catch (error) {
      // No alternate output, no implicit retry: the native queue may have accepted.
      const rejected = REFRESH_ERRORS.has(error.code) || ['PRINTER_NOT_FOUND', 'UNSUPPORTED_OPTION', 'PAYLOAD_LIMIT', 'IDEMPOTENCY_CONFLICT', 'INVALID_PARAMS'].includes(error.code)
      const updated = { ...sending, state: rejected ? 'failed' : 'unknown', error: recoveryMessage(error), updatedAt: now() }
      await journal.put(updated)
      if (REFRESH_ERRORS.has(error.code)) { state.connection = 'approval-required'; await journal.saveSetting('approved', false) }
      try { await report(updated) } catch { /* Reconcile later. */ }
      await refreshJobs().catch(() => {})
      return await journal.get(updated.key)
    }
  }
  async function retry(key) {
    return lock(`esafepos-print:${key}`, async () => {
      await connect(); await refreshJobs()
      const record = await journal.get(key)
      if (!record || !['prepared', 'unknown', 'failed'].includes(record.state) || record.agentJobId) throw new Error('Inspect the existing job. Reprinting an accepted job needs a new authorized intent.')
      await authorize(record)
      return submit(record) // Exactly the stored bytes, options and idempotency key.
    })
  }
  async function cancel(key) {
    const record = await journal.get(key)
    if (!record?.agentJobId) throw new Error('No accepted native job is known. Refresh its status first.')
    return observe(record, await client.jobs.cancel(record.agentJobId))
  }
  async function reprint(key) {
    const busyKey = `reprint:${key}`
    if (busyKeys.has(busyKey)) return busyKeys.get(busyKey)
    const pending = createReprint(key).finally(() => busyKeys.delete(busyKey))
    busyKeys.set(busyKey, pending)
    return pending
  }
  async function createReprint(key) {
    const original = await journal.get(key)
    if (!original?.agentJobId) throw new Error('Refresh the original job before requesting another copy.')
    await connect()
    const id = crypto.randomUUID()
    const record = { ...original, key: id, intentId: id, reference: { ...original.reference, reprint: 1 },
      reprintOf: original.intentId, nativeReprint: true, automatic: false, state: 'prepared', agentJobId: null, error: '', createdAt: now(), updatedAt: now() }
    delete record.request
    await journal.put(record)
    try { await authorize(record) }
    catch (error) { await journal.put({ ...record, state: 'failed', error: error.message }); await refreshJobs().catch(() => {}); throw error }
    await journal.put({ ...record, state: 'submitting' })
    try { return await observe(record, await client.jobs.reprint(original.agentJobId, id)) }
    catch (error) { const unknown = { ...record, state: 'unknown', error: recoveryMessage(error) }; await journal.put(unknown); throw error }
    finally { await refreshJobs().catch(() => {}) }
  }
  async function preview(profile, role, format, data, options = {}) {
    const selected = await binding(profile)
    if (!selected[role]) throw new Error('Select and approve a printer before previewing.')
    return client.preview({ printerId: selected[role], format, data, options })
  }
  async function resume() {
    if (!initialized) {
      initialized = true
      off.push(client.on('job.changed', (job) => { (async () => {
        const rows = await journal.list()
        const found = rows.find((r) => r.agentJobId === job.id) || rows.find((r) => !r.agentJobId && !r.nativeReprint && r.title === job.title && r.printerId === job.printerId)
        if (found) await observe(found, job)
        state.jobs = (await journal.list()).sort((a, b) => b.createdAt - a.createdAt).slice(0, 100)
      })().catch((e) => { state.error = recoveryMessage(e) }) }), client.on('resync', () => { refreshJobs().catch((e) => { state.error = recoveryMessage(e) }) }), client.on('connection.closed', () => {
        state.connection = 'disconnected'
        if (!pairing && !connecting && !stopped) reconnect().catch(() => {})
      }))
    }
    state.jobs = (await journal.list()).sort((a, b) => b.createdAt - a.createdAt).slice(0, 100)
    state.documents = await journal.setting('document-fallbacks') || []
    if (await journal.setting('approved')) await connect().catch((e) => { state.error = recoveryMessage(e) })
  }
  async function reconnect() {
    if (reconnecting || stopped || !await journal.setting('approved')) return
    reconnecting = true
    try { for (const delay of [1000, 2500, 5000]) { await wait(delay); if (stopped) break; try { await connect(); break } catch { if (state.connection === 'approval-required') break } } }
    finally { reconnecting = false }
  }
  function disconnect() { stopped = true; client.disconnect(); state.connection = 'disconnected' }
  function dispose() { disconnect(); off.splice(0).forEach((f) => f()); initialized = false }
  return { state, binding, saveBinding, rememberDocument, connect, refreshPrinters, capabilities, refreshJobs, dispatch, retry, reprint, cancel, preview, resume, disconnect, dispose }
}
