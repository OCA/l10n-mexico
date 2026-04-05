from unittest.mock import PropertyMock, patch

from odoo.exceptions import ValidationError

from .common import CFDIAccountTestCommon


class TestAccountPayment(CFDIAccountTestCommon):
    def test_action_generate_cfdi_with_existing_cfdi(self):
        payment = self.env["account.payment"].new(
            {
                "payment_type": "inbound",
                "is_reconciled": True,
            }
        )
        document = self._create_document(type="P", state="published")
        with (
            patch.object(
                type(payment),
                "cfdi_document_id",
                new_callable=PropertyMock,
                return_value=document,
            ),
            self.assertRaises(ValidationError),
        ):
            payment.action_generate_cfdi()

    def test_action_generate_cfdi_not_reconciled(self):
        payment = self.env["account.payment"].new(
            {
                "payment_type": "inbound",
                "is_reconciled": False,
            }
        )
        with (
            patch.object(
                type(payment),
                "cfdi_document_id",
                new_callable=PropertyMock,
                return_value=False,
            ),
            self.assertRaises(ValidationError),
        ):
            payment.action_generate_cfdi()

    def test_create_payment_cfdi_outbound_raises(self):
        payment = self.env["account.payment"].new({"payment_type": "outbound"})
        with self.assertRaises(ValidationError):
            payment.create_payment_cfdi()

    def test_prepare_payment_cfdi_missing_invoice_cfdi(self):
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        payment = self._register_invoice_payment(invoice)
        with self.assertRaises(ValidationError):
            payment.prepare_payment_cfdi()

    def test_create_payment_cfdi_success(self):
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        self._create_published_invoice_cfdi(invoice)
        payment = self._register_invoice_payment(invoice)
        with self._mock_cfdi_publish():
            payment.create_payment_cfdi()
        self.assertTrue(payment.related_cert_ids)
        self.assertEqual(payment.cfdi_use_id.code, "CP01")

    def test_create_payment_cfdi_publico_en_general(self):
        public_partner = self.env.ref(
            "l10n_mx_cfdi.l10n_mx_cfdi_res_partner_publico_en_general"
        )
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                partner_id=public_partner.id,
                receiver_id=public_partner.id,
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id,
            )
        )
        self._create_published_invoice_cfdi(invoice)
        payment = self._register_invoice_payment(invoice)
        with self._mock_cfdi_publish():
            payment.create_payment_cfdi()
        self.assertTrue(payment.related_cert_ids)

    def test_create_payment_cfdi_legacy_receiver(self):
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                receiver_id=False,
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id,
            )
        )
        document = self._create_published_invoice_cfdi(invoice)
        document.receiver_id = self.customer
        payment = self._register_invoice_payment(invoice)
        with self._mock_cfdi_publish():
            payment.create_payment_cfdi()
        self.assertTrue(payment.related_cert_ids)

    def test_compute_taxes(self):
        self.cfdi_product.taxes_id = [(6, 0, [self._iva_tax().id])]
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        payment = self._register_invoice_payment(invoice)
        taxes = payment._compute_taxes(invoice.amount_total, invoice)
        self.assertTrue(taxes)

    def test_cancel_payment_cfdi(self):
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
        with patch.object(type(document), "cancel", return_value=None):
            payment.cancel_payment_cfdi()

    def test_action_generate_cfdi_inbound_success(self):
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        self._create_published_invoice_cfdi(invoice)
        payment = self._register_invoice_payment(invoice)
        with self._mock_cfdi_publish():
            payment.action_generate_cfdi()
        self.assertTrue(payment.related_cert_ids)

    def test_create_payment_cfdi_failure_unlinks_document(self):
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        self._create_published_invoice_cfdi(invoice)
        payment = self._register_invoice_payment(invoice)
        with (
            patch.object(
                type(self.service),
                "create_cfdi",
                side_effect=ValidationError("publish failed"),
            ),
            self.assertRaises(ValidationError),
        ):
            payment.create_payment_cfdi()
        self.assertFalse(payment.related_cert_ids)
