from odoo import models


class TipoIncapacidad(models.Model):
    """SAT payroll catalog ``c_TipoIncapacidad``."""

    _name = "l10n_mx_catalogs.c_tipo_incapacidad"
    _inherit = "l10n_mx_catalogs.sat_nomina_catalog"
    _description = "Catálogo SAT de tipos de incapacidad"
