# Copyright (c) 2026, Future Studio and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CRMExternalIdentity(Document):
	def validate(self):
		self.identity_key = f"{self.channel}:{self.account_id or ''}:{self.external_user_id}".lower()
		if not (self.lead or self.contact or self.deal):
			frappe.throw(_("An external identity must be linked to a lead, contact, or deal"))
