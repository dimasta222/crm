import json
from decimal import Decimal

import frappe
from frappe import _
from frappe.query_builder import Case, DocType
from frappe.query_builder.functions import Avg, Coalesce, Count, Date, DateFormat, IfNull, Sum
from pypika.functions import Function

from crm.fcrm.doctype.crm_dashboard.crm_dashboard import create_default_manager_dashboard
from crm.utils import sales_user_only


# Custom function for TIMESTAMPDIFF (MySQL/MariaDB)
class TimestampDiff(Function):
	def __init__(self, unit, start, end, **kwargs):
		super().__init__("TIMESTAMPDIFF", unit, start, end, **kwargs)


@frappe.whitelist()
def reset_to_default():
	frappe.only_for("System Manager", True)
	create_default_manager_dashboard(force=True)


@frappe.whitelist()
@sales_user_only
def get_dashboard(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""
	Get the dashboard data for the CRM dashboard.
	"""

	if not from_date or not to_date:
		from_date = frappe.utils.get_first_day(from_date or frappe.utils.nowdate())
		to_date = frappe.utils.get_last_day(to_date or frappe.utils.nowdate())

	roles = frappe.get_roles(frappe.session.user)
	is_sales_manager = "Sales Manager" in roles or "System Manager" in roles
	is_sales_user = "Sales User" in roles and not is_sales_manager

	if is_sales_user:
		user = frappe.session.user

	dashboard = frappe.db.exists("CRM Dashboard", "Manager Dashboard")

	layout = []

	if not dashboard:
		layout = json.loads(create_default_manager_dashboard())
		frappe.db.commit()
	else:
		layout = json.loads(frappe.db.get_value("CRM Dashboard", "Manager Dashboard", "layout") or "[]")

	for l in layout:
		method_name = f"get_{l['name']}"
		if hasattr(frappe.get_attr("crm.api.dashboard"), method_name):
			method = getattr(frappe.get_attr("crm.api.dashboard"), method_name)
			l["data"] = method(from_date, to_date, user)
		else:
			l["data"] = None

	return layout


@frappe.whitelist()
@sales_user_only
def get_chart(
	name: str, type: str, from_date: str | None = None, to_date: str | None = None, user: str | None = None
):
	"""
	Get number chart data for the dashboard.
	"""
	if not from_date or not to_date:
		from_date = frappe.utils.get_first_day(from_date or frappe.utils.nowdate())
		to_date = frappe.utils.get_last_day(to_date or frappe.utils.nowdate())

	roles = frappe.get_roles(frappe.session.user)
	is_sales_manager = "Sales Manager" in roles or "System Manager" in roles
	is_sales_user = "Sales User" in roles and not is_sales_manager

	if is_sales_user:
		user = frappe.session.user

	method_name = f"get_{name}"
	if hasattr(frappe.get_attr("crm.api.dashboard"), method_name):
		method = getattr(frappe.get_attr("crm.api.dashboard"), method_name)
		return method(from_date, to_date, user)
	else:
		return {"error": _("Invalid chart name")}


def _period_condition(field, from_date: str, to_date: str):
	return (field >= from_date) & (field < frappe.utils.add_days(to_date, 1))


def _with_deal_owner(condition, Deal, user: str | None):
	if user:
		return condition & (Deal.deal_owner == user)
	return condition


def _number_card(title: str, tooltip: str, value, *, currency: bool = False):
	card = {
		"title": _(title),
		"tooltip": _(tooltip),
		"value": value or 0,
	}
	if currency:
		card["prefix"] = get_base_currency_symbol()
	return card


def get_total_order_amount(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""Return order_total for non-cancelled orders created in the selected period."""
	Deal = DocType("CRM Deal")
	Status = DocType("CRM Deal Status")
	condition = (
		_period_condition(Deal.creation, from_date, to_date)
		& (Status.type != "Lost")
		& (Deal.currency == get_base_currency())
	)
	condition = _with_deal_owner(condition, Deal, user)

	result = (
		frappe.qb.from_(Deal)
		.join(Status)
		.on(Deal.status == Status.name)
		.select(Sum(Deal.order_total).as_("value"))
		.where(condition)
	).run(as_dict=True)[0]

	return _number_card(
		"Total order amount",
		"Sum of order totals for orders created in the selected period",
		result.value,
		currency=True,
	)


def get_paid_for_period_orders(
	from_date: str | None = None, to_date: str | None = None, user: str | None = None
):
	"""Return current paid_amount for orders created in the selected period."""
	Deal = DocType("CRM Deal")
	condition = _period_condition(Deal.creation, from_date, to_date) & (Deal.currency == get_base_currency())
	condition = _with_deal_owner(condition, Deal, user)

	result = (frappe.qb.from_(Deal).select(Sum(Deal.paid_amount).as_("value")).where(condition)).run(
		as_dict=True
	)[0]

	return _number_card(
		"Paid for period orders",
		"Current paid amount for orders created in the selected period",
		result.value,
		currency=True,
	)


def get_awaiting_payment(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""Return positive balances for non-cancelled, non-refunded period orders."""
	Deal = DocType("CRM Deal")
	Status = DocType("CRM Deal Status")
	condition = (
		_period_condition(Deal.creation, from_date, to_date)
		& (Deal.balance_amount > 0)
		& (Status.type != "Lost")
		& (Coalesce(Deal.payment_status, "").notin(["Cancelled", "Refunded"]))
		& (Deal.currency == get_base_currency())
	)
	condition = _with_deal_owner(condition, Deal, user)

	result = (
		frappe.qb.from_(Deal)
		.join(Status)
		.on(Deal.status == Status.name)
		.select(Sum(Deal.balance_amount).as_("value"))
		.where(condition)
	).run(as_dict=True)[0]

	return _number_card(
		"Awaiting Payment",
		"Outstanding balance for orders created in the selected period",
		result.value,
		currency=True,
	)


def get_current_orders(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""Return a current snapshot of unfinished, non-cancelled orders."""
	Deal = DocType("CRM Deal")
	Status = DocType("CRM Deal Status")
	condition = _with_deal_owner(Status.type.notin(["Won", "Lost"]), Deal, user)

	result = (
		frappe.qb.from_(Deal)
		.join(Status)
		.on(Deal.status == Status.name)
		.select(Count(Deal.name).as_("value"))
		.where(condition)
	).run(as_dict=True)[0]

	return _number_card(
		"Current orders (now)",
		"Current number of unfinished and non-cancelled orders",
		result.value,
	)


def get_completed_orders(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""Return won orders whose closed_date is in the selected period."""
	Deal = DocType("CRM Deal")
	Status = DocType("CRM Deal Status")
	condition = _period_condition(Deal.closed_date, from_date, to_date) & (Status.type == "Won")
	condition = _with_deal_owner(condition, Deal, user)

	result = (
		frappe.qb.from_(Deal)
		.join(Status)
		.on(Deal.status == Status.name)
		.select(Count(Deal.name).as_("value"))
		.where(condition)
	).run(as_dict=True)[0]

	return _number_card(
		"Completed orders",
		"Number of completed orders by closure date in the selected period",
		result.value,
	)


def get_average_order_value(
	from_date: str | None = None, to_date: str | None = None, user: str | None = None
):
	"""Return average order_total for non-cancelled orders created in the selected period."""
	Deal = DocType("CRM Deal")
	Status = DocType("CRM Deal Status")
	condition = (
		_period_condition(Deal.creation, from_date, to_date)
		& (Status.type != "Lost")
		& (Deal.currency == get_base_currency())
	)
	condition = _with_deal_owner(condition, Deal, user)

	result = (
		frappe.qb.from_(Deal)
		.join(Status)
		.on(Deal.status == Status.name)
		.select(Avg(Deal.order_total).as_("value"))
		.where(condition)
	).run(as_dict=True)[0]

	return _number_card(
		"Average order value",
		"Average order total for orders created in the selected period",
		result.value,
		currency=True,
	)


def _snapshot_order_count(title: str, tooltip: str, condition, Deal, Status, user: str | None):
	condition = _with_deal_owner(condition, Deal, user)
	result = (
		frappe.qb.from_(Deal)
		.join(Status)
		.on(Deal.status == Status.name)
		.select(Count(Deal.name).as_("value"))
		.where(condition)
	).run(as_dict=True)[0]
	return _number_card(title, tooltip, result.value)


def get_orders_in_production(
	from_date: str | None = None, to_date: str | None = None, user: str | None = None
):
	"""Return the current number of unfinished orders in production."""
	Deal = DocType("CRM Deal")
	Status = DocType("CRM Deal Status")
	condition = (Status.name == "In Production") & Status.type.notin(["Won", "Lost"])
	return _snapshot_order_count(
		"Orders in production (now)",
		"Current number of unfinished orders in production",
		condition,
		Deal,
		Status,
		user,
	)


def get_orders_ready_for_pickup(
	from_date: str | None = None, to_date: str | None = None, user: str | None = None
):
	"""Return the current number of unfinished orders ready for pickup."""
	Deal = DocType("CRM Deal")
	Status = DocType("CRM Deal Status")
	condition = (Status.name == "Ready for Pickup") & Status.type.notin(["Won", "Lost"])
	return _snapshot_order_count(
		"Ready for pickup (now)",
		"Current number of unfinished orders ready for pickup",
		condition,
		Deal,
		Status,
		user,
	)


def get_overdue_orders(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""Return the current number of unfinished orders overdue before today."""
	Deal = DocType("CRM Deal")
	Status = DocType("CRM Deal Status")
	condition = (Deal.production_deadline < frappe.utils.nowdate()) & Status.type.notin(["Won", "Lost"])
	return _snapshot_order_count(
		"Overdue orders (now)",
		"Current number of unfinished orders with a production deadline before today",
		condition,
		Deal,
		Status,
		user,
	)


def get_unpaid_orders(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""Return the current number of unfinished orders with no payment."""
	Deal = DocType("CRM Deal")
	Status = DocType("CRM Deal Status")
	condition = (
		(Deal.order_total > 0) & (Coalesce(Deal.paid_amount, 0) == 0) & Status.type.notin(["Won", "Lost"])
	)
	return _snapshot_order_count(
		"Unpaid orders (now)",
		"Current number of unfinished orders with a positive total and no payment",
		condition,
		Deal,
		Status,
		user,
	)


def _category_value(field):
	"""Return a category expression that normalizes NULL and empty values."""
	return Case().when(field.isnotnull() & (field != ""), field).else_("Not specified")


def _decimal_or_zero(value):
	return value if value is not None else Decimal("0.00")


def _count_axis_chart(title, subtitle, category_title, category_key, data, *, swap_xy=False):
	chart = {
		"data": data or [],
		"title": _(title),
		"subtitle": _(subtitle),
		"xAxis": {"title": _(category_title), "key": category_key, "type": "category"},
		"yAxis": {"title": _("Count")},
		"series": [{"name": "count", "type": "bar", "echartOptions": {"name": _("Count")}}],
	}
	if swap_xy:
		chart["swapXY"] = True
	return chart


def _donut_chart(title, subtitle, category_title, rows, category_key):
	category_column = _(category_title)
	value_column = _("Count")
	return {
		"data": [
			{category_column: _(row.get(category_key) or "Not specified"), value_column: row.get("count") or 0}
			for row in rows
		],
		"title": _(title),
		"subtitle": _(subtitle),
		"categoryColumn": category_column,
		"valueColumn": value_column,
	}


def get_completed_order_amount_by_day(
	from_date: str | None = None, to_date: str | None = None, user: str | None = None
):
	"""Return base-currency totals for won orders grouped by their closure date."""
	Deal = DocType("CRM Deal")
	Status = DocType("CRM Deal Status")
	condition = (
		_period_condition(Deal.closed_date, from_date, to_date)
		& (Status.type == "Won")
		& (Deal.currency == get_base_currency())
	)
	condition = _with_deal_owner(condition, Deal, user)
	rows = (
		frappe.qb.from_(Deal)
		.join(Status)
		.on(Deal.status == Status.name)
		.select(Deal.closed_date.as_("date"), Sum(Deal.order_total).as_("amount"))
		.where(condition)
		.groupby(Deal.closed_date)
		.orderby(Deal.closed_date)
	).run(as_dict=True)
	for row in rows:
		row["date"] = frappe.utils.getdate(row.date).isoformat()
		row["amount"] = _decimal_or_zero(row.amount)

	return {
		"data": rows,
		"title": _("Completed order amount by day"),
		"subtitle": _("Order total for completed orders by closure date"),
		"xAxis": {"title": _("Date"), "key": "date", "type": "time", "timeGrain": "day"},
		"yAxis": {"title": _("Amount") + f" ({get_base_currency_symbol()})"},
		"series": [
			{
				"name": "amount",
				"type": "line",
				"showDataPoints": True,
				"echartOptions": {"name": _("Order amount")},
			}
		],
	}


def get_orders_by_status(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""Return current statuses for orders created in the selected period."""
	Deal = DocType("CRM Deal")
	status = _category_value(Deal.status)
	condition = _with_deal_owner(_period_condition(Deal.creation, from_date, to_date), Deal, user)
	rows = (
		frappe.qb.from_(Deal)
		.select(status.as_("status"), Count(Deal.name).as_("count"))
		.where(condition)
		.groupby(status)
		.orderby(Count(Deal.name), order=frappe.qb.desc)
	).run(as_dict=True)
	return _donut_chart(
		"Current statuses of period orders",
		"Current status distribution for orders created in the selected period",
		"Status",
		rows,
		"status",
	)


def get_orders_by_production_type(
	from_date: str | None = None, to_date: str | None = None, user: str | None = None
):
	"""Return distinct order counts for each application service type."""
	Deal = DocType("CRM Deal")
	Application = DocType("CRM Deal Application")
	service_type = _category_value(Application.service_type)
	count = Count(Deal.name).distinct()
	condition = _with_deal_owner(_period_condition(Deal.creation, from_date, to_date), Deal, user)
	rows = (
		frappe.qb.from_(Deal)
		.left_join(Application)
		.on(
			(Application.parent == Deal.name)
			& (Application.parenttype == "CRM Deal")
			& (Application.parentfield == "applications")
		)
		.select(service_type.as_("service_type"), count.as_("count"))
		.where(condition)
		.groupby(service_type)
		.orderby(count, order=frappe.qb.desc)
	).run(as_dict=True)
	for row in rows:
		row["service_type"] = _(row.get("service_type") or "Not specified")
	return _count_axis_chart(
		"Orders by production type",
		"Production methods for orders created in the selected period",
		"Production Type",
		"service_type",
		rows,
		swap_xy=True,
	)


def get_orders_by_source(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""Return first-touch source with source as a fallback for period orders."""
	Deal = DocType("CRM Deal")
	source = (
		Case()
		.when(Deal.first_touch_source.isnotnull() & (Deal.first_touch_source != ""), Deal.first_touch_source)
		.when(Deal.source.isnotnull() & (Deal.source != ""), Deal.source)
		.else_("Not specified")
	)
	condition = _with_deal_owner(_period_condition(Deal.creation, from_date, to_date), Deal, user)
	rows = (
		frappe.qb.from_(Deal)
		.select(source.as_("source"), Count(Deal.name).as_("count"))
		.where(condition)
		.groupby(source)
		.orderby(Count(Deal.name), order=frappe.qb.desc)
	).run(as_dict=True)
	return _donut_chart(
		"Orders by source",
		"First-touch sources for orders created in the selected period",
		"Source",
		rows,
		"source",
	)


def get_orders_by_acquisition_manager(
	from_date: str | None = None, to_date: str | None = None, user: str | None = None
):
	"""Return period order counts grouped by the acquisition manager."""
	Deal = DocType("CRM Deal")
	User = DocType("User")
	manager = (
		Case()
		.when(User.full_name.isnotnull() & (User.full_name != ""), User.full_name)
		.when(Deal.attracted_by.isnotnull() & (Deal.attracted_by != ""), Deal.attracted_by)
		.else_("Not specified")
	)
	condition = _with_deal_owner(_period_condition(Deal.creation, from_date, to_date), Deal, user)
	rows = (
		frappe.qb.from_(Deal)
		.left_join(User)
		.on(User.name == Deal.attracted_by)
		.select(manager.as_("manager"), Count(Deal.name).as_("count"))
		.where(condition)
		.groupby(Deal.attracted_by, User.full_name)
		.orderby(Count(Deal.name), order=frappe.qb.desc)
	).run(as_dict=True)
	for row in rows:
		row["manager"] = _(row.get("manager") or "Not specified")
	return _count_axis_chart(
		"Orders by acquisition manager",
		"Acquisition managers for orders created in the selected period",
		"Acquisition Manager",
		"manager",
		rows,
		swap_xy=True,
	)


def get_outstanding_balance_by_payment_status(
	from_date: str | None = None, to_date: str | None = None, user: str | None = None
):
	"""Return a current base-currency debt snapshot grouped by payment status."""
	Deal = DocType("CRM Deal")
	Status = DocType("CRM Deal Status")
	payment_status = _category_value(Deal.payment_status)
	condition = (
		(Deal.balance_amount > 0)
		& (Deal.currency == get_base_currency())
		& (Coalesce(Status.type, "") != "Lost")
		& Coalesce(Deal.payment_status, "").notin(["Cancelled", "Refunded"])
	)
	condition = _with_deal_owner(condition, Deal, user)
	rows = (
		frappe.qb.from_(Deal)
		.left_join(Status)
		.on(Deal.status == Status.name)
		.select(payment_status.as_("payment_status"), Sum(Deal.balance_amount).as_("balance"))
		.where(condition)
		.groupby(payment_status)
		.orderby(Sum(Deal.balance_amount), order=frappe.qb.desc)
	).run(as_dict=True)
	for row in rows:
		row["payment_status"] = _(row.get("payment_status") or "Not specified")
		row["balance"] = _decimal_or_zero(row.balance)

	return {
		"data": rows,
		"title": _("Outstanding balance by payment status (now)"),
		"subtitle": _("Current outstanding balance grouped by payment status"),
		"xAxis": {"title": _("Payment Status"), "key": "payment_status", "type": "category"},
		"yAxis": {"title": _("Outstanding Balance") + f" ({get_base_currency_symbol()})"},
		"series": [
			{"name": "balance", "type": "bar", "echartOptions": {"name": _("Outstanding Balance")}}
		],
	}


def get_total_leads(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""
	Get lead count for the dashboard.
	"""
	diff = frappe.utils.date_diff(to_date, from_date)
	if diff == 0:
		diff = 1

	prev_from_date = frappe.utils.add_days(from_date, -diff)
	to_date_plus_one = frappe.utils.add_days(to_date, 1)

	Lead = DocType("CRM Lead")

	# Build conditions for current period
	current_cond = (Lead.creation >= from_date) & (Lead.creation < to_date_plus_one)
	if user:
		current_cond = current_cond & (Lead.lead_owner == user)

	# Build conditions for previous period
	prev_cond = (Lead.creation >= prev_from_date) & (Lead.creation < from_date)
	if user:
		prev_cond = prev_cond & (Lead.lead_owner == user)

	# Build query with CASE expressions
	query = frappe.qb.from_(Lead).select(
		Count(Case().when(current_cond, Lead.name).else_(None)).as_("current_month_leads"),
		Count(Case().when(prev_cond, Lead.name).else_(None)).as_("prev_month_leads"),
	)

	result = query.run(as_dict=True)

	current_month_leads = result[0].current_month_leads or 0
	prev_month_leads = result[0].prev_month_leads or 0

	delta_in_percentage = (
		(current_month_leads - prev_month_leads) / prev_month_leads * 100 if prev_month_leads else 0
	)

	return {
		"title": _("Total leads"),
		"tooltip": _("Total number of leads"),
		"value": current_month_leads,
		"delta": delta_in_percentage,
		"deltaSuffix": "%",
	}


def get_ongoing_deals(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""
	Get ongoing deal count for the dashboard, and also calculate average deal value for ongoing deals.
	"""
	diff = frappe.utils.date_diff(to_date, from_date)
	if diff == 0:
		diff = 1

	prev_from_date = frappe.utils.add_days(from_date, -diff)
	to_date_plus_one = frappe.utils.add_days(to_date, 1)

	Deal = DocType("CRM Deal")
	Status = DocType("CRM Deal Status")

	# Build conditions for current period
	current_cond = (
		(Deal.creation >= from_date)
		& (Deal.creation < to_date_plus_one)
		& (Status.type.notin(["Won", "Lost"]))
	)
	if user:
		current_cond = current_cond & (Deal.deal_owner == user)

	# Build conditions for previous period
	prev_cond = (
		(Deal.creation >= prev_from_date) & (Deal.creation < from_date) & (Status.type.notin(["Won", "Lost"]))
	)
	if user:
		prev_cond = prev_cond & (Deal.deal_owner == user)

	# Build query with CASE expressions
	query = (
		frappe.qb.from_(Deal)
		.join(Status)
		.on(Deal.status == Status.name)
		.select(
			Count(Case().when(current_cond, Deal.name).else_(None)).as_("current_month_deals"),
			Count(Case().when(prev_cond, Deal.name).else_(None)).as_("prev_month_deals"),
		)
	)

	result = query.run(as_dict=True)

	current_month_deals = result[0].current_month_deals or 0
	prev_month_deals = result[0].prev_month_deals or 0

	delta_in_percentage = (
		(current_month_deals - prev_month_deals) / prev_month_deals * 100 if prev_month_deals else 0
	)

	return {
		"title": _("Ongoing deals"),
		"tooltip": _("Total number of non won/lost deals"),
		"value": current_month_deals,
		"delta": delta_in_percentage,
		"deltaSuffix": "%",
	}


def get_average_ongoing_deal_value(
	from_date: str | None = None, to_date: str | None = None, user: str | None = None
):
	"""
	Get ongoing deal count for the dashboard, and also calculate average deal value for ongoing deals.
	"""
	diff = frappe.utils.date_diff(to_date, from_date)
	if diff == 0:
		diff = 1

	prev_from_date = frappe.utils.add_days(from_date, -diff)
	to_date_plus_one = frappe.utils.add_days(to_date, 1)

	Deal = DocType("CRM Deal")
	Status = DocType("CRM Deal Status")

	# Build conditions for current period
	current_cond = (
		(Deal.creation >= from_date)
		& (Deal.creation < to_date_plus_one)
		& (Status.type.notin(["Won", "Lost"]))
	)
	if user:
		current_cond = current_cond & (Deal.deal_owner == user)

	# Build conditions for previous period
	prev_cond = (
		(Deal.creation >= prev_from_date) & (Deal.creation < from_date) & (Status.type.notin(["Won", "Lost"]))
	)
	if user:
		prev_cond = prev_cond & (Deal.deal_owner == user)

	# Calculate deal value with exchange rate
	deal_value_expr = Deal.deal_value * IfNull(Deal.exchange_rate, 1)

	# Build query with CASE expressions
	query = (
		frappe.qb.from_(Deal)
		.join(Status)
		.on(Deal.status == Status.name)
		.select(
			Avg(Case().when(current_cond, deal_value_expr).else_(None)).as_("current_month_avg_value"),
			Avg(Case().when(prev_cond, deal_value_expr).else_(None)).as_("prev_month_avg_value"),
		)
	)

	result = query.run(as_dict=True)

	current_month_avg_value = result[0].current_month_avg_value or 0
	prev_month_avg_value = result[0].prev_month_avg_value or 0

	avg_value_delta = current_month_avg_value - prev_month_avg_value if prev_month_avg_value else 0

	return {
		"title": _("Avg. ongoing deal value"),
		"tooltip": _("Average deal value of non won/lost deals"),
		"value": current_month_avg_value,
		"delta": avg_value_delta,
		"prefix": get_base_currency_symbol(),
	}


def get_won_deals(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""
	Get won deal count for the dashboard, and also calculate average deal value for won deals.
	"""
	diff = frappe.utils.date_diff(to_date, from_date)
	if diff == 0:
		diff = 1

	prev_from_date = frappe.utils.add_days(from_date, -diff)
	to_date_plus_one = frappe.utils.add_days(to_date, 1)

	Deal = DocType("CRM Deal")
	Status = DocType("CRM Deal Status")

	# Build conditions for current period
	current_cond = (
		(Deal.closed_date >= from_date) & (Deal.closed_date < to_date_plus_one) & (Status.type == "Won")
	)
	if user:
		current_cond = current_cond & (Deal.deal_owner == user)

	# Build conditions for previous period
	prev_cond = (Deal.closed_date >= prev_from_date) & (Deal.closed_date < from_date) & (Status.type == "Won")
	if user:
		prev_cond = prev_cond & (Deal.deal_owner == user)

	# Build query with CASE expressions
	query = (
		frappe.qb.from_(Deal)
		.join(Status)
		.on(Deal.status == Status.name)
		.select(
			Count(Case().when(current_cond, Deal.name).else_(None)).as_("current_month_deals"),
			Count(Case().when(prev_cond, Deal.name).else_(None)).as_("prev_month_deals"),
		)
	)

	result = query.run(as_dict=True)

	current_month_deals = result[0].current_month_deals or 0
	prev_month_deals = result[0].prev_month_deals or 0

	delta_in_percentage = (
		(current_month_deals - prev_month_deals) / prev_month_deals * 100 if prev_month_deals else 0
	)

	return {
		"title": _("Won deals"),
		"tooltip": _("Total number of won deals based on its closure date"),
		"value": current_month_deals,
		"delta": delta_in_percentage,
		"deltaSuffix": "%",
	}


def get_average_won_deal_value(
	from_date: str | None = None, to_date: str | None = None, user: str | None = None
):
	"""
	Get won deal count for the dashboard, and also calculate average deal value for won deals.
	"""
	diff = frappe.utils.date_diff(to_date, from_date)
	if diff == 0:
		diff = 1

	prev_from_date = frappe.utils.add_days(from_date, -diff)
	to_date_plus_one = frappe.utils.add_days(to_date, 1)

	Deal = DocType("CRM Deal")
	Status = DocType("CRM Deal Status")

	# Build conditions for current period
	current_cond = (
		(Deal.closed_date >= from_date) & (Deal.closed_date < to_date_plus_one) & (Status.type == "Won")
	)
	if user:
		current_cond = current_cond & (Deal.deal_owner == user)

	# Build conditions for previous period
	prev_cond = (Deal.closed_date >= prev_from_date) & (Deal.closed_date < from_date) & (Status.type == "Won")
	if user:
		prev_cond = prev_cond & (Deal.deal_owner == user)

	# Calculate deal value with exchange rate
	deal_value_expr = Deal.deal_value * IfNull(Deal.exchange_rate, 1)

	# Build query with CASE expressions
	query = (
		frappe.qb.from_(Deal)
		.join(Status)
		.on(Deal.status == Status.name)
		.select(
			Avg(Case().when(current_cond, deal_value_expr).else_(None)).as_("current_month_avg_value"),
			Avg(Case().when(prev_cond, deal_value_expr).else_(None)).as_("prev_month_avg_value"),
		)
	)

	result = query.run(as_dict=True)

	current_month_avg_value = result[0].current_month_avg_value or 0
	prev_month_avg_value = result[0].prev_month_avg_value or 0

	avg_value_delta = current_month_avg_value - prev_month_avg_value if prev_month_avg_value else 0

	return {
		"title": _("Avg. won deal value"),
		"tooltip": _("Average deal value of won deals"),
		"value": current_month_avg_value,
		"delta": avg_value_delta,
		"prefix": get_base_currency_symbol(),
	}


def get_average_deal_value(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""
	Get average deal value for the dashboard.
	"""
	diff = frappe.utils.date_diff(to_date, from_date)
	if diff == 0:
		diff = 1

	prev_from_date = frappe.utils.add_days(from_date, -diff)
	to_date_plus_one = frappe.utils.add_days(to_date, 1)

	Deal = DocType("CRM Deal")
	Status = DocType("CRM Deal Status")

	# Build conditions for current period
	current_cond = (Deal.creation >= from_date) & (Deal.creation < to_date_plus_one) & (Status.type != "Lost")
	if user:
		current_cond = current_cond & (Deal.deal_owner == user)

	# Build conditions for previous period
	prev_cond = (Deal.creation >= prev_from_date) & (Deal.creation < from_date) & (Status.type != "Lost")
	if user:
		prev_cond = prev_cond & (Deal.deal_owner == user)

	# Calculate deal value with exchange rate
	deal_value_expr = Deal.deal_value * IfNull(Deal.exchange_rate, 1)

	# Build query with CASE expressions
	query = (
		frappe.qb.from_(Deal)
		.join(Status)
		.on(Deal.status == Status.name)
		.select(
			Avg(Case().when(current_cond, deal_value_expr).else_(None)).as_("current_month_avg"),
			Avg(Case().when(prev_cond, deal_value_expr).else_(None)).as_("prev_month_avg"),
		)
	)

	result = query.run(as_dict=True)

	current_month_avg = result[0].current_month_avg or 0
	prev_month_avg = result[0].prev_month_avg or 0

	delta = current_month_avg - prev_month_avg if prev_month_avg else 0

	return {
		"title": _("Avg. deal value"),
		"tooltip": _("Average deal value of ongoing & won deals"),
		"value": current_month_avg,
		"prefix": get_base_currency_symbol(),
		"delta": delta,
		"deltaSuffix": "%",
	}


def get_average_time_to_close_a_lead(
	from_date: str | None = None, to_date: str | None = None, user: str | None = None
):
	"""
	Get average time to close deals for the dashboard.
	"""
	diff = frappe.utils.date_diff(to_date, from_date)
	if diff == 0:
		diff = 1

	prev_from_date = frappe.utils.add_days(from_date, -diff)
	to_date_plus_one = frappe.utils.add_days(to_date, 1)
	prev_to_date = from_date

	Deal = DocType("CRM Deal")
	Status = DocType("CRM Deal Status")
	Lead = DocType("CRM Lead")

	# Base condition: closed_date is not null and status type is Won
	base_cond = (Deal.closed_date.isnotnull()) & (Status.type == "Won")
	if user:
		base_cond = base_cond & (Deal.deal_owner == user)

	# Current period condition
	current_cond = (Deal.closed_date >= from_date) & (Deal.closed_date < to_date_plus_one)

	# Previous period condition
	prev_cond = (Deal.closed_date >= prev_from_date) & (Deal.closed_date < prev_to_date)

	# Calculate time difference from lead/deal creation to deal closure
	time_diff = TimestampDiff(
		frappe.qb.terms.LiteralValue("DAY"), Coalesce(Lead.creation, Deal.creation), Deal.closed_date
	)

	# Build query
	query = (
		frappe.qb.from_(Deal)
		.join(Status)
		.on(Deal.status == Status.name)
		.left_join(Lead)
		.on(Deal.lead == Lead.name)
		.where(base_cond)
		.select(
			Avg(Case().when(current_cond, time_diff).else_(None)).as_("current_avg_lead"),
			Avg(Case().when(prev_cond, time_diff).else_(None)).as_("prev_avg_lead"),
		)
	)

	result = query.run(as_dict=True)

	current_avg_lead = result[0].current_avg_lead or 0
	prev_avg_lead = result[0].prev_avg_lead or 0
	delta_lead = current_avg_lead - prev_avg_lead if prev_avg_lead else 0

	return {
		"title": _("Avg. time to close a lead"),
		"tooltip": _("Average time taken from lead creation to deal closure"),
		"value": current_avg_lead,
		"suffix": " " + _("days"),
		"delta": delta_lead,
		"deltaSuffix": " " + _("days"),
		"negativeIsBetter": True,
	}


def get_average_time_to_close_a_deal(
	from_date: str | None = None, to_date: str | None = None, user: str | None = None
):
	"""
	Get average time to close deals for the dashboard.
	"""
	diff = frappe.utils.date_diff(to_date, from_date)
	if diff == 0:
		diff = 1

	prev_from_date = frappe.utils.add_days(from_date, -diff)
	to_date_plus_one = frappe.utils.add_days(to_date, 1)
	prev_to_date = from_date

	Deal = DocType("CRM Deal")
	Status = DocType("CRM Deal Status")
	Lead = DocType("CRM Lead")

	# Base condition: closed_date is not null and status type is Won
	base_cond = (Deal.closed_date.isnotnull()) & (Status.type == "Won")
	if user:
		base_cond = base_cond & (Deal.deal_owner == user)

	# Current period condition
	current_cond = (Deal.closed_date >= from_date) & (Deal.closed_date < to_date_plus_one)

	# Previous period condition
	prev_cond = (Deal.closed_date >= prev_from_date) & (Deal.closed_date < prev_to_date)

	# Calculate time difference from deal creation to deal closure
	time_diff = TimestampDiff(frappe.qb.terms.LiteralValue("DAY"), Deal.creation, Deal.closed_date)

	# Build query
	query = (
		frappe.qb.from_(Deal)
		.join(Status)
		.on(Deal.status == Status.name)
		.left_join(Lead)
		.on(Deal.lead == Lead.name)
		.where(base_cond)
		.select(
			Avg(Case().when(current_cond, time_diff).else_(None)).as_("current_avg_deal"),
			Avg(Case().when(prev_cond, time_diff).else_(None)).as_("prev_avg_deal"),
		)
	)

	result = query.run(as_dict=True)

	current_avg_deal = result[0].current_avg_deal or 0
	prev_avg_deal = result[0].prev_avg_deal or 0
	delta_deal = current_avg_deal - prev_avg_deal if prev_avg_deal else 0

	return {
		"title": _("Avg. time to close a deal"),
		"tooltip": _("Average time taken from deal creation to deal closure"),
		"value": current_avg_deal,
		"suffix": " " + _("days"),
		"delta": delta_deal,
		"deltaSuffix": " " + _("days"),
		"negativeIsBetter": True,
	}


def get_sales_trend(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""
	Get sales trend data for the dashboard.
	[
		{ date: new Date('2024-05-01'), leads: 45, deals: 23, won_deals: 12 },
		{ date: new Date('2024-05-02'), leads: 50, deals: 30, won_deals: 15 },
		...
	]
	"""
	if not from_date or not to_date:
		from_date = frappe.utils.get_first_day(from_date or frappe.utils.nowdate())
		to_date = frappe.utils.get_last_day(to_date or frappe.utils.nowdate())

	Lead = DocType("CRM Lead")
	Deal = DocType("CRM Deal")
	Status = DocType("CRM Deal Status")

	# Build leads query
	leads_query = (
		frappe.qb.from_(Lead)
		.select(
			Date(Lead.creation).as_("date"),
			Count("*").as_("leads"),
			frappe.qb.terms.ValueWrapper(0).as_("deals"),
			frappe.qb.terms.ValueWrapper(0).as_("won_deals"),
		)
		.where(Date(Lead.creation).between(from_date, to_date))
	)

	if user:
		leads_query = leads_query.where(Lead.lead_owner == user)

	leads_query = leads_query.groupby(Date(Lead.creation))

	# Build deals query
	deals_query = (
		frappe.qb.from_(Deal)
		.join(Status)
		.on(Deal.status == Status.name)
		.select(
			Date(Deal.creation).as_("date"),
			frappe.qb.terms.ValueWrapper(0).as_("leads"),
			Count("*").as_("deals"),
			Sum(Case().when(Status.type == "Won", 1).else_(0)).as_("won_deals"),
		)
		.where(Date(Deal.creation).between(from_date, to_date))
	)

	if user:
		deals_query = deals_query.where(Deal.deal_owner == user)

	deals_query = deals_query.groupby(Date(Deal.creation))

	# Combine with UNION ALL and aggregate by date
	union_query = leads_query.union_all(deals_query)

	# Wrap in outer query to aggregate by date
	daily = (
		frappe.qb.from_(union_query)
		.select(
			DateFormat(union_query.date, "%Y-%m-%d").as_("date"),
			Sum(union_query.leads).as_("leads"),
			Sum(union_query.deals).as_("deals"),
			Sum(union_query.won_deals).as_("won_deals"),
		)
		.groupby(union_query.date)
		.orderby(union_query.date)
	)

	result = daily.run(as_dict=True)

	sales_trend = [
		{
			"date": frappe.utils.get_datetime(row.date).strftime("%Y-%m-%d"),
			"leads": row.leads or 0,
			"deals": row.deals or 0,
			"won_deals": row.won_deals or 0,
		}
		for row in result
	]

	return {
		"data": sales_trend,
		"title": _("Sales trend"),
		"subtitle": _("Daily performance of leads, deals, and wins"),
		"xAxis": {
			"title": _("Date"),
			"key": "date",
			"type": "time",
			"timeGrain": "day",
		},
		"yAxis": {
			"title": _("Count"),
		},
		"series": [
			{"name": "leads", "type": "line", "showDataPoints": True, "echartOptions": {"name": _("Leads")}},
			{"name": "deals", "type": "line", "showDataPoints": True, "echartOptions": {"name": _("Deals")}},
			{"name": "won_deals", "type": "line", "showDataPoints": True, "echartOptions": {"name": _("Won Deals")}},
		],
	}


def get_forecasted_revenue(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""
	Get forecasted revenue for the dashboard.
	[
		{ date: new Date('2024-05-01'), forecasted: 1200000, actual: 980000 },
		{ date: new Date('2024-06-01'), forecasted: 1350000, actual: 1120000 },
		{ date: new Date('2024-07-01'), forecasted: 1600000, actual: "" },
		{ date: new Date('2024-08-01'), forecasted: 1500000, actual: "" },
		...
	]
	"""
	# Using Frappe Query Builder with CASE expressions
	CRMDeal = DocType("CRM Deal")
	CRMDealStatus = DocType("CRM Deal Status")

	# Calculate the date 12 months ago
	twelve_months_ago = frappe.utils.add_months(frappe.utils.nowdate(), -12)

	forecasted_value = (
		Case()
		.when(CRMDealStatus.type == "Lost", CRMDeal.expected_deal_value * IfNull(CRMDeal.exchange_rate, 1))
		.else_(
			CRMDeal.expected_deal_value
			* IfNull(CRMDeal.probability, 0)
			/ 100
			* IfNull(CRMDeal.exchange_rate, 1)
		)
	)

	actual_value = (
		Case()
		.when(CRMDealStatus.type == "Won", CRMDeal.deal_value * IfNull(CRMDeal.exchange_rate, 1))
		.else_(0)
	)

	query = (
		frappe.qb.from_(CRMDeal)
		.join(CRMDealStatus)
		.on(CRMDeal.status == CRMDealStatus.name)
		.select(
			DateFormat(CRMDeal.expected_closure_date, "%Y-%m").as_("month"),
			Sum(forecasted_value).as_("forecasted"),
			Sum(actual_value).as_("actual"),
		)
		.where(CRMDeal.expected_closure_date >= twelve_months_ago)
		.groupby(DateFormat(CRMDeal.expected_closure_date, "%Y-%m"))
		.orderby(DateFormat(CRMDeal.expected_closure_date, "%Y-%m"))
	)

	if user:
		query = query.where(CRMDeal.deal_owner == user)

	result = query.run(as_dict=True)

	for row in result:
		row["month"] = frappe.utils.get_datetime(row["month"]).strftime("%Y-%m-01")
		row["forecasted"] = row["forecasted"] or ""
		row["actual"] = row["actual"] or ""

	return {
		"data": result or [],
		"title": _("Forecasted revenue"),
		"subtitle": _("Projected vs actual revenue based on deal probability"),
		"xAxis": {
			"title": _("Month"),
			"key": "month",
			"type": "time",
			"timeGrain": "month",
		},
		"yAxis": {
			"title": _("Revenue") + f" ({get_base_currency_symbol()})",
		},
		"series": [
			{"name": "forecasted", "type": "line", "showDataPoints": True, "echartOptions": {"name": _("Forecasted")}},
			{"name": "actual", "type": "line", "showDataPoints": True, "echartOptions": {"name": _("Actual")}},
		],
	}


def get_funnel_conversion(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""
	Get funnel conversion data for the dashboard.
	[
		{ stage: 'Leads', count: 120 },
		{ stage: 'Qualification', count: 100 },
		{ stage: 'Negotiation', count: 80 },
		{ stage: 'Ready to Close', count: 60 },
		{ stage: 'Won', count: 30 },
		...
	]
	"""
	lead_conds = ""
	deal_conds = ""

	if not from_date or not to_date:
		from_date = frappe.utils.get_first_day(from_date or frappe.utils.nowdate())
		to_date = frappe.utils.get_last_day(to_date or frappe.utils.nowdate())

	lead_filters = {"from": from_date, "to": to_date}
	deal_filters = {"from": from_date, "to": to_date}

	if user:
		lead_conds += " AND lead_owner = %(user)s"
		deal_conds += " AND deal_owner = %(user)s"
		lead_filters["user"] = user
		deal_filters["user"] = user

	result = []

	# Get total leads using Query Builder
	CRMLead = DocType("CRM Lead")

	query = (
		frappe.qb.from_(CRMLead)
		.select(Count("*").as_("count"))
		.where(Date(CRMLead.creation).between(from_date, to_date))
	)

	if user:
		query = query.where(CRMLead.lead_owner == user)

	total_leads = query.run(as_dict=True)
	total_leads_count = total_leads[0].count if total_leads else 0

	result.append({"stage": _("Leads"), "count": total_leads_count})

	result += get_deal_status_change_counts(from_date, to_date, deal_conds, deal_filters)
	for row in result:
		row["stage"] = _(row.get("stage") or "")

	return {
		"data": result or [],
		"title": _("Funnel conversion"),
		"subtitle": _("Lead to deal conversion pipeline"),
		"xAxis": {
			"title": _("Stage"),
			"key": "stage",
			"type": "category",
		},
		"yAxis": {
			"title": _("Count"),
		},
		"swapXY": True,
		"series": [
			{
				"name": "count",
				"type": "bar",
				"echartOptions": {
					"name": _("Count"),
					"colorBy": "data",
				},
			},
		],
	}


def get_deals_by_stage_axis(
	from_date: str | None = None, to_date: str | None = None, user: str | None = None
):
	"""
	Get deal data by stage for the dashboard.
	[
		{ stage: 'Prospecting', count: 120 },
		{ stage: 'Negotiation', count: 45 },
		...
	]
	"""
	if not from_date or not to_date:
		from_date = frappe.utils.get_first_day(from_date or frappe.utils.nowdate())
		to_date = frappe.utils.get_last_day(to_date or frappe.utils.nowdate())

	# Using Frappe Query Builder with NOT IN clause
	CRMDeal = DocType("CRM Deal")
	CRMDealStatus = DocType("CRM Deal Status")

	query = (
		frappe.qb.from_(CRMDeal)
		.join(CRMDealStatus)
		.on(CRMDeal.status == CRMDealStatus.name)
		.select(CRMDeal.status.as_("stage"), Count("*").as_("count"), CRMDealStatus.type.as_("status_type"))
		.where((Date(CRMDeal.creation).between(from_date, to_date)) & (CRMDealStatus.type.notin(["Lost"])))
		.groupby(CRMDeal.status)
		.orderby(Count("*"), order=frappe.qb.desc)
	)

	if user:
		query = query.where(CRMDeal.deal_owner == user)

	result = query.run(as_dict=True)
	for row in result:
		row["stage"] = _(row.get("stage") or "")

	return {
		"data": result or [],
		"title": _("Deals by ongoing & won stage"),
		"xAxis": {
			"title": _("Stage"),
			"key": "stage",
			"type": "category",
		},
		"yAxis": {"title": _("Count")},
		"series": [
			{"name": "count", "type": "bar", "echartOptions": {"name": _("Count")}},
		],
	}


def get_deals_by_stage_donut(
	from_date: str | None = None, to_date: str | None = None, user: str | None = None
):
	"""
	Get deal data by stage for the dashboard.
	[
		{ stage: 'Prospecting', count: 120 },
		{ stage: 'Negotiation', count: 45 },
		...
	]
	"""
	if not from_date or not to_date:
		from_date = frappe.utils.get_first_day(from_date or frappe.utils.nowdate())
		to_date = frappe.utils.get_last_day(to_date or frappe.utils.nowdate())

	# Using Frappe Query Builder with JOIN
	CRMDeal = DocType("CRM Deal")
	CRMDealStatus = DocType("CRM Deal Status")

	query = (
		frappe.qb.from_(CRMDeal)
		.join(CRMDealStatus)
		.on(CRMDeal.status == CRMDealStatus.name)
		.select(CRMDeal.status.as_("stage"), Count("*").as_("count"), CRMDealStatus.type.as_("status_type"))
		.where(Date(CRMDeal.creation).between(from_date, to_date))
		.groupby(CRMDeal.status)
		.orderby(Count("*"), order=frappe.qb.desc)
	)

	if user:
		query = query.where(CRMDeal.deal_owner == user)

	result = query.run(as_dict=True)
	category_column = _("Stage")
	value_column = _("Count")
	localized_result = [
		{category_column: _(row.get("stage") or ""), value_column: row.get("count") or 0}
		for row in result
	]

	return {
		"data": localized_result,
		"title": _("Deals by stage"),
		"subtitle": _("Current pipeline distribution"),
		"categoryColumn": category_column,
		"valueColumn": value_column,
	}


def get_lost_deal_reasons(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""
	Get lost deal reasons for the dashboard.
	[
		{ reason: 'Price too high', count: 20 },
		{ reason: 'Competitor won', count: 15 },
		...
	]
	"""
	if not from_date or not to_date:
		from_date = frappe.utils.get_first_day(from_date or frappe.utils.nowdate())
		to_date = frappe.utils.get_last_day(to_date or frappe.utils.nowdate())

	# Using Frappe Query Builder with JOIN
	CRMDeal = DocType("CRM Deal")
	CRMDealStatus = DocType("CRM Deal Status")

	query = (
		frappe.qb.from_(CRMDeal)
		.join(CRMDealStatus)
		.on(CRMDeal.status == CRMDealStatus.name)
		.select(CRMDeal.lost_reason.as_("reason"), Count("*").as_("count"))
		.where((Date(CRMDeal.creation).between(from_date, to_date)) & (CRMDealStatus.type == "Lost"))
		.groupby(CRMDeal.lost_reason)
		.having((CRMDeal.lost_reason.isnotnull()) & (CRMDeal.lost_reason != ""))
		.orderby(Count("*"), order=frappe.qb.desc)
	)

	if user:
		query = query.where(CRMDeal.deal_owner == user)

	result = query.run(as_dict=True)

	return {
		"data": result or [],
		"title": _("Lost deal reasons"),
		"subtitle": _("Common reasons for losing deals"),
		"xAxis": {
			"title": _("Reason"),
			"key": "reason",
			"type": "category",
		},
		"yAxis": {
			"title": _("Count"),
		},
		"series": [
			{"name": "count", "type": "bar", "echartOptions": {"name": _("Count")}},
		],
	}


def get_leads_by_source(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""
	Get lead data by source for the dashboard.
	[
		{ source: 'Website', count: 120 },
		{ source: 'Referral', count: 45 },
		...
	]
	"""
	if not from_date or not to_date:
		from_date = frappe.utils.get_first_day(from_date or frappe.utils.nowdate())
		to_date = frappe.utils.get_last_day(to_date or frappe.utils.nowdate())

	# Using Frappe Query Builder (safer, more maintainable)
	CRMLead = DocType("CRM Lead")

	query = (
		frappe.qb.from_(CRMLead)
		.select(IfNull(CRMLead.source, "Empty").as_("source"), Count("*").as_("count"))
		.where(Date(CRMLead.creation).between(from_date, to_date))
		.groupby(CRMLead.source)
		.orderby(Count("*"), order=frappe.qb.desc)
	)

	if user:
		query = query.where(CRMLead.lead_owner == user)

	result = query.run(as_dict=True)
	category_column = _("Source")
	value_column = _("Count")
	localized_result = [
		{category_column: _(row.get("source") or ""), value_column: row.get("count") or 0}
		for row in result
	]

	return {
		"data": localized_result,
		"title": _("Leads by source"),
		"subtitle": _("Lead generation channel analysis"),
		"categoryColumn": category_column,
		"valueColumn": value_column,
	}


def get_deals_by_source(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""
	Get deal data by source for the dashboard.
	[
		{ source: 'Website', count: 120 },
		{ source: 'Referral', count: 45 },
		...
	]
	"""
	if not from_date or not to_date:
		from_date = frappe.utils.get_first_day(from_date or frappe.utils.nowdate())
		to_date = frappe.utils.get_last_day(to_date or frappe.utils.nowdate())

	# Using Frappe Query Builder
	CRMDeal = DocType("CRM Deal")

	query = (
		frappe.qb.from_(CRMDeal)
		.select(IfNull(CRMDeal.source, "Empty").as_("source"), Count("*").as_("count"))
		.where(Date(CRMDeal.creation).between(from_date, to_date))
		.groupby(CRMDeal.source)
		.orderby(Count("*"), order=frappe.qb.desc)
	)

	if user:
		query = query.where(CRMDeal.deal_owner == user)

	result = query.run(as_dict=True)
	category_column = _("Source")
	value_column = _("Count")
	localized_result = [
		{category_column: _(row.get("source") or ""), value_column: row.get("count") or 0}
		for row in result
	]

	return {
		"data": localized_result,
		"title": _("Deals by source"),
		"subtitle": _("Deal generation channel analysis"),
		"categoryColumn": category_column,
		"valueColumn": value_column,
	}


def get_deals_by_territory(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""
	Get deal data by territory for the dashboard.
	[
		{ territory: 'North America', deals: 45, value: 2300000 },
		{ territory: 'Europe', deals: 30, value: 1500000 },
		...
	]
	"""
	if not from_date or not to_date:
		from_date = frappe.utils.get_first_day(from_date or frappe.utils.nowdate())
		to_date = frappe.utils.get_last_day(to_date or frappe.utils.nowdate())

	# Using Frappe Query Builder with complex aggregations
	CRMDeal = DocType("CRM Deal")

	query = (
		frappe.qb.from_(CRMDeal)
		.select(
			IfNull(CRMDeal.territory, "Empty").as_("territory"),
			Count("*").as_("deals"),
			Sum(Coalesce(CRMDeal.deal_value, 0) * IfNull(CRMDeal.exchange_rate, 1)).as_("value"),
		)
		.where(Date(CRMDeal.creation).between(from_date, to_date))
		.groupby(CRMDeal.territory)
		.orderby(Count("*"), order=frappe.qb.desc)
		.orderby(
			Sum(Coalesce(CRMDeal.deal_value, 0) * IfNull(CRMDeal.exchange_rate, 1)), order=frappe.qb.desc
		)
	)

	if user:
		query = query.where(CRMDeal.deal_owner == user)

	result = query.run(as_dict=True)

	return {
		"data": result or [],
		"title": _("Deals by territory"),
		"subtitle": _("Geographic distribution of deals and revenue"),
		"xAxis": {
			"title": _("Territory"),
			"key": "territory",
			"type": "category",
		},
		"yAxis": {
			"title": _("Number of deals"),
		},
		"y2Axis": {
			"title": _("Deal value") + f" ({get_base_currency_symbol()})",
		},
		"series": [
			{"name": "deals", "type": "bar", "echartOptions": {"name": _("Deals")}},
			{"name": "value", "type": "line", "showDataPoints": True, "axis": "y2", "echartOptions": {"name": _("Value")}},
		],
	}


def get_deals_by_salesperson(
	from_date: str | None = None, to_date: str | None = None, user: str | None = None
):
	"""
	Get deal data by salesperson for the dashboard.
	[
		{ salesperson: 'John Smith', deals: 45, value: 2300000 },
		{ salesperson: 'Jane Doe', deals: 30, value: 1500000 },
		...
	]
	"""
	if not from_date or not to_date:
		from_date = frappe.utils.get_first_day(from_date or frappe.utils.nowdate())
		to_date = frappe.utils.get_last_day(to_date or frappe.utils.nowdate())

	# Using Frappe Query Builder with LEFT JOIN
	CRMDeal = DocType("CRM Deal")
	User = DocType("User")

	query = (
		frappe.qb.from_(CRMDeal)
		.left_join(User)
		.on(User.name == CRMDeal.deal_owner)
		.select(
			IfNull(User.full_name, CRMDeal.deal_owner).as_("salesperson"),
			Count("*").as_("deals"),
			Sum(Coalesce(CRMDeal.deal_value, 0) * IfNull(CRMDeal.exchange_rate, 1)).as_("value"),
		)
		.where(Date(CRMDeal.creation).between(from_date, to_date))
		.groupby(CRMDeal.deal_owner)
		.orderby(Count("*"), order=frappe.qb.desc)
		.orderby(
			Sum(Coalesce(CRMDeal.deal_value, 0) * IfNull(CRMDeal.exchange_rate, 1)), order=frappe.qb.desc
		)
	)

	if user:
		query = query.where(CRMDeal.deal_owner == user)

	result = query.run(as_dict=True)

	return {
		"data": result or [],
		"title": _("Deals by salesperson"),
		"subtitle": _("Number of deals and total value per salesperson"),
		"xAxis": {
			"title": _("Salesperson"),
			"key": "salesperson",
			"type": "category",
		},
		"yAxis": {
			"title": _("Number of deals"),
		},
		"y2Axis": {
			"title": _("Deal value") + f" ({get_base_currency_symbol()})",
		},
		"series": [
			{"name": "deals", "type": "bar", "echartOptions": {"name": _("Deals")}},
			{"name": "value", "type": "line", "showDataPoints": True, "axis": "y2", "echartOptions": {"name": _("Value")}},
		],
	}


def get_base_currency():
	"""Get the dashboard base currency from CRM settings."""
	return frappe.db.get_single_value("FCRM Settings", "currency") or "RUB"


def get_base_currency_symbol():
	"""
	Get the base currency symbol from the system settings.
	"""
	return frappe.db.get_value("Currency", get_base_currency(), "symbol") or ""


def get_deal_status_change_counts(
	from_date: str | None = None,
	to_date: str | None = None,
	deal_conds: str = "",
	filters: dict | None = None,
):
	"""
	Get count of each status change (to) for each deal, excluding deals with current status type 'Lost'.
	Order results by status position.
	Returns:
	[
	  {"status": "Qualification", "count": 120},
	  {"status": "Negotiation", "count": 85},
	  ...
	]
	"""
	# Using Frappe Query Builder with multiple JOINs and table aliases
	CRMStatusChangeLog = DocType("CRM Status Change Log")
	CRMDeal = DocType("CRM Deal")
	CurrentStatus = DocType("CRM Deal Status").as_("s")
	TargetStatus = DocType("CRM Deal Status").as_("st")

	query = (
		frappe.qb.from_(CRMStatusChangeLog)
		.join(CRMDeal)
		.on(CRMStatusChangeLog.parent == CRMDeal.name)
		.join(CurrentStatus)
		.on(CRMDeal.status == CurrentStatus.name)
		.join(TargetStatus)
		.on(CRMStatusChangeLog.to == TargetStatus.name)
		.select(CRMStatusChangeLog.to.as_("stage"), Count("*").as_("count"))
		.where(
			(CRMStatusChangeLog.to.isnotnull())
			& (CRMStatusChangeLog.to != "")
			& (CurrentStatus.type != "Lost")
			& (Date(CRMDeal.creation).between(from_date, to_date))
		)
		.groupby(CRMStatusChangeLog.to, TargetStatus.position)
		.orderby(TargetStatus.position)
	)

	# Handle optional user filter if deal_conds contains user condition
	if filters and filters.get("user"):
		query = query.where(CRMDeal.deal_owner == filters["user"])

	result = query.run(as_dict=True)
	return result or []
