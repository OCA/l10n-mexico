from odoo import api, fields, models


class ResCountry(models.Model):
    """ Add CFDI fields to res.country """

    _inherit = "res.country"
    _l10n_mx_catalog_name = "c_Pais"

    l10n_mx_cfdi_code = fields.Char(
        "CFDI Code",
        help="Code used in CFDI documents",
    )

    l10n_mx_cfdi_zip_code_format = fields.Char(
        "CFDI Zip Code Format",
        help="Format of the zip code used in CFDI documents",
    )


class ResCountryState(models.Model):
    """ Add CFDI fields to res.country.state """

    _inherit = "res.country.state"
    _l10n_mx_catalog_name = "c_Estado"

    l10n_mx_cfdi_code = fields.Char(
        "CFDI Code",
        help="Code used in CFDI documents",
    )
