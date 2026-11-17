# CBSUA Office Routing Boot Refactor

## Module organization

CBSUA-owned DocTypes live in `helpdesk/cbsua/doctype/` and the `CBSUA` module. They use the `CB` prefix: `CB Office`, `CB Office Request Type`, and `CB Team Office`. Existing Frappe Helpdesk entities remain `HD` DocTypes; their app-owned fields are installed through `get_custom_fields()`.

## Lifecycle

- `after_install` installs CBSUA fields, seeds office/request-type records, and grants Link permissions.
- `patches.txt` and `after_migrate` call the idempotent bootstrap so existing installations receive the same setup.
- Helpdesk workspace exposes direct shortcuts to Offices and Office Request Types; HD Settings exposes the CBSUA Routing tab and default office.

## Link permissions

Frappe Link search requires `select` permission, not merely `read`. The bootstrap grants both to System Manager, Administrator, Agent Manager, Agent, HD Customer, and HD Customer Manager for the two linked master DocTypes.

## Acceptance checks

- [ ] Offices and request types are accessible from the Helpdesk workspace.
- [ ] Teams are accessible from Helpdesk → Agent Configuration → Team and show Assigned Offices.
- [ ] HD Settings exposes CBSUA Routing, and default office.
- [ ] Administrator and System Manager can search and select offices in Link fields.
- [ ] Customers can see only enabled offices and request types for the chosen office.
- [ ] Teams cannot be assigned tickets outside their mapped offices.
