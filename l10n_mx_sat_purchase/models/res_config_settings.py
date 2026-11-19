# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_mx_sat_purchase_match_mode = fields.Selection(
        related="company_id.l10n_mx_sat_purchase_match_mode", readonly=False
    )
    l10n_mx_sat_purchase_price_source = fields.Selection(
        related="company_id.l10n_mx_sat_purchase_price_source", readonly=False
    )
    l10n_mx_sat_purchase_learn_vendor_code = fields.Boolean(
        related="company_id.l10n_mx_sat_purchase_learn_vendor_code", readonly=False
    )
    l10n_mx_sat_purchase_total_tolerance = fields.Float(
        related="company_id.l10n_mx_sat_purchase_total_tolerance", readonly=False
    )
    l10n_mx_sat_purchase_price_tolerance = fields.Float(
        related="company_id.l10n_mx_sat_purchase_price_tolerance", readonly=False
    )
