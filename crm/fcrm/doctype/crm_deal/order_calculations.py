# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import frappe
from frappe import _

ORDER_TYPES = {"Product Printing", "DTF Roll", "DTF Pieces", "Combined"}
PRODUCTION_TYPES = {
	"DTF Printing",
	"Screen Printing",
	"Embroidery",
	"Sublimation",
	"Heat Transfer Printing",
	"Artwork Preparation",
	"Combined",
}
PLACEMENTS = {"Chest", "Back", "Sleeve", "Tag / Inner Part", "Other"}
SIZING_MODES = {"Format", "Custom Size", "Quantity Only"}
SHEET_FORMATS = {"A6", "A5", "A4", "A3", "A3+", "A3++"}

NEW_ORDER_TABLES = (
	"order_items",
	"order_applications",
	"dtf_roll_lines",
	"dtf_piece_lines",
)


def uses_new_order_model(deal):
	"""Enable the new model only when at least one new child table has a row."""
	return any(deal.get(table) for table in NEW_ORDER_TABLES)


def ensure_item_keys(deal):
	"""Generate missing keys once and enforce order-local uniqueness."""
	used_keys = set()
	for row in deal.get("order_items") or []:
		stored = _get_stored_order_item(row)
		key = (row.get("item_key") or "").strip()
		stored_key = (stored.get("item_key") if stored else "") or ""
		if stored_key:
			key = stored_key
			row.item_key = key
		elif not key:
			key = _new_item_key(used_keys)
			row.item_key = key

		if key in used_keys:
			frappe.throw(_("Item key {0} must be unique within the order.").format(key))
		used_keys.add(key)


def validate_and_calculate_order(deal):
	"""Validate and calculate a print-studio order without trusting client totals."""
	_validate_order_type(deal)
	ensure_item_keys(deal)
	precision = get_currency_precision(deal)

	items_by_key = _calculate_items(deal, precision)
	_calculate_applications(deal, items_by_key, precision)
	_calculate_roll_lines(deal, precision)
	_calculate_piece_lines(deal, precision)
	_validate_categories(deal)

	items_subtotal = _sum_money((row.amount for row in deal.get("order_items") or []), precision)
	applications_subtotal = _sum_money(
		(row.amount for row in deal.get("order_applications") or []), precision
	)
	dtf_roll_subtotal = _sum_money((row.amount for row in deal.get("dtf_roll_lines") or []), precision)
	dtf_piece_subtotal = _sum_money((row.amount for row in deal.get("dtf_piece_lines") or []), precision)
	discount_amount = _sum_money((row.discount_amount for row in deal.get("order_items") or []), precision)
	subtotal = _sum_money(
		(
			items_subtotal,
			applications_subtotal,
			dtf_roll_subtotal,
			dtf_piece_subtotal,
		),
		precision,
	)
	_set_currency(deal, "items_subtotal", items_subtotal, precision)
	_set_currency(deal, "applications_subtotal", applications_subtotal, precision)
	_set_currency(deal, "dtf_roll_subtotal", dtf_roll_subtotal, precision)
	_set_currency(deal, "dtf_piece_subtotal", dtf_piece_subtotal, precision)
	_set_currency(deal, "discount_amount", discount_amount, precision)
	_set_currency(deal, "subtotal", subtotal, precision)

	_validate_optional_non_negative(deal.get("manual_order_total"), _("Manual Order Total"))
	manual_order_total = round_money(deal.get("manual_order_total"), precision)
	order_total = manual_order_total if deal.get("use_manual_total") else subtotal
	_set_currency(deal, "manual_order_total", manual_order_total, precision)
	_set_currency(deal, "order_total", order_total, precision)
	_set_currency(deal, "deal_value", order_total, precision)


def get_currency_precision(deal=None):
	"""Resolve Currency precision through Frappe settings/meta, with a safe fallback."""
	try:
		precision = int(frappe.get_precision("CRM Deal", "order_total", deal))
		if 0 <= precision <= 9:
			return precision
	except (AttributeError, TypeError, ValueError):
		pass

	try:
		precision = int(frappe.get_meta("CRM Deal").get_field("order_total").precision)
		if 0 <= precision <= 9:
			return precision
	except (AttributeError, TypeError, ValueError):
		pass

	return 2


def round_money(value, precision=2):
	quantum = Decimal(1).scaleb(-precision)
	return _as_decimal(value).quantize(quantum, rounding=ROUND_HALF_UP)


def _set_currency(doc, fieldname, value, precision):
	"""Assign Currency values only after Decimal calculation and rounding."""
	setattr(doc, fieldname, float(round_money(value, precision)))


def _validate_order_type(deal):
	if deal.get("order_type") not in ORDER_TYPES:
		frappe.throw(_("Select a valid Order Type for the print-studio order."))


