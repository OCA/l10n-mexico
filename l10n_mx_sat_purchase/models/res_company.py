# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models

# A plain list, not a callable, so the options are translated on each field
MATCH_MODES = [("document", "Whole CFDI"), ("line", "By lines")]


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_mx_sat_purchase_match_mode = fields.Selection(
        selection=MATCH_MODES,
        string="Match SAT CFDIs with Purchase Orders",
        default="document",
        required=True,
        help="Whole CFDI: the bill takes everything pending to bill in the "
        "purchase orders.\nBy lines: each line of the CFDI is matched with the "
        "purchase order lines it bills, with its quantity.\n"
        "A vendor can have its own value, and it can be changed when billing.",
    )
    l10n_mx_sat_purchase_price_source = fields.Selection(
        selection=[
            ("cfdi", "CFDI"),
            ("order", "Purchase order"),
        ],
        string="Price of Bills Matched by Lines",
        default="cfdi",
        required=True,
        help="Unit price of the bill lines when a CFDI is matched by lines "
        "with purchase orders.",
    )
    l10n_mx_sat_purchase_learn_vendor_code = fields.Boolean(
        string="Learn Vendor Product Codes from SAT CFDIs",
        default=True,
        help="When a line of a CFDI is matched by hand with a purchase order "
        "line, keep its code in the vendor pricelist of the product so the "
        "next CFDI with that code is matched alone.",
    )
    l10n_mx_sat_purchase_total_tolerance = fields.Float(
        string="SAT CFDI Total Tolerance",
        default=1.0,
        help="A CFDI is proposed for the purchase orders when its total differs "
        "from theirs by this amount at most.",
    )
    l10n_mx_sat_purchase_price_tolerance = fields.Float(
        string="SAT CFDI Price Tolerance (%)",
        default=1.0,
        help="A line of a CFDI is highlighted when its unit price differs from "
        "the one of the purchase order line by more than this percentage.",
    )
