# Current Architecture and Repository Boundaries

> Status: repository inspection notes for the `feat/anonymous-tickets` workstream. Verified against the repository files listed below; re-check paths and refs when the branch changes.

## 1. Repository responsibilities

CBSUA Helpdesk is a multi-repository Frappe application stack. Do not treat `cbsua-app-helpdesk` as a self-contained application or assume that its frontend and framework are vendored entirely inside it.

```mermaid
flowchart TB
  subgraph Platform["CBSUA Frappe platform"]
    F["cbsua-app-frappe\nFrappe Framework fork\nRuntime, DocTypes, auth, permissions, APIs, Desk"]
    S["Studio app in Frappe\nJSON-defined Vue portal runtime"]
    U["cbsua-app-frappe-ui\nVue component library / composables"]
    F --> S
  end

  subgraph Product["CBSUA Helpdesk product"]
    H["cbsua-app-helpdesk\nHelpdesk backend + agent Desk + Studio portal source"]
    P["studio/helpdesk\nStudio App pages, scripts, components, stores"]
    B["helpdesk/\nPython APIs, DocTypes, controllers, hooks"]
    H --> P
    H --> B
  end

  U -. "frontend library dependency / submodule" .-> H
  F --> H
  D["cbsua-app-helpdesk-deployment\nSource refs, image build, Compose, release operations"]
  H --> D
  F --> D
  U --> D
```

### `cbsua-app-frappe` — framework dependency

This is the CBSUA-maintained Frappe Framework fork. It supplies the platform capabilities used by Helpdesk, including:

- Bench/site application runtime and migration lifecycle.
- DocTypes, ORM/database model, document controllers and hooks.
- Authentication, sessions, roles, permissions and whitelisted APIs.
- Background jobs, scheduler, realtime and core Desk.
- The Frappe Studio application/runtime used to render exported Studio Apps.

Helpdesk-specific requester behavior belongs in Helpdesk or a dedicated extension, not in the framework fork unless a reusable framework-level change is demonstrably required.

### `cbsua-app-frappe-ui` — frontend UI library dependency

This is the CBSUA-maintained fork of Frappe UI, the Vue-based frontend component library. It supplies shared UI components, composables, utilities and styling consumed by the Helpdesk frontend.

It is not the Studio runtime and is not a separately installed Frappe app. It is consumed as a frontend source dependency/submodule in the Helpdesk repository/build.

**Submodule provenance check:** the `.gitmodules` file inspected on the current `develop` branch declared path `frappe-ui` with URL `https://github.com/frappe/frappe-ui.git`, while the CBSUA fork repository exists separately. Before depending on CBSUA-only UI changes, verify the `.gitmodules` URL and gitlink SHA on `feat/anonymous-tickets`, and verify the deployment source lock/build checkout. Do not infer that the CBSUA fork is actually built merely because it exists. Resolve the URL/ref mismatch deliberately if needed; preserve the exact tested gitlink SHA.

### `cbsua-app-helpdesk` — application and portal source

This repository contains the Helpdesk app: backend Python code, DocTypes/controllers, API methods, hooks, agent Desk frontend and the exported Studio customer portal.

It depends on the CBSUA framework fork for its runtime and on the Frappe UI library for frontend components. It is not the deployment repository.

### `cbsua-app-helpdesk-deployment` — release and runtime assembly

This repository owns deployment-specific source refs/source lock, image assembly, Compose configuration, release promotion, operational runbooks, backups and rollback. The exact framework, Helpdesk, Telephony and UI source revisions used in a build must be verified there rather than inferred from branch names.

## 2. Customer portal: Studio, not a standalone Vue router app

The customer-facing portal at `/help` is an exported **Studio App named `helpdesk`**, defined in this repository under `studio/helpdesk/`. Studio ships with the Frappe framework fork.

The Studio app record in `studio/helpdesk/helpdesk.json` identifies:

- `app_name`: `helpdesk`
- `route`: `help`
- `app_home`: the public knowledge-base page

Studio renders each page from a JSON block tree. A page can also have a TypeScript setup script. Custom Vue components are referenced from those block trees and rendered by Studio. Do not add a separate Vue router or replace the Studio app architecture for this feature.

### Studio source layout

The portal README (`studio/README.md`) documents this layout:

```text
studio/helpdesk/
  helpdesk.json
  router.ts
  studio_page/<page>/
    <page>.json
    <page>.ts
  studio_components/
  components/
  stores/
  composables/
  shared/
```

