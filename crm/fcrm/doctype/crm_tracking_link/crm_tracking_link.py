# Copyright (c) 2026, Future Studio and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import random_string


class CRMTrackingLink(Document):
	def autoname(self):
		if not self.tracking_code:
			self.tracking_code = random_string(10).lower()
		self.name = self.tracking_code.strip().lower()

	def validate(self):
		self.tracking_code = (self.tracking_code or "").strip().lower()
		if not self.tracking_code:
			frappe.throw(_("Tracking code is required"))
		if not all(character.isalnum() or character in "-_" for character in self.tracking_code):
			frappe.throw(_("Tracking code may contain only letters, numbers, hyphens, and underscores"))
		if not self.is_new() and self.tracking_code != self.name:
			frappe.throw(_("Tracking code cannot be changed after the link is created"))
