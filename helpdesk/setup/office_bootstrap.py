"""Idempotent CBSUA office, request-type, and team bootstrap.

Safe to run after install and on every migrate. Existing office settings are
preserved; only missing baseline records are inserted. Office teams are created
without staff membership because team membership is an operational decision.
Request types receive configurable default-team destinations.
"""

import frappe

DEFAULT_OFFICES = [
    {"office_name": "ICT Office", "office_code": "ICT", "is_default": 1},
    {"office_name": "Registrar's Office", "office_code": "REG"},
    {"office_name": "Admissions Office", "office_code": "ADM"},
    {"office_name": "Cashier's Office", "office_code": "CSH"},
]

DEFAULT_REQUEST_TYPES = [
    ("ICT", "Tech Support", "TECH-SUPPORT", 10),
    ("ICT", "Inquiry", "ICT-INQUIRY", 20),
    ("REG", "Inquiry", "REG-INQUIRY", 10),
    ("ADM", "Inquiry", "ADM-INQUIRY", 10),
    ("CSH", "Inquiry", "CSH-INQUIRY", 10),
]


def bootstrap_offices():
    """Create baseline offices and request types without overwriting edits."""
    for office in DEFAULT_OFFICES:
        if not frappe.db.exists("CB Office", {"office_code": office["office_code"]}):
            legacy_name = frappe.db.get_value(
                "HD Office", {"office_code": office["office_code"]}, "name"
            ) if frappe.db.exists("DocType", "HD Office") else None
            legacy = frappe.db.get_value("HD Office", legacy_name, "*", as_dict=True) if legacy_name else {}
            values = {key: value for key, value in (legacy or {}).items() if key in ("office_name", "office_code", "enabled", "is_default", "description")}
            frappe.get_doc({"doctype": "CB Office", **office, "enabled": 1, **values}).insert(
                ignore_permissions=True
            )

    # Keep the HD Settings default authoritative, falling back to ICT on first boot.
    default_office = frappe.db.get_single_value("HD Settings", "default_cb_office")
    if not default_office or not frappe.db.get_value(
        "CB Office", {"name": default_office, "enabled": 1}, "name"
    ):
        default_office = frappe.db.get_value(
            "CB Office", {"is_default": 1, "enabled": 1}, "name"
        )
        if not default_office:
            default_office = frappe.db.get_value(
                "CB Office", {"office_code": "ICT", "enabled": 1}, "name"
            )
        if default_office:
            frappe.db.set_single_value("HD Settings", "default_cb_office", default_office)
    if default_office:
        frappe.db.set_value("CB Office", {"is_default": 1}, "is_default", 0)
        frappe.db.set_value("CB Office", default_office, "is_default", 1)

    for office_code, label, code, order in DEFAULT_REQUEST_TYPES:
        office = frappe.db.get_value("CB Office", {"office_code": office_code}, "name")
        if not office or frappe.db.exists("CB Office Request Type", code):
            continue
        legacy = frappe.db.get_value("HD Office Request Type", code, "*", as_dict=True) if frappe.db.exists("DocType", "HD Office Request Type") else {}
        values = {key: value for key, value in (legacy or {}).items() if key in ("request_type_name", "request_type_code", "enabled", "display_order", "description")}
        frappe.get_doc({
            "doctype": "CB Office Request Type",
            "request_type_name": label,
            "request_type_code": code,
            "office": office,
            "enabled": 1,
            "display_order": order,
            **values,
        }).insert(ignore_permissions=True)



# Keep these as native Helpdesk teams so membership, assignment rules, and ticket
# assignment continue to use the existing HD Team workflows.
DEFAULT_OFFICE_TEAMS = [
    ("ICT Support Team", "ICT"),
    ("Registrar Support Team", "REG"),
    ("Admissions Support Team", "ADM"),
    ("Cashier Support Team", "CSH"),
]


