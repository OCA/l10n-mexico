from odoo import api, fields, models


class CFDIFrequency(models.Model):
    _name = "l10n_mx_cfdi.cfdi_frequency"
    _description = "CFDI Frequency"
    _inherit = "l10n_mx_cfdi.catalog_mixin"
    _l10n_mx_catalog_name = "c_Periodicidad"
