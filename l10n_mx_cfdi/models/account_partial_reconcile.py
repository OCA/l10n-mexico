from odoo import models


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    def create(self, vals_list):
        """Create Payments and Credit Note CFDI if required"""

        res = super().create(vals_list)

        if self.env.company.l10n_mx_cfdi_auto:
            move_line_ids = res.debit_move_id | res.credit_move_id

            for move in move_line_ids.move_id:
                if move.move_type == "entry":
                    # create payment CFDI if required
                    payment = move.payment_id
                    payment_requires_cfdi = any(
                        invoice.cfdi_required
                        and invoice.payment_method_id.code == "PPD"
                        for invoice in payment.reconciled_invoice_ids
                    )

                    if (
                        payment.payment_type == "inbound"
                        and payment.is_reconciled
                        and payment_requires_cfdi
                    ):
                        payment.create_payment_cfdi()

                if move.move_type == "out_refund":
                    # create credit note CFDI if required
                    existent_cfdi = move.related_cert_ids.filtered_domain(
                        [("type", "=", "E"), ("state", "=", "published")]
                    )

                    if (
                        move.amount_residual == 0
                        and move.cfdi_required
                        and not existent_cfdi
                    ):
                        move.create_refund_cfdi()

        return res

    def unlink(self):
        """Cancel related Payments CFDI if any"""

        move_line_ids = self.debit_move_id | self.credit_move_id
        res = super().unlink()

        if self.env.company.l10n_mx_cfdi_auto:
            for move in move_line_ids.move_id:
                if move.move_type == "entry":
                    payment = move.payment_id
                    related_cfdi = payment.related_cert_ids.filtered_domain(
                        [("type", "=", "P"), ("state", "=", "published")]
                    )
                    if related_cfdi and not payment.is_reconciled:
                        payment.cancel_payment_cfdi()

                if move.move_type == "out_refund":
                    for cfdi in move.related_cert_ids:
                        if cfdi.state == "published" and cfdi.type == "E":
                            cfdi.cancel(
                                "02"
                            )  # cancel reason: 'Comprobantes emitidos con errores sin relación'

        return res