def bootstrap_office_teams():
    """Ensure each CBSUA office has a dedicated, correctly mapped HD Team.

    Safe on fresh installs and upgrades. Existing members, disabled state,
    assignment rules, and additional office mappings are preserved.
    """
    for team_name, office_code in DEFAULT_OFFICE_TEAMS:
        office = frappe.db.get_value(
            "CB Office", {"office_code": office_code, "enabled": 1}, "name"
        )
        if not office:
            continue

        if not frappe.db.exists("HD Team", team_name):
            team = frappe.new_doc("HD Team")
            team.team_name = team_name
            # An empty team is valid during initial setup; its generated
            # support-rotation Assignment Rule remains disabled until staffed.
            team.insert(ignore_permissions=True, ignore_mandatory=True)
        else:
            team = frappe.get_doc("HD Team", team_name)

        assigned_offices = {row.office for row in team.get("offices", []) if row.office}
        if office not in assigned_offices:
            team.append("offices", {"office": office})
            team.save(ignore_permissions=True)

    # Configure only missing defaults; administrator-defined destinations win.
    for request_code, team_name in (
        ("TECH-SUPPORT", "ICT Support Team"),
        ("ICT-INQUIRY", "ICT Support Team"),
        ("REG-INQUIRY", "Registrar Support Team"),
        ("ADM-INQUIRY", "Admissions Support Team"),
        ("CSH-INQUIRY", "Cashier Support Team"),
    ):
        if (
            frappe.db.exists("CB Office Request Type", request_code)
            and frappe.db.exists("HD Team", team_name)
            and not frappe.db.get_value("CB Office Request Type", request_code, "default_team")
        ):
            frappe.db.set_value(
                "CB Office Request Type", request_code, "default_team", team_name,
                update_modified=False,
            )


def execute():
    """Patch entry point used by patches.txt and after_migrate.

    Existing sites do not run after_install during an app upgrade, so ensure
    app-owned ticket/team custom fields are installed as part of migration too.
    """
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    from helpdesk.setup.install import get_custom_fields

    create_custom_fields(get_custom_fields(), update=True)
    migrate_legacy_office_records()
    bootstrap_offices()
    bootstrap_office_teams()
    migrate_legacy_team_offices()
    remove_legacy_office_doctypes()
    add_cbsua_link_permissions()


def add_cbsua_link_permissions():
    """Grant Link-field select access; read alone does not authorize Link queries."""
    from frappe.permissions import add_permission, update_permission_property

    for doctype in ("CB Office", "CB Office Request Type"):
        for role in ("System Manager", "Administrator", "Agent Manager", "Agent", "HD Customer", "HD Customer Manager"):
            add_permission(doctype, role)
            update_permission_property(doctype, role, 0, "read", 1)
            update_permission_property(doctype, role, 0, "select", 1)


def migrate_legacy_office_records():
    """Copy all existing HD office masters before retiring the old DocTypes."""
    if frappe.db.exists("DocType", "HD Office"):
        for row in frappe.get_all(
            "HD Office",
            fields=["office_name", "office_code", "enabled", "is_default", "description"],
        ):
            if not frappe.db.exists("CB Office", {"office_code": row.office_code}):
                frappe.get_doc({"doctype": "CB Office", **row}).insert(
                    ignore_permissions=True
                )

    if frappe.db.exists("DocType", "HD Office Request Type") and frappe.db.exists(
        "DocType", "HD Office"
    ):
        for row in frappe.get_all(
            "HD Office Request Type",
            fields=[
                "request_type_name",
                "request_type_code",
                "office",
                "enabled",
                "display_order",
                "description",
            ],
        ):
            if frappe.db.exists("CB Office Request Type", row.request_type_code):
                continue
            office_code = frappe.db.get_value("HD Office", row.office, "office_code")
            office = frappe.db.get_value(
                "CB Office", {"office_code": office_code}, "name"
            )
            if office:
                frappe.get_doc(
                    {"doctype": "CB Office Request Type", **row, "office": office}
                ).insert(ignore_permissions=True)


def migrate_legacy_team_offices():
    """Copy existing HD Team Office child rows to the CBSUA child table."""
    if not frappe.db.exists("DocType", "HD Team Office"):
        return
    for row in frappe.get_all(
        "HD Team Office",
        fields=["parent", "parentfield", "parenttype", "idx", "office"],
        order_by="parent, idx",
    ):
        if not frappe.db.exists(
            "CB Team Office",
            {"parent": row.parent, "parentfield": row.parentfield, "office": row.office},
        ):
            frappe.get_doc({"doctype": "CB Team Office", **row}).insert(
                ignore_permissions=True
            )


def remove_legacy_office_doctypes():
    """Remove the superseded HD-prefixed CBSUA DocTypes after data migration."""
    for doctype in ("HD Team Office", "HD Office Request Type", "HD Office"):
        if frappe.db.exists("DocType", doctype):
            frappe.delete_doc("DocType", doctype, force=True, ignore_missing=True)
