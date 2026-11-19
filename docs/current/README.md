# Current Project Context

> **Purpose:** This folder is the maintained handoff and integration context for the active CBSUA Helpdesk project. Read this document before starting implementation or making architectural changes.

## Why `docs/current/` exists

This project is being developed by multiple contributors and may be handed between developers, maintainers, and agentic coding systems. Important decisions have previously been distributed across chat conversations, README files, issue discussions, implementation notes, and Mermaid diagrams. That information is useful only when the next contributor can find it, understand which decisions remain current, and distinguish implemented behavior from proposed work.

The `current/` folder consolidates that working context into a predictable entry point. Its purpose is to reduce onboarding time, prevent repeated rediscovery, preserve architectural reasoning, and make integration work safer. It is intentionally a **living project handoff area**, not a replacement for durable feature, architecture, API, operations, or user documentation.

The root `docs/README.md` should link here prominently. Contributors should update the relevant current-context documents and roadmap as implementation decisions change. Record why a decision was made, not only what was chosen.

## Documentation lifecycle and eventual upstream integration

This repository currently carries CBSUA-specific Helpdesk work while the project moves toward an extension-oriented relationship with upstream Frappe Helpdesk.

The immediate priority is to complete and validate the anonymous-ticket capability as a coherent feature in this repository. During that work, keep a clear record of:

- which behavior is generic Helpdesk functionality;
- which behavior is CBSUA-specific policy or integration;
- which changes are unavoidable integration points in upstream-owned code;
- which changes can live in a separate CBSUA extension app;
- tests, migrations, compatibility constraints, and deployment requirements.

Once the feature/submodule is complete and the extension boundary is understood, the project can evaluate merging or porting the application changes into the original upstream Helpdesk repository (subject to maintainer review and upstream acceptance). At that integration milestone, the relevant durable documentation should be reconciled with and moved into the original project's documentation structure. The temporary handoff context should not be copied blindly: resolve duplicates, preserve useful architectural history, and retain CBSUA-specific deployment or policy documentation in the appropriate CBSUA repository.

This is a planned documentation and integration lifecycle, **not a claim that upstream has accepted or merged any changes**. Until that milestone is reached, this folder remains the handoff source for the current work in this repository.

## How contributors should use this folder

1. Start here before editing code.
2. Read the implementation roadmap and the relevant architecture/feature notes before choosing an implementation.
3. Check the repository's actual code and tests; documentation is context, not proof that a feature exists.
4. Keep status explicit: **implemented**, **in progress**, **planned**, **deferred**, or **blocked**.
5. Update the roadmap when scope, dependencies, decisions, or acceptance criteria change.
6. When a decision changes, update the relevant document and explain the reason; do not leave contradictory guidance in multiple files.
7. Link to durable documents elsewhere in `docs/` rather than duplicating their full contents here.
8. Before handing work off, record the current branch, commit/PR state, changed areas, validation performed, known gaps, and the next actionable task.

## Architecture orientation

Before working on the portal or guest submission, read [Current Architecture and Repository Boundaries](architecture.md). It records the actual multi-repository dependency model and the Studio portal implementation.

In particular:

- `cbsua-app-frappe` supplies the Frappe Framework runtime, including the Studio app/runtime.
- `cbsua-app-frappe-ui` supplies the Vue UI library used by the Helpdesk frontend and is intended to be consumed as a submodule/source dependency; verify the actual submodule URL and gitlink SHA.
- `cbsua-app-helpdesk` contains the Helpdesk backend, agent Desk frontend, and exported Studio customer portal source.
- The customer portal at `/help` is the Helpdesk Studio App, not a separate standalone Vue SPA/router or a generic Frappe Web Form.
- The guest ticket feature must add a guest-accessible Studio page and a dedicated backend service while leaving the existing authenticated Studio ticket page and API assumptions intact.

## Current project direction

The current architectural direction is to reduce long-term divergence from upstream Frappe Helpdesk and favor extension/configuration over maintaining a branded fork.

Guiding principles:

