from odoo import fields, models


class MetodoPago(models.Model):
    _name = "l10n_mx_catalogs.c_metodo_pago"
    _description = "Catalogo SAT de Metodos de pago"

    code = fields.Char(string="Codigo", required=True)
    name = fields.Char(string="Nombre", required=True)