def _calculate_items(deal, precision):
	items_by_key = {}
	for row in deal.get("order_items") or []:
		label = _("Item {0}").format(row.idx)
		key = (row.get("item_key") or "").strip()
		if not key:
			frappe.throw(_("{0}: Item Key is required.").format(label))
		if key in items_by_key:
			frappe.throw(_("Item key {0} must be unique within the order.").format(key))
		row.item_key = key
		items_by_key[key] = row

		_validate_positive(row.get("qty"), _("{0}: Quantity").format(label))
		if row.get("supply_type") not in {"Customer Item", "Studio Product"}:
			frappe.throw(_("{0}: Select a valid Supply Type.").format(label))

		if row.supply_type == "Customer Item":
			base_rate = Decimal("0")
			manual_rate = Decimal("0")
			rate = Decimal("0")
		else:
			_validate_optional_non_negative(
				row.get("manual_rate"), _("{0}: Manual Rate").format(label)
			)
			if not row.get("product"):
				frappe.throw(_("{0}: Product is required for a Studio Product.").format(label))
			stored = _get_stored_order_item(row)
			catalog_rate = frappe.db.get_value("CRM Product", row.product, "standard_rate")
			if catalog_rate in (None, ""):
				frappe.throw(_("{0}: Studio Product must exist and have a Standard Rate.").format(label))
			base_rate = (
				stored.get("base_rate") if stored and stored.get("product") == row.product else catalog_rate
			)
			_validate_non_negative(base_rate, _("{0}: Base Rate").format(label))
			base_rate = round_money(base_rate, precision)
			manual_rate = round_money(row.get("manual_rate"), precision)
			rate = manual_rate if row.get("use_manual_rate") else base_rate

		_set_currency(row, "base_rate", base_rate, precision)
		_set_currency(row, "manual_rate", manual_rate, precision)
		_set_currency(row, "rate", rate, precision)
		_validate_non_negative(rate, _("{0}: Rate").format(label))
		discount_percentage = (
			Decimal("0")
			if row.supply_type == "Customer Item"
			else _as_decimal(row.get("discount_percentage"))
		)
		if not 0 <= discount_percentage <= 100:
			frappe.throw(_("{0}: Discount Percentage must be between 0 and 100.").format(label))
		row.discount_percentage = discount_percentage
		gross_amount = round_money(_as_decimal(row.qty) * rate, precision)
		discount_amount = round_money(gross_amount * discount_percentage / Decimal("100"), precision)
		amount = round_money(gross_amount - discount_amount, precision)
		_set_currency(row, "gross_amount", gross_amount, precision)
		_set_currency(row, "discount_amount", discount_amount, precision)
		_set_currency(row, "amount", amount, precision)
	return items_by_key


def _calculate_applications(deal, items_by_key, precision):
	for row in deal.get("order_applications") or []:
		label = _("Application {0}").format(row.idx)
		key = (row.get("item_key") or "").strip()
		if not key or key not in items_by_key:
			frappe.throw(_("{0}: Item Key must reference an order item.").format(label))
		row.item_key = key
		if row.get("production_type") not in PRODUCTION_TYPES:
			frappe.throw(_("{0}: Select a valid Production Type.").format(label))
		if row.get("placement") not in PLACEMENTS:
			frappe.throw(_("{0}: Select a valid Placement.").format(label))
		_validate_positive(row.get("qty"), _("{0}: Quantity").format(label))
		if _as_decimal(row.qty) > _as_decimal(items_by_key[key].qty):
			frappe.throw(_("{0}: Quantity cannot exceed the linked item quantity.").format(label))
		_validate_optional_non_negative(row.get("width_cm"), _("{0}: Width").format(label))
		_validate_optional_non_negative(row.get("height_cm"), _("{0}: Height").format(label))
		_validate_non_negative(row.get("rate"), _("{0}: Rate").format(label))
		_validate_optional_non_negative(row.get("manual_amount"), _("{0}: Manual Amount").format(label))
		_validate_optional_non_negative(
			row.get("embroidery_setup_fee"), _("{0}: Embroidery Artwork Preparation").format(label)
		)
		_validate_optional_non_negative(
			row.get("screen_color_count"), _("{0}: Number of Colors").format(label)
		)
		if row.get("fabric_type") and row.fabric_type not in {"White", "Dark", "Colored"}:
			frappe.throw(_("{0}: Select a valid Fabric Type.").format(label))

		# A unit rate must retain kopecks even when order totals are configured
		# with zero decimal places. Round only the completed service line to the
		# order currency precision.
		rate_precision = max(precision, 2)
		rate = round_money(row.get("rate"), rate_precision)
		setup_fee = Decimal("0")
		if row.production_type == "Embroidery":
			setup_fee = round_money(row.get("embroidery_setup_fee"), precision)
			_set_currency(row, "embroidery_setup_fee", setup_fee, precision)

		calculated_amount = round_money(_as_decimal(row.qty) * rate + setup_fee, precision)
		_set_currency(row, "rate", rate, rate_precision)
		_set_currency(row, "calculated_amount", calculated_amount, precision)
		_set_currency(
			row, "amount", _manual_or_calculated_amount(row, calculated_amount, precision), precision
		)


