from odoo import api, fields, models


class CfdiTaxableCode(models.Model):
    _name = "l10n_mx_cfdi.cfdi_taxable_code"
    _description = "CFDI Taxable Code"
    _inherit = "l10n_mx_cfdi.catalog_mixin"
    _l10n_mx_catalog_name = "c_ObjetoImp"
