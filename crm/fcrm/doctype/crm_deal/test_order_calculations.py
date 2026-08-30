from decimal import Decimal
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from crm.fcrm.doctype.crm_deal.crm_deal import CRMDeal
from crm.fcrm.doctype.crm_deal.order_calculations import (
	_sum_money,
	ensure_item_keys,
	get_currency_precision,
	round_money,
	uses_new_order_model,
	validate_and_calculate_order,
)


class TestOrderCalculations(FrappeTestCase):
	def setUp(self):
		super().setUp()
		self.catalog_rates = {"TEST-PRODUCT": 500, "OTHER-PRODUCT": 800}
		self.stored_items = {}
		self.db_get_value = patch.object(frappe.db, "get_value", side_effect=self._get_value)
		self.get_precision = patch.object(frappe, "get_precision", return_value=2)
		self.mock_get_value = self.db_get_value.start()
		self.mock_get_precision = self.get_precision.start()
		self.addCleanup(self.db_get_value.stop)
		self.addCleanup(self.get_precision.stop)

	def _get_value(self, doctype, name, fieldname, **kwargs):
		if doctype == "CRM Product":
			return self.catalog_rates.get(name)
		if doctype == "CRM Order Item":
			stored = self.stored_items.get(name)
			return frappe._dict(stored) if stored else None
		return None

	def test_empty_new_tables_keep_legacy_model(self):
		self.assertFalse(uses_new_order_model(deal(None)))

	def test_round_money_returns_decimal_with_half_up_rounding(self):
		result = round_money(Decimal("0.105"), 2)
		self.assertIsInstance(result, Decimal)
		self.assertEqual(result, Decimal("0.11"))
		self.assertEqual(_sum_money((Decimal("0.1"), Decimal("0.2")), 2), Decimal("0.30"))

	def test_currency_precision_uses_frappe_primary_branch(self):
		self.mock_get_precision.return_value = 3
		self.assertEqual(get_currency_precision(deal("DTF Roll")), 3)

	def test_currency_precision_falls_back_to_field_meta(self):
		self.mock_get_precision.side_effect = AttributeError
		field = frappe._dict(precision="4")
		with patch.object(frappe, "get_meta", return_value=frappe._dict(get_field=lambda _: field)):
			self.assertEqual(get_currency_precision(deal("DTF Roll")), 4)

	def test_orphan_application_activates_new_model_and_is_rejected(self):
		doc = deal("Product Printing", order_applications=[application(key="ORPHAN")])
		self.assertTrue(uses_new_order_model(doc))
		with self.assertRaises(frappe.ValidationError):
			validate_and_calculate_order(doc)

	def test_crm_deal_validate_keeps_legacy_calculation_when_new_tables_are_empty(self):
		doc = MagicMock()
		doc.get.side_effect = lambda field: [] if field in NEW_TABLES else None
		doc.is_new.return_value = False
		doc.has_value_changed.return_value = False

		CRMDeal.validate(doc)

		doc.set_item_references.assert_called_once_with()
		doc.validate_application_references.assert_called_once_with()
		doc.calculate_order_totals.assert_called_once_with()

	def test_crm_deal_validate_uses_new_calculation_when_any_new_table_has_rows(self):
		doc = MagicMock()
		doc.get.side_effect = lambda field: [application()] if field == "order_applications" else []
		doc.is_new.return_value = False
		doc.has_value_changed.return_value = False

		with patch("crm.fcrm.doctype.crm_deal.order_calculations.validate_and_calculate_order") as calculate:
			CRMDeal.validate(doc)

		calculate.assert_called_once_with(doc)
		doc.calculate_order_totals.assert_not_called()

	def test_product_printing_calculates_items_applications_discount_and_total(self):
		customer_item = row(
			2,
			item_key="ITEM-002",
			supply_type="Customer Item",
			qty=3,
			base_rate=900,
			use_manual_rate=1,
			manual_rate=800,
			discount_percentage=50,
		)
		doc = deal(
			"Product Printing",
			order_items=[studio_item(discount_percentage=10), customer_item],
			order_applications=[application(qty=2, rate=120)],
		)

		validate_and_calculate_order(doc)

		self.assertEqual(doc.order_items[0].gross_amount, 1000)
		self.assertEqual(doc.order_items[0].discount_amount, 100)
		self.assertEqual(doc.order_items[0].amount, 900)
		self.assertEqual(customer_item.base_rate, 0)
		self.assertEqual(customer_item.manual_rate, 0)
		self.assertEqual(customer_item.rate, 0)
		self.assertEqual(customer_item.discount_percentage, 0)
		self.assertEqual(customer_item.amount, 0)
		self.assertEqual(doc.applications_subtotal, 240)
		self.assertEqual(doc.subtotal, 1140)
		self.assertEqual(doc.order_total, 1140)
		self.assertEqual(doc.deal_value, 1140)

	def test_embroidery_uses_manual_rate_and_artwork_preparation(self):
		item = studio_item(qty=32)
		print_application = application(
			production_type="Embroidery",
			qty=32,
			stitch_count=12500,
			stitch_rate_per_1000=70,
			embroidery_setup_fee=500,
			rate=227.5,
		)
		doc = product_printing(item, print_application)

		validate_and_calculate_order(doc)

		self.assertEqual(Decimal(str(print_application.rate)), Decimal("227.5"))
		self.assertEqual(
			Decimal(str(print_application.calculated_amount)), Decimal("7780")
		)
		self.assertEqual(Decimal(str(doc.applications_subtotal)), Decimal("7780"))

	def test_application_decimal_multiplication_is_exact(self):
		item = studio_item(qty=40)
		print_application = application(qty=40, rate=Decimal("227.5"))

		validate_and_calculate_order(product_printing(item, print_application))

		self.assertEqual(Decimal(str(print_application.calculated_amount)), Decimal("9100"))

	def test_one_order_mixes_customer_and_studio_items_with_dtf_and_embroidery(self):
		customer_item = row(
			1,
			item_key="ITEM-CUSTOMER",
			supply_type="Customer Item",
			item_name="32 футболки клиента",
			qty=32,
			base_rate=0,
			manual_rate=0,
			use_manual_rate=0,
			discount_percentage=0,
		)
		studio_product = studio_item(2, key="ITEM-STUDIO", qty=2)
		dtf = application(
			1,
			key="ITEM-CUSTOMER",
			qty=32,
			rate=10,
			comment="На каждой футболке своё имя",
		)
		embroidery = application(
			2,
			key="ITEM-STUDIO",
			production_type="Embroidery",
			qty=2,
			embroidery_setup_fee=500,
			rate=875,
			comment="Логотип на груди",
		)
		doc = deal(
			"Product Printing",
			order_items=[customer_item, studio_product],
			order_applications=[dtf, embroidery],
		)

		validate_and_calculate_order(doc)

		self.assertEqual(customer_item.amount, 0)
		self.assertEqual(studio_product.amount, 1000)
		self.assertEqual(dtf.amount, 320)
		self.assertEqual(embroidery.amount, 2250)
		self.assertEqual(doc.order_total, 3570)
		self.assertEqual(dtf.comment, "На каждой футболке своё имя")
		self.assertIsNone(dtf.get("width_cm"))
		self.assertIsNone(dtf.get("height_cm"))

	def test_optional_dimensions_accept_empty_and_legacy_zero_values(self):
		item = studio_item(qty=2)
		applications = [
			application(1, width_cm=None, height_cm=None),
			application(2, width_cm=0, height_cm=0),
		]
		doc = deal(
			"Product Printing",
			order_items=[item],
			order_applications=applications,
		)

		validate_and_calculate_order(doc)

		self.assertEqual(doc.applications_subtotal, 200)

	def test_server_generates_unique_item_keys_and_retries_collision(self):
		doc = deal(
			"Product Printing",
			order_items=[studio_item(1, key=""), studio_item(2, key="")],
		)
		with patch.object(frappe, "generate_hash", side_effect=("same", "same", "different")):
			ensure_item_keys(doc)

		self.assertEqual(doc.order_items[0].item_key, "ITEM-SAME")
		self.assertEqual(doc.order_items[1].item_key, "ITEM-DIFFERENT")

	def test_supplied_duplicate_item_keys_are_rejected(self):
		doc = deal("Product Printing", order_items=[studio_item(1), studio_item(2)])
		with self.assertRaises(frappe.ValidationError):
			ensure_item_keys(doc)

	def test_generated_item_key_is_stable_after_recalculation_and_persisted_reload(self):
		item = studio_item(key="", name="new-crm-order-item-1")
		doc = deal("Product Printing", order_items=[item])
		ensure_item_keys(doc)
		generated_key = item.item_key
		doc.order_applications = [application(key=generated_key)]
		validate_and_calculate_order(doc)

		item.name = "CRM-ORDER-ITEM-0001"
		self.stored_items[item.name] = {
			"item_key": generated_key,
			"product": item.product,
			"base_rate": item.base_rate,
		}
		item.item_key = "CLIENT-TAMPERED-KEY"
		item.base_rate = 999999
		validate_and_calculate_order(doc)

		self.assertEqual(item.item_key, generated_key)
		self.assertEqual(item.base_rate, 500)

	def test_new_studio_product_ignores_tampered_base_rate(self):
		item = studio_item(base_rate=999999)
		doc = product_printing(item)
		validate_and_calculate_order(doc)
		self.assertEqual(item.base_rate, 500)
		self.assertEqual(item.rate, 500)

	def test_missing_or_unpriced_studio_product_is_rejected(self):
		self.catalog_rates["UNPRICED-PRODUCT"] = ""
		for product in ("MISSING-PRODUCT", "UNPRICED-PRODUCT"):
			with self.subTest(product=product):
				with self.assertRaises(frappe.ValidationError):
					validate_and_calculate_order(product_printing(studio_item(product=product)))

	def test_unchanged_product_uses_saved_snapshot_on_repeat_save(self):
		item = studio_item(name="CRM-ORDER-ITEM-1", base_rate=999999)
		self.stored_items[item.name] = {
			"item_key": item.item_key,
			"product": "TEST-PRODUCT",
			"base_rate": 425,
		}
		validate_and_calculate_order(product_printing(item))
		self.assertEqual(item.base_rate, 425)

	def test_catalog_price_change_does_not_change_saved_snapshot(self):
		item = studio_item(name="CRM-ORDER-ITEM-2")
		self.stored_items[item.name] = {
			"item_key": item.item_key,
			"product": "TEST-PRODUCT",
			"base_rate": 500,
		}
		self.catalog_rates["TEST-PRODUCT"] = 900
		validate_and_calculate_order(product_printing(item))
		self.assertEqual(item.base_rate, 500)

	def test_product_change_takes_new_catalog_snapshot(self):
		item = studio_item(name="CRM-ORDER-ITEM-3", product="OTHER-PRODUCT", base_rate=1)
		self.stored_items[item.name] = {
			"item_key": item.item_key,
			"product": "TEST-PRODUCT",
			"base_rate": 500,
		}
		validate_and_calculate_order(product_printing(item))
		self.assertEqual(item.base_rate, 800)
		self.assertEqual(item.rate, 800)

	def test_customer_item_always_has_zero_effective_rate(self):
		item = studio_item(
			supply_type="Customer Item",
			product="TEST-PRODUCT",
			base_rate=700,
			use_manual_rate=1,
			manual_rate=600,
		)
		validate_and_calculate_order(product_printing(item))
		self.assertEqual(item.base_rate, 0)
		self.assertEqual(item.rate, 0)
		self.assertEqual(item.amount, 0)
		self.assertFalse(any(call.args[0] == "CRM Product" for call in self.mock_get_value.call_args_list))

	def test_manual_rate_amount_and_total_preserve_zero(self):
		doc = deal(
			"Product Printing",
			order_items=[studio_item(use_manual_rate=1, manual_rate=0)],
			order_applications=[application(use_manual_amount=1, manual_amount=0)],
			use_manual_total=1,
			manual_order_total=0,
		)
		validate_and_calculate_order(doc)
		self.assertEqual(doc.order_items[0].rate, 0)
		self.assertEqual(doc.order_applications[0].amount, 0)
		self.assertEqual(doc.manual_order_total, 0)
		self.assertEqual(doc.order_total, 0)

	def test_disabled_manual_values_do_not_affect_calculation(self):
		doc = deal(
			"DTF Roll",
			dtf_roll_lines=[roll_line(length_m=2, rate_per_meter=10, manual_amount=999)],
			manual_order_total=999,
		)
		validate_and_calculate_order(doc)
		self.assertEqual(doc.dtf_roll_lines[0].amount, 20)
		self.assertEqual(doc.order_total, 20)

	def test_round_half_up_is_applied_to_rates_discount_and_amounts(self):
		self.catalog_rates["TEST-PRODUCT"] = 0.105
		item = studio_item(qty=3, discount_percentage=5)
		doc = product_printing(item, application(rate=0))
		validate_and_calculate_order(doc)
		self.assertEqual(Decimal(str(item.rate)), Decimal("0.11"))
		self.assertEqual(Decimal(str(item.gross_amount)), Decimal("0.33"))
		self.assertEqual(Decimal(str(item.discount_amount)), Decimal("0.02"))
		self.assertEqual(Decimal(str(item.amount)), Decimal("0.31"))

	def test_fractional_discount_percentage_stays_decimal(self):
		self.mock_get_precision.return_value = 3
		item = studio_item(qty=1, discount_percentage=Decimal("12.345"))
		doc = product_printing(item, application(rate=0))
		validate_and_calculate_order(doc)

		expected_discount_amount = Decimal("61.725")
		expected_amount = Decimal("438.275")
		self.assertIsInstance(item.discount_percentage, Decimal)
		self.assertEqual(item.discount_percentage, Decimal("12.345"))
		self.assertEqual(Decimal(str(item.discount_amount)), expected_discount_amount)
		self.assertEqual(Decimal(str(item.amount)), expected_amount)

	def test_decimal_multiplication_and_multi_line_sum_have_no_float_residue(self):
		doc = deal(
			"DTF Pieces",
			dtf_piece_lines=[piece_line(idx, qty=1, unit_price=0.1) for idx in range(1, 4)],
		)
		validate_and_calculate_order(doc)
		self.assertEqual([Decimal(str(line.amount)) for line in doc.dtf_piece_lines], [Decimal("0.1")] * 3)
		self.assertEqual(Decimal(str(doc.dtf_piece_subtotal)), Decimal("0.3"))
		self.assertEqual(Decimal(str(doc.order_total)), Decimal("0.3"))

	def test_dtf_roll_calculation(self):
		doc = deal("DTF Roll", dtf_roll_lines=[roll_line(length_m=2.5, rate_per_meter=400)])
		validate_and_calculate_order(doc)
		self.assertEqual(doc.dtf_roll_subtotal, 1000)
		self.assertEqual(doc.order_total, 1000)

	def test_dtf_pieces_accepts_literal_formats_and_clears_incompatible_fields(self):
		expected_formats = ("A6", "A5", "A4", "A3", "A3+", "A3++")
		lines = [
			piece_line(
				idx,
				"Format",
				qty=1,
				unit_price=10,
				sheet_format=sheet_format,
				width_cm=99,
				height_cm=99,
			)
			for idx, sheet_format in enumerate(expected_formats, 1)
		]
		lines.extend(
			(
				piece_line(7, "Custom Size", width_cm=12, height_cm=18, sheet_format="A4"),
				piece_line(8, "Quantity Only", width_cm=12, height_cm=18, sheet_format="A4"),
				piece_line(9, "Custom Size", width_cm=None, height_cm=None),
			)
		)
		doc = deal("DTF Pieces", dtf_piece_lines=lines)
		validate_and_calculate_order(doc)

		for format_line in lines[:6]:
			self.assertIsNone(format_line.width_cm)
			self.assertIsNone(format_line.height_cm)
		self.assertIsNone(lines[6].sheet_format)
		self.assertEqual((lines[6].width_cm, lines[6].height_cm), (12, 18))
		self.assertIsNone(lines[7].sheet_format)
		self.assertIsNone(lines[7].width_cm)
		self.assertIsNone(lines[7].height_cm)
		self.assertIsNone(lines[8].width_cm)
		self.assertIsNone(lines[8].height_cm)

	def test_all_literal_production_types_are_accepted(self):
		expected_types = (
			"DTF Printing",
			"Screen Printing",
			"Embroidery",
			"Sublimation",
			"Heat Transfer Printing",
			"Artwork Preparation",
			"Combined",
		)
		for production_type in expected_types:
			with self.subTest(production_type=production_type):
				validate_and_calculate_order(
					product_printing(studio_item(), application(production_type=production_type))
				)

	def test_combined_accepts_each_pair_of_complete_business_categories(self):
		valid_documents = (
			deal(
				"Combined",
				order_items=[studio_item()],
				order_applications=[application()],
				dtf_roll_lines=[roll_line()],
			),
			deal(
				"Combined",
				order_items=[studio_item()],
				order_applications=[application()],
				dtf_piece_lines=[piece_line()],
			),
			deal("Combined", dtf_roll_lines=[roll_line()], dtf_piece_lines=[piece_line()]),
		)
		for doc in valid_documents:
			with self.subTest(groups=tuple(bool(doc.get(table)) for table in NEW_TABLES)):
				validate_and_calculate_order(doc)

	def test_combined_rejects_one_or_incomplete_business_category(self):
		invalid_documents = (
			product_printing(studio_item(), application(), order_type="Combined"),
			deal("Combined", order_items=[studio_item()], dtf_roll_lines=[roll_line()]),
			deal("Combined", order_applications=[application()], dtf_roll_lines=[roll_line()]),
			deal("Combined", dtf_roll_lines=[roll_line()]),
		)
		for doc in invalid_documents:
			with self.subTest(groups=tuple(bool(doc.get(table)) for table in NEW_TABLES)):
				with self.assertRaises(frappe.ValidationError):
					validate_and_calculate_order(doc)

	def test_server_overwrites_all_client_totals(self):
		line = roll_line(length_m=3, rate_per_meter=200)
		line.calculated_amount = 1
		line.amount = 1
		doc = deal("DTF Roll", dtf_roll_lines=[line])
		validate_and_calculate_order(doc)
		self.assertEqual(line.calculated_amount, 600)
		self.assertEqual(line.amount, 600)
		self.assertEqual(doc.subtotal, 600)
		self.assertEqual(doc.order_total, 600)
		self.assertEqual(doc.deal_value, 600)

	def test_tracking_and_attribution_fields_survive_calculate_and_full_validate(self):
		doc = MagicMock()
		tracking = {
			"first_touch_source": "Website",
			"first_touch_channel": "Website",
			"campaign_name": "August",
			"tracking_code": "TRACK-42",
			"utm_source": "yandex",
			"yclid": "clid-1",
		}
		data = deal("DTF Roll", dtf_roll_lines=[roll_line()], **tracking)
		doc.get.side_effect = data.get
		for key, value in data.items():
			setattr(doc, key, value)
		doc.is_new.return_value = False
		doc.has_value_changed.return_value = False

		CRMDeal.validate(doc)

		self.assertEqual({key: getattr(doc, key) for key in tracking}, tracking)

	def test_application_quantity_and_unknown_key_are_rejected(self):
		invalid_documents = (
			product_printing(studio_item(), application(key="UNKNOWN")),
			product_printing(studio_item(qty=1), application(qty=2)),
		)
		for doc in invalid_documents:
			with self.assertRaises(frappe.ValidationError):
				validate_and_calculate_order(doc)

	def test_invalid_values_and_modes_are_rejected(self):
		invalid_documents = (
			deal("DTF Roll", dtf_roll_lines=[roll_line(length_m=0)]),
			deal("DTF Roll", dtf_roll_lines=[roll_line(rate_per_meter=-1)]),
			deal("DTF Roll", dtf_roll_lines=[roll_line(manual_amount=-1)]),
			deal("DTF Pieces", dtf_piece_lines=[piece_line(qty=0)]),
			deal("DTF Pieces", dtf_piece_lines=[piece_line(unit_price=-1)]),
			deal("DTF Pieces", dtf_piece_lines=[piece_line(sizing_mode="Format", sheet_format="A2")]),
			product_printing(studio_item(discount_percentage=101), application()),
			product_printing(studio_item(manual_rate=-1), application()),
			deal("DTF Roll", dtf_roll_lines=[roll_line()], manual_order_total=-1),
		)
		for doc in invalid_documents:
			with self.subTest(order_type=doc.order_type):
				with self.assertRaises(frappe.ValidationError):
					validate_and_calculate_order(doc)

	def test_single_order_types_reject_other_categories(self):
		invalid_documents = (
			deal(
				"Product Printing",
				order_items=[studio_item()],
				order_applications=[application()],
				dtf_roll_lines=[roll_line()],
			),
			deal("DTF Roll", dtf_roll_lines=[roll_line()], dtf_piece_lines=[piece_line()]),
			deal("DTF Pieces", dtf_piece_lines=[piece_line()], dtf_roll_lines=[roll_line()]),
		)
		for doc in invalid_documents:
			with self.assertRaises(frappe.ValidationError):
				validate_and_calculate_order(doc)


