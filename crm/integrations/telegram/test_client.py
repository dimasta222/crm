from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe.exceptions import ValidationError
from frappe.tests import UnitTestCase

from crm.api.omnichannel import _ingest_message
from crm.integrations.telegram import api as telegram_api
from crm.integrations.telegram import client as telegram_client
from crm.integrations.telegram.business_connection import (
	clear_cached_connection,
	upsert_business_connection,
)
from crm.tests import CRMTestCase


class TestTelegramClient(UnitTestCase):
	def test_request_failure_does_not_expose_bot_token(self):
		with (
			patch.object(
				telegram_client.telegram_api,
				"request",
				side_effect=telegram_api.TelegramTemporaryAPIError("network"),
			),
			self.assertRaises(ValidationError) as context,
		):
			telegram_client.subscribe_webhook("https://crm.example.test/webhook", "webhook-secret")
		self.assertEqual(str(context.exception), "Could not configure the Telegram webhook")

	def test_redirect_contains_one_business_chat_button(self):
		captured = {}

		def request(method, payload):
			captured.update(method=method, payload=payload)
			return {"ok": True, "result": {"message_id": 1}}

		with (
			patch.object(telegram_client, "value", return_value="  @FutureStudioBusiness  "),
			patch.object(telegram_client.telegram_api, "request", side_effect=request),
		):
			_result, has_button = telegram_client.send_bot_redirect("chat-1", 10)

		self.assertTrue(has_button)
		self.assertEqual(captured["method"], "sendMessage")
		self.assertEqual(captured["payload"]["chat_id"], "chat-1")
		self.assertEqual(captured["payload"]["reply_parameters"], {"message_id": 10})
		buttons = captured["payload"]["reply_markup"]["inline_keyboard"]
		self.assertEqual(len(buttons), 1)
		self.assertEqual(len(buttons[0]), 1)
		self.assertEqual(buttons[0][0]["url"], "https://t.me/FutureStudioBusiness")

	def test_empty_business_username_sends_safe_text_without_button(self):
		captured = {}

		def request(method, payload):
			captured.update(method=method, payload=payload)
			return {"ok": True, "result": {"message_id": 1}}

		with (
			patch.object(telegram_client, "value", return_value=""),
			patch.object(telegram_client.telegram_api, "request", side_effect=request),
		):
			_result, has_button = telegram_client.send_bot_redirect("chat-1")

		self.assertFalse(has_button)
		self.assertNotIn("reply_markup", captured["payload"])
		self.assertIn("временно недоступен", captured["payload"]["text"])

	def test_reply_without_can_reply_is_rejected_before_api_call(self):
		conversation = type(
			"Conversation",
			(),
			{"account_id": "connection-1", "external_chat_id": "chat-1"},
		)()
		connection = {
			"connection_id": "connection-1",
			"is_enabled": True,
			"can_reply": False,
		}
		with (
			patch.object(telegram_client, "resolve_business_connection", return_value=connection),
			patch.object(telegram_client.telegram_api, "request") as api_request,
			self.assertRaises(ValidationError) as context,
		):
			telegram_client._business_connection_for_reply(conversation)

		api_request.assert_not_called()
		self.assertIn("не разрешает отвечать", str(context.exception))


class TestTelegramBusinessClientIntegration(CRMTestCase):
	def setUp(self):
		super().setUp()
		suffix = uuid4().hex
		self.connection_id = f"connection-{suffix}"
		self.chat_id = f"chat-{suffix}"
		self.external_user_id = f"customer-{suffix}"
		upsert_business_connection(
			{
				"id": self.connection_id,
				"user": {
					"id": f"business-user-{suffix}",
					"username": "FutureStudioBusiness",
				},
				"user_chat_id": f"owner-chat-{suffix}",
				"date": 1788256800,
				"is_enabled": True,
				"rights": {
					"can_read_messages": True,
					"can_reply": True,
				},
			},
			source="webhook",
		)
		incoming = _ingest_message(
			channel="Telegram",
			account_id=self.connection_id,
			external_user_id=self.external_user_id,
			external_chat_id=self.chat_id,
			external_message_id="incoming-1",
			content="Incoming test",
			sender_name="Test Customer",
			sent_at=1788256800,
			direction="Incoming",
		)
		self.conversation = frappe.get_doc(
			"CRM Channel Conversation", incoming["conversation"]
		)

	def tearDown(self):
		clear_cached_connection(self.connection_id)
		frappe.db.rollback()
		super().tearDown()

	def test_business_send_saves_one_outgoing_message(self):
		before_messages = frappe.db.count("CRM Channel Message")
		before_leads = frappe.db.count("CRM Lead")
		with (
			patch.object(
				telegram_client,
				"value",
				side_effect=lambda field: {
					"telegram_enabled": True,
					"telegram_bot_username": "test_bot",
				}.get(field),
			),
			patch.object(
				telegram_client.telegram_api,
				"request",
				return_value={"ok": True, "result": {"message_id": 501}},
			) as api_request,
		):
			result = telegram_client.send_text(self.conversation, "Business reply")

		method, payload = api_request.call_args.args
		self.assertEqual(method, "sendMessage")
		self.assertEqual(payload["business_connection_id"], self.connection_id)
		self.assertEqual(payload["chat_id"], self.chat_id)
		self.assertEqual(frappe.db.count("CRM Channel Message"), before_messages + 1)
		self.assertEqual(frappe.db.count("CRM Lead"), before_leads)
		message = frappe.get_doc("CRM Channel Message", result["message"])
		self.assertEqual(message.direction, "Outgoing")
		self.assertEqual(message.external_message_id, "501")

	def test_business_send_requires_linked_recipient(self):
		self.conversation.external_chat_id = f"unlinked-{uuid4().hex}"
		with (
			patch.object(
				telegram_client,
				"value",
				side_effect=lambda field: {
					"telegram_enabled": True,
					"telegram_bot_username": "test_bot",
				}.get(field),
			),
			patch.object(telegram_client.telegram_api, "request") as api_request,
			self.assertRaises(ValidationError) as context,
		):
			telegram_client.send_text(self.conversation, "Blocked reply")

		api_request.assert_not_called()
		self.assertIn("not linked", str(context.exception))
