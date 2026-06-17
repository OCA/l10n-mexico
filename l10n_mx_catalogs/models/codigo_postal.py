from odoo import fields, models


class CodigoPostal(models.Model):
    _name = "l10n_mx_catalogs.c_codigo_postal"
    _description = "Catálogo de Codigo Postal de México (SAT)"
    _rec_name = "code"

    code = fields.Char(string="Código Postal", size=5, required=True)
    state_code = fields.Char(string="Código de Estado", size=3, required=True)
    municipality_code = fields.Char(string="Código de Municipio", size=4)
    locality_code = fields.Char(string="Código de Localidad", size=4)