class TestOrderPaymentRegression(FrappeTestCase):
	def payment_doc(self, payment_status="Unpaid", paid_amount=25, order_total=100):
		return frappe._dict(
			order_total=order_total,
			paid_amount=paid_amount,
			balance_amount=999,
			payment_status=payment_status,
			payment_terms="Prepayment",
		)

	def test_payment_summary_and_balance_still_work(self):
		doc = self.payment_doc()
		with patch(
			"crm.fcrm.doctype.crm_deal.order_calculations.get_currency_precision",
			return_value=2,
		):
			CRMDeal.update_payment_summary(doc)
		self.assertEqual(doc.balance_amount, 75)
		self.assertEqual(doc.payment_status, "Partially Paid")

	def test_cancelled_and_refunded_statuses_are_not_overwritten(self):
		for status in ("Cancelled", "Refunded"):
			doc = self.payment_doc(status)
			CRMDeal.update_payment_summary(doc)
			self.assertEqual(doc.balance_amount, 75)
			self.assertEqual(doc.payment_status, status)

	def test_paid_amount_above_order_total_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			CRMDeal.update_payment_summary(self.payment_doc(paid_amount=101))

	def test_payment_history_calculates_paid_balance_status_and_last_date(self):
		doc = self.payment_doc(paid_amount=999)
		doc.meta = MagicMock()
		doc.meta.get_field.return_value = frappe._dict(fieldname="payments")
		doc.payments = [
			frappe._dict(amount=25, paid_at="2026-08-28 10:15:00", payment_method="Cash"),
			frappe._dict(amount=35, paid_at="2026-08-29 18:45:00", payment_method="Bank Card"),
		]

		with patch(
			"crm.fcrm.doctype.crm_deal.order_calculations.get_currency_precision",
			return_value=2,
		):
			CRMDeal.update_payment_summary(doc)

		self.assertEqual(doc.paid_amount, 60)
		self.assertEqual(doc.balance_amount, 40)
		self.assertEqual(doc.payment_status, "Partially Paid")
		self.assertEqual(str(doc.last_payment_date), "2026-08-29")
		self.assertEqual(doc.payment_method, "Bank Card")

	def test_payment_history_accepts_decimal_paid_amount_from_currency_rounding(self):
		doc = self.payment_doc(order_total=100.5)
		doc.meta = MagicMock()
		doc.meta.get_field.return_value = frappe._dict(fieldname="payments")
		doc.payments = [
			frappe._dict(
				amount=Decimal("25.25"),
				paid_at="2026-08-29 18:45:00",
				payment_method="Cash",
			)
		]

		with patch(
			"crm.fcrm.doctype.crm_deal.order_calculations.get_currency_precision",
			return_value=2,
		):
			CRMDeal.update_payment_summary(doc)

		self.assertEqual(doc.paid_amount, Decimal("25.25"))
		self.assertEqual(doc.balance_amount, 75.25)

	def test_empty_payment_history_clears_the_derived_paid_amount(self):
		doc = self.payment_doc(paid_amount=25)
		doc.meta = MagicMock()
		doc.meta.get_field.return_value = frappe._dict(fieldname="payments")
		doc.payments = []

		with patch(
			"crm.fcrm.doctype.crm_deal.order_calculations.get_currency_precision",
			return_value=2,
		):
			CRMDeal.update_payment_summary(doc)

		self.assertEqual(doc.paid_amount, 0)
		self.assertEqual(doc.balance_amount, 100)
		self.assertEqual(doc.payment_status, "Unpaid")


