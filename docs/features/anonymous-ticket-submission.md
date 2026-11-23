# Anonymous ticket submission

Anonymous ticket submission provides a login-less way for a visitor to contact CBSUA Helpdesk while preserving the native Helpdesk ticket lifecycle and keeping ticket access restricted to authenticated agents.

## User experience

1. A visitor opens the shared CBSUA Frappe login page.
2. The page presents **Submit a ticket without logging in**, which navigates to `/help/guest/new`.
3. The guest form collects an optional name, email address, office, request type, subject, and plain-text description.
4. The server sends a six-digit one-time password (OTP) to the submitted email address.
5. The visitor enters the OTP on the same page. A ticket is not created until the email challenge is verified.
6. On success, the page displays the native Helpdesk ticket reference. Agents can reply through the normal Helpdesk workflow, and replies are sent to the guest's submitted email address.

The guest route is available even when the knowledge base is private. The route exception is limited to `/help/guest/new`; other private knowledge-base routes retain their normal login requirement. Authenticated visitors continue to use the existing ticket creation and ticket-list routes. The public knowledge-base homepage does not display a duplicate anonymous-submission call to action.

## Scope and limitations

- Guest submission creates a native `HD Ticket`; it does not create a Frappe User, Contact, or HD Customer.
- Attachments are not supported in the guest form.
- Anonymous visitors do not receive ticket list, detail, update, or public lookup endpoints.
- The submitted email address is used as the requester identity for outbound agent replies.
- Matching an existing Contact or customer email does not automatically associate the guest ticket with that account.
- Agent replies and the configured guest acknowledgement are email-based. Do not assume every ticket status transition produces an email unless the relevant notification behavior is separately configured and verified.
- Inbound email replies from the guest are not part of the supported contract until sender matching and ownership validation are audited and tested.

## Backend API

The guest service is implemented in `helpdesk/anonymous_tickets.py`.

| Method | Purpose |
|---|---|
| `get_guest_form_options` | Return enabled offices and request types suitable for guest submission |
| `start_guest_submission` | Validate the allowlisted request fields, create a pending OTP challenge, and send the verification email |
| `verify_guest_submission(challenge_id, otp)` | Verify the OTP and create one native ticket |
| `resend_guest_submission_otp(challenge_id)` | Rotate and resend the OTP subject to cooldown and resend limits |

The endpoints are explicitly guest-whitelisted and method-restricted. The server accepts only the supported form fields; callers cannot supply ticket ownership, customer/contact links, assignment, priority, status, internal visibility, or arbitrary DocType values. Office and request type are validated when the request starts and checked again when the challenge is consumed.

## OTP and abuse controls

- Six-digit numeric code generated with a cryptographically secure random generator.
- Ten-minute challenge lifetime.
- HMAC-SHA256 digest bound to the opaque challenge ID and keyed with the site's Frappe encryption key; the cache stores the digest rather than the plaintext OTP.
- Maximum five incorrect attempts.
- Sixty-second resend cooldown and a maximum of three resends. Resending rotates the code and invalidates the previous one.
- IP-based rate limits on submission, verification, and resend.
- Site-scoped distributed locking serializes verification and resend for a challenge.
- Deterministic ticket key derived from the opaque challenge ID, backed by a unique constraint, to prevent duplicate ticket creation on retries.
- Challenge cleanup occurs after transaction completion.
- Verification emails contain the OTP, expiry, and a minimal request summary (subject, office, and request type); they do not contain the request description or a verification URL.

## Native ticket integration and permissions

The feature extends the native `HD Ticket` controller through `helpdesk.extends.anonymous_ticket.AnonymousHDTicketMixin`, registered using Frappe's `extend_doctype_class` hook.

The mixin bypasses Contact ownership validation and Contact/Customer auto-association only when the server-side verification service sets the transient `anonymous_submission` flag. It also supplies the deterministic idempotency key. The anonymous service performs a narrowly scoped `insert(ignore_permissions=True)` after successful OTP verification. This is not a Guest role permission grant.

Guest has no general `HD Ticket` create, read, or write permission. Guest read/list access remains denied, including when a registered user's login name matches the submitted email address. Agents continue to use the normal team and assignment visibility rules. Authenticated ticket creation and customer ticket browsing retain their existing paths.

The native portal acknowledgement workflow is skipped for guest-owned tickets. The feature sends a guest-specific acknowledgement using a requester-safe message without a ticket-detail URL, respecting the Helpdesk acknowledgement setting. The native agent-reply method is retained, with the customer-portal template branch bypassed for guest-owned tickets so that the email does not include an authenticated portal link. A Helpdesk ticket update hook sends a minimal status notice when a guest-owned ticket's status changes, subject to the configured email-workflow skip behavior.

First-ticket tagging is skipped only for server-flagged anonymous submissions. Frappe's native tag-link update checks ticket write permission separately from the initial privileged insert; skipping this nonessential tag avoids granting Guest write access. Normal authenticated tickets retain native first-ticket tagging.

## Email behavior and local development

### OTP email

OTP email is sent using Frappe's supported template interface:

- HTML template: `helpdesk/templates/emails/guest_ticket_verification.html`
- Plain-text template: `helpdesk/templates/emails/guest_ticket_verification.txt`