- `.json` files define Studio App/Page/Component records and page block trees.
- Page `.ts` files export `setup(context)`; their returned values are exposed to blocks.
- `components/` contains custom Vue components referenced by Studio block definitions.
- `stores/` and `composables/` hold portal state and page logic.
- Shared code is used by both the portal and agent Desk only when genuinely shared; preserve existing imports and conventions.

Studio source files are the source of truth for standard app pages. `bench migrate` imports the standard records into Studio DocTypes; developer-mode editor saves write source files. Build the Studio bundle with the documented Frappe commands, not by treating the JSON as a conventional Vue route component.

### Existing portal pages and access

The current `studio/README.md` documents these page routes:

| Studio page | Portal URL | Guest access | Purpose |
|---|---|---:|---|
| `public_kb` | `/help` | Yes | Public knowledge-base home |
| `categories` | `/help/categories` | Yes | Knowledge-base categories |
| `category` | `/help/category/:category` | Yes | Category articles |
| `article` | `/help/articles/:name` | Yes | Public article |
| `customer_tickets` | `/help/my-tickets` | No | Authenticated ticket list |
| `new_ticket` | `/help/tickets/new` (legacy redirect may route to `/help/my-tickets/new`) | No | Authenticated ticket creation |
| `guest_new_ticket` | `/help/guest/new` | Yes | Email-verified anonymous ticket submission |
| `ticket` | `/help/tickets/:name` | No | Authenticated ticket conversation |

The exact route aliases and current route constants must be checked in the actual shared portal route source before adding a new route.

### Guest/session behavior

The current portal session store (`studio/helpdesk/stores/session.ts`) derives `isGuest` from the config response and defines `canCreateTicket` as false for guests. Its private-KB redirect now exempts only `/help/guest/new`, both before app initialization and after the session config loads. The boot hook applies the same exact path exception; all other Guest routes remain protected. This source behavior still requires browser validation.

The existing new-ticket Studio Page JSON (`studio/helpdesk/studio_page/new_ticket/new_ticket.json`) has `allow_guest: 0`. Therefore, exposing anonymous ticket creation is not just a backend API change: it needs a Studio page explicitly available to guests and deliberate session/navigation/UI behavior that preserves the existing authenticated routes.

The dedicated `/help/guest/new` page is implemented in `studio/helpdesk/studio_page/guest_new_ticket/` with `allow_guest: 1`. Its route is registered in `shared/src/portalRoutes.ts`. The existing authenticated page remains guest-disabled; do not change its access metadata. The public KB page no longer contains a top-level anonymous CTA, and the empty-state ticket action group is visible only when the page's `canCreateTicket` binding is true.


### Shared CBSUA login experience and guest route exception

The login entry path spans the Helpdesk Studio portal and the shared Frappe login page:

- Helpdesk `loginUrl()` preserves `last_visited` and navigates to plain `/login`; it no longer adds a `helpdesk_guest=1` query marker.
- Frappe `frappe/www/login.py` sets the shared login logo to the canonical Helpdesk static asset `/assets/helpdesk/desk/cbsua/cbsua-logo-2400.png` and sets the displayed app name to CBSUA Helpdesk.
- Frappe `frappe/www/login.html` renders **Submit a ticket without logging in** as a text link below the primary login actions, with a fixed `/help/guest/new` destination. It updates the welcome heading and overrides favicon, PNG favicon and Apple touch icon references to the existing Helpdesk static assets under `/assets/helpdesk/desk/cbsua/`.
- The CTA is global to the CBSUA deployment login page, not conditional on a Helpdesk-origin marker or Referer. It is navigation only and does not alter guest authorization.
- Frappe changes are on `feat/anonymous-helpdesk-login-cta`; Helpdesk session changes are on `feat/anonymous-tickets`. The deployment lock remains unchanged and neither feature branch is promoted by this work.

The Helpdesk repository exposes the relevant assets under `desk/public/cbsua/`; the existing app listing already references `/assets/helpdesk/desk/cbsua/favicon-32x32.png`, supporting the chosen public asset URL pattern. The exact login-page image requests and full browser experience still require runtime verification.

## 3. Existing ticket creation and requester model

The existing portal form is the custom Vue component `NewTicketForm.vue`, used by the Studio `new_ticket` page. It currently:

1. Loads the existing ticket template and field layout.
2. Loads CBSUA offices and office-specific request types.
3. Validates subject, description and configured required fields in the browser.
4. Uploads private attachments through the existing authenticated upload path.
5. Calls `helpdesk.helpdesk.doctype.hd_ticket.api.new`.

The backend `api.new` function currently:

