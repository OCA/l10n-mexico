from odoo import models, fields


class ParteTransporte(models.Model):
    _name = "l10n_mx_catalogs.c_parte_transporte"
    _description = "Catálogo Parte Transporte"
    _rec_name = "description"

    code = fields.Char(string="Código", required=True)
    description = fields.Char(string="Descripción", required=True)
