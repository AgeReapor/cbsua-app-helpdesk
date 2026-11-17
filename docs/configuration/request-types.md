# Request Type Configuration

Each `CB Office Request Type` belongs to one `CB Office`. The ticket form
loads request types after the customer selects an office.

## Automatic team routing

Each request type has a **Default Team** Link to the existing Helpdesk
`HD Team` DocType. When a new ticket is submitted, the server reads the
selected request type's default team and sets the ticket's native
`HD Ticket.agent_group` field automatically.

The selected team must be mapped to the request type's office through the
team's **Assigned Offices** table. Invalid cross-office mappings are rejected
server-side. A valid team explicitly selected by an agent is retained; the
default team is used when the ticket has no team yet.

## Initial mappings

| Office | Request type | Default team |
|---|---|---|
| ICT Office | Tech Support | ICT Support Team |
| ICT Office | Inquiry | ICT Support Team |
| Registrar's Office | Inquiry | Registrar Support Team |
| Admissions Office | Inquiry | Admissions Support Team |
| Cashier's Office | Inquiry | Cashier Support Team |

These defaults are inserted only when no team is configured already. They can
be changed by an administrator on the corresponding **CB Office Request Type**
record. Adding a new request type does not silently invent a team: configure
its Default Team explicitly.

Team routing chooses the responsible team. The existing Helpdesk assignment
rule then distributes the ticket to an eligible member of that team according
to its configured rotation. Add agents to each team's **Users** table and
configure/enable its assignment rule before expecting individual agent
assignment.
