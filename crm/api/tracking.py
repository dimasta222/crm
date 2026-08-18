from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import frappe
from frappe.utils import now_datetime


ATTRIBUTION_FIELDS = (
	"attracted_by",
	"first_touch_source",
	"first_touch_channel",
	"campaign_name",
	"tracking_code",
	"first_touch_at",
	"landing_url",
	"utm_source",
	"utm_medium",
	"utm_campaign",
	"utm_content",
	"utm_term",
	"yclid",
	"yandex_client_id",
)

CONTACT_ATTRIBUTION_FIELDS = {
	"attracted_by": "crm_attracted_by",
	"first_touch_source": "crm_first_touch_source",
	"first_touch_channel": "crm_first_touch_channel",
	"campaign_name": "crm_campaign_name",
	"tracking_code": "crm_tracking_code",
	"first_touch_at": "crm_first_touch_at",
}


def get_tracking_link(code):
	if not code:
		return None
	name = frappe.db.exists("CRM Tracking Link", {"tracking_code": code.lower(), "active": 1})
	return frappe.get_doc("CRM Tracking Link", name) if name else None


def build_destination(link):
	destination = link.destination_url
	if link.telegram_bot_username and link.channel == "Telegram":
		destination = f"https://t.me/{link.telegram_bot_username.lstrip('@')}?start={link.tracking_code}"
	parts = urlsplit(destination)
	query = dict(parse_qsl(parts.query, keep_blank_values=True))
	query.setdefault("crm_tracking_code", link.tracking_code)
	return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def register_click(link):
	frappe.db.sql(
		"""update `tabCRM Tracking Link`
		set click_count = coalesce(click_count, 0) + 1,
			last_clicked_at = %s
		where name = %s""",
		(now_datetime(), link.name),
	)


def apply_first_touch(doc, code, request_args=None):
	"""Apply immutable first-touch attribution to a CRM Lead or CRM Deal."""
	if not code or doc.get("first_touch_at"):
		return False
	link = get_tracking_link(code)
	if not link:
		return False
	request_args = request_args or {}
	doc.update(
		{
			"attracted_by": link.manager,
			"first_touch_source": link.source,
			"first_touch_channel": link.channel,
			"campaign_name": link.campaign_name,
			"tracking_code": link.tracking_code,
			"first_touch_at": now_datetime(),
			"landing_url": request_args.get("landing_url"),
			"utm_source": request_args.get("utm_source"),
			"utm_medium": request_args.get("utm_medium"),
			"utm_campaign": request_args.get("utm_campaign"),
			"utm_content": request_args.get("utm_content"),
			"utm_term": request_args.get("utm_term"),
			"yclid": request_args.get("yclid"),
			"yandex_client_id": request_args.get("yandex_client_id"),
		}
	)
	return True


def ensure_first_touch_timestamp(doc):
	"""Timestamp manually entered attribution so it becomes immutable after save."""
	if doc.get("first_touch_at"):
		return
	if any(doc.get(fieldname) for fieldname in ATTRIBUTION_FIELDS if fieldname != "first_touch_at"):
		doc.set("first_touch_at", now_datetime())


def copy_attribution(source, target):
	for fieldname in ATTRIBUTION_FIELDS:
		if target.meta.has_field(fieldname) and not target.get(fieldname):
			target.set(fieldname, source.get(fieldname))


def copy_attribution_to_contact(source, contact_name):
	"""Preserve the first-touch source on a new or existing Contact."""
	if not contact_name:
		return
	contact = frappe.get_doc("Contact", contact_name)
	values = {}
	for source_field, contact_field in CONTACT_ATTRIBUTION_FIELDS.items():
		if contact.meta.has_field(contact_field) and not contact.get(contact_field):
			value = source.get(source_field)
			if value:
				values[contact_field] = value
	if values:
		frappe.db.set_value("Contact", contact.name, values, update_modified=False)
