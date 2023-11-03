from odoo import api, fields, models


class CFDIPaymentMethod(models.Model):
    _name = "l10n_mx_cfdi.cfdi_payment_policy"
    _description = "CFDI Payment Policy"
    _inherit = "l10n_mx_cfdi.catalog_mixin"
    _l10n_mx_catalog_name = "c_MetodoPago"

    _l10n_mx_catalog_col_mapping = {
        "c_MetodoPago": "code",
        "Descripción": "description",
    }
