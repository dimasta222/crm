# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from decimal import Decimal

import frappe
from frappe import _
from frappe.desk.form.assign_to import _add as assign
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, getdate, now_datetime

from crm.api.exchange_rate import get_exchange_rate
from crm.api.tracking import (
	ATTRIBUTION_FIELDS,
	copy_attribution,
	copy_attribution_to_contact,
	ensure_first_touch_timestamp,
)
from crm.fcrm.doctype.crm_service_level_agreement.utils import get_sla
from crm.fcrm.doctype.crm_status_change_log.crm_status_change_log import add_status_change_log
from crm.fcrm.doctype.utils import add_or_remove_lost_reason_section_in_sidepanel


class CRMDeal(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from crm.fcrm.doctype.crm_contacts.crm_contacts import CRMContacts
		from crm.fcrm.doctype.crm_dtf_piece_line.crm_dtf_piece_line import CRMDTFPieceLine
		from crm.fcrm.doctype.crm_dtf_roll_line.crm_dtf_roll_line import CRMDTFRollLine
		from crm.fcrm.doctype.crm_order_application.crm_order_application import CRMOrderApplication
		from crm.fcrm.doctype.crm_deal_payment.crm_deal_payment import CRMDealPayment
		from crm.fcrm.doctype.crm_order_item.crm_order_item import CRMOrderItem
		from crm.fcrm.doctype.crm_products.crm_products import CRMProducts
		from crm.fcrm.doctype.crm_rolling_response_time.crm_rolling_response_time import (
			CRMRollingResponseTime,
		)
		from crm.fcrm.doctype.crm_status_change_log.crm_status_change_log import CRMStatusChangeLog

		annual_revenue: DF.Currency
		applications_subtotal: DF.Currency
		closed_date: DF.Date | None
		communication_status: DF.Link | None
		contact: DF.Link | None
		contacts: DF.Table[CRMContacts]
		currency: DF.Link | None
		deal_owner: DF.Link | None
		deal_value: DF.Currency
		discount_amount: DF.Currency
		dtf_piece_lines: DF.Table[CRMDTFPieceLine]
		dtf_piece_subtotal: DF.Currency
		dtf_roll_lines: DF.Table[CRMDTFRollLine]
		dtf_roll_subtotal: DF.Currency
		email: DF.Data | None
		exchange_rate: DF.Float
		expected_closure_date: DF.Date | None
		expected_deal_value: DF.Currency
		first_name: DF.Data | None
		first_responded_on: DF.Datetime | None
		first_response_time: DF.Duration | None
		gender: DF.Link | None
		industry: DF.Link | None
		items_subtotal: DF.Currency
		job_title: DF.Data | None
		last_name: DF.Data | None
		last_responded_on: DF.Datetime | None
		last_response_time: DF.Duration | None
		lead: DF.Link | None
		lead_name: DF.Data | None
		lost_notes: DF.Text | None
		lost_reason: DF.Link | None
		mobile_no: DF.Data | None
		manual_order_total: DF.Currency
		naming_series: DF.Literal["CRM-DEAL-.YYYY.-"]
		net_total: DF.Currency
		next_step: DF.Data | None
		no_of_employees: DF.Literal["1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"]
		organization: DF.Link | None
		organization_name: DF.Data | None
		order_applications: DF.Table[CRMOrderApplication]
		order_items: DF.Table[CRMOrderItem]
		payments: DF.Table[CRMDealPayment]
		order_type: DF.Literal["", "Product Printing", "DTF Roll", "DTF Pieces", "Combined"]
		phone: DF.Data | None
		probability: DF.Percent
		products: DF.Table[CRMProducts]
		response_by: DF.Datetime | None
		rolling_responses: DF.Table[CRMRollingResponseTime]
		salutation: DF.Link | None
		sla: DF.Link | None
		sla_creation: DF.Datetime | None
		sla_status: DF.Literal["", "First Response Due", "Rolling Response Due", "Failed", "Fulfilled"]
		source: DF.Link | None
		status: DF.Link
		status_change_log: DF.Table[CRMStatusChangeLog]
		subtotal: DF.Currency
		territory: DF.Link | None
		total: DF.Currency
		use_manual_total: DF.Check
		website: DF.Data | None
	# end: auto-generated types

	def before_validate(self):
		from crm.fcrm.doctype.crm_deal.order_calculations import ensure_item_keys

		ensure_item_keys(self)
		if not self.currency:
			self.currency = frappe.db.get_single_value("FCRM Settings", "currency") or "RUB"
		if self.source and not self.first_touch_source:
			self.first_touch_source = self.source
		ensure_first_touch_timestamp(self)
		self.set_sla()

	def validate(self):
		self.validate_status()
		from crm.fcrm.doctype.crm_deal.order_calculations import (
			uses_new_order_model,
			validate_and_calculate_order,
		)

		if uses_new_order_model(self):
			validate_and_calculate_order(self)
		else:
			self.set_item_references()
			self.validate_application_references()
			self.calculate_order_totals()
		self.update_payment_summary()
		self.validate_first_touch()
		self.set_primary_contact()
		self.set_primary_email_mobile_no()
		if not self.is_new() and self.has_value_changed("deal_owner") and self.deal_owner:
			self.share_with_agent(self.deal_owner)
			self.assign_agent(self.deal_owner)
		if self.has_value_changed("status"):
			add_status_change_log(self)
			if frappe.db.get_value("CRM Deal Status", self.status, "type") == "Won":
				self.closed_date = frappe.utils.nowdate()
		self.validate_forecasting_fields()
		self.validate_lost_reason()
		self.update_exchange_rate()

	def after_insert(self):
		if self.deal_owner:
			if self.deal_owner != frappe.session.user:
				self.share_with_agent(self.deal_owner)
			self.assign_agent(self.deal_owner)

	def before_save(self):
		self.apply_sla()

	def validate_status(self):
		if self.is_new() and not self.status:
			if frappe.db.exists("CRM Deal Status", "New Order"):
				self.status = "New Order"
			else:
				self.status = frappe.get_all("CRM Deal Status", {"type": "Open"}, pluck="name")[0]

	def set_item_references(self):
		for index, item in enumerate(self.products or [], 1):
			if not item.item_reference:
				item.item_reference = f"ITEM-{index:03d}"
			if flt(item.qty) <= 0:
				frappe.throw(_("Order item {0} must have a quantity greater than zero.").format(index))
			if flt(item.rate) < 0:
				frappe.throw(_("Order item {0} cannot have a negative rate.").format(index))
		if len(self.products or []) == 1:
			item_reference = self.products[0].item_reference
			for application in self.applications or []:
				if not application.item_reference:
					application.item_reference = item_reference

	def validate_application_references(self):
		item_reference_list = [item.item_reference for item in self.products or []]
		if len(item_reference_list) != len(set(item_reference_list)):
			frappe.throw(_("Every order item must have a unique item reference."))
		item_references = set(item_reference_list)
		for application in self.applications or []:
			if not application.item_reference:
				frappe.throw(_("Select an order item for application row {0}.").format(application.idx))
			if application.item_reference not in item_references:
				frappe.throw(
					_("Application row {0} refers to an unknown item: {1}").format(
						application.idx, application.item_reference
					)
				)
			if flt(application.quantity) <= 0:
				frappe.throw(
					_("Application row {0} must have a quantity greater than zero.").format(application.idx)
				)

	def calculate_order_totals(self):
		previous_order_total = flt(self.order_total)
		total = 0
		net_total = 0
		for item in self.products or []:
			item.amount = flt(item.qty) * flt(item.rate)
			item.discount_amount = item.amount * flt(item.discount_percentage) / 100
			item.net_amount = item.amount - item.discount_amount
			total += item.amount
			net_total += item.net_amount
		self.total = total
		self.net_total = net_total
		if self.has_value_changed("order_total"):
			self.order_total = previous_order_total
		elif self.products:
			self.order_total = flt(self.net_total)
		elif self.has_value_changed("deal_value"):
			self.order_total = flt(self.deal_value)
		else:
			self.order_total = previous_order_total or flt(self.deal_value or self.total)
		self.deal_value = self.order_total

	def update_payment_summary(self):
		payments = self.get("payments") or []
		has_payment_history = bool(
			getattr(self, "meta", None) and self.meta.get_field("payments")
		)
		if has_payment_history:
			from crm.fcrm.doctype.crm_deal.order_calculations import (
				get_currency_precision,
				round_money,
			)

			paid_amount = Decimal("0")
			latest_payment = None
			for index, payment in enumerate(payments, 1):
				amount = Decimal(str(payment.amount or 0))
				if amount <= 0:
					frappe.throw(
						_("Payment row {0} must have an amount greater than zero.").format(index)
					)
				if not payment.paid_at:
					payment.paid_at = now_datetime()
				paid_amount += amount
				paid_at = get_datetime(payment.paid_at)
				if latest_payment is None or paid_at > latest_payment.paid_at:
					latest_payment = frappe._dict(
						paid_at=paid_at, payment_method=payment.payment_method
					)

			self.paid_amount = round_money(paid_amount, get_currency_precision(self))
			self.last_payment_date = getdate(latest_payment.paid_at) if latest_payment else None
			self.payment_method = latest_payment.payment_method if latest_payment else None
		else:
			self.paid_amount = max(flt(self.paid_amount), 0)
		if flt(self.order_total) > 0 and self.paid_amount > flt(self.order_total):
			frappe.throw(_("Paid amount cannot exceed the order total."))
		self.balance_amount = max(flt(self.order_total) - self.paid_amount, 0)
		if self.payment_status in {"Cancelled", "Refunded"}:
			return
		if flt(self.order_total) > 0 and self.paid_amount >= flt(self.order_total):
			self.payment_status = "Paid"
		elif self.paid_amount > 0:
			self.payment_status = "Partially Paid"
		elif self.payment_terms == "Postpayment" and flt(self.order_total) > 0:
			self.payment_status = "Postpaid"
		else:
			self.payment_status = "Unpaid"

	def validate_first_touch(self):
		if self.is_new() or "System Manager" in frappe.get_roles():
			return
		old_doc = self.get_doc_before_save()
		if not old_doc or not old_doc.first_touch_at:
			return
		for fieldname in ATTRIBUTION_FIELDS:
			if self.has_value_changed(fieldname):
				frappe.throw(_("First-touch attribution can only be changed by a System Manager."))

	def set_primary_contact(self, contact=None):
		if not self.contacts:
			return

		if not contact and len(self.contacts) == 1:
			self.contacts[0].is_primary = 1
		elif contact:
			for d in self.contacts:
				if d.contact == contact:
					d.is_primary = 1
				else:
					d.is_primary = 0

	def set_primary_email_mobile_no(self):
		if not self.contacts:
			self.email = ""
			self.mobile_no = ""
			self.phone = ""
			return

		if len([contact for contact in self.contacts if contact.is_primary]) > 1:
			frappe.throw(_("Only one {0} can be set as primary.").format(frappe.bold("Contact")))

		primary_contact_exists = False
		for d in self.contacts:
			if d.is_primary == 1:
				primary_contact_exists = True
				self.email = d.email.strip() if d.email else ""
				self.mobile_no = d.mobile_no.strip() if d.mobile_no else ""
				self.phone = d.phone.strip() if d.phone else ""
				break

		if not primary_contact_exists:
			self.email = ""
			self.mobile_no = ""
			self.phone = ""

	def assign_agent(self, agent):
		if not agent:
			return

		assignees = self.get_assigned_users()
		if assignees:
			for assignee in assignees:
				if agent == assignee:
					# the agent is already set as an assignee
					return

		assign({"assign_to": [agent], "doctype": "CRM Deal", "name": self.name}, ignore_permissions=True)

	def share_with_agent(self, agent):
		if not agent:
			return

		docshares = frappe.get_all(
			"DocShare",
			filters={"share_name": self.name, "share_doctype": self.doctype},
			fields=["name", "user"],
		)

		shared_with = [d.user for d in docshares] + [agent]

		for user in shared_with:
			if user == agent and not frappe.db.exists(
				"DocShare",
				{"user": agent, "share_name": self.name, "share_doctype": self.doctype},
			):
				frappe.share.add_docshare(
					self.doctype,
					self.name,
					agent,
					write=1,
					flags={"ignore_share_permission": True},
				)
			elif user != agent:
				frappe.share.remove(
					self.doctype,
					self.name,
					user,
					flags={"ignore_share_permission": True, "ignore_permissions": True},
				)

	def set_sla(self):
		"""
		Find an SLA to apply to the deal.
		"""
		if self.sla:
			return

		sla = get_sla(self)
		if not sla:
			self.first_responded_on = None
			self.first_response_time = None
			return
		self.sla = sla.name

	def apply_sla(self):
		"""
		Apply SLA if set.
		"""
		if not self.sla:
			return
		sla = frappe.get_last_doc("CRM Service Level Agreement", {"name": self.sla})
		if sla:
			sla.apply(self)

	def update_closed_date(self):
		"""
		Update the closed date based on the "Won" status.
		"""
		if (
			self.status
			and frappe.get_cached_value("CRM Deal Status", self.status, "type") == "Won"
			and not self.closed_date
		):
			self.closed_date = frappe.utils.nowdate()

	def update_default_probability(self):
		"""
		Update the default probability based on the status.
		"""
		if not self.probability or self.probability == 0:
			self.probability = frappe.db.get_value("CRM Deal Status", self.status, "probability") or 0

	def update_expected_deal_value(self):
		"""
		Update the expected deal value based on the net total or total.
		"""
		if (
			frappe.db.get_single_value("FCRM Settings", "auto_update_expected_deal_value")
			and (self.net_total or self.total)
			and self.expected_deal_value
		):
			self.expected_deal_value = self.net_total or self.total

	def validate_forecasting_fields(self):
		self.update_closed_date()
		self.update_default_probability()
		self.update_expected_deal_value()
		if frappe.db.get_single_value("FCRM Settings", "enable_forecasting"):
			if not self.expected_deal_value or self.expected_deal_value == 0:
				frappe.throw(_("Expected deal value is required."), frappe.MandatoryError)
			if not self.expected_closure_date:
				frappe.throw(_("Expected closure date is required."), frappe.MandatoryError)

	def validate_lost_reason(self):
		"""
		Validate the lost reason if the status is set to "Lost".
		"""
		if self.status and frappe.get_cached_value("CRM Deal Status", self.status, "type") == "Lost":
			if not self.lost_reason:
				frappe.throw(_("Please specify a reason for losing the deal."), frappe.ValidationError)
			elif self.lost_reason == "Other" and not self.lost_notes:
				frappe.throw(_("Please specify the reason for losing the deal."), frappe.ValidationError)
		if self.has_value_changed("status"):
			add_or_remove_lost_reason_section_in_sidepanel(self)

	def update_exchange_rate(self):
		if self.has_value_changed("currency") or not self.exchange_rate:
			system_currency = frappe.db.get_single_value("FCRM Settings", "currency") or "USD"
			exchange_rate = 1
			if self.currency and self.currency != system_currency:
				exchange_rate = get_exchange_rate(self.currency, system_currency)

			self.db_set("exchange_rate", exchange_rate)

	@staticmethod
	def default_list_data():
		columns = [
			{
				"label": "Organization",
				"type": "Link",
				"key": "organization",
				"options": "CRM Organization",
				"width": "11rem",
			},
			{
				"label": "Annual Revenue",
				"type": "Currency",
				"key": "annual_revenue",
				"align": "right",
				"width": "9rem",
			},
			{
				"label": "Status",
				"type": "Link",
				"options": "CRM Deal Status",
				"key": "status",
				"width": "10rem",
			},
			{
				"label": "Email",
				"type": "Data",
				"key": "email",
				"width": "12rem",
			},
			{
				"label": "Mobile No.",
				"type": "Data",
				"key": "mobile_no",
				"width": "11rem",
			},
			{
				"label": "Assigned To",
				"type": "Text",
				"key": "_assign",
				"width": "10rem",
			},
			{
				"label": "Last Modified",
				"type": "Datetime",
				"key": "modified",
				"width": "8rem",
			},
		]
		rows = [
			"name",
			"organization",
			"annual_revenue",
			"status",
			"email",
			"currency",
			"mobile_no",
			"deal_owner",
			"sla_status",
			"response_by",
			"first_response_time",
			"first_responded_on",
			"modified",
			"_assign",
		]
		return {"columns": columns, "rows": rows}

	@staticmethod
	def default_kanban_settings():
		return {
			"column_field": "status",
			"title_field": "organization",
			"kanban_fields": '["annual_revenue", "email", "mobile_no", "_assign", "modified"]',
		}


@frappe.whitelist()
def add_contact(deal: str, contact: str):
	if not frappe.has_permission("CRM Deal", "write", deal):
		frappe.throw(_("Not allowed to add contact to Deal"), frappe.PermissionError)

	deal = frappe.get_cached_doc("CRM Deal", deal)
	deal.append("contacts", {"contact": contact})
	deal.save()
	return True


@frappe.whitelist()
def remove_contact(deal: str, contact: str):
	if not frappe.has_permission("CRM Deal", "write", deal):
		frappe.throw(_("Not allowed to remove contact from Deal"), frappe.PermissionError)

	deal = frappe.get_cached_doc("CRM Deal", deal)
	deal.contacts = [d for d in deal.contacts if d.contact != contact]
	deal.save()
	return True


@frappe.whitelist()
def set_primary_contact(deal: str, contact: str):
	if not frappe.has_permission("CRM Deal", "write", deal):
		frappe.throw(_("Not allowed to set primary contact for Deal"), frappe.PermissionError)

	deal = frappe.get_cached_doc("CRM Deal", deal)
	deal.set_primary_contact(contact)
	deal.save()
	return True


def create_organization(doc):
	if not doc.get("organization_name"):
		return

	existing_organization = frappe.db.exists(
		"CRM Organization", {"organization_name": doc.get("organization_name")}
	)
	if existing_organization:
		return existing_organization

	organization = frappe.new_doc("CRM Organization")
	organization.update(
		{
			"organization_name": doc.get("organization_name"),
			"website": doc.get("website"),
			"territory": doc.get("territory"),
			"industry": doc.get("industry"),
			"annual_revenue": doc.get("annual_revenue"),
		}
	)
	organization.insert(ignore_permissions=True)
	return organization.name


def contact_exists(doc):
	email_exist = frappe.db.exists("Contact Email", {"email_id": doc.get("email")})
	mobile_exist = frappe.db.exists("Contact Phone", {"phone": doc.get("mobile_no")})

	doctype = "Contact Email" if email_exist else "Contact Phone"
	name = email_exist or mobile_exist

	if name:
		return frappe.db.get_value(doctype, name, "parent")

	return False


def create_contact(doc):
	existing_contact = contact_exists(doc)
	if existing_contact:
		copy_attribution_to_contact(doc, existing_contact)
		return existing_contact

	contact = frappe.new_doc("Contact")
	contact.update(
		{
			"first_name": doc.get("first_name"),
			"last_name": doc.get("last_name"),
			"salutation": doc.get("salutation"),
			"company_name": doc.get("organization") or doc.get("organization_name"),
			"gender": doc.get("gender"),
		}
	)

	if doc.get("email"):
		contact.append("email_ids", {"email_id": doc.get("email"), "is_primary": 1})

	if doc.get("mobile_no"):
		contact.append("phone_nos", {"phone": doc.get("mobile_no"), "is_primary_mobile_no": 1})

	contact.insert(ignore_permissions=True)
	contact.reload()  # load changes by hooks on contact
	copy_attribution_to_contact(doc, contact.name)

	return contact.name


@frappe.whitelist()
def create_deal(doc: dict):
	deal = frappe.new_doc("CRM Deal")

	contact = doc.get("contact")
	if not contact and (
		doc.get("first_name") or doc.get("last_name") or doc.get("email") or doc.get("mobile_no")
	):
		contact = create_contact(doc)

	deal.update(
		{
			"organization": doc.get("organization") or create_organization(doc),
			"contacts": [{"contact": contact, "is_primary": 1}] if contact else [],
		}
	)

	doc.pop("organization", None)

	deal.update(doc)
	if deal.lead:
		copy_attribution(frappe.get_cached_doc("CRM Lead", deal.lead), deal)

	deal.insert(ignore_permissions=True)
	return deal.name
