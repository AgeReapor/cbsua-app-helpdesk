"""Guest-only ticket submission with email ownership verification.

The pending payload is short-lived and stored in the site cache. A random
bearer token is emailed to the requester; only its SHA-256 digest is used as
the cache key. Successful verification creates one native HD Ticket.
"""

import hashlib
import html
import secrets
import uuid
from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import get_url, validate_email_address
from frappe.utils.jinja import get_email_from_template

from helpdesk.utils import CUSTOMER_PORTAL_ROOT

PENDING_TTL_SECONDS = 30 * 60
MAX_DESCRIPTION_LENGTH = 10_000
CACHE_PREFIX = "helpdesk:guest-ticket:"


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _cache_key(digest: str) -> str:
    return f"{CACHE_PREFIX}{digest}"


def _ticket_key(digest: str) -> str:
    # The native HD Ticket key doubles as a durable idempotency marker.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"cbsua-guest-ticket:{digest}"))


def _build_verification_url(token: str) -> str:
    query = urlencode({"verify": token})
    return get_url(
        f"{CUSTOMER_PORTAL_ROOT}/guest/new?{query}",
        allow_header_override=False,
    )


def _render_guest_verification_email(
    payload: dict, token: str
) -> tuple[str, str | None]:
    office_name = frappe.db.get_value("CB Office", payload["office"], "office_name")
    request_type_name = frappe.db.get_value(
        "CB Office Request Type", payload["request_type"], "request_type_name"
    )
    return get_email_from_template(
        "guest_ticket_verification",
        {
            "full_name": payload["full_name"],
            "subject": payload["subject"],
            "office": office_name or payload["office"],
            "request_type": request_type_name or payload["request_type"],
            "verify_url": _build_verification_url(token),
            "logo_url": get_url(
                "/assets/helpdesk/desk/cbsua/cbsua-logo-2400.png",
                allow_header_override=False,
            ),
            "expires_in_minutes": PENDING_TTL_SECONDS // 60,
        },
    )


def _release_verification_lock(lock) -> None:
    """Release a verification lock after the database transaction settles."""
    try:
        if lock.owned():
            lock.release()
    except Exception:
        # The lock has a finite lease; a Redis outage must not mask the request result.
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Guest ticket verification lock release failed",
        )


def _validate_submission(
    email: str,
    full_name: str,
    subject: str,
    description: str,
    office: str,
    request_type: str,
) -> dict:
    values = (email, full_name, subject, description, office, request_type)
    if not all(isinstance(value, str) for value in values):
        frappe.throw(_("Invalid submission data."), frappe.ValidationError)

    email = email.strip().lower()
    full_name = full_name.strip()
    subject = subject.strip()
    description = description.strip()

    if len(email) > 254:
        frappe.throw(_("Email address is too long."), frappe.ValidationError)
    validate_email_address(email, throw=True)
    if any(ord(character) < 32 for character in subject):
        frappe.throw(
            _("Subject contains unsupported control characters."),
            frappe.ValidationError,
        )
    if any(ord(character) < 32 for character in full_name):
        frappe.throw(
            _("Name contains unsupported control characters."),
            frappe.ValidationError,
        )
    if any(
        ord(character) < 32 and character not in "\n\r\t"
        for character in description
    ):
        frappe.throw(
            _("Description contains unsupported control characters."),
            frappe.ValidationError,
        )
    if len(full_name) > 140:
        frappe.throw(_("Name must be 140 characters or fewer."))
    if not subject or len(subject) > 140:
        frappe.throw(_("Subject is required and must be 140 characters or fewer."))
    if not description or len(description) > MAX_DESCRIPTION_LENGTH:
        frappe.throw(
            _("Description is required and must be 10,000 characters or fewer.")
        )
    if not frappe.db.exists("CB Office", {"name": office, "enabled": 1}):
        frappe.throw(_("Select an available office."))
    if not frappe.db.exists(
        "CB Office Request Type",
        {"name": request_type, "office": office, "enabled": 1},
    ):
        frappe.throw(_("Select a request type available for that office."))

    return {
        "email": email,
        "full_name": full_name,
        "subject": subject,
        # The guest form accepts plain text only; the ticket HTML is escaped at insert.
        "description": description,
        "office": office,
        "request_type": request_type,
    }


