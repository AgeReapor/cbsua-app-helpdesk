"""Server-side office routing and resolution authorization."""

import frappe
from frappe import _


def _is_privileged():
    return frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles()


def set_ticket_defaults(doc, method=None):
    """Set the configured default office for newly created legacy/API tickets."""
    if not doc.is_new() or doc.office:
        return
    default_office = frappe.db.get_value("HD Office", {"is_default": 1, "enabled": 1}, "name")
    if default_office:
        doc.office = default_office


def validate_ticket_office_routing(doc, method=None):
    """Validate office/type/team consistency for every ticket write."""
    if not doc.office:
        # Existing pre-office tickets remain readable and editable during migration.
        if doc.is_new():
            frappe.throw(_("Select an office before creating this ticket."))
        return

    office = frappe.db.get_value("HD Office", doc.office, ["enabled"], as_dict=True)
    if not office or not office.enabled:
        frappe.throw(_("The selected office is unavailable."))

    if doc.request_type:
        valid_type = frappe.db.exists(
            "HD Office Request Type",
            {"name": doc.request_type, "office": doc.office, "enabled": 1},
        )
        if not valid_type:
            frappe.throw(_("The selected request type is not enabled for this office."))
    elif doc.is_new():
        frappe.throw(_("Select a type of request for the selected office."))

    if doc.agent_group:
        team = frappe.get_doc("HD Team", doc.agent_group)
        allowed_offices = {row.office for row in team.get("offices", []) if row.office}
        if doc.office not in allowed_offices:
            frappe.throw(_("Team {0} is not assigned to {1}.").format(doc.agent_group, doc.office))

    # Resolution must be performed by an agent who belongs to the ticket's
    # assigned team. Administrators retain operational override capability.
    if doc.status_category == "Resolved" and doc.has_value_changed("status"):
        if not doc.agent_group:
            frappe.throw(_("Assign this ticket to an office team before resolving it."))
        if not _is_privileged():
            team_users = frappe.get_all(
                "HD Team Member", filters={"parent": doc.agent_group}, pluck="user"
            )
            if frappe.session.user not in team_users:
                frappe.throw(_("Only members of the assigned office team can resolve this ticket."), frappe.PermissionError)


@frappe.whitelist()
def get_office_request_types(office):
    """Return enabled request types for customer/agent dependent selects."""
    if not frappe.db.get_value("HD Office", office, "enabled"):
        return []
    return frappe.get_all(
        "HD Office Request Type",
        filters={"office": office, "enabled": 1},
        fields=["name", "request_type_name"],
        order_by="display_order asc, request_type_name asc",
    )
