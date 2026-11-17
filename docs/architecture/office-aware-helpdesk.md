# CBSUA Office-Aware Helpdesk Architecture

## Module and DocTypes

CBSUA-owned records live in the **CBSUA** module and use the `CB` prefix:

- `CB Office` — the service destination selected by a requester.
- `CB Office Request Type` — a request category owned by one office.
- `CB Team Office` — child table mapping an existing `HD Team` to one or more offices.

The Frappe Helpdesk-owned `HD Team` and `HD Ticket` remain their original DocTypes. Their CBSUA-specific fields are installed as app-managed Custom Fields and link to the CB DocTypes.

## Baseline configuration

| Office | Request types |
|---|---|
| ICT Office | Tech Support, Inquiry |
| Registrar's Office | Inquiry |
| Admissions Office | Inquiry |
| Cashier's Office | Inquiry |

ICT is selected as the initial default in `HD Settings` under the **CBSUA Routing** tab. Administrators can change the default office there. Office and request-type records are managed from the **CBSUA Office Routing** card in the Helpdesk workspace.

## Teams and routing

Open Helpdesk → Agent Configuration → Team to edit an existing `HD Team`. Use **Assigned Offices** to map the team to every office it serves. A team can serve multiple offices. Do not infer office assignment from the team's name or its members.

A ticket stores `office` and `request_type`. The request type must be enabled and belong to the selected office. An assigned team must explicitly serve that office. A user resolving a ticket must be a member of the assigned team; System Manager and Administrator retain administrative override.

## Link-field permissions

Frappe Link controls check `select` permission when searching linked records. Read permission alone is insufficient. Installation and migration explicitly grant read/select to System Manager, Administrator, Agent Manager, Agent, HD Customer, and HD Customer Manager for `CB Office` and `CB Office Request Type`. Customer-facing listing APIs return only enabled offices and office-scoped request types.

## Boot lifecycle

- Fresh install creates app-managed ticket/team/settings fields, seeds baseline offices and request types, and grants Link permissions.
- Migration re-applies the app-managed fields and idempotent bootstrap.
- The bootstrap does not overwrite office names, codes, enabled states, or request-type configuration once records exist.
- No team is automatically assigned to an office. Administrators make that operational decision.

## Documentation index

- [Office administration](../configuration/offices.md)
- [Request type administration](../configuration/request-types.md)
- [Team-office assignment](../configuration/teams.md)
- [Boot refactor and acceptance tests](../development/boot-refactor.md)