- Is whitelisted without `allow_guest=True`.
- Accepts the ticket document, attachments and optional portal origin.
- Sets `doctype = "HD Ticket"`.
- Sets `via_customer_portal` from the current session user.
- Sets `raised_by = frappe.session.user`.
- Inserts the native `HD Ticket` and returns fields filtered through `TicketFields`.

The `HD Ticket` DocType currently has a `raised_by` Data field with Email options and permission level 7. This is already a requester-email-shaped field, but the authenticated API populates it with the session user. Its use in notification routing, permissions, inbound email association and other lifecycle code must be traced before deciding whether it is sufficient for verified anonymous requesters.

**Implication:** do not expose the existing `api.new` method to guests or merely allow guests on the current Studio page. Its current assumptions are authenticated-session assumptions. Implement a narrowly scoped guest submission service that sets requester identity and privileged ticket fields server-side, then creates a native ticket through the normal controller lifecycle.

### Existing permission and hook boundaries

The app registers:

- `permission_query_conditions["HD Ticket"]` and `has_permission["HD Ticket"]` to enforce ticket access.
- `doc_events["HD Ticket"]` hooks for CBSUA office routing defaults and validation.
- Studio boot and website-context hooks for the portal shell.
- Redirects from legacy `/helpdesk` customer portal paths to `/help`.

These hooks and native permission checks must remain intact. Do not bypass them with `ignore_permissions=True` for normal ticket creation or introduce broad Guest DocType Create/Read permissions.

## 4. Anonymous ticket implementation implications

1. Add a separate guest-accessible Studio page under the existing Studio app; do not replace the authenticated `new_ticket` page.
2. Reuse existing portal design patterns and Frappe UI components. Prefer a guest-specific component or an explicitly designed guest mode over changing authenticated form assumptions implicitly.
3. Build a guest-only server API with strict allowlisted input fields, explicit POST method, type validation, rate limiting, safe error responses and idempotent verification handling.
4. Do not expose the normal `HD Ticket` DocType directly to Guest permissions.
5. Email verification is implemented as the prerequisite for ticket creation. The current design sends a six-digit OTP to the submitted address and accepts it through an inline POST from `/help/guest/new`; the 10-minute challenge is bound to the pending submission by an HMAC digest. Enforce attempt/resend limits, preserve idempotent retry, and never treat an unverified email string as proof of requester ownership. This supersedes the earlier 30-minute bearer-link description.
6. Inspect upload handling separately. The existing form uploads private files through an authenticated flow; do not enable guest uploads by changing a generic upload permission. The MVP may exclude attachments until a safe guest upload-and-attach lifecycle is designed.
7. Keep anonymous ticket updates in the existing Helpdesk notification lifecycle, but verify that only requester-visible content is emailed. Do not expose internal comments, private attachments, agent-only fields or ticket details through a public endpoint.
8. Do not add a public ticket list/detail route. Anonymous requesters receive updates through email.
9. Render guest OTP mail from dedicated Helpdesk-owned HTML and plain-text Jinja templates. The current inline OTP flow has no verification URL; keep requester descriptions and sensitive details out of verification email.
10. Future account association must be an explicit, auditable identity-linking process for verified email addresses, not automatic matching on an arbitrary string.

## 5. Development and verification workflow

### Framework / Studio

Consult the Studio-specific instructions in the actual framework checkout:

- `studio/frontend/README.md` in `cbsua-app-frappe` for Studio frontend dev server, exported apps, and `watch-studio`.
- The Studio App building skill is currently available in upstream Frappe at `frappe/frappe/skills/studio-app-building/` (the checked CBSUA framework fork did not contain a copy at that path). Read `SKILL.md`, `RULES.md`, `ROUTING.md`, and `DESIGN.md` before editing Studio pages, bindings, navigation, or styling.
- The skill can be installed from the upstream Frappe repository's `develop/skills/studio-app-building` path.

The Helpdesk portal README documents using `/dev/help` during development, running the Studio watcher, and building the production bundle after development. Follow the exact instructions for the checked-out framework version.

### Frappe app development

The official `frappe-app-dev` skill requires using Pilot for Frappe development, explicitly targeting the site for commands, testing in the correct compatible framework bench, and scanning changed files with Frappe Semgrep rules. Follow the installed version of the skill and the repository's local testing instructions.

The official `frappe-code-review` skill emphasizes correctness/atomicity, strict guest trust boundaries, typed inputs, permission checks, race conditions, least privilege, supported extension points and backward compatibility.

The LUBUS `api-development`, `frontend-development`, `web-forms`, `doctype-development`, and `testing` skills are useful supplementary references. They do not override the actual Studio architecture or repository-specific conventions. In particular, a generic Frappe Web Form is not the default recommendation for this feature because the customer portal is already implemented as a Studio App.

