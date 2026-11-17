import frappe
from frappe.tests.utils import FrappeTestCase

from helpdesk.setup.office_bootstrap import bootstrap_offices
from helpdesk.setup.office_routing import (
    get_office_request_types,
    validate_ticket_office_routing,
)


class TestOfficeBootstrap(FrappeTestCase):
    def test_bootstrap_creates_cbsua_baseline(self):
        bootstrap_offices()
        expected = {
            "ICT": {"Tech Support", "Inquiry"},
            "REG": {"Inquiry"},
            "ADM": {"Inquiry"},
            "CSH": {"Inquiry"},
        }
        for code, labels in expected.items():
            office = frappe.db.get_value("CB Office", {"office_code": code}, "name")
            self.assertTrue(office)
            actual = {
                row.request_type_name
                for row in frappe.get_all(
                    "CB Office Request Type",
                    filters={"office": office, "enabled": 1},
                    fields=["request_type_name"],
                )
            }
            self.assertEqual(actual, labels)

    def test_bootstrap_is_idempotent(self):
        bootstrap_offices()
        before = frappe.db.count("CB Office")
        request_types_before = frappe.db.count("CB Office Request Type")
        bootstrap_offices()
        self.assertEqual(frappe.db.count("CB Office"), before)
        self.assertEqual(frappe.db.count("CB Office Request Type"), request_types_before)

    def test_request_type_lookup_is_office_scoped(self):
        bootstrap_offices()
        ict = frappe.db.get_value("CB Office", {"office_code": "ICT"}, "name")
        rows = get_office_request_types(ict)
        self.assertEqual({row.request_type_name for row in rows}, {"Tech Support", "Inquiry"})

    def test_customer_ticket_rejects_request_type_from_another_office(self):
        bootstrap_offices()
        ict = frappe.db.get_value("CB Office", {"office_code": "ICT"}, "name")
        registrar_type = frappe.db.get_value(
            "CB Office Request Type", "REG-INQUIRY", "name"
        )
        ticket = frappe.get_doc(
            {
                "doctype": "HD Ticket",
                "office": ict,
                "request_type": registrar_type,
                "via_customer_portal": 1,
            }
        )
        with self.assertRaises(frappe.ValidationError):
            validate_ticket_office_routing(ticket)

    def test_office_link_permissions_include_select_for_administrators(self):
        from helpdesk.setup.office_bootstrap import add_cbsua_link_permissions

        add_cbsua_link_permissions()
        for doctype in ("CB Office", "CB Office Request Type"):
            for role in ("System Manager", "Administrator"):
                permission = frappe.db.get_value(
                    "DocPerm",
                    {"parent": doctype, "role": role, "permlevel": 0},
                    ["read", "select"],
                    as_dict=True,
                )
                self.assertTrue(permission)
                self.assertTrue(permission.read)
                self.assertTrue(permission.select)
