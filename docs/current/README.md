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

Before working on the portal or guest submission, read [Current Architecture and Repository Boundaries](architecture.md) and the [Agent Handoff](HANDOFF.md). The handoff is the task-level execution guide; the architecture document records the multi-repository dependency model and Studio portal implementation.

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

**Goal:** Add an optional login-less ticket submission path to the existing guest-facing `/help` portal. A visitor can choose the existing authenticated path or submit a request without creating an account. The anonymous path collects an email address and an optional name; agent replies and selected status-change notices are delivered by email. It does not provide anonymous portal ticket browsing. Anonymous users do not receive a `/help/my-tickets` listing or general ticket-browsing capability.

### Proposed guest-entry experience (revised 2026-11-19)

The initial idea of placing an anonymous-submission button at the top of the public knowledge-base page is superseded. Pilot testing showed that Guests can be redirected to login before the Studio page is reached when the knowledge base is private, and that the homepage action layout exposes authenticated actions in the wrong session state.

The implemented source-level flow is (runtime verification still pending):

1. A Guest who opens `/help` while the knowledge base is private is sent to the shared Frappe `/login` page, as required by the existing private-KB policy.
2. The generic CBSUA login page displays **Welcome back to CBSUA Helpdesk**, the CBSUA logo/favicon, and the clickable **Submit a ticket without logging in** text link beneath the primary authentication actions.
3. The link is available whether the visitor arrived from `/help`, another CBSUA page, or directly at `/login`; it always navigates to the fixed local route `/help/guest/new`.
4. The guest page uses the existing verified-email submission flow described below.
5. When the knowledge base is public, Guests may browse it, but they must not see authenticated-only `Raise a ticket` or `View my tickets` actions. The anonymous entry link is not duplicated as a prominent top-of-homepage button.
6. Authenticated visitors retain the existing authenticated ticket creation and ticket-list actions. The authenticated `/help/tickets/new` and `/help/my-tickets` routes remain protected.

The login CTA is a navigation affordance only. It does not authorize ticket creation or change the private-KB policy. The CTA is intentionally global to the CBSUA deployment's shared login page; confirm that the deployment is not serving independently branded tenants before rollout.

The guest route is registered in `shared/src/portalRoutes.ts` and the Studio page is configured with `allow_guest: 1`. Both redirect guards now exempt only `/help/guest/new` (allowing a trailing slash); all other private-KB Guest routes remain subject to login. This is source-implemented but not yet browser-validated.

### Guest submission behavior

- `/help/guest/new`: guest-accessible Studio page with a dedicated submission component.
- Submission: optional name, email, office, request type, subject and plain-text description; attachments are excluded.
- Verification: sends a 30-minute single-use email link; ticket creation occurs only after successful verification.
- Confirmation: displays the native ticket reference and explains that requester-facing agent replies are emailed.
- No anonymous ticket-list, ticket-detail, update, or lookup endpoint is added.

### Verification email and confirmation behavior (source update 2026-11-23)

The verification email uses dedicated Frappe/Jinja templates at `helpdesk/templates/emails/guest_ticket_verification.html` and `.txt`, selected through Frappe's supported `frappe.sendmail(template=..., args=...)` interface. It carries CBSUA Helpdesk branding, the request subject/office/type summary, an explicit confirmation action, and the 30-minute expiry explanation. The request description is deliberately omitted from email. Dynamic HTML values are escaped.

The verification URL is built from Frappe's configured site URL with request-host overrides disabled, and its token query parameter is URL-encoded. This avoids accepting an arbitrary incoming Host header as the destination host. The configured site hostname must still be the public gateway hostname (including the correct scheme/port where required); this cannot be confirmed from source alone.

Opening the link remains read-only. The portal asks the visitor to press **Confirm email and submit request**. The verification API now distinguishes:
- `invalid_or_expired`: malformed, expired, or already-consumed token without an existing ticket;
- `processing`: another confirmation currently owns the verification lock;
- `temporarily_unavailable`: cache/lock service failure, with safe server-side diagnostics;
- success: returns the original ticket reference on an idempotent retry.

The UI no longer labels every failure as an expired link. It offers retry on temporary/processing failures and a fresh-request path only for invalid/expired links. Database insertion exceptions remain exceptions so Frappe can roll back; they are not converted into a success-shaped response. These changes are source-level only until the targeted Frappe tests and pilot gateway email round-trip are run.

The backend feature and revised entry/navigation source changes are implemented in this branch. The KB homepage top CTA has been removed, and its empty-state ticket actions are gated by `canCreateTicket`. The behavior is not yet runtime-validated.

### Architectural direction

