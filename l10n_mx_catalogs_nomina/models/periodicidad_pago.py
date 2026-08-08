from odoo import models


class PeriodicidadPago(models.Model):
    """SAT payroll catalog ``c_PeriodicidadPago``."""

    _name = "l10n_mx_catalogs.c_periodicidad_pago"
    _inherit = "l10n_mx_catalogs.sat_nomina_catalog"
    _description = "Catálogo SAT de periodicidad del pago"
