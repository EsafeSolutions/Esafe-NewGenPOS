<template>
  <section class="catalogue-workspace">
    <header class="catalogue-heading"><div><h2>{{ t('Menu & catalogue') }}</h2><p>{{ t('All selling items, grouped for customers. Prepare one document to print or export as PDF.') }}</p></div><button class="btn btn-outline" :disabled="!profile || loading || preparing || session.offline" @click="loadAll">{{ t('Refresh all items') }}</button></header>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="session.offline" class="notice">{{ t('Reconnect to load current prices. A prepared document remains available to print or export.') }}</p>
    <div class="catalogue-layout">
      <div class="catalogue-controls">
        <label class="field"><span>{{ t('Outlet') }}</span><select v-model="profile" :disabled="loading || preparing" :aria-label="t('Catalogue outlet')"><option value="">{{ t('Choose an outlet') }}</option><option v-for="name in profiles" :key="name">{{ name }}</option></select></label>
        <p v-if="loading" role="status">{{ t('Loading all items…') }} {{ rows.length }}</p>
        <button v-if="loading" class="btn btn-outline" @click="cancelLoad">{{ t('Cancel loading') }}</button>
        <fieldset :disabled="!loaded || loading || preparing">
          <label class="field"><span>{{ t('Document title') }}</span><input v-model="options.title" :aria-label="t('Catalogue title')" maxlength="100" /></label>
          <div class="control-pair"><label class="field"><span>{{ t('Layout') }}</span><select v-model="options.mode" :aria-label="t('Catalogue layout')"><option value="catalogue">{{ t('Product catalogue') }}</option><option value="menu">{{ t('Compact menu') }}</option></select></label><label class="field"><span>{{ t('Paper') }}</span><select v-model="options.paper" :aria-label="t('Catalogue paper')"><option>A4</option><option>Letter</option></select></label></div>
          <label class="field"><span>{{ t('Group items by') }}</span><select v-model="options.grouping" :aria-label="t('Catalogue grouping')"><option value="category-brand">{{ t('Category, then brand') }}</option><option value="brand-category">{{ t('Brand, then category') }}</option></select></label>
          <div class="control-pair"><label class="field"><span>{{ t('Category') }}</span><select v-model="category" :aria-label="t('Catalogue category')"><option value="">{{ t('All categories') }}</option><option v-for="name in categories" :key="name">{{ name }}</option></select></label><label class="field"><span>{{ t('Brand') }}</span><select v-model="brand" :aria-label="t('Catalogue brand')"><option value="">{{ t('All brands') }}</option><option v-for="name in brands" :key="name">{{ name }}</option></select></label></div>
          <label class="field"><span>{{ t('Find items') }}</span><input v-model="search" :aria-label="t('Catalogue item search')" :placeholder="t('Name, code or description')" /></label>
          <div class="catalogue-toggles"><label><input v-model="options.images" type="checkbox" />{{ t('Product images') }}</label><label><input v-model="options.descriptions" type="checkbox" />{{ t('Full descriptions') }}</label><label><input v-model="options.discounts" type="checkbox" />{{ t('Discounts and offer details') }}</label></div>
          <p class="selection-summary">{{ selected.length }} / {{ rows.length }} {{ t('items selected') }}</p>
          <button class="btn btn-primary" :disabled="!selected.length" @click="prepare">{{ t('Prepare complete document') }}</button>
        </fieldset>
        <p v-if="progress" role="status">{{ progress }}</p>
        <p v-if="meta" class="pricing-note">{{ meta.price_note }}<br />{{ t('Prices checked') }}: {{ meta.generated_at }} · {{ meta.pricing_engine }}</p>
        <p v-if="missing.length" class="notice" role="status">{{ missing.length }} {{ t('product images could not be loaded; their positions use a No image placeholder. Retry preparation or turn images off if needed.') }}</p>
      </div>
      <div class="catalogue-preview">
        <div class="preview-toolbar"><div><strong>{{ prepared ? prepared.count : selected.length }} {{ t('items') }}</strong><span v-if="prepared"> · {{ prepared.doc.pages.length }} {{ t('pages in one document') }}</span></div><div class="output-actions"><button class="btn btn-outline" :disabled="!prepared || preparing || loading" @click="print">{{ t('Print catalogue') }}</button><button class="btn btn-primary" :disabled="!prepared || preparing || loading" @click="pdf">{{ t('Export one PDF') }}</button></div></div>
        <div v-if="!prepared" class="catalogue-empty"><Icon name="report" :size="30" /><h3>{{ t('Prepare your menu or catalogue') }}</h3><p>{{ t('Every selected item is included. Categories and brands stay together, and long descriptions continue onto the following page.') }}</p></div>
        <iframe v-else :srcdoc="prepared.html" sandbox="" :title="t('Menu and catalogue preview')"></iframe>
      </div>
    </div>
  </section>
