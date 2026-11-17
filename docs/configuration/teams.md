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

The generic **Billing** and **Product Experts** teams remain available for
existing Helpdesk workflows. They are not automatically authorized for any
CBSUA office.

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
The CBSUA office is stored separately on the ticket, and server-side validation
checks that the selected team is mapped to that office. This preserves native
Helpdesk team assignment and membership behavior while adding an office scope.

Only members of the assigned team may resolve that team's office tickets;
System Manager and Administrator retain the documented administrative
override. Configure team membership before enabling the teams for live service.
