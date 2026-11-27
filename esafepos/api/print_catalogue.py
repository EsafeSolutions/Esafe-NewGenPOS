"""Read-only, permission-scoped menu/catalogue data and single-unit offers."""
from html.parser import HTMLParser

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from esafepos.api import permissions
from esafepos.price_books import effective_prices, standard_prices, resolve_price_list
from esafepos.promotions.engine import evaluate, is_active, _matching_indexes
from esafepos.promotions.loader import get_active_promotions

PAGE_SIZE = 200


def can_print():
    return bool(permissions.allowed(permissions.PRINT_LABELS) and frappe.has_permission("Item", "read"))


class _Description(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        if tag in ("p", "br", "div", "li") and not self.hidden:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        if tag in ("p", "div", "li") and not self.hidden:
            self.parts.append("\n")

    def handle_data(self, value):
        if not self.hidden:
            self.parts.append(value)


def description_text(value):
    parser = _Description()
    parser.feed(str(value or ""))
    parser.close()
    return "\n".join(" ".join(line.split()) for line in "".join(parser.parts).splitlines() if line.strip())


def _erp_rate(profile, item, price, customer, group, currency, now):
    # Resolve one item at quantity one, never a synthetic multi-item basket.
    # The native rule resolver reads rules without inserting an invoice or
    # changing the POS Profile's ignore_pricing_rule setting.
    from erpnext.accounts.doctype.pricing_rule.pricing_rule import get_pricing_rule_for_item
    parenttype = "Sales Invoice" if profile.get("esafepos_invoice_mode") == "Sales Invoice" else "POS Invoice"
    args = frappe._dict(doctype=parenttype + " Item", parenttype=parenttype, parent=None,
                        name="catalogue-preview", item_code=item.name, item_group=item.item_group,
                        brand=item.brand, qty=1, stock_qty=1, uom=item.stock_uom, stock_uom=item.stock_uom,
                        conversion_factor=1, company=profile.company, pos_profile=profile.name,
                        warehouse=profile.get("warehouse"), customer=customer,
                        customer_group=group, territory=frappe.get_cached_value("Customer", customer, "territory") if customer else None,
                        currency=currency, conversion_rate=1, plc_conversion_rate=1, price_list_currency=currency,
                        price_list=resolve_price_list(profile, group, customer=customer), price_list_rate=price,
                        rate=price, amount=price, transaction_type="selling", transaction_date=str(now.date()),
                        ignore_pricing_rule=0, coupon_code=None, pricing_rules=None)
    result = get_pricing_rule_for_item(args) or {}
    rate = flt(result.get("price_list_rate", price))
    if result.get("margin_type") == "Percentage":
        rate *= 1 + flt(result.get("margin_rate_or_amount")) / 100
    elif result.get("margin_type") == "Amount":
        rate += flt(result.get("margin_rate_or_amount"))
    discount = flt(result.get("discount_amount"))
    if not discount:
        discount = rate * flt(result.get("discount_percentage")) / 100
    offers = []
    if result.get("has_pricing_rule"):
        offers.append(_("Automatic ERPNext pricing rule"))
    if result.get("free_item_data"):
        offers.append(_("Free-item offer; checkout conditions apply"))
    return max(0, rate - discount), offers, rate


def _unit_offer(line, promos, profile, group, now):
    cart = {"pos_profile": profile.name, "customer_group": group, "items": [line]}
    result = evaluate(cart, promos, now)
    net = max(0, line["price"] - result["line_discounts"][0] - result.get("basket_discount", 0))
    applied = {row["name"] for row in result.get("applied", [])}
    offers = []
    for promo in promos:
        if is_active(promo, now, cart) and _matching_indexes(cart, promo):
            suffix = "" if promo["name"] in applied else _(" (conditions apply)")
            offers.append((promo.get("title") or promo["name"]) + suffix)
    return net, offers


@frappe.whitelist()
def page(pos_profile, after=""):
    if not can_print():
        frappe.throw(_("You are not allowed to print item catalogues."), frappe.PermissionError)
    permissions.assert_outlet(pos_profile)
    profile = frappe.get_cached_doc("POS Profile", pos_profile)
    if profile.get("disabled"):
        frappe.throw(_("Choose an enabled outlet."))
    from esafepos.api.catalog import internal_item_codes, item_groups_under
    from esafepos.api.labels import _tax_factors
    from esafepos.features import enabled
    from esafepos.currency import company_currency

    filters = [["disabled", "=", 0], ["is_sales_item", "=", 1], ["has_variants", "=", 0]]
    if after:
        filters.append(["name", ">", str(after)])
    internal = internal_item_codes()
    if internal:
        filters.append(["name", "not in", sorted(internal)])
    groups = item_groups_under([row.item_group for row in profile.get("item_groups") or []])
    if groups:
        filters.append(["item_group", "in", groups])
    # get_list preserves Item user permissions, including every subsequent page.
    items = frappe.get_list("Item", filters=filters,
                            fields=["name", "item_name", "item_group", "brand", "stock_uom", "description", "image", "_user_tags"],
                            order_by="name asc", limit_page_length=PAGE_SIZE + 1)
    more = len(items) > PAGE_SIZE
    items = items[:PAGE_SIZE]
    codes = [row.name for row in items]
    uoms = {row.name: row.stock_uom for row in items}
    customer = profile.get("customer")
    group = frappe.get_cached_value("Customer", customer, "customer_group") if customer else None
    currency = profile.get("currency") or company_currency(profile.company)
    prices = effective_prices(profile, codes, group, stock_uom_map=uoms, customer=customer)
    standard = standard_prices(profile, codes, stock_uom_map=uoms)
    factors = _tax_factors(profile, codes, prices)
    now = now_datetime()
    erp = enabled("enable_erp_pricing_rules")
    promos = [] if erp else get_active_promotions(profile.name)
    rows = []
    for item in items:
        price = flt(prices.get(item.name))
        line = {"item_code": item.name, "item_group": item.item_group, "brand": item.brand,
                "tags": [tag.strip() for tag in (item.get("_user_tags") or "").split(",") if tag.strip()],
                "qty": 1, "price": price, "standard_price": flt(standard.get(item.name)) or price}
        net, offers = (price, [])
        reference = max(price, flt(standard.get(item.name)))
        if price > 0:
            if erp:
                net, offers, rule_reference = _erp_rate(profile, item, price, customer, group, currency, now)
                reference = max(reference, rule_reference)
            else:
                net, offers = _unit_offer(line, promos, profile, group, now)
        factor = factors.get(item.name, 1)
        rows.append({"item_code": item.name, "item_name": item.item_name or item.name,
                     "category": item.item_group or "", "brand": item.brand or "", "uom": item.stock_uom,
                     "description": description_text(item.description), "image": item.image or "",
                     "price": flt(net * factor, 6), "regular_price": flt(reference * factor, 6),
                     "unpriced": price <= 0, "offers": offers})
    return {"items": rows, "has_more": more, "next": items[-1].name if more and items else "",
            "company": profile.company, "outlet": profile.name, "currency": currency,
            "price_list": resolve_price_list(profile, group, customer=customer), "generated_at": str(now),
            "pricing_engine": "ERPNext" if erp else "EsafePOS",
            "price_note": _("Prices for one stock unit and the outlet's default customer, including configured item taxes. Fixed transaction charges, coupons and basket/quantity conditions may change checkout totals.")}
