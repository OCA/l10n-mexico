from odoo import api, fields, models


class CFDIExportType(models.Model):
    _name = "l10n_mx_cfdi.cfdi_export_type"
    _description = "CFDI Export Type (c_Exportacion)"
    _inherit = "l10n_mx_cfdi.catalog_mixin"
