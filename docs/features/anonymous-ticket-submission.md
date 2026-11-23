# Anonymous ticket submission

> Status: source implementation in progress on `feat/anonymous-tickets`, with a coordinated Frappe login-template branch. Backend, guest route exception, login CTA, and KB homepage cleanup are committed in source; verify behavior against a migrated test site before release.

## User experience

- The shared CBSUA Frappe `/login` page displays **Welcome back to CBSUA Helpdesk**, the CBSUA logo/favicon, and **Submit a ticket without logging in** as a clickable text link beneath the primary authentication actions. It is available on direct login visits and Helpdesk-origin redirects and always navigates to `/help/guest/new`. The earlier prominent homepage CTA has been removed.
- A visitor submits an optional name, email address, office, request type, subject and plain-text description.
- Attachments are intentionally unavailable in this first implementation. The existing upload path is authenticated and must not be opened to Guest.
- The server emails a six-digit OTP using the CBSUA-branded HTML and plain-text templates. The email contains a minimal request summary (subject, office and request type), the 10-minute expiry, and no verification URL or request description. The customer enters the code inline on the same page; no ticket is created before the email is verified. See **Email OTP verification (current implementation)** below for the authoritative API and security details.
- After successful inline OTP verification, the guest form creates a native `HD Ticket` and displays its reference. Follow-up updates are sent to the submitted email address through Helpdesk's existing agent-reply email path.
- Anonymous users do not receive ticket list, detail, update, or lookup endpoints.

## Backend boundary

The guest endpoints live in `helpdesk/anonymous_tickets.py`:

| Method | Purpose |
|---|---|
| `get_guest_form_options` | Return enabled offices and request types only |
| `start_guest_submission` | Validate allowlisted fields, cache a short-lived pending request, and send verification email |
| `verify_guest_submission(challenge_id, otp)` | Verify the challenge-bound OTP and create one native ticket |

The endpoints are explicitly guest-whitelisted and method-restricted. Submission and verification have IP-based rate limits. The current pending record is an OTP challenge that expires after 10 minutes. The six-digit code is generated with `secrets`, and only a challenge-bound HMAC digest is cached. The customer enters the code on the same page; there is no link to open and no scanner-prefetch behavior. Successful verification can create only one ticket; retries after a successful commit return that same ticket reference. See the current Email OTP section below. The verification URL is built from the configured site hostname with Host-header overrides disabled and the token is URL-encoded. A site-scoped Redis lock is held until the surrounding database transaction commits or rolls back, preventing a second request from racing the first request's uncommitted insert. The deterministic native ticket key is also backed by a `unique` constraint added to the `HD Ticket.key` DocType field as a final database concurrency guard. This changes the schema on migration; verify existing key values contain no duplicates and confirm index creation on a representative copy before release.

The public API does not accept arbitrary DocType dictionaries, ticket identifiers, contact/customer links, assignment, priority, status, internal visibility, or attachment references. The HD Ticket permission hook explicitly denies Guest reads and excludes Guest-owned tickets from non-agent read/list access, including the edge case where a registered user's login name matches the submitted email address. Agents still use the normal team/assignment visibility checks. Office and request type are revalidated at verification time.

## Native ticket integration

`helpdesk.extends.anonymous_ticket.AnonymousHDTicketMixin` is registered through Frappe's `extend_doctype_class` hook. It bypasses Contact ownership validation and Contact/Customer auto-association only when the server-side verification method sets the transient `anonymous_submission` flag. The mixin also supplies the deterministic idempotency key. All ordinary ticket submissions continue through the original controller methods.

The guest service performs a narrowly scoped server-side `insert(ignore_permissions=True)`. This is not a Guest role permission grant: no generic `HD Ticket` create/read/write permission is added, and the authenticated `api.new`, ticket list, and ticket detail endpoints remain unchanged.

The native portal ticket lifecycle skips acknowledgement email. After verified creation, the service sends a guest-specific acknowledgement using a fixed requester-safe message with no ticket-detail URL; it respects the acknowledgement setting. The configurable authenticated acknowledgement template is intentionally not reused because it may contain a portal link that Guest requesters cannot open. The HD Ticket mixin preserves the native agent reply method and recipient default (`raised_by`), but temporarily disables its customer-portal template branch for Guest-owned tickets. The public reply body is still emailed through the native path without an authenticated ticket-detail link. A dedicated `HD Ticket.on_update` hook emails a minimal status-only notice when the ticket owner is `Guest` and the status changes; it respects the Helpdesk email-workflow skip setting.

### Verification email and failure handling