Prefer creating a native Helpdesk ticket through a narrowly scoped server-side service rather than introducing a parallel guest-ticket DocType or creating disposable Frappe User accounts.

Before adding fields or DocTypes, inspect the actual Helpdesk requester model and lifecycle. Reuse existing fields and native notification/communication paths where safe. Keep any custom requester metadata minimal and justified by a concrete gap.

Email verification before ticket creation is the implemented safeguard because an email address alone does not prove control of that mailbox. The implementation uses a cryptographically random, single-use, expiring token; stores only its SHA-256 digest as the cache key; binds it to the pending submission; and makes successful ticket creation idempotent against replay or concurrent requests.

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
| 1. Anonymous submission MVP | Guest entry/navigation, form, email verification, and native ticket creation. | Guest can reach the form from the login screen even with a private KB; one verified submission creates one native ticket; authenticated flow is unchanged. | **In progress — backend, guest page, route exceptions, login CTA, and KB action cleanup are implemented in source; runtime validation remains** |
| 2. Email communications | Verification and acknowledgement email; public agent replies use native `raised_by` recipient; evaluate requester-visible status updates and inbound email replies. | Real outbound delivery and template privacy are tested; inbound sender identity policy is explicit. | **In progress — branded verification template and differentiated verification responses implemented in source; outbound delivery/runtime validation and inbound trust audit remain** |
| 3. Security and operational readiness | Rate limiting, replay/idempotency protection, expiry/cleanup, duplicate handling, attachment policy, auditability, accessibility, monitoring, and regression tests. | Security and acceptance tests pass; deployment and support requirements are documented. | **In progress — IP rate limits, expiring tokens, idempotent verification, no-attachment policy, and Guest read isolation implemented; bench/security validation pending** |
| 4. Account association | Match eligible verified anonymous requester identities to newly registered accounts after ownership verification. | Explicit migration rules, audit trail, history preservation, and tests are accepted. | **Deferred — future enhancement** |
| 5. Upstream integration and documentation reconciliation | Review the completed feature against upstream extension points; propose or port generic changes upstream where appropriate; reconcile documentation. | Upstream integration path is agreed; durable docs live in the correct upstream/CBSUA locations; this handoff folder is retired or reduced to a historical pointer. | **Deferred — after feature completion** |

## Phase 0 audit checklist

Initial inspection has confirmed the framework/UI dependency roles, the Studio-based customer portal, the existing authenticated ticket form/API assumptions, and the current `frappe-ui` submodule URL discrepancy. See [Current Architecture and Repository Boundaries](architecture.md). The following checklist tracks the remaining verification; do not begin implementation until the required design decisions are resolved:

- [x] Locate the existing `/help` route: it is the Helpdesk Studio App rendered by Frappe Studio, not a standalone SPA or generic Web Form.
- [x] Identify the authenticated submission flow: Studio `new_ticket` page and `NewTicketForm.vue`; retain its conventions without exposing its authenticated API.
- [x] Inspect the `HD Ticket` requester field and controller lifecycle. The current implementation resolves Contact collisions with a narrowly scoped `extend_doctype_class` mixin that skips Contact/Customer association only for verified guest submissions; end-to-end collision tests remain pending.
- [x] Trace requester email, Contact/customer association, and ticket permission behavior at controller level; end-to-end account/email identity behavior still requires tests.
- [ ] Complete outbound email audit: acknowledgement is skipped for portal-origin tickets; agent replies can email `raised_by`; realtime customer notifications resolve Frappe Users and do not notify email-only requesters. Verify every template and event.
- [ ] Complete inbound email trust audit: Message-ID/References thread stitching exists, but sender-address ownership validation has not been established.
- [x] Confirm the supported Frappe v17 `extend_doctype_class` mechanism and register a narrow HD Ticket mixin.
- [x] Define the guest API contract, allowlisted fields, POST methods, IP-based rate limits, expiring cache payload, and idempotent verification key.
- [x] Add a guest Studio page and route without changing the authenticated new-ticket page.
- [x] Implement the Helpdesk-origin login CTA and exact private-KB route exception in Helpdesk and Frappe source (see [Agent Handoff](HANDOFF.md)); browser validation remains outstanding.
- [x] Remove the obsolete top-of-homepage guest CTA and hide authenticated-only empty-state actions from Guests; browser validation remains outstanding.
- [ ] Test token expiry/replay, concurrent verification, Contact collision isolation, notification privacy, and authenticated regression on a disposable site.
- [ ] Complete outbound/inbound email and deployment source-lock audits.
- [x] Record implementation files and ownership boundary in [the anonymous-ticket feature guide](../features/anonymous-ticket-submission.md).

## Acceptance criteria

The feature is ready for integration review only when:

