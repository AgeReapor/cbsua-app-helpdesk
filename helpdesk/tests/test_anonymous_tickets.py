"""Focused tests for the anonymous ticket submission boundary."""

from unittest.mock import Mock, patch
from uuid import UUID

import frappe
from frappe.tests.utils import FrappeTestCase

from helpdesk.anonymous_tickets import (
    MAX_OTP_ATTEMPTS,
    OTP_LENGTH,
    OTP_TTL_SECONDS,
    _cache_key,
    _digest,
    _guest_otp_email_context,
    _new_otp,
    _otp_digest,
    _send_guest_otp_email,
    _ticket_key,
    _validate_submission,
    resend_guest_submission_otp,
    verify_guest_submission,
)
from helpdesk.helpdesk.doctype.hd_ticket.hd_ticket import (
    has_permission,
    permission_query,
)
from helpdesk.test_utils import create_user, unique_email


class TestAnonymousTicketHelpers(FrappeTestCase):
    def test_challenge_id_cache_key_and_ticket_key_are_opaque_and_stable(self):
        challenge_id = "a" * 48
        self.assertNotIn(challenge_id, _cache_key(challenge_id))
        self.assertEqual(len(_digest(challenge_id)), 64)
        self.assertEqual(_ticket_key(challenge_id), _ticket_key(challenge_id))
        self.assertIsInstance(UUID(_ticket_key(challenge_id)), UUID)

    def test_otp_is_six_digits_and_digest_is_bound_to_challenge(self):
        otp = _new_otp()
        self.assertEqual(len(otp), OTP_LENGTH)
        self.assertTrue(otp.isdigit())
        with patch("helpdesk.anonymous_tickets.get_encryption_key", return_value="site-secret"):
            digest = _otp_digest("challenge-a", otp)
            self.assertEqual(digest, _otp_digest("challenge-a", otp))
            self.assertNotEqual(digest, _otp_digest("challenge-b", otp))
            self.assertNotEqual(digest, otp)

    def test_otp_email_context_omits_request_description_and_site_url(self):
        payload = {
            "full_name": "Campus Visitor",
            "email": "visitor@example.com",
            "subject": "Cannot access Wi-Fi",
            "description": "Private request details",
            "office": "ICT",
            "request_type": "TECH-SUPPORT",
        }
        with patch(
            "helpdesk.anonymous_tickets.frappe.db.get_value",
            side_effect=["ICT Office", "Technical Support"],
        ):
            context = _guest_otp_email_context(payload, "123456")
        self.assertEqual(context["otp"], "123456")
        self.assertEqual(context["expires_in_minutes"], OTP_TTL_SECONDS // 60)
        self.assertNotIn("description", context)
        self.assertNotIn("verify_url", context)
        self.assertNotIn("logo_url", context)

    def test_guest_otp_email_uses_post_commit_delivery_and_redacts_body(self):
        payload = {
            "email": "visitor@example.com",
            "full_name": "Campus Visitor",
            "subject": "Cannot access Wi-Fi",
            "office": "ICT",
            "request_type": "TECH-SUPPORT",
        }
        with (
            patch(
                "helpdesk.anonymous_tickets._guest_otp_email_context",
                return_value={"otp": "123456"},
            ),
            patch("helpdesk.anonymous_tickets.frappe.sendmail") as sendmail,
        ):
            _send_guest_otp_email(payload, "123456")
        kwargs = sendmail.call_args.kwargs
        self.assertEqual(kwargs["recipients"], ["visitor@example.com"])
        self.assertEqual(kwargs["template"], "guest_ticket_verification")
        self.assertTrue(kwargs["now"])
        self.assertTrue(kwargs["redact_message_after_send"])
        self.assertEqual(kwargs["args"], {"otp": "123456"})
        self.assertIn("verification code", kwargs["subject"].lower())

    def test_guest_otp_resend_uses_same_post_commit_delivery_configuration(self):
        payload = {
            "email": "visitor@example.com",
            "full_name": "Campus Visitor",
            "subject": "Cannot access Wi-Fi",
            "office": "ICT",
            "request_type": "TECH-SUPPORT",
        }
        with (
            patch(
                "helpdesk.anonymous_tickets._guest_otp_email_context",
                return_value={"otp": "654321"},
            ),
            patch("helpdesk.anonymous_tickets.frappe.sendmail") as sendmail,
        ):
            _send_guest_otp_email(payload, "654321", resend=True)
        kwargs = sendmail.call_args.kwargs
        self.assertTrue(kwargs["now"])
        self.assertTrue(kwargs["redact_message_after_send"])
        self.assertIn("new", kwargs["subject"].lower())
        self.assertEqual(kwargs["args"], {"otp": "654321"})

    def test_verification_rejects_malformed_challenge_or_otp_before_lookup(self):
        self.assertEqual(
            verify_guest_submission("short", "123456"),
            {"success": False, "code": "invalid_or_expired"},
        )
        self.assertEqual(
            verify_guest_submission("a" * 48, "12x456"),
            {"success": False, "code": "invalid_or_expired"},
        )

    def test_verification_lock_failure_is_reported_as_temporary(self):
        with (
            patch("helpdesk.anonymous_tickets.frappe.db.get_value", return_value=None),
            patch("helpdesk.anonymous_tickets._acquire_challenge_lock", side_effect=RuntimeError),
            patch("helpdesk.anonymous_tickets.frappe.log_error"),
        ):
            result = verify_guest_submission("a" * 48, "123456")
        self.assertEqual(result, {"success": False, "code": "temporarily_unavailable"})

    def test_expired_challenge_is_reported_without_creating_a_ticket(self):
        with (
            patch("helpdesk.anonymous_tickets.frappe.db.get_value", return_value=None),
            patch("helpdesk.anonymous_tickets._acquire_challenge_lock", return_value=Mock()),
            patch("helpdesk.anonymous_tickets.frappe.cache.get_value", return_value=None),
        ):
            result = verify_guest_submission("a" * 48, "123456")
        self.assertEqual(result, {"success": False, "code": "invalid_or_expired"})

    def test_incorrect_otp_increments_attempts_and_returns_remaining_count(self):
        challenge_id = "a" * 48
        challenge = {
            "payload": {},
            "otp_digest": "not-the-code",
            "attempts": 0,
            "created_at": __import__("time").time(),
        }
        with (
            patch("helpdesk.anonymous_tickets.frappe.db.get_value", return_value=None),
            patch("helpdesk.anonymous_tickets._acquire_challenge_lock", return_value=Mock()),
            patch("helpdesk.anonymous_tickets.frappe.cache.get_value", return_value=challenge),
            patch("helpdesk.anonymous_tickets.frappe.cache.set_value") as set_value,
            patch("helpdesk.anonymous_tickets.get_encryption_key", return_value="site-secret"),
        ):
            result = verify_guest_submission(challenge_id, "123456")
        self.assertEqual(result["code"], "invalid_code")
        self.assertEqual(result["attempts_remaining"], MAX_OTP_ATTEMPTS - 1)
        self.assertEqual(challenge["attempts"], 1)
        set_value.assert_called_once()

    def test_verification_cache_outage_is_reported_as_temporary(self):
        with (
            patch("helpdesk.anonymous_tickets.frappe.db.get_value", return_value=None),
            patch("helpdesk.anonymous_tickets._acquire_challenge_lock", return_value=Mock()),
            patch("helpdesk.anonymous_tickets.frappe.cache.get_value", side_effect=RuntimeError),
            patch("helpdesk.anonymous_tickets.frappe.log_error"),
        ):
            result = verify_guest_submission("a" * 48, "123456")
        self.assertEqual(result, {"success": False, "code": "temporarily_unavailable"})

    def test_resend_obeys_cooldown_and_resend_limit(self):
        challenge_id = "a" * 48
        challenge = {
            "payload": {"email": "visitor@example.com"},
            "resends": 0,
            "last_sent_at": 990,
            "created_at": 500,
        }
        with (
            patch("helpdesk.anonymous_tickets._acquire_challenge_lock", return_value=Mock()),
            patch("helpdesk.anonymous_tickets.frappe.cache.get_value", return_value=challenge),
            patch("helpdesk.anonymous_tickets.time.time", return_value=1000),
        ):
            result = resend_guest_submission_otp(challenge_id)
        self.assertEqual(result["code"], "cooldown")
        challenge["resends"] = 3
        challenge["last_sent_at"] = 800
        with (
            patch("helpdesk.anonymous_tickets._acquire_challenge_lock", return_value=Mock()),
            patch("helpdesk.anonymous_tickets.frappe.cache.get_value", return_value=challenge),
            patch("helpdesk.anonymous_tickets.time.time", return_value=1000),
        ):
            result = resend_guest_submission_otp(challenge_id)
        self.assertEqual(result["code"], "resend_limit")

    def test_native_ticket_key_is_unique_in_the_doctype_schema(self):
        key_field = frappe.get_meta("HD Ticket").get_field("key")
        self.assertTrue(key_field.unique)

    def test_guest_owned_ticket_is_not_readable_by_guest_or_matching_email_user(self):
        email = unique_email("anonymous-requester")
        create_user(email)
        ticket = frappe._dict(
            {
                "owner": "Guest",
                "raised_by": email,
                "contact": None,
                "customer": None,
                "agent_group": None,
                "_assign": None,
            }
        )

        self.assertFalse(has_permission(ticket, "Guest"))
        self.assertFalse(has_permission(ticket, email))
        self.assertEqual(permission_query("Guest"), "1=0")
        self.assertIn("owner != 'Guest'", permission_query(email))

    def test_anonymous_insert_rules_preserve_verified_email_and_guest_owner(self):
        ticket = frappe.new_doc("HD Ticket")
        ticket.flags.anonymous_submission = True
        ticket.flags.anonymous_ticket_key = "guest-key"
        ticket.owner = "Administrator"
        ticket.raised_by = "visitor@example.com"

        ticket.before_insert()

        self.assertEqual(ticket.owner, "Guest")
        self.assertEqual(ticket.raised_by, "visitor@example.com")
        self.assertEqual(ticket.via_customer_portal, 1)
        self.assertEqual(ticket.key, "guest-key")

    def test_submission_rejects_invalid_email(self):
        with self.assertRaises(frappe.ValidationError):
            _validate_submission(
                "not-an-email",
                "",
                "Need help",
                "Please assist.",
                "ICT",
                "TECH-SUPPORT",
            )

    def test_submission_normalizes_email_and_trims_text(self):
        with patch("helpdesk.anonymous_tickets.frappe.db.exists", return_value=True):
            result = _validate_submission(
                "  REQUESTER@EXAMPLE.COM ",
                "  Campus Visitor  ",
                "  Cannot access Wi-Fi  ",
                "  Wi-Fi is unavailable in the library.  ",
                "ICT",
                "TECH-SUPPORT",
            )

        self.assertEqual(
            result,
            {
                "email": "requester@example.com",
                "full_name": "Campus Visitor",
                "subject": "Cannot access Wi-Fi",
                "description": "Wi-Fi is unavailable in the library.",
                "office": "ICT",
                "request_type": "TECH-SUPPORT",
            },
        )

    def test_submission_rejects_request_type_from_another_office(self):
        def exists(doctype, filters):
            if doctype == "CB Office":
                return True
            if doctype == "CB Office Request Type":
                return False
            return False

        with patch("helpdesk.anonymous_tickets.frappe.db.exists", side_effect=exists):
            with self.assertRaises(frappe.ValidationError):
                _validate_submission(
                    "requester@example.com",
                    "",
                    "Need help",
                    "Please assist.",
                    "ICT",
                    "REG-INQUIRY",
                )

    def test_submission_rejects_non_string_fields_and_subject_controls(self):
        with self.assertRaises(frappe.ValidationError):
            _validate_submission(
                ["requester@example.com"],
                "",
                "Need help",
                "Please assist.",
                "ICT",
                "TECH-SUPPORT",
            )

        with patch("helpdesk.anonymous_tickets.frappe.db.exists", return_value=True):
            with self.assertRaises(frappe.ValidationError):
                _validate_submission(
                    "requester@example.com",
                    "",
                    "Need help\nBcc: attacker@example.com",
                    "Please assist.",
                    "ICT",
                    "TECH-SUPPORT",
                )

    def test_submission_rejects_empty_or_oversized_content(self):
        with patch("helpdesk.anonymous_tickets.frappe.db.exists", return_value=True):
            with self.assertRaises(frappe.ValidationError):
                _validate_submission(
                    "requester@example.com",
                    "",
                    "   ",
                    "Details",
                    "ICT",
                    "TECH-SUPPORT",
                )
            with self.assertRaises(frappe.ValidationError):
                _validate_submission(
                    "requester@example.com",
                    "",
                    "Need help",
                    "x" * 10_001,
                    "ICT",
                    "TECH-SUPPORT",
                )