@frappe.whitelist(allow_guest=True, methods=["POST"])
def get_guest_form_options() -> dict:
    """Public, read-only options needed by the guest form; no ticket data."""
    # These enabled routing choices are intentionally public; Guest has no
    # general read permission on either configuration DocType.
    offices = frappe.get_all(
        "CB Office",
        filters={"enabled": 1},
        fields=["name", "office_name", "is_default"],
        order_by="is_default desc, office_name asc",
    )
    request_types = frappe.get_all(
        "CB Office Request Type",
        filters={"enabled": 1, "office": ["in", [row.name for row in offices]]},
        fields=["name", "office", "request_type_name"],
        order_by="display_order asc, request_type_name asc",
    ) if offices else []
    return {"offices": offices, "request_types": request_types}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=60, user_based=False)
def start_guest_submission(
    email: str,
    subject: str,
    description: str,
    office: str,
    request_type: str,
    full_name: str = "",
) -> dict:
    """Email a one-time verification link; does not create a ticket."""
    payload = _validate_submission(
        email, full_name, subject, description, office, request_type
    )
    token = secrets.token_urlsafe(32)
    digest = _token_digest(token)
    frappe.cache.set_value(
        _cache_key(digest), payload, expires_in_sec=PENDING_TTL_SECONDS
    )

    message, text_content = _render_guest_verification_email(payload, token)
    try:
        frappe.sendmail(
            recipients=[payload["email"]],
            subject=_("Verify your email | CBSUA Helpdesk"),
            message=message,
            text_content=text_content,
        )
    except Exception:
        frappe.cache.delete_value(_cache_key(digest))
        raise
    return {
        "message": _("If the request is valid, a verification email has been sent.")
    }


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=60, user_based=False)
def verify_guest_submission(token: str) -> dict:
    """Verify the email bearer token and create exactly one native HD Ticket."""
    if not isinstance(token, str) or len(token) < 32 or len(token) > 128:
        return {"success": False, "code": "invalid_or_expired"}

    digest = _token_digest(token)
    key = _ticket_key(digest)
    existing = frappe.db.get_value("HD Ticket", {"key": key}, "name")
    if existing:
        return {"success": True, "ticket": existing}

    cache_key = _cache_key(digest)
    lock_name = f"{frappe.local.site}:{cache_key}:verify-lock"
    try:
        lock = frappe.cache.lock(lock_name, timeout=300, blocking_timeout=15)
        acquired = lock.acquire()
    except Exception:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Guest ticket verification lock unavailable",
        )
        return {"success": False, "code": "temporarily_unavailable"}

    if not acquired:
        return {"success": False, "code": "processing"}

    # Keep the distributed lock until the database transaction settles. Releasing
    # it when this function returns is too early: Frappe commits the request only
    # after the whitelisted method returns, allowing a concurrent request to see
    # neither the first ticket nor its cache cleanup and create a duplicate.
    frappe.db.after_commit.add(lambda: _release_verification_lock(lock))
    frappe.db.after_rollback.add(lambda: _release_verification_lock(lock))

    existing = frappe.db.get_value("HD Ticket", {"key": key}, "name")
    if existing:
        return {"success": True, "ticket": existing}

    try:
        payload = frappe.cache.get_value(cache_key)
    except Exception:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Guest ticket verification cache unavailable",
        )
        return {"success": False, "code": "temporarily_unavailable"}

    if not isinstance(payload, dict):
        return {"success": False, "code": "invalid_or_expired"}

    # Recheck routing at verification time; an office/type may have been disabled.
    payload = _validate_submission(
        payload["email"],
        payload.get("full_name", ""),
        payload["subject"],
        payload["description"],
        payload["office"],
        payload["request_type"],
    )

    description_html = html.escape(payload["description"]).replace("\n", "<br>")

    ticket = frappe.get_doc(
        {
            "doctype": "HD Ticket",
            "subject": payload["subject"],
            "description": description_html,
            "raised_by": payload["email"],
            "via_customer_portal": 1,
            "office": payload["office"],
            "request_type": payload["request_type"],
        }
    )
    ticket.flags.anonymous_submission = True
    ticket.flags.anonymous_requester_name = payload["full_name"]
    ticket.flags.anonymous_ticket_key = key
    # This is a narrow server-side insert. Guest receives no DocType permission.
    ticket.insert(ignore_permissions=True)

    # The native portal lifecycle skips its acknowledgement email. Send a
    # guest-safe acknowledgement without an authenticated portal link.
    if (
        not frappe.flags.initial_sync
        and frappe.db.get_single_value("HD Settings", "send_acknowledgement_email")
    ):
        send_guest_acknowledgement_email(ticket)
    # Keep the pending payload retryable if the DB transaction rolls back.
    frappe.db.after_commit.add(lambda: frappe.cache.delete_value(cache_key))
    return {"success": True, "ticket": ticket.name}


