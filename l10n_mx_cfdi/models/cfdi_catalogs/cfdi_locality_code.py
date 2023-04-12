from odoo import api, fields, models


class CFDILocalityCode(models.Model):
    _name = "l10n_mx_cfdi.cfdi_locality_code"
    _description = "CFDI Locality Code (c_Localidad)"
    _inherit = "l10n_mx_cfdi.catalog_mixin"

    state_id = fields.Many2one(
        "res.country.state",
        "State",
        required=True,
    )

    border_zone_incentive = fields.Integer(
        "Border Zone Incentive",
        help="Border Zone Incentive",
    )
