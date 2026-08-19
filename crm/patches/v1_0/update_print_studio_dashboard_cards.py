import json

import frappe

from crm.fcrm.doctype.crm_dashboard.crm_dashboard import (
	LEGACY_DEFAULT_MANAGER_DASHBOARD_LAYOUT,
	default_manager_dashboard_layout,
)


def execute():
	if not frappe.db.exists("CRM Dashboard", "Manager Dashboard"):
		return

	current_layout = frappe.db.get_value("CRM Dashboard", "Manager Dashboard", "layout")
	updated_layout = get_updated_layout(current_layout)
	if updated_layout is None:
		return

	frappe.db.set_value(
		"CRM Dashboard",
		"Manager Dashboard",
		"layout",
		updated_layout,
		update_modified=False,
	)


def is_legacy_default_layout(layout):
	try:
		current = json.loads(layout or "[]") if isinstance(layout, str) else layout
		legacy = json.loads(LEGACY_DEFAULT_MANAGER_DASHBOARD_LAYOUT)
	except (TypeError, json.JSONDecodeError):
		return False
	return current == legacy


def get_updated_layout(layout):
	if not is_legacy_default_layout(layout):
		return None
	return default_manager_dashboard_layout()
