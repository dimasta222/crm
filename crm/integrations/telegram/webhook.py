"""Receive Telegram Bot API updates and store them in CRM conversations.

Configure Telegram's webhook with the endpoint below and the same value for
``secret_token`` as the Webhook Secret in CRM Channel Settings. The connector
accepts both regular bot messages and Telegram Business messages.
"""

from __future__ import annotations

import hmac
import pickle

import frappe
from frappe import _
from redis.exceptions import RedisError

from crm.api.omnichannel import _ingest_message
from crm.integrations.channel_settings import value
from crm.integrations.telegram import api as telegram_api
from crm.integrations.telegram.business_connection import (
	PermanentBusinessConnectionError,
	TemporaryBusinessConnectionError,
	is_readable,
	mark_connection_review,
	resolve_business_connection,
	upsert_business_connection,
)
from crm.integrations.telegram.client import send_bot_redirect
from crm.integrations.utils import make_message_key, normalize_external_datetime

REDIRECT_CACHE_PREFIX = "crm:telegram:bot_redirect"
REDIRECT_PROCESSING_TTL = 60
REDIRECT_DONE_TTL = 7 * 24 * 60 * 60


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive():
	"""Store an incoming Telegram update after validating its secret header."""
	_validate_secret()
	payload = _request_payload()
	if connection := payload.get("business_connection"):
		try:
			upsert_business_connection(connection, source="webhook")
		except PermanentBusinessConnectionError as error:
			return {"ok": True, "ignored": True, "reason": error.error_type}
		return {"ok": True, "business_connection_saved": True}

	if message := payload.get("message"):
		return _handle_technical_bot_message(message)

	account_id = str(((payload.get("business_message") or {}).get("business_connection_id")) or "")
	try:
		message, account_id, direction = _message_from_update(payload)
	except TemporaryBusinessConnectionError as error:
		return _retry_response(error.error_type)
	except PermanentBusinessConnectionError as error:
		if account_id and error.error_type == "unknown_direction":
			mark_connection_review(account_id, error.error_type)
			return _retry_response(error.error_type)
		if account_id and error.error_type == "insufficient_read_rights":
			mark_connection_review(account_id, error.error_type)
		return {"ok": True, "ignored": True, "reason": error.error_type}
	if not message:
		return {"ok": True, "ignored": True}

	chat = message.get("chat") or {}
	sender = message.get("from") or {}
	chat_id = str(chat.get("id") or "")
	message_id = str(message.get("message_id") or "")
	if not chat_id or not message_id:
		frappe.throw(_("Telegram update does not contain a chat or message identifier"))

	external_user_id = str(sender.get("id") or chat_id)
	if direction == "Outgoing":
		external_user_id = _linked_external_user(account_id, chat_id)
		if not external_user_id:
			return {"ok": True, "ignored": True}

	raw_sent_at = message.get("date")
	sent_at = normalize_external_datetime(raw_sent_at)
	if raw_sent_at in (None, "") or sent_at is None:
		return {"ok": True, "ignored": True, "reason": "invalid_timestamp"}

	sender_name = " ".join(filter(None, [sender.get("first_name"), sender.get("last_name")]))
	result = _ingest_message(
		channel="Telegram",
		account_id=account_id,
		external_user_id=external_user_id,
		external_chat_id=chat_id,
		external_message_id=message_id,
		content=message.get("text") or message.get("caption"),
		sender_name=sender_name or sender.get("username"),
		sent_at=sent_at,
		attachment_type=_attachment_type(message),
		raw_payload=payload,
		direction=direction,
		lead_data={"username": sender.get("username")},
	)
	return {"ok": True, **result}


def _validate_secret():
	expected = value("telegram_webhook_secret")
	received = frappe.request.headers.get("X-Telegram-Bot-Api-Secret-Token")
	if not expected or not received or not hmac.compare_digest(str(expected), str(received)):
		frappe.throw(_("Unauthorized Telegram webhook"), frappe.PermissionError)


def _request_payload():
	try:
		return frappe.request.get_json(silent=False) or {}
	except Exception:
		frappe.throw(_("Telegram webhook body must be valid JSON"))


def _message_from_update(payload):
	if message := payload.get("business_message"):
		account_id = str(message.get("business_connection_id") or "")
		if not account_id:
			return None, None, None
		direction = _business_message_direction(message, account_id)
		if not direction:
			return None, None, None
		return message, account_id, direction
	return None, None, None


def _remember_business_connection(connection):
	"""Compatibility wrapper retained for callers and older tests."""
	return upsert_business_connection(connection, source="webhook")


