# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document


class CRMDashboard(Document):
	pass


LEGACY_DEFAULT_MANAGER_DASHBOARD_LAYOUT = '[{"name":"total_leads","type":"number_chart","tooltip":"Total number of leads","layout":{"x":0,"y":0,"w":4,"h":3,"i":"total_leads"}},{"name":"ongoing_deals","type":"number_chart","tooltip":"Total number of ongoing deals","layout":{"x":8,"y":0,"w":4,"h":3,"i":"ongoing_deals"}},{"name":"won_deals","type":"number_chart","tooltip":"Total number of won deals","layout":{"x":12,"y":0,"w":4,"h":3,"i":"won_deals"}},{"name":"average_won_deal_value","type":"number_chart","tooltip":"Average value of won deals","layout":{"x":16,"y":0,"w":4,"h":3,"i":"average_won_deal_value"}},{"name":"average_deal_value","type":"number_chart","tooltip":"Average deal value of ongoing and won deals","layout":{"x":0,"y":2,"w":4,"h":3,"i":"average_deal_value"}},{"name":"average_time_to_close_a_lead","type":"number_chart","tooltip":"Average time taken to close a lead","layout":{"x":4,"y":0,"w":4,"h":3,"i":"average_time_to_close_a_lead"}},{"name":"average_time_to_close_a_deal","type":"number_chart","layout":{"x":4,"y":2,"w":4,"h":3,"i":"average_time_to_close_a_deal"}},{"name":"spacer","type":"spacer","layout":{"x":8,"y":2,"w":12,"h":3,"i":"spacer"}},{"name":"sales_trend","type":"axis_chart","layout":{"x":0,"y":4,"w":10,"h":9,"i":"sales_trend"}},{"name":"forecasted_revenue","type":"axis_chart","layout":{"x":10,"y":4,"w":10,"h":9,"i":"forecasted_revenue"}},{"name":"funnel_conversion","type":"axis_chart","layout":{"x":0,"y":11,"w":10,"h":9,"i":"funnel_conversion"}},{"name":"deals_by_stage_donut","type":"donut_chart","layout":{"x":10,"y":11,"w":10,"h":9,"i":"deals_by_stage_donut"}},{"name":"lost_deal_reasons","type":"axis_chart","layout":{"x":0,"y":32,"w":20,"h":9,"i":"lost_deal_reasons"}},{"name":"leads_by_source","type":"donut_chart","layout":{"x":0,"y":18,"w":10,"h":9,"i":"leads_by_source"}},{"name":"deals_by_source","type":"donut_chart","layout":{"x":10,"y":18,"w":10,"h":9,"i":"deals_by_source"}},{"name":"deals_by_territory","type":"axis_chart","layout":{"x":0,"y":25,"w":10,"h":9,"i":"deals_by_territory"}},{"name":"deals_by_salesperson","type":"axis_chart","layout":{"x":10,"y":25,"w":10,"h":9,"i":"deals_by_salesperson"}}]'

PRINT_STUDIO_DASHBOARD_CARDS_2B2 = [
	{
		"name": "total_order_amount",
		"type": "number_chart",
		"layout": {"x": 0, "y": 0, "w": 4, "h": 3, "i": "total_order_amount"},
	},
	{
		"name": "paid_for_period_orders",
		"type": "number_chart",
		"layout": {"x": 4, "y": 0, "w": 4, "h": 3, "i": "paid_for_period_orders"},
	},
	{
		"name": "awaiting_payment",
		"type": "number_chart",
		"layout": {"x": 8, "y": 0, "w": 4, "h": 3, "i": "awaiting_payment"},
	},
	{
		"name": "current_orders",
		"type": "number_chart",
		"layout": {"x": 12, "y": 0, "w": 4, "h": 3, "i": "current_orders"},
	},
	{
		"name": "completed_orders",
		"type": "number_chart",
		"layout": {"x": 16, "y": 0, "w": 4, "h": 3, "i": "completed_orders"},
	},
	{
		"name": "average_order_value",
		"type": "number_chart",
		"layout": {"x": 0, "y": 2, "w": 4, "h": 3, "i": "average_order_value"},
	},
	{
		"name": "spacer",
		"type": "spacer",
		"layout": {"x": 4, "y": 2, "w": 16, "h": 3, "i": "spacer"},
	},
]

PRINT_STUDIO_OPERATIONAL_DASHBOARD_CARDS = [
	{
		"name": "orders_in_production",
		"type": "number_chart",
		"layout": {"x": 4, "y": 2, "w": 4, "h": 3, "i": "orders_in_production"},
	},
	{
		"name": "orders_ready_for_pickup",
		"type": "number_chart",
		"layout": {"x": 8, "y": 2, "w": 4, "h": 3, "i": "orders_ready_for_pickup"},
	},
	{
		"name": "overdue_orders",
		"type": "number_chart",
		"layout": {"x": 12, "y": 2, "w": 4, "h": 3, "i": "overdue_orders"},
	},
	{
		"name": "unpaid_orders",
		"type": "number_chart",
		"layout": {"x": 16, "y": 2, "w": 4, "h": 3, "i": "unpaid_orders"},
	},
]

PRINT_STUDIO_DASHBOARD_CARDS = [
	*PRINT_STUDIO_DASHBOARD_CARDS_2B2[:-1],
	*PRINT_STUDIO_OPERATIONAL_DASHBOARD_CARDS,
]


def _manager_dashboard_layout(cards):
	legacy_layout = json.loads(LEGACY_DEFAULT_MANAGER_DASHBOARD_LAYOUT)
	return json.dumps(cards + legacy_layout[8:], separators=(",", ":"))


def stage_2b2_manager_dashboard_layout():
	"""Return the exact default layout introduced by dashboard stage 2B-2."""
	return _manager_dashboard_layout(PRINT_STUDIO_DASHBOARD_CARDS_2B2)


def default_manager_dashboard_layout():
	"""
	Returns the default layout for the CRM Manager Dashboard.
	"""
	return _manager_dashboard_layout(PRINT_STUDIO_DASHBOARD_CARDS)


def create_default_manager_dashboard(force=False):
	"""
	Creates the default CRM Manager Dashboard if it does not exist.
	"""
	if not frappe.db.exists("CRM Dashboard", "Manager Dashboard"):
		doc = frappe.new_doc("CRM Dashboard")
		doc.title = "Manager Dashboard"
		doc.layout = default_manager_dashboard_layout()
		doc.insert(ignore_permissions=True)
	else:
		doc = frappe.get_doc("CRM Dashboard", "Manager Dashboard")
		if force:
			doc.layout = default_manager_dashboard_layout()
			doc.save(ignore_permissions=True)
	return doc.layout
