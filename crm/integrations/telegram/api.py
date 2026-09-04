"""Small, token-safe wrapper around the Telegram Bot API."""

from __future__ import annotations

import requests
from urllib3.util import connection as urllib3_connection

from crm.integrations.channel_settings import value

API_ROOT = "https://api.telegram.org"

# The production host has no reliable IPv6 route to Telegram.
urllib3_connection.HAS_IPV6 = False


class TelegramAPIError(Exception):
	def __init__(self, error_type):
		self.error_type = error_type
		super().__init__(error_type)


class TelegramTemporaryAPIError(TelegramAPIError):
	pass


class TelegramPermanentAPIError(TelegramAPIError):
	pass


def request(method, payload=None, timeout=20):
	"""Call the Bot API without ever propagating its token-bearing URL."""
	token = value("telegram_bot_token")
	if not token:
		raise TelegramPermanentAPIError("token_missing")

	try:
		response = requests.post(
			f"{API_ROOT}/bot{token}/{method}",
			json=payload or {},
			timeout=timeout,
		)
	except (requests.Timeout, requests.ConnectionError):
		raise TelegramTemporaryAPIError("network") from None
	except requests.RequestException:
		raise TelegramTemporaryAPIError("request_failed") from None

	status_code = int(response.status_code or 0)
	if status_code == 429:
		raise TelegramTemporaryAPIError("telegram_429")
	if status_code >= 500:
		raise TelegramTemporaryAPIError("telegram_5xx")
	if status_code >= 400:
		error_type = "unknown_connection" if method == "getBusinessConnection" else "telegram_4xx"
		raise TelegramPermanentAPIError(error_type)

	try:
		result = response.json()
	except ValueError:
		raise TelegramTemporaryAPIError("invalid_response") from None

	if not isinstance(result, dict):
		raise TelegramTemporaryAPIError("invalid_response")
	if not result.get("ok"):
		error_code = int(result.get("error_code") or 0)
		if error_code == 429:
			raise TelegramTemporaryAPIError("telegram_429")
		if error_code >= 500:
			raise TelegramTemporaryAPIError("telegram_5xx")
		error_type = "unknown_connection" if method == "getBusinessConnection" else "telegram_rejected"
		raise TelegramPermanentAPIError(error_type)
	return result
