import catalog from '../../esafepos/release_notes.json'

export const interfaceVersion = __ESAFEPOS_VERSION__
export const bundledReleaseNotes = catalog
export const changeTypes = { feature: 'Features', improvement: 'Improvements', fix: 'Fixes' }
export const changeTypeNames = { feature: 'Feature', improvement: 'Improvement', fix: 'Fix' }

export function changeCounts(releases) {
  const counts = { updates: releases.length, feature: 0, improvement: 0, fix: 0, changes: 0 }
  for (const release of releases) {
    for (const change of release.changes || []) {
      if (Object.prototype.hasOwnProperty.call(changeTypes, change.type)) { counts[change.type]++; counts.changes++ }
    }
  }
  return counts
}

export function releaseNews() {
  return catalog.releases.flatMap(release => release.changes.filter(change => change.type === 'feature').map(change => ({
    ...change, version: release.version,
    when: change.audience === 'settings' ? session => Boolean(session.permissions.settings) : undefined,
  })))
}
