# Office Administration

## Where to manage offices

In Desk, open **Helpdesk → CBSUA Office Routing → Offices**. This opens the `CB Office` list where an administrator can create, edit, enable, disable, and choose the default office.

The baseline records are ICT Office, Registrar's Office, Admissions Office, and Cashier's Office. Each office has a unique office code. Disabling an office removes it from customer ticket creation without deleting historical tickets.

## Default office

Open **Helpdesk → Ticket Configuration → General Settings**, then the **CBSUA Routing** tab. Set **Default Office** to the office that should be preselected for new tickets. ICT Office is selected on a fresh install. The office record's Default Office flag mirrors this setting.

## Adding an office

1. Create a `CB Office` record with a unique name and code.
2. Add its request types under **CBSUA Office Routing → Office Request Types**.
3. Assign one or more existing Helpdesk teams to it using the team's Assigned Offices table.
4. Enable the office when it is ready for customer submissions.

Do not delete an office that has historical tickets; disable it instead.
