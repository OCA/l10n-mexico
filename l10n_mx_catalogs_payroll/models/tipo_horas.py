from odoo import models


class TipoHoras(models.Model):
    """SAT payroll catalog ``c_TipoHoras``."""

    _name = "l10n_mx_catalogs.c_tipo_horas"
    _inherit = "l10n_mx_catalogs.sat_nomina_catalog"
    _description = "Catálogo SAT de tipos de hora extra"
