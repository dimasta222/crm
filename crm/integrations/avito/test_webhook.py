from frappe.tests import UnitTestCase

from crm.integrations.avito.webhook import _attachment_type, _attachment_url, _message_text


class TestAvitoWebhook(UnitTestCase):
	def test_reads_supported_text_content(self):
		self.assertEqual(_message_text("text", {"text": "Привет"}), "Привет")
		self.assertEqual(
			_message_text("link", {"link": {"text": "Ссылка", "url": "https://example.com"}}),
			"Ссылка",
		)

	def test_uses_largest_image_from_webhook(self):
		content = {
			"image": {
				"sizes": {
					"32x32": "https://example.com/small.jpg",
					"1280x960": "https://example.com/large.jpg",
				}
			}
		}
		self.assertEqual(_attachment_url("image", content), "https://example.com/large.jpg")
		self.assertEqual(_attachment_type("image"), "Image")

	def test_ignores_unknown_attachment_formats(self):
		self.assertIsNone(_attachment_url("file", {}))
		self.assertIsNone(_attachment_type("system"))
