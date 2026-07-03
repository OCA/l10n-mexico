from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    l10n_mx_cfdi_dangerous_material_indicator = fields.Boolean(
        string="Indicador de material peligroso CFDI", default=False
    )
    l10n_mx_cfid_dangerous_material_code = fields.Char(
        string="Código de material Peligroso"
    )
