import frappe


PAYMENT_STATUS_OPTIONS = "Unpaid\nPartially Paid\nPaid\nPostpaid\nRefunded\nCancelled"

PAYMENT_SUMMARY_SCRIPT = """class CRMDeal {
  onLoad() {
    this.updatePaymentSummary()
  }

  order_total() {
    this.doc.deal_value = this.toAmount(this.doc.order_total)
    this.updatePaymentSummary()
  }

  paid_amount() {
    this.updatePaymentSummary()
  }

  payment_terms() {
    this.updatePaymentSummary()
  }

  toAmount(value) {
    const amount = Number(value || 0)
    return Number.isFinite(amount) ? Math.max(amount, 0) : 0
  }

  updatePaymentSummary() {
    const total = this.toAmount(this.doc.order_total || this.doc.deal_value)
    const paid = this.toAmount(this.doc.paid_amount)

    this.doc.order_total = total
    this.doc.balance_amount = Math.max(total - paid, 0)

    if (total > 0 && paid >= total) {
      this.doc.payment_status = 'Paid'
    } else if (paid > 0) {
      this.doc.payment_status = 'Partially Paid'
    } else if (this.doc.payment_terms === 'Postpayment' && total > 0) {
      this.doc.payment_status = 'Postpaid'
    } else {
      this.doc.payment_status = 'Unpaid'
    }
  }
}
"""


def execute():
	configure_system_settings()
	configure_payment_fields()
	migrate_payment_statuses()
	create_payment_summary_script()
	frappe.clear_cache(doctype="CRM Deal")
	frappe.clear_cache(doctype="System Settings")


def configure_system_settings():
	frappe.db.set_single_value("System Settings", "language", "ru")
	frappe.db.set_single_value("System Settings", "time_format", "HH:mm")


def configure_payment_fields():
	frappe.db.set_value(
		"DocField",
		{"parent": "CRM Deal", "fieldname": "order_total"},
		"read_only",
		0,
		update_modified=False,
	)
	frappe.db.set_value(
		"DocField",
		{"parent": "CRM Deal", "fieldname": "payment_status"},
		"options",
		PAYMENT_STATUS_OPTIONS,
		update_modified=False,
	)


def migrate_payment_statuses():
	frappe.db.sql(
		"""
		UPDATE `tabCRM Deal`
		SET payment_status = 'Postpaid'
		WHERE payment_status = 'Postpayment'
		"""
	)


def create_payment_summary_script():
	name = "Print Studio Payment Summary"
	if frappe.db.exists("CRM Form Script", name):
		doc = frappe.get_doc("CRM Form Script", name)
	else:
		doc = frappe.new_doc("CRM Form Script")
		doc.name = name

	doc.update(
		{
			"dt": "CRM Deal",
			"view": "Form",
			"enabled": 1,
			"is_standard": 1,
			"script": PAYMENT_SUMMARY_SCRIPT,
		}
	)
	doc.save(ignore_permissions=True)