</template>
<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { call } from '../api'
import { t } from '../i18n'
import { useSessionStore } from '../stores/session'
import Icon from '../components/Icon.vue'
import { cataloguePages } from '../catalogue/document.js'
import { browserPrint, cataloguePdf, documentHtml, downloadPdf, loadImages } from '../catalogue/output.js'
const session = useSessionStore()
const profiles = computed(() => [...new Set([session.posProfile, ...(session.availableProfiles || [])].filter(Boolean))])
const profile = ref(session.posProfile || profiles.value[0] || '')
const rows = ref([]), meta = ref(null), loaded = ref(false), loading = ref(false), preparing = ref(false), error = ref(''), progress = ref(''), prepared = ref(null), missing = ref([])
const category = ref(''), brand = ref(''), search = ref('')
const options = ref({ title: 'Product catalogue', mode: 'catalogue', paper: 'A4', grouping: 'category-brand', images: true, descriptions: true, discounts: true })
const categories = computed(() => [...new Set(rows.value.map(row => row.category || 'Uncategorised'))].sort())
const brands = computed(() => [...new Set(rows.value.map(row => row.brand || 'Unbranded'))].sort())
const selected = computed(() => rows.value.filter(row => (!category.value || (row.category || 'Uncategorised') === category.value) && (!brand.value || (row.brand || 'Unbranded') === brand.value) && (!search.value || `${row.item_name} ${row.item_code} ${row.description}`.toLocaleLowerCase().includes(search.value.toLocaleLowerCase()))))
let generation = 0
function cancelLoad() { generation++; loading.value = false; loaded.value = false; progress.value = ''; error.value = t('Loading cancelled. Refresh all items before preparing a document.') }
async function loadAll() {
  if (!profile.value || session.offline) return
  const seq = ++generation, outlet = profile.value
  rows.value = []; prepared.value = null; missing.value = []; loaded.value = false; loading.value = true; error.value = ''; category.value = ''; brand.value = ''; progress.value = ''
  let after = ''; const seen = new Set()
  try {
    do {
      const data = await call('esafepos.api.print_catalogue.page', { pos_profile: outlet, after }, { timeout: 60000 })
      if (seq !== generation) return
      for (const row of data.items) {
        if (seen.has(row.item_code)) throw new Error(t('The item list changed while loading. Refresh all items and try again.'))
        seen.add(row.item_code); rows.value.push(row)
      }
      meta.value = data
      if (data.has_more && (!data.next || data.next === after)) throw new Error(t('The catalogue could not load its next page. Refresh all items.'))
      after = data.has_more ? data.next : ''
    } while (after)
    loaded.value = true
  } catch (e) { if (seq === generation) error.value = e.message }
  finally { if (seq === generation) loading.value = false }
}
async function prepare() {
  if (!loaded.value || !selected.value.length || preparing.value) return
  preparing.value = true; error.value = ''; prepared.value = null; missing.value = []
  try {
    const items = [...selected.value], settings = { ...options.value }
    const assets = settings.images ? await loadImages(items, (done, total) => { progress.value = `${t('Preparing images')} ${done} / ${total}` }) : { images: {}, missing: [] }
    const doc = cataloguePages(items, meta.value, settings, assets.images)
    prepared.value = { doc, count: items.length, html: documentHtml(doc), title: settings.title }
    missing.value = assets.missing
  } catch (e) { error.value = e.message }
  finally { preparing.value = false; progress.value = '' }
}
async function print() {
  if (!prepared.value || preparing.value) return
  preparing.value = true; error.value = ''
  try { await browserPrint(prepared.value.doc) } catch (e) { error.value = e.message }
  finally { preparing.value = false }
}
async function pdf() {
  if (!prepared.value || preparing.value) return
  preparing.value = true; error.value = ''
  let stream
  try {
    const name = `${(prepared.value.title || 'catalogue').replace(/[^a-z0-9_-]/gi, '-')}.pdf`
    if (typeof window.showSaveFilePicker === 'function') {
      const handle = await window.showSaveFilePicker({ suggestedName: name, types: [{ description: 'PDF document', accept: { 'application/pdf': ['.pdf'] } }] })
      stream = await handle.createWritable()
    }
    const blob = await cataloguePdf(prepared.value.doc, (page, total) => { progress.value = `${t('Exporting PDF')} ${page} / ${total}` }, stream)
    if (stream) await stream.close()
    else downloadPdf(blob, name)
  }
  catch (e) { if (stream) await stream.abort().catch(() => {}); if (e.name !== 'AbortError') error.value = e.message }
  finally { preparing.value = false; progress.value = '' }
}
watch([options, category, brand, search], () => { prepared.value = null; missing.value = [] }, { deep: true })
watch(profile, loadAll, { immediate: true })
onBeforeUnmount(() => { generation++ })
</script>
<style scoped>
.catalogue-workspace{padding:24px;max-width:1500px;margin:auto;width:100%;box-sizing:border-box}.catalogue-heading{display:flex;align-items:start;justify-content:space-between;gap:20px;margin-bottom:22px}h2{font-size:21px;margin:0}p{font-size:12px;line-height:1.7;color:var(--text-muted)}.catalogue-layout{display:grid;grid-template-columns:330px minmax(0,1fr);gap:24px}.catalogue-controls{min-width:0}.field{display:flex;flex-direction:column;gap:6px;font-size:12px;margin-bottom:15px}.control-pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}input,select{width:100%;box-sizing:border-box;font:inherit;padding:9px;border:1px solid var(--border);border-radius:var(--radius);background:var(--input-bg);color:var(--text)}fieldset{border:0;margin:0;padding:0;min-width:0}.catalogue-toggles{display:grid;gap:12px;margin:10px 0 20px}.catalogue-toggles label{display:flex;align-items:center;gap:8px;font-size:12px}.catalogue-toggles input{width:15px;flex:none}.selection-summary{font-weight:650;color:var(--text)}.catalogue-preview{min-width:0;background:var(--input-bg);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}.preview-toolbar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;padding:14px;background:var(--card-bg);border-bottom:1px solid var(--border);font-size:12px}.output-actions{display:flex;gap:8px}.catalogue-preview iframe{display:block;width:100%;height:760px;border:0}.catalogue-empty{padding:80px 30px;max-width:380px;margin:auto;text-align:center}.catalogue-empty h3{font-size:16px}.error{color:var(--red)}.notice{border-left:3px solid var(--brand);padding:8px 12px}.pricing-note{border-top:1px solid var(--border);padding-top:14px}@media(max-width:1000px){.catalogue-layout{grid-template-columns:290px minmax(0,1fr)}.catalogue-workspace{padding:18px}.output-actions{flex-wrap:wrap}}@media(max-width:760px){.catalogue-layout{grid-template-columns:1fr}.catalogue-heading{flex-direction:column}.catalogue-preview iframe{height:650px}}@media(max-width:420px){.catalogue-workspace{padding:14px}.control-pair{grid-template-columns:1fr}.output-actions{width:100%}.output-actions .btn{flex:1}}
</style>
