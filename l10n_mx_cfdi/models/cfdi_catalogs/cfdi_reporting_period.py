from odoo import api, fields, models


class CFDIReportingPeriod(models.Model):
    _name = "l10n_mx_cfdi.cfdi_reporting_period"
    _description = "CFDI Reporting Period (c_Meses)"
    _inherit = "l10n_mx_cfdi.catalog_mixin"
