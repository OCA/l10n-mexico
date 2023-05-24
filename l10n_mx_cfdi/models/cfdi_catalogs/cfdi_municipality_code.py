from odoo import api, fields, models


class CFDIMunicipalityCode(models.Model):
    _name = "l10n_mx_cfdi.cfdi_municipality_code"
    _description = "CFDI Municipality Code"
    _inherit = "l10n_mx_cfdi.catalog_mixin"
    _l10n_mx_catalog_name = "C_Municipio"
    _l10n_mx_catalog_col_mapping = {
        "c_Municipio": "code",
        "Descripción": "description",
        "c_Estado": "state_id",
    }

    state_id = fields.Many2one(
        "res.country.state",
        "State",
        required=True,
    )
