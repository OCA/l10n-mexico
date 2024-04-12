from odoo import models, fields


class Meses(models.Model):
    _name = "l10n_mx_catalogs.c_meses"
    _description = "Catalogo Sat Meses"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Nombre", required=True)
