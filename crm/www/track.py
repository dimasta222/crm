import frappe
from frappe import _

from crm.api.tracking import build_destination, get_tracking_link, register_click


def get_context(context):
	context.no_cache = 1
	code = frappe.form_dict.get("code")
	link = get_tracking_link(code)
	if not link:
		frappe.throw(_("Tracking link not found"), frappe.DoesNotExistError)
	register_click(link)
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = build_destination(link)
	return context
