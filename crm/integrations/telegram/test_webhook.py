from frappe.tests import UnitTestCase

from crm.integrations.telegram.webhook import _attachment_type, _message_from_update


class TestTelegramWebhook(UnitTestCase):
	def test_business_message_keeps_connection_id(self):
		message = {"message_id": 1, "business_connection_id": "connection-1"}
		self.assertEqual(
			_message_from_update({"business_message": message}),
			(message, "connection-1"),
		)

	def test_detects_telegram_attachments(self):
		self.assertEqual(_attachment_type({"photo": [{}]}), "Photo")
		self.assertEqual(_attachment_type({"voice": {"file_id": "voice-1"}}), "Voice")
		self.assertIsNone(_attachment_type({"text": "Привет"}))
