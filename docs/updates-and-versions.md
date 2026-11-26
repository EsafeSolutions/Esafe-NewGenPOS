# Updates and versions

The header shows the version of the interface this window is actually running. Select its **v0.70.0** badge, or open **Settings → Updates & versions**. **Status** also links to this screen. A window that postpones an update can keep an older interface while the server runs a newer release; both versions are shown separately.

**Check for updates** reads the deployed server version and release history. It never installs anything, clears a basket or restarts a till. **Review available update** returns to Sell (or Insights for reports-only users) and exposes the existing **Agree and update / Later** controls. Finish active work before agreeing. An interface rebuilt within the same version is still detected by its build reference. Deploying server code remains an administrator operation; this screen updates the till window after deployment.

Each recorded release has an update number, version, date and change list. Features have stable `F-001` IDs, improvements `I-001`, and fixes `X-001`. Counts come from these records, both across the recorded history and for each update. Search by version, title, description or ID and filter by change type; totals continue to describe the entire recorded release, while a separate line states how many filtered changes are shown.

Numbered tracking begins at **v0.70.0, Update #1**, with **6 features, 2 improvements and 1 fix (9 changes)**. Releases through v0.69.5 predate this tracking and are not assigned invented counts. Existing historical release notes remain in the user guide and Help. Current feature entries also feed the existing **What is new** card, including feature IDs and the displayed note count. Bundled notes remain available without a connection; checking the server requires a connection.

## Maintaining releases

`esafepos/__init__.py` is the authoritative package version. For each new release:

1. Assign the release version there and synchronize `frontend/package.json` and both root version fields in `frontend/package-lock.json`.
2. Set `current_version` and prepend the new record in `esafepos/release_notes.json`. Give it the next permanent update number, the same version and the release date. Retain previous records unchanged.
3. Add each user-visible feature, improvement and fix with the next unused ID for its type. Do not reuse IDs or update numbers. Counts are calculated from the arrays; there are no manual count fields to drift.
4. Update the user guide and project logbook, rebuild the committed production assets with `npm run build`, and deploy through the normal process. Vite rejects mismatched package/manifest versions, reused IDs, duplicate release versions and invalid update numbers. The compiled interface embeds the Python package version, so a cached interface cannot relabel itself as a newer server release.

The read-only `esafepos.api.updates.get_updates` endpoint serves the checked-in catalogue plus the existing deployed shell revision to signed-in users. No new DocType, database migration or client-side version editing is introduced by the version-management screen. Other features included in v0.70.0, such as bank display settings, retain their own migration requirements.

Verification: `node versions-browser-check.mjs`, `node update-check.mjs` and `node update-layout-check.mjs` from `frontend/`, production build, release JSON/version validation and Python 3.7 syntax checks. The browser fixtures exercise the actual App and Settings, stable counts/IDs, filtering/search, a newer server with the older running interface, offline/API failure, manual check without reload, retained active basket, review routing, keyboard focus, reduced motion and desktop/tablet/mobile layouts. See [desktop](screenshots/versions/updates-1440.png), [mobile](screenshots/versions/updates-390.png), and [version dialog](screenshots/versions/version-details-mobile.png).
