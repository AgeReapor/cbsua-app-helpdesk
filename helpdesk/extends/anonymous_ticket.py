"""Narrow HD Ticket lifecycle extension for verified guest submissions."""

from __future__ import annotations

import frappe


class AnonymousHDTicketMixin:
    """Keep email-only requesters separate from authenticated Contact identities."""

    def before_insert(self) -> None:
        super().before_insert()
        if getattr(self.flags, "anonymous_submission", False):
            # Frappe sets owner from the active session before before_insert runs.
            self.owner = "Guest"

    def apply_ticket_insert_rules(self) -> None:
        if getattr(self.flags, "anonymous_submission", False):
            # The guest service owns requester identity and all insertable fields.
            # Do not replace the verified email with the current session user.
            self.via_customer_portal = 1
            return
        super().apply_ticket_insert_rules()

    def validate_portal_contact(self) -> None:
        if getattr(self.flags, "anonymous_submission", False):
            return
        super().validate_portal_contact()

    def set_contact(self) -> None:
        if getattr(self.flags, "anonymous_submission", False):
            return
        super().set_contact()

    def set_customer(self) -> None:
        if getattr(self.flags, "anonymous_submission", False):
            return
        super().set_customer()

    def generate_key(self) -> None:
        if getattr(self.flags, "anonymous_submission", False):
            self.key = self.flags.anonymous_ticket_key
            return
        super().generate_key()

    @frappe.whitelist(methods=["POST"])
    def reply_via_agent(
        self,
        message: str,
        from_email: dict | None = None,
        to: str | None = None,
        cc: str | None = None,
        bcc: str | None = None,
        attachments: list[str] | None = None,
    ) -> str:
        if not getattr(self.flags, "anonymous_submission", False) and self.owner != "Guest":
            return super().reply_via_agent(
                message, from_email, to, cc, bcc, attachments or []
            )

        # The native customer-portal reply template links to ticket detail. Guest
        # requesters cannot open that page, so send the public reply body without it.
        via_customer_portal = self.via_customer_portal
        self.via_customer_portal = 0
        try:
            return super().reply_via_agent(
                message, from_email, to, cc, bcc, attachments or []
            )
        finally:
            self.via_customer_portal = via_customer_portal

    def create_communication_via_contact(
        self,
        message: str,
        attachments: list[dict] | None = None,
        new_ticket: bool = False,
    ):
        result = super().create_communication_via_contact(
            message, attachments, new_ticket
        )
        if not (
            getattr(self.flags, "anonymous_submission", False)
            and new_ticket
        ):
            return result

        communication = frappe.db.get_value(
            "Communication",
            {
                "reference_doctype": "HD Ticket",
                "reference_name": self.name,
                "sender": "Guest",
                "sent_or_received": "Received",
            },
            "name",
            order_by="creation desc",
        )
        if communication:
            frappe.db.set_value(
                "Communication",
                communication,
                {
                    "sender": self.raised_by,
                    "sender_full_name": (
                        getattr(self.flags, "anonymous_requester_name", None)
                        or self.raised_by
                    ),
                },
                update_modified=False,
            )
        return result
