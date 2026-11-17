import frappe
from frappe import _
from frappe.model.document import Document


class CBOfficeRequestType(Document):
    def validate(self):
        if self.office and not frappe.db.get_value("CB Office", self.office, "enabled"):
            frappe.throw(_("Request types can only be configured for enabled offices."))
