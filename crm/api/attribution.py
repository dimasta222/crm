import frappe
from frappe import _
from frappe.query_builder.functions import Count


@frappe.whitelist()
def get_attribution_summary(from_date=None, to_date=None):
	if not frappe.has_permission("CRM Lead", "read"):
		frappe.throw(_("Not permitted to view lead attribution"), frappe.PermissionError)

	lead = frappe.qb.DocType("CRM Lead")
	query = (
		frappe.qb.from_(lead)
		.select(
			lead.attracted_by,
			lead.first_touch_source,
			lead.first_touch_channel,
			lead.campaign_name,
			lead.tracking_code,
			Count(lead.name).as_("lead_count"),
		)
		.groupby(
			lead.attracted_by,
			lead.first_touch_source,
			lead.first_touch_channel,
			lead.campaign_name,
			lead.tracking_code,
		)
	)
	if from_date:
		query = query.where(lead.creation >= from_date)
	if to_date:
		query = query.where(lead.creation <= to_date)
	return query.run(as_dict=True)
