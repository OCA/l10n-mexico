from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    hr_expense_reimbursement_debit_account_id = fields.Many2one(
        'account.account',
        related='company_id.hr_expense_reimbursement_debit_account_id',
        string='Cuenta débito reembolso empleado',
        readonly=False,
    )
    hr_expense_reimbursement_credit_account_id = fields.Many2one(
        'account.account',
        related='company_id.hr_expense_reimbursement_credit_account_id',
        string='Cuenta acreedores diversos – empleados',
        readonly=False,
    )