class TestOrderPersistence(FrappeTestCase):
	def test_generated_key_snapshot_and_attribution_survive_save_reload(self):
		from crm.fcrm.doctype.crm_deal.test_crm_deal import create_test_deal

		suffix = frappe.generate_hash(length=8)
		product = frappe.get_doc(
			{
				"doctype": "CRM Product",
				"product_code": f"SNAPSHOT-{suffix}",
				"product_name": f"Snapshot Product {suffix}",
				"standard_rate": 0.105,
			}
		).insert(ignore_permissions=True)
		deal_doc = create_test_deal(
			organization=f"Order Persistence {suffix}",
			order_type="Product Printing",
			tracking_code=f"TRACK-{suffix}",
			utm_source="persistence-test",
		)
		item = deal_doc.append(
			"order_items",
			{
				"supply_type": "Studio Product",
				"product": product.name,
				"qty": 2,
				"base_rate": 999999,
			},
		)
		ensure_item_keys(deal_doc)
		generated_key = item.item_key
		deal_doc.append(
			"order_applications",
			{
				"item_key": generated_key,
				"production_type": "DTF Printing",
				"placement": "Chest",
				"qty": 1,
				"rate": 10,
			},
		)

		deal_doc.save(ignore_permissions=True)
		deal_doc.reload()
		self.assertEqual(deal_doc.order_items[0].item_key, generated_key)
		self.assertEqual(Decimal(str(deal_doc.order_items[0].base_rate)), Decimal("0.11"))
		self.assertEqual(Decimal(str(deal_doc.order_items[0].gross_amount)), Decimal("0.22"))
		self.assertEqual(Decimal(str(deal_doc.order_total)), Decimal("10.22"))

		frappe.db.set_value("CRM Product", product.name, "standard_rate", 900)
		deal_doc.order_items[0].item_key = "CLIENT-TAMPERED-KEY"
		deal_doc.order_items[0].base_rate = 1
		deal_doc.save(ignore_permissions=True)
		deal_doc.reload()

		self.assertEqual(deal_doc.order_items[0].item_key, generated_key)
		self.assertEqual(Decimal(str(deal_doc.order_items[0].base_rate)), Decimal("0.11"))
		self.assertEqual(deal_doc.tracking_code, f"TRACK-{suffix}")
		self.assertEqual(deal_doc.utm_source, "persistence-test")


