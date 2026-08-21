import frappe

DOCTYPES = (
	"crm_order_item",
	"crm_order_application",
	"crm_dtf_roll_line",
	"crm_dtf_piece_line",
	"crm_deal",
)


def execute():
	"""Install the additive print-studio order schema without touching legacy data."""
	for doctype in DOCTYPES:
		frappe.reload_doc("fcrm", "doctype", doctype, force=True)

	for doctype in (
		"CRM Order Item",
		"CRM Order Application",
		"CRM DTF Roll Line",
		"CRM DTF Piece Line",
		"CRM Deal",
	):
		frappe.clear_cache(doctype=doctype)