def _calculate_roll_lines(deal, precision):
	for row in deal.get("dtf_roll_lines") or []:
		label = _("DTF Roll Line {0}").format(row.idx)
		_validate_positive(row.get("length_m"), _("{0}: Length").format(label))
		_validate_non_negative(row.get("rate_per_meter"), _("{0}: Rate per Meter").format(label))
		_validate_optional_non_negative(row.get("manual_amount"), _("{0}: Manual Amount").format(label))
		rate_per_meter = round_money(row.get("rate_per_meter"), precision)
		calculated_amount = round_money(_as_decimal(row.length_m) * rate_per_meter, precision)
		_set_currency(row, "rate_per_meter", rate_per_meter, precision)
		_set_currency(row, "calculated_amount", calculated_amount, precision)
		_set_currency(
			row, "amount", _manual_or_calculated_amount(row, calculated_amount, precision), precision
		)


def _calculate_piece_lines(deal, precision):
	for row in deal.get("dtf_piece_lines") or []:
		label = _("DTF Piece Line {0}").format(row.idx)
		mode = row.get("sizing_mode")
		if mode not in SIZING_MODES:
			frappe.throw(_("{0}: Select a valid Sizing Mode.").format(label))
		if mode == "Format":
			if row.get("sheet_format") not in SHEET_FORMATS:
				frappe.throw(_("{0}: Select a valid Sheet Format.").format(label))
			row.width_cm = None
			row.height_cm = None
		elif mode == "Custom Size":
			row.sheet_format = None
			_validate_optional_non_negative(row.get("width_cm"), _("{0}: Width").format(label))
			_validate_optional_non_negative(row.get("height_cm"), _("{0}: Height").format(label))
		else:
			row.sheet_format = None
			row.width_cm = None
			row.height_cm = None

		_validate_positive(row.get("qty"), _("{0}: Quantity").format(label))
		_validate_non_negative(row.get("unit_price"), _("{0}: Unit Price").format(label))
		_validate_optional_non_negative(row.get("manual_amount"), _("{0}: Manual Amount").format(label))
		unit_price = round_money(row.get("unit_price"), precision)
		calculated_amount = round_money(_as_decimal(row.qty) * unit_price, precision)
		_set_currency(row, "unit_price", unit_price, precision)
		_set_currency(row, "calculated_amount", calculated_amount, precision)
		_set_currency(
			row, "amount", _manual_or_calculated_amount(row, calculated_amount, precision), precision
		)


def _manual_or_calculated_amount(row, calculated_amount, precision):
	manual_amount = round_money(row.get("manual_amount"), precision)
	_set_currency(row, "manual_amount", manual_amount, precision)
	if row.get("use_manual_amount"):
		return manual_amount
	return calculated_amount


def _validate_categories(deal):
	has_items = bool(deal.get("order_items"))
	has_applications = bool(deal.get("order_applications"))
	has_roll = bool(deal.get("dtf_roll_lines"))
	has_pieces = bool(deal.get("dtf_piece_lines"))
	order_type = deal.order_type

	if order_type == "Product Printing":
		if not has_items or not has_applications:
			frappe.throw(_("Product Printing requires at least one item and one application."))
		if has_roll or has_pieces:
			frappe.throw(_("Product Printing cannot contain DTF Roll or DTF Piece lines."))
	elif order_type == "DTF Roll":
		if not has_roll:
			frappe.throw(_("DTF Roll requires at least one roll line."))
		if has_items or has_applications or has_pieces:
			frappe.throw(_("DTF Roll cannot contain other order categories."))
	elif order_type == "DTF Pieces":
		if not has_pieces:
			frappe.throw(_("DTF Pieces requires at least one piece line."))
		if has_items or has_applications or has_roll:
			frappe.throw(_("DTF Pieces cannot contain other order categories."))
	else:
		if has_items != has_applications:
			frappe.throw(_("Combined Product Printing requires both items and applications."))
		business_categories = (has_items and has_applications, has_roll, has_pieces)
		if sum(business_categories) < 2:
			frappe.throw(_("Combined requires at least two complete business categories."))


def _get_stored_order_item(row):
	name = row.get("name")
	if not name or str(name).lower().startswith("new-"):
		return None
	return frappe.db.get_value(
		"CRM Order Item",
		name,
		["item_key", "product", "base_rate"],
		as_dict=True,
	)


def _new_item_key(used_keys):
	while True:
		key = f"ITEM-{frappe.generate_hash(length=12).upper()}"
		if key not in used_keys:
			return key


def _sum_money(values, precision):
	return round_money(sum((_as_decimal(value) for value in values), Decimal("0")), precision)


def _as_decimal(value):
	if value in (None, ""):
		return Decimal("0")
	try:
		return Decimal(str(value))
	except (InvalidOperation, TypeError, ValueError):
		frappe.throw(_("Invalid monetary value: {0}").format(value))


def _validate_positive(value, label):
	if value in (None, "") or _as_decimal(value) <= 0:
		frappe.throw(_("{0} must be greater than zero.").format(label))


def _validate_optional_positive(value, label):
	if value not in (None, ""):
		_validate_positive(value, label)


def _validate_non_negative(value, label):
	if value in (None, "") or _as_decimal(value) < 0:
		frappe.throw(_("{0} cannot be negative.").format(label))


def _validate_optional_non_negative(value, label):
	if value not in (None, ""):
		_validate_non_negative(value, label)
