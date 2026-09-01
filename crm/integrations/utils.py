"""Shared helpers for external channel payloads."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone

from frappe.utils import convert_utc_to_system_timezone, get_datetime

NUMERIC_TIMESTAMP = re.compile(r"^[+-]?\d+(?:\.\d+)?$")


def normalize_external_datetime(value):
	"""Return a naive system-time datetime accepted by Frappe/MariaDB.

	Unix timestamps and timezone-aware values represent absolute instants. They
	are converted to Frappe's configured system timezone before the timezone
	marker is removed. Naive datetimes are already interpreted as system time.
	Invalid external values return ``None`` so callers can reject or ignore the
	event without inventing a replacement timestamp.
	"""
	if value is None or value == "" or isinstance(value, bool):
		return None

	try:
		if isinstance(value, (int, float)):
			if isinstance(value, float) and not math.isfinite(value):
				return None
			parsed = datetime.fromtimestamp(value, timezone.utc)
		elif isinstance(value, datetime):
			parsed = value
		else:
			text = str(value).strip()
			if not text:
				return None
			if NUMERIC_TIMESTAMP.fullmatch(text):
				timestamp = float(text) if "." in text else int(text)
				parsed = datetime.fromtimestamp(timestamp, timezone.utc)
			else:
				parsed = get_datetime(text)
	except Exception:
		return None

	if not parsed:
		return None
	if parsed.tzinfo is None or parsed.utcoffset() is None:
		return parsed.replace(tzinfo=None)

	utc_value = parsed.astimezone(timezone.utc)
	return convert_utc_to_system_timezone(utc_value).replace(tzinfo=None)


def make_message_key(channel, account_id, external_chat_id, external_message_id):
	"""Build a stable, fixed-length deduplication key for a channel message."""
	parts = [channel, account_id, external_chat_id, external_message_id]
	normalized = [str(part or "").casefold() for part in parts]
	material = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
	return hashlib.sha256(material.encode("utf-8")).hexdigest()
