"""Guest-only ticket submission with email ownership verification.

The pending payload is short-lived and stored in the site cache. A random
bearer token is emailed to the requester; only its SHA-256 digest is used as
the cache key. Successful verification creates one native HD Ticket.
"""

import hashlib
import html
import hmac
import secrets
import time
import uuid

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import validate_email_address
from frappe.utils.password import get_encryption_key

OTP_TTL_SECONDS = 10 * 60
OTP_LENGTH = 6
MAX_OTP_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60
MAX_OTP_RESENDS = 3
MAX_DESCRIPTION_LENGTH = 10_000
CACHE_PREFIX = "helpdesk:guest-ticket:otp:"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _cache_key(challenge_id: str) -> str:
    return f"{CACHE_PREFIX}{_digest(challenge_id)}"


def _ticket_key(challenge_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"cbsua-guest-ticket:{_digest(challenge_id)}"))


def _otp_digest(challenge_id: str, otp: str) -> str:
    secret = get_encryption_key()
    message = f"{challenge_id}:{otp}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _new_otp() -> str:
    return f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"


def _guest_otp_email_context(payload: dict, otp: str) -> dict:
    office_name = frappe.db.get_value("CB Office", payload["office"], "office_name")
    request_type_name = frappe.db.get_value(
        "CB Office Request Type", payload["request_type"], "request_type_name"
    )
    return {
        "full_name": payload["full_name"],
        "subject": payload["subject"],
        "office": office_name or payload["office"],
        "request_type": request_type_name or payload["request_type"],
        "otp": otp,
        "expires_in_minutes": OTP_TTL_SECONDS // 60,
    }


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
    """Create a pending challenge and email a six-digit OTP; no ticket yet."""
    payload = _validate_submission(email, full_name, subject, description, office, request_type)
    challenge_id = secrets.token_urlsafe(32)
    otp = _new_otp()
    now = time.time()
    challenge = {
        "payload": payload,
        "otp_digest": _otp_digest(challenge_id, otp),
        "attempts": 0,
        "resends": 0,
        "last_sent_at": now,
        "created_at": now,
    }
    cache_key = _cache_key(challenge_id)
    try:
        frappe.cache.set_value(cache_key, challenge, expires_in_sec=OTP_TTL_SECONDS)
    except Exception:
        frappe.log_error(message=frappe.get_traceback(), title="Guest ticket OTP cache unavailable")
        return {"success": False, "code": "temporarily_unavailable"}
    try:
        frappe.sendmail(
            recipients=[payload["email"]],
            subject=_("Your CBSUA Helpdesk verification code"),
            template="guest_ticket_verification",
            args=_guest_otp_email_context(payload, otp),
        )
    except Exception:
        frappe.cache.delete_value(cache_key)
        raise
    return {
        "success": True,
        "challenge_id": challenge_id,
        "expires_in_seconds": OTP_TTL_SECONDS,
        "message": _("A verification code has been sent to your email address."),
    }


