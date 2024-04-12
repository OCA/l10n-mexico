from odoo import models, fields, api


class ProductTemplate(models.Model):
    # Add CFDI required product code and measure unit to product template
    # reference: https://www.cfdi.org.mx/catalogos-de-cfdi/productos-y-servicios/

    _inherit = "product.template"

    l10n_mx_cfdi_product_code_id = fields.Many2one(
        "l10n_mx_catalogs.c_clave_prod_serv", string="Código de Producto"
    )

    l10n_mx_cfdi_product_measurement_unit_id = fields.Many2one(
        "l10n_mx_catalogs.c_clave_unidad", string="Unidad de Medida"
    )
