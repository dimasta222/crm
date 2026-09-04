import frappe

from crm.tests import CRMTestCase


class TestCRMChannelSettings(CRMTestCase):
	def test_business_username_is_normalized(self):
		settings = frappe.new_doc("CRM Channel Settings")
		settings.telegram_bot_username = "FutureStudioBot"
		settings.telegram_business_username = "  @FutureStudioBusiness  "

		settings.validate()

		self.assertEqual(settings.telegram_business_username, "FutureStudioBusiness")

	def test_business_username_cannot_match_technical_bot(self):
		settings = frappe.new_doc("CRM Channel Settings")
		settings.telegram_bot_username = "FutureStudioBot"
		settings.telegram_business_username = "@futurestudiobot"

		with self.assertRaises(frappe.ValidationError):
			settings.validate()

	def test_invalid_business_username_is_rejected(self):
		settings = frappe.new_doc("CRM Channel Settings")
		settings.telegram_bot_username = "FutureStudioBot"
		settings.telegram_business_username = "not a username"

		with self.assertRaises(frappe.ValidationError):
			settings.validate()
