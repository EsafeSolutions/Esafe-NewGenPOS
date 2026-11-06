<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<!-- One table of products added up (lumenpos.api.reports._grouped): sold,
     returned, net quantity and net sales, and the cost, gross profit and margin
     when the server sent them. -->
<template>
  <div class="wrap">
    <table class="rt">
      <thead>
        <tr>
          <th>{{ head }}</th>
          <th v-if="detail">{{ t('Item group') }}</th>
          <th class="num">{{ t('Sold') }}</th>
          <th class="num">{{ t('Returned') }}</th>
          <th class="num">{{ t('Net sales') }}</th>
          <template v-if="withProfit">
            <th class="num">{{ t('Cost') }}</th>
            <th class="num">{{ t('Gross profit') }}</th>
            <th class="num">{{ t('Gross margin') }}</th>
          </template>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.key">
          <td class="who">
            <bdi>{{ r.label || t('None') }}</bdi>
            <span v-if="detail && r.key !== r.label" class="muted small">&nbsp;<bdi>{{ r.key }}</bdi></span>
          </td>
          <td v-if="detail"><bdi>{{ r.item_group }}</bdi></td>
          <td class="num">{{ qty(r.sold) }}</td>
          <td class="num"><span :class="{ muted: !r.returned }">{{ qty(r.returned) }}</span></td>
          <td class="num strong"><bdi>{{ money(r.net, currency) }}</bdi></td>
          <template v-if="withProfit">
            <td class="num"><bdi>{{ money(r.cost, currency) }}</bdi></td>
            <td class="num" :class="{ loss: r.profit < 0 }"><bdi>{{ money(r.profit, currency) }}</bdi></td>
            <td class="num" :class="{ loss: r.margin !== null && r.margin < 0 }"><bdi>{{ r.margin === null ? '' : r.margin + '%' }}</bdi></td>
          </template>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { t } from '../i18n'
import { money } from '../format'

defineProps({
  rows: { type: Array, required: true },
  head: { type: String, default: '' },
  currency: { type: String, default: '' },
  withProfit: { type: Boolean, default: false },
  detail: { type: Boolean, default: false },
})
const qty = (v) => Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 3 })
</script>

<style scoped>
.wrap { overflow-x: auto; }
.rt { width: 100%; border-collapse: collapse; font-size: 13px; }
.rt th { text-align: start; font-weight: 600; color: var(--text-muted); font-size: 12px; padding: 8px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; }
.rt td { padding: 8px 10px; border-bottom: 1px solid var(--border-subtle); vertical-align: top; }
.rt .num { text-align: end; white-space: nowrap; font-variant-numeric: tabular-nums; }
.rt .strong { font-weight: 700; }
.rt .who { min-width: 160px; }
.loss { color: var(--red); font-weight: 600; }
</style>
