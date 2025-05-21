from odoo import fields, models


class Colonia(models.Model):
    _name = "l10n_mx_catalogs.c_colonia"
    _description = "Catálogo SAT Colonia"

    name = fields.Char(required=True)
    code = fields.Char(size=5, required=True)
    zip = fields.Char(size=5, required=True)
