from odoo import api, fields, models


class CFDIMunicipalityCode(models.Model):
    _name = "l10n_mx_cfdi.cfdi_municipality_code"
    _description = "CFDI Municipality Code (c_Municipio)"
    _inherit = "l10n_mx_cfdi.catalog_mixin"

    state_id = fields.Many2one(
        "res.country.state",
        "State",
        required=True,
    )
