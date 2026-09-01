from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import get_datetime, get_system_timezone

from crm.integrations.telegram import webhook as telegram_webhook
from crm.integrations.telegram.webhook import _attachment_type, _message_from_update
from crm.integrations.utils import make_message_key, normalize_external_datetime
from crm.tests import CRMTestCase


class TestTelegramWebhook(UnitTestCase):
	def test_business_message_keeps_connection_id_and_direction(self):
		message = {
			"message_id": 1,
			"business_connection_id": "connection-1",
			"from": {"id": 200},
		}
		with patch.object(telegram_webhook.frappe.cache, "get_value", return_value="100"):
			self.assertEqual(
				_message_from_update({"business_message": message}),
				(message, "connection-1", "Incoming"),
			)

	def test_business_bot_message_is_outgoing(self):
		message = {
			"message_id": 1,
			"business_connection_id": "connection-1",
			"sender_business_bot": {"id": 300},
		}
		self.assertEqual(
			_message_from_update({"business_message": message}),
			(message, "connection-1", "Outgoing"),
		)

	def test_unknown_business_sender_is_ignored(self):
		message = {"message_id": 1, "business_connection_id": "connection-1"}
		with patch.object(telegram_webhook.frappe.cache, "get_value", return_value=None):
			self.assertEqual(
				_message_from_update({"business_message": message}),
				(None, None, None),
			)

	def test_business_connection_updates_direction_cache(self):
		connection = {"id": "connection-1", "user": {"id": 100}, "is_enabled": True}
		with patch.object(telegram_webhook.frappe.cache, "set_value") as set_value:
			telegram_webhook._remember_business_connection(connection)
		set_value.assert_called_once_with(
			telegram_webhook._business_connection_cache_key("connection-1"), "100"
		)

	def test_disabled_business_connection_clears_direction_cache(self):
		connection = {"id": "connection-1", "user": {"id": 100}, "is_enabled": False}
		with patch.object(telegram_webhook.frappe.cache, "delete_value") as delete_value:
			telegram_webhook._remember_business_connection(connection)
		delete_value.assert_called_once_with(telegram_webhook._business_connection_cache_key("connection-1"))

	def test_detects_telegram_attachments(self):
		self.assertEqual(_attachment_type({"photo": [{}]}), "Photo")
		self.assertEqual(_attachment_type({"voice": {"file_id": "voice-1"}}), "Voice")
		self.assertIsNone(_attachment_type({"text": "Привет"}))

	def test_message_key_is_stable_and_fits_database_field(self):
		key = make_message_key("Telegram", "account", "chat", "message")
		self.assertEqual(key, make_message_key("Telegram", "account", "chat", "message"))
		self.assertEqual(len(key), 64)
		self.assertLessEqual(len(key), 140)

	def test_aware_datetime_is_converted_to_naive_system_time(self):
		value = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
		expected = value.astimezone(ZoneInfo(get_system_timezone())).replace(tzinfo=None)
		self.assertEqual(normalize_external_datetime(value), expected)
		self.assertIsNone(normalize_external_datetime(value).tzinfo)

	def test_invalid_datetime_returns_none(self):
		self.assertIsNone(normalize_external_datetime("not-a-timestamp"))
		self.assertIsNone(normalize_external_datetime(None))


