import frappe
from frappe.model.document import Document


class HDOffice(Document):
    def validate(self):
        if self.is_default and self.enabled:
            frappe.db.set_value(
                "HD Office", {"is_default": 1, "name": ["!=", self.name]}, "is_default", 0
            )
