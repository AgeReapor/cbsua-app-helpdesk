# Office-aware Helpdesk Architecture

## Scope

CBSUA Helpdesk adds an office routing dimension to Frappe Helpdesk without replacing its existing ticket, team, assignment-rule, SLA, or customer models.

## Entities

- **HD Office**: independently enabled service office, with a unique office code and one configurable default office.
- **HD Office Request Type**: request classification owned by exactly one office. A request type code is globally unique so labels such as `Inquiry` can exist independently for each office.
- **HD Team**: existing Frappe Helpdesk team, extended with an `offices` Table MultiSelect relationship.
- **HD Ticket**: existing ticket, extended with `office` and `request_type` links.

A team can serve multiple offices. A ticket's selected team must explicitly list the ticket's office. Team membership continues to use the existing HD Team Member child table.

## Baseline records

| Office | Initial request types |
|---|---|
| ICT Office | Tech Support, Inquiry |
| Registrar's Office | Inquiry |
| Admissions Office | Inquiry |
| Cashier's Office | Inquiry |

ICT is the default office on a fresh install. No team membership or office assignment is guessed by the installer; administrators explicitly associate existing teams with offices.

## Ticket lifecycle

The office and request type are persisted on HD Ticket. The customer form should select Office first, then call `helpdesk.setup.office_routing.get_office_request_types` to populate the request-type select. Server validation is authoritative and rejects mismatched or disabled request types.

Team selection is constrained by the office in the UI, but the same relationship is checked server-side on every ticket save. Resolution is permitted only when a team is assigned and the acting user belongs to that team; Administrator and System Manager retain administrative override.

## Legacy tickets

Existing tickets without office metadata are not bulk-assigned to ICT because that would fabricate routing history. They remain accessible under existing Helpdesk permissions. New tickets must specify an enabled office and request type.

## Operational configuration

1. Create or enable an office.
2. Add office-specific request types.
3. Edit each HD Team and add its authorized offices.
4. Configure customer portal controls to use the office and request-type endpoint.

The installer seeds missing baseline rows only. Subsequent migrations preserve administrator edits and do not auto-assign teams.
