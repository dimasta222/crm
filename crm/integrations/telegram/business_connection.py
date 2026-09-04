"""Durable Telegram Business connection state with Redis as a cache only."""

from __future__ import annotations

import json
import re
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime

from crm.integrations.telegram import api as telegram_api
from crm.integrations.utils import normalize_external_datetime

BUSINESS_CONNECTION_DOCTYPE = "CRM Telegram Business Connection"
BUSINESS_CONNECTION_CACHE_PREFIX = "crm:telegram:business_connection"
BUSINESS_CONNECTION_CACHE_TTL = 300
BUSINESS_CONNECTION_STALE_CACHE_TTL = 60
BUSINESS_CONNECTION_REFRESH_AFTER = timedelta(hours=6)
TELEGRAM_USERNAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")
ALLOWED_BUSINESS_RIGHTS = {
	"can_reply",
	"can_read_messages",
	"can_delete_sent_messages",
	"can_delete_all_messages",
	"can_edit_name",
	"can_edit_bio",
	"can_edit_profile_photo",
	"can_edit_username",
	"can_change_gift_settings",
	"can_view_gifts_and_stars",
	"can_convert_gifts_to_stars",
	"can_transfer_and_upgrade_gifts",
	"can_transfer_stars",
	"can_manage_stories",
}


class BusinessConnectionError(Exception):
	def __init__(self, error_type):
		self.error_type = error_type
		super().__init__(error_type)


class TemporaryBusinessConnectionError(BusinessConnectionError):
	pass


class PermanentBusinessConnectionError(BusinessConnectionError):
	pass


def normalize_business_username(username, *, raise_on_invalid=False):
	username = str(username or "").strip().lstrip("@").strip()
	if not username:
		return None
	if not TELEGRAM_USERNAME_PATTERN.fullmatch(username):
		if raise_on_invalid:
			frappe.throw(_("Telegram Business username is invalid"))
		return None
	return username


