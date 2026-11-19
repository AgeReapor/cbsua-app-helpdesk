"""Narrow HD Ticket lifecycle extension for verified guest submissions."""

from __future__ import annotations

import frappe


class AnonymousHDTicketMixin:
    """Keep email-only requesters separate from authenticated Contact identities."""

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
                "sender",
                self.raised_by,
                update_modified=False,
            )
        return result
