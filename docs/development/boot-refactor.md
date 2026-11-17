# Office-aware boot refactor

## Lifecycle

- `after_install` calls `bootstrap_offices()` after the app's standard DocTypes and defaults are installed.
- `patches.txt` invokes `helpdesk.setup.office_bootstrap.execute` after model sync for existing installations.
- `after_migrate` runs the same idempotent bootstrap so a missed or interrupted baseline setup can be repaired.

## Idempotency

The bootstrap inserts only missing office codes and request type codes. It does not overwrite labels, enabled flags, default selections, office-team mappings, or team members. It does not create or assign teams automatically.

## Validation

`helpdesk.setup.office_routing` centralizes ticket defaults, office/type validation, team-office checks, and resolution membership checks. Hooks run for desk, portal, API, and import document writes.