- Preserve native Helpdesk ticket lifecycle, agent workspace, portal behavior, assignment, SLA, and communication features wherever practical.
- Prefer upstream extension points and documented APIs over copying whole upstream components, monkey-patching, or maintaining parallel implementations.
- Keep institutional branding, boot data, defaults, office routing, and CBSUA-specific policy explicit and isolated where feasible.
- Do not move code into a separate extension merely for theoretical purity; first verify that the required extension points exist and that the result remains maintainable.
- Treat permissions, requester identity, and internal-versus-public communications as security boundaries.
- Keep deployment and release orchestration in the deployment repository.

## Active workstream: anonymous ticket submission

**Branch:** `feat/anonymous-tickets`

**Goal:** Add an optional login-less ticket submission path to the existing guest-facing `/help` portal. A visitor can choose the existing authenticated path or submit a request without creating an account. The anonymous path collects an email address and an optional name; subsequent requester-facing updates are delivered by email. Anonymous users do not receive a `/help/my-tickets` listing or general ticket-browsing capability.

### Proposed experience

- `/help`: retains the public knowledge base and now links to the guest submission path.
- `/help/guest/new`: published guest-accessible Studio page with a dedicated submission component.
- Submission: collects an optional name, email, office, request type, subject and plain-text description; attachments are excluded.
- Verification: sends a 30-minute single-use email link; ticket creation occurs only after successful verification.
- Confirmation: displays the native ticket reference and explains that requester-facing agent replies are emailed.
- No anonymous ticket-list or ticket-detail endpoint is added.

The route is registered in `shared/src/portalRoutes.ts` and exported as a standard Studio Page. Verify its published build on a migrated test site.

### Architectural direction

Prefer creating a native Helpdesk ticket through a narrowly scoped server-side service rather than introducing a parallel guest-ticket DocType or creating disposable Frappe User accounts.

Before adding fields or DocTypes, inspect the actual Helpdesk requester model and lifecycle. Reuse existing fields and native notification/communication paths where safe. Keep any custom requester metadata minimal and justified by a concrete gap.

Email verification before ticket creation is the recommended safeguard because an email address alone does not prove control of that mailbox. Verification should use a cryptographically random, single-use, expiring token; store only a protected representation; bind it to the intended email and submission; and make successful ticket creation idempotent against replay or concurrent requests.

Guest endpoints must accept only explicitly allowed fields, validate input server-side, set privileged fields on the server, and never grant broad Guest Create or Read permissions on Helpdesk tickets. No public endpoint should reveal ticket details, internal comments, private attachments, agent-only data, or ticket existence.

Native email notifications should expose only requester-visible information. Inbound email replies may be considered only after the existing Helpdesk inbound-mail association and trust model has been inspected.

### Institutional rationale

Anonymous submission is an accessibility path for campus service reporting. Students, employees, faculty, and campus visitors may need to report a service issue even when they cannot authenticate or do not have an account. Requiring login for every request can prevent reporting, especially when the reported problem is itself an account or access issue.

The campus-network deployment context helps define the intended service audience, but it is not a substitute for security controls. A campus network can contain compromised or shared devices and can be exposed through misconfiguration. The feature still requires abuse controls, rate limits, input validation, attachment restrictions, privacy safeguards, and monitoring.

Suggested policy statement:

> Anonymous ticket submission is an accessibility feature of the CBSUA campus service-desk system. It allows members of the university community and campus visitors to report service disruptions without requiring an existing Helpdesk account. Requester email ownership is verified, while ticket management and internal processing remain governed by the existing Helpdesk authorization model.

### Future account association

A later enhancement may associate eligible anonymous tickets with a newly registered account when the account owner proves control of the same verified email address. This is not part of the initial submission MVP. Email equality alone must not trigger an unsafe ownership transfer. Preserve original requester metadata and communication history, define eligibility rules, and record the association for audit purposes.

## Implementation roadmap

This roadmap is the working status tracker for the anonymous-ticket workstream. Update it as work is completed; do not mark a phase complete based only on code existing.

