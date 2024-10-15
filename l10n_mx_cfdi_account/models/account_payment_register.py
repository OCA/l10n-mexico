from odoo import models, fields
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    payment_form_id = fields.Many2one(
        "l10n_mx_catalogs.c_forma_pago", string="Forma de Pago", required=True
    )

    def _init_payments(self, to_process, edit_mode=False):
        """
        Add payment for id to payments creation data
        """
        for entry in to_process:
            entry["create_vals"].update(
                {
                    "payment_form_id": self.payment_form_id.id,
                }
            )

        return super()._init_payments(to_process, edit_mode)

    def _create_payments(self):
        # Prevent partial payments on invoices with cfdi and payment method different of 'PPD'
        if self.payment_difference > 0:
            related_invoices = self.line_ids.move_id
            if any(
                invoice.cfdi_required and invoice.payment_method_id.code != "PPD"
                for invoice in related_invoices
            ):
                raise UserError(
                    "No se puede registrar un pago parcial sobre una factura con CFDI "
                    "y método de pago diferente a PPD"
                )

        return super()._create_payments()