- Template: `helpdesk/templates/emails/guest_ticket_verification.html`, with a plain-text companion at `helpdesk/templates/emails/guest_ticket_verification.txt`.
- The backend selects both formats through Frappe's supported `frappe.sendmail(template="guest_ticket_verification", args=context)` interface. Frappe loads the matching HTML and optional plain-text templates internally; do not pass `text_content` directly because that keyword is not supported by this Frappe v17 fork. Dynamic values are HTML-escaped. The message shows CBSUA Helpdesk branding and only the request subject, office, and request type; it intentionally omits the full description.
- **Superseded:** the former absolute verification URL and canonical-host requirement were removed by the inline OTP implementation. The active flow does not generate or redirect to a verification URL.
- The OTP is entered explicitly in the guest form; there is no link to prefetch or consume. Ticket creation occurs only after the server verifies the code.
- Verification responses distinguish `invalid_or_expired`, `processing`, and `temporarily_unavailable`. The portal offers a retry for temporary failures and does not recommend creating a second request while the original outcome is uncertain.
- Cache/lock exceptions are logged server-side with traceback context but without logging the OTP or challenge secret. Ticket insertion failures are allowed to roll back normally.

## Privacy and security constraints

- Email verification is required before ticket creation.
- Contact and HD Customer associations are deliberately not inferred from an email match. A matching email does not prove ownership of an existing account or organization.
- No public ticket list/detail/lookup endpoint is added.
- No generic Guest DocType permission is granted.
- No Guest file upload is enabled.
- User-provided description text is treated as plain text and HTML-escaped when stored.
- Only the allowlisted office/request-type values are accepted and they are checked again when the token is consumed.
- The current OTP challenge expires after 10 minutes and cannot create more than one ticket. See the current Email OTP section below for attempt, resend and replay controls.
- Inbound email reply ownership validation has not been established. Do not advertise inbound email replies as a supported anonymous-ticket feature until the inbound sender identity path is audited and tested.
- Realtime customer notifications resolve Frappe User records; they do not provide delivery to email-only requesters. Do not claim that every status transition emails an anonymous requester.

## Current guest-entry status

The source changes now implement the revised flow:

- `helpdesk/helpdesk/hooks/studio_app.py` sets `send_guest_to_login` false only for the exact `/help/guest/new` request path when the KB is private.
- `studio/helpdesk/stores/session.ts` applies the same exact route exception to both its early boot redirect and its asynchronous session-load guard.
- Helpdesk `loginUrl()` preserves `last_visited` and now returns plain `/login`; the obsolete `helpdesk_guest=1` marker has been removed.
- The CBSUA Frappe fork's `frappe/www/login.py` sets the login logo and app name to CBSUA Helpdesk. `frappe/www/login.html` renders the fixed `/help/guest/new` text link, updates the welcome heading, and uses the existing CBSUA favicon and touch-icon assets. This framework change is isolated on `feat/anonymous-helpdesk-login-cta`.
- `public_kb.json` no longer contains the top-level anonymous CTA. The empty-state authenticated ticket action group is gated by `canCreateTicket`, exposed from `useKnowledgeBaseHeader()`.

These are source-level changes only. The private/public KB browser matrix, Referer behavior, login variants, Studio production build, and Frappe tests have not yet been run. See [the agent handoff](../current/HANDOFF.md) for commits and remaining validation.

## Remaining work before release

1. Run `bench --site <site> run-tests --app helpdesk --module helpdesk.tests.test_anonymous_tickets` on a disposable Frappe v17-compatible bench and confirm the `extend_doctype_class` MRO on the deployed framework commit.
2. Test the guest flow end-to-end with a real outbound email account: start, verify, duplicate verification, expiry, and acknowledgement delivery.
3. Test a submitted email that already belongs to a Contact linked to another user; confirm the new ticket has no Contact or HD Customer association.
4. Test authenticated ticket creation, authenticated `/help/my-tickets`, ticket detail, and agent replies for regressions.
5. Audit inbound email sender matching before considering replies from the requester.
6. Run Frappe Semgrep on changed Python files and the Studio production build; inspect the public page as Guest and as an authenticated user. The focused helper tests are in `helpdesk/tests/test_anonymous_tickets.py`; they do not replace end-to-end verification/replay/Contact-collision tests.
7. Decide whether to add CAPTCHA or additional deployment-level abuse controls based on observed traffic. IP rate limiting is the current MVP baseline.

## Deployment integration

The deployment repository currently documents `develop` as the canonical CBSUA Helpdesk build branch. This feature branch is therefore not included in the standard deployment image until it is merged or otherwise integrated into the configured build ref. Keep release/source-ref changes in `cbsua-app-helpdesk-deployment`; do not change deployment refs as part of this feature implementation without a coordinated release decision.

## Current limitations

