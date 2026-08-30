"""Avito Messenger API client based on the official v1/v3 schema."""

import frappe
import requests
from frappe import _

from crm.api.omnichannel import _ingest_message
from crm.integrations.channel_settings import value


API_ROOT = "https://api.avito.ru"
TOKEN_CACHE_KEY = "crm:avito:access_token"


def send_text(conversation, content):
	if not value("avito_enabled"):
		frappe.throw(_("Avito integration is disabled"))
	if len(content) > 1000:
		frappe.throw(_("Avito messages cannot exceed 1000 characters"))

	account_id = str(conversation.account_id or value("avito_account_id") or "")
	if not account_id:
		frappe.throw(_("Avito account ID is not configured"))
	response = _request(
		"post",
		f"/messenger/v1/accounts/{account_id}/chats/{conversation.external_chat_id}/messages",
		json={"type": "text", "message": {"text": content}},
	)
	identity = frappe.db.get_value(
		"CRM External Identity",
		{
			"channel": "Avito",
			"account_id": account_id,
			"external_chat_id": conversation.external_chat_id,
		},
		["external_user_id", "username"],
		as_dict=True,
	)
	if not identity:
		frappe.throw(_("Avito identity is not linked to this conversation"))
	return _ingest_message(
		channel="Avito",
		account_id=account_id,
		external_user_id=identity.external_user_id,
		external_chat_id=conversation.external_chat_id,
		external_message_id=str(response.get("id")),
		content=content,
		sender_name=frappe.utils.get_fullname(frappe.session.user),
		raw_payload=response,
		direction="Outgoing",
		lead_data={"username": identity.username},
	)


def subscribe_webhook(url):
	return _request("post", "/messenger/v3/webhook", json={"url": url})


def enrich_identity(account_id, chat_id, external_user_id):
	"""Fill the Avito profile name asynchronously without delaying the webhook."""
	chat = _request("get", f"/messenger/v2/accounts/{account_id}/chats/{chat_id}")
	participant = next(
		(user for user in chat.get("users") or [] if str(user.get("id")) == str(external_user_id)),
		None,
	)
	if not participant or not participant.get("name"):
		return
	identity_name = frappe.db.get_value(
		"CRM External Identity",
		{
			"channel": "Avito",
			"account_id": str(account_id),
			"external_user_id": str(external_user_id),
		},
		"name",
	)
	if not identity_name:
		return
	identity = frappe.get_doc("CRM External Identity", identity_name)
	identity.db_set("username", participant["name"], update_modified=False)
	if identity.lead:
		first_name = frappe.db.get_value("CRM Lead", identity.lead, "first_name")
		if not first_name or first_name == "Avito customer":
			frappe.db.set_value("CRM Lead", identity.lead, "first_name", participant["name"])


def _request(method, path, **kwargs):
	try:
		response = requests.request(
			method,
			f"{API_ROOT}{path}",
			headers={"Authorization": f"Bearer {_access_token()}"},
			timeout=20,
			**kwargs,
		)
		response.raise_for_status()
		return response.json()
	except (requests.RequestException, ValueError) as error:
		frappe.log_error(title="Avito Messenger API request failed", message=str(error))
		frappe.throw(_("Avito Messenger API request failed"))


def _access_token():
	if token := frappe.cache.get_value(TOKEN_CACHE_KEY):
		return token
	client_id = value("avito_client_id")
	client_secret = value("avito_client_secret")
	if not client_id or not client_secret:
		frappe.throw(_("Avito API credentials are not configured"))
	try:
		response = requests.post(
			f"{API_ROOT}/token",
			data={
				"grant_type": "client_credentials",
				"client_id": client_id,
				"client_secret": client_secret,
			},
			timeout=20,
		)
		response.raise_for_status()
		payload = response.json()
	except (requests.RequestException, ValueError) as error:
		frappe.log_error(title="Avito OAuth request failed", message=str(error))
		frappe.throw(_("Could not authorize with Avito"))
	token = payload.get("access_token")
	if not token:
		frappe.throw(_("Avito did not return an access token"))
	frappe.cache.set_value(
		TOKEN_CACHE_KEY,
		token,
		expires_in_sec=max(60, int(payload.get("expires_in") or 3600) - 60),
	)
	return token
