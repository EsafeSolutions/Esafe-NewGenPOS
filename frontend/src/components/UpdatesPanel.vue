<template>
  <section class="updates-panel" :aria-labelledby="titleId">
    <header class="updates-heading"><div><span class="updates-eyebrow"><Icon name="refresh" /> {{ t('Release history') }}</span><h1 :id="titleId">{{ t('Updates & versions') }}</h1><p class="muted">{{ t('See what changed, count new features, and review available POS updates.') }}</p></div><button class="btn btn-outline" :disabled="checking || session.offline || updateBusy" @click="checkUpdates"><Icon name="refresh" :class="{ spinning: checking }" /> {{ checking ? t('Checking…') : t('Check for updates') }}</button></header>
    <div class="updates-versions card">
      <div><span>{{ t('Running interface') }}</span><strong><Icon name="monitor" /> <bdi>v{{ interfaceVersion }}</bdi></strong><small>{{ t('The version this window is using') }}</small></div>
      <div><span>{{ checkedVersion ? t('Latest on server') : t('Server at last connection') }}</span><strong><Icon name="company" /><bdi>{{ serverVersion ? `v${serverVersion}` : '—' }}</bdi></strong><small>{{ checkedAt ? t('Checked at {time}', { time: checkedAt }) : t('Check online for the latest deployed version') }}</small></div>
      <div><span>{{ t('Update status') }}</span><strong><Icon :name="available ? 'download' : checkedAt && !error ? 'check' : 'help'" /> {{ available ? t('Update available') : checkedAt && !error ? t('Up to date') : t('Ready to check') }}</strong><small>{{ available ? t('Your current work stays open until you agree') : t('Checking never restarts the till') }}</small></div>
    </div>
    <p v-if="session.offline" class="updates-note"><Icon name="help" /> {{ t('You are offline. Bundled release notes remain available; reconnect to check the server.') }}</p>
    <p v-if="error" role="alert" class="updates-error">{{ error }}</p>
    <p v-if="updateError" role="alert" class="updates-error">{{ updateError }}</p>
    <div v-if="available && controller" class="updates-offer"><div><b>{{ t('Review the update before restarting') }}</b><p>{{ t('Finish any sale, count or other task, then use Agree and update on Sell. You can keep working and update later.') }}</p></div><button class="btn btn-primary" :disabled="updateBusy || session.offline" @click="reviewUpdate"><Icon name="download" /> {{ t('Review available update') }}</button></div>
    <div class="updates-counts" :aria-label="t('Recorded update totals')"><div v-for="counter in counters" :key="counter.key"><span>{{ t(counter.label) }}</span><strong>{{ totals[counter.key] }}</strong></div></div>
    <p class="muted small">{{ t('Numbered history starts at v{version}. Counts cover recorded entries, not all older POS releases.', { version: notes.tracking_started }) }}</p>
    <div class="updates-filters"><label><Icon name="search" /><input v-model="search" :placeholder="t('Find a version, feature or change ID')" :aria-label="t('Search updates')" /></label><select v-model="filter" :aria-label="t('Change type')"><option value="all">{{ t('All changes') }}</option><option v-for="(label, key) in changeTypes" :key="key" :value="key">{{ t(label) }}</option></select></div>
    <article v-for="release in visibleReleases" :key="release.version" class="card update-release">
      <header class="release-heading"><div><span class="release-number">{{ t('Update #{n}', { n: release.number }) }} · <bdi>v{{ release.version }}</bdi></span><h2>{{ t(release.title) }}</h2><span class="muted small">{{ release.date }}</span></div><span class="release-state">{{ release.version === interfaceVersion ? t('Running version') : release.version === serverVersion ? t('Server version') : t('Recorded release') }}</span></header>
      <div class="release-counts"><span><b>{{ release.counts.feature }}</b> {{ t(release.counts.feature === 1 ? 'feature' : 'features') }}</span><span><b>{{ release.counts.improvement }}</b> {{ t(release.counts.improvement === 1 ? 'improvement' : 'improvements') }}</span><span><b>{{ release.counts.fix }}</b> {{ t(release.counts.fix === 1 ? 'fix' : 'fixes') }}</span><span><b>{{ release.counts.changes }}</b> {{ t('total changes') }}</span></div>
      <ol class="release-changes"><li v-for="change in release.visibleChanges" :key="change.id"><span class="change-symbol"><Icon :name="change.type === 'feature' ? 'plus' : change.type === 'fix' ? 'check' : 'refresh'" /></span><div><div class="change-heading"><b>{{ t(change.title) }}</b><span class="change-id"><bdi>{{ change.id }}</bdi> · {{ t(changeTypeNames[change.type]) }}</span></div><p>{{ t(change.text) }}</p></div></li></ol>
      <p v-if="release.visibleChanges.length !== release.changes.length" class="muted small release-filter-note">{{ t('{shown} of {total} changes shown for this update', { shown: release.visibleChanges.length, total: release.changes.length }) }}</p>
    </article>
    <p v-if="!visibleReleases.length" class="updates-note">{{ t('No recorded changes match this search.') }}</p>
    <details class="updates-guide"><summary><Icon name="help" /> {{ t('How versions, updates and feature counts work') }}</summary><p>{{ t('Each release has a version and an update number. Feature IDs start with F, improvements with I, and fixes with X. Counts come from the recorded list and do not change when you search or filter.') }}</p><p>{{ t('The running interface can be older than the server while an update is postponed. A rebuilt interface can also be available within the same release number. Review available update opens the existing agreement controls; checking and reading notes never install or restart anything.') }}</p><p>{{ t('Include the running version and build reference when asking for support. Server releases appear here after deployment; this screen manages the update of this till window.') }}</p><p class="muted small">{{ t('Version {version} and earlier predate the numbered history; their exact feature totals are not recorded here.', { version: notes.previous_version }) }}</p><bdi v-if="revision" class="build-reference">{{ t('Running build') }}: {{ revision }}</bdi></details>
  </section>
