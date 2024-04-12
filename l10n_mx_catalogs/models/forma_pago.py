from odoo import models, fields


class FormaPago(models.Model):
    _name = "l10n_mx_catalogs.c_forma_pago"
    _description = "Catalogo SAT de Formas de Pago"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Nombre", required=True)
