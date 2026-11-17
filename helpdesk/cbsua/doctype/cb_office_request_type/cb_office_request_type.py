import frappe
from frappe import _
from frappe.model.document import Document


class CBOfficeRequestType(Document):
    def validate(self):
        if self.office and not frappe.db.get_value("CB Office", self.office, "enabled"):
            frappe.throw(_("Request types can only be configured for enabled offices."))
        if self.default_team:
            if not frappe.db.exists("HD Team", self.default_team):
                frappe.throw(_("Select a valid Helpdesk team."))
            team = frappe.get_doc("HD Team", self.default_team)
            allowed_offices = {row.office for row in team.get("offices", []) if row.office}
            if self.office not in allowed_offices:
                frappe.throw(_("The default team must be assigned to this request type's office."))