NEW_TABLES = ("order_items", "order_applications", "dtf_roll_lines", "dtf_piece_lines")


def row(idx=1, **values):
	return frappe._dict(idx=idx, **values)


def deal(order_type, **values):
	data = {
		"order_type": order_type,
		"order_items": [],
		"order_applications": [],
		"dtf_roll_lines": [],
		"dtf_piece_lines": [],
		"use_manual_total": 0,
		"manual_order_total": 0,
		"order_total": 999999,
		"deal_value": 999999,
		"items_subtotal": 999999,
		"applications_subtotal": 999999,
		"dtf_roll_subtotal": 999999,
		"dtf_piece_subtotal": 999999,
		"discount_amount": 999999,
		"subtotal": 999999,
	}
	data.update(values)
	return frappe._dict(data)


def studio_item(idx=1, key="ITEM-001", qty=2, base_rate=500, **values):
	data = {
		"item_key": key,
		"supply_type": "Studio Product",
		"product": "TEST-PRODUCT",
		"qty": qty,
		"base_rate": base_rate,
		"use_manual_rate": 0,
		"manual_rate": 0,
		"discount_percentage": 0,
	}
	data.update(values)
	return row(idx, **data)


def application(idx=1, key="ITEM-001", qty=1, rate=100, **values):
	data = {
		"item_key": key,
		"production_type": "DTF Printing",
		"placement": "Chest",
		"qty": qty,
		"rate": rate,
		"use_manual_amount": 0,
		"manual_amount": 0,
	}
	data.update(values)
	return row(idx, **data)


def roll_line(idx=1, length_m=2, rate_per_meter=300, **values):
	data = {
		"length_m": length_m,
		"rate_per_meter": rate_per_meter,
		"use_manual_amount": 0,
		"manual_amount": 0,
	}
	data.update(values)
	return row(idx, **data)


def piece_line(idx=1, sizing_mode="Quantity Only", qty=2, unit_price=50, **values):
	data = {
		"sizing_mode": sizing_mode,
		"qty": qty,
		"unit_price": unit_price,
		"use_manual_amount": 0,
		"manual_amount": 0,
	}
	data.update(values)
	return row(idx, **data)


def product_printing(item, print_application=None, order_type="Product Printing"):
	return deal(
		order_type,
		order_items=[item],
		order_applications=[print_application or application(key=item.item_key)],
	)
