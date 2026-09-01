"""Receive Avito Messenger V3 webhook events."""

from __future__ import annotations

import hmac

import frappe
from frappe import _

from crm.api.omnichannel import _ingest_message
from crm.integrations.channel_settings import value
from crm.integrations.utils import normalize_external_datetime


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive():
	"""Store a V3 Messenger event using Avito's stable message and user IDs."""
	_validate_token()
	payload = _request_payload()
	# Avito checks the callback with an empty JSON body during registration.
	if not payload:
		return {"ok": True, "ignored": True}

	event = payload.get("payload") or {}
	if event.get("type") != "message" or not event.get("value"):
		return {"ok": True, "ignored": True}
	message = event["value"]
	message_id = message.get("id")
	chat_id = message.get("chat_id")
	account_id = str(message.get("user_id") or "")
	author_id = str(message.get("author_id") or "")
	if not message_id or not chat_id or not account_id or not author_id:
		frappe.throw(_("Avito event does not contain a message, chat, account, or author identifier"))

	direction = "Outgoing" if author_id == account_id else "Incoming"
	external_user_id = author_id
	if direction == "Outgoing":
		external_user_id = _linked_external_user(account_id, chat_id)
		if not external_user_id:
			return {"ok": True, "ignored": True}

	raw_sent_at = message.get("created")
	sent_at = normalize_external_datetime(raw_sent_at)
	if raw_sent_at in (None, "") or sent_at is None:
		return {"ok": True, "ignored": True, "reason": "invalid_timestamp"}

	content = message.get("content") or {}
	result = _ingest_message(
		channel="Avito",
		account_id=account_id,
		external_user_id=external_user_id,
		external_chat_id=str(chat_id),
		external_message_id=str(message_id),
		content=_message_text(message.get("type"), content),
		sender_name=None,
		sent_at=sent_at,
		attachment_url=_attachment_url(message.get("type"), content),
		attachment_type=_attachment_type(message.get("type")),
		raw_payload=payload,
		direction=direction,
		lead_data={},
	)
	if direction == "Incoming":
		frappe.enqueue(
			"crm.integrations.avito.client.enrich_identity",
			queue="short",
			enqueue_after_commit=True,
			account_id=account_id,
			chat_id=str(chat_id),
			external_user_id=external_user_id,
		)
	return {"ok": True, **result}


def _validate_token():
	expected = value("avito_webhook_token")
	received = frappe.request.args.get("token")
	if not expected or not received or not hmac.compare_digest(str(expected), str(received)):
		frappe.throw(_("Unauthorized Avito webhook"), frappe.PermissionError)


def _request_payload():
	try:
		return frappe.request.get_json(silent=False) or {}
	except Exception:
		frappe.throw(_("Avito webhook body must be valid JSON"))


def _linked_external_user(account_id, chat_id):
	return frappe.db.get_value(
		"CRM External Identity",
		{"channel": "Avito", "account_id": account_id, "external_chat_id": str(chat_id)},
		"external_user_id",
	)


def _message_text(message_type, content):
	if message_type == "text":
		return content.get("text")
	if message_type == "link":
		return content.get("link", {}).get("text") or content.get("link", {}).get("url")
	if message_type == "location":
		return content.get("location", {}).get("text") or content.get("location", {}).get("title")
	if message_type == "item":
		return content.get("item", {}).get("title")
	return None


def _attachment_url(message_type, content):
	if message_type != "image":
		return None
	sizes = (content.get("image") or {}).get("sizes") or {}
	if not sizes:
		return None
	return max(sizes.items(), key=lambda item: _image_area(item[0]))[1]


def _image_area(size):
	try:
		width, height = size.lower().split("x", 1)
		return int(width) * int(height)
	except (TypeError, ValueError):
		return 0


def _attachment_type(message_type):
	return {"image": "Image", "file": "File", "video": "Video", "voice": "Voice"}.get(message_type)
