import frappe
from frappe.model.document import Document


class CBOffice(Document):
    def validate(self):
        if self.is_default and self.enabled:
            frappe.db.set_value(
                "CB Office", {"is_default": 1, "name": ["!=", self.name]}, "is_default", 0
            )
            frappe.db.set_single_value("HD Settings", "default_cb_office", self.name)
