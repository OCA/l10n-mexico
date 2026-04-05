from unittest.mock import patch

from .common import CFDIAccountTestCommon


class TestAccountPartialReconcile(CFDIAccountTestCommon):
    def test_create_triggers_payment_cfdi(self):
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        self._create_published_invoice_cfdi(invoice)
        self.company.l10n_mx_cfdi_auto = True
        with self._mock_cfdi_publish():
            self._register_invoice_payment(invoice)
        payment = self.env["account.payment"].search(
            [("reconciled_invoice_ids", "in", invoice.ids)], limit=1
        )
        self.assertTrue(payment.related_cert_ids)

    def test_create_triggers_refund_cfdi(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        self._create_published_invoice_cfdi(invoice)
        refund = self._create_cfdi_invoice(move_type="out_refund")
        refund.action_post()
        self.company.l10n_mx_cfdi_auto = True
        with self._mock_cfdi_publish():
            register = (
                self.env["account.payment.register"]
                .with_context(active_model="account.move", active_ids=refund.ids)
                .create(
                    {
                        "amount": refund.amount_residual,
                        "payment_form_id": self.env.ref(
                            "l10n_mx_catalogs.c_forma_pago_03"
                        ).id,
                    }
                )
            )
            register._create_payments()
        self.assertTrue(
            refund.related_cert_ids.filtered_domain(
                [("type", "=", "E"), ("state", "=", "published")]
            )
        )

    def test_unlink_cancels_payment_cfdi(self):
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        self._create_published_invoice_cfdi(invoice)
        payment = self._register_invoice_payment(invoice)
        document = self._create_document(
            type="P",
            state="published",
            related_payment_id=payment.id,
            receiver_id=self.customer.id,
        )
        payment.related_cert_ids = [(4, document.id)]
        self.company.l10n_mx_cfdi_auto = True
        with patch.object(type(document), "cancel", return_value=None) as mocked:
            payment.move_id.line_ids.remove_move_reconcile()
        mocked.assert_called()

    def test_unlink_cancels_refund_cfdi(self):
        refund = self._create_cfdi_invoice(move_type="out_refund")
        refund.action_post()
        document = self._create_document(
            type="E",
            state="published",
            related_invoice_id=refund.id,
            receiver_id=self.customer.id,
        )
        refund.related_cert_ids = [(4, document.id)]
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        self._create_published_invoice_cfdi(invoice)
        payment = self._register_invoice_payment(refund)
        self.company.l10n_mx_cfdi_auto = True
        with patch.object(type(document), "cancel", return_value=None) as mocked:
            payment.move_id.line_ids.remove_move_reconcile()
        mocked.assert_called()