## 6. Repository facts to re-verify at implementation time

- [ ] Framework branch/commit and exact Studio version used by Helpdesk.
- [ ] `frappe-ui` submodule URL and gitlink SHA on this feature branch; verify whether it points to the CBSUA fork.
- [ ] Deployment source-lock SHA for framework, Helpdesk, UI submodule and required apps.
- [ ] Exact `ROUTES` source file path and route helper conventions.
- [ ] Existing requester-email use across ticket controller, notification templates, inbound email, contact/customer association and ticket permissions.
- [ ] Exact guest-safe office/request-type API behavior and whether those APIs are intentionally public.
- [ ] Upload API permissions and private file lifecycle.
- [ ] Current tests covering portal ticket creation, customer visibility, notifications and email replies.


## 7. Detailed ticket lifecycle findings from the Phase 0 trace

The following behavior was verified in the current feature branch's tracked source. It narrows the design but does not yet complete the audit of outbound/inbound email processing.

### Ticket creation API

Source: `helpdesk/helpdesk/doctype/hd_ticket/api.py`, function `new`.

- Decorated with `@frappe.whitelist()` and no `allow_guest=True`.
- Existing rate limit is 300 requests per 60 seconds, user-based. This is an authenticated-user-oriented limit and is not an appropriate anonymous abuse control.
- It accepts a document dictionary, attachment File references, and optional portal origin.
- It sets `doctype = "HD Ticket"`, `via_customer_portal` from the session, and `raised_by` from `frappe.session.user`.
- It inserts the native document and strips hidden fields for the response.

**Design consequence:** leave this method authenticated. Add a separate guest-only submission entry point rather than widening the existing method's trust boundary. The guest entry point should not accept arbitrary DocType fields or arbitrary File names.

### HD Ticket controller lifecycle

Source: `helpdesk/helpdesk/doctype/hd_ticket/hd_ticket.py`.

- `before_validate` calls `set_raised_by`, `validate_portal_contact`, `set_contact`, `set_customer`, and ticket-origin handling.
- `set_raised_by` falls back to `frappe.session.user` only when the field is empty.
- `set_contact` attempts to find a Contact whose `email_id` matches the email parsed from `raised_by`.
- `validate_portal_contact` restricts non-agent users from attributing a ticket to another Contact. A guest flow must not accept a client-selected Contact or impersonate an existing Contact owner.
- `set_customer` may derive an HD Customer from the matched Contact when the setting `auto_set_customer_from_contact` is enabled.
- `after_insert` creates a Communication from the description and sends the acknowledgement email only when `via_customer_portal` is false (and acknowledgement is enabled). The existing portal form therefore does not rely on that acknowledgement path.
- The controller generates a UUID `key`; inspect every use before treating it as a guest access credential. It is currently also used by email feedback flow.

**Design consequence:** a verified external email can potentially be represented by the existing `raised_by` field, but Contact/customer auto-association must be explicitly constrained. Do not attach an anonymous ticket to a Contact merely because the submitted email string matches a record linked to a different user. Preserve the native lifecycle and add only the smallest safe integration needed.

### CBSUA office routing

Source: `helpdesk/setup/office_routing.py`, registered from `helpdesk/hooks.py` as HD Ticket `before_validate` and `validate` events.

- `set_ticket_defaults` supplies a default office.
- It supplies a default request type for tickets where `via_customer_portal` is false.
- `validate_ticket_office_routing` requires a valid enabled office and request type for new tickets.
- The request type can supply the default team, with team-to-office consistency checked.
- Non-privileged users cannot select a team not mapped to the selected office.

**Design consequence:** guest tickets need the same required office/request-type values and validation as customer-portal tickets. The guest service must set the server-controlled portal-origin flag deliberately and must not trust a submitted team or agent. Confirm how this flag interacts with all existing controller behavior before choosing its exact value.

### Existing frontend form

Source: `studio/helpdesk/studio_page/new_ticket/new_ticket.json`, its TypeScript setup, and `studio/helpdesk/components/ticket/NewTicketForm.vue`.

- The page is not guest-enabled.
- The form loads the ticket template and dynamic fields.
- The CBSUA form additionally loads offices and request types.
- It uses authenticated file upload and then passes File names to the ticket creation API.
- It calls the existing authenticated API directly.

**Design consequence:** reuse the visual/form conventions and office/request-type interaction, but do not assume the current upload flow works for guests. For the first MVP, excluding attachments is safer than weakening generic upload permissions. If attachments are required in the first release, design a guest-scoped upload lifecycle with ownership, expiry, size/type restrictions, and safe association after verification.