- No attachments on guest submissions.
- No anonymous ticket list, detail, or public ticket lookup.
- No inbound email reply guarantee.
- No email delivery guarantee for every status transition; native realtime notifications remain user-based.
- No automatic account association. That remains a separate future feature requiring explicit identity proof and audit history.


## Implemented shared CBSUA login page

The shared Frappe `/login` page now has source changes to serve both internal system users and customers/requesters:

- Keep **Continue** and **Login with Email Link** as the primary authentication actions.
- Add **Submit a ticket without logging in** as a clickable text link immediately below the primary authentication actions. It navigates to the fixed local route `/help/guest/new`.
- Replace the generic welcome copy with **Welcome back to CBSUA Helpdesk**.
- Replace the login-page logo and favicon with the existing CBSUA brand assets. Frappe references the public paths under `/assets/helpdesk/desk/cbsua/`; the source artwork is in `desk/public/cbsua/`.

This supersedes the earlier Helpdesk-origin-only CTA proposal. The link is visible in the generic CBSUA `/login` template regardless of the page from which the visitor arrived. The old login-origin marker and Referer gate have been removed from source. The CTA remains navigation only and does not weaken the guest API or ticket permissions.

Implementation commits: Frappe context `ca22bad01035014b33a6cb5b9b9277468187f028`, Frappe template `3bea4a3b153e6805c284043c4332933a3e690bd3`, Helpdesk session cleanup `a85fed011fd195e3bf763c72d936bbaa09b2ceab`. The deployment source lock remains unchanged.

**Status: implemented in source; not yet build-, browser-, or runtime-validated.**


### Submission HTTP 500 compatibility fix (2026-11-23)

The pilot's guest form submission returned an Internal Server Error because the backend passed the unsupported `text_content` keyword to `frappe.sendmail`. The framework's `frappe.email.sendmail` API accepts `template` and `args`, and handles the paired HTML/plain-text templates internally. The endpoint now uses that API. Source commits: `34ef87ead0c95d1f9382e5bc10453acf510ac842` (backend) and `26b84a3e7f5868253e761a08643def3ab46b7c4d` (test update). This correction has not yet been confirmed against the live Pilot instance.

## Email OTP verification (current implementation, 2026-11-23)

**This section supersedes the earlier email-link verification instructions above.** The customer remains on `/help/guest/new` throughout submission and verification. After submitting the form, the backend emails a six-digit code; the page transitions to an inline code-entry state. The customer enters the code and selects **Verify and submit request**. No link, redirect, hostname, or second page is involved.

### API contract

| Endpoint | Purpose |
|---|---|
| `get_guest_form_options` | Return enabled office/request-type options only |
| `start_guest_submission` | Validate form data, create a pending OTP challenge, and send the code; returns an opaque `challenge_id` and expiry metadata |
| `verify_guest_submission(challenge_id, otp)` | Validate the code and create one native HD Ticket |
| `resend_guest_submission_otp(challenge_id)` | Rotate and resend the code subject to cooldown and resend limits |

### Challenge and abuse controls

- Six-digit numeric code generated with `secrets`; plaintext is only included in the outbound email template.
- Ten-minute challenge lifetime.
- HMAC-SHA256 digest bound to challenge ID and code, keyed by Frappe's `get_encryption_key()` helper. The cache stores the digest, not the OTP.
- Maximum five incorrect attempts. A failed attempt is counted and the API reports remaining attempts without exposing the expected value.
- Resend cooldown of 60 seconds and maximum three resends. Each resend rotates the digest, invalidating the previous code and resetting the failed-attempt counter.
- Submission, verification, and resend endpoints have IP-based rate limits. A site-scoped distributed lock serializes verification and resend for a challenge.
- A deterministic native HD Ticket key derived from the opaque challenge ID preserves idempotency after successful ticket creation. The lock is retained until the database transaction commits or rolls back; challenge cache cleanup occurs after commit.
- Email contains the code, expiry, and minimal request summary (subject, office, request type). It excludes the request description and contains no URL.
- Guest has no general HD Ticket read/create/write permission. Ticket insertion remains a narrowly scoped server-side operation after successful OTP verification.

### Runtime validation still required

Run `pilot frappe --site <disposable-site> run-tests --module helpdesk.tests.test_anonymous_tickets` (or the equivalent command supported by the checked-out Pilot/Frappe version), build the Studio frontend, and run Frappe Semgrep on changed Python files. Then test real email delivery, valid/invalid/expired OTP, five failed attempts, resend cooldown/limit and invalidation, concurrent verification, transaction rollback, cache outage, exactly-one-ticket idempotency, Guest permissions, and authenticated ticket regression. The GitHub source connector cannot run a Pilot bench or browser, so source commits alone are not runtime evidence.

