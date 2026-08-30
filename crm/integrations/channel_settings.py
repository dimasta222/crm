"""Read connector settings without exposing credentials to API responses."""

import frappe


def value(fieldname):
	settings = frappe.get_single("CRM Channel Settings")
	if fieldname.endswith("_token") or fieldname.endswith("_secret"):
		return settings.get_password(fieldname)
	return settings.get(fieldname)
