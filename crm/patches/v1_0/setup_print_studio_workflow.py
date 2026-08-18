import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


LEAD_STATUSES = [
	("New", "Open", "gray", 1),
	("Order Discussion", "Ongoing", "orange", 2),
	("In Progress", "Ongoing", "blue", 3),
	("Ready", "Won", "green", 4),
	("Refused", "Lost", "red", 5),
]

DEAL_STATUSES = [
	("New Order", "Open", "gray", 1, 5),
	("Costing", "Ongoing", "orange", 2, 15),
	("Awaiting Artwork", "On Hold", "amber", 3, 20),
	("Artwork Approval", "Ongoing", "yellow", 4, 30),
	("Awaiting Payment", "On Hold", "pink", 5, 40),
	("Queued", "Ongoing", "cyan", 6, 55),
	("In Production", "Ongoing", "blue", 7, 70),
	("Quality Control", "Ongoing", "violet", 8, 85),
	("Ready for Pickup", "Ongoing", "green", 9, 95),
	("Delivered", "Won", "green", 10, 100),
	("Cancelled", "Lost", "red", 11, 0),
]

LEAD_STATUS_MAP = {
	"Contacted": "Order Discussion",
	"Nurture": "In Progress",
	"Qualified": "Ready",
	"Converted": "Ready",
	"Unqualified": "Refused",
	"Junk": "Refused",
}

DEAL_STATUS_MAP = {
	"New": "New Order",
	"Open": "New Order",
	"Qualification": "Costing",
	"Demo/Making": "In Production",
	"Proposal/Quotation": "Costing",
	"Negotiation": "Awaiting Payment",
	"Ready to Close": "Ready for Pickup",
	"Won": "Delivered",
	"Lost": "Cancelled",
}


def execute():
	_create_contact_attribution_fields()
	_sync_statuses()
	_sync_sidepanel_section("Contact", _contact_attribution_section())
	_sync_data_fields_layout("CRM Lead", _lead_attribution_tab())
	_sync_data_fields_layout("CRM Deal", _deal_production_tab())
	_sync_data_fields_layout("CRM Deal", _deal_payment_tab())
	_sync_data_fields_layout("CRM Deal", _deal_attribution_tab())
	frappe.clear_cache()


def _create_contact_attribution_fields():
	create_custom_fields(
		{
			"Contact": [
				{
					"fieldname": "crm_attribution_section",
					"label": "CRM Attribution",
					"fieldtype": "Section Break",
					"insert_after": "company_name",
				},
				{
					"fieldname": "crm_attracted_by",
					"label": "Attracted By",
					"fieldtype": "Link",
					"options": "User",
					"insert_after": "crm_attribution_section",
				},
				{
					"fieldname": "crm_first_touch_source",
					"label": "First Touch Source",
					"fieldtype": "Link",
					"options": "CRM Lead Source",
					"insert_after": "crm_attracted_by",
				},
				{
					"fieldname": "crm_first_touch_channel",
					"label": "First Touch Channel",
					"fieldtype": "Data",
					"insert_after": "crm_first_touch_source",
				},
				{
					"fieldname": "crm_campaign_name",
					"label": "Campaign",
					"fieldtype": "Data",
					"insert_after": "crm_first_touch_channel",
				},
				{
					"fieldname": "crm_tracking_code",
					"label": "Tracking Code",
					"fieldtype": "Data",
					"read_only": 1,
					"insert_after": "crm_campaign_name",
				},
				{
					"fieldname": "crm_first_touch_at",
					"label": "First Touch At",
					"fieldtype": "Datetime",
					"read_only": 1,
					"insert_after": "crm_tracking_code",
				},
			],
		},
		update=True,
	)


def _sync_statuses():
	for name, status_type, color, position in LEAD_STATUSES:
		_upsert_status("CRM Lead Status", "lead_status", name, status_type, color, position)
	for name, status_type, color, position, probability in DEAL_STATUSES:
		_upsert_status(
			"CRM Deal Status", "deal_status", name, status_type, color, position, probability
		)

	_migrate_status_values("CRM Lead", LEAD_STATUS_MAP)
	_migrate_status_values("CRM Deal", DEAL_STATUS_MAP)
	_migrate_status_logs("CRM Lead", LEAD_STATUS_MAP)
	_migrate_status_logs("CRM Deal", DEAL_STATUS_MAP)

	lead_allowed = {row[0] for row in LEAD_STATUSES}
	deal_allowed = {row[0] for row in DEAL_STATUSES}
	_migrate_unmapped_statuses(
		"CRM Lead Status",
		"CRM Lead",
		lead_allowed,
		{"Open": "New", "Ongoing": "In Progress", "On Hold": "In Progress", "Won": "Ready", "Lost": "Refused"},
	)
	_migrate_unmapped_statuses(
		"CRM Deal Status",
		"CRM Deal",
		deal_allowed,
		{
			"Open": "New Order",
			"Ongoing": "In Production",
			"On Hold": "Awaiting Payment",
			"Won": "Delivered",
			"Lost": "Cancelled",
		},
	)
	_keep_only("CRM Lead Status", lead_allowed)
	_keep_only("CRM Deal Status", deal_allowed)
	_sync_kanban_columns("CRM Lead", [row[0] for row in LEAD_STATUSES])
	_sync_kanban_columns("CRM Deal", [row[0] for row in DEAL_STATUSES])


