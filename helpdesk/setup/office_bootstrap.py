"""Idempotent CBSUA office and request-type bootstrap.

Safe to run after install and on every migrate. Existing office settings are
preserved; only missing baseline records are inserted. Teams are deliberately
not assigned automatically because membership is an operational decision.
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
        if not frappe.db.exists("HD Office", {"office_code": office["office_code"]}):
            frappe.get_doc({"doctype": "HD Office", "enabled": 1, **office}).insert(
                ignore_permissions=True
            )

    # Keep ICT as the default only when no default office has been configured.
    if not frappe.db.exists("HD Office", {"is_default": 1, "enabled": 1}):
        ict = frappe.db.get_value("HD Office", {"office_code": "ICT"}, "name")
        if ict:
            frappe.db.set_value("HD Office", ict, "is_default", 1)

    for office_code, label, code, order in DEFAULT_REQUEST_TYPES:
        office = frappe.db.get_value("HD Office", {"office_code": office_code}, "name")
        if not office or frappe.db.exists("HD Office Request Type", code):
            continue
        frappe.get_doc({
            "doctype": "HD Office Request Type",
            "request_type_name": label,
            "request_type_code": code,
            "office": office,
            "enabled": 1,
            "display_order": order,
        }).insert(ignore_permissions=True)


def execute():
    """Patch entry point used by patches.txt and after_migrate.

    Existing sites do not run after_install during an app upgrade, so ensure
    app-owned ticket/team custom fields are installed as part of migration too.
    """
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    from helpdesk.setup.install import get_custom_fields

    create_custom_fields(get_custom_fields(), update=True)
    bootstrap_offices()
