"""Server-side office routing and resolution authorization."""

import frappe
from frappe import _


def _is_privileged():
    """Whether the current user may override office-team routing."""
    return frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles()


def _team_is_assigned_to_office(team_name, office):
    """Return whether an HD Team is explicitly mapped to the given CBSUA office."""
    if not team_name or not office:
        return False
    team = frappe.get_doc("HD Team", team_name)
    return office in {row.office for row in team.get("offices", []) if row.office}


def set_ticket_defaults(doc, method=None):
    """Apply office and request-type defaults before ticket validation."""
    if not doc.is_new():
        return

    if not doc.office:
        default_office = frappe.db.get_single_value("HD Settings", "default_cb_office")
        if not default_office or not frappe.db.get_value(
            "CB Office", {"name": default_office, "enabled": 1}, "name"
        ):
            default_office = frappe.db.get_value(
                "CB Office", {"is_default": 1, "enabled": 1}, "name"
            )
        if default_office:
            doc.office = default_office

    # Email integrations and internal agent-created tickets predate the portal's
    # explicit request-type selector. Give those flows the office's Inquiry type
    # (or first enabled type) while requiring portal submissions to choose one.
    if doc.office and not doc.request_type and not doc.via_customer_portal:
        request_type = frappe.db.get_value(
            "CB Office Request Type",
            {"office": doc.office, "request_type_name": "Inquiry", "enabled": 1},
            "name",
        ) or frappe.db.get_value(
            "CB Office Request Type",
            {"office": doc.office, "enabled": 1},
            "name",
            order_by="display_order asc",
        )
        if request_type:
            doc.request_type = request_type


def validate_ticket_office_routing(doc, method=None):
    """Validate office/type consistency while allowing privileged team overrides."""
    if not doc.office:
        # Existing pre-office tickets remain readable and editable during migration.
        if doc.is_new():
            frappe.throw(_("Select an office before creating this ticket."))
        return

    office = frappe.db.get_value("CB Office", doc.office, ["enabled"], as_dict=True)
    if not office or not office.enabled:
        frappe.throw(_("The selected office is unavailable."))

    if doc.request_type:
        valid_type = frappe.db.exists(
            "CB Office Request Type",
            {"name": doc.request_type, "office": doc.office, "enabled": 1},
        )
        if not valid_type:
            frappe.throw(_("The selected request type is not enabled for this office."))
    elif doc.is_new():
        frappe.throw(_("Select a type of request for the selected office."))

    # Apply the request type's team only when no team was explicitly selected.
    # This runs after office/type defaults and validation, in the ticket save lifecycle.
    if doc.is_new() and not doc.agent_group and doc.request_type:
        default_team = frappe.db.get_value(
            "CB Office Request Type",
            {"name": doc.request_type, "office": doc.office, "enabled": 1},
            "default_team",
        )
        if default_team:
            if not _team_is_assigned_to_office(default_team, doc.office):
                frappe.throw(
                    _("The default team {0} is not assigned to {1}.").format(
                        default_team, doc.office
                    )
                )
            doc.agent_group = default_team

    # Office-team mapping is a soft default, not a hard routing boundary for admins.
    if (
        doc.agent_group
        and not _is_privileged()
        and not _team_is_assigned_to_office(doc.agent_group, doc.office)
    ):
        frappe.throw(
            _("Team {0} is not assigned to {1}.").format(doc.agent_group, doc.office)
        )

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
def get_office_request_types(office: str) -> list[dict]:
    """Return enabled request types for customer/agent dependent selects."""
    if not frappe.has_permission("CB Office", "read", office):
        frappe.throw(_("You do not have access to this office."), frappe.PermissionError)
    if not frappe.db.get_value("CB Office", office, "enabled"):
        return []
    return frappe.get_list(
        "CB Office Request Type",
        filters={"office": office, "enabled": 1},
        fields=["name", "request_type_name"],
        order_by="display_order asc, request_type_name asc",
    )


@frappe.whitelist()
def get_enabled_offices() -> list[dict]:
    """Enabled offices for the customer and agent ticket forms."""
    return frappe.get_list(
        "CB Office",
        filters={"enabled": 1},
        fields=["name", "office_name", "is_default"],
        order_by="is_default desc, office_name asc",
    )