class TestTelegramWebhookIntegration(CRMTestCase):
	def tearDown(self):
		frappe.db.rollback()
		super().tearDown()

	def test_unix_timestamp_creates_message_without_timezone_suffix(self):
		timestamp = 1788256800
		result = self._receive(self._ordinary_payload(timestamp=timestamp))
		message = frappe.get_doc("CRM Channel Message", result["message"])
		stored = get_datetime(message.sent_at)
		expected = (
			datetime.fromtimestamp(timestamp, timezone.utc)
			.astimezone(ZoneInfo(get_system_timezone()))
			.replace(tzinfo=None)
		)

		self.assertEqual(stored, expected)
		self.assertIsNone(stored.tzinfo)
		self.assertNotIn("+00:00", str(message.sent_at))

	def test_same_message_id_in_different_chats_creates_two_messages(self):
		message_id = 77
		first = self._receive(self._ordinary_payload(chat_id="chat-a", message_id=message_id))
		second = self._receive(self._ordinary_payload(chat_id="chat-b", message_id=message_id))
		first_message = frappe.get_doc("CRM Channel Message", first["message"])
		second_message = frappe.get_doc("CRM Channel Message", second["message"])

		self.assertNotEqual(first_message.name, second_message.name)
		self.assertNotEqual(first_message.message_key, second_message.message_key)
		self.assertNotEqual(first_message.conversation, second_message.conversation)

	def test_repeat_in_same_chat_is_deduplicated(self):
		payload = self._ordinary_payload(chat_id="chat-repeat", message_id=88)
		before = frappe.db.count("CRM Channel Message")
		first = self._receive(payload)
		second = self._receive(payload)

		self.assertEqual(first["message"], second["message"])
		self.assertEqual(frappe.db.count("CRM Channel Message"), before + 1)

	def test_ordinary_incoming_message_creates_expected_documents(self):
		before_leads = frappe.db.count("CRM Lead")
		result = self._receive(self._ordinary_payload())
		message = frappe.get_doc("CRM Channel Message", result["message"])
		conversation = frappe.get_doc("CRM Channel Conversation", result["conversation"])
		identity = frappe.get_doc(
			"CRM External Identity",
			{"channel": "Telegram", "external_user_id": "customer-1"},
		)

		self.assertEqual(message.direction, "Incoming")
		self.assertEqual(message.content, "Привет")
		self.assertEqual(conversation.external_chat_id, "chat-1")
		self.assertEqual(identity.lead, result["lead"])
		self.assertEqual(frappe.db.count("CRM Lead"), before_leads + 1)

	def test_incoming_business_message_is_saved_as_incoming(self):
		connection_id = f"connection-{uuid4().hex}"
		cache_key = telegram_webhook._business_connection_cache_key(connection_id)
		frappe.cache.set_value(cache_key, "business-owner")
		self.addCleanup(frappe.cache.delete_value, cache_key)
		payload = {
			"business_message": {
				"message_id": 41,
				"business_connection_id": connection_id,
				"date": 1788256800,
				"chat": {"id": "business-chat"},
				"from": {"id": "customer-41", "first_name": "Customer"},
				"text": "Новый запрос",
			}
		}
		result = self._receive(payload)
		message = frappe.get_doc("CRM Channel Message", result["message"])

		self.assertEqual(message.direction, "Incoming")
		self.assertTrue(result["lead"])

	def test_outgoing_business_message_does_not_create_lead(self):
		before_leads = frappe.db.count("CRM Lead")
		connection_id = f"connection-{uuid4().hex}"
		cache_key = telegram_webhook._business_connection_cache_key(connection_id)
		frappe.cache.set_value(cache_key, "business-owner")
		self.addCleanup(frappe.cache.delete_value, cache_key)
		incoming = {
			"business_message": {
				"message_id": 42,
				"business_connection_id": connection_id,
				"date": 1788256800,
				"chat": {"id": "business-chat-outgoing"},
				"from": {"id": "customer-42", "first_name": "Customer"},
				"text": "Входящий запрос",
			}
		}
		incoming_result = self._receive(incoming)
		lead_count_after_incoming = frappe.db.count("CRM Lead")
		outgoing = {
			"business_message": {
				"message_id": 43,
				"business_connection_id": connection_id,
				"date": 1788256800,
				"chat": {"id": "business-chat-outgoing"},
				"from": {"id": "business-owner", "first_name": "Owner"},
				"sender_business_bot": {"id": "bot-1"},
				"text": "Исходящий ответ",
			}
		}
		outgoing_result = self._receive(outgoing)
		outgoing_message = frappe.get_doc("CRM Channel Message", outgoing_result["message"])

		self.assertEqual(lead_count_after_incoming, before_leads + 1)
		self.assertEqual(outgoing_result["lead"], incoming_result["lead"])
		self.assertEqual(outgoing_message.direction, "Outgoing")
		self.assertEqual(frappe.db.count("CRM Lead"), lead_count_after_incoming)

	def test_invalid_timestamp_is_ignored_without_creating_records(self):
		before_leads = frappe.db.count("CRM Lead")
		before_messages = frappe.db.count("CRM Channel Message")
		result = self._receive(self._ordinary_payload(timestamp="not-a-timestamp"))

		self.assertTrue(result["ignored"])
		self.assertEqual(result["reason"], "invalid_timestamp")
		self.assertEqual(frappe.db.count("CRM Lead"), before_leads)
		self.assertEqual(frappe.db.count("CRM Channel Message"), before_messages)

	def test_invalid_secret_is_safe_and_creates_no_records(self):
		before = frappe.db.count("CRM Channel Message")
		expected_secret = "expected-webhook-secret"
		received_secret = "wrong-webhook-secret"
		request = SimpleNamespace(headers={"X-Telegram-Bot-Api-Secret-Token": received_secret})
		with (
			patch.object(telegram_webhook, "value", return_value=expected_secret),
			patch.object(telegram_webhook.frappe, "request", request),
			patch.object(telegram_webhook.frappe, "log_error") as log_error,
			self.assertRaises(frappe.PermissionError) as context,
		):
			telegram_webhook._validate_secret()

		error_text = str(context.exception)
		self.assertNotIn(expected_secret, error_text)
		self.assertNotIn(received_secret, error_text)
		log_error.assert_not_called()
		self.assertEqual(frappe.db.count("CRM Channel Message"), before)

	def _receive(self, payload):
		with (
			patch.object(telegram_webhook, "_validate_secret"),
			patch.object(telegram_webhook, "_request_payload", return_value=payload),
			patch.object(telegram_webhook, "value", return_value="test-bot"),
		):
			return telegram_webhook.receive()

	def _ordinary_payload(self, chat_id="chat-1", message_id=1, timestamp=1788256800):
		return {
			"message": {
				"message_id": message_id,
				"date": timestamp,
				"chat": {"id": chat_id},
				"from": {
					"id": "customer-1",
					"first_name": "Иван",
					"username": "ivan_test",
				},
				"text": "Привет",
			}
		}
