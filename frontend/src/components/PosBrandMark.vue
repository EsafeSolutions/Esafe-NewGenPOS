<!-- Copyright (c) 2026 Esafe (PVT) LTD
     SPDX-License-Identifier: AGPL-3.0-only
     "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md. -->
<template>
  <span class="brand-badge">
    <img :src="posIcon" alt="" width="36" height="36" />
  </span>
</template>

<script setup>
const posIcon = import.meta.env.BASE_URL + 'pos-icon.svg'
</script>

<style scoped>
.brand-badge {
  flex: none;
  width: 36px;
  height: 36px;
}
.brand-badge img {
  display: block;
}
</style>