def _upsert_status(doctype, status_field, name, status_type, color, position, probability=None):
	values = {
		status_field: name,
		"type": status_type,
		"color": color,
		"position": position,
	}
	if probability is not None:
		values["probability"] = probability
	if frappe.db.exists(doctype, name):
		frappe.db.set_value(doctype, name, values, update_modified=False)
	else:
		frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True)


def _migrate_status_values(doctype, mapping):
	for old_status, new_status in mapping.items():
		table = "tabCRM Lead" if doctype == "CRM Lead" else "tabCRM Deal"
		frappe.db.sql(f"update `{table}` set status = %s where status = %s", (new_status, old_status))


def _migrate_unmapped_statuses(status_doctype, parent_doctype, allowed, type_mapping):
	for status in frappe.get_all(status_doctype, fields=["name", "type"]):
		if status.name in allowed:
			continue
		new_status = type_mapping.get(status.type)
		if not new_status:
			continue
		mapping = {status.name: new_status}
		_migrate_status_values(parent_doctype, mapping)
		_migrate_status_logs(parent_doctype, mapping)


def _migrate_status_logs(parenttype, mapping):
	for old_status, new_status in mapping.items():
		frappe.db.sql(
			"""update `tabCRM Status Change Log`
			set `from` = %s where parenttype = %s and `from` = %s""",
			(new_status, parenttype, old_status),
		)
		frappe.db.sql(
			"""update `tabCRM Status Change Log`
			set `to` = %s where parenttype = %s and `to` = %s""",
			(new_status, parenttype, old_status),
		)


def _keep_only(doctype, allowed):
	for name in frappe.get_all(doctype, pluck="name"):
		if name not in allowed:
			frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)


def _sync_kanban_columns(doctype, statuses):
	columns = json.dumps([{"name": status} for status in statuses])
	for view_name in frappe.get_all(
		"CRM View Settings",
		filters={"dt": doctype, "type": "kanban", "column_field": "status"},
		pluck="name",
	):
		frappe.db.set_value(
			"CRM View Settings", view_name, "kanban_columns", columns, update_modified=False
		)


def _sync_data_fields_layout(doctype, tab):
	name = frappe.db.exists("CRM Fields Layout", {"dt": doctype, "type": "Data Fields"})
	if not name:
		return
	doc = frappe.get_doc("CRM Fields Layout", name)
	layout = json.loads(doc.layout or "[]")
	if layout and "sections" not in layout[0]:
		layout = [{"name": "existing_fields", "label": "Details", "sections": layout}]
	if any(existing.get("name") == tab["name"] for existing in layout):
		return
	layout.append(tab)
	doc.layout = json.dumps(layout)
	doc.save(ignore_permissions=True)


def _sync_sidepanel_section(doctype, section):
	name = frappe.db.exists("CRM Fields Layout", {"dt": doctype, "type": "Side Panel"})
	if not name:
		return
	doc = frappe.get_doc("CRM Fields Layout", name)
	layout = json.loads(doc.layout or "[]")
	if any(existing.get("name") == section["name"] for existing in layout):
		return
	layout.append(section)
	doc.layout = json.dumps(layout)
	doc.save(ignore_permissions=True)


def _tab(name, label, sections):
	return {"name": name, "label": label, "sections": sections}


def _section(name, label, fields, opened=True):
	if len(fields) == 1:
		return {
			"name": name,
			"label": label,
			"opened": opened,
			"columns": [{"name": f"{name}_full", "fields": fields}],
		}
	midpoint = (len(fields) + 1) // 2
	return {
		"name": name,
		"label": label,
		"opened": opened,
		"columns": [
			{"name": f"{name}_left", "fields": fields[:midpoint]},
			{"name": f"{name}_right", "fields": fields[midpoint:]},
		],
	}


def _lead_attribution_tab():
	return _tab(
		"print_studio_attribution",
		"Attribution",
		[
			_section(
				"first_touch",
				"First Touch Attribution",
				[
					"attracted_by",
					"first_touch_source",
					"first_touch_channel",
					"campaign_name",
					"tracking_code",
					"first_touch_at",
					"landing_url",
					"utm_source",
					"utm_medium",
					"utm_campaign",
					"utm_content",
					"utm_term",
					"yclid",
					"yandex_client_id",
				],
			)
		],
	)


def _contact_attribution_section():
	return _section(
		"print_studio_attribution",
		"Attribution",
		[
			"crm_attracted_by",
			"crm_first_touch_source",
			"crm_first_touch_channel",
			"crm_campaign_name",
			"crm_tracking_code",
			"crm_first_touch_at",
		],
	)


def _deal_production_tab():
	return _tab(
		"print_studio_production",
		"Production",
		[
			_section(
				"production_details",
				"Production Details",
				["production_deadline", "production_manager", "production_notes"],
			),
			_section("order_items", "Order Items", ["products"]),
			_section("applications", "Applications", ["applications"]),
		],
	)


def _deal_payment_tab():
	return _tab(
		"print_studio_payment",
		"Payment",
		[
			_section(
				"payment_details",
				"Payment Details",
				[
					"order_total",
					"paid_amount",
					"balance_amount",
					"payment_status",
					"payment_terms",
					"payment_method",
					"payment_due_date",
					"last_payment_date",
				],
			)
		],
	)


def _deal_attribution_tab():
	return _lead_attribution_tab() | {"name": "print_studio_deal_attribution"}
