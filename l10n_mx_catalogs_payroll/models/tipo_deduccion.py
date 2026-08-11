from odoo import models


class TipoDeduccion(models.Model):
    """SAT payroll catalog ``c_TipoDeduccion``."""

    _name = "l10n_mx_catalogs.c_tipo_deduccion"
    _inherit = "l10n_mx_catalogs.sat_nomina_catalog"
    _description = "Catálogo SAT de tipos de deducción"
