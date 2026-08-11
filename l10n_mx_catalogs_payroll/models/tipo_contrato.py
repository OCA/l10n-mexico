from odoo import models


class TipoContrato(models.Model):
    """SAT payroll catalog ``c_TipoContrato``."""

    _name = "l10n_mx_catalogs.c_tipo_contrato"
    _inherit = "l10n_mx_catalogs.sat_nomina_catalog"
    _description = "Catálogo SAT de tipos de contrato"
