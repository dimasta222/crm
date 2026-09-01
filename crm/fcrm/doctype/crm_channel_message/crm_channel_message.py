# Copyright (c) 2026, Future Studio and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from crm.integrations.utils import make_message_key


class CRMChannelMessage(Document):
	def validate(self):
		conversation = frappe.get_cached_doc("CRM Channel Conversation", self.conversation)
		self.message_key = make_message_key(
			conversation.channel,
			conversation.account_id,
			conversation.external_chat_id,
			self.external_message_id or self.name,
		)

	def after_insert(self):
		frappe.db.set_value(
			"CRM Channel Conversation",
			self.conversation,
			{
				"last_message_at": self.sent_at or self.creation,
				"last_message_preview": (self.content or "")[:140],
			},
			update_modified=False,
		)
