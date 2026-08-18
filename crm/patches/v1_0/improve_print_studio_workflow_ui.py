import json

import frappe


def execute():
	configure_currencies()
	configure_data_fields_layout()


def configure_currencies():
	"""Keep USD/EUR available and make RUB the default CRM currency."""
	currencies = {
		"USD": "$",
		"EUR": "€",
		"RUB": "₽",
	}
	currency_meta = frappe.get_meta("Currency")

	for currency, symbol in currencies.items():
		if not frappe.db.exists("Currency", currency):
			doc = frappe.new_doc("Currency")
			doc.currency_name = currency
			doc.symbol = symbol
			if currency_meta.has_field("enabled"):
				doc.enabled = 1
			doc.insert(ignore_permissions=True)
			continue

		values = {"symbol": symbol}
		if currency_meta.has_field("enabled"):
			values["enabled"] = 1
		frappe.db.set_value(
			"Currency", currency, values, update_modified=False
		)

	frappe.db.set_single_value("FCRM Settings", "currency", "RUB")
	frappe.defaults.set_global_default("currency", "RUB")

	# Previous CRM defaults assigned USD automatically. Convert those records to
	# the new base currency, while preserving records explicitly created in EUR.
	for doctype in ("CRM Deal", "CRM Organization"):
		frappe.db.sql(
			f"""
			UPDATE `tab{doctype}`
			SET currency = 'RUB', exchange_rate = 1
			WHERE IFNULL(currency, '') IN ('', 'USD')
			"""
		)

	frappe.clear_cache()


def configure_data_fields_layout():
	name = frappe.db.exists(
		"CRM Fields Layout", {"dt": "CRM Deal", "type": "Data Fields"}
	)
	if not name:
		return

	doc = frappe.get_doc("CRM Fields Layout", name)
	layout = json.loads(doc.layout or "[]")
	changed = False

	for tab in layout:
		if tab.get("name") != "print_studio_production":
			continue
		for section in tab.get("sections", []):
			if section.get("name") not in {"order_items", "applications"}:
				continue
			fields = [
				field
				for column in section.get("columns", [])
				for field in column.get("fields", [])
			]
			section["columns"] = [
				{"name": f'{section["name"]}_full', "fields": fields}
			]
			changed = True

	if changed:
		doc.layout = json.dumps(layout)
		doc.save(ignore_permissions=True)
