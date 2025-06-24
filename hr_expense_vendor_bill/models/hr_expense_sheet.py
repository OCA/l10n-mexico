from collections import defaultdict

from odoo import _, fields, models
from odoo.exceptions import UserError


class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    def _create_supplier_invoices(self):
        invoices = self.env["account.move"]
        for sheet in self:
            # Agrupar gastos por proveedor
            expenses_by_supplier = defaultdict(list)
            for exp in sheet.expense_line_ids:
                if exp.vendor_id:
                    expenses_by_supplier[exp.vendor_id].append(exp)

            # Para cada proveedor, generar una factura
            for supplier, expenses in expenses_by_supplier.items():
                inv_date = fields.Date.context_today(self)
                invoice_lines = []

                for exp in expenses:
                    # Calcular precio sin impuestos (subtotal) y asignar impuestos
                    net_amount = exp.total_amount - exp.tax_amount
                    invoice_lines.append(
                        (
                            0,
                            0,
                            {
                                "name": exp.name or _("Gasto de %s") % supplier.name,
                                "account_id": exp.account_id.id,
                                "quantity": 1.0,
                                "price_unit": net_amount,
                                "tax_ids": [(6, 0, exp.tax_ids.ids)],
                            },
                        )
                    )

                # Encabezado de la factura de proveedor
                inv_vals = {
                    "move_type": "in_invoice",
                    "partner_id": supplier.id,
                    "invoice_date": inv_date,
                    "invoice_date_due": inv_date,
                    "journal_id": sheet.journal_id.id,
                    "ref": _("Gastos %s") % sheet.name,
                    "expense_sheet_id": sheet.id,
                    "invoice_line_ids": invoice_lines,
                }
                invoice = self.env["account.move"].create(inv_vals)
                invoices |= invoice

        # Asignar fecha de vencimiento a la línea de cuenta por pagar antes de validar
        for invoice in invoices:
            for line in invoice.line_ids:
                if line.account_id.internal_group == "liability_payable":
                    line.date_maturity = invoice.invoice_date_due
            invoice.action_post()
        return invoices

    def _generate_supplier_payments(self):
        PaymentRegister = self.env["account.payment.register"]

        # Selección de diario de pagos "Pagos del empleado"
        pay_journal = self.env["account.journal"].search(
            [("type", "=", "bank"), ("name", "ilike", "Pagos del empleado")], limit=1
        ) or self.env["account.journal"].search([("type", "=", "bank")], limit=1)
        if not pay_journal:
            raise UserError(
                _(
                    "Debe configurar al menos un diario bancario "
                    "para registrar pagos de proveedores."
                )
            )

        # Elegir o crear un método de pago de salida (outbound)
        if pay_journal.outbound_payment_method_line_ids:
            pm_line = pay_journal.outbound_payment_method_line_ids[:1]
        else:
            manual = self.env.ref(
                "account.account_payment_method_manual_out", raise_if_not_found=False
            )
            if not manual:
                raise UserError(
                    _(
                        "El diario '%s' no tiene método de pago"
                        " y no existe el método manual."
                    )
                    % pay_journal.name
                )
            pm_line = self.env["account.payment.method.line"].create(
                {
                    "journal_id": pay_journal.id,
                    "payment_method_id": manual.id,
                    "payment_type": "outbound",
                    "code": manual.code or "manual",
                    "name": manual.name or _("Manual"),
                }
            )

        # Para cada factura in_invoice posteada y no pagada, lanzar el wizard de pago
        for sheet in self:
            for invoice in sheet.account_move_ids.filtered(
                lambda m: m.move_type == "in_invoice"
                and m.state == "posted"
                and m.payment_state != "paid"
            ):
                context = {
                    "active_model": "account.move",
                    "active_ids": [invoice.id],
                    "active_id": invoice.id,
                }
                wizard = PaymentRegister.with_context(**context).create(
                    {
                        "journal_id": pay_journal.id,
                        "payment_method_line_id": pm_line.id,
                        "amount": invoice.amount_residual,
                        "payment_date": fields.Date.context_today(self),
                    }
                )
                wizard.action_create_payments()

    def _create_employee_reimbursement_invoice(self):
        AccountMove = self.env["account.move"]
        invoices = self.env["account.move"]

        company = self.company_id
        acc_debit = company.hr_expense_reimbursement_debit_account_id
        acc_credit = company.hr_expense_reimbursement_credit_account_id
        if not acc_debit or not acc_credit:
            raise UserError(
                _(
                    "Debes configurar en Ajustes → Empresas "
                    "las cuentas de débito y crédito para el reembolso de empleados."
                )
            )

        for sheet in self:
            total_amount = sum(exp.total_amount for exp in sheet.expense_line_ids)
            if total_amount <= 0:
                continue

            partner = sheet.employee_id.sudo().work_contact_id
            if not partner:
                raise UserError(
                    _("El empleado %s no tiene un contacto laboral configurado.")
                    % sheet.employee_id.name
                )
            partner = partner.with_company(sheet.company_id)

            inv_date = fields.Date.context_today(sheet)

            journal = sheet.journal_id
            if not journal:
                raise UserError(_("No se ha definido un diario en la hoja de gastos."))

            invoice_lines = [
                (
                    0,
                    0,
                    {
                        "name": _("Reembolso de gastos"),
                        "account_id": acc_debit.id,
                        "quantity": 1.0,
                        "price_unit": total_amount,
                        "tax_ids": [],
                    },
                )
            ]

            move_vals = {
                "move_type": "in_invoice",
                "partner_id": partner.id,
                "invoice_date": inv_date,
                "invoice_date_due": inv_date,
                "ref": _("Reembolso %s") % sheet.name,
                "journal_id": journal.id,
                "invoice_line_ids": invoice_lines,
            }

            move = AccountMove.create(move_vals)
            move.action_post()
            sheet.write({"account_move_ids": [(4, move.id)]})
            invoices |= move

        return invoices

    def _reconcile_account_lines(self):
        # Wzard de conciliación automática
        ReconcileWizard = self.env["account.reconcile.wizard"]

        for sheet in self:
            account = sheet.company_id.hr_expense_reimbursement_credit_account_id
            if not account:
                raise UserError(
                    _(
                        "Debes configurar en Contabilidad → Configuración → Empresas "
                        "la cuenta para poder conciliar."
                    )
                )
            # Busca las líneas contables de la cuenta en los movimientos del sheet
            move_lines = self.env["account.move.line"].search(
                [
                    ("move_id", "in", sheet.account_move_ids.ids),
                    ("account_id", "=", account.id),
                ]
            )
            if len(move_lines) >= 2:
                context = {
                    "active_model": "account.move.line",
                    "active_ids": move_lines.ids,
                    "allow_partials": True,
                }
                wizard = ReconcileWizard.with_context(**context).new(
                    {"allow_partials": True}
                )
                wizard.reconcile()

    def action_approve_expense_sheets(self):
        # Método original para aprobar hojas de gasto
        res = super().action_approve_expense_sheets()

        for sheet in self:
            moves = sheet.account_move_ids.sudo()
            for move in moves:
                if move.state == "posted":
                    move.sudo().button_cancel()
                    move.sudo().button_draft()
                elif move.state == "cancel":
                    move.sudo().button_draft()
            moves.unlink()
            sheet.sudo().write({"account_move_ids": [(5, 0, 0)]})

        # Ejecución del flujo completo de gastos
        self._create_supplier_invoices()
        self._generate_supplier_payments()
        self._create_employee_reimbursement_invoice()
        self._reconcile_account_lines()

        return res

    def action_open_account_moves(self):
        self.ensure_one()
        # Prepara la acción para mostrar los movimientos contables relacionados
        action = {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "views": [(False, "list"), (False, "form")],
            "domain": [("id", "in", self.account_move_ids.ids)],
            "context": {"default_expense_sheet_id": self.id},
        }
        # Si solo hay un movimiento, abre directamente el formulario
        if len(self.account_move_ids) == 1:
            action.update(
                {
                    "view_mode": "form",
                    "res_id": self.account_move_ids.id,
                }
            )
        return action
