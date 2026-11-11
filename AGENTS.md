# Repository Guidelines

## Project Structure & Module Organization

`lumenpos/` is the Frappe app. Keep server-side business logic in `lumenpos/api/`, pure promotion rules in `lumenpos/promotions/`, DocType definitions in `lumenpos/lumenpos/doctype/`, and the `/pos` page shell in `lumenpos/www/`.

`frontend/` is the Vue 3/Vite POS client: views live in `frontend/src/views/`, reusable UI in `frontend/src/components/`, state in `frontend/src/stores/`, and global styles in `frontend/src/styles.css`. `lumenpos/public/pos/` is generated frontend output; rebuild it instead of editing it directly. User-facing documentation is in `docs/`.

## Build, Test, and Development Commands

- `cd frontend && npm ci` installs the locked frontend dependencies.
- `cd frontend && npm run dev` starts Vite on port 8080 and proxies API requests to a local bench on port 8000.
- `cd frontend && npm run build` rebuilds the committed production bundle in `lumenpos/public/pos/`.
- `python -m unittest lumenpos.promotions.test_engine` runs the standalone promotion-engine suite from the repository root.
- `python scripts/test_shift_schedule.py` validates scheduling edge cases.
- `cd frontend && node parity-check.mjs` verifies the browser promotion mirror matches Python rules. Run `node barcode-check.mjs` and `node clock-check.mjs` when changing those utilities.

## Coding Style & Naming Conventions

Use four spaces for Python and two spaces for Vue/JavaScript/CSS. Python modules and functions use `snake_case`; Vue components use `PascalCase` filenames (for example, `PaymentOverlay.vue`); composables and stores use clear `camelCase` exports. Keep API endpoints narrowly scoped and preserve the `lumenpos.api.*` namespace. Support Python 3.7 syntax compatibility.

Keep promotion behavior synchronized: update `lumenpos/promotions/engine.py`, `frontend/src/promotions.js`, and relevant parity scenarios together. Use existing CSS variables and component patterns instead of introducing one-off colors or controls.

## Testing Guidelines

Add focused `unittest` cases named `test_<behavior>` beside the affected Python feature. Cover boundary conditions—dates, currencies, quantities, permissions, and offline behavior—when they change. For visual Vue changes, build the bundle and attach desktop/mobile screenshots to the PR.

## Commit & Pull Request Guidelines

Recent commits use concise imperative summaries, often version-prefixed (for example, `0.69.0: stock count from the till`) or scoped documentation prefixes such as `docs(website-guide): ...`. Keep commits focused.

PRs should state the user impact, list verification commands, link the issue when applicable, and include screenshots for UI changes. Commit regenerated `lumenpos/public/pos/` assets with source changes under `frontend/src/`.

## Project Logbook Updates

For every project change or upgrade, update `docs/project-logbook-and-component-details.md` in the same change. Record the user-visible behavior and technical impact, the affected modules/components and data model where relevant, and the verification performed. For work not tied to a released version, add it under an `Unreleased` logbook heading; when a version is assigned, move or summarize the entry under that release. Keep the feature inventory, architecture, component responsibilities, and DocType overview current when the change affects them. Do not wait for the user to request this documentation update.
