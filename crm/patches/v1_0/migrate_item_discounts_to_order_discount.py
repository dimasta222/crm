from decimal import Decimal, InvalidOperation

import frappe


def execute():
	if not frappe.db.has_column("CRM Deal", "order_discount_percentage"):
		return

	deals = frappe.db.sql(
		"""
		SELECT
			name,
			COALESCE(subtotal, 0) AS subtotal,
			COALESCE(items_subtotal, 0) AS items_subtotal,
			COALESCE(discount_amount, 0) AS discount_amount,
			COALESCE(order_discount_percentage, 0) AS order_discount_percentage
		FROM `tabCRM Deal`
		WHERE COALESCE(discount_amount, 0) > 0
		""",
		as_dict=True,
	)

	for deal in deals:
		if _decimal(deal.order_discount_percentage) > 0:
			continue

		discount = _decimal(deal.discount_amount)
		net_subtotal = _decimal(deal.subtotal)
		gross_subtotal = net_subtotal + discount
		if discount <= 0 or gross_subtotal <= 0:
			continue

		percentage = discount * Decimal("100") / gross_subtotal
		frappe.db.sql(
			"""
			UPDATE `tabCRM Deal`
			SET
				order_discount_percentage = %s,
				items_subtotal = %s,
				subtotal = %s
			WHERE name = %s
			""",
			(
				float(percentage),
				float(_decimal(deal.items_subtotal) + discount),
				float(gross_subtotal),
				deal.name,
			),
		)
		frappe.db.sql(
			"""
			UPDATE `tabCRM Order Item`
			SET
				amount = COALESCE(gross_amount, COALESCE(amount, 0) + COALESCE(discount_amount, 0)),
				discount_percentage = 0,
				discount_amount = 0
			WHERE parenttype = 'CRM Deal' AND parent = %s
			""",
			(deal.name,),
		)


def _decimal(value):
	try:
		return Decimal(str(value or 0))
	except (InvalidOperation, TypeError, ValueError):
		return Decimal("0")
