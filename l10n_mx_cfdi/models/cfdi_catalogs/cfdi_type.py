from odoo import models, fields


class CFDIType(models.Model):
    _name = "l10n_mx_cfdi.cfdi_type"
    _description = "CFDI Type"
    _inherit = "l10n_mx_cfdi.catalog_mixin"
    _l10n_mx_catalog_name = "c_TipoDeComprobante"
    _l10n_mx_catalog_col_mapping = {
        "c_TipoDeComprobante": "code",
        "Descripción": "description",
    }
