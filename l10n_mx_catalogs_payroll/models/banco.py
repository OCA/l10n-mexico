from odoo import fields, models


class Banco(models.Model):
    """SAT payroll catalog ``c_Banco``."""

    _name = "l10n_mx_catalogs.c_banco"
    _inherit = "l10n_mx_catalogs.sat_nomina_catalog"
    _description = "Catálogo SAT de bancos"

    legal_name = fields.Char(string="Nombre o razón social")
