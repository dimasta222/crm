import frappe
from pypika import Criterion


@frappe.whitelist()
def get_views(doctype: str):
	View = frappe.qb.DocType("CRM View Settings")
	query = (
		frappe.qb.from_(View)
		.select("*")
		.where(Criterion.any([View.user == "", View.user == frappe.session.user]))
	)
	if doctype:
		query = query.where(View.dt == doctype)
	views = query.run(as_dict=True)
	# The frontend indexes standard views by doctype and type. Return the global
	# default first and the current user's view last so their saved columns,
	# filters and sort order always win after a page refresh.
	views.sort(key=lambda view: bool(view.get("user")))
	return views
