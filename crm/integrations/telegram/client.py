"""Outgoing Telegram Bot API client."""

import frappe
from frappe import _
from frappe.exceptions import ValidationError

from crm.api.omnichannel import _ingest_message
from crm.integrations.channel_settings import value
from crm.integrations.telegram import api as telegram_api
from crm.integrations.telegram.business_connection import (
	PermanentBusinessConnectionError,
	TemporaryBusinessConnectionError,
	is_replyable,
	normalize_business_username,
	resolve_business_connection,
)

REDIRECT_TEXT = _(
	"Здравствуйте! Для связи с Future Studio перейдите в наш основной Telegram-чат."
)
REDIRECT_TEXT_WITHOUT_LINK = _(
	"Здравствуйте! Основной Telegram-чат Future Studio временно недоступен. "
	"Пожалуйста, используйте контакты на сайте."
)


def subscribe_webhook(url, secret):
	try:
		return telegram_api.request(
			"setWebhook",
			{
				"url": url,
				"secret_token": secret,
				"allowed_updates": ["message", "business_connection", "business_message"],
			},
		)
	except (telegram_api.TelegramTemporaryAPIError, telegram_api.TelegramPermanentAPIError):
		raise ValidationError(_("Could not configure the Telegram webhook")) from None


def send_text(conversation, content):
	if not value("telegram_enabled"):
		frappe.throw(_("Telegram integration is disabled"))

	payload = {"chat_id": conversation.external_chat_id, "text": content}
	bot_username = str(value("telegram_bot_username") or "").lstrip("@")
	if conversation.account_id and conversation.account_id not in {"bot", bot_username}:
		connection = _business_connection_for_reply(conversation)
		payload["business_connection_id"] = connection["connection_id"]

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

	try:
		result = telegram_api.request("sendMessage", payload)
	except (telegram_api.TelegramTemporaryAPIError, telegram_api.TelegramPermanentAPIError):
		raise ValidationError(_("Telegram did not accept the message")) from None

	telegram_message = result.get("result") or {}
	external_message_id = str(telegram_message.get("message_id") or "")
	if not external_message_id:
		raise ValidationError(_("Telegram did not return a message identifier"))

	return _ingest_message(
		channel="Telegram",
		account_id=conversation.account_id,
		external_user_id=identity.external_user_id,
		external_chat_id=conversation.external_chat_id,
		external_message_id=external_message_id,
		content=content,
		sender_name=frappe.utils.get_fullname(frappe.session.user),
		raw_payload=result,
		direction="Outgoing",
		lead_data={"username": identity.username},
	)


def send_bot_redirect(chat_id, reply_to_message_id=None):
	"""Reply to a direct bot message without creating CRM customer records."""
	username = normalize_business_username(value("telegram_business_username"))
	payload = {
		"chat_id": chat_id,
		"text": REDIRECT_TEXT if username else REDIRECT_TEXT_WITHOUT_LINK,
	}
	if reply_to_message_id:
		payload["reply_parameters"] = {"message_id": reply_to_message_id}
	if username:
		payload["reply_markup"] = {
			"inline_keyboard": [
				[
					{
						"text": _("Написать Future Studio"),
						"url": f"https://t.me/{username}",
					}
				]
			]
		}
	return telegram_api.request("sendMessage", payload), bool(username)


def _business_connection_for_reply(conversation):
	try:
		connection = resolve_business_connection(conversation.account_id)
	except (TemporaryBusinessConnectionError, PermanentBusinessConnectionError):
		raise ValidationError(_("Telegram Business connection is unavailable")) from None
	if not connection.get("is_enabled"):
		raise ValidationError(_("Telegram Business connection is disabled"))
	if not is_replyable(connection):
		raise ValidationError(
			_("Telegram Business не разрешает отвечать через это подключение")
		)
	if str(conversation.account_id or "") != connection.get("connection_id"):
		raise ValidationError(_("Telegram Business conversation does not match the connection"))
	if not conversation.external_chat_id:
		raise ValidationError(_("Telegram Business conversation has no recipient"))
	return connection
