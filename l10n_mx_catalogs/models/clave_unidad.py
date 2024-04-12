from odoo import fields, models


class ClaveUnidad(models.Model):
    _name = "l10n_mx_catalogs.c_clave_unidad"
    _description = "Catálogo SAT Clave Unidad"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Nombre", required=True)
    description = fields.Char(string="Descripción")
    symbol = fields.Char(string="Símbolo")
