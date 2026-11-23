# CBSUA Helpdesk — Agent Handoff

> **Handoff date:** 2026-11-19  
> **Workstream:** Anonymous / guest ticket submission  
> **Primary repository:** [AgeReapor/cbsua-app-helpdesk](https://github.com/AgeReapor/cbsua-app-helpdesk)  
> **Working branch:** `feat/anonymous-tickets`  
> **Status:** Backend, guest Studio form, exact private-KB route exception, shared CBSUA login CTA/branding, and KB homepage cleanup are implemented in source across Helpdesk and Frappe feature branches. Runtime/browser/security/build validation remains outstanding. **Do not treat this feature as production-ready.**

This is the operational handoff for the next engineer or coding agent. Read it together with [Current Architecture](architecture.md), [Current Project Context](README.md), and the [Anonymous Ticket Submission feature guide](../features/anonymous-ticket-submission.md). The source code and deployment lock take precedence over this document whenever they disagree.

---

## 1. Mission and expected outcome

Complete an optional login-less ticket submission path in the existing CBSUA Helpdesk customer portal. A visitor who cannot or does not want to authenticate must be able to submit a service request after proving control of an email address. The resulting record must be a normal native `HD Ticket`, processed by the existing agent workspace and ticket lifecycle.

The feature is deliberately **not** an anonymous ticket-management portal. A Guest must not be able to list, read, search, update, or infer ticket records. Requester communication is email-based and limited to verified, requester-visible messages.

### User journey decision (current)

The original approach put a large `Submit a request without signing in` button at the top of the public knowledge-base homepage. Pilot feedback showed that this did not solve the private-knowledge-base case: Guests were redirected to login before reaching the Studio page. It also placed anonymous and authenticated actions awkwardly together.

The revised intended flow is:

1. Guest opens `/help`.
2. If the knowledge base is private, the existing policy sends the Guest to the Frappe login page.
3. The shared CBSUA `/login` page shows **Submit a ticket without logging in** as clickable text immediately below **Continue** and **Login with Email Link**.
4. The login page uses the generic CBSUA Helpdesk welcome heading and CBSUA logo/favicon, and is intended for both system users and customers/requesters.
5. The secondary link opens the fixed local route `/help/guest/new` directly.
6. The guest form submits the request and sends an email verification link. A ticket is not created merely by opening the email link; the visitor confirms on the page.
7. After successful verification, the visitor sees the native ticket reference and is told that requester-facing updates/replies are sent by email.

When the KB is public, Guests may browse it, but must not see authenticated-only **Raise a ticket** or **View my tickets** actions. Do not add a second prominent anonymous button to the KB homepage. Authenticated users keep their existing portal actions and routes.

The login CTA is a navigation affordance only. It must not act as an authorization control or weaken the portal's access policy. The shared-login CTA and branding implementation supersedes the earlier Helpdesk-origin-only CTA proposal.

---

## 2. Multi-repository architecture and ownership

The CBSUA deployment is a coordinated Frappe application stack, not a single repository. Understand the dependency roles before changing code:

| Repository | Responsibility | Relevance to this work |
|---|---|---|
| [cbsua-app-frappe](https://github.com/AgeReapor/cbsua-app-frappe) | CBSUA Frappe Framework fork and runtime | Shared CBSUA login template/context, login branding and guest-submission entry link |
| [cbsua-app-frappe-ui](https://github.com/AgeReapor/cbsua-app-frappe-ui) | Forked Frappe UI library consumed by Helpdesk frontend | No change currently indicated; do not put route policy or product-specific login behavior here |
| [cbsua-app-helpdesk](https://github.com/AgeReapor/cbsua-app-helpdesk) | Helpdesk backend, agent Desk UI, and Studio customer portal | Owns anonymous API, ticket integration, Guest route policy, Studio UI, tests, and feature documentation |
| [cbsua-app-helpdesk-deployment](https://github.com/AgeReapor/cbsua-app-helpdesk-deployment) | Combined image/build/source lock and release orchestration | Owns immutable source refs and pilot release integration; do not change refs as part of feature coding without a release decision |
| [cbsua-app-pilot](https://github.com/AgeReapor/cbsua-app-pilot) | Local Pilot-managed development/runtime tooling | Useful for creating and operating a compatible local bench; not the owner of Helpdesk feature code |

The customer portal at `/help` is the Helpdesk **Studio App**. It is not a separate standalone Vue SPA, generic Frappe Web Form, or independent frontend application. Studio page definitions are exported under `studio/helpdesk/studio_page/`; frontend source/components live under `studio/helpdesk/` and `shared/`.

### Dependency and compatibility discipline

- Helpdesk's `pyproject.toml` declares Frappe `>=17.0.0-dev,<18.0.0` and Telephony `>=0.0.1,<1.0.0`.
- The current source uses Frappe's `extend_doctype_class` hook for the HD Ticket mixin. The mechanism was confirmed in the CBSUA Frappe source previously inspected, but the exact framework SHA in the deployment source lock still needs to be checked before release.
- The Frappe login page is shared by the CBSUA deployment. The current product decision is to make it a generic CBSUA Helpdesk sign-in experience and show the guest-submission link on `/login` for both system users and customers. Confirm that the deployment is not serving independently branded tenants before applying CBSUA branding globally.
- The UI library fork is not an appropriate place for CBSUA Helpdesk access policy.
- Deployment documentation identifies `develop` as the canonical build branch. A feature branch is not automatically present in the pilot image. Verify the actual workflow and `config/source-lock.json`; use immutable SHAs for release reproducibility.

---

## 3. Current implementation inventory

The following describes source inspected on `feat/anonymous-tickets`. It does not imply that runtime tests have passed.

### Backend service

**`helpdesk/anonymous_tickets.py`**

Guest-whitelisted, POST-only methods:

| Method | Role |
|---|---|
| `get_guest_form_options` | Returns enabled offices and enabled request types for the guest form; no ticket data |
| `start_guest_submission` | Validates allowlisted request data, stores a pending payload, and emails a verification link |
| `verify_guest_submission` | Validates/consumes the email token and creates one native ticket |

Key properties in the current source:

- Required email; optional full name; subject, plain-text description, office, and office-specific request type.
- Email normalized to lowercase and trimmed; subject/name/description validated for type, length, and control characters.
- Office and request type are validated both when the submission begins and when verification is consumed.
- Description limit is 10,000 characters; name and subject limits are 140 characters; email is limited to 254 characters.
- Pending submission TTL is 30 minutes.
- Token is generated using `secrets.token_urlsafe(32)`; only its SHA-256 digest is used in the cache key.
- Opening the verification link does not itself create the ticket. The guest page requires an explicit confirmation action, reducing accidental submission by mail-security link scanners.
- IP-based rate limits currently apply to start (5 requests / 60 seconds) and verify (10 requests / 60 seconds), using `user_based=False`.
- Verification uses a site-scoped Redis lock held until the surrounding DB transaction commits or rolls back. A deterministic UUID ticket key and a unique `HD Ticket.key` field provide idempotency backstops.
- The pending cache entry is deleted after commit, not before. A rollback leaves the pending request available for a retry.
- Ticket insertion is a narrow server-side `insert(ignore_permissions=True)`. It is not a Guest role permission grant.
- Attachments are not accepted.

### Native HD Ticket integration

**`helpdesk/extends/anonymous_ticket.py`**

`AnonymousHDTicketMixin` is registered through `extend_doctype_class` in `helpdesk/hooks.py`.

The service sets transient server-owned flags only after token verification. The mixin then:

- Sets owner to `Guest` for the anonymous submission.
- Preserves the verified email in `raised_by`.
- Skips Contact ownership validation and Contact/Customer auto-association only for the verified anonymous path.
- Assigns the deterministic idempotency key.
- Preserves the native ticket controller behavior for ordinary submissions.
- Keeps native agent reply delivery but avoids the authenticated customer-portal reply template/link for Guest-owned tickets.

This narrow lifecycle exception exists because the normal ticket controller may associate or reject an email that matches an existing Contact. An email string is not proof of an authenticated Contact/Customer identity. Never broaden this exception to normal tickets.

### Hooks and permissions

**`helpdesk/hooks.py`**

- Registers `AnonymousHDTicketMixin` under `extend_doctype_class["HD Ticket"]`.
- Registers `notify_anonymous_requester_status` on `HD Ticket.on_update`.
- Existing HD Ticket `has_permission` and `permission_query_conditions` hooks remain responsible for read isolation.

The guest path must not use any helper that grants broad Guest read/write/create permission on `HD Ticket`. The service is the only public creation boundary; ticket list/detail/update routes remain protected.

### Email behavior

- Verification email is sent to the submitted address.
- After ticket creation, a fixed guest-safe acknowledgement is sent when the Helpdesk acknowledgement setting is enabled. It does not include an authenticated portal URL.
- Agent replies use the native reply workflow with `raised_by` as the default recipient. The Guest-owned ticket path suppresses the customer portal template branch so the inaccessible ticket-detail link is not included.
- A custom `HD Ticket.on_update` hook sends a minimal status-only notice when the status changes, subject to the existing email-workflow skip setting.
- Realtime notifications are user-based and do not cover email-only requesters.
- **Inbound anonymous email reply ownership has not been established. Do not claim inbound email replies are supported.**
- Do not claim every field update or every status event is emailed. The custom hook is status-change-only.

### Studio guest page and route

- `studio/helpdesk/studio_page/guest_new_ticket/guest_new_ticket.json` is published with `allow_guest: 1`, route `/guest/new`.
- The public portal root is `/help`, so the full guest URL is `/help/guest/new`.
- `shared/src/portalRoutes.ts` defines `ROUTES.guestTicket = '/guest/new'`.
- The form component is `studio/helpdesk/components/ticket/PortalPortalGuestTicketSubmission.vue`.
- The guest page uses the guest form options/start/verify endpoints and has explicit confirmation before verification.

### Existing route map (important)

The portal route definitions currently show:

| Purpose | Canonical portal path |
|---|---|
| Portal / KB home | `/help` |
| Guest submission | `/help/guest/new` |
| Authenticated ticket list | `/help/my-tickets` |
| Authenticated new ticket | `/help/my-tickets/new` |
| Authenticated ticket detail | `/help/my-tickets/:name` |

Do not confuse the canonical authenticated new-ticket route with `/help/tickets/new`. Legacy redirects in `helpdesk/hooks.py` forward older `/helpdesk/my-tickets...` and `/help/tickets/...` paths into the current `/help/my-tickets...` structure. Confirm the actual redirect behavior when testing old links.

---

## 4. Known guest-access defect and exact intended policy

### Root cause and source-level fix

The Studio page's `allow_guest: 1` is not enough to make the page reachable when the private-KB redirects execute earlier.

Two guards currently force Guests to login:

1. **`helpdesk/helpdesk/hooks/studio_app.py`** sets boot value `send_guest_to_login` when session user is Guest and `HD Settings.public_knowledge_base` is false.
2. **`studio/helpdesk/stores/session.ts`** has an early boot redirect based on `window.boot.send_guest_to_login`, then a second session-load guard `sendGuestToLogin()` that calls `signIn()` whenever the KB is private.

The observed pilot behavior is that direct guest access to `/help/guest/new` is redirected to login under private-KB configuration. The guest route metadata does not override these global guards.

### Intended route policy

| KB setting | Route | Guest behavior | Authenticated behavior |
|---|---|---|---|
| Private | `/help` | Redirect to login | Preserve existing behavior |
| Private | `/help/guest/new` | **Allow guest submission** | Preserve page behavior |
| Private | `/help/my-tickets` | Keep protected / redirect to login | Allow |
| Private | `/help/my-tickets/new` | Keep protected / redirect to login | Allow |
| Public | `/help` | Browse public KB; no authenticated-only ticket actions | Browse KB and retain normal ticket actions |
| Public | `/help/guest/new` | Allow guest submission | Preserve page behavior |

Implemented in both boot-time and Studio session guards. The boot hook compares the request path to the exact `/help/guest/new` route after trimming trailing slashes. The session store applies the same exact path predicate to both its early boot redirect and asynchronous session-load redirect. `?verify=...` does not affect `location.pathname`. Do not broaden this to `/help/guest/*`. Normalize the path only as required (for example, a trailing slash), but do not use a broad `startsWith('/help/guest')` or disable the private-KB redirect globally. Do not expose private KB content, ticket reads, or authenticated ticket creation.

---

## 5. Revised guest-entry UI implementation plan

This UI/navigation slice is **not implemented yet**. Work on the existing feature branch after verifying its current head.

### Task A — route-specific redirect exception (implemented in Helpdesk source)

Files:

- `helpdesk/helpdesk/hooks/studio_app.py`
- `studio/helpdesk/stores/session.ts`

Implementation requirements:

1. Determine the request path available at boot time in `get_boot()`; verify whether it is the full path or a path relative to the Studio app.
2. Set `send_guest_to_login` false only for Guest requests whose resolved path is the guest submission route.
3. In `session.ts`, add the same exact route exception to the early boot redirect and the asynchronous `sendGuestToLogin()` guard. Avoid having one guard redirect after the other allows the page.
4. Keep `isGuest` and `canCreateTicket` semantics unchanged. A Guest remains a Guest.
5. Test direct navigation, refresh, trailing slash, query string `?verify=...`, and client-side navigation. The verification query must not cause the route to be treated as a different path.

### Task B — shared CBSUA login page (implemented in source)

The Frappe login context now sets the logo to `/assets/helpdesk/desk/cbsua/cbsua-logo-2400.png` and the app name to **CBSUA Helpdesk**. The login template renders **Submit a ticket without logging in** as a fixed `/help/guest/new` text link beneath the primary authentication actions, replaces the sign-in welcome copy with **Welcome back to CBSUA Helpdesk**, and overrides the favicon, PNG favicons and Apple touch icon with the canonical CBSUA assets. This link is available on direct `/login` visits and is a navigation affordance, not authorization.

Helpdesk `loginUrl()` now preserves `last_visited` and returns plain `/login`; the `helpdesk_guest=1` marker and Referer condition have been removed. The Frappe changes are on `feat/anonymous-helpdesk-login-cta`; the Helpdesk session change is on `feat/anonymous-tickets`. The deployment lock remains unchanged. Runtime verification of static asset delivery, login variants and redirects is still required.

Original investigation files:

- Helpdesk's `loginUrl()` in `studio/helpdesk/stores/session.ts`. It stores `location.pathname + location.search` in localStorage key `last_visited` and returns `/login`.
- Framework login template: `cbsua-app-frappe/frappe/www/login.html`. Its `email_login_body()` macro renders the existing Continue and Login with Email Link options and is reused by the login page's main and social-login subviews.
- Framework website/login context and hooks to identify a supported way to pass a Helpdesk-origin marker.

Requirements:

1. Establish a reliable, narrowly validated Helpdesk-origin context that survives the redirect to `/login`. Inspect the Frappe login/last_visited behavior before choosing the mechanism; do not guess that localStorage is visible to the server template.
2. Prefer a supported Helpdesk app integration or login-context hook if available. If a framework template change is required, keep it conditional and minimal.
3. Render the secondary link below the normal login options only when the request is clearly from the Helpdesk portal. Avoid displaying the CBSUA Helpdesk CTA on unrelated Frappe app login screens.
4. Link to the fixed local path `/help/guest/new`; do not accept an arbitrary external redirect target.
5. Treat the CTA strictly as navigation. The guest endpoint's own validation and authorization boundaries remain mandatory.
6. Consider all login template states: password Continue may be disabled, email-link login may be enabled, LDAP/social login may be configured, and the macro may render in more than one login subview. Do not duplicate or misplace the CTA.

Potential ownership: Helpdesk should own the origin marker and guest destination; the framework fork should change only the shared login template/context if there is no clean app-level extension. Verify exact Frappe framework commit compatibility and document the framework patch rationale.

### Task C — KB homepage actions (implemented in Helpdesk source)

Files:

- `studio/helpdesk/studio_page/public_kb/public_kb.json`
- `studio/helpdesk/studio_page/public_kb/public_kb.ts`
- `studio/helpdesk/composables/useKnowledgeBaseHeader.ts`

Implemented source changes:

- A top-level `guest-request-entry` block in `public_kb.json` adds the anonymous CTA before the KB content.
- The empty-KB state has `Raise a ticket` and `View my tickets` buttons without a Guest visibility condition.
- The header/composable has session capability logic; preserve its authenticated behavior.

Requirements:

1. Removed the top-level `guest-request-entry` block.
2. Exposed `session.canCreateTicket` through `useKnowledgeBaseHeader()` and applied `visibilityCondition: {{ canCreateTicket }}` to the empty-state action group. The underlying session capability remains false for Guests.
3. Authenticated actions and the existing header behavior are preserved.
4. No replacement anonymous CTA was added to the KB homepage.

### Task D — update feature and current docs

Source implementation has been made. Documentation updates record source status separately from runtime validation:

- `docs/features/anonymous-ticket-submission.md`
- `docs/current/README.md`
- `docs/current/architecture.md`
- This handoff file with actual commit and validation results.

Clearly distinguish implementation from tested behavior. Update the deployment note only after checking the deployment repository's current build branch/source lock.

---

## 6. Security and privacy invariants (must not regress)

1. Email ownership must be verified before ticket creation.
2. Guest endpoints accept only the explicit allowlist; never accept arbitrary DocType payloads or privileged fields.
3. Never accept client control of owner, contact, customer, agent group, assignment, priority, status, internal visibility, ticket key, or attachments.
4. Do not grant generic Guest read/create/write permissions on `HD Ticket`.
5. Guest cannot list, read, search, update, or infer any ticket, including a ticket whose `raised_by` matches the Guest's submitted email or a registered user's login name.
6. Do not auto-associate a Guest submission to an existing Contact or HD Customer based on email equality.
7. Only a server-verified submission may set the transient anonymous ticket flags. Do not expose a client-controlled flag.
8. Keep verification token single-use, expiring, protected in cache, and idempotent under replay/concurrency.
9. Keep the verification lock held until commit/rollback. Do not release it at function return.
10. Pending payload must remain available if ticket insertion rolls back; delete it only after commit.
11. No guest attachment uploads until a separate upload authorization, ownership, expiry, and cleanup design exists.
12. Email content must be requester-safe. Internal comments and agent-only information must never be mailed to the requester.
13. Do not include an authenticated portal ticket link in Guest acknowledgement or agent-reply emails.
14. Do not advertise inbound email replies until sender identity validation is implemented and tested.
15. Rate limiting is not a complete anti-abuse solution. Evaluate CAPTCHA or deployment-level controls based on actual threat model and traffic; document the choice.

---

## 7. Validation plan and release gates

No Frappe bench/site, browser session, real outgoing mail account, Studio production build, or Semgrep run was available during this implementation. The focused test file exists but **has not been executed here**. Source changes are committed to the feature branches, but every runtime, integration, build, and security check below remains outstanding.

### A. Environment and source lock

- Create/use a disposable Frappe v17-compatible bench with the same Helpdesk, Frappe, Telephony, and UI refs intended for integration.
- Verify the exact deployed framework commit supports `extend_doctype_class` and the login-context integration selected.
- Inspect the deployment repository's `config/source-lock.json`, build workflow, and documented canonical branch before promoting the feature.
- Confirm database engine/version and migration behavior for the unique `HD Ticket.key` index.

### B. Focused tests

Run from the bench:

```bash
bench --site <disposable-site> run-tests --app helpdesk --module helpdesk.tests.test_anonymous_tickets
```

The existing tests cover helper-level behavior including token digest/cache key, deterministic ticket key, unique metadata, Guest read isolation, server-owned insert flags, input normalization, invalid email, office/request-type consistency, malformed token/value handling, and content limits. They do **not** establish the full transaction, email, or browser flow.

Add integration tests for:

- Start request sends a verification email and creates no ticket.
- Invalid/expired token cannot create a ticket.
- Successful verification creates exactly one native ticket.
- Repeated verification returns the same ticket.
- Concurrent verification requests cannot create duplicates.
- DB rollback does not consume the pending token or permanently strand the lock.
- Existing Contact / Customer email collision does not associate the Guest ticket or reject the valid submission.
- Guest and a registered user sharing the same email cannot read the Guest-owned ticket.
- Guest cannot list/read/update tickets via portal/API/DocType endpoints.
- Client-supplied privileged fields are rejected or ignored.
- Agent reply and status notification email contain no private data or authenticated portal link.
- Authenticated ticket create/list/detail/reply behavior remains unchanged.

### C. Browser and route matrix

Test in a real browser with both public-KB settings and both Guest/authenticated sessions:

- Private KB + Guest + `/help`: redirects to login.
- Private KB + Guest + direct `/help/guest/new`: guest page loads after the redirect exception.
- Private KB + Guest + refresh and `?verify=<token>`: page remains accessible.
- Private KB + Guest + `/help/my-tickets` and `/help/my-tickets/new`: remain protected.
- Public KB + Guest + `/help`: articles remain browseable; no authenticated ticket actions; no top-level anonymous CTA.
- Public KB + Guest + `/help/guest/new`: loads.
- Authenticated + public KB: authenticated actions remain available and work.
- Authenticated + private KB: existing portal policy remains unchanged.
- Login page reached from Helpdesk: guest CTA appears in the intended location.
- Login page reached from unrelated app/root: Helpdesk CTA does not appear.
- Login configurations with password, email-link, and optional LDAP/social login do not duplicate or hide the CTA incorrectly.
- Mobile layout and keyboard/screen-reader navigation work.

### D. Build, static analysis, migration and email

- Build Studio/Desk assets using the repository's documented package manager and build scripts; inspect `package.json` before selecting commands.
- Run Frappe Semgrep on changed Python files and resolve findings.
- Run formatting/lint/type checks used by this repository.
- Migrate a representative copy of a real site; confirm no duplicate `HD Ticket.key` values and that the unique index is created.
- Verify outbound verification, acknowledgement, agent-reply and status-change email with a real configured account and inspect rendered content/headers.
- Test email workflow disabled settings and failure logging.
- Check that logs do not contain raw verification tokens or sensitive requester content.

### E. Acceptance criteria

Do not call the feature complete until all are true:

- Guest can discover and reach `/help/guest/new` from the Helpdesk-origin login screen, including when KB is private.
- Public KB Guests do not see authenticated ticket actions.
- Email is verified before exactly one native ticket is created.
- Guest cannot read or manage any ticket.
- Existing authenticated customer and agent flows remain unchanged.
- Requester emails are privacy-safe and verified in a real mail setup.
- Migrations, rate limits, expiry, replay, concurrency, and failure behavior are validated.
- The deployment image uses reviewed immutable source SHAs and has passed site migration and smoke tests.

---

## 8. Suggested execution order for the next agent

1. **Orient and verify:** read this handoff, `docs/current/README.md`, `docs/current/architecture.md`, and the feature guide. Fetch the current branch head; do not assume the SHAs in an old chat are still current. Inspect the current source before editing.
2. **Build a disposable runtime:** confirm exact Frappe/Helpdesk/Telephony refs and get the existing focused tests running. This catches pre-existing API/version issues before adding more UI work.
3. **Validate the route exception:** test the exact Guest route exemption in both boot and Studio guards on a running private-KB site.
4. **Validate login context:** exercise the marker and same-origin Referer checks in a browser; ensure unrelated login flows do not show the CTA.
5. **Validate the login CTA:** test password, email-link, LDAP/social login template states and confirm the fixed local destination.
6. **Validate the KB homepage:** confirm the top CTA is absent and authenticated-only empty-state actions are hidden for Guest but remain available to authenticated users.
7. **Add integration/browser tests:** cover route matrix, login origin, privacy, transaction, email and authenticated regressions.
8. **Run build/security/migration checks:** record exact commands and output, including unique-index migration result.
9. **Reconcile docs and deployment:** update feature/current docs; inspect deployment source lock and prepare a separate coordinated release change only when authorized.
10. **Handoff again:** record commit SHAs, changed files, checks actually run, remaining gaps, and the next concrete task.

Avoid combining the login-template change, Helpdesk route policy, and deployment source-lock promotion into one unreviewable change. Keep commits logically separated where practical.

---

## 9. Important references and working resources

### CBSUA repositories

- [CBSUA Helpdesk fork](https://github.com/AgeReapor/cbsua-app-helpdesk)
- [CBSUA Frappe fork](https://github.com/AgeReapor/cbsua-app-frappe)
- [CBSUA Frappe UI fork](https://github.com/AgeReapor/cbsua-app-frappe-ui)
- [CBSUA Helpdesk deployment](https://github.com/AgeReapor/cbsua-app-helpdesk-deployment)
- [CBSUA Pilot](https://github.com/AgeReapor/cbsua-app-pilot)

### Relevant source files

- [Guest API](https://github.com/AgeReapor/cbsua-app-helpdesk/blob/feat/anonymous-tickets/helpdesk/anonymous_tickets.py)
- [Anonymous ticket mixin](https://github.com/AgeReapor/cbsua-app-helpdesk/blob/feat/anonymous-tickets/helpdesk/extends/anonymous_ticket.py)
- [Helpdesk hooks](https://github.com/AgeReapor/cbsua-app-helpdesk/blob/feat/anonymous-tickets/helpdesk/hooks.py)
- [Studio boot hook](https://github.com/AgeReapor/cbsua-app-helpdesk/blob/feat/anonymous-tickets/helpdesk/helpdesk/hooks/studio_app.py)
- [Studio session store](https://github.com/AgeReapor/cbsua-app-helpdesk/blob/feat/anonymous-tickets/studio/helpdesk/stores/session.ts)
- [Guest Studio page definition](https://github.com/AgeReapor/cbsua-app-helpdesk/blob/feat/anonymous-tickets/studio/helpdesk/studio_page/guest_new_ticket/guest_new_ticket.json)
- [KB homepage definition](https://github.com/AgeReapor/cbsua-app-helpdesk/blob/feat/anonymous-tickets/studio/helpdesk/studio_page/public_kb/public_kb.json)
- [Portal route definitions](https://github.com/AgeReapor/cbsua-app-helpdesk/blob/feat/anonymous-tickets/shared/src/portalRoutes.ts)
- [Framework login template](https://github.com/AgeReapor/cbsua-app-frappe/blob/feat/anonymous-helpdesk-login-cta/frappe/www/login.html) — shared Frappe login page; companion implementation branch: [feat/anonymous-helpdesk-login-cta](https://github.com/AgeReapor/cbsua-app-frappe/tree/feat/anonymous-helpdesk-login-cta).
- [Feature guide](../features/anonymous-ticket-submission.md)
- [Architecture notes](architecture.md)

### Upstream and skill resources

- [Frappe Framework documentation](https://docs.frappe.io/framework)
- [Frappe Helpdesk upstream](https://github.com/frappe/helpdesk)
- [Frappe official agent skills](https://github.com/frappe/skills)
- [LUBUS Frappe skills](https://github.com/lubusIN/frappe-skills)
- [Frappe Framework hooks documentation](https://docs.frappe.io/framework/user/en/python-api/hooks)
- [Frappe DocType controller documentation](https://docs.frappe.io/framework/user/en/basics/doctypes/controllers)
- [Frappe testing documentation](https://docs.frappe.io/framework/user/en/guides/automated-testing)

Use the repository's actual skill notes and the installed/repository Frappe development, API, code-review, web-form, and enterprise-pattern skills where applicable. Confirm that skill instructions match the target v17 framework version. Do not assume an upstream guide describes CBSUA fork behavior exactly.

---

## 10. Handoff completion template

The receiving agent should replace/update this section at the next handoff:

- **Date / agent:**
- **Branch:**
- **Latest implementation commit SHAs:** Helpdesk `45c4bd8d3603d61d6362280be95ead16d60a2cfb`; Frappe `5ae23fcaa85436fb818f2716eafb543bee2849ae` (branch `feat/anonymous-helpdesk-login-cta`). Latest Helpdesk documentation commit before this handoff refresh: `02274ed4ec7b1b3b41d94f837dab53ac505850a9`.
- **Repositories changed:** `AgeReapor/cbsua-app-helpdesk` (`feat/anonymous-tickets`), `AgeReapor/cbsua-app-frappe` (`feat/anonymous-helpdesk-login-cta`)
- **Source changes:** exact `/help/guest/new` bypass in both guards; marker + same-origin Referer-gated login CTA; removed KB top CTA; Guest-hidden empty-state actions via `canCreateTicket`.
- **Summary of implementation:**
- **Files changed:**
- **Tests run (exact commands):** None; no local checkout/bench/browser is available through the current repository connector.
- **Build / lint / Semgrep results:** Not run.
- **Migration / unique-index result:**
- **Email verification evidence:**
- **Browser route matrix result:**
- **Known defects / risks:** Source-level changes have not been runtime-verified; login CTA depends on same-origin Referer being sent by the browser; verify deployed framework compatibility and Studio binding behavior. The route trailing-slash normalizer uses a forward-slash-only regular expression.
- **Deployment source-lock status:** Unchanged. The lock still pins Frappe `0c68cdeff2e64d0fe0be84568b515531e2b506a8` and Helpdesk `98838938409bbeb038717667ac7880dd5b5edd6f`; neither feature branch is promoted.
- **Next concrete action:**

**Final caution:** Source inspection and documentation commits are not runtime validation. Keep the feature marked in progress until the acceptance criteria above have real test evidence.


## Login-page implementation update — 2026-11-23

- Frappe branch `feat/anonymous-helpdesk-login-cta`: login context commit `ca22bad01035014b33a6cb5b9b9277468187f028`; login template commit `3bea4a3b153e6805c284043c4332933a3e690bd3`.
- Helpdesk branch `feat/anonymous-tickets`: session redirect cleanup commit `a85fed011fd195e3bf763c72d936bbaa09b2ceab`.
- Frappe login page now uses the CBSUA logo and favicon assets served by Helpdesk, generic CBSUA welcome copy, and a global guest-submission text link.
- Removed the Helpdesk-origin query marker and Referer gate; `last_visited` storage remains intact.
- **Validation not run:** no local checkout/bench/browser/build runner is available through the GitHub repository connection. Verify the login template renders correctly with password, email-link, LDAP and social login configurations; verify all static asset URLs; run Python lint/tests and frontend build; test direct `/login`, private/public KB and guest-route matrix.

**Next concrete action:** check out both feature branches in a compatible Frappe v17 bench, run targeted tests and builds, then verify the full browser matrix. Do not promote the deployment source lock until that validation passes.


---

## Guest verification email and failure-state fix — 2026-11-23

- **Repository / branch:** `AgeReapor/cbsua-app-helpdesk`, `feat/anonymous-tickets`.
- **Base observed before edits:** `2e08d4a5599c749cb7bfb12e39155957c7e81252`.
- **Problem traced:** the backend previously collapsed invalid/expired tokens and infrastructure exceptions into Frappe errors, while the Vue component mapped every failed verification call to one expired/already-used message. The email body was assembled inline and the URL was built by concatenating `get_url()` with a route, leaving Host-header-derived URL behavior and query encoding implicit.
- **Source changes committed:**
  - Added branded HTML and plain-text templates: `helpdesk/templates/emails/guest_ticket_verification.html` and `.txt`.
  - Added Jinja rendering with both HTML and plain-text alternatives passed to `frappe.sendmail`, a request summary limited to subject/office/type, escaped template values, and a canonical URL builder using `get_url(..., allow_header_override=False)` plus URL encoding.
  - Verification now returns structured `invalid_or_expired`, `processing`, and `temporarily_unavailable` codes for expected failure modes. Cache/lock failures are logged with traceback context; bearer tokens are not included in those log messages.
  - Portal confirmation UI now separates expired/invalid from temporary service errors, supports retry for temporary/in-progress outcomes, and avoids telling a requester to create a duplicate request when the result is uncertain.
  - Added focused tests for malformed and expired tokens, canonical URL generation/encoding, and lock/cache service failure classification.
- **Implementation commits:**
  - Portal error-state UI: `17dba88734d8809a4f06f143ab5054662b4116d7`, wording refinement `f047ffca3569c1916ea21a3b700f5fbb9ab18fc5`
  - Backend URL/rendering/error classification: `29f61d75db79bbe19a04dacc09299209fc388564`, then plain-text delivery integration `04f02e6653edc2bf79c01ef59f88dc07c09a475d`
  - Branded HTML template: `98f05dc7e5a74c1414060305a6e086920e157091`
  - Plain-text template: `20db53df72f69f3a83cf89f9d715205d15245b6d`
  - Template escaping: `16aefa7f928cbdfadca874b65fab9bb8a78fe710`
  - Verification tests: `20387817219b429ce2d82f63c17cc85094f79a5a`, `efe55fa4388662d5877b8d1cb4844ab550160c4d`, plus expiry/cache-outage coverage `fb86a6e7d9fad5e2a7351e066fc98f4cd3814c66`
  - Lock-release outage handling: `6f21a47ada046d953632007e2b1b6e5473804388`
- **Validation performed:** source inspection only. No local checkout, Pilot bench, Redis, browser, or real outbound mail account is available through the GitHub connector; targeted Frappe tests, template rendering, Studio build, and gateway round-trip have not been run.
- **Important runtime check:** the site config `host_name` / `hostname` must point to the public gateway hostname with the correct scheme and port. Because the new URL builder intentionally ignores request Host headers, an incorrect/missing canonical host setting will produce a non-public or unreachable link. Verify the generated link is exactly the externally reachable gateway origin.
- **Next actions:** run `bench --site <site> run-tests --app helpdesk --module helpdesk.tests.test_anonymous_tickets` (or the repository's Pilot equivalent); build Studio; send a real test email through the pilot gateway; confirm link opens the confirmation screen without consuming the token; confirm once; reopen the link and confirm it returns the same ticket reference; test expiry and temporary Redis outage; inspect rendered email in desktop/mobile clients.
- **Deployment:** no framework branch, deployment source lock, image ref, or pilot gateway configuration was changed. Do not promote until the runtime checks above pass.


**Latest source commits after the initial email fix:** backend lock-release resilience `6f21a47ada046d953632007e2b1b6e5473804388`; expiry/cache outage tests `fb86a6e7d9fad5e2a7351e066fc98f4cd3814c66`. The email backend now loads both template formats through Frappe's `get_email_from_template` and passes the plain-text alternative as `text_content` to `frappe.sendmail`.

**Latest feature branch head at handoff refresh:** `f047ffca3569c1916ea21a3b700f5fbb9ab18fc5`. This is the Helpdesk feature branch only; no changes were made to the framework or deployment repositories. The latest documentation refresh follows the latest implementation commits.

**Final source formatting commits:** backend email-renderer signature `7b6fc8e76378f661633ccd95263ba10bec6548b2`; focused test formatting `d098e6b3cdeae813c6cdaf29fb4c719591c7cc60`. The working branch head before this handoff-document refresh was `d098e6b3cdeae813c6cdaf29fb4c719591c7cc60`.

---

## Pilot HTTP 500 on anonymous submission — 2026-11-23

- **Symptom reported:** submitting the guest form at `/help/guest/new` returns an Internal Server Error.
- **Root cause identified from source compatibility:** `start_guest_submission()` passed `text_content=` to `frappe.sendmail()`. The exact Frappe v17 fork branch `feat/anonymous-helpdesk-login-cta` exposes `frappe.email.sendmail(..., template=None, args=None, ...)`, but has no `text_content` parameter. This raises a Python unexpected-keyword `TypeError` when the endpoint queues the verification email.
- **Correct implementation:** use `frappe.sendmail(recipients=[...], subject=..., template="guest_ticket_verification", args=email_context)`. Frappe internally calls `get_email_from_template` and supplies both the HTML and optional text alternative to its queue builder. The Helpdesk backend now prepares only the template context and delegates both renderings to the supported Frappe API.
- **Helpdesk commits:** backend correction `34ef87ead0c95d1f9382e5bc10453acf510ac842`; test update `26b84a3e7f5868253e761a08643def3ab46b7c4d`.
- **Framework source inspected:** `AgeReapor/cbsua-app-frappe`, `feat/anonymous-helpdesk-login-cta`, `frappe/email/__init__.py`. Its sendmail signature documents and implements `template` and `args`; it does not accept `text_content`.
- **Important correction to the earlier handoff note:** the previous claim that Helpdesk could pass `text_content` directly to `frappe.sendmail` was incorrect. The supported Frappe template interface is now used.
- **Validation state:** source-level root cause and correction only. No live Pilot request, bench test, email queue, or rendered-message validation has been run. Deploy/restart the Helpdesk app containing this commit, retry one guest submission, and inspect the Frappe Error Log if a 500 remains. If it persists, capture the server traceback and failing request method; do not assume it is still the same issue.
- **Next checks:** run the focused anonymous-ticket test module; confirm `start_guest_submission` queues the named email template; confirm both HTML and text alternatives appear in the queued message; confirm the generated verification link uses the public gateway origin; then complete the verify/replay/expiry checks.
