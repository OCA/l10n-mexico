from odoo import api, fields, models


class CfdiDistrictCode(models.Model):
    _name = "l10n_mx_cfdi.cfdi_district_code"
    _description = "CFDI District Code (c_Colonia)"
    _inherit = "l10n_mx_cfdi.catalog_mixin"

    zip_code = fields.Char(
        string="Zip",
        required=True,
    )
