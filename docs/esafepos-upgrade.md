# Upgrade an existing site to ESAFE POS

The new Bench app, Python package and API namespace are `esafepos`. The till URL stays at `/pos`. This procedure is for a self-hosted Bench or a Bench administrator who can run a site console.

1. Let all tills reconnect and confirm their offline sales logs are clear. This step is required because the renamed till starts with a new browser database. Wait for register jobs to finish and close the till tabs. Put the site into maintenance mode and take a database and files backup. Test the procedure on a restored copy first.
2. Make the new `esafepos` package available on the Bench with `bench get-app https://github.com/EsafeSolutions/Esafe-NewGenPOS`. Keep the previous checkout available until all sites on that Bench have been migrated. Use the upgrade procedure for existing sites. The regular `install-app` command is for fresh sites.
3. Open `bench --site yoursite console` and run this once per existing site:

   ```python
   from esafepos.site_upgrade import execute

   execute(previous_app="previous_app_id")
   ```

   Replace `previous_app_id` with the old POS app ID shown by `bench --site yoursite list-apps`. The upgrade moves the existing app registration, settings, app-owned records, roles and custom fields into the new namespace. It stops if the old and new records would collide. If it raises an error, keep the site in maintenance mode and investigate on the backed-up copy before proceeding.
4. Run `bench --site yoursite migrate` and `bench --site yoursite clear-cache`. Verify that existing roles still open the till, the settings and audit log are present, and a sale posts to the configured ERPNext invoice type. Take the site out of maintenance mode and reopen the till while online to rebuild its local catalog.
5. Update custom integrations to call `esafepos.api.*` and to use the new names of app-owned fields and roles. The Stock app and Reports integration each need a version that supports this namespace. When every site on the Bench has been migrated, the Bench administrator can retire the previous checkout.