| Phase | Scope | Exit condition | Status |
|---|---|---|---|
| 0. Repository and extension-point audit | Inspect portal routes/components, HD Ticket fields/controller, ticket creation, outbound notifications, inbound email, hooks, tests, and upstream extension points. | Confirmed native ticket model, supported `extend_doctype_class` hook on the CBSUA Frappe v17 source, API boundary, and remaining email trust gaps. | **In progress — outbound/inbound email and deployment source-lock audits remain** |
| 1. Anonymous submission MVP | Add guest choice and form; validate email/name/request details; verify mailbox ownership; create a native ticket through server-side code. | Verified guest can create exactly one native ticket; unverified/invalid requests cannot; authenticated flow is unchanged. | **In progress — backend, Studio page, and initial tests committed; bench validation pending** |
| 2. Email communications | Verification and acknowledgement email; public agent replies use native `raised_by` recipient; evaluate requester-visible status updates and inbound email replies. | Real outbound delivery and template privacy are tested; inbound sender identity policy is explicit. | **In progress — verification, acknowledgement, agent-reply delivery, and status-change notices implemented; inbound trust remains unverified** |
| 3. Security and operational readiness | Rate limiting, replay/idempotency protection, expiry/cleanup, duplicate handling, attachment policy, auditability, accessibility, monitoring, and regression tests. | Security and acceptance tests pass; deployment and support requirements are documented. | **In progress — IP rate limits, expiring tokens, idempotent verification, no-attachment policy, and Guest read isolation implemented; bench/security validation pending** |
| 4. Account association | Match eligible verified anonymous requester identities to newly registered accounts after ownership verification. | Explicit migration rules, audit trail, history preservation, and tests are accepted. | **Deferred — future enhancement** |
| 5. Upstream integration and documentation reconciliation | Review the completed feature against upstream extension points; propose or port generic changes upstream where appropriate; reconcile documentation. | Upstream integration path is agreed; durable docs live in the correct upstream/CBSUA locations; this handoff folder is retired or reduced to a historical pointer. | **Deferred — after feature completion** |

## Phase 0 audit checklist

Initial inspection has confirmed the framework/UI dependency roles, the Studio-based customer portal, the existing authenticated ticket form/API assumptions, and the current `frappe-ui` submodule URL discrepancy. See [Current Architecture and Repository Boundaries](architecture.md). The following checklist tracks the remaining verification; do not begin implementation until the required design decisions are resolved:

- [x] Locate the existing `/help` route: it is the Helpdesk Studio App rendered by Frappe Studio, not a standalone SPA or generic Web Form.
- [x] Identify the authenticated submission flow: Studio `new_ticket` page and `NewTicketForm.vue`; retain its conventions without exposing its authenticated API.
- [x] Inspect the `HD Ticket` requester field and initial controller lifecycle. **Open blocker:** Contact auto-association can reject or incorrectly associate anonymous submissions; see architecture.md.
- [x] Trace requester email, Contact/customer association, and ticket permission behavior at controller level; end-to-end account/email identity behavior still requires tests.
- [ ] Complete outbound email audit: acknowledgement is skipped for portal-origin tickets; agent replies can email `raised_by`; realtime customer notifications resolve Frappe Users and do not notify email-only requesters. Verify every template and event.
- [ ] Complete inbound email trust audit: Message-ID/References thread stitching exists, but sender-address ownership validation has not been established.
- [x] Confirm the supported Frappe v17 `extend_doctype_class` mechanism and register a narrow HD Ticket mixin.
- [x] Define the guest API contract, allowlisted fields, POST methods, IP-based rate limits, expiring cache payload, and idempotent verification key.
- [x] Add a guest Studio page, route, and public home-page entry point without changing the authenticated new-ticket page.
- [ ] Test token expiry/replay, concurrent verification, Contact collision isolation, notification privacy, and authenticated regression on a disposable site.
- [ ] Complete outbound/inbound email and deployment source-lock audits.
- [x] Record implementation files and ownership boundary in [the anonymous-ticket feature guide](../features/anonymous-ticket-submission.md).

