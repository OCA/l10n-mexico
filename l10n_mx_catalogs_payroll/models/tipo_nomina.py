from odoo import models


class TipoNomina(models.Model):
    """SAT payroll catalog ``c_TipoNomina``."""

    _name = "l10n_mx_catalogs.c_tipo_nomina"
    _inherit = "l10n_mx_catalogs.sat_nomina_catalog"
    _description = "Catálogo SAT de tipos de nómina"
