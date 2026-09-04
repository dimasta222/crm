from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import get_datetime, get_system_timezone

from crm.api.omnichannel import _ingest_message
from crm.integrations.telegram import webhook as telegram_webhook
from crm.integrations.telegram.business_connection import (
	BUSINESS_CONNECTION_DOCTYPE,
	PermanentBusinessConnectionError,
	TemporaryBusinessConnectionError,
	clear_cached_connection,
	upsert_business_connection,
)
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
		connection = frappe._dict(
			connection_id="connection-1",
			business_user_id="100",
			is_enabled=True,
			can_read_messages=True,
		)
		with patch.object(
			telegram_webhook, "resolve_business_connection", return_value=connection
		):
			self.assertEqual(
				_message_from_update({"business_message": message}),
				(message, "connection-1", "Incoming"),
			)

	def test_business_user_message_is_outgoing(self):
		message = {
			"message_id": 1,
			"business_connection_id": "connection-1",
			"from": {"id": "business-owner"},
		}
		connection = frappe._dict(
			connection_id="connection-1",
			business_user_id="business-owner",
			is_enabled=True,
			can_read_messages=True,
		)
		with patch.object(
			telegram_webhook, "resolve_business_connection", return_value=connection
		):
			self.assertEqual(
				_message_from_update({"business_message": message})[2], "Outgoing"
			)

	def test_business_bot_message_is_outgoing_without_resolver(self):
		message = {
			"message_id": 1,
			"business_connection_id": "connection-1",
			"sender_business_bot": {"id": 300},
		}
		with patch.object(telegram_webhook, "resolve_business_connection") as resolver:
			self.assertEqual(
				_message_from_update({"business_message": message}),
				(message, "connection-1", "Outgoing"),
			)
		resolver.assert_not_called()

	def test_saved_crm_message_id_is_outgoing(self):
		message = {"message_id": 2, "business_connection_id": "connection-1"}
		with (
			patch.object(telegram_webhook, "_stored_message_direction", return_value="Outgoing"),
			patch.object(telegram_webhook, "resolve_business_connection") as resolver,
		):
			self.assertEqual(
				_message_from_update({"business_message": message})[2], "Outgoing"
			)
		resolver.assert_not_called()

	def test_unknown_business_sender_is_marked_for_review(self):
		message = {"message_id": 1, "business_connection_id": "connection-1"}
		connection = frappe._dict(
			connection_id="connection-1",
			business_user_id="100",
			is_enabled=True,
			can_read_messages=True,
		)
		with (
			patch.object(telegram_webhook, "resolve_business_connection", return_value=connection),
			self.assertRaises(PermanentBusinessConnectionError) as context,
		):
			_message_from_update({"business_message": message})
		self.assertEqual(context.exception.error_type, "unknown_direction")

	def test_business_connection_event_uses_durable_upsert(self):
		connection = {"id": "connection-1", "user": {"id": 100}, "is_enabled": True}
		with patch.object(telegram_webhook, "upsert_business_connection") as upsert:
			telegram_webhook._remember_business_connection(connection)
		upsert.assert_called_once_with(connection, source="webhook")

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
	def setUp(self):
		super().setUp()
		self.connection_ids = []

	def tearDown(self):
		for connection_id in self.connection_ids:
			clear_cached_connection(connection_id)
		frappe.local.response.pop("http_status_code", None)
		frappe.db.rollback()
		super().tearDown()

	def test_business_connection_event_creates_no_customer_records(self):
		connection_id = f"connection-{uuid4().hex}"
		self.connection_ids.append(connection_id)
		doctypes = (
			"CRM Lead",
			"CRM External Identity",
			"CRM Channel Conversation",
			"CRM Channel Message",
		)
		before = {doctype: frappe.db.count(doctype) for doctype in doctypes}
		result = self._receive(
			{"business_connection": self._connection_payload(connection_id)}
		)

		self.assertTrue(result["business_connection_saved"])
		self.assertTrue(
			frappe.db.exists(BUSINESS_CONNECTION_DOCTYPE, {"connection_id": connection_id})
		)
		self.assertEqual({doctype: frappe.db.count(doctype) for doctype in doctypes}, before)

	def test_unix_timestamp_creates_message_without_timezone_suffix(self):
		timestamp = 1788256800
		connection_id = self._connect()
		result = self._receive(self._business_payload(connection_id, timestamp=timestamp))
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
		connection_id = self._connect()
		first = self._receive(
			self._business_payload(connection_id, chat_id="chat-a", message_id=77)
		)
		second = self._receive(
			self._business_payload(connection_id, chat_id="chat-b", message_id=77)
		)
		first_message = frappe.get_doc("CRM Channel Message", first["message"])
		second_message = frappe.get_doc("CRM Channel Message", second["message"])

		self.assertNotEqual(first_message.name, second_message.name)
		self.assertNotEqual(first_message.message_key, second_message.message_key)
		self.assertNotEqual(first_message.conversation, second_message.conversation)

	def test_repeat_in_same_chat_is_deduplicated(self):
		connection_id = self._connect()
		payload = self._business_payload(
			connection_id, chat_id="chat-repeat", message_id=88
		)
		before = frappe.db.count("CRM Channel Message")
		first = self._receive(payload)
		second = self._receive(payload)

		self.assertEqual(first["message"], second["message"])
		self.assertEqual(frappe.db.count("CRM Channel Message"), before + 1)

	def test_technical_bot_message_redirects_without_creating_crm_records(self):
		doctypes = (
			"CRM Lead",
			"CRM External Identity",
			"CRM Channel Conversation",
			"CRM Channel Message",
		)
		before = {doctype: frappe.db.count(doctype) for doctype in doctypes}
		with (
			patch.object(telegram_webhook, "_claim_redirect", return_value="claimed"),
			patch.object(telegram_webhook, "_finish_redirect"),
			patch.object(
				telegram_webhook,
				"send_bot_redirect",
				return_value=({"ok": True, "result": {"message_id": 100}}, True),
			) as redirect,
		):
			result = self._receive(self._ordinary_payload())

		self.assertTrue(result["redirected"])
		redirect.assert_called_once_with("chat-1", "1")
		self.assertEqual({doctype: frappe.db.count(doctype) for doctype in doctypes}, before)

	def test_repeated_bot_webhook_sends_only_one_redirect(self):
		payload = self._ordinary_payload(chat_id=f"chat-{uuid4().hex}", message_id=91)
		chat_id = str(payload["message"]["chat"]["id"])
		redirect_key = make_message_key("Telegram Redirect", "test-bot", chat_id, "91")
		cache_key = f"{telegram_webhook.REDIRECT_CACHE_PREFIX}:{redirect_key}"
		self.addCleanup(frappe.cache.delete_value, cache_key)
		with patch.object(
			telegram_webhook,
			"send_bot_redirect",
			return_value=({"ok": True, "result": {"message_id": 100}}, True),
		) as redirect:
			first = self._receive(payload)
			second = self._receive(payload)

		self.assertTrue(first["redirected"])
		self.assertEqual(second["reason"], "duplicate_redirect")
		redirect.assert_called_once()

	def test_new_bot_message_from_same_chat_gets_new_redirect(self):
		chat_id = f"chat-{uuid4().hex}"
		payloads = (
			self._ordinary_payload(chat_id=chat_id, message_id=101),
			self._ordinary_payload(chat_id=chat_id, message_id=102),
		)
		cache_keys = []
		for message_id in ("101", "102"):
			redirect_key = make_message_key(
				"Telegram Redirect", "test-bot", chat_id, message_id
			)
			cache_keys.extend(
				(
					telegram_webhook._redirect_done_cache_key(redirect_key),
					telegram_webhook._redirect_lock_cache_key(redirect_key),
				)
			)
		for cache_key in cache_keys:
			self.addCleanup(frappe.cache.delete_value, cache_key)

		with patch.object(
			telegram_webhook,
			"send_bot_redirect",
			return_value=({"ok": True, "result": {"message_id": 100}}, True),
		) as redirect:
			first = self._receive(payloads[0])
			second = self._receive(payloads[1])

		self.assertTrue(first["redirected"])
		self.assertTrue(second["redirected"])
		self.assertEqual(redirect.call_count, 2)

	def test_redirect_done_marker_is_written_only_after_success(self):
		payload = self._ordinary_payload(chat_id=f"chat-{uuid4().hex}", message_id=103)
		chat_id = str(payload["message"]["chat"]["id"])
		redirect_key = make_message_key("Telegram Redirect", "test-bot", chat_id, "103")
		done_key = telegram_webhook._redirect_done_cache_key(redirect_key)
		lock_key = telegram_webhook._redirect_lock_cache_key(redirect_key)
		self.addCleanup(frappe.cache.delete_value, done_key)
		self.addCleanup(frappe.cache.delete_value, lock_key)
		with patch.object(
			telegram_webhook,
			"send_bot_redirect",
			side_effect=(
				telegram_webhook.telegram_api.TelegramTemporaryAPIError("network"),
				({"ok": True, "result": {"message_id": 100}}, True),
			),
		) as redirect:
			first = self._receive(payload)
			self.assertTrue(first["retry"])
			self.assertIsNone(frappe.cache.get_value(done_key))
			self.assertIsNone(frappe.cache.get_value(lock_key))
			frappe.local.response.pop("http_status_code", None)
			second = self._receive(payload)

		self.assertTrue(second["redirected"])
		self.assertEqual(redirect.call_count, 2)
		self.assertEqual(frappe.cache.get_value(done_key), "done")
		self.assertIsNone(frappe.cache.get_value(lock_key))

	def test_redirect_redis_eviction_does_not_change_crm_data(self):
		payload = self._ordinary_payload(chat_id=f"chat-{uuid4().hex}", message_id=104)
		chat_id = str(payload["message"]["chat"]["id"])
		redirect_key = make_message_key("Telegram Redirect", "test-bot", chat_id, "104")
		done_key = telegram_webhook._redirect_done_cache_key(redirect_key)
		lock_key = telegram_webhook._redirect_lock_cache_key(redirect_key)
		self.addCleanup(frappe.cache.delete_value, done_key)
		self.addCleanup(frappe.cache.delete_value, lock_key)
		doctypes = (
			"CRM Lead",
			"CRM External Identity",
			"CRM Channel Conversation",
			"CRM Channel Message",
		)
		before = {doctype: frappe.db.count(doctype) for doctype in doctypes}
		with patch.object(
			telegram_webhook,
			"send_bot_redirect",
			return_value=({"ok": True, "result": {"message_id": 100}}, True),
		):
			result = self._receive(payload)
		self.assertTrue(result["redirected"])
		frappe.cache.delete_value(done_key)
		self.assertEqual({doctype: frappe.db.count(doctype) for doctype in doctypes}, before)

	def test_missing_business_username_sets_one_safe_diagnostic(self):
		payload = self._ordinary_payload(chat_id=f"chat-{uuid4().hex}", message_id=92)
		chat_id = str(payload["message"]["chat"]["id"])
		redirect_key = make_message_key(
			"Telegram Redirect", "test-bot", chat_id, "92"
		)
		cache_key = f"{telegram_webhook.REDIRECT_CACHE_PREFIX}:{redirect_key}"
		self.addCleanup(frappe.cache.delete_value, cache_key)
		with (
			patch.object(
				telegram_webhook,
				"send_bot_redirect",
				return_value=({"ok": True, "result": {"message_id": 100}}, False),
			),
			patch.object(telegram_webhook, "_set_business_diagnostic") as diagnostic,
		):
			first = self._receive(payload)
			second = self._receive(payload)

		self.assertTrue(first["redirected"])
		self.assertFalse(first["has_button"])
		self.assertEqual(second["reason"], "duplicate_redirect")
		diagnostic.assert_called_once_with("Business username missing")

	def test_incoming_business_message_is_saved_as_incoming(self):
		connection_id = self._connect()
		result = self._receive(self._business_payload(connection_id, message_id=41))
		message = frappe.get_doc("CRM Channel Message", result["message"])

		self.assertEqual(message.direction, "Incoming")
		self.assertTrue(result["lead"])

	def test_outgoing_business_message_does_not_create_lead(self):
		before_leads = frappe.db.count("CRM Lead")
		connection_id = self._connect()
		incoming = self._business_payload(
			connection_id, chat_id="business-chat-outgoing", message_id=42
		)
		incoming_result = self._receive(incoming)
		lead_count_after_incoming = frappe.db.count("CRM Lead")
		outgoing = self._business_payload(
			connection_id,
			chat_id="business-chat-outgoing",
			message_id=43,
			sender_id="business-owner",
			sender_business_bot=True,
		)
		outgoing_result = self._receive(outgoing)
		outgoing_message = frappe.get_doc("CRM Channel Message", outgoing_result["message"])

		self.assertEqual(lead_count_after_incoming, before_leads + 1)
		self.assertEqual(outgoing_result["lead"], incoming_result["lead"])
		self.assertEqual(outgoing_message.direction, "Outgoing")
		self.assertEqual(frappe.db.count("CRM Lead"), lead_count_after_incoming)

	def test_saved_crm_reply_is_not_duplicated_by_webhook(self):
		connection_id = self._connect()
		incoming_result = self._receive(
			self._business_payload(connection_id, chat_id="crm-reply-chat", message_id=50)
		)
		identity = frappe.get_doc(
			"CRM External Identity",
			{"channel": "Telegram", "external_user_id": "customer-1"},
		)
		_ingest_message(
			channel="Telegram",
			account_id=connection_id,
			external_user_id=identity.external_user_id,
			external_chat_id="crm-reply-chat",
			external_message_id="51",
			content="CRM reply",
			direction="Outgoing",
		)
		before = frappe.db.count("CRM Channel Message")
		result = self._receive(
			self._business_payload(
				connection_id,
				chat_id="crm-reply-chat",
				message_id=51,
				sender_id="business-owner",
			)
		)

		self.assertEqual(result["lead"], incoming_result["lead"])
		self.assertEqual(frappe.db.count("CRM Channel Message"), before)
		message = frappe.get_doc("CRM Channel Message", result["message"])
		self.assertEqual(message.direction, "Outgoing")

	def test_invalid_timestamp_is_ignored_without_creating_records(self):
		connection_id = self._connect()
		before_leads = frappe.db.count("CRM Lead")
		before_messages = frappe.db.count("CRM Channel Message")
		result = self._receive(
			self._business_payload(connection_id, timestamp="not-a-timestamp")
		)

		self.assertTrue(result["ignored"])
		self.assertEqual(result["reason"], "invalid_timestamp")
		self.assertEqual(frappe.db.count("CRM Lead"), before_leads)
		self.assertEqual(frappe.db.count("CRM Channel Message"), before_messages)

	def test_insufficient_read_rights_creates_no_lead(self):
		connection_id = self._connect(can_read=False)
		before = frappe.db.count("CRM Lead")
		result = self._receive(self._business_payload(connection_id))

		self.assertTrue(result["ignored"])
		self.assertEqual(result["reason"], "insufficient_read_rights")
		self.assertEqual(frappe.db.count("CRM Lead"), before)

	def test_disabled_connection_creates_no_lead(self):
		connection_id = self._connect(is_enabled=False)
		before = frappe.db.count("CRM Lead")
		result = self._receive(self._business_payload(connection_id))

		self.assertTrue(result["ignored"])
		self.assertEqual(result["reason"], "connection_disabled")
		self.assertEqual(frappe.db.count("CRM Lead"), before)

	def test_temporary_resolver_error_returns_503_without_creating_lead(self):
		connection_id = f"connection-{uuid4().hex}"
		before = frappe.db.count("CRM Lead")
		with patch.object(
			telegram_webhook,
			"resolve_business_connection",
			side_effect=TemporaryBusinessConnectionError("network"),
		):
			result = self._receive(self._business_payload(connection_id))

		self.assertTrue(result["retry"])
		self.assertEqual(result["reason"], "network")
		self.assertEqual(frappe.local.response["http_status_code"], 503)
		self.assertEqual(frappe.db.count("CRM Lead"), before)

	def test_unknown_direction_retries_without_creating_customer_records(self):
		connection_id = self._connect()
		doctypes = (
			"CRM Lead",
			"CRM External Identity",
			"CRM Channel Conversation",
			"CRM Channel Message",
		)
		before = {doctype: frappe.db.count(doctype) for doctype in doctypes}
		payload = self._business_payload(connection_id)
		payload["business_message"].pop("from")
		result = self._receive(payload)

		self.assertTrue(result["retry"])
		self.assertEqual(result["reason"], "unknown_direction")
		self.assertEqual(frappe.local.response["http_status_code"], 503)
		self.assertEqual({doctype: frappe.db.count(doctype) for doctype in doctypes}, before)
		doc = frappe.get_doc(
			BUSINESS_CONNECTION_DOCTYPE, {"connection_id": connection_id}
		)
		self.assertEqual(doc.sync_status, "Needs Review")

	def test_unknown_direction_recovers_after_connection_refresh(self):
		connection_id = f"connection-{uuid4().hex}"
		self.connection_ids.append(connection_id)
		upsert_business_connection(
			{
				"id": connection_id,
				"is_enabled": True,
				"rights": {"can_read_messages": True, "can_reply": True},
			},
			source="webhook",
		)
		payload = self._business_payload(connection_id, message_id=105)
		before_messages = frappe.db.count("CRM Channel Message")
		before_leads = frappe.db.count("CRM Lead")

		first = self._receive(payload)
		self.assertTrue(first["retry"])
		self.assertEqual(first["reason"], "unknown_direction")
		self.assertEqual(frappe.db.count("CRM Channel Message"), before_messages)
		self.assertEqual(frappe.db.count("CRM Lead"), before_leads)

		upsert_business_connection(
			self._connection_payload(connection_id), source="webhook"
		)
		frappe.local.response.pop("http_status_code", None)
		second = self._receive(payload)
		message = frappe.get_doc("CRM Channel Message", second["message"])
		self.assertEqual(message.direction, "Incoming")
		self.assertEqual(frappe.db.count("CRM Channel Message"), before_messages + 1)
		self.assertEqual(frappe.db.count("CRM Lead"), before_leads + 1)

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

	def _connect(self, *, can_read=True, can_reply=True, is_enabled=True):
		connection_id = f"connection-{uuid4().hex}"
		self.connection_ids.append(connection_id)
		upsert_business_connection(
			self._connection_payload(
				connection_id,
				can_read=can_read,
				can_reply=can_reply,
				is_enabled=is_enabled,
			),
			source="webhook",
		)
		return connection_id

	def _connection_payload(
		self,
		connection_id,
		*,
		can_read=True,
		can_reply=True,
		is_enabled=True,
	):
		return {
			"id": connection_id,
			"user": {"id": "business-owner", "username": "FutureStudioBusiness"},
			"user_chat_id": "owner-chat",
			"date": 1788256800,
			"is_enabled": is_enabled,
			"rights": {
				"can_read_messages": can_read,
				"can_reply": can_reply,
			},
		}

	def _business_payload(
		self,
		connection_id,
		*,
		chat_id="business-chat",
		message_id=1,
		timestamp=1788256800,
		sender_id="customer-1",
		sender_business_bot=False,
	):
		message = {
			"message_id": message_id,
			"business_connection_id": connection_id,
			"date": timestamp,
			"chat": {"id": chat_id},
			"from": {"id": sender_id, "first_name": "Customer"},
			"text": "Новый запрос",
		}
		if sender_business_bot:
			message["sender_business_bot"] = {"id": "bot-1"}
		return {"business_message": message}

	def _ordinary_payload(self, chat_id="chat-1", message_id=1, timestamp=1788256800):
		return {
			"message": {
				"message_id": message_id,
				"date": timestamp,
				"chat": {"id": chat_id, "type": "private"},
				"from": {
					"id": "customer-1",
					"first_name": "Test Customer",
					"username": "customer_test",
				},
				"text": "Привет",
			}
		}
