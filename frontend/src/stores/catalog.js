// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
// "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
import { defineStore } from 'pinia'
import { call, OfflineError } from '../api'
import {
  saveCatalog,
  searchCatalog,
  saveCustomers,
  patchCatalogStock,
  patchCatalogStockBy,
  patchCatalogItems,
  kvSet,
} from '../offline'
import { useSessionStore } from './session'
import { notifyCatalogChanged } from '../catalogSync'
import { applyStockLevel } from '../itemStock'

const PAGE_SIZE = 80

export function scaleBarcodeOptions(settings) {
  if (Number(settings?.enable_scale_barcodes ?? 1) === 0) return null
  return {
    prefixes: settings?.scale_barcode_prefixes?.split(',').map((prefix) => prefix.trim()),
    pluLen: Number(settings?.scale_barcode_plu_len ?? 5),
    decimals: Number(settings?.scale_barcode_weight_decimals ?? 3),
  }
}

export const useCatalogStore = defineStore('catalog', {
  state: () => ({
    items: [],
    loading: false,
    search: '',
    itemGroup: '',
    brand: '',
    hasMore: false,
    _query: '',
    _searchTimer: null,
    _requestId: 0,
    _liveRequest: 0,
    _catalogEpoch: 0,
    liveRevision: 0,
    liveLastSync: 0,
    liveError: '',
    liveExtraCodes: [],
  }),

  getters: {
    brands: (state) => [...new Set([...useSessionStore().itemBrands, ...state.items.map((item) => item.brand).filter(Boolean)])]
      .sort((a, b) => a.localeCompare(b)),
  },

  actions: {
    signalChange() {
      this._catalogEpoch++
      this._liveRequest++
      this._requestId++; this.loading = false
      notifyCatalogChanged()
    },

    applyLiveUpdate(snapshot, { upsert = false } = {}) {
      if (!snapshot) return { pricesChanged: false }
      const removed = new Set(snapshot.removed || [])
      const rows = snapshot.items || []
      let changed = removed.size > 0, pricesChanged = removed.size > 0
      for (const row of rows) {
        const existing = this.items.find(item => item.item_code === row.item_code)
        if (!existing) {
          pricesChanged = true
          const session = useSessionStore(), term = this.search.trim().toLowerCase()
          const groups = this.itemGroup ? session.itemGroupMembers?.[this.itemGroup] || [this.itemGroup] : null
          if (upsert && (!groups || groups.includes(row.item_group)) && (!this.brand || row.brand === this.brand) &&
              (!term || [row.item_name, row.item_code, row.barcode].some(value => String(value || '').toLowerCase().includes(term)))) {
            this.items.push({ ...row }); changed = true
          }
          continue
        }
        if (JSON.stringify([existing.price, existing.standard_price, existing.selling_units]) !==
            JSON.stringify([row.price, row.standard_price, row.selling_units])) pricesChanged = true
        if (JSON.stringify(existing) !== JSON.stringify(row)) changed = true
        Object.assign(existing, row)
      }
      if (removed.size) this.items = this.items.filter(item => !removed.has(item.item_code))
      if (changed) { this._catalogEpoch++; this._requestId++; this.loading = false }
      patchCatalogItems(rows, [...removed]).catch(() => {})
      return { pricesChanged }
    },

    async refreshLive(extraCodes = []) {
      const session = useSessionStore()
      if (!session.posProfile || session.offline || this.loading) return false
      const profile = session.posProfile, epoch = this._catalogEpoch, id = ++this._liveRequest
      const codes = [...new Set([...this.items.map(item => item.item_code), ...this.liveExtraCodes, ...extraCodes].filter(Boolean))]
      const batches = []
      for (let start = 0; start < codes.length; start += 500) batches.push(codes.slice(start, start + 500))
      const snapshots = await Promise.all(batches.map(item_codes => call('esafepos.api.catalog_sync.item_updates', { pos_profile: profile, item_codes })))
      if (id !== this._liveRequest || profile !== session.posProfile || epoch !== this._catalogEpoch) return false
      const applied = this.applyLiveUpdate({ items: snapshots.flatMap(data => data.items || []), removed: snapshots.flatMap(data => data.removed || []) })
      this.liveLastSync = Date.now(); this.liveRevision++
      return { ...applied, items: snapshots.flatMap(data => data.items || []) }
    },
    async fetch(append = false) {
      const session = useSessionStore()
      if (!session.posProfile || (append && (this.loading || !this.hasMore))) return
      const profile = session.posProfile
      const filters = { search: this.search, item_group: this.itemGroup, brand: this.brand }
      const query = JSON.stringify([profile, filters])
      if (append && query !== this._query) return
      if (!append) clearTimeout(this._searchTimer)
      const requestId = ++this._requestId
      const current = () => requestId === this._requestId && profile === session.posProfile
      const start = append ? this.items.length : 0
      if (!append && query !== this._query) this.items = []
      this.loading = true
      try {
        // The offline catalog can be stock-only or capped. Browse live
        // pages while connected so a partial cache never ends the list.
        if (!session.offline) {
          try {
            const { items } = await call('esafepos.api.catalog.get_items', {
              pos_profile: profile, ...filters, start, limit: PAGE_SIZE,
            })
            if (!current()) return
            this.items = append ? [...this.items, ...items] : items
            this._query = query
            this.hasMore = items.length === PAGE_SIZE
            return items
          } catch (error) {
            if (!current()) return
            if (!(error instanceof OfflineError)) {
              if (!append) this.hasMore = false
              session.notify(error.message, true)
              return
            }
            session.markOffline()
          }
        }
        const group = filters.item_group
        const groups = group ? session.itemGroupMembers?.[group] || [group] : null
        const items = await searchCatalog(filters.search, groups, Infinity, filters.brand,
          scaleBarcodeOptions(session.settings)).catch(() => [])
        if (!current()) return
        this.items = items
        this._query = query
        this.hasMore = false
      } finally {
        if (current()) this.loading = false
      }
    },

    // Pull the whole catalog into IndexedDB so search is instant and the
    // POS keeps selling if the connection drops.
    async cacheFullCatalog() {
      const session = useSessionStore()
      const profile = session.posProfile
      const epoch = this._catalogEpoch
      if (!profile || session.offline) return
      try {
        const items = await call('esafepos.api.catalog.get_full_catalog', {
          pos_profile: profile,
        })
        if (session.posProfile !== profile || epoch !== this._catalogEpoch) return
        await saveCatalog(items)
        // Selling in another currency without a connection: each currency
        // walk-in's own prices (esafepos.currency.offline_prices).
        if (session.multiCurrency?.enabled) {
          const prices = await call('esafepos.currency.offline_prices', {
            pos_profile: session.posProfile,
          }).catch(() => null)
          if (prices) {
            session.offlinePrices = prices
            await kvSet('currency_prices', prices).catch(() => {})
          }
        }
      } catch {
        /* cache refresh is best-effort */
      }
    },

    // Cache a capped recent/frequent customer subset for offline SELECT (not the
    // full directory. See the offline-customers decision). Best-effort.
    async cacheCustomers() {
      const session = useSessionStore()
      if (!session.posProfile || session.offline) return
      try {
        const res = await call('esafepos.api.catalog.recent_customers', {
          pos_profile: session.posProfile,
        })
        await saveCustomers(res.customers || [])
      } catch {
        /* best-effort */
      }
    },

    // The server tells us what is left after a sale or a return (the same
    // number the till will refuse on). Write it onto the tiles AND the cache so
    // the quantity moves with the sale, not at the next catalogue refresh.
    applyStock(levels) {
      if (!levels) return
      const codes = Object.keys(levels)
      if (!codes.length) return
      this.signalChange()
      for (const item of this.items) {
        if (item.item_code in levels) applyStockLevel(item, levels[item.item_code])
      }
      patchCatalogStock(levels).catch(() => {
        /* the tiles are already right, the cache catches up on the next refresh */
      })
    },

    // Offline there is no server answer, so take the sold quantity off the
    // cached figure ourselves (negative qty for a return puts it back). The
    // sale's real answer replaces this estimate when the queue syncs. The
    // device's cache moves by the same amount for every item, on screen or
    // not: until 0.56.1 an item missing from the grid at that moment (another
    // search, another group) kept its old figure, so a return taken back from
    // History could stay hidden at 0.
    applyStockDelta(lines) {
      const deltas = {}
      for (const line of lines || []) {
        const code = line.item_code
        if (!code) continue
        deltas[code] = (deltas[code] || 0) + (Number(line.qty) || 0)
      }
      if (!Object.keys(deltas).length) return
      this._catalogEpoch++; this._liveRequest++
      for (const item of this.items) {
        if (item.is_stock_item && item.item_code in deltas) {
          applyStockLevel(item, (Number(item.actual_qty) || 0) - deltas[item.item_code])
        }
      }
      patchCatalogStockBy(deltas).catch(() => {
        /* the tiles are already right, the cache catches up on the next refresh */
      })
    },

    setSearch(value) {
      this.search = value
      this._requestId++
      this.hasMore = false
      clearTimeout(this._searchTimer)
      this._searchTimer = setTimeout(() => this.fetch(), useSessionStore().offline ? 60 : 250)
    },

    setGroup(group) {
      this.itemGroup = group || ''
      this.fetch()
    },

    setBrand(brand) {
      this.brand = brand || ''
      this.fetch()
    },

    clearSearch() {
      this.search = ''
      this.fetch()
    },
  },
})
