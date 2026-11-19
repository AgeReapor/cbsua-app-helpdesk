"""Guest-only ticket submission with email ownership verification.

The pending payload is short-lived and stored in the site cache. A random
bearer token is emailed to the requester; only its SHA-256 digest is used as
the cache key. Successful verification creates one native HD Ticket.
"""

import hashlib
import html
import secrets
import uuid

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import get_url, validate_email_address

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


def _validate_submission(
    email: str,
    full_name: str,
    subject: str,
    description: str,
    office: str,
    request_type: str,
) -> dict:
    email = email.strip().lower()
    validate_email_address(email, throw=True)
    full_name = full_name.strip()
    subject = subject.strip()
    description = description.strip()

    if len(email) > 254:
        frappe.throw(_("Email address is too long."))
    if len(full_name) > 140:
        frappe.throw(_("Name must be 140 characters or fewer."))
    if not subject or len(subject) > 140:
        frappe.throw(_("Subject is required and must be 140 characters or fewer."))
    if not description or len(description) > MAX_DESCRIPTION_LENGTH:
        frappe.throw(_("Description is required and must be 10,000 characters or fewer."))
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

    verify_url = f"{get_url()}{CUSTOMER_PORTAL_ROOT}/guest/new?verify={token}"
    greeting = f"Hello {html.escape(payload['full_name'])}," if payload["full_name"] else "Hello,"
    frappe.sendmail(
        recipients=[payload["email"]],
        subject=_("Verify your CBSUA Helpdesk request"),
        message=(
            f"<p>{greeting}</p>"
            "<p>Someone submitted a helpdesk request using this email address. "
            "Confirm the address to create the ticket.</p>"
            f'<p><a href="{html.escape(verify_url, quote=True)}">Verify email and submit request</a></p>'
            f"<p>This link expires in 30 minutes. If you did not make this request, "
            "you can ignore this email.</p>"
        ),
    )
    return {"message": _("If the request is valid, a verification email has been sent.")}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=60, user_based=False)
def verify_guest_submission(token: str) -> dict:
    """Verify the email bearer token and create exactly one native HD Ticket."""
    if not isinstance(token, str) or len(token) < 32 or len(token) > 128:
        frappe.throw(_("This verification link is invalid or has expired."))

    digest = _token_digest(token)
    key = _ticket_key(digest)
    existing = frappe.db.get_value("HD Ticket", {"key": key}, "name")
    if existing:
        return {"success": True, "ticket": existing}

    cache_key = _cache_key(digest)
    with frappe.cache.lock(f"{frappe.local.site}:{cache_key}:verify-lock", timeout=300, blocking_timeout=15):
        # A concurrent request may have completed while this request waited.
        existing = frappe.db.get_value("HD Ticket", {"key": key}, "name")
        if existing:
            return {"success": True, "ticket": existing}

        payload = frappe.cache.get_value(cache_key)
        if not isinstance(payload, dict):
            frappe.throw(_("This verification link is invalid or has expired."))

        # Recheck routing at verification time; an office/type may have been disabled.
        payload = _validate_submission(
            payload["email"],
            payload.get("full_name", ""),
            payload["subject"],
            payload["description"],
            payload["office"],
            payload["request_type"],
        )

        ticket = frappe.get_doc(
            {
                "doctype": "HD Ticket",
                "subject": payload["subject"],
                "description": html.escape(payload["description"] + ("\n\nSubmitted by: " + payload["full_name"] if payload["full_name"] else "")).replace("\n", "<br>"),
                "raised_by": payload["email"],
                "via_customer_portal": 1,
                "office": payload["office"],
                "request_type": payload["request_type"],
            }
        )
        ticket.flags.anonymous_submission = True
        ticket.flags.anonymous_ticket_key = key
        # This is a narrow server-side insert. Guest receives no DocType permission.
        try:
            ticket.insert(ignore_permissions=True)
        except frappe.DuplicateEntryError:
            # The unique HD Ticket key is the final guard if two workers race.
            existing = frappe.db.get_value("HD Ticket", {"key": key}, "name")
            if existing:
                return {"success": True, "ticket": existing}
            raise

        # The native portal lifecycle skips its acknowledgement email. Send the
        # existing Helpdesk acknowledgement explicitly after verified creation.
        if frappe.db.get_single_value("HD Settings", "send_acknowledgement_email"):
            ticket.send_acknowledgement_email()
        frappe.cache.delete_value(cache_key)
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
        if not doc.sender_email():
            return
        frappe.sendmail(
            recipients=[doc.raised_by],
            subject=_("Ticket #{0}: status update").format(doc.name),
            message=message,
            reference_doctype="HD Ticket",
            reference_name=doc.name,
            in_reply_to=doc._last_threadable_communication(),
            email_headers={"X-Auto-Generated": "hd-anonymous-status-update"},
        )
    except Exception:
        frappe.log_error(
            title="Anonymous ticket status email failed",
            message=f"Could not queue a status email for HD Ticket {doc.name}.",
        )
