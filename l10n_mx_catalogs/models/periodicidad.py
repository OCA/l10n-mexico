from odoo import models, fields


class Periodicidad(models.Model):
    _name = "l10n_mx_catalogs.c_periodicidad"
    _description = "Catalogo SAT de Periodicidad"

    code = fields.Char(string="Codigo", required=True)
    name = fields.Char(string="Nombre", required=True)