</template>
<script setup>
import { computed, getCurrentInstance, inject, ref } from 'vue'
import { call } from '../api'
import { useSessionStore } from '../stores/session'
import { bundledReleaseNotes, changeCounts, changeTypeNames, changeTypes, interfaceVersion } from '../releaseNotes'
import { t } from '../i18n'
import Icon from './Icon.vue'
const emit = defineEmits(['navigate'])
const titleId = `updates-title-${getCurrentInstance().uid}`
const session = useSessionStore(), controller = inject('posUpdates', null)
const notes = ref(bundledReleaseNotes), checking = ref(false), error = ref(''), checkedVersion = ref(''), checkedAt = ref(''), checkedRevision = ref('')
const search = ref(''), filter = ref('all')
const revision = window.esafepos_shell_revision || ''
const serverVersion = computed(() => checkedVersion.value || controller?.serverVersion?.value || session.settings?.version || '')
const available = computed(() => Boolean(controller?.revision?.value || checkedRevision.value && revision && checkedRevision.value !== revision))
const updateBusy = computed(() => Boolean(controller?.busy?.value))
const updateError = computed(() => controller?.error?.value || '')
const totals = computed(() => changeCounts(notes.value.releases))
const counters = [{ key: 'updates', label: 'Recorded updates' }, { key: 'feature', label: 'Features added' }, { key: 'improvement', label: 'Improvements' }, { key: 'fix', label: 'Fixes' }]
const visibleReleases = computed(() => {
  const query = search.value.trim().toLowerCase()
  return notes.value.releases.map(release => {
    const releaseMatch = `${release.version} ${release.number} ${release.title}`.toLowerCase().includes(query)
    const visibleChanges = release.changes.filter(change => (filter.value === 'all' || change.type === filter.value) &&
      (releaseMatch || `${change.id} ${change.title} ${change.text}`.toLowerCase().includes(query)))
    return { ...release, counts: changeCounts([release]), visibleChanges }
  }).filter(release => release.visibleChanges.length)
})
async function checkUpdates() {
  if (checking.value || session.offline) return
  checking.value = true; error.value = ''
  try {
    const result = await call('esafepos.api.updates.get_updates', {}, { timeout: 10000 })
    if (!result?.version || !result.revision || !Array.isArray(result.catalog?.releases)) throw new Error(t('The server could not provide release information. Bundled notes are still available.'))
    // Merge by version so an older server never erases the running bundle's notes.
    const releases = new Map(bundledReleaseNotes.releases.map(release => [release.version, release]))
    for (const release of result.catalog.releases) {
      if (!Array.isArray(release.changes)) continue
      releases.set(release.version, release)
    }
    notes.value = { ...bundledReleaseNotes, releases: [...releases.values()].sort((a, b) => b.number - a.number) }
    checkedVersion.value = result.version; checkedRevision.value = result.revision
    checkedAt.value = new Date().toLocaleTimeString()
    await controller?.check()
  } catch (e) { error.value = e.message || t('Could not check for updates. Try again when connected.') }
  finally { checking.value = false }
}
function reviewUpdate() { controller?.review(); emit('navigate') }
</script>
<style scoped>
.updates-panel { display: grid; gap: 16px; min-width: 0; }
.updates-heading, .release-heading, .updates-offer { display: flex; align-items: center; justify-content: space-between; gap: 20px; }
.updates-heading h1 { font-size: 27px; margin: 6px 0; letter-spacing: -.02em; }
.updates-heading p { margin: 0; font-size: 13px; line-height: 1.6; }
.updates-eyebrow { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; color: var(--brand-dark); }
.updates-versions { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); padding: 18px; gap: 20px; }
.updates-versions > div { display: grid; gap: 8px; align-content: start; min-width: 0; }
.updates-versions > div > span { font-size: 12px; color: var(--text-muted); }
.updates-versions strong { display: flex; align-items: center; gap: 7px; font-size: clamp(16px, 1.8vw, 21px); overflow-wrap: anywhere; }
.updates-versions small { font-size: 11px; line-height: 1.5; color: var(--text-muted); }
.updates-note, .updates-error, .updates-offer { margin: 0; padding: 14px; border-inline-start: 3px solid var(--brand); border-radius: var(--radius); background: var(--surface-2); font-size: 13px; line-height: 1.6; }
.updates-error { border-color: var(--red); color: var(--red); }
.updates-offer p { margin: 5px 0 0; }
.updates-counts { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; gap: 18px; }
.updates-counts > div { display: grid; gap: 6px; }
.updates-counts span { font-size: 12px; color: var(--text-muted); }
.updates-counts strong { font-size: 28px; font-variant-numeric: tabular-nums; }
.updates-panel > .small { margin: -8px 0 0; line-height: 1.6; }
.updates-filters { display: flex; gap: 10px; }
.updates-filters label { display: flex; align-items: center; gap: 10px; flex: 1; min-width: 0; }
.updates-filters input { width: 100%; min-width: 0; }
.updates-filters select { max-width: 45%; }
.update-release { padding: 20px; }
.release-number { color: var(--brand-dark); font-size: 12px; font-weight: 700; }
.release-heading h2 { font-size: 19px; margin: 8px 0; overflow-wrap: anywhere; }
.release-state { color: var(--brand-dark); background: var(--surface-2); padding: 6px 10px; border-radius: 6px; font-size: 11px; white-space: nowrap; }
.release-counts { display: flex; flex-wrap: wrap; gap: 10px 18px; padding: 14px 0; margin-top: 8px; border-bottom: 1px solid var(--border); color: var(--text-muted); font-size: 12px; }
.release-counts b { color: var(--text); }
.release-changes { list-style: none; padding: 0; margin: 0; }
.release-changes li { display: grid; grid-template-columns: 28px minmax(0, 1fr); gap: 12px; padding: 18px 0; border-bottom: 1px solid var(--border-subtle); }
.release-changes li:last-child { border-bottom: 0; padding-bottom: 0; }
.change-symbol { display: grid; place-items: center; align-self: start; width: 28px; height: 28px; background: var(--surface-2); color: var(--brand-dark); border-radius: 50%; }
.change-heading { display: flex; justify-content: space-between; gap: 8px; align-items: baseline; flex-wrap: wrap; }
.change-heading b { font-size: 14px; }
.change-id { color: var(--text-muted); font-size: 11px; white-space: nowrap; }
.release-changes p { font-size: 12px; line-height: 1.7; color: var(--text-muted); margin: 7px 0 0; }
.release-filter-note { margin-bottom: 0; }
.updates-guide { padding: 16px; background: var(--surface-2); border-radius: var(--radius); }
.updates-guide summary { cursor: pointer; font-size: 13px; font-weight: 600; }
.updates-guide p { font-size: 12px; line-height: 1.7; }
.build-reference { display: block; overflow-wrap: anywhere; color: var(--text-muted); font-size: 11px; }
.updates-panel button { transition: transform .16s ease, background .16s ease; }
.updates-panel button:hover:not(:disabled) { transform: translateY(-1px); }
.updates-panel button:active:not(:disabled) { transform: translateY(1px); }
.spinning { animation: updates-spin .8s linear infinite; }
@keyframes updates-spin { to { transform: rotate(360deg); } }
@media (max-width: 700px) { .updates-heading, .release-heading, .updates-offer { flex-direction: column; align-items: stretch; gap: 12px; } .updates-versions { grid-template-columns: minmax(0, 1fr); gap: 16px; } .updates-counts { grid-template-columns: repeat(2, minmax(0, 1fr)); } .update-release { padding: 16px; } .release-state { align-self: flex-start; } }
@media (prefers-reduced-motion: reduce) { .updates-panel button { transition: none; transform: none !important; } .spinning { animation: none; } }
</style>
