from odoo import models


class OrigenRecurso(models.Model):
    """SAT payroll catalog ``c_OrigenRecurso``."""

    _name = "l10n_mx_catalogs.c_origen_recurso"
    _inherit = "l10n_mx_catalogs.sat_nomina_catalog"
    _description = "Catálogo SAT del tipo de origen del recurso"
