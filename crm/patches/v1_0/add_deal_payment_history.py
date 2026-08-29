import json

import frappe
from frappe.utils import get_datetime


def execute():
	_sync_payment_layout()
	_migrate_existing_payments()
	frappe.clear_cache(doctype="CRM Deal")
	frappe.clear_cache(doctype="CRM Deal Payment")


def _sync_payment_layout():
	name = frappe.db.exists("CRM Fields Layout", {"dt": "CRM Deal", "type": "Data Fields"})
	if not name:
		return
	doc = frappe.get_doc("CRM Fields Layout", name)
	layout = json.loads(doc.layout or "[]")
	if any(
		field == "payments"
		for tab in layout
		for section in tab.get("sections", [])
		for column in section.get("columns", [])
		for field in column.get("fields", [])
	):
		return

	payment_tab = next(
		(tab for tab in layout if tab.get("name") == "print_studio_payment" or tab.get("label") == "Payment"),
		None,
	)
	if not payment_tab:
		return
	payment_tab.setdefault("sections", []).append(
		{
			"name": "payment_history",
			"label": "Payment History",
			"opened": True,
			"columns": [{"name": "payment_history_full", "fields": ["payments"]}],
		}
	)
	doc.layout = json.dumps(layout)
	doc.save(ignore_permissions=True)


def _migrate_existing_payments():
	for deal in frappe.get_all(
		"CRM Deal",
		filters={"paid_amount": [">", 0]},
		fields=["name", "paid_amount", "payment_method", "last_payment_date", "modified"],
	):
		if frappe.db.exists("CRM Deal Payment", {"parent": deal.name, "parentfield": "payments"}):
			continue
		payment = frappe.get_doc(
			{
				"doctype": "CRM Deal Payment",
				"parent": deal.name,
				"parenttype": "CRM Deal",
				"parentfield": "payments",
				"idx": 1,
				"paid_at": get_datetime(deal.last_payment_date or deal.modified),
				"amount": deal.paid_amount,
				"payment_method": deal.payment_method,
				"note": "Migrated from the previous paid amount",
			}
		)
		payment.db_insert()
