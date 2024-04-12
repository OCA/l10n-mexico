from odoo import models, fields


class UsoCFDI(models.Model):
    _name = "l10n_mx_catalogs.c_uso_cfdi"
    _description = "Catalogo SAT de uso de CFDI"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Nombre", required=True)
    applies_to_natural_person = fields.Boolean(string="Aplica para persona física")
    applies_to_legal_person = fields.Boolean(string="Aplica para persona moral")

    applies_to_fiscal_regimes = fields.Char(string="Aplica para régimen fiscal")
