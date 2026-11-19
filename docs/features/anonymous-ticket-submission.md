# Anonymous ticket submission

> Status: implementation in progress on `feat/anonymous-tickets`. This document records the current guest-submission boundary; verify behavior against a migrated test site before release.

## User experience

- The public Helpdesk home page links to `/help/guest/new`.
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

The endpoints are explicitly guest-whitelisted and method-restricted. Submission and verification have IP-based rate limits. The pending record expires after 30 minutes. The email token is generated with `secrets.token_urlsafe`; only its SHA-256 digest is used in the cache key. The token is single-use, and a cache lock plus a deterministic native ticket key makes verification retries idempotent.

The public API does not accept arbitrary DocType dictionaries, ticket identifiers, contact/customer links, assignment, priority, status, internal visibility, or attachment references. The HD Ticket permission hook explicitly denies Guest reads, and its list query returns no rows for Guest, including tickets whose owner field is Guest. Office and request type are revalidated at verification time.

## Native ticket integration

`helpdesk.extends.anonymous_ticket.AnonymousHDTicketMixin` is registered through Frappe's `extend_doctype_class` hook. It bypasses Contact ownership validation and Contact/Customer auto-association only when the server-side verification method sets the transient `anonymous_submission` flag. The mixin also supplies the deterministic idempotency key. All ordinary ticket submissions continue through the original controller methods.

The guest service performs a narrowly scoped server-side `insert(ignore_permissions=True)`. This is not a Guest role permission grant: no generic `HD Ticket` create/read/write permission is added, and the authenticated `api.new`, ticket list, and ticket detail endpoints remain unchanged.

The native portal ticket lifecycle skips acknowledgement email. After verified creation, the service explicitly invokes the existing Helpdesk acknowledgement email. The existing agent reply method defaults its recipient to `raised_by`, so public agent replies can use the verified external address. A dedicated `HD Ticket.on_update` hook emails a minimal status-only notice when the ticket owner is `Guest` and the status changes; it respects the Helpdesk email-workflow skip setting.

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

## Remaining work before release

1. Run backend tests on a disposable Frappe v17-compatible bench and confirm the `extend_doctype_class` MRO on the deployed framework commit.
2. Test the guest flow end-to-end with a real outbound email account: start, verify, duplicate verification, expiry, and acknowledgement delivery.
3. Test a submitted email that already belongs to a Contact linked to another user; confirm the new ticket has no Contact or HD Customer association.
4. Test authenticated ticket creation, authenticated `/help/my-tickets`, ticket detail, and agent replies for regressions.
5. Audit inbound email sender matching before considering replies from the requester.
6. Run Frappe Semgrep on changed Python files and the Studio production build; inspect the public page as Guest and as an authenticated user.
7. Decide whether to add CAPTCHA or additional deployment-level abuse controls based on observed traffic. IP rate limiting is the current MVP baseline.

## Current limitations

- No attachments on guest submissions.
- No anonymous ticket list, detail, or public ticket lookup.
- No inbound email reply guarantee.
- No email delivery guarantee for every status transition; native realtime notifications remain user-based.
- No automatic account association. That remains a separate future feature requiring explicit identity proof and audit history.
