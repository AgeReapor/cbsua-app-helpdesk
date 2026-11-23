"""Tests for CBSUA customer-facing email presentation."""

from unittest.mock import call, patch

from frappe.tests.utils import FrappeTestCase

from helpdesk.helpdesk.doctype.hd_settings.helpers import get_default_email_content
from helpdesk.setup.email import disable_email_open_tracking


class TestCustomerReplyEmailPresentation(FrappeTestCase):
    def test_agent_reply_template_contains_only_message_and_generic_signature(self):
        template = get_default_email_content("reply_via_agent")

        self.assertIn("{{ message }}", template)
        self.assertIn("CBSUA Support", template)
        self.assertNotIn("{{ doc.name }}", template)
        self.assertNotIn("{{ ticket_url }}", template)
        self.assertNotIn("View in Portal", template)
        self.assertNotIn("<img", template.lower())

    def test_new_email_accounts_have_open_tracking_disabled(self):
        account = frappe._dict({"track_email_status": 1})
        disable_email_open_tracking(account)
        self.assertEqual(account.track_email_status, 0)
