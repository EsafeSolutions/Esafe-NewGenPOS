<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<template>
  <span class="brand-badge">
    <img :src="esafeMark" alt="" width="26" height="20" />
  </span>
</template>

<script setup>
import esafeMark from '../assets/esafe-solutions-favicon.png'
</script>

<style scoped>
.brand-badge {
  display: grid;
  place-items: center;
  flex: none;
  width: 36px;
  height: 36px;
  border: 1px solid color-mix(in srgb, var(--brand-soft) 52%, transparent);
  border-radius: var(--radius);
  background: color-mix(in srgb, var(--topbar-bg) 75%, black);
}
.brand-badge img {
  object-fit: cover;
  object-position: center top;
}
</style>
