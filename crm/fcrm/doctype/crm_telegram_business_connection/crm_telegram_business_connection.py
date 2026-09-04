# Copyright (c) 2026, Future Studio and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document

from crm.integrations.telegram.business_connection import (
	ALLOWED_BUSINESS_RIGHTS,
	normalize_business_username,
)


class CRMTelegramBusinessConnection(Document):
	def validate(self):
		self.connection_id = str(self.connection_id or "").strip()
		if not self.connection_id:
			frappe.throw(_("Telegram Business connection ID is required"))
		self.business_username = normalize_business_username(self.business_username) or ""
		try:
			rights = json.loads(self.rights_json or "{}")
		except (TypeError, ValueError):
			frappe.throw(_("Telegram Business rights must be valid JSON"))
		if not isinstance(rights, dict):
			frappe.throw(_("Telegram Business rights must be a JSON object"))
		if set(rights) - ALLOWED_BUSINESS_RIGHTS:
			frappe.throw(_("Telegram Business rights contain unsupported fields"))
		if any(not isinstance(value, bool) for value in rights.values()):
			frappe.throw(_("Telegram Business rights must contain boolean values"))
		self.rights_json = json.dumps(rights, sort_keys=True, separators=(",", ":"))
