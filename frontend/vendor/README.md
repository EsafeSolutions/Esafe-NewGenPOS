# Private Esafe SDK

`esafe-printer-manager-0.2.0.tgz` is the supplied `@esafe/printer-manager` 0.2.0 package, copied unchanged from `Esafe-POS-Cash-Drawer-Kit-0.2.1.zip`. Its SHA-256 is `808e3066a5bf32a3fa548ab4812de706581752766a490ec580685b3f2da97143`. Manager 0.2.1 adds native drawer controls; the SDK helper uses protocol-1 raw printing and also supports manager 0.2.0. The previous 0.1.0 tarball is retained only as historical rollback material.

The relative `file:vendor/esafe-printer-manager-0.2.0.tgz` dependency and npm lockfile make deployment independent of the development workstation and a public npm registry. The tarball includes the supplier's ESM client, declarations and package metadata. Its API declarations/documentation and implementation were inspected before integration; do not replace it with a hand-written protocol or assume newer APIs exist.

To upgrade, obtain the approved private package and matching manager documentation, review API/protocol/permission changes, update the tarball/dependency/lockfile, run the integration checks and qualify hardware. See [deployment, cashier setup and limitations](../../docs/esafe-print-manager.md). Distribution/license terms remain those of the supplied private package; no new SDK license is asserted here.
