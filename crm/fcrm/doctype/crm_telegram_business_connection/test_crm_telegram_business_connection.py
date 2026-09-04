import frappe

from crm.tests import CRMTestCase


class TestCRMTelegramBusinessConnection(CRMTestCase):
	def _doc(self, rights_json):
		return frappe.get_doc(
			{
				"doctype": "CRM Telegram Business Connection",
				"connection_id": "validation-test-connection",
				"rights_json": rights_json,
			}
		)

	def test_rights_json_must_be_valid_json(self):
		with self.assertRaises(frappe.ValidationError):
			self._doc("not-json").validate()

	def test_rights_json_must_be_an_object(self):
		with self.assertRaises(frappe.ValidationError):
			self._doc("[]").validate()

	def test_rights_json_rejects_unknown_fields(self):
		with self.assertRaises(frappe.ValidationError):
			self._doc('{"unrelated_update_field":true}').validate()

	def test_rights_json_accepts_only_booleans(self):
		with self.assertRaises(frappe.ValidationError):
			self._doc('{"can_reply":1}').validate()

	def test_valid_rights_are_canonicalized(self):
		doc = self._doc('{"can_reply":true,"can_read_messages":false}')

		doc.validate()

		self.assertEqual(
			doc.rights_json,
			'{"can_read_messages":false,"can_reply":true}',
		)
