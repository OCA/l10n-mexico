from odoo import api, fields, models


class CFDIPaymentWay(models.Model):
    _name = "l10n_mx_cfdi.cfdi_payment_way"
    _description = "CFDI Payment Way"
    _inherit = "l10n_mx_cfdi.catalog_mixin"
    _l10n_mx_catalog_name = "c_FormaPago"

    _l10n_mx_catalog_col_mapping = {
        "c_FormaPago": "code",
        "Descripción": "description",
    }
