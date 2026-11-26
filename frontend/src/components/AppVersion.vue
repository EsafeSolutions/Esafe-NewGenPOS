<template>
  <button type="button" class="pos-version" :title="t('View POS version details')"
    :aria-label="`${t('POS version')} ${release}. ${t('View version details')}`" @click="dialog.showModal()">
    <Icon name="tag" :size="12" /><bdi>v{{ release }}</bdi>
  </button>
  <dialog ref="dialog" class="version-dialog" aria-labelledby="pos-version-title" @click.self="dialog.close()">
    <section class="version-content">
      <header><h2 id="pos-version-title"><Icon name="tag" /> {{ t('POS version') }}</h2><button type="button" class="btn btn-outline" :aria-label="t('Close version details')" @click="dialog.close()"><Icon name="close" /></button></header>
      <UpdatesPanel @navigate="dialog.close()" />
      <footer><button type="button" class="btn btn-primary" @click="dialog.close()">{{ t('Done') }}</button></footer>
    </section>
  </dialog>
</template>
<script setup>
import { ref } from 'vue'
import { t } from '../i18n'
import Icon from './Icon.vue'
import UpdatesPanel from './UpdatesPanel.vue'
import { interfaceVersion } from '../releaseNotes'
const release = interfaceVersion
const dialog = ref(null)
</script>
<style scoped>
.pos-version { display: inline-flex; align-items: center; gap: 4px; flex-shrink: 0; padding: 5px 8px; border-radius: 6px; border: 1px solid currentColor; color: var(--on-pos-blue-muted); background: transparent; font-size: 11px; line-height: 1.2; font-weight: 600; cursor: pointer; white-space: nowrap; transition: transform .16s ease, background .16s ease; }
.pos-version:hover { background: rgba(255, 255, 255, .16); transform: translateY(-1px); }
.pos-version:active { transform: translateY(1px); }
.pos-version:focus-visible { outline: 2px solid var(--brand-soft); outline-offset: 3px; }
.version-dialog { width: min(980px, calc(100vw - 32px)); max-height: calc(100dvh - 32px); padding: 0; border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--card-bg); color: var(--text); box-shadow: var(--shadow-md); }
.version-dialog::backdrop { background: rgba(0, 0, 0, .45); }
.version-dialog[open] { animation: version-open .16s ease-out; }
.version-content { padding: 20px; }
header { margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
h2 { display: flex; align-items: center; gap: 8px; font-size: 18px; margin: 0; }
footer { display: flex; justify-content: flex-end; margin-top: 20px; }
@keyframes version-open { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) { .pos-version { transition: none; transform: none !important; } .version-dialog[open] { animation: none; } }
</style>
