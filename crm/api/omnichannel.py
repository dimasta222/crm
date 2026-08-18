import json
import re

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime

from crm.api.tracking import apply_first_touch


SUPPORTED_CHANNELS = {"Telegram", "Avito", "MAX", "Email", "Phone", "Website"}
HANDOFF_CODE_PATTERN = re.compile(r"\bCRM-[A-Z0-9]{8}\b", re.IGNORECASE)


@frappe.whitelist()
def create_channel_handoff(reference_doctype, reference_name, valid_for_hours=168):
	"""Create a short-lived code that links a new channel to an existing customer."""
	if reference_doctype not in {"CRM Lead", "CRM Deal", "Contact"}:
		frappe.throw(_("Unsupported reference type: {0}").format(reference_doctype))
	if not frappe.has_permission(reference_doctype, "read", reference_name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	valid_for_hours = max(1, min(int(valid_for_hours or 168), 24 * 30))
	links = _reference_links(reference_doctype, reference_name)
	code = f"CRM-{frappe.generate_hash(length=8).upper()}"
	handoff = frappe.get_doc(
		{
			"doctype": "CRM Channel Handoff",
			"handoff_code": code,
			"expires_at": add_to_date(now_datetime(), hours=valid_for_hours),
			**links,
		}
	).insert(ignore_permissions=True)
	return {
		"code": handoff.handoff_code,
		"expires_at": handoff.expires_at,
		"instruction": _("Send this code as the first message in the new channel"),
	}


@frappe.whitelist()
def ingest_message(
	channel,
	external_user_id,
	external_chat_id,
	external_message_id,
	content=None,
	account_id=None,
	sender_name=None,
	sent_at=None,
	attachment_url=None,
	attachment_type=None,
	raw_payload=None,
	tracking_code=None,
	lead_data=None,
	direction="Incoming",
	handoff_code=None,
):
	"""Store an authenticated connector event without creating duplicate leads.

	Connectors should call this method with an API-key authenticated Frappe user.
	The stable channel/account/user tuple identifies the customer. Every later
	message reuses the same lead and conversation.
	"""
	if frappe.session.user == "Guest":
		frappe.throw(_("Authentication is required"), frappe.PermissionError)
	if channel not in SUPPORTED_CHANNELS:
		frappe.throw(_("Unsupported communication channel: {0}").format(channel))
	if direction not in {"Incoming", "Outgoing"}:
		frappe.throw(_("Message direction must be Incoming or Outgoing"))
	if not handoff_code and direction == "Incoming" and content:
		match = HANDOFF_CODE_PATTERN.search(content)
		handoff_code = match.group(0).upper() if match else None

	account_id = account_id or "default"
	message_key = f"{channel}:{account_id}:{external_message_id}".lower()
	existing_message = frappe.db.exists("CRM Channel Message", {"message_key": message_key})
	if existing_message:
		return _result(existing_message)

	identity = _get_or_create_identity(
		channel,
		account_id,
		external_user_id,
		external_chat_id,
		sender_name,
		tracking_code,
		frappe.parse_json(lead_data) if lead_data else {},
		handoff_code,
	)
	conversation = _get_or_create_conversation(identity, external_chat_id)
	message = frappe.get_doc(
		{
			"doctype": "CRM Channel Message",
			"conversation": conversation.name,
			"external_message_id": external_message_id,
			"direction": direction,
			"sender_name": sender_name,
			"sent_at": sent_at or now_datetime(),
			"delivery_status": "Delivered",
			"content": content,
			"attachment_url": attachment_url,
			"attachment_type": attachment_type,
			"raw_payload": json.dumps(frappe.parse_json(raw_payload), ensure_ascii=False)
			if raw_payload
			else None,
		}
	).insert(ignore_permissions=True)
	identity.db_set("last_message_at", message.sent_at, update_modified=False)
	result = _result(message.name)
	frappe.publish_realtime("crm_channel_message", result, after_commit=True)
	return result


@frappe.whitelist()
def get_channel_messages(reference_doctype, reference_name):
	"""Return all channel messages linked to a Lead, Deal, or Contact."""
	fieldname = {
		"CRM Lead": "lead",
		"CRM Deal": "deal",
		"Contact": "contact",
	}.get(reference_doctype)
	if not fieldname:
		frappe.throw(_("Unsupported reference type: {0}").format(reference_doctype))
	if not frappe.has_permission(reference_doctype, "read", reference_name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	conversations = frappe.get_all(
		"CRM Channel Conversation",
		filters={fieldname: reference_name},
		fields=["name", "channel", "account_id", "external_chat_id"],
	)
	if not conversations:
		return []
	conversation_map = {conversation.name: conversation for conversation in conversations}
	messages = frappe.get_all(
		"CRM Channel Message",
		filters={"conversation": ["in", list(conversation_map)]},
		fields=[
			"name",
			"conversation",
			"direction",
			"sender_name",
			"sent_at",
			"delivery_status",
			"content",
			"attachment_url",
			"attachment_type",
		],
		order_by="sent_at asc, creation asc",
		limit_page_length=1000,
	)
	for message in messages:
		conversation = conversation_map[message.conversation]
		message.channel = conversation.channel
		message.account_id = conversation.account_id
		message.external_chat_id = conversation.external_chat_id
	return messages


def _get_or_create_identity(
	channel,
	account_id,
	external_user_id,
	external_chat_id,
	sender_name,
	tracking_code,
	lead_data,
	handoff_code=None,
):
	identity_key = f"{channel}:{account_id}:{external_user_id}".lower()
	name = frappe.db.exists("CRM External Identity", {"identity_key": identity_key})
	if name:
		return frappe.get_doc("CRM External Identity", name)

	handoff = _get_handoff(handoff_code) if handoff_code else None
	if handoff:
		links = {"lead": handoff.lead, "contact": handoff.contact, "deal": handoff.deal}
	else:
		lead = frappe.new_doc("CRM Lead")
		lead.first_name = lead_data.get("first_name") or sender_name or f"{channel} customer"
		lead.last_name = lead_data.get("last_name")
		lead.email = lead_data.get("email")
		lead.mobile_no = lead_data.get("mobile_no")
		lead.source = lead_data.get("source")
		lead.first_touch_channel = channel
		lead.tracking_code = tracking_code
		apply_first_touch(lead, tracking_code, lead_data)
		lead.insert(ignore_permissions=True)
		links = {"lead": lead.name, "contact": None, "deal": None}

	identity = frappe.get_doc(
		{
			"doctype": "CRM External Identity",
			"channel": channel,
			"account_id": account_id,
			"external_user_id": external_user_id,
			"external_chat_id": external_chat_id,
			"username": lead_data.get("username"),
			**links,
			"is_primary": 1,
		}
	).insert(ignore_permissions=True)
	if handoff:
		handoff.db_set(
			{
				"used_at": now_datetime(),
				"used_channel": channel,
				"used_external_user_id": external_user_id,
			},
			update_modified=False,
		)
	return identity


def _get_or_create_conversation(identity, external_chat_id):
	conversation_key = f"{identity.channel}:{identity.account_id or ''}:{external_chat_id}".lower()
	name = frappe.db.exists("CRM Channel Conversation", {"conversation_key": conversation_key})
	if name:
		return frappe.get_doc("CRM Channel Conversation", name)
	return frappe.get_doc(
		{
			"doctype": "CRM Channel Conversation",
			"channel": identity.channel,
			"account_id": identity.account_id,
			"external_chat_id": external_chat_id,
			"lead": identity.lead,
			"contact": identity.contact,
			"deal": identity.deal,
			"status": "Open",
		}
	).insert(ignore_permissions=True)


def _result(message_name):
	message = frappe.get_doc("CRM Channel Message", message_name)
	conversation = frappe.get_cached_doc("CRM Channel Conversation", message.conversation)
	return {
		"message": message.name,
		"conversation": conversation.name,
		"lead": conversation.lead,
		"contact": conversation.contact,
		"deal": conversation.deal,
	}


def link_conversations_after_conversion(lead, deal, contact=None):
	"""Keep channel identities and history attached after lead conversion."""
	frappe.db.sql(
		"""update `tabCRM Channel Conversation`
		set deal = %s, contact = coalesce(%s, contact)
		where lead = %s""",
		(deal, contact, lead),
	)
	frappe.db.sql(
		"""update `tabCRM External Identity`
		set deal = coalesce(deal, %s) where lead = %s""",
		(deal, lead),
	)
	if contact:
		frappe.db.sql(
			"""update `tabCRM External Identity`
			set contact = %s where lead = %s and (contact is null or contact = '')""",
			(contact, lead),
		)
	frappe.db.sql(
		"""update `tabCRM Channel Handoff`
		set deal = %s, contact = coalesce(%s, contact)
		where lead = %s and used_at is null""",
		(deal, contact, lead),
	)


def _reference_links(reference_doctype, reference_name):
	if reference_doctype == "CRM Lead":
		return {"lead": reference_name, "contact": None, "deal": None}
	if reference_doctype == "Contact":
		lead = frappe.db.get_value(
			"CRM External Identity",
			{"contact": reference_name, "lead": ["is", "set"]},
			"lead",
			order_by="last_message_at desc",
		)
		return {"lead": lead, "contact": reference_name, "deal": None}
	deal = frappe.get_cached_doc("CRM Deal", reference_name)
	return {"lead": deal.lead, "contact": deal.contact, "deal": deal.name}


def _get_handoff(code):
	name = frappe.db.exists("CRM Channel Handoff", {"handoff_code": (code or "").upper()})
	if not name:
		frappe.throw(_("Channel link code is invalid"))
	handoff = frappe.get_doc("CRM Channel Handoff", name)
	if handoff.used_at:
		frappe.throw(_("Channel link code has already been used"))
	if get_datetime(handoff.expires_at) < now_datetime():
		frappe.throw(_("Channel link code has expired"))
	return handoff
