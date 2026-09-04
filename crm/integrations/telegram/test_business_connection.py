import traceback
from unittest.mock import Mock, patch
from uuid import uuid4

import frappe
import requests
from frappe.tests import UnitTestCase

from crm.integrations.telegram import api as telegram_api
from crm.integrations.telegram import business_connection
from crm.integrations.telegram.business_connection import (
	BUSINESS_CONNECTION_DOCTYPE,
	PermanentBusinessConnectionError,
	TemporaryBusinessConnectionError,
	clear_cached_connection,
	normalize_business_username,
	resolve_business_connection,
	upsert_business_connection,
)
from crm.tests import CRMTestCase


def concurrent_upsert_worker(connection_id, username):
	"""Exercise the production upsert from an independent bench process."""
	upsert_business_connection(
		{
			"id": connection_id,
			"user": {
				"id": "concurrent-business-user",
				"username": username,
			},
			"user_chat_id": "concurrent-owner-chat",
			"date": 1788256800,
			"is_enabled": True,
			"rights": {
				"can_read_messages": True,
				"can_reply": True,
			},
		},
		source="webhook",
	)
	frappe.db.commit()
	return frappe.db.count(
		BUSINESS_CONNECTION_DOCTYPE, {"connection_id": connection_id}
	)


class TestTelegramAPI(UnitTestCase):
	def test_network_error_does_not_expose_token(self):
		token = "telegram-token-sentinel"
		error = requests.ConnectTimeout(
			f"Connection failed for https://api.telegram.org/bot{token}/getBusinessConnection"
		)
		with (
			patch.object(telegram_api, "value", return_value=token),
			patch.object(telegram_api.requests, "post", side_effect=error),
			self.assertRaises(telegram_api.TelegramTemporaryAPIError) as context,
		):
			telegram_api.request("getBusinessConnection", {"business_connection_id": "test"})

		formatted = "".join(
			traceback.format_exception(
				type(context.exception), context.exception, context.exception.__traceback__
			)
		)
		self.assertNotIn(token, str(context.exception))
		self.assertNotIn(token, formatted)
		self.assertEqual(context.exception.error_type, "network")

	def test_429_and_5xx_are_temporary(self):
		for status_code, error_type in ((429, "telegram_429"), (503, "telegram_5xx")):
			response = Mock(status_code=status_code)
			with (
				patch.object(telegram_api, "value", return_value="test-token"),
				patch.object(telegram_api.requests, "post", return_value=response),
				self.assertRaises(telegram_api.TelegramTemporaryAPIError) as context,
			):
				telegram_api.request("getBusinessConnection", {"business_connection_id": "test"})
			self.assertEqual(context.exception.error_type, error_type)

	def test_get_business_connection_4xx_is_permanent(self):
		response = Mock(status_code=400)
		with (
			patch.object(telegram_api, "value", return_value="test-token"),
			patch.object(telegram_api.requests, "post", return_value=response),
			self.assertRaises(telegram_api.TelegramPermanentAPIError) as context,
		):
			telegram_api.request("getBusinessConnection", {"business_connection_id": "test"})
		self.assertEqual(context.exception.error_type, "unknown_connection")


class TestBusinessUsername(UnitTestCase):
	def test_username_is_trimmed_and_at_sign_removed(self):
		self.assertEqual(normalize_business_username("  @Future_Studio  "), "Future_Studio")

	def test_invalid_username_is_rejected(self):
		self.assertIsNone(normalize_business_username("bad username"))


