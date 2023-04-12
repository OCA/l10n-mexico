from odoo import api, fields, models


class CFDIPaymentMethod(models.Model):
    _name = "l10n_mx_cfdi.cfdi_payment_method"
    _description = "CFDI Payment Method (c_MetodoPago)"
    _inherit = "l10n_mx_cfdi.catalog_mixin"
