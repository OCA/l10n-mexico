from odoo import models, fields


class FiguraTransporte(models.Model):
    _name = "l10n_mx_catalogs.c_figura_transporte"
    _description = "Catálogo Figura Transporte"
    _rec_name = "description"

    code = fields.Char(string="Código", required=True)
    description = fields.Char(string="Descripción", required=True)