def upsert_business_connection(connection, *, source="webhook"):
	"""Atomically insert or update the durable connection record."""
	if not isinstance(connection, dict):
		raise PermanentBusinessConnectionError("invalid_connection")
	connection_id = str(connection.get("id") or "").strip()
	if not connection_id:
		raise PermanentBusinessConnectionError("missing_connection_id")

	user = connection.get("user") if isinstance(connection.get("user"), dict) else None
	rights_present = "rights" in connection
	rights = _normalize_rights(connection.get("rights")) if rights_present else {}
	now = now_datetime()
	is_sync = source in {"api", "webhook"}
	connected_at = normalize_external_datetime(connection.get("date")) if "date" in connection else None
	owner = frappe.session.user if frappe.session.user and frappe.session.user != "Guest" else "Administrator"
	values = {
		"name": frappe.generate_hash(length=10),
		"owner": owner,
		"now": now,
		"connection_id": connection_id,
		"business_user_id": str((user or {}).get("id") or ""),
		"business_username": normalize_business_username((user or {}).get("username")) or "",
		"business_first_name": str((user or {}).get("first_name") or ""),
		"business_last_name": str((user or {}).get("last_name") or ""),
		"user_chat_id": str(connection.get("user_chat_id") or ""),
		"connected_at": connected_at,
		"is_enabled": cint(connection.get("is_enabled")) if "is_enabled" in connection else 0,
		"can_read_messages": cint(rights.get("can_read_messages")),
		"can_reply": cint(rights.get("can_reply")),
		"rights_json": json.dumps(rights, sort_keys=True, separators=(",", ":")),
		"last_event_at": now if source == "webhook" else None,
		"disabled_at": now if connection.get("is_enabled") is False else None,
		"has_user": cint(user is not None),
		"has_user_chat_id": cint("user_chat_id" in connection),
		"has_date": cint("date" in connection),
		"has_is_enabled": cint("is_enabled" in connection),
		"has_rights": cint(rights_present),
		"is_webhook": cint(source == "webhook"),
		"has_sync": cint(is_sync),
		"last_synced_at": now if is_sync else None,
	}
	frappe.db.sql(
		f"""
		insert into `tab{BUSINESS_CONNECTION_DOCTYPE}`
			(name, creation, modified, modified_by, owner, docstatus, idx,
			 connection_id, business_user_id, business_username, business_first_name,
			 business_last_name, user_chat_id, connected_at, is_enabled,
			 can_read_messages, can_reply, rights_json, last_event_at,
			 last_synced_at, disabled_at, sync_status, last_sync_error_type)
		values
			(%(name)s, %(now)s, %(now)s, %(owner)s, %(owner)s, 0, 0,
			 %(connection_id)s, %(business_user_id)s, %(business_username)s,
			 %(business_first_name)s, %(business_last_name)s, %(user_chat_id)s,
			 %(connected_at)s, %(is_enabled)s, %(can_read_messages)s, %(can_reply)s,
			 %(rights_json)s, %(last_event_at)s, %(last_synced_at)s, %(disabled_at)s,
			 'Unknown', '')
		on duplicate key update
			modified = values(modified),
			modified_by = values(modified_by),
			business_user_id = if(%(has_user)s, values(business_user_id), business_user_id),
			business_username = if(%(has_user)s, values(business_username), business_username),
			business_first_name = if(%(has_user)s, values(business_first_name), business_first_name),
			business_last_name = if(%(has_user)s, values(business_last_name), business_last_name),
			user_chat_id = if(%(has_user_chat_id)s, values(user_chat_id), user_chat_id),
			connected_at = if(%(has_date)s, values(connected_at), connected_at),
			is_enabled = if(%(has_is_enabled)s, values(is_enabled), is_enabled),
			can_read_messages = if(%(has_rights)s, values(can_read_messages), can_read_messages),
			can_reply = if(%(has_rights)s, values(can_reply), can_reply),
			rights_json = if(%(has_rights)s, values(rights_json), rights_json),
			last_event_at = if(%(is_webhook)s, values(last_event_at), last_event_at),
			last_synced_at = if(%(has_sync)s, values(last_synced_at), last_synced_at),
			disabled_at = if(%(has_is_enabled)s, values(disabled_at), disabled_at),
			last_sync_error_type = ''
		""",
		values,
	)
	doc = _get_from_db(connection_id)
	status = _connection_status(doc)
	frappe.db.set_value(
		BUSINESS_CONNECTION_DOCTYPE,
		doc.name,
		{"sync_status": status, "last_sync_error_type": ""},
		update_modified=False,
	)
	doc.sync_status = status
	doc.last_sync_error_type = ""
	_cache_connection(doc)
	_update_settings_status(status, doc.last_synced_at)
	return _as_connection(doc)


def resolve_business_connection(connection_id, *, force_refresh=False):
	"""Resolve from Redis, then DB, then Telegram, refreshing stale DB data."""
	connection_id = str(connection_id or "").strip()
	if not connection_id:
		raise PermanentBusinessConnectionError("missing_connection_id")

	if not force_refresh and (cached := _get_from_cache(connection_id)):
		return cached

	doc = _get_from_db(connection_id)
	if doc and not force_refresh and not _is_stale(doc):
		_cache_connection(doc)
		return _as_connection(doc)

	try:
		response = telegram_api.request(
			"getBusinessConnection", {"business_connection_id": connection_id}
		)
	except telegram_api.TelegramTemporaryAPIError as error:
		if doc and _is_usable_connection(doc):
			doc = _mark_sync_error(connection_id, "Stale/Temporary Error", error.error_type)
			_cache_connection(doc, expires_in_sec=BUSINESS_CONNECTION_STALE_CACHE_TTL)
			return _as_connection(doc)
		_mark_sync_error(connection_id, "Temporary Error", error.error_type)
		raise TemporaryBusinessConnectionError(error.error_type) from None
	except telegram_api.TelegramPermanentAPIError as error:
		_mark_sync_error(connection_id, "Invalid", error.error_type)
		raise PermanentBusinessConnectionError(error.error_type) from None

	result = response.get("result")
	if not isinstance(result, dict) or str(result.get("id") or "") != connection_id:
		_mark_sync_error(connection_id, "Invalid", "invalid_response")
		raise PermanentBusinessConnectionError("invalid_response")
	return upsert_business_connection(result, source="api")