The shared sender uses post-commit queueing (`now=True`) and message redaction after successful delivery. Queueing is not a delivery receipt; the outgoing Email Account and transport must still be configured correctly.

### Customer-facing agent replies

Customer-facing agent replies use the native Helpdesk communication and Email Queue workflow, but the default reply template is intentionally minimal:

```html
<div>
  {{ message }}
  <p>Regards,<br />CBSUA Support</p>
</div>
```

The customer receives the agent's reply followed by the generic **CBSUA Support** signature. The default message does not add a ticket heading, portal call-to-action, portal URL, logo, or tracking image. The communication remains linked to the native ticket so the agent workspace retains its normal conversation history.

A site-specific custom value in `HD Settings.reply_via_agent_email_content` can override the default. The email-presentation migration clears that field once so the generic template takes effect on existing sites.

### Email-open tracking policy

Frappe Email Queue injects an email-open tracking image when the selected outgoing Email Account has `track_email_status` enabled and the queued message is linked to a Communication. The image calls `frappe.core.doctype.communication.email.mark_email_as_seen`. On localhost, the generated URL can contain a hostname such as `cbsua-helpdesk.localhost`, which external recipients cannot resolve.

CBSUA Helpdesk now disables this behavior as an application policy:

- A post-model-sync patch turns off `track_email_status` for existing Email Accounts.
- A Helpdesk `Email Account.before_insert` hook turns it off for newly created accounts.
- The reply template itself contains no tracking pixel and does not remove or alter legitimate agent-supplied inline images.

This is intentionally an account-wide policy: email-open tracking is disabled for outgoing messages sent through CBSUA Helpdesk Email Accounts, not only anonymous-ticket replies. The communication record, message threading, attachments, delivery workflow, and agent-side history remain intact.

The permanent outbound email address/domain has not yet been finalized. When it is, the team can separately review whether email-open tracking is useful and intentionally reintroduce it with a publicly reachable HTTPS hostname. Do not re-enable it merely to fix a localhost URL.

## Frontend integration

- Login entry point: shared CBSUA Frappe `/login` page, with the anonymous-submission text link.
- Guest route: `/help/guest/new`, registered in `shared/src/portalRoutes.ts`.
- Guest Studio page: `studio/helpdesk/studio_page/guest_new_ticket/`.
- Submission component: `studio/helpdesk/components/ticket/PortalGuestTicketSubmission.vue`.
- Guest route access is exempted narrowly in the Studio session/redirect guards.
- The knowledge-base homepage hides authenticated-only ticket actions from Guest sessions.

The shared login page is maintained in the CBSUA Frappe fork, not in the Helpdesk repository. Coordinate changes to that page with the framework repository and its deployment source lock.

## Validation

The CBSUA Pilot workflow has been confirmed end to end by the project owner: anonymous form submission, OTP verification, native ticket creation, and agent reply email to the submitted requester address all worked when tested with a fresh internet connection.

For future changes, retain regression coverage for:

- valid, invalid, expired, and replayed OTP challenges;
- attempt limits, resend cooldown, resend limit, and code rotation;
- concurrent verification and idempotent retry behavior;
- cache/lock failures and transaction rollback;
- existing Contact email collisions without automatic account association;
- Guest ticket read/write isolation;
- authenticated ticket creation and normal first-ticket tagging;
- guest acknowledgement, agent reply, and status-notice email behavior;
- private/public knowledge-base routing and authenticated portal regressions.

Run the focused tests on a compatible Frappe v17 Pilot bench:

```bash
pilot frappe --site <site> run-tests --module helpdesk.tests.test_anonymous_tickets
pilot frappe --site <site> run-tests --module helpdesk.tests.test_email_presentation
```

The email-presentation test covers the minimal reply template, the new-account tracking policy, and the one-time migration. Confirm the migration on the Pilot site with `pilot frappe --site <site> migrate`, then send a fresh agent reply and inspect its raw email source: it should contain the reply and the **CBSUA Support** signature, with no `mark_email_as_seen` image. Also verify that a legitimate inline image supplied in an agent reply is still preserved.

Build the Studio frontend and verify the guest flow in a browser after changes to the page, routing, or session guards. Pilot end-to-end confirmation does not replace regression testing after subsequent code changes.

## Deployment

The Helpdesk feature branch is not included in the standard deployment image until its changes are integrated into the branch selected by `cbsua-app-helpdesk-deployment`. The deployment repository owns image source refs, image builds, migrations, release promotion, and rollback instructions. Update its source lock only as part of a coordinated release.

## Related documentation

- [CBSUA Office-Aware Helpdesk Architecture](../architecture/office-aware-helpdesk.md)
- [Office administration](../configuration/offices.md)
- [CBSUA Helpdesk branding](../ui/cbsua-branding.md)
- [CBSUA Helpdesk UI styling](../ui/cbsua-ui-styling.md)

## Current validation status

The project owner has confirmed in the CBSUA Pilot environment, using a fresh internet connection, that anonymous submission, OTP verification, native ticket creation, and agent reply delivery to the requester all work end to end. The customer-facing email presentation change described above is implemented in source but still requires a post-migration Pilot email test. Backend tests and frontend builds must be run on the compatible Frappe v17 bench before release.
