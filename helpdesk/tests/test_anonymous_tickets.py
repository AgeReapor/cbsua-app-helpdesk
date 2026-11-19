"""Focused tests for the anonymous ticket submission boundary."""

from unittest.mock import patch
from uuid import UUID

import frappe
from frappe.tests.utils import FrappeTestCase

from helpdesk.helpdesk.doctype.hd_ticket.hd_ticket import has_permission, permission_query
from helpdesk.test_utils import create_user, unique_email
from helpdesk.anonymous_tickets import (
    _cache_key,
    _ticket_key,
    _token_digest,
    _validate_submission,
)


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
                    "Need help\\nBcc: attacker@example.com",
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
