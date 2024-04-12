from odoo import fields, models


class Colonia(models.Model):
    _name = "l10n_mx_catalogs.c_colonia"
    _description = "Catálogo SAT Colonia"

    name = fields.Char("Name", required=True)
    code = fields.Char("Code", size=5, required=True)
    zip = fields.Char("Zip", size=5, required=True)
