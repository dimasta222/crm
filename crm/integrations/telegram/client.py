"""Outgoing Telegram Bot API client."""

import frappe
import requests
from frappe import _

from crm.api.omnichannel import _ingest_message
from crm.integrations.channel_settings import value


def subscribe_webhook(url, secret):
	token = value("telegram_bot_token")
	if not token:
		frappe.throw(_("Telegram bot token is not configured"))
	try:
		response = requests.post(
			f"https://api.telegram.org/bot{token}/setWebhook",
			json={
				"url": url,
				"secret_token": secret,
				"allowed_updates": ["message", "business_connection", "business_message"],
			},
			timeout=20,
		)
		response.raise_for_status()
		result = response.json()
	except (requests.RequestException, ValueError) as error:
		frappe.log_error(title="Telegram webhook setup failed", message=str(error))
		frappe.throw(_("Could not configure the Telegram webhook"))
	if not result.get("ok"):
		frappe.throw(result.get("description") or _("Could not configure the Telegram webhook"))
	return result


def send_text(conversation, content):
	if not value("telegram_enabled"):
		frappe.throw(_("Telegram integration is disabled"))
	token = value("telegram_bot_token")
	if not token:
		frappe.throw(_("Telegram bot token is not configured"))

	payload = {"chat_id": conversation.external_chat_id, "text": content}
	bot_username = str(value("telegram_bot_username") or "").lstrip("@")
	if conversation.account_id and conversation.account_id not in {"bot", bot_username}:
		payload["business_connection_id"] = conversation.account_id

	try:
		response = requests.post(
			f"https://api.telegram.org/bot{token}/sendMessage",
			json=payload,
			timeout=20,
		)
		response.raise_for_status()
		result = response.json()
	except (requests.RequestException, ValueError) as error:
		frappe.log_error(title="Telegram message delivery failed", message=str(error))
		frappe.throw(_("Telegram did not accept the message"))
	if not result.get("ok"):
		frappe.throw(result.get("description") or _("Telegram did not accept the message"))

	telegram_message = result.get("result") or {}
	identity = frappe.db.get_value(
		"CRM External Identity",
		{
			"channel": "Telegram",
			"account_id": conversation.account_id,
			"external_chat_id": conversation.external_chat_id,
		},
		["external_user_id", "username"],
		as_dict=True,
	)
	if not identity:
		frappe.throw(_("Telegram identity is not linked to this conversation"))

	return _ingest_message(
		channel="Telegram",
		account_id=conversation.account_id,
		external_user_id=identity.external_user_id,
		external_chat_id=conversation.external_chat_id,
		external_message_id=str(telegram_message.get("message_id")),
		content=content,
		sender_name=frappe.utils.get_fullname(frappe.session.user),
		raw_payload=result,
		direction="Outgoing",
		lead_data={"username": identity.username},
	)
