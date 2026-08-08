from odoo import models


class TipoOtroPago(models.Model):
    """SAT payroll catalog ``c_TipoOtroPago``."""

    _name = "l10n_mx_catalogs.c_tipo_otro_pago"
    _inherit = "l10n_mx_catalogs.sat_nomina_catalog"
    _description = "Catálogo SAT de otros tipos de pago"