### Email communication status

The controller's agent reply method defaults its recipient to `raised_by`, creates a linked Communication, and can send a threaded email through the configured outgoing account. Its email body/template path is aware of `via_customer_portal`.

The initial trace has **not yet established** all of the following:

- whether inbound email replies are enabled and how they identify the ticket;
- how sender addresses are validated against the ticket requester;
- which inbound messages become public Communications versus internal comments;
- which status-change notifications are sent to external requester addresses;
- whether every outbound template is safe for an anonymous external requester.

These are open Phase 0 items. Do not claim inbound email replies are supported for anonymous tickets until they are verified end-to-end.



### Customer notification and inbound email trace

Additional sources inspected: the latter sections of `hd_ticket.py`, `helpdesk/overrides/email_account.py`, and the ticket permission helpers in `hd_ticket.py`.

- `HDTicket.notify_customers()` calls `ping_customers()`.
- `get_customers_to_notify()` starts with `raised_by`, owner, contact and customer managers, but then resolves those candidates against enabled Frappe `User` records. An arbitrary external email string with no User record is therefore not an email-notification recipient in this realtime path.
- Ticket updates publish realtime events and user-scoped notifications; that is not equivalent to sending email to an anonymous requester.
- `send_acknowledgement_email()` sends to `raised_by`, but `after_insert()` invokes it only when `via_customer_portal` is false. The authenticated portal sets this flag true, so a guest portal submission following the same path would also skip the normal acknowledgement.
- Agent replies can send email to `raised_by` by default through `reply_via_agent()`, subject to the existing Helpdesk email settings and configured outgoing account. This path should be validated with a real test account and template.
- The custom inbound Email Account override extends Frappe's Message-ID/References thread matching. Incoming Communications linked to a ticket cause `on_communication_update()` to update customer-response timestamps and reopen the ticket where appropriate.

**Important open security question:** the trace confirms thread matching, but does not establish that an inbound message's From address is required to match the ticket's verified requester email before it is accepted as a customer reply. Do not claim sender ownership is validated merely because a message is attached to the ticket thread. Inspect Frappe's Communication/Email receive path and add an explicit policy/test if anonymous email replies are included.

**Design consequence for the MVP:** an anonymous ticket needs a deliberate requester email confirmation path, because the native portal acknowledgement is skipped and user-scoped realtime notifications cannot reach an email-only requester. Do not assume all ticket status changes currently produce requester emails. Define a minimal email event policy (submission confirmation, public agent reply, and any specifically required status transitions) and implement it using Helpdesk's existing email/template facilities where appropriate. Internal comments must never trigger requester mail.

### Ticket permission and broad Guest permission hazard

The ticket controller's custom `has_permission(doc, user)` grants direct customer visibility when the user matches `doc.contact`, `doc.raised_by`, or `doc.owner`, with additional customer-manager and agent checks. The list permission query similarly scopes customer rows to the current user's direct associations and managed customers. An anonymous email string is not itself a Frappe User identity, so do not assume these existing authenticated customer permissions automatically grant safe anonymous access.

The same controller file also defines `set_guest_ticket_creation_permission()`, which programmatically grants the Guest role permission-level-zero read, write and create permissions on `HD Ticket`. A corresponding removal helper exists. The current source inspection has not established that the grant helper is invoked in the installed app lifecycle; verify its call sites and the effective site permissions before changing anything.

**Non-negotiable:** do not invoke this broad Guest permission helper to implement the feature. Guest users must not receive general ticket read/write access. Use a narrow guest submission service that creates tickets server-side, and leave normal ticket read/list APIs protected.


### Critical edge case: existing Contact matches

The controller's `before_validate()` sequence is:

1. `validate_portal_contact()`
2. `set_contact()`
3. `set_customer()`

The `set_contact()` method looks up a Contact by the email in `raised_by` and assigns it when found. For a normal non-agent session, `validate_portal_contact()` only permits a Contact equal to the session user's own Contact. A Guest session has no authenticated user-owned Contact, so an anonymous submission using an email that already belongs to a Contact can be rejected by the normal controller validation. If this were bypassed carelessly, `set_customer()` could also associate the request with an existing HD Customer.

This is a real lifecycle interaction, not merely a theoretical concern.

