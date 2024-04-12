from odoo import fields, models


class RegimenFiscal(models.Model):
    _name = "l10n_mx_catalogs.c_regimen_fiscal"
    _description = "Catálogo Regimen Fiscal"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Nombre", required=True)
    applies_to_natural_person = fields.Boolean(string="Aplica para persona física")
    applies_to_legal_person = fields.Boolean(string="Aplica para persona moral")
