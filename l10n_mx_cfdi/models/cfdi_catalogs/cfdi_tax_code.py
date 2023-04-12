from odoo import fields, models, api


class CFDITaxCode(models.Model):
    _name = "l10n_mx_cfdi.cfdi_tax_code"
    _description = "CFDI Tax Code (c_Impuesto)"
    _inherit = "l10n_mx_cfdi.catalog_mixin"
    is_retention = fields.Boolean("Is Retention")
    is_carried = fields.Boolean("Is Carried")
