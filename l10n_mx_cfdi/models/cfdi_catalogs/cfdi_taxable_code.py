from odoo import api, fields, models


class CfdiTaxableCode(models.Model):
    _name = "l10n_mx_cfdi.cfdi_taxable_code"
    _description = "CFDI Taxable Code (c_ObjetoImp)"
    _inherit = "l10n_mx_cfdi.catalog_mixin"
