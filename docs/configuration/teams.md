# Team and Office Administration

CBSUA uses the existing Helpdesk `HD Team` DocType. Each team keeps its native
agent membership and assignment rule; the app adds an **Assigned Offices**
Table MultiSelect backed by `CB Team Office`.

## Baseline teams

The installer and migration bootstrap create these office teams:

| Helpdesk team | Assigned office |
| --- | --- |
| ICT Support Team | ICT Office |
| Registrar Support Team | Registrar's Office |
| Admissions Support Team | Admissions Office |
| Cashier Support Team | Cashier's Office |

The CBSUA installer no longer seeds the generic **Billing** or **Product Experts** teams. Existing records on upgraded sites are left untouched; this change does not delete historical team records.

## Configure agents

Open **Helpdesk → Agent Configuration → Team** and edit the appropriate office
team. Add the staff accounts to its **Users** table. The team is created with no
members on a fresh install, so its generated support-rotation Assignment Rule
stays disabled until users are assigned.

A team can serve more than one office. The bootstrap only adds its baseline
office mapping; it does not remove additional mappings, change membership,
enable a disabled team, or overwrite its assignment-rule configuration.

## Routing behavior

Tickets retain the standard `HD Ticket.agent_group` relationship to `HD Team`.
The CBSUA office is stored separately on the ticket. For new tickets, the
request type's configured team is applied automatically when no team was
selected. This is a soft default: Administrator and System Manager may
deliberately assign a ticket to any Helpdesk team, including one mapped to
another office. Other users must select a team mapped to the ticket's office.
The office and request type are not rewritten when an administrator changes
the team, and the default is not reapplied on later edits.

Only members of the assigned team may resolve that team's office tickets;
System Manager and Administrator retain the documented administrative
override. Configure team membership before enabling the teams for live service.
