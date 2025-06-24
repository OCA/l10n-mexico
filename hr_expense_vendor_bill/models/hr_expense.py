from odoo import models, fields

class HrExpense(models.Model):
    _inherit = 'hr.expense'

    vendor_id = fields.Many2one(
        'res.partner', string="Proveedor",
        help="Proveedor del cual proviene este gasto.",
    )