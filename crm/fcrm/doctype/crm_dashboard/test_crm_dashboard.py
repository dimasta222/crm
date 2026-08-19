# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json
from decimal import Decimal

import frappe
from frappe.tests.utils import FrappeTestCase

from crm.api.dashboard import (
	get_average_order_value,
	get_awaiting_payment,
	get_base_currency,
	get_base_currency_symbol,
	get_completed_order_amount_by_day,
	get_completed_orders,
	get_current_orders,
	get_orders_by_acquisition_manager,
	get_orders_by_production_type,
	get_orders_by_source,
	get_orders_by_status,
	get_orders_in_production,
	get_orders_ready_for_pickup,
	get_outstanding_balance_by_payment_status,
	get_overdue_orders,
	get_paid_for_period_orders,
	get_total_order_amount,
	get_unpaid_orders,
)
from crm.fcrm.doctype.crm_dashboard.crm_dashboard import (
	LEGACY_DEFAULT_MANAGER_DASHBOARD_LAYOUT,
	default_manager_dashboard_layout,
	stage_2b2_manager_dashboard_layout,
	stage_2b3_manager_dashboard_layout,
)
from crm.patches.v1_0.add_print_studio_operational_dashboard_cards import (
	get_updated_layout as get_operational_cards_updated_layout,
)
from crm.patches.v1_0.update_print_studio_dashboard_cards import (
	get_updated_layout as get_primary_cards_updated_layout,
)
from crm.patches.v1_0.update_print_studio_dashboard_graphs import (
	get_updated_layout as get_dashboard_graphs_updated_layout,
)

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class TestCRMDashboard(FrappeTestCase):
	"""
	Unit tests for CRMDashboard.
	Use this class for testing individual functions and methods.
	"""

	owner = "dashboard-2b2@example.invalid"
	from_date = "2026-08-01"
	to_date = "2026-08-10"

	def setUp(self):
		super().setUp()
		frappe.db.set_single_value("FCRM Settings", "currency", "RUB")
		self.open_status = self._ensure_status("Dashboard 2B2 Open", "Open")
		self.ongoing_status = self._ensure_status("Dashboard 2B2 Ongoing", "Ongoing")
		self.won_status = self._ensure_status("Dashboard 2B2 Won", "Won")
		self.lost_status = self._ensure_status("Dashboard 2B2 Lost", "Lost")
		self.in_production_status = self._ensure_status("In Production", "Ongoing")
		self.ready_for_pickup_status = self._ensure_status("Ready for Pickup", "Ongoing")

	def tearDown(self):
		frappe.db.rollback()
		super().tearDown()

	def test_period_amount_and_average_exclude_cancelled_orders(self):
		self._create_order(self.open_status, "2026-08-01 00:00:00", order_total=100)
		self._create_order(self.won_status, "2026-08-10 23:59:59", order_total=300)
		self._create_order(self.lost_status, "2026-08-05 12:00:00", order_total=900)
		self._create_order(self.open_status, "2026-07-31 23:59:59", order_total=500)
		self._create_order(self.open_status, "2026-08-11 00:00:00", order_total=600)

		total = get_total_order_amount(self.from_date, self.to_date, self.owner)
		average = get_average_order_value(self.from_date, self.to_date, self.owner)

		self.assertEqual(total["value"], Decimal("400"))
		self.assertEqual(average["value"], Decimal("200"))

	def test_paid_and_awaiting_payment_use_current_order_values(self):
		self._create_order(
			self.open_status,
			"2026-08-05 12:00:00",
			order_total=100,
			paid_amount=40,
			balance_amount=60,
		)
		self._create_order(
			self.open_status,
			"2026-08-06 12:00:00",
			order_total=200,
			paid_amount=80,
			balance_amount=120,
			payment_status="Refunded",
		)
		self._create_order(
			self.lost_status,
			"2026-08-07 12:00:00",
			order_total=300,
			paid_amount=50,
			balance_amount=250,
		)
		self._create_order(
			self.open_status,
			"2026-08-08 12:00:00",
			order_total=90,
			paid_amount=10,
			balance_amount=80,
			payment_status="Cancelled",
		)
		self._create_order(
			self.open_status,
			"2026-08-11 00:00:00",
			order_total=500,
			paid_amount=100,
			balance_amount=400,
		)

		paid = get_paid_for_period_orders(self.from_date, self.to_date, self.owner)
		awaiting = get_awaiting_payment(self.from_date, self.to_date, self.owner)

		self.assertEqual(paid["value"], Decimal("180"))
		self.assertEqual(awaiting["value"], Decimal("60"))

	def test_monetary_cards_only_include_base_currency_orders(self):
		self._create_order(
			self.open_status,
			"2026-08-05 12:00:00",
			currency="RUB",
			order_total=Decimal("100.25"),
			paid_amount=Decimal("40.10"),
			balance_amount=Decimal("60.15"),
		)
		self._create_order(
			self.open_status,
			"2026-08-06 12:00:00",
			currency="RUB",
			order_total=Decimal("200.35"),
			paid_amount=Decimal("100.20"),
			balance_amount=Decimal("100.15"),
		)
		self._create_order(
			self.open_status,
			"2026-08-05 12:00:00",
			currency="USD",
			order_total=Decimal("900.45"),
			paid_amount=Decimal("300.15"),
			balance_amount=Decimal("600.30"),
		)
		self._create_order(
			self.won_status,
			"2026-08-06 12:00:00",
			currency="USD",
			order_total=Decimal("500.55"),
			paid_amount=Decimal("500.55"),
			balance_amount=Decimal("0.00"),
			closed_date="2026-08-07",
		)
		self._create_order(
			self.open_status,
			"2026-08-07 12:00:00",
			currency="RUB",
			owner="another-dashboard-owner@example.invalid",
			order_total=Decimal("700.65"),
			paid_amount=Decimal("200.25"),
			balance_amount=Decimal("500.40"),
		)

		total = get_total_order_amount(self.from_date, self.to_date, self.owner)
		paid = get_paid_for_period_orders(self.from_date, self.to_date, self.owner)
		awaiting = get_awaiting_payment(self.from_date, self.to_date, self.owner)
		average = get_average_order_value(self.from_date, self.to_date, self.owner)

		self.assertIsInstance(total["value"], Decimal)
		self.assertIsInstance(paid["value"], Decimal)
		self.assertIsInstance(awaiting["value"], Decimal)
		self.assertIsInstance(average["value"], Decimal)
		self.assertEqual(total["value"], Decimal("300.60"))
		self.assertEqual(paid["value"], Decimal("140.30"))
		self.assertEqual(awaiting["value"], Decimal("160.30"))
		self.assertEqual(average["value"], Decimal("150.30"))
		self.assertEqual(get_current_orders(self.from_date, self.to_date, self.owner)["value"], 3)
		self.assertEqual(get_completed_orders(self.from_date, self.to_date, self.owner)["value"], 1)

	def test_deal_owner_filters_all_cards(self):
		self._create_order(
			self.open_status,
			"2026-08-05 12:00:00",
			order_total=100,
			paid_amount=40,
			balance_amount=60,
		)
		self._create_order(
			self.won_status,
			"2026-08-06 12:00:00",
			order_total=300,
			paid_amount=300,
			balance_amount=0,
			closed_date="2026-08-07",
		)
		self._create_order(
			self.open_status,
			"2026-08-05 12:00:00",
			owner="another-dashboard-owner@example.invalid",
			order_total=900,
			paid_amount=100,
			balance_amount=800,
		)
		self._create_order(
			self.won_status,
			"2026-08-06 12:00:00",
			owner="another-dashboard-owner@example.invalid",
			order_total=700,
			paid_amount=700,
			balance_amount=0,
			closed_date="2026-08-07",
		)

		self.assertEqual(
			get_total_order_amount(self.from_date, self.to_date, self.owner)["value"],
			Decimal("400"),
		)
		self.assertEqual(
			get_paid_for_period_orders(self.from_date, self.to_date, self.owner)["value"],
			Decimal("340"),
		)
		self.assertEqual(
			get_awaiting_payment(self.from_date, self.to_date, self.owner)["value"],
			Decimal("60"),
		)
		self.assertEqual(get_current_orders(self.from_date, self.to_date, self.owner)["value"], 1)
		self.assertEqual(get_completed_orders(self.from_date, self.to_date, self.owner)["value"], 1)
		self.assertEqual(
			get_average_order_value(self.from_date, self.to_date, self.owner)["value"],
			Decimal("200"),
		)

	def test_base_currency_and_symbol_use_the_same_system_setting(self):
		self.assertEqual(get_base_currency(), "RUB")
		self.assertEqual(
			get_base_currency_symbol(),
			frappe.db.get_value("Currency", "RUB", "symbol") or "",
		)

	def test_completed_orders_use_inclusive_closed_date_period(self):
		self._create_order(self.won_status, "2026-01-01 12:00:00", closed_date=self.from_date)
		self._create_order(self.won_status, "2026-01-02 12:00:00", closed_date=self.to_date)
		self._create_order(self.won_status, "2026-01-03 12:00:00", closed_date="2026-07-31")
		self._create_order(self.won_status, "2026-01-04 12:00:00", closed_date="2026-08-11")
		self._create_order(self.open_status, "2026-01-05 12:00:00", closed_date="2026-08-05")

		completed = get_completed_orders(self.from_date, self.to_date, self.owner)

		self.assertEqual(completed["value"], 2)

	def test_current_orders_are_a_period_independent_snapshot(self):
		self._create_order(self.open_status, "2020-01-01 12:00:00")
		self._create_order(self.ongoing_status, "2030-01-01 12:00:00")
		self._create_order(self.won_status, "2026-08-05 12:00:00")
		self._create_order(self.lost_status, "2026-08-05 12:00:00")

		current = get_current_orders(self.from_date, self.to_date, self.owner)

		self.assertEqual(current["value"], 2)
		self.assertEqual(current["title"], frappe._("Current orders (now)"))

	def test_average_order_value_is_zero_without_orders(self):
		average = get_average_order_value(
			self.from_date,
			self.to_date,
			"dashboard-empty-2b2@example.invalid",
		)

		self.assertEqual(average["value"], 0)

	def test_orders_in_production_are_a_manager_filtered_snapshot(self):
		self._create_order(self.in_production_status, "2020-01-01 12:00:00")
		self._create_order(self.ready_for_pickup_status, "2030-01-01 12:00:00")
		self._create_order(self.won_status, "2026-08-05 12:00:00")
		self._create_order(
			self.in_production_status,
			"2026-08-05 12:00:00",
			owner="another-dashboard-owner@example.invalid",
		)

		self._assert_snapshot_value(get_orders_in_production, 1)

	def test_orders_ready_for_pickup_are_a_manager_filtered_snapshot(self):
		self._create_order(self.ready_for_pickup_status, "2020-01-01 12:00:00")
		self._create_order(self.in_production_status, "2030-01-01 12:00:00")
		self._create_order(self.lost_status, "2026-08-05 12:00:00")
		self._create_order(
			self.ready_for_pickup_status,
			"2026-08-05 12:00:00",
			owner="another-dashboard-owner@example.invalid",
		)

		self._assert_snapshot_value(get_orders_ready_for_pickup, 1)

	def test_overdue_orders_use_local_date_boundary_and_manager_filter(self):
		today = frappe.utils.nowdate()
		yesterday = frappe.utils.add_days(today, -1)
		tomorrow = frappe.utils.add_days(today, 1)

		self._create_order(
			self.ongoing_status,
			"2020-01-01 12:00:00",
			production_deadline=f"{yesterday} 23:59:59",
		)
		self._create_order(
			self.ongoing_status,
			"2020-01-01 12:00:00",
			production_deadline=f"{today} 00:00:00",
		)
		self._create_order(
			self.ongoing_status,
			"2020-01-01 12:00:00",
			production_deadline=f"{tomorrow} 00:00:00",
		)
		self._create_order(
			self.won_status,
			"2020-01-01 12:00:00",
			production_deadline=f"{yesterday} 12:00:00",
		)
		self._create_order(
			self.lost_status,
			"2020-01-01 12:00:00",
			production_deadline=f"{yesterday} 12:00:00",
		)
		self._create_order(
			self.ongoing_status,
			"2020-01-01 12:00:00",
			owner="another-dashboard-owner@example.invalid",
			production_deadline=f"{yesterday} 12:00:00",
		)

		self._assert_snapshot_value(get_overdue_orders, 1)

	def test_unpaid_orders_include_null_and_zero_payment_only(self):
		self._create_order(self.ongoing_status, "2020-01-01 12:00:00", order_total=100, paid_amount=0)
		self._create_order(self.ongoing_status, "2030-01-01 12:00:00", order_total=50, paid_amount=None)
		self._create_order(self.ongoing_status, "2026-08-05 12:00:00", order_total=0, paid_amount=0)
		self._create_order(self.ongoing_status, "2026-08-05 12:00:00", order_total=100, paid_amount=10)
		self._create_order(self.won_status, "2026-08-05 12:00:00", order_total=100, paid_amount=0)
		self._create_order(self.lost_status, "2026-08-05 12:00:00", order_total=100, paid_amount=0)
		self._create_order(
			self.ongoing_status,
			"2026-08-05 12:00:00",
			owner="another-dashboard-owner@example.invalid",
			order_total=100,
			paid_amount=0,
		)

		self._assert_snapshot_value(get_unpaid_orders, 2)

	def test_completed_order_amount_by_day_uses_closed_date_won_rub_and_owner(self):
		self._create_order(
			self.won_status,
			"2020-01-01 12:00:00",
			closed_date=self.from_date,
			order_total=Decimal("100.25"),
		)
		self._create_order(
			self.won_status,
			"2030-01-01 12:00:00",
			closed_date=self.to_date,
			order_total=Decimal("50.15"),
		)
		self._create_order(
			self.won_status,
			"2026-01-01 12:00:00",
			closed_date=self.from_date,
			order_total=Decimal("200.35"),
		)
		self._create_order(
			self.open_status,
			"2026-08-05 12:00:00",
			closed_date="2026-08-05",
			order_total=Decimal("900.45"),
		)
		self._create_order(
			self.won_status,
			"2026-08-05 12:00:00",
			closed_date="2026-08-05",
			currency="USD",
			order_total=Decimal("800.55"),
		)
		self._create_order(
			self.won_status,
			"2026-08-05 12:00:00",
			closed_date="2026-08-05",
			owner="another-dashboard-owner@example.invalid",
			order_total=Decimal("700.65"),
		)
		self._create_order(
			self.won_status,
			"2026-08-05 12:00:00",
			closed_date="2026-07-31",
			order_total=Decimal("600.75"),
		)
		self._create_order(
			self.won_status,
			"2026-08-05 12:00:00",
			closed_date="2026-08-11",
			order_total=Decimal("500.85"),
		)

		chart = get_completed_order_amount_by_day(self.from_date, self.to_date, self.owner)
		amounts = {row.date: row.amount for row in chart["data"]}

		self.assertEqual(amounts, {self.from_date: Decimal("300.60"), self.to_date: Decimal("50.15")})
		self.assertTrue(all(isinstance(amount, Decimal) for amount in amounts.values()))

	def test_completed_order_amount_preserves_decimal_zero(self):
		owner = "dashboard-zero-amount@example.invalid"
		self._create_order(
			self.won_status,
			"2026-08-05 12:00:00",
			owner=owner,
			closed_date="2026-08-05",
			order_total=Decimal("0.00"),
		)

		chart = get_completed_order_amount_by_day(self.from_date, self.to_date, owner)

		self.assertEqual(len(chart["data"]), 1)
		self.assertIsInstance(chart["data"][0].amount, Decimal)
		self.assertEqual(chart["data"][0].amount, Decimal("0.00"))

	def test_period_category_graphs_use_boundaries_fallbacks_nulls_and_owner(self):
		first = self._create_order(
			self.open_status,
			"2026-08-01 00:00:00",
			first_touch_source="Website",
			source="Referral",
			attracted_by="Administrator",
		)
		self._add_application(first, "DTF Printing")
		self._add_application(first, "DTF Printing")
		self._add_application(first, "Embroidery")

		second = self._create_order(
			self.won_status,
			"2026-08-10 23:59:59",
			first_touch_source="",
			source="Referral",
			attracted_by="missing-dashboard-user@example.invalid",
		)
		self._add_application(second, "Combined")

		self._create_order(None, "2026-08-05 12:00:00", first_touch_source="", source="", attracted_by="")
		outside = self._create_order(self.open_status, "2026-08-11 00:00:00", source="Outside")
		self._add_application(outside, "Screen Printing")
		other_owner = self._create_order(
			self.open_status,
			"2026-08-05 12:00:00",
			owner="another-dashboard-owner@example.invalid",
			source="Other owner",
			attracted_by="other-owner@example.invalid",
		)
		self._add_application(other_owner, "Sublimation")

		status_chart = get_orders_by_status(self.from_date, self.to_date, self.owner)
		source_chart = get_orders_by_source(self.from_date, self.to_date, self.owner)
		production_chart = get_orders_by_production_type(self.from_date, self.to_date, self.owner)
		manager_chart = get_orders_by_acquisition_manager(self.from_date, self.to_date, self.owner)

		self.assertEqual(
			self._donut_values(status_chart),
			{self.open_status: 1, self.won_status: 1, frappe._("Not specified"): 1},
		)

		self.assertEqual(
			self._donut_values(source_chart),
			{"Website": 1, "Referral": 1, frappe._("Not specified"): 1},
		)
		self.assertEqual(
			{row.service_type: row.count for row in production_chart["data"]},
			{
				frappe._("DTF Printing"): 1,
				frappe._("Embroidery"): 1,
				frappe._("Combined"): 1,
				frappe._("Not specified"): 1,
			},
		)
		self.assertEqual(
			{row.manager: row.count for row in manager_chart["data"]},
			{
				frappe.db.get_value("User", "Administrator", "full_name") or "Administrator": 1,
				"missing-dashboard-user@example.invalid": 1,
				frappe._("Not specified"): 1,
			},
		)

	def test_acquisition_manager_localizes_missing_category_in_russian(self):
		owner = "dashboard-russian-manager@example.invalid"
		self._create_order(
			self.open_status,
			"2026-08-05 12:00:00",
			owner=owner,
			attracted_by=None,
		)
		original_language = frappe.local.lang
		try:
			frappe.local.lang = "ru"
			chart = get_orders_by_acquisition_manager(self.from_date, self.to_date, owner)
		finally:
			frappe.local.lang = original_language

		self.assertEqual(chart["data"][0].manager, "Не указан")

	def test_outstanding_balance_graph_is_snapshot_and_excludes_invalid_debts(self):
		self._create_order(
			self.open_status,
			"2020-01-01 12:00:00",
			balance_amount=Decimal("60.15"),
			payment_status=None,
		)
		self._create_order(
			self.won_status,
			"2030-01-01 12:00:00",
			balance_amount=Decimal("100.15"),
			payment_status="Unpaid",
		)
		self._create_order(
			None,
			"2026-08-05 12:00:00",
			balance_amount=Decimal("25.35"),
			payment_status="Partially Paid",
		)
		self._create_order(
			self.open_status,
			"2026-08-05 12:00:00",
			balance_amount=Decimal("0.00"),
			payment_status="Unpaid",
		)
		self._create_order(
			self.open_status,
			"2026-08-05 12:00:00",
			balance_amount=Decimal("-10.25"),
			payment_status="Unpaid",
		)
		for status, payment_status, currency, owner in (
			(self.lost_status, "Unpaid", "RUB", self.owner),
			(self.open_status, "Cancelled", "RUB", self.owner),
			(self.open_status, "Refunded", "RUB", self.owner),
			(self.open_status, "Unpaid", "USD", self.owner),
			(self.open_status, "Unpaid", "RUB", "another-dashboard-owner@example.invalid"),
		):
			self._create_order(
				status,
				"2026-08-05 12:00:00",
				currency=currency,
				owner=owner,
				balance_amount=Decimal("900.25"),
				payment_status=payment_status,
			)

		past = get_outstanding_balance_by_payment_status("1900-01-01", "1900-01-02", self.owner)
		future = get_outstanding_balance_by_payment_status("2100-01-01", "2100-01-02", self.owner)
		for chart in (past, future):
			balances = {row.payment_status: row.balance for row in chart["data"]}
			self.assertEqual(
				balances,
				{
					frappe._("Unpaid"): Decimal("100.15"),
					frappe._("Partially Paid"): Decimal("25.35"),
					frappe._("Not specified"): Decimal("60.15"),
				},
			)
			self.assertTrue(all(isinstance(balance, Decimal) for balance in balances.values()))

	def test_default_layout_has_ten_cards_and_six_print_studio_graphs(self):
		updated = json.loads(default_manager_dashboard_layout())

		self.assertEqual(
			[item["name"] for item in updated[:10]],
			[
				"total_order_amount",
				"paid_for_period_orders",
				"awaiting_payment",
				"current_orders",
				"completed_orders",
				"average_order_value",
				"orders_in_production",
				"orders_ready_for_pickup",
				"overdue_orders",
				"unpaid_orders",
			],
		)
		self.assertEqual(
			[item["name"] for item in updated[10:]],
			[
				"completed_order_amount_by_day",
				"orders_by_status",
				"orders_by_production_type",
				"orders_by_source",
				"orders_by_acquisition_manager",
				"outstanding_balance_by_payment_status",
			],
		)
		self.assertEqual(len(updated), 16)

	def test_layout_migration_only_updates_untouched_legacy_default(self):
		legacy = json.loads(LEGACY_DEFAULT_MANAGER_DASHBOARD_LAYOUT)
		custom = json.loads(LEGACY_DEFAULT_MANAGER_DASHBOARD_LAYOUT)
		custom[0]["layout"]["w"] = 5

		self.assertEqual(
			get_primary_cards_updated_layout(json.dumps(legacy, indent=2)),
			default_manager_dashboard_layout(),
		)
		self.assertIsNone(get_primary_cards_updated_layout(json.dumps(custom)))
		self.assertIsNone(get_primary_cards_updated_layout(default_manager_dashboard_layout()))

	def test_operational_layout_migration_only_updates_stage_2b2_default(self):
		stage_2b2 = json.loads(stage_2b2_manager_dashboard_layout())
		custom = json.loads(stage_2b2_manager_dashboard_layout())
		custom[0]["layout"]["w"] = 5

		self.assertEqual(
			get_operational_cards_updated_layout(json.dumps(stage_2b2, indent=2)),
			default_manager_dashboard_layout(),
		)
		self.assertIsNone(get_operational_cards_updated_layout(json.dumps(custom)))
		self.assertIsNone(get_operational_cards_updated_layout(default_manager_dashboard_layout()))

	def test_graph_layout_migration_only_updates_exact_stage_2b3_default(self):
		stage_2b3 = json.loads(stage_2b3_manager_dashboard_layout())
		custom = json.loads(stage_2b3_manager_dashboard_layout())
		custom[10]["layout"]["w"] = 9

		self.assertEqual(
			get_dashboard_graphs_updated_layout(json.dumps(stage_2b3, indent=2)),
			default_manager_dashboard_layout(),
		)
		self.assertIsNone(get_dashboard_graphs_updated_layout(json.dumps(custom)))
		self.assertIsNone(get_dashboard_graphs_updated_layout(default_manager_dashboard_layout()))

	def _assert_snapshot_value(self, metric, expected):
		past_period = metric("1900-01-01", "1900-01-02", self.owner)
		future_period = metric("2100-01-01", "2100-01-02", self.owner)
		self.assertEqual(past_period["value"], expected)
		self.assertEqual(future_period["value"], expected)

	def _donut_values(self, chart):
		return {row[chart["categoryColumn"]]: row[chart["valueColumn"]] for row in chart["data"]}

	def _add_application(self, order, service_type):
		idx = frappe.db.count(
			"CRM Deal Application",
			{"parent": order, "parenttype": "CRM Deal", "parentfield": "applications"},
		) + 1
		application = frappe.get_doc(
			{
				"doctype": "CRM Deal Application",
				"parent": order,
				"parenttype": "CRM Deal",
				"parentfield": "applications",
				"idx": idx,
				"item_reference": f"ITEM-{idx}",
				"service_type": service_type,
				"combined_methods": "DTF Printing + Embroidery" if service_type == "Combined" else None,
				"placement": "Chest",
				"quantity": 1,
			}
		)
		application.db_insert()

	def _ensure_status(self, name, status_type):
		if not frappe.db.exists("CRM Deal Status", name):
			frappe.get_doc(
				{
					"doctype": "CRM Deal Status",
					"deal_status": name,
					"type": status_type,
				}
			).insert(ignore_permissions=True)
		return name

	def _create_order(
		self,
		status,
		creation,
		*,
		currency="RUB",
		owner=None,
		order_total=0,
		paid_amount=0,
		balance_amount=None,
		payment_status=None,
		closed_date=None,
		production_deadline=None,
		first_touch_source=None,
		source=None,
		attracted_by=None,
	):
		order = frappe.get_doc(
			{
				"doctype": "CRM Deal",
				"status": self.open_status,
				"order_total": order_total,
				"paid_amount": paid_amount,
			}
		).insert(ignore_permissions=True)

		values = {
			"status": status,
			"creation": creation,
			"currency": currency,
			"deal_owner": owner or self.owner,
			"order_total": order_total,
			"paid_amount": paid_amount,
			"balance_amount": order_total - (paid_amount or 0) if balance_amount is None else balance_amount,
			"payment_status": payment_status,
		}
		if closed_date:
			values["closed_date"] = closed_date
		if production_deadline:
			values["production_deadline"] = production_deadline
		if first_touch_source is not None:
			values["first_touch_source"] = first_touch_source
		if source is not None:
			values["source"] = source
		if attracted_by is not None:
			values["attracted_by"] = attracted_by
		frappe.db.set_value("CRM Deal", order.name, values, update_modified=False)
		return order.name
