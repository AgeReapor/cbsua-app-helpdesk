# CBSUA Helpdesk Documentation

This directory contains the maintained product architecture, feature specifications, configuration guides, development notes, testing procedures, and UI documentation for the CBSUA Helpdesk application. Temporary agent handoff notes are not maintained here; the durable feature and architecture documents are the source of truth.

## Architecture

- [CBSUA Office-Aware Helpdesk Architecture](architecture/office-aware-helpdesk.md)

## Features

- [Anonymous ticket submission](features/anonymous-ticket-submission.md)

## Configuration

- [Office administration](configuration/offices.md)
- [Office request types](configuration/request-types.md)
- [Team-to-office assignments](configuration/teams.md)

## Development

- [Office routing boot and migration refactor](development/boot-refactor.md)

## Testing

- [MVP 1 office-routing acceptance tests](testing/mvp1-acceptance-tests.md)

## UI

- [CBSUA branding](ui/cbsua-branding.md)
- [CBSUA UI styling](ui/cbsua-ui-styling.md)

## In Desk

Open the **Helpdesk** workspace. The **CBSUA Office Routing** card links to the `CB Office` and `CB Office Request Type` lists. Teams remain under **Agent Configuration → Team**. Open **Ticket Configuration → General Settings → CBSUA Routing** to configure office routing and the default office.