## Acceptance criteria

The feature is ready for integration review only when:

- A logged-out visitor can reach the guest submission path from `/help`.
- Email is required and name remains optional.
- Email ownership is verified before ticket creation.
- A successful verification creates one native Helpdesk ticket, not a parallel record or temporary user.
- Guest users cannot list, read, modify, or infer other tickets through public endpoints.
- Client-supplied privileged fields cannot control assignment, team, priority, status, or internal visibility.
- Requester emails contain only requester-visible content.
- Existing authenticated submission and `/help/my-tickets` behavior remain intact.
- Rate limiting, replay protection, cleanup, error handling, and operational behavior are tested.
- Documentation and deployment implications are reviewed.

## Handoff note template

At each meaningful handoff, append or update a concise status note with:

- **Date / contributor:**
- **Branch and latest commit:**
- **Current phase:**
- **Completed:**
- **Files/modules changed:**
- **Tests and checks run (exact commands and results):**
- **Known issues / risks:**
- **Decisions made or changed (with rationale):**
- **Next concrete task:**
- **Upstream integration implications:**

Do not use this document as a substitute for commit history, PR review, or test evidence. It is the navigational context that helps the next contributor find and interpret those artifacts.

## Related repositories and references

- [CBSUA Helpdesk repository](https://github.com/AgeReapor/cbsua-app-helpdesk)
- [Frappe Helpdesk upstream](https://github.com/frappe/helpdesk)
- [Frappe official skills](https://github.com/frappe/skills)
- [LUBUS Frappe skills](https://github.com/lubusIN/frappe-skills)
- [CBSUA Helpdesk deployment](https://github.com/AgeReapor/cbsua-app-helpdesk-deployment)

For Frappe work, consult the applicable installed/repository skills before implementation, especially app development, code review, API development, web forms, and enterprise patterns. Verify skill instructions against the actual target Frappe/Helpdesk versions and repository conventions.


## Implementation handoff — 2026-11-19

The first implementation slice is committed on `feat/anonymous-tickets`. It adds `helpdesk/anonymous_tickets.py`, `helpdesk/extends/anonymous_ticket.py`, the `extend_doctype_class` hook, a guest-only Studio page/component, the `/guest/new` route, a public-home entry point, initial backend tests, and the feature guide. The authenticated `api.new` endpoint and existing authenticated Studio page remain unchanged.

The backend creates native tickets only after email verification. It deliberately avoids Contact/HD Customer auto-association, does not accept attachments, and does not grant Guest DocType permissions. The existing Helpdesk acknowledgement is invoked after creation when enabled; public agent replies default to `raised_by`, and a guest-specific hook sends status-only emails on ticket status changes. Inbound email sender verification and all outbound templates still need a deeper audit.

**Validation status:** source files and framework extension-hook implementation were inspected through GitHub. No disposable Frappe site, email account, frontend build, Semgrep run, or integration test runner was available in this session. Do not treat the feature as release-ready until those checks pass.

## Implementation handoff update — 2026-11-19

The anonymous verification path now keeps its site-scoped Redis lock until the Frappe database transaction commits or rolls back. Releasing the lock when the whitelisted method returned was too early because Frappe commits after the method response is prepared; concurrent requests could otherwise race an uncommitted ticket insert. The deterministic ticket key and the existing unique HD Ticket.key index remain the durable idempotency backstop.

A focused test module was added at helpdesk/tests/test_anonymous_tickets.py for token digest/key behavior, input normalization, office/request-type consistency, and invalid/oversized content. These tests have **not** been run in this session because no Frappe bench/site runtime is connected. End-to-end tests for verification replay, expiry, concurrent requests, Contact collisions, notification privacy, and authenticated regressions remain required.

The implementation also received a source-level correction to preserve actual newline characters in the escaped plain-text ticket description. No inbound email reply support is claimed. The current feature remains in progress and is not release-ready pending bench, email, Studio build, and Semgrep validation.
