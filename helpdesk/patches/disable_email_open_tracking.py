"""Disable email-open tracking for existing CBSUA Helpdesk accounts."""

import frappe


def execute():
    """Disable remote read pixels and reset the customer reply template."""
    for account in frappe.get_all(
        "Email Account", filters={"track_email_status": 1}, pluck="name"
    ):
        frappe.db.set_value(
            "Email Account", account, "track_email_status", 0, update_modified=False
        )

    if frappe.db.exists("DocType", "HD Settings"):
        frappe.db.set_single_value("HD Settings", "reply_via_agent_email_content", "")