**Resolution in the current implementation:** the guest submission service sets a transient server-side `anonymous_submission` flag only after successful email OTP verification. The registered `AnonymousHDTicketMixin` skips Contact ownership validation and Contact/Customer auto-association only for that server-created document, while preserving the normal controller behavior for every other ticket. It also assigns a deterministic ticket key for idempotency. See [Implemented anonymous submission boundary](#8-implemented-anonymous-submission-boundary).

This is an application-level extension, not a framework fork change. The exact framework commit used by deployment must still be verified before release.

### Permission helper caution

The `HD Ticket` controller also contains a helper that can grant Guest read/write/create permission at permission level zero. The audit has not confirmed whether that helper is invoked anywhere in the installed app. Regardless, it is not an acceptable implementation path: it would broaden Guest's access to the entire ticket DocType rather than provide one controlled submission operation.


## 8. Implemented anonymous submission boundary

The initial implementation on `feat/anonymous-tickets` consists of:

- `helpdesk/anonymous_tickets.py`: guest options, pending OTP challenge, OTP verification/resend, and native ticket creation.
- `helpdesk/extends/anonymous_ticket.py`: a narrow `HDTicket` mixin that skips Contact ownership checks and Contact/Customer auto-association only when the server sets the transient verified-submission flag.
- `helpdesk/hooks.py`: registers the mixin with `extend_doctype_class`.
- `studio/helpdesk/studio_page/guest_new_ticket/`: a guest-enabled Studio page at `/help/guest/new`.
- `studio/helpdesk/components/ticket/PortalPortalGuestTicketSubmission.vue`: the guest form and verification confirmation state.
- `shared/src/portalRoutes.ts`: the `guestTicket` route.
- `studio/helpdesk/studio_page/public_kb/public_kb.json`: public entry point to the guest form.

The framework hook was confirmed in the CBSUA Frappe fork's current `develop` source: `frappe/model/document.py` resolves `extend_doctype_class` after the base/override controller and composes the extension mixin ahead of the native controller in the MRO. The Helpdesk app declares Frappe `>=17.0.0-dev,<18.0.0`, so this hook is available in the inspected framework line. Verify the exact framework commit in the deployment source lock before release.

The guest API accepts only email, optional name, subject, plain-text description, office, and request type. It does not accept a ticket DocType payload, contact/customer, agent group, assignment, priority, status, internal fields, or attachments. The pending payload is cached for 30 minutes; the emailed token is random, and only its digest is used as the cache key. Verification is serialized with a cache lock and uses a deterministic HD Ticket `key` to make retries return the already-created ticket.

The server inserts the native ticket through the existing controller with a narrow `ignore_permissions=True` operation. This does not grant the Guest role generic DocType permissions. The verified guest path explicitly sets `owner = Guest` and leaves `contact` and `customer` unset, even when the email matches a Contact or login name. The extension preserves the verified email even when a visitor is already signed in, rather than letting normal insert rules replace it with the current session user.

### Current limitations and validation gates

- Attachments are excluded until a separate guest upload ownership/expiry design exists.
- Agent replies use the native email path to `raised_by`; a guest-specific `HD Ticket.on_update` hook also emails a minimal status-only notice when the status changes, unless the Helpdesk email workflow is disabled. Test both paths with the configured outgoing account.
- The native portal acknowledgement is skipped for portal-origin tickets, so the guest service sends a fixed requester-safe acknowledgement without a ticket-detail URL. Agent replies keep the native workflow but omit the authenticated portal link for Guest-owned tickets.
- Realtime customer notifications resolve enabled Frappe Users; they do not deliver to email-only requesters. The guest-specific status email hook covers status changes only, not every field change or internal comment.
- Inbound email Message-ID/References threading exists, but sender-address ownership validation has not been confirmed. Anonymous inbound replies remain unsupported until audited and tested.
- The focused test module covers OTP digest/cache-key behavior, deterministic ticket keys, the unique-key DocType metadata, Guest and matching-email-user read isolation, server-owned anonymous insert flags, input normalization, invalid email, office/request-type consistency, malformed challenge/code values, and content limits. It also includes helper-level assertions for post-commit OTP mail configuration. It does not yet exercise the full verification transaction, OTP expiry/replay, concurrent requests, Contact-collision insertion, actual outbound email delivery, or authenticated regressions. Run `bench --site <site> run-tests --app helpdesk --module helpdesk.tests.test_anonymous_tickets` on a disposable Frappe v17-compatible site, then add those integration tests.
- The current environment did not run a Frappe bench, Studio build, Semgrep, or real email delivery. Source inspection alone is not release validation.


## 9. Guest entry point and private knowledge-base routing — revised 2026-11-19

### Observed pilot behavior

The guest Studio page is configured with `allow_guest: 1` and is registered at `/help/guest/new`, but pilot visitors are redirected to the Frappe login page when the knowledge base is private. The route metadata is therefore not sufficient to establish reachability: the application applies a global Guest-to-login policy before the page can be used.

Two relevant guards were identified:

- `helpdesk/helpdesk/hooks/studio_app.py` computes the boot setting `send_guest_to_login` for a Guest when `HD Settings.public_knowledge_base` is false.
- `studio/helpdesk/stores/session.ts` implements `sendGuestToLogin()`, which calls `signIn()` for a Guest whenever the public knowledge base is disabled.

The two layers must be considered together. Changing only the Studio page's `allow_guest` metadata or only one guard can leave the route inaccessible.

### Intended access policy

| Route / state | Guest | Authenticated user |
|---|---|---|
| Private KB: `/help` | Redirect to login | Existing portal behavior |
| Private KB: `/help/guest/new` | Allow guest submission | Allow according to page behavior |
| Private KB: `/help/my-tickets` | Keep protected / redirect to login | Allow |
| Private KB: `/help/tickets/new` | Keep protected / redirect to login | Allow |
| Public KB: `/help` | Browse KB; no authenticated ticket actions | Browse KB and retain ticket actions |
| Public KB: `/help/guest/new` | Allow guest submission | Allow according to page behavior |

The exception must be exact to the guest submission route. Do not turn off the private-KB redirect globally, and do not grant Guest read access to tickets or private articles.

### Login screen entry point

The shared `/login` page is planned as the generic CBSUA Helpdesk sign-in and ticket-entry page for both system users and customers/requesters. Keep the existing **Continue** and **Login with Email Link** actions, then place a clickable secondary text link immediately beneath them:

**Submit a ticket without logging in** → `/help/guest/new`

The CTA is now intended to appear on the shared CBSUA login page regardless of whether the visitor arrived from `/help`, another CBSUA page, or directly at `/login`. This supersedes the earlier Helpdesk-origin-only marker/Referer visibility rule. The previous conditional CTA implementation has been replaced with the shared-login behavior. The fixed local destination is a navigation affordance only; it does not authorize ticket creation or grant access to private KB pages or authenticated ticket routes.

Also replace the generic heading **“Sign In Welcome! Please sign in to continue”** with **“Welcome back to CBSUA Helpdesk”** (or a close approved equivalent), and use the CBSUA logo and favicon assets already present in the Helpdesk repository under `desk/src/assets/logos/` and `desk/public/cbsua/`. The exact website-accessible asset URLs must be verified. If the framework login template cannot safely load Helpdesk assets directly, copy the approved artwork into a clearly named Frappe public directory and document its source path/hash.

The shared page is part of the CBSUA platform experience, so confirm the deployment is not intended to host unrelated apps or independently branded tenants before applying CBSUA branding globally.

### Homepage action policy

Remove the current prominent anonymous-request action from the top of the public knowledge-base homepage. Guests viewing a public KB must not see authenticated-only `Raise a ticket` or `View my tickets` actions in the empty state. Authenticated users retain their normal actions. Preserve existing session capability flags rather than redefining Guests as authenticated.

### Cross-repository implementation boundary

- Helpdesk owns the route-specific guest access exception, Studio session guard, homepage conditional rendering and guest submission page.
- The framework fork may own a conditional login-template link if there is no supported Helpdesk-specific login extension point. The CBSUA login template is intentionally branded for this deployment and shows the guest ticket link on every login entry. Confirm that this deployment is not intended for unrelated independently branded tenants.
- The UI library has no identified responsibility for this change.
- The deployment repository owns source locks and pilot release integration.

The route exception and current conditional login CTA have source implementations, but remain unvalidated in a running browser. The generic CBSUA login-page redesign and shared-login CTA are a new planned follow-up; see [Planned shared CBSUA login-page experience](#planned-shared-cbsua-login-page-experience--revised-2026-11-23).

## Implemented shared CBSUA login-page experience — source only (2026-11-23)

The shared `/login` page now has source changes for both internal system users and customers/requesters:

- Keep **Continue** and **Login with Email Link** as the primary authentication actions.
- Add **Submit a ticket without logging in** as a clickable text link beneath the primary authentication actions. It navigates to the fixed local route `/help/guest/new`.
- Replace the generic sign-in welcome copy with **Welcome back to CBSUA Helpdesk**.
- Replace the login-page logo and favicon with the existing CBSUA brand assets. Frappe references the public paths under `/assets/helpdesk/desk/cbsua/`; the canonical source artwork is in `desk/public/cbsua/`.
- The link is visible on direct `/login` visits and Helpdesk-origin redirects. The old query marker and Referer gate have been removed; Helpdesk preserves `last_visited` and redirects to plain `/login`.

Implementation commits: Frappe login context `ca22bad01035014b33a6cb5b9b9277468187f028`, Frappe login template `3bea4a3b153e6805c284043c4332933a3e690bd3`, Helpdesk session redirect cleanup `a85fed011fd195e3bf763c72d936bbaa09b2ceab`.

**Status:** Implemented in source on the coordinated feature branches. Deployment source locks remain unchanged. Python tests, Frappe/Studio builds, asset delivery, browser behavior and login regression checks have not been run; do not treat this as runtime-validated.


## Guest submission HTTP 500 — email API compatibility correction (2026-11-23)

The guest submission endpoint queues the verification message using Frappe's supported email-template API: `frappe.sendmail(recipients=..., subject=..., template="guest_ticket_verification", args=context)`. The Frappe v17 fork's `frappe.email.sendmail` signature accepts `template` and `args`, internally calls `get_email_from_template`, and passes the rendered HTML and optional plain-text alternative to the queue builder. It does **not** accept a `text_content` keyword. Do not pass the output of `get_email_from_template` back to `frappe.sendmail` using a `text_content` argument. The previous implementation did so and caused a Python argument TypeError on guest submission. This is corrected in Helpdesk commit `34ef87ead0c95d1f9382e5bc10453acf510ac842`; regression test update is `26b84a3e7f5868253e761a08643def3ab46b7c4d`. Runtime validation remains outstanding.

## Guest email OTP verification architecture (2026-11-23)

The email-link challenge is superseded by an in-page email OTP challenge. `/help/guest/new` remains the only customer-facing page; no absolute site URL, public callback, or email-link routing is involved. `start_guest_submission` validates the allowlisted form payload, creates a random opaque challenge ID, generates a six-digit code with `secrets`, stores the pending payload plus HMAC digest in the site cache, and queues the OTP template. The digest is HMAC-SHA256 over challenge ID and code using Frappe's `get_encryption_key()` helper; plaintext OTP is passed only to the mail template and never returned by the API or logged.

Challenge lifetime is 10 minutes; maximum failed attempts is five; resend cooldown is 60 seconds and maximum resends is three. A resend rotates the digest and resets the attempt count, invalidating the old code. `verify_guest_submission(challenge_id, otp)` validates the format, compares digests with `hmac.compare_digest`, obtains a site-scoped distributed lock, revalidates the cached payload, and inserts the native HD Ticket with a deterministic idempotency key. Lock release and challenge deletion are registered against transaction completion so rollback does not consume the challenge. `resend_guest_submission_otp` uses the same challenge lock. No Guest DocType permissions are added. Treat cache/lock/mail failures as infrastructure failures, never as successful verification.

The design removes the localhost canonical-host problem but does not remove the requirement for functioning outbound email. Source implementation is committed; Pilot integration, real mail delivery, concurrency, rollback, abuse-limit and browser tests remain outstanding.

## Outbound email delivery behavior and OTP investigation (2026-11-23)

Frappe outbound email has two relevant delivery modes. In the CBSUA framework branch feat/ui/login, frappe.email.sendmail defaults to delayed=True: it creates an Email Queue record for the scheduled frappe.email.queue.flush task. When now=True is passed, Frappe still creates the queue record but registers its send operation with frappe.db.after_commit, so delivery is attempted immediately after the transaction commits. The framework registers frappe.email.queue.flush under scheduler_events["all"]; the queue flush skips when email is muted or suspend_email_queue=1, and selects eligible Not Sent / Partially Sent records older than 10 seconds.

The Login Link endpoint frappe.www.login.send_login_link passes now=True. The OTP start and resend endpoints now use the shared `_send_guest_otp_email()` helper, which also passes `now=True` and `redact_message_after_send=True`. Frappe still creates an Email Queue record and registers its send method after the database transaction commits. The source-level cause was a delivery-mode mismatch: OTP had relied on periodic delayed queue flushing, whereas Login Link used post-commit sending. This is a plausible explanation for the observed partial delivery, not a confirmed runtime diagnosis; Pilot Email Queue records and transport state must still be inspected. The OTP endpoint's success response currently indicates that Frappe accepted/queued the email, not that delivery completed.

The Helpdesk Email Account class override customizes inbound mail processing only; no outgoing send override was found. The likely fix is to align both OTP send paths with the Login Link's now=True behavior, with redact_message_after_send=True for OTP privacy, while retaining Email Queue visibility/retry. Keep queue health operationally monitored because now=True is not a bypass of the Email Queue or a guarantee of inbox delivery. See the Outbound OTP delivery correction in the current README for the diagnostic checklist and test plan.