## Outbound OTP delivery: implemented correction (2026-11-23)

The OTP start and resend endpoints now call the shared `_send_guest_otp_email()` helper. It uses the supported Frappe template interface, sets `now=True` to register the Email Queue send operation after transaction commit (matching the working Login Link endpoint), and sets `redact_message_after_send=True` to reduce retention of the OTP body after successful delivery. Both endpoints report that the email was queued; this is not a delivery receipt.

The source-level cause was a difference in delivery mode: OTP messages previously depended on the scheduled delayed queue flush, while Login Link uses post-commit sending. This plausibly explains the partial delivery symptom, but the live Pilot Email Queue and transport must still be inspected to confirm the runtime cause. `now=True` still uses Frappe's Email Queue and does not guarantee inbox placement.

### Implementation and test coverage

- A shared helper keeps recipient, template, subject, send timing, and message redaction consistent between initial OTP and resend.
- Focused tests assert the helper uses the correct recipient/template context, `now=True`, and `redact_message_after_send=True` for both initial and resend mail.
- The existing challenge security controls remain unchanged: HMAC digest, 10-minute expiry, five attempts, 60-second cooldown, three resends, and challenge rotation.
- Pilot validation remains required: verify Email Queue records and status, actual mailbox delivery, resend invalidation, SMTP failure/retry, and ordinary delayed email queue processing.


## Correct-OTP insertion failure: first-ticket tag permission (2026-11-23)

Pilot testing found that an incorrect OTP returned the expected invalid-code response, but a correct OTP produced a generic temporary-unavailable frontend message and no committed HD Ticket. The available Error Log entry was unrelated to this endpoint, and no verification-specific Error Log metadata was present.

Source tracing found that the native `HD Ticket.after_insert()` invokes `tag_first_ticket()`. The Helpdesk `add_tag()` override routes this through `helpdesk.api.tags.apply_tag()`, which ultimately invokes Frappe's `DocTags.update_tags()`. That framework method calls `doc.check_permission("write")`. The ticket's narrowly scoped `insert(ignore_permissions=True)` does not make this subsequent write check succeed for Guest, so first-ticket tagging can raise a permission exception and roll back ticket creation.

The anonymous-ticket mixin now overrides `tag_first_ticket()` to skip this cosmetic operation only when the server-set `anonymous_submission` flag is present. Other ticket submissions retain the native first-ticket tag. A focused regression test asserts that `apply_tag` is not called for the anonymous path. This keeps Guest permissions, ticket read isolation, and native ticket validation unchanged.

**Commits:** `0d3065d82bdd85369982dda21c983cf5c8004cbc` (implementation) and `ba0be55d2a997288b8a4cced8ded40257e3db33b` (regression test).

**Validation still required:** run `helpdesk.tests.test_anonymous_tickets` on a disposable Frappe v17-compatible bench; verify correct OTP creates exactly one HD Ticket in Pilot; retry the same challenge to confirm idempotency; confirm Guest cannot read or modify tickets; and confirm authenticated first-ticket tagging still works. The root cause is source-supported but not yet confirmed by a live endpoint traceback or post-patch Pilot test.


## Pilot end-to-end status and outbound tracking pixel (2026-11-23)

**Pilot confirmation:** with a fresh internet connection, anonymous ticket submission, OTP verification, native HD Ticket creation, and agent replies to the submitted customer email have been confirmed working end to end. This is no longer merely source-level implementation status for the tested Pilot environment.

The remaining visible email issue is an automatically appended image URL targeting Frappe's `mark_email_as_seen` endpoint on `cbsua-helpdesk.localhost`. This is the Email Queue open-tracking pixel, not an image embedded by the anonymous-ticket feature or the agent's reply content. In the CBSUA Frappe fork, `EmailQueue.get_tracker_str()` injects it when the outgoing Email Account's `track_email_status` setting is enabled and the message is linked to a Communication. Gmail's `googleusercontent.com` URL is an image proxy/rewrite; the original URL remains the local-only Frappe host.

To remove the pixel, disable **Track Email Status** on the outgoing Email Account used for agent replies; this affects all outgoing messages sent through that account. If email-open tracking is desired, instead configure the Frappe site's canonical public HTTPS hostname (`host_name` / site URL configuration), which makes the tracker URL externally accessible but retains the pixel. This is an Email Account/deployment configuration decision; do not modify the anonymous reply template to strip it.

**Follow-up validation:** apply the chosen Pilot configuration, send a new agent reply, and inspect the raw message source. Confirm either that no `mark_email_as_seen` image is emitted (tracking disabled) or that its URL uses the externally reachable HTTPS hostname (tracking retained).
