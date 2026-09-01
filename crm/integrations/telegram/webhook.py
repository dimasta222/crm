"""Receive Telegram Bot API updates and store them in CRM conversations.

Configure Telegram's webhook with the endpoint below and the same value for
``secret_token`` as the Webhook Secret in CRM Channel Settings. The connector
accepts both regular bot messages and Telegram Business messages.
"""

from __future__ import annotations

import hmac

import frappe
from frappe import _

from crm.api.omnichannel import _ingest_message
from crm.integrations.channel_settings import value
from crm.integrations.utils import normalize_external_datetime

BUSINESS_CONNECTION_CACHE_PREFIX = "crm:telegram:business_connection"


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive():
	"""Store an incoming Telegram update after validating its secret header."""
	_validate_secret()
	payload = _request_payload()
	if connection := payload.get("business_connection"):
		_remember_business_connection(connection)
		return {"ok": True, "ignored": True}

	message, account_id, direction = _message_from_update(payload)
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
	# Business messages include a connection ID, which identifies the personal
	# Telegram account the message belongs to. Direct bot messages use the bot's
	# configured username as the account identifier.
	if message := payload.get("business_message"):
		account_id = str(message.get("business_connection_id") or "")
		if not account_id:
			return None, None, None
		direction = _business_message_direction(message, account_id)
		if not direction:
			return None, None, None
		return message, account_id, direction
	if message := payload.get("message"):
		return message, str(value("telegram_bot_username") or "bot"), "Incoming"
	return None, None, None


def _remember_business_connection(connection):
	connection_id = str(connection.get("id") or "")
	user_id = str((connection.get("user") or {}).get("id") or "")
	if not connection_id:
		return
	key = _business_connection_cache_key(connection_id)
	if connection.get("is_enabled") is False:
		frappe.cache.delete_value(key)
	elif user_id:
		frappe.cache.set_value(key, user_id)


def _business_message_direction(message, account_id):
	if message.get("sender_business_bot"):
		return "Outgoing"
	business_user_id = frappe.cache.get_value(_business_connection_cache_key(account_id))
	if not business_user_id:
		return None
	sender_id = str((message.get("from") or {}).get("id") or "")
	if not sender_id:
		return None
	return "Outgoing" if sender_id == str(business_user_id) else "Incoming"


def _business_connection_cache_key(connection_id):
	return f"{BUSINESS_CONNECTION_CACHE_PREFIX}:{connection_id}"


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
