# Anonymous ticket submission

> Status: implementation in progress on `feat/anonymous-tickets`. This document records the current guest-submission boundary; verify behavior against a migrated test site before release.

## User experience

- The intended entry point is a Helpdesk-origin-only link on the Frappe login page, leading to `/help/guest/new`. The earlier prominent homepage CTA is superseded; the login CTA and private-KB route exception are still planned, not implemented.
- A visitor submits an optional name, email address, office, request type, subject and plain-text description.
- Attachments are intentionally unavailable in this first implementation. The existing upload path is authenticated and must not be opened to Guest.
- The server emails a single-use verification link. No ticket is created before the email is verified.
- The verification page creates a native `HD Ticket` and displays its reference. Follow-up updates are sent to the submitted email address through Helpdesk's existing agent-reply email path.
- Anonymous users do not receive ticket list, detail, update, or lookup endpoints.

## Backend boundary

The guest endpoints live in `helpdesk/anonymous_tickets.py`:

| Method | Purpose |
|---|---|
| `get_guest_form_options` | Return enabled offices and request types only |
| `start_guest_submission` | Validate allowlisted fields, cache a short-lived pending request, and send verification email |
| `verify_guest_submission` | Consume a verified token and create one native ticket |

The endpoints are explicitly guest-whitelisted and method-restricted. Submission and verification have IP-based rate limits. The pending record expires after 30 minutes. The email token is generated with `secrets.token_urlsafe`; only its SHA-256 digest is used in the cache key. Opening the link does not consume the token: the page requires an explicit confirmation click so mail-security link scanners do not automatically create tickets. The verification token can create only one ticket; retries after a successful commit return that same ticket reference. A site-scoped Redis lock is held until the surrounding database transaction commits or rolls back, preventing a second request from racing the first request's uncommitted insert. The deterministic native ticket key is also backed by a `unique` constraint added to the `HD Ticket.key` DocType field as a final database concurrency guard. This changes the schema on migration; verify existing key values contain no duplicates and confirm index creation on a representative copy before release.

The public API does not accept arbitrary DocType dictionaries, ticket identifiers, contact/customer links, assignment, priority, status, internal visibility, or attachment references. The HD Ticket permission hook explicitly denies Guest reads and excludes Guest-owned tickets from non-agent read/list access, including the edge case where a registered user's login name matches the submitted email address. Agents still use the normal team/assignment visibility checks. Office and request type are revalidated at verification time.

## Native ticket integration

`helpdesk.extends.anonymous_ticket.AnonymousHDTicketMixin` is registered through Frappe's `extend_doctype_class` hook. It bypasses Contact ownership validation and Contact/Customer auto-association only when the server-side verification method sets the transient `anonymous_submission` flag. The mixin also supplies the deterministic idempotency key. All ordinary ticket submissions continue through the original controller methods.

The guest service performs a narrowly scoped server-side `insert(ignore_permissions=True)`. This is not a Guest role permission grant: no generic `HD Ticket` create/read/write permission is added, and the authenticated `api.new`, ticket list, and ticket detail endpoints remain unchanged.

The native portal ticket lifecycle skips acknowledgement email. After verified creation, the service sends a guest-specific acknowledgement using a fixed requester-safe message with no ticket-detail URL; it respects the acknowledgement setting. The configurable authenticated acknowledgement template is intentionally not reused because it may contain a portal link that Guest requesters cannot open. The HD Ticket mixin preserves the native agent reply method and recipient default (`raised_by`), but temporarily disables its customer-portal template branch for Guest-owned tickets. The public reply body is still emailed through the native path without an authenticated ticket-detail link. A dedicated `HD Ticket.on_update` hook emails a minimal status-only notice when the ticket owner is `Guest` and the status changes; it respects the Helpdesk email-workflow skip setting.

## Privacy and security constraints

- Email verification is required before ticket creation.
- Contact and HD Customer associations are deliberately not inferred from an email match. A matching email does not prove ownership of an existing account or organization.
- No public ticket list/detail/lookup endpoint is added.
- No generic Guest DocType permission is granted.
- No Guest file upload is enabled.
- User-provided description text is treated as plain text and HTML-escaped when stored.
- Only the allowlisted office/request-type values are accepted and they are checked again when the token is consumed.
- The verification token expires after 30 minutes and cannot create more than one ticket.
- Inbound email reply ownership validation has not been established. Do not advertise inbound email replies as a supported anonymous-ticket feature until the inbound sender identity path is audited and tested.
- Realtime customer notifications resolve Frappe User records; they do not provide delivery to email-only requesters. Do not claim that every status transition emails an anonymous requester.

## Current guest-entry status\n\nThe guest Studio page and backend exist, but pilot testing found that private-KB Guest redirects prevent the route from being reached. The revised design places a secondary anonymous-request link beneath the login options only when login originated from Helpdesk. The route exception must be implemented in both `helpdesk/helpdesk/hooks/studio_app.py` and `studio/helpdesk/stores/session.ts`. The KB homepage must not show the anonymous CTA or authenticated-only ticket actions to Guests. See [the agent handoff](../current/HANDOFF.md) for the exact implementation and validation plan.\n\n## Remaining work before release

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
