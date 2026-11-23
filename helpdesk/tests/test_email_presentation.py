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

    def test_migration_disables_existing_accounts_and_clears_old_reply_template(self):
        with (
            patch(
                "helpdesk.patches.disable_email_open_tracking.frappe.get_all",
                return_value=["Outgoing A", "Outgoing B"],
            ),
            patch(
                "helpdesk.patches.disable_email_open_tracking.frappe.db.set_value"
            ) as set_value,
            patch(
                "helpdesk.patches.disable_email_open_tracking.frappe.db.exists",
                return_value=True,
            ),
            patch(
                "helpdesk.patches.disable_email_open_tracking.frappe.db.set_single_value"
            ) as set_single_value,
        ):
            from helpdesk.patches.disable_email_open_tracking import execute

            execute()

        self.assertEqual(set_value.call_count, 2)
        self.assertEqual(
            set_single_value.call_args.args,
            ("HD Settings", "reply_via_agent_email_content", ""),
        )
