from odoo import models


class RiesgoPuesto(models.Model):
    """SAT payroll catalog ``c_RiesgoPuesto``."""

    _name = "l10n_mx_catalogs.c_riesgo_puesto"
    _inherit = "l10n_mx_catalogs.sat_nomina_catalog"
    _description = "Catálogo SAT de clases de riesgo de puesto"
