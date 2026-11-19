"""Narrow HD Ticket lifecycle extension for verified guest submissions."""

from __future__ import annotations


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
