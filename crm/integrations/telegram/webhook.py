"""Receive Telegram Bot API updates and store them in CRM conversations.

Configure Telegram's webhook with the endpoint below and the same value for
``secret_token`` as the Webhook Secret in CRM Channel Settings. The connector
accepts both regular bot messages and Telegram Business messages.
"""

from __future__ import annotations

import hmac
from datetime import datetime, timezone

import frappe
from frappe import _
from crm.api.omnichannel import _ingest_message
from crm.integrations.channel_settings import value


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive():
	"""Store an incoming Telegram update after validating its secret header."""
	_validate_secret()
	payload = _request_payload()
	message, account_id = _message_from_update(payload)
	if not message:
		return {"ok": True, "ignored": True}

	chat = message.get("chat") or {}
	sender = message.get("from") or {}
	chat_id = str(chat.get("id") or "")
	message_id = str(message.get("message_id") or "")
	if not chat_id or not message_id:
		frappe.throw(_("Telegram update does not contain a chat or message identifier"))

	sender_name = " ".join(filter(None, [sender.get("first_name"), sender.get("last_name")]))
	result = _ingest_message(
		channel="Telegram",
		account_id=account_id,
		external_user_id=str(sender.get("id") or chat_id),
		external_chat_id=chat_id,
		external_message_id=message_id,
		content=message.get("text") or message.get("caption"),
		sender_name=sender_name or sender.get("username"),
		sent_at=datetime.fromtimestamp(int(message["date"]), timezone.utc)
		if message.get("date")
		else None,
		attachment_type=_attachment_type(message),
		raw_payload=payload,
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
		return message, str(message.get("business_connection_id") or "business")
	if message := payload.get("message"):
		return message, str(value("telegram_bot_username") or "bot")
	return None, None


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
