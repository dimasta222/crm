import traceback
from unittest.mock import patch

import requests
from frappe.exceptions import ValidationError
from frappe.tests import UnitTestCase

from crm.integrations.telegram import client as telegram_client


class TestTelegramClient(UnitTestCase):
	def test_request_failure_does_not_expose_bot_token(self):
		bot_token = "telegram-token-sentinel"
		request_error = requests.ConnectTimeout(
			f"Connection failed for https://api.telegram.org/bot{bot_token}/setWebhook"
		)
		with (
			patch.object(telegram_client, "value", return_value=bot_token),
			patch.object(telegram_client.requests, "post", side_effect=request_error),
			self.assertRaises(ValidationError) as context,
		):
			telegram_client.subscribe_webhook("https://crm.example.test/webhook", "webhook-secret")

		formatted_traceback = "".join(
			traceback.format_exception(
				type(context.exception), context.exception, context.exception.__traceback__
			)
		)
		self.assertNotIn(bot_token, str(context.exception))
		self.assertNotIn(bot_token, formatted_traceback)
