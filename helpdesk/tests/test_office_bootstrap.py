import frappe
from frappe.tests.utils import FrappeTestCase

from helpdesk.setup.office_bootstrap import bootstrap_office_teams, bootstrap_offices
from helpdesk.test_utils import make_ticket
from helpdesk.setup.office_routing import (
    get_enabled_offices,
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


    def test_bootstrap_creates_office_teams_and_assigns_the_matching_office(self):
        bootstrap_offices()
        bootstrap_office_teams()
        expected = {
            "ICT Support Team": "ICT",
            "Registrar Support Team": "REG",
            "Admissions Support Team": "ADM",
            "Cashier Support Team": "CSH",
        }
        for team_name, office_code in expected.items():
            team = frappe.get_doc("HD Team", team_name)
            office = frappe.db.get_value(
                "CB Office", {"office_code": office_code}, "name"
            )
            self.assertIn(office, {row.office for row in team.offices})

    def test_office_team_bootstrap_is_idempotent_and_preserves_extra_mappings(self):
        bootstrap_offices()
        bootstrap_office_teams()
        team = frappe.get_doc("HD Team", "ICT Support Team")
        registrar = frappe.db.get_value(
            "CB Office", {"office_code": "REG"}, "name"
        )
        team.append("offices", {"office": registrar})
        team.save(ignore_permissions=True)
        before = frappe.db.count("HD Team")
        bootstrap_office_teams()
        self.assertEqual(frappe.db.count("HD Team"), before)
        refreshed = frappe.get_doc("HD Team", "ICT Support Team")
        self.assertEqual(len(refreshed.offices), 2)


    def test_request_type_default_team_routes_new_ticket(self):
        bootstrap_offices()
        bootstrap_office_teams()
        ict = frappe.db.get_value("CB Office", {"office_code": "ICT"}, "name")
        ticket = make_ticket(
            subject="Office routing integration",
            office=ict,
            request_type="TECH-SUPPORT",
            via_customer_portal=1,
        )
        self.assertEqual(ticket.agent_group, "ICT Support Team")

    def test_all_baseline_request_types_route_to_their_configured_teams(self):
        bootstrap_offices()
        bootstrap_office_teams()
        expected = {
            "TECH-SUPPORT": ("ICT", "ICT Support Team"),
            "ICT-INQUIRY": ("ICT", "ICT Support Team"),
            "REG-INQUIRY": ("REG", "Registrar Support Team"),
            "ADM-INQUIRY": ("ADM", "Admissions Support Team"),
            "CSH-INQUIRY": ("CSH", "Cashier Support Team"),
        }
        for request_type, (office_code, team_name) in expected.items():
            office = frappe.db.get_value(
                "CB Office", {"office_code": office_code}, "name"
            )
            ticket = make_ticket(
                subject=f"Routing {request_type}",
                office=office,
                request_type=request_type,
                via_customer_portal=1,
            )
            self.assertEqual(ticket.agent_group, team_name)

    def test_administrator_reassignment_persists_on_ticket_update(self):
        bootstrap_offices()
        bootstrap_office_teams()
        ict = frappe.db.get_value("CB Office", {"office_code": "ICT"}, "name")
        ticket = make_ticket(
            subject="Administrator reassignment",
            office=ict,
            request_type="TECH-SUPPORT",
            via_customer_portal=1,
        )
        self.assertEqual(ticket.agent_group, "ICT Support Team")
        previous_user = frappe.session.user
        try:
            frappe.set_user("Administrator")
            ticket.agent_group = "Registrar Support Team"
            ticket.save(ignore_permissions=True)
        finally:
            frappe.set_user(previous_user)
        ticket.reload()
        self.assertEqual(ticket.agent_group, "Registrar Support Team")

    def test_missing_default_team_does_not_invent_an_assignment(self):
        bootstrap_offices()
        bootstrap_office_teams()
        frappe.db.set_value(
            "CB Office Request Type", "TECH-SUPPORT", "default_team", None
        )
        ict = frappe.db.get_value("CB Office", {"office_code": "ICT"}, "name")
        ticket = make_ticket(
            subject="Unconfigured office route",
            office=ict,
            request_type="TECH-SUPPORT",
            via_customer_portal=1,
        )
        self.assertFalse(ticket.agent_group)

    def test_explicit_team_selection_is_preserved(self):
        bootstrap_offices()
        bootstrap_office_teams()
        ict = frappe.db.get_value("CB Office", {"office_code": "ICT"}, "name")
        ticket = frappe.get_doc({
            "doctype": "HD Ticket",
            "office": ict,
            "request_type": "TECH-SUPPORT",
            "agent_group": "ICT Support Team",
            "via_customer_portal": 1,
        })
        validate_ticket_office_routing(ticket)
        self.assertEqual(ticket.agent_group, "ICT Support Team")

    def test_administrator_can_override_office_team_default(self):
        bootstrap_offices()
        bootstrap_office_teams()
        ict = frappe.db.get_value("CB Office", {"office_code": "ICT"}, "name")
        ticket = frappe.get_doc({
            "doctype": "HD Ticket",
            "office": ict,
            "request_type": "TECH-SUPPORT",
            "agent_group": "Registrar Support Team",
            "via_customer_portal": 1,
        })
        previous_user = frappe.session.user
        try:
            frappe.set_user("Administrator")
            validate_ticket_office_routing(ticket)
        finally:
            frappe.set_user(previous_user)
        self.assertEqual(ticket.agent_group, "Registrar Support Team")

    def test_non_admin_cannot_override_office_team_mapping(self):
        bootstrap_offices()
        bootstrap_office_teams()
        ict = frappe.db.get_value("CB Office", {"office_code": "ICT"}, "name")
        ticket = frappe.get_doc({
            "doctype": "HD Ticket",
            "office": ict,
            "request_type": "TECH-SUPPORT",
            "agent_group": "Registrar Support Team",
            "via_customer_portal": 1,
        })
        previous_user = frappe.session.user
        try:
            frappe.set_user("office-routing-test@example.com")
            with self.assertRaises(frappe.ValidationError):
                validate_ticket_office_routing(ticket)
        finally:
            frappe.set_user(previous_user)

    def test_request_type_rejects_default_team_from_another_office(self):
        bootstrap_offices()
        bootstrap_office_teams()
        request_type = frappe.get_doc("CB Office Request Type", "TECH-SUPPORT")
        request_type.default_team = "Registrar Support Team"
        with self.assertRaises(frappe.ValidationError):
            request_type.save(ignore_permissions=True)

    def test_bootstrap_is_idempotent(self):
        bootstrap_offices()
        before = frappe.db.count("CB Office")
        request_types_before = frappe.db.count("CB Office Request Type")
        bootstrap_offices()
        self.assertEqual(frappe.db.count("CB Office"), before)
        self.assertEqual(frappe.db.count("CB Office Request Type"), request_types_before)

    def test_enabled_offices_lookup_returns_configured_offices(self):
        bootstrap_offices()
        rows = get_enabled_offices()
        self.assertEqual(
            {row.office_name for row in rows},
            {
                "ICT Office",
                "Registrar's Office",
                "Admissions Office",
                "Cashier's Office",
            },
        )

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