def _business_message_direction(message, account_id):
	if message.get("sender_business_bot"):
		return "Outgoing"
	if stored_direction := _stored_message_direction(message, account_id):
		return stored_direction
	connection = resolve_business_connection(account_id)
	business_user_id = str(connection.get("business_user_id") or "")
	if not connection.get("is_enabled"):
		raise PermanentBusinessConnectionError("connection_disabled")
	if not is_readable(connection):
		raise PermanentBusinessConnectionError("insufficient_read_rights")
	if not business_user_id:
		raise PermanentBusinessConnectionError("unknown_direction")
	sender_id = str((message.get("from") or {}).get("id") or "")
	if not sender_id:
		raise PermanentBusinessConnectionError("unknown_direction")
	return "Outgoing" if sender_id == business_user_id else "Incoming"


def _stored_message_direction(message, account_id):
	chat_id = str((message.get("chat") or {}).get("id") or "")
	message_id = str(message.get("message_id") or "")
	if not chat_id or not message_id:
		return None
	return frappe.db.get_value(
		"CRM Channel Message",
		{"message_key": make_message_key("Telegram", account_id, chat_id, message_id)},
		"direction",
	)


def _handle_technical_bot_message(message):
	chat = message.get("chat") or {}
	if chat.get("type") not in (None, "private"):
		return {"ok": True, "ignored": True, "reason": "non_private_bot_message"}
	chat_id = str(chat.get("id") or "")
	message_id = str(message.get("message_id") or "")
	if not chat_id or not message_id:
		return {"ok": True, "ignored": True, "reason": "invalid_bot_message"}

	redirect_key = make_message_key(
		"Telegram Redirect",
		str(value("telegram_bot_username") or "bot"),
		chat_id,
		message_id,
	)
	claim = _claim_redirect(redirect_key)
	if claim == "done":
		return {"ok": True, "ignored": True, "reason": "duplicate_redirect"}
	if claim != "claimed":
		return _retry_response("redirect_in_progress")

	try:
		_result, has_button = send_bot_redirect(chat_id, message_id)
	except telegram_api.TelegramTemporaryAPIError as error:
		_release_redirect(redirect_key)
		return _retry_response(error.error_type)
	except telegram_api.TelegramPermanentAPIError as error:
		_release_redirect(redirect_key)
		_set_business_diagnostic("Technical bot redirect failed")
		return {"ok": True, "ignored": True, "reason": error.error_type}

	_finish_redirect(redirect_key)
	if not has_button:
		_set_business_diagnostic("Business username missing")
	return {"ok": True, "redirected": True, "has_button": has_button}


def _claim_redirect(redirect_key):
	done_key = _redirect_done_cache_key(redirect_key)
	if frappe.cache.get_value(done_key, expires=True) == "done":
		return "done"
	try:
		claimed = frappe.cache.set(
			frappe.cache.make_key(_redirect_lock_cache_key(redirect_key)),
			pickle.dumps("processing"),
			nx=True,
			ex=REDIRECT_PROCESSING_TTL,
		)
	except RedisError:
		return "unavailable"
	return "claimed" if claimed else "processing"


def _finish_redirect(redirect_key):
	frappe.cache.set_value(
		_redirect_done_cache_key(redirect_key), "done", expires_in_sec=REDIRECT_DONE_TTL
	)
	frappe.cache.delete_value(_redirect_lock_cache_key(redirect_key))


def _release_redirect(redirect_key):
	frappe.cache.delete_value(_redirect_lock_cache_key(redirect_key))


def _redirect_done_cache_key(redirect_key):
	return f"{REDIRECT_CACHE_PREFIX}:{redirect_key}"


def _redirect_lock_cache_key(redirect_key):
	return f"{REDIRECT_CACHE_PREFIX}:lock:{redirect_key}"


def _retry_response(reason):
	frappe.local.response["http_status_code"] = 503
	return {"ok": False, "retry": True, "reason": reason}


def _set_business_diagnostic(status):
	current = frappe.db.get_single_value("CRM Channel Settings", "telegram_business_status")
	if current != status:
		frappe.db.set_single_value("CRM Channel Settings", "telegram_business_status", status)


def _linked_external_user(account_id, chat_id):
	return frappe.db.get_value(
		"CRM External Identity",
		{"channel": "Telegram", "account_id": account_id, "external_chat_id": str(chat_id)},
		"external_user_id",
	)


def _attachment_type(message):
	for key, label in (
		("photo", "Photo"),
		("document", "Document"),
		("video", "Video"),
		("voice", "Voice"),
		("audio", "Audio"),
	):
		if message.get(key):
			return label
	return None
