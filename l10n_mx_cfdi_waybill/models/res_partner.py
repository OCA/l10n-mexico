from odoo import models, fields


class Partner(models.Model):
    _inherit = 'res.partner'

    l10n_mx_cfdi_waybill_driving_license = fields.Char(string='Licencia de Conducir')
