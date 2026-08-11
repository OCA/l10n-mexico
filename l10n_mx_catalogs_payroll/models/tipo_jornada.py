from odoo import models


class TipoJornada(models.Model):
    """SAT payroll catalog ``c_TipoJornada``."""

    _name = "l10n_mx_catalogs.c_tipo_jornada"
    _inherit = "l10n_mx_catalogs.sat_nomina_catalog"
    _description = "Catálogo SAT de tipos de jornada laboral"