class TestBusinessConnectionPersistence(CRMTestCase):
	def setUp(self):
		super().setUp()
		self.connection_id = f"connection-{uuid4().hex}"

	def tearDown(self):
		clear_cached_connection(self.connection_id)
		frappe.db.rollback()
		super().tearDown()

	def test_first_connection_and_repeated_event_upsert_one_record(self):
		before = frappe.db.count(BUSINESS_CONNECTION_DOCTYPE)
		first = upsert_business_connection(self._payload(), source="webhook")
		second = upsert_business_connection(
			self._payload(username="FutureStudioUpdated"), source="webhook"
		)

		self.assertEqual(frappe.db.count(BUSINESS_CONNECTION_DOCTYPE), before + 1)
		self.assertEqual(first.connection_id, second.connection_id)
		self.assertEqual(second.business_username, "FutureStudioUpdated")

	def test_rights_disable_and_reenable_are_persisted(self):
		upsert_business_connection(self._payload(can_reply=False), source="webhook")
		doc = self._doc()
		self.assertTrue(doc.can_read_messages)
		self.assertFalse(doc.can_reply)
		self.assertEqual(doc.sync_status, "Read Only")

		upsert_business_connection(self._payload(is_enabled=False), source="webhook")
		doc.reload()
		self.assertFalse(doc.is_enabled)
		self.assertTrue(doc.disabled_at)
		self.assertEqual(doc.sync_status, "Disabled")

		upsert_business_connection(self._payload(is_enabled=True), source="webhook")
		doc.reload()
		self.assertTrue(doc.is_enabled)
		self.assertFalse(doc.disabled_at)
		self.assertEqual(doc.sync_status, "Connected")

	def test_event_without_optional_fields_preserves_known_values(self):
		upsert_business_connection(self._payload(), source="webhook")
		upsert_business_connection({"id": self.connection_id, "is_enabled": True}, source="webhook")
		doc = self._doc()

		self.assertEqual(doc.business_user_id, "business-owner")
		self.assertEqual(doc.business_username, "FutureStudioBusiness")
		self.assertTrue(doc.can_read_messages)
		self.assertTrue(doc.can_reply)

	def test_redis_hit_does_not_query_database(self):
		upsert_business_connection(self._payload(), source="webhook")
		with patch.object(business_connection, "_get_from_db") as get_from_db:
			resolved = resolve_business_connection(self.connection_id)
		get_from_db.assert_not_called()
		self.assertEqual(resolved.business_user_id, "business-owner")

	def test_redis_miss_restores_connection_from_database(self):
		upsert_business_connection(self._payload(), source="webhook")
		clear_cached_connection(self.connection_id)
		with patch.object(telegram_api, "request") as api_request:
			resolved = resolve_business_connection(self.connection_id)
		api_request.assert_not_called()
		self.assertEqual(resolved.connection_id, self.connection_id)
		self.assertIsInstance(
			frappe.cache.get_value(business_connection.cache_key(self.connection_id)), dict
		)

	def test_database_miss_fetches_and_saves_api_result(self):
		with patch.object(
			telegram_api, "request", return_value={"ok": True, "result": self._payload()}
		) as api_request:
			resolved = resolve_business_connection(self.connection_id)

		api_request.assert_called_once_with(
			"getBusinessConnection", {"business_connection_id": self.connection_id}
		)
		self.assertEqual(resolved.connection_id, self.connection_id)
		self.assertTrue(
			frappe.db.exists(BUSINESS_CONNECTION_DOCTYPE, {"connection_id": self.connection_id})
		)

	def test_stale_database_record_is_refreshed_from_api(self):
		upsert_business_connection(self._payload(), source="webhook")
		doc = self._doc()
		frappe.db.set_value(
			BUSINESS_CONNECTION_DOCTYPE,
			doc.name,
			"last_synced_at",
			"2000-01-01 00:00:00",
			update_modified=False,
		)
		clear_cached_connection(self.connection_id)
		with patch.object(
			telegram_api,
			"request",
			return_value={"ok": True, "result": self._payload(can_reply=False)},
		) as api_request:
			resolved = resolve_business_connection(self.connection_id)

		api_request.assert_called_once_with(
			"getBusinessConnection", {"business_connection_id": self.connection_id}
		)
		self.assertFalse(resolved.can_reply)

	def test_temporary_refresh_uses_usable_stale_database_record(self):
		upsert_business_connection(self._payload(), source="webhook")
		doc = self._doc()
		frappe.db.set_value(
			BUSINESS_CONNECTION_DOCTYPE,
			doc.name,
			"last_synced_at",
			"2000-01-01 00:00:00",
			update_modified=False,
		)
		clear_cached_connection(self.connection_id)
		with patch.object(
			telegram_api,
			"request",
			side_effect=telegram_api.TelegramTemporaryAPIError("network"),
		) as api_request:
			resolved = resolve_business_connection(self.connection_id)

		api_request.assert_called_once_with(
			"getBusinessConnection", {"business_connection_id": self.connection_id}
		)
		self.assertEqual(resolved.business_user_id, "business-owner")
		self.assertTrue(resolved.is_enabled)
		self.assertEqual(resolved.sync_status, "Stale/Temporary Error")
		doc.reload()
		self.assertEqual(doc.sync_status, "Stale/Temporary Error")
		self.assertEqual(doc.last_sync_error_type, "network")
		self.assertEqual(str(doc.last_synced_at), "2000-01-01 00:00:00")

	def test_temporary_api_error_is_classified_and_stored(self):
		with (
			patch.object(
				telegram_api,
				"request",
				side_effect=telegram_api.TelegramTemporaryAPIError("network"),
			),
			self.assertRaises(TemporaryBusinessConnectionError),
		):
			resolve_business_connection(self.connection_id)

		doc = self._doc()
		self.assertEqual(doc.sync_status, "Temporary Error")
		self.assertEqual(doc.last_sync_error_type, "network")

	def test_permanent_api_error_is_classified_and_stored(self):
		with (
			patch.object(
				telegram_api,
				"request",
				side_effect=telegram_api.TelegramPermanentAPIError("unknown_connection"),
			),
			self.assertRaises(PermanentBusinessConnectionError),
		):
			resolve_business_connection(self.connection_id)

		doc = self._doc()
		self.assertEqual(doc.sync_status, "Invalid")
		self.assertEqual(doc.last_sync_error_type, "unknown_connection")

	def test_only_business_rights_are_serialized(self):
		payload = self._payload()
		payload["rights"]["unrelated_update_field"] = True
		upsert_business_connection(payload, source="webhook")
		doc = self._doc()
		self.assertNotIn("unrelated_update_field", doc.rights_json)

	def _doc(self):
		name = frappe.db.get_value(
			BUSINESS_CONNECTION_DOCTYPE, {"connection_id": self.connection_id}, "name"
		)
		return frappe.get_doc(BUSINESS_CONNECTION_DOCTYPE, name)

	def _payload(
		self,
		*,
		username="FutureStudioBusiness",
		is_enabled=True,
		can_read=True,
		can_reply=True,
	):
		return {
			"id": self.connection_id,
			"user": {
				"id": "business-owner",
				"username": username,
				"first_name": "Business",
				"last_name": "Owner",
			},
			"user_chat_id": "owner-chat",
			"date": 1788256800,
			"is_enabled": is_enabled,
			"rights": {
				"can_read_messages": can_read,
				"can_reply": can_reply,
				"can_delete_sent_messages": False,
			},
		}
