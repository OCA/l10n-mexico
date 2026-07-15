from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    l10n_mx_cfdi_tariff_code = fields.Many2one(
        "l10n_mx_catalogs.c_fraccion",
        string="Tariff Code",
        help=(
            "Tariff code for product template according to the SAT catalog "
            "for Mexican regulations compliance."
        ),
    )
