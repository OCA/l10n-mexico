from odoo import api, fields, models


class CFDIUse(models.Model):
    _name = "l10n_mx_cfdi.cfdi_use"
    _description = "CFDI Use (c_UsoCFDI)"
    _inherit = "l10n_mx_cfdi.catalog_mixin"

    similar_terms = fields.Char("Similar Terms")

    applicable_to_natural_person = fields.Boolean("Applicable to Natural Person")
    applicable_to_legal_entity = fields.Boolean("Applicable to Legal Entity")

    tax_regime_ids = fields.Many2many(
        "l10n_mx_cfdi.cfdi_tax_regime",
        "l10n_mx_cfdi_cfdi_use_tax_regime_rel",
        "Applicable to Tax Regimes",
    )

    border_zone_incentive = fields.Integer("Border Zone Incentive")
