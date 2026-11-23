"""Email Account defaults for CBSUA Helpdesk."""

def disable_email_open_tracking(doc, method=None):
    """Keep new outgoing accounts from adding remote email-open pixels."""
    doc.track_email_status = 0