- A logged-out visitor can reach the guest submission path from the Helpdesk-origin login page, including when the knowledge base is private.
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

The backend creates native tickets only after email verification. It deliberately avoids Contact/HD Customer auto-association, does not accept attachments, and does not grant Guest DocType permissions. A guest-specific acknowledgement without a ticket-detail link is sent when enabled; public agent replies default to `raised_by` but omit the inaccessible portal link, and a guest-specific hook sends status-only emails on ticket status changes. Inbound email sender verification and all outbound templates still need a deeper audit.

**Validation status:** source files and framework extension-hook implementation were inspected through GitHub. No disposable Frappe site, email account, frontend build, Semgrep run, or integration test runner was available in this session. Do not treat the feature as release-ready until those checks pass.

## Implementation handoff update — 2026-11-19

The anonymous verification path now keeps its site-scoped Redis lock until the Frappe database transaction commits or rolls back. Releasing the lock when the whitelisted method returned was too early because Frappe commits after the method response is prepared; concurrent requests could otherwise race an uncommitted ticket insert. The deterministic ticket key and the newly declared unique constraint on HD Ticket.key remain the durable idempotency backstop. A representative-site migration must confirm existing key values are unique and the database index is created successfully.

A focused test module was added at helpdesk/tests/test_anonymous_tickets.py for token digest/key behavior, unique-key metadata, Guest read isolation, input normalization, office/request-type consistency, malformed tokens/values, and content limits. These tests have **not** been run in this session because no Frappe bench/site runtime is connected. End-to-end tests for verification replay, expiry, concurrent requests, Contact collisions, notification privacy, and authenticated regressions remain required.

The implementation also received a source-level correction to preserve actual newline characters in the escaped plain-text ticket description. No inbound email reply support is claimed. The current feature remains in progress and is not release-ready pending bench, email, Studio build, and Semgrep validation.


## Handoff update — guest-entry redesign — 2026-11-19

### Decision

The guest entry point is moving from the public knowledge-base homepage to the Frappe login screen. This is a correction based on pilot behavior, not a change to the verified-ticket backend.

The current implementation's Studio page has `allow_guest: 1`, but the private-knowledge-base policy has an earlier global redirect. The framework boot value `send_guest_to_login` is set for Guests when `HD Settings.public_knowledge_base` is false, and the Studio session store's `sendGuestToLogin()` calls `signIn()` for Guests whenever the KB is private. Consequently, the route-level guest setting cannot by itself make `/help/guest/new` reachable. The user-visible pilot behavior confirms that direct navigation is currently redirected.

### Required next implementation slice

1. **Helpdesk route exception** — in `helpdesk/helpdesk/hooks/studio_app.py`, ensure the Guest redirect is not requested when the current path is exactly `/help/guest/new` (normalize a trailing slash if the router can produce one). Keep private-KB behavior for every other guest portal route.
2. **Studio session guard exception** — in `studio/helpdesk/stores/session.ts`, make `sendGuestToLogin()` return without signing in only for the guest submission route. Do not weaken `isGuest`, `canCreateTicket`, or authenticated route guards globally.
3. **Login-page CTA** — inspect the actual Frappe login request/context and implement a Helpdesk-origin marker that survives the redirect to login. In `cbsua-app-frappe/frappe/www/login.html`, add a secondary link below `Continue` and `Login with Email Link` only when that marker proves the login originated from Helpdesk. Link to the absolute `/help/guest/new` path. Do not show this CBSUA-specific CTA on unrelated Frappe login pages. Confirm the marker cannot be forged into a broad permission bypass; the CTA is navigation only.
4. **Homepage actions** — in `studio/helpdesk/studio_page/public_kb/public_kb.json` and its setup/composable, remove the prominent top-level anonymous button. Ensure the empty-state `Raise a ticket` and `View my tickets` actions are hidden for Guests. Preserve the normal authenticated actions and the header's existing `canCreateTicket` behavior.
5. **Documentation and validation** — update the feature guide after the implementation is actually present. Test private-KB Guest access to `/help/guest/new`, private-KB Guest denial/redirect for `/help`, `/help/my-tickets`, and `/help/tickets/new`, public-KB Guest browsing without authenticated actions, and authenticated homepage/ticket flows.

### Repository ownership

- **`AgeReapor/cbsua-app-helpdesk`**: owns the Studio guest page, route/session behavior, private-KB exception, homepage action visibility, backend guest API, ticket mixin and tests.
- **`AgeReapor/cbsua-app-frappe`**: owns the shared Frappe login template/context change only if the CTA cannot be implemented cleanly through an existing Helpdesk-specific integration point. The CBSUA login template is intentionally branded for this deployment and shows the guest ticket link on every login entry. Confirm that this deployment is not intended for unrelated independently branded tenants.
- **`AgeReapor/cbsua-app-frappe-ui`**: no change is currently indicated; do not modify the UI library for route policy or login-template concerns.
- **`AgeReapor/cbsua-app-helpdesk-deployment`**: owns source-lock/build-ref and pilot release integration. Do not change deployment refs as part of this UI task without an explicit release decision.

