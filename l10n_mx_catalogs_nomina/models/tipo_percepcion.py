from odoo import models


class TipoPercepcion(models.Model):
    """SAT payroll catalog ``c_TipoPercepcion``."""

    _name = "l10n_mx_catalogs.c_tipo_percepcion"
    _inherit = "l10n_mx_catalogs.sat_nomina_catalog"
    _description = "Catálogo SAT de tipos de percepción"
