# Private Esafe SDK

`esafe-printer-manager-0.1.0.tgz` is the supplied `@esafe/printer-manager` 0.1.0 package, copied unchanged from the local Esafe 0.1.0 integration kit. Its SHA-256 is `5585ee1882fd3a4b3d3d26011187bf1afb4d960420b5a4f274db2d3513085680`.

The relative `file:vendor/esafe-printer-manager-0.1.0.tgz` dependency and npm lockfile make deployment independent of the development workstation and a public npm registry. The tarball includes the supplier's ESM client, declarations and package metadata. Its API declarations/documentation and implementation were inspected before integration; do not replace it with a hand-written protocol or assume newer APIs exist.

To upgrade, obtain the approved private package and matching manager documentation, review API/protocol/permission changes, update the tarball/dependency/lockfile, run the integration checks and qualify hardware. See [deployment, cashier setup and limitations](../../docs/esafe-print-manager.md). Distribution/license terms remain those of the supplied private package; no new SDK license is asserted here.
