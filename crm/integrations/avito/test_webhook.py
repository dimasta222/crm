from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import get_datetime

from crm.integrations.avito import webhook as avito_webhook
from crm.integrations.avito.webhook import _attachment_type, _attachment_url, _message_text
from crm.tests import CRMTestCase


class TestAvitoWebhook(UnitTestCase):
	def test_reads_supported_text_content(self):
		self.assertEqual(_message_text("text", {"text": "Привет"}), "Привет")
		self.assertEqual(
			_message_text("link", {"link": {"text": "Ссылка", "url": "https://example.com"}}),
			"Ссылка",
		)

	def test_uses_largest_image_from_webhook(self):
		content = {
			"image": {
				"sizes": {
					"32x32": "https://example.com/small.jpg",
					"1280x960": "https://example.com/large.jpg",
				}
			}
		}
		self.assertEqual(_attachment_url("image", content), "https://example.com/large.jpg")
		self.assertEqual(_attachment_type("image"), "Image")

	def test_ignores_unknown_attachment_formats(self):
		self.assertIsNone(_attachment_url("file", {}))
		self.assertIsNone(_attachment_type("system"))


class TestAvitoWebhookIntegration(CRMTestCase):
	def tearDown(self):
		frappe.db.rollback()
		super().tearDown()

	def test_timezone_aware_timestamp_creates_message(self):
		payload = {
			"payload": {
				"type": "message",
				"value": {
					"id": "avito-message-1",
					"chat_id": "avito-chat-1",
					"user_id": "avito-account-1",
					"author_id": "avito-customer-1",
					"created": "2026-09-01T10:00:00+00:00",
					"type": "text",
					"content": {"text": "Здравствуйте"},
				},
			}
		}
		with (
			patch.object(avito_webhook, "_validate_token"),
			patch.object(avito_webhook, "_request_payload", return_value=payload),
			patch.object(avito_webhook.frappe, "enqueue"),
		):
			result = avito_webhook.receive()

		message = frappe.get_doc("CRM Channel Message", result["message"])
		stored = get_datetime(message.sent_at)
		self.assertEqual(message.direction, "Incoming")
		self.assertIsNone(stored.tzinfo)
		self.assertNotIn("+00:00", str(message.sent_at))
