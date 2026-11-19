import frappe
from frappe.tests import IntegrationTestCase

from helpdesk.anonymous_tickets import (
    _ticket_key,
    _token_digest,
    _validate_submission,
    verify_guest_submission,
)


class TestAnonymousTicketSubmission(IntegrationTestCase):
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