### Files to inspect first

- Helpdesk: `helpdesk/helpdesk/hooks/studio_app.py`
- Helpdesk: `studio/helpdesk/stores/session.ts`
- Helpdesk: `studio/helpdesk/studio_page/public_kb/public_kb.json`
- Helpdesk: `studio/helpdesk/studio_page/public_kb/public_kb.ts` and `studio/helpdesk/composables/useKnowledgeBaseHeader.ts`
- Helpdesk: `studio/helpdesk/studio_page/guest_new_ticket/guest_new_ticket.json`
- Helpdesk: `shared/src/portalRoutes.ts`
- Framework: `frappe/www/login.html`
- Feature details: [Anonymous ticket submission](../features/anonymous-ticket-submission.md)
- Architecture/dependency context: [Current Architecture and Repository Boundaries](architecture.md)

### Validation state and cautions

No changes to the login template, guest redirect, homepage actions, or route guards have been made as part of this handoff update. The guest-entry redesign is **planned**, not implemented. Do not describe the pilot as fixed until the actual login-origin CTA and both redirect exceptions have been tested.

The previously documented backend status remains unchanged: focused source-level tests exist but have not been run in a Frappe bench; end-to-end verification/replay/expiry/concurrency, Contact-collision, outbound email privacy/delivery, authenticated regression, Studio build, Semgrep, and migration/index checks remain release gates. Anonymous inbound email replies are not supported or claimed.

### Implemented shared CBSUA login-page UX

The shared CBSUA login-page redesign is now implemented in source documented in [Current Architecture](architecture.md) and [Agent Handoff](HANDOFF.md): show **Submit a ticket without logging in** directly below **Continue** and **Login with Email Link** on `/login`, replace the welcome heading with **Welcome back to CBSUA Helpdesk**, and use the existing CBSUA logo/favicon assets. This supersedes the earlier Helpdesk-origin-only visibility rule for the CTA. Coordinate the template/context work in `cbsua-app-frappe` with the canonical brand assets in this repository. Keep the guest route and ticket authorization boundaries unchanged.

**Suggested next task for the receiving agent:** validate the implemented login-page UX in a compatible Frappe v17 bench, including the login variants, static asset delivery, guest-route access matrix, and authenticated redirects. Do not change deployment source locks in this task; runtime validation remains required.


### Guest submission HTTP 500 correction — 2026-11-23

Pilot reported an Internal Server Error when submitting the guest form. Source inspection traced a concrete compatibility error: the feature passed `text_content=` directly to `frappe.sendmail`, but the project's Frappe v17 implementation does not expose that keyword. Its supported multipart-template interface is `template="guest_ticket_verification"` with `args=email_context`; Frappe internally loads both the HTML and optional `.txt` templates. The backend now uses that interface and no longer passes the unsupported argument. A regression-focused helper test was updated to validate the template context. This is a source fix; the Pilot request still needs to be retried after deploying/restarting with this branch, and the exact runtime traceback should be checked if the 500 persists.

## Email OTP verification — implementation update (2026-11-23)

**Status: source implementation committed; Pilot/runtime validation pending.** This supersedes the earlier email-link verification flow described above. The localhost/gateway redirect dependency has been removed: the guest stays on `/help/guest/new`, receives a six-digit code by email, and enters it in the same Studio form. The API returns an opaque challenge ID; it does not return the OTP. The challenge and pending allowlisted request are stored in the site cache. Only an HMAC-SHA256 digest of the code (bound to the challenge ID and using the site's Frappe encryption key) is stored. The code expires after 10 minutes, permits five failed attempts, and supports up to three resends with a 60-second cooldown. Resending rotates the digest, invalidating the previous code. Verification creates one native HD Ticket using a deterministic key derived from the challenge ID; the distributed lock is retained through transaction commit/rollback and the challenge is deleted after commit. Guest ticket permissions and authenticated ticket flows remain unchanged.

The verification email templates now contain the OTP and minimal request summary; they contain no verification URL. API methods are `start_guest_submission`, `verify_guest_submission(challenge_id, otp)`, and `resend_guest_submission_otp(challenge_id)`. The feature is not runtime validated: execute the focused Frappe tests, Studio production build, security scan, and Pilot email-to-ticket acceptance tests before release. See `docs/features/anonymous-ticket-submission.md` and the latest handoff section for implementation details.
