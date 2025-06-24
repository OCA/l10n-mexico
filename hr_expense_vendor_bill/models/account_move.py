from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

    expense_sheet_id = fields.Many2one(
        'hr.expense.sheet', string="Reporte de Gastos",
        help="Hoja de gastos de la que se originó esta factura de proveedor.",
        ondelete='set null'
    )

    is_employee_reimbursement = fields.Boolean(
        string="Reembolso de empleado",
        default=False,
        help="Marca las facturas creadas por hr_expense_vendor_bill"
    )

    def _compute_payment_state(self):
        super()._compute_payment_state()

        reembolsos = self.filtered(lambda m: m.is_employee_reimbursement)
        for move in reembolsos:
            move.payment_state = 'not_paid'
