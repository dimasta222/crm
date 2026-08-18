# Copyright (c) 2026, Future Studio and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CRMChannelConversation(Document):
	def validate(self):
		self.conversation_key = f"{self.channel}:{self.account_id or ''}:{self.external_chat_id}".lower()
		if not (self.lead or self.contact or self.deal):
			frappe.throw(_("A conversation must be linked to a lead, contact, or deal"))
