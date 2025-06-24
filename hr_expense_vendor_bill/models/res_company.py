from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    hr_expense_reimbursement_debit_account_id = fields.Many2one(
        'account.account',
        string='Cuenta débito reembolso empleado',
        domain=[('deprecated', '=', False)],
        help='Cuenta para el débito en la factura de reembolso al empleado',
    )
    hr_expense_reimbursement_credit_account_id = fields.Many2one(
        'account.account',
        string='Cuenta acreedores diversos – empleados',
        domain=[('deprecated', '=', False)],
        help='Cuenta para el crédito en la factura de reembolso al empleado',
    )
