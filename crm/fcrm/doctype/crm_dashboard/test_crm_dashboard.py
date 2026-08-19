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
	get_completed_orders,
	get_current_orders,
	get_orders_in_production,
	get_orders_ready_for_pickup,
	get_overdue_orders,
	get_paid_for_period_orders,
	get_total_order_amount,
	get_unpaid_orders,
)
from crm.fcrm.doctype.crm_dashboard.crm_dashboard import (
	LEGACY_DEFAULT_MANAGER_DASHBOARD_LAYOUT,
	default_manager_dashboard_layout,
	stage_2b2_manager_dashboard_layout,
)
from crm.patches.v1_0.add_print_studio_operational_dashboard_cards import (
	get_updated_layout as get_operational_cards_updated_layout,
)
from crm.patches.v1_0.update_print_studio_dashboard_cards import (
	get_updated_layout as get_primary_cards_updated_layout,
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

	def test_default_layout_replaces_only_number_cards(self):
		legacy = json.loads(LEGACY_DEFAULT_MANAGER_DASHBOARD_LAYOUT)
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
		self.assertEqual(updated[10:], legacy[8:])

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

	def _assert_snapshot_value(self, metric, expected):
		past_period = metric("1900-01-01", "1900-01-02", self.owner)
		future_period = metric("2100-01-01", "2100-01-02", self.owner)
		self.assertEqual(past_period["value"], expected)
		self.assertEqual(future_period["value"], expected)

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
		}
		if payment_status:
			values["payment_status"] = payment_status
		if closed_date:
			values["closed_date"] = closed_date
		if production_deadline:
			values["production_deadline"] = production_deadline
		frappe.db.set_value("CRM Deal", order.name, values, update_modified=False)
		return order.name
