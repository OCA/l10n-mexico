from odoo import models


class CFDIType(models.Model):
    _name = "l10n_mx_cfdi.cfdi_type"
    _description = "CFDI Type (c_TipoDeComprobante)"
    _inherit = "l10n_mx_cfdi.catalog_mixin"