def notify_anonymous_requester_status(doc, method=None) -> None:
    """Email a minimal, requester-safe notice when an agent changes ticket status."""
    if (
        doc.owner != "Guest"
        or not doc.via_customer_portal
        or not doc.raised_by
        or not doc.has_value_changed("status")
        or doc.skip_email_workflow()
    ):
        return

    status = frappe.db.get_value(
        "HD Ticket Status",
        doc.status,
        ["label_agent", "label_customer", "different_view"],
        as_dict=True,
    )
    status_label = (
        status.label_customer
        if status and status.different_view and status.label_customer
        else status.label_agent if status else doc.status
    )
    message = (
        f"<p>{_('Your CBSUA Helpdesk request has a status update.')}</p>"
        f"<p><strong>{_('Ticket')}:</strong> {html.escape(doc.name)}</p>"
        f"<p><strong>{_('Subject')}:</strong> {html.escape(doc.subject or '')}</p>"
        f"<p><strong>{_('Status')}:</strong> {html.escape(status_label or '')}</p>"
    )
    try:
        sender_email = doc.sender_email()
        if not sender_email:
            return
        last_communication = doc._last_threadable_communication()
        in_reply_to = (
            frappe.db.get_value("Communication", last_communication, "message_id")
            if last_communication
            else None
        )
        frappe.sendmail(
            recipients=[doc.raised_by],
            sender=sender_email.email_id,
            subject=_("Ticket #{0}: status update").format(doc.name),
            message=message,
            reference_doctype="HD Ticket",
            reference_name=doc.name,
            in_reply_to=in_reply_to,
            email_headers={"X-Auto-Generated": "hd-anonymous-status-update"},
        )
    except Exception:
        frappe.log_error(
            title="Anonymous ticket status email failed",
            message=f"Could not queue a status email for HD Ticket {doc.name}.",
        )



def send_guest_acknowledgement_email(ticket) -> None:
    """Send a requester-safe acknowledgement without an authenticated portal link."""
    message = (
        f"<p>{_('Thank you for contacting CBSUA Helpdesk. We have received your request.')}</p>"
        f"<p><strong>{_('Ticket reference')}:</strong> {html.escape(ticket.name)}</p>"
        f"<p><strong>{_('Subject')}:</strong> {html.escape(ticket.subject or '')}</p>"
        f"<p>{_('Our team will review your request and contact you using this email address.')}</p>"
        f"<p>{_('Keep this reference for future correspondence. Anonymous requests cannot be viewed in the ticket portal.')}</p>"
    )
    frappe.sendmail(
        recipients=[ticket.raised_by],
        subject=_("Ticket #{0}: We've received your request").format(ticket.name),
        message=message,
        reference_doctype="HD Ticket",
        reference_name=ticket.name,
        now=ticket.instantly_send_email(),
        expose_recipients="header",
        email_headers={"X-Auto-Generated": "hd-acknowledgement"},
    )
