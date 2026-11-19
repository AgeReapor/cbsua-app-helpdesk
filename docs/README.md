# CBSUA Helpdesk Documentation

## Current project handoff

Start with [Current Project Context](current/README.md) before implementation or handoff. This living entry point consolidates the active project direction, anonymous-ticket workstream, implementation roadmap, acceptance criteria, and contributor handoff process. Update it as decisions and implementation status change. It also documents the intended documentation lifecycle: reconcile durable documentation with upstream Frappe Helpdesk after the feature/submodule is complete and the integration boundary is agreed.

## Office routing administration

- [Architecture and entity relationships](architecture/office-aware-helpdesk.md)
- [Office administration](configuration/offices.md)
- [Office request types](configuration/request-types.md)
- [Team-to-office assignments](configuration/teams.md)
- [Boot and migration refactor](development/boot-refactor.md)
- [MVP 1 acceptance tests](testing/mvp1-acceptance-tests.md)

## In Desk

Open the **Helpdesk** workspace. The **CBSUA Office Routing** card links to the `CB Office` and `CB Office Request Type` lists. Teams remain under **Agent Configuration → Team**. Open **Ticket Configuration → General Settings → CBSUA Routing** to configure office routing and the default office.