def _acquire_challenge_lock(challenge_id: str):
    lock_name = f"{frappe.local.site}:{_cache_key(challenge_id)}:lock"
    lock = frappe.cache.lock(lock_name, timeout=300, blocking_timeout=5)
    if not lock.acquire():
        return None
    frappe.db.after_commit.add(lambda: _release_verification_lock(lock))
    frappe.db.after_rollback.add(lambda: _release_verification_lock(lock))
    return lock


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=60, user_based=False)
def verify_guest_submission(challenge_id: str, otp: str) -> dict:
    """Verify an email OTP and create exactly one native HD Ticket."""
    if (
        not isinstance(challenge_id, str)
        or len(challenge_id) < 32
        or len(challenge_id) > 128
        or not isinstance(otp, str)
        or len(otp) != OTP_LENGTH
        or not otp.isdigit()
    ):
        return {"success": False, "code": "invalid_or_expired"}

    key = _ticket_key(challenge_id)
    existing = frappe.db.get_value("HD Ticket", {"key": key}, "name")
    if existing:
        return {"success": True, "ticket": existing}

    try:
        lock = _acquire_challenge_lock(challenge_id)
    except Exception:
        frappe.log_error(message=frappe.get_traceback(), title="Guest ticket OTP lock unavailable")
        return {"success": False, "code": "temporarily_unavailable"}
    if not lock:
        return {"success": False, "code": "processing"}

    cache_key = _cache_key(challenge_id)
    try:
        challenge = frappe.cache.get_value(cache_key)
    except Exception:
        frappe.log_error(message=frappe.get_traceback(), title="Guest ticket OTP cache unavailable")
        return {"success": False, "code": "temporarily_unavailable"}
    if not isinstance(challenge, dict):
        return {"success": False, "code": "invalid_or_expired"}
    if challenge.get("attempts", 0) >= MAX_OTP_ATTEMPTS:
        return {"success": False, "code": "too_many_attempts"}

    expected = _otp_digest(challenge_id, otp)
    if not hmac.compare_digest(challenge.get("otp_digest", ""), expected):
        challenge["attempts"] = challenge.get("attempts", 0) + 1
        remaining = max(0, MAX_OTP_ATTEMPTS - challenge["attempts"])
        ttl = max(1, int(OTP_TTL_SECONDS - (time.time() - challenge["created_at"])))
        try:
            frappe.cache.set_value(cache_key, challenge, expires_in_sec=ttl)
        except Exception:
            frappe.log_error(message=frappe.get_traceback(), title="Guest ticket OTP attempt update failed")
            return {"success": False, "code": "temporarily_unavailable"}
        return {
            "success": False,
            "code": "too_many_attempts" if remaining == 0 else "invalid_code",
            "attempts_remaining": remaining,
        }

    payload = challenge["payload"]
    payload = _validate_submission(
        payload["email"], payload.get("full_name", ""), payload["subject"],
        payload["description"], payload["office"], payload["request_type"],
    )
    description_html = html.escape(payload["description"]).replace("\n", "<br>")
    ticket = frappe.get_doc({
        "doctype": "HD Ticket",
        "subject": payload["subject"],
        "description": description_html,
        "raised_by": payload["email"],
        "via_customer_portal": 1,
        "office": payload["office"],
        "request_type": payload["request_type"],
    })
    ticket.flags.anonymous_submission = True
    ticket.flags.anonymous_requester_name = payload["full_name"]
    ticket.flags.anonymous_ticket_key = key
    ticket.insert(ignore_permissions=True)

    if (
        not frappe.flags.initial_sync
        and frappe.db.get_single_value("HD Settings", "send_acknowledgement_email")
    ):
        send_guest_acknowledgement_email(ticket)
    frappe.db.after_commit.add(lambda: frappe.cache.delete_value(cache_key))
    return {"success": True, "ticket": ticket.name}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=60, user_based=False)
def resend_guest_submission_otp(challenge_id: str) -> dict:
    """Rotate the OTP subject to cooldown and resend limits."""
    if not isinstance(challenge_id, str) or len(challenge_id) < 32 or len(challenge_id) > 128:
        return {"success": False, "code": "invalid_or_expired"}
    try:
        lock = _acquire_challenge_lock(challenge_id)
    except Exception:
        frappe.log_error(message=frappe.get_traceback(), title="Guest ticket OTP resend lock unavailable")
        return {"success": False, "code": "temporarily_unavailable"}
    if not lock:
        return {"success": False, "code": "processing"}

    cache_key = _cache_key(challenge_id)
    try:
        challenge = frappe.cache.get_value(cache_key)
    except Exception:
        frappe.log_error(message=frappe.get_traceback(), title="Guest ticket OTP resend cache unavailable")
        return {"success": False, "code": "temporarily_unavailable"}
    if not isinstance(challenge, dict):
        return {"success": False, "code": "invalid_or_expired"}
    if challenge.get("resends", 0) >= MAX_OTP_RESENDS:
        return {"success": False, "code": "resend_limit"}
    wait = RESEND_COOLDOWN_SECONDS - int(time.time() - challenge.get("last_sent_at", 0))
    if wait > 0:
        return {"success": False, "code": "cooldown", "retry_after": wait}

    otp = _new_otp()
    updated = dict(challenge)
    updated["otp_digest"] = _otp_digest(challenge_id, otp)
    updated["attempts"] = 0
    updated["resends"] = challenge.get("resends", 0) + 1
    updated["last_sent_at"] = time.time()
    ttl = max(1, int(OTP_TTL_SECONDS - (time.time() - challenge["created_at"])))
    try:
        frappe.cache.set_value(cache_key, updated, expires_in_sec=ttl)
    except Exception:
        frappe.log_error(message=frappe.get_traceback(), title="Guest ticket OTP resend cache update failed")
        return {"success": False, "code": "temporarily_unavailable"}
    try:
        frappe.sendmail(
            recipients=[challenge["payload"]["email"]],
            subject=_("Your new CBSUA Helpdesk verification code"),
            template="guest_ticket_verification",
            args=_guest_otp_email_context(challenge["payload"], otp),
        )
    except Exception:
        frappe.cache.set_value(cache_key, challenge, expires_in_sec=ttl)
        raise
    return {"success": True, "message": _("A new verification code has been sent.")}



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
