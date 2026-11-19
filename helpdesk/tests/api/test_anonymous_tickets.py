import frappe
from frappe.tests import IntegrationTestCase

from helpdesk.helpdesk.doctype.hd_ticket.hd_ticket import (
    has_permission,
    permission_query,
)
from helpdesk.anonymous_tickets import (
    _ticket_key,
    _token_digest,
    _validate_submission,
    verify_guest_submission,
)


class TestAnonymousTicketSubmission(IntegrationTestCase):
    def test_anonymous_insert_rules_preserve_verified_email(self):
        ticket = frappe.new_doc("HD Ticket")
        ticket.flags.anonymous_submission = True
        ticket.raised_by = "visitor@example.com"

        ticket.apply_ticket_insert_rules()

        self.assertEqual(ticket.raised_by, "visitor@example.com")
        self.assertEqual(ticket.via_customer_portal, 1)

    def test_native_ticket_key_is_unique_for_idempotent_creation(self):
        self.assertTrue(frappe.get_meta("HD Ticket").get_field("key").unique)

    def test_token_digest_is_stable_and_does_not_expose_the_token(self):
        token = "a-long-random-verification-token"
        digest = _token_digest(token)

        self.assertEqual(digest, _token_digest(token))
        self.assertNotEqual(digest, token)
        self.assertEqual(len(digest), 64)
        self.assertEqual(_ticket_key(digest), _ticket_key(digest))

    def test_invalid_verification_token_is_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            verify_guest_submission("invalid")

    def test_submission_rejects_disabled_or_missing_office(self):
        with self.assertRaises(frappe.ValidationError):
            _validate_submission(
                "visitor@example.com",
                "",
                "Unable to connect",
                "The service is unavailable.",
                "missing-office",
                "missing-request-type",
            )

    def test_submission_rejects_invalid_email(self):
        with self.assertRaises(frappe.ValidationError):
            _validate_submission(
                "not-an-email",
                "",
                "Unable to connect",
                "The service is unavailable.",
                "missing-office",
                "missing-request-type",
            )

    def test_guest_cannot_read_or_list_tickets_even_when_guest_owns_them(self):
        ticket = frappe._dict(
            owner="Guest",
            contact=None,
            raised_by="visitor@example.com",
            customer=None,
        )

        self.assertFalse(has_permission(ticket, "Guest"))
        self.assertEqual(permission_query("Guest"), "1=0")

        # Email-as-username accounts must not inherit access from raised_by.
        self.assertFalse(has_permission(ticket, "visitor@example.com"))
        self.assertIn("owner != 'Guest'", permission_query("visitor@example.com"))