def mark_connection_review(connection_id, error_type):
	_mark_sync_error(connection_id, "Needs Review", error_type)


def is_readable(connection):
	return bool(connection and connection.get("is_enabled") and connection.get("can_read_messages"))


def is_replyable(connection):
	return bool(connection and connection.get("is_enabled") and connection.get("can_reply"))


def cache_key(connection_id):
	return f"{BUSINESS_CONNECTION_CACHE_PREFIX}:{connection_id}"


def clear_cached_connection(connection_id):
	frappe.cache.delete_value(cache_key(connection_id))


def _normalize_rights(rights):
	if rights in (None, ""):
		return {}
	if isinstance(rights, str):
		try:
			rights = json.loads(rights)
		except (TypeError, ValueError):
			raise PermanentBusinessConnectionError("invalid_rights") from None
	if not isinstance(rights, dict):
		raise PermanentBusinessConnectionError("invalid_rights")
	return {key: bool(rights[key]) for key in sorted(ALLOWED_BUSINESS_RIGHTS) if key in rights}


def _get_from_db(connection_id):
	name = frappe.db.get_value(BUSINESS_CONNECTION_DOCTYPE, {"connection_id": connection_id}, "name")
	return frappe.get_doc(BUSINESS_CONNECTION_DOCTYPE, name) if name else None


def _get_from_cache(connection_id):
	value = frappe.cache.get_value(cache_key(connection_id), expires=True)
	if not isinstance(value, dict) or value.get("connection_id") != connection_id:
		return None
	return frappe._dict(value)


def _cache_connection(connection, *, expires_in_sec=BUSINESS_CONNECTION_CACHE_TTL):
	frappe.cache.set_value(
		cache_key(connection.connection_id),
		dict(_as_connection(connection)),
		expires_in_sec=expires_in_sec,
	)


def _as_connection(connection):
	return frappe._dict(
		connection_id=str(connection.connection_id),
		business_user_id=str(connection.business_user_id or ""),
		business_username=str(connection.business_username or ""),
		user_chat_id=str(connection.user_chat_id or ""),
		is_enabled=bool(connection.is_enabled),
		can_read_messages=bool(connection.can_read_messages),
		can_reply=bool(connection.can_reply),
		rights=_normalize_rights(connection.rights_json),
		last_synced_at=connection.last_synced_at,
		sync_status=connection.sync_status,
	)


def _is_stale(connection):
	if not connection.last_synced_at:
		return True
	return get_datetime(connection.last_synced_at) + BUSINESS_CONNECTION_REFRESH_AFTER < now_datetime()


def _is_usable_connection(connection):
	return bool(
		connection.business_user_id
		and connection.is_enabled
		and (connection.can_read_messages or connection.can_reply)
	)


def _connection_status(connection):
	if not connection.business_user_id:
		return "Incomplete"
	if not connection.is_enabled:
		return "Disabled"
	if connection.can_read_messages and connection.can_reply:
		return "Connected"
	if connection.can_read_messages:
		return "Read Only"
	return "Insufficient Rights"


def _mark_sync_error(connection_id, status, error_type):
	doc = _get_from_db(connection_id)
	if not doc:
		upsert_business_connection({"id": connection_id}, source="error")
		doc = _get_from_db(connection_id)
	frappe.db.set_value(
		BUSINESS_CONNECTION_DOCTYPE,
		doc.name,
		{"sync_status": status, "last_sync_error_type": error_type},
		update_modified=False,
	)
	doc.sync_status = status
	doc.last_sync_error_type = error_type
	clear_cached_connection(connection_id)
	_update_settings_status(status, doc.last_synced_at)
	return doc


def _update_settings_status(status, synced_at):
	frappe.db.set_single_value("CRM Channel Settings", "telegram_business_status", status)
	frappe.db.set_single_value(
		"CRM Channel Settings", "telegram_business_last_synced_at", synced_at
	)
