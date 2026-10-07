# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models

from .res_company import MATCH_MODES


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_mx_sat_purchase_match_mode = fields.Selection(
        selection=MATCH_MODES,
        string="Match SAT CFDIs",
        company_dependent=True,
        help="How the CFDIs of this vendor are matched with its purchase "
        "orders. Leave it empty to use the value of the company.",
    )
