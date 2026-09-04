# Copyright (c) 2026, Future Studio and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from crm.integrations.telegram.business_connection import normalize_business_username


class CRMChannelSettings(Document):
	def validate(self):
		raw_username = str(self.telegram_business_username or "").strip()
		business_username = normalize_business_username(
			raw_username, raise_on_invalid=bool(raw_username)
		)
		bot_username = normalize_business_username(self.telegram_bot_username)
		if (
			business_username
			and bot_username
			and business_username.casefold() == bot_username.casefold()
		):
			frappe.throw(_("Telegram Business username must differ from the bot username"))
		self.telegram_business_username = business_username or ""
