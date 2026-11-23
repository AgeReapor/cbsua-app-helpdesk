"""Focused tests for the anonymous ticket submission boundary."""

from unittest.mock import patch
from uuid import UUID

import frappe
from frappe.tests.utils import FrappeTestCase

from helpdesk.anonymous_tickets import (
    _build_verification_url,
    _cache_key,
    _ticket_key,
    _token_digest,
    _validate_submission,
    verify_guest_submission,
)
from helpdesk.helpdesk.doctype.hd_ticket.hd_ticket import (
    has_permission,
    permission_query,
)
from helpdesk.test_utils import create_user, unique_email


class TestAnonymousTicketHelpers(FrappeTestCase):
    def test_token_digest_and_cache_key_do_not_expose_token(self):
        token = "a" * 48
        digest = _token_digest(token)

        self.assertNotEqual(digest, token)
        self.assertEqual(len(digest), 64)
        self.assertEqual(_cache_key(digest), f"helpdesk:guest-ticket:{digest}")
        self.assertNotIn(token, _cache_key(digest))

    def test_ticket_key_is_a_stable_uuid_for_one_verification_token(self):
        digest = _token_digest("verification-token-for-idempotency")
        key = _ticket_key(digest)

        self.assertEqual(key, _ticket_key(digest))
        self.assertIsInstance(UUID(key), UUID)
        self.assertNotEqual(key, _ticket_key(_token_digest("another-token")))

    def test_verification_rejects_malformed_tokens_before_lookup(self):
        self.assertEqual(
            verify_guest_submission("too-short"),
            {"success": False, "code": "invalid_or_expired"},
        )

    def test_verification_url_uses_canonical_site_host_and_encodes_token(self):
        token = "a" * 40 + "/+"
        with patch("helpdesk.anonymous_tickets.get_url") as get_url:
            get_url.return_value = "https://helpdesk.example/help/guest/new?verify=safe"
            result = _build_verification_url(token)

        self.assertEqual(
            get_url.call_args.args[0],
            "/help/guest/new?verify=" + __import__("urllib.parse").parse.quote(token, safe=""),
        )
        self.assertFalse(get_url.call_args.kwargs["allow_header_override"])
        self.assertEqual(result, get_url.return_value)

    def test_verification_lock_failure_is_reported_as_temporary(self):
        with (
            patch("helpdesk.anonymous_tickets.frappe.db.get_value", return_value=None),
            patch("helpdesk.anonymous_tickets.frappe.cache.lock", side_effect=RuntimeError),
            patch("helpdesk.anonymous_tickets.frappe.log_error"),
        ):
            result = verify_guest_submission("a" * 48)

        self.assertEqual(
            result, {"success": False, "code": "temporarily_unavailable"}
        )

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
