from odoo import models


class TipoRegimen(models.Model):
    """SAT payroll catalog ``c_TipoRegimen``."""

    _name = "l10n_mx_catalogs.c_tipo_regimen"
    _inherit = "l10n_mx_catalogs.sat_nomina_catalog"
    _description = "Catálogo SAT de tipos de régimen de contratación"
