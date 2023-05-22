from odoo import api, fields, models


class CFDIMunicipalityCode(models.Model):
    _name = "l10n_mx_cfdi.cfdi_municipality_code"
    _description = "CFDI Municipality Code"
    _inherit = "l10n_mx_cfdi.catalog_mixin"
    _l10n_mx_catalog_name = "c_Municipio"

    state_id = fields.Many2one(
        "res.country.state",
        "State",
        required=True,
    )
