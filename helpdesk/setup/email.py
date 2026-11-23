"""Disable email-open tracking pixels for CBSUA Helpdesk customer mail."""

import frappe


def execute():
    """Turn off tracking on existing accounts and use the plain reply template."""
    for account in frappe.get_all(
        "Email Account", filters={"track_email_status": 1}, pluck="name"
    ):
        frappe.db.set_value(
            "Email Account", account, "track_email_status", 0, update_modified=False
        )

    if frappe.db.exists("DocType", "HD Settings"):
        frappe.db.set_single_value("HD Settings", "reply_via_agent_email_content", "")


def disable_email_open_tracking(doc, method=None):
    """Do not let newly created outgoing accounts add remote read pixels."""
    doc.track_email_status = 0
