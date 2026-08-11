from datetime import date
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError, ValidationError

from .common import CFDIAccountTestCommon


class TestDocumentCancelWizard(CFDIAccountTestCommon):
    def test_default_get_from_invoice(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        document = self._create_published_invoice_cfdi(invoice)
        wizard_model = self.env["l10n_mx_cfdi_account.document_cancel"]
        defaults = wizard_model.with_context(
            active_model="account.move",
            active_ids=invoice.ids,
        ).default_get(["certificate_ids", "related_invoices", "cancel_reason_id"])
        self.assertIn(document, defaults["certificate_ids"])
        self.assertEqual(defaults["related_invoices"], invoice)

    def test_requires_replacement_for_reason_01(self):
        wizard = self.env["l10n_mx_cfdi_account.document_cancel"].new(
            {
                "cancel_reason_id": self.env.ref(
                    "l10n_mx_catalogs.c_motivo_cancelacion_01"
                ).id,
            }
        )
        wizard._compute_requires_replacement()
        self.assertTrue(wizard.requires_replacement)

    def test_cancel_certificate(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        document = self._create_published_invoice_cfdi(invoice)
        wizard = self.env["l10n_mx_cfdi_account.document_cancel"].create(
            {
                "certificate_ids": [(6, 0, document.ids)],
                "cancel_reason_id": self.env.ref(
                    "l10n_mx_catalogs.c_motivo_cancelacion_02"
                ).id,
                "simulate_operation": True,
            }
        )
        action = wizard.cancel_certificate()
        self.assertEqual(document.state, "canceled")
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "display_notification")
        self.assertIn("cancellation", action["params"]["message"].lower())

    def test_cancel_certificate_with_auto_draft(self):
        self.company.l10n_mx_cfdi_auto = True
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        document = self._create_published_invoice_cfdi(invoice)
        wizard = self.env["l10n_mx_cfdi_account.document_cancel"].create(
            {
                "certificate_ids": [(6, 0, document.ids)],
                "cancel_reason_id": self.env.ref(
                    "l10n_mx_catalogs.c_motivo_cancelacion_02"
                ).id,
                "simulate_operation": True,
            }
        )
        with patch.object(type(invoice), "button_draft", return_value=True):
            wizard.cancel_certificate()

    def test_cancel_certificate_payment_document(self):
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        payment = self._register_invoice_payment(invoice)
        document = self._create_document(
            type="P",
            state="published",
            related_payment_id=payment.id,
            receiver_id=self.customer.id,
        )
        wizard = self.env["l10n_mx_cfdi_account.document_cancel"].create(
            {
                "certificate_ids": [(6, 0, document.ids)],
                "cancel_reason_id": self.env.ref(
                    "l10n_mx_catalogs.c_motivo_cancelacion_02"
                ).id,
                "simulate_operation": True,
            }
        )
        wizard.cancel_certificate()
        self.assertEqual(document.state, "canceled")

    def test_cancel_certificate_no_published_document(self):
        document = self._create_document(state="draft", receiver_id=self.customer.id)
        wizard = self.env["l10n_mx_cfdi_account.document_cancel"].create(
            {
                "certificate_ids": [(6, 0, document.ids)],
                "cancel_reason_id": self.env.ref(
                    "l10n_mx_catalogs.c_motivo_cancelacion_02"
                ).id,
                "simulate_operation": True,
            }
        )
        action = wizard.cancel_certificate()
        self.assertEqual(action["params"]["type"], "warning")
        self.assertIn("No published CFDI", action["params"]["message"])


class TestGenericInvoiceCreateWizard(CFDIAccountTestCommon):
    def _create_wizard(self, invoices):
        return (
            self.env["l10n_mx_cfdi_account.generic_invoice_create"]
            .with_context(active_model="account.move", active_ids=invoices.ids)
            .create(
                {
                    "issuer_id": self.issuer.id,
                    "periodicity_id": self.env.ref(
                        "l10n_mx_catalogs.c_periodicidad_01"
                    ).id,
                    "meses_id": self.env.ref("l10n_mx_catalogs.c_meses_01").id,
                    "year": "2026",
                    "date": fields.Date.today(),
                    "move_ids": [(6, 0, invoices.ids)],
                }
            )
        )

    def test_default_get(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        defaults = (
            self.env["l10n_mx_cfdi_account.generic_invoice_create"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .default_get(["move_ids", "year", "cfdi_use_id"])
        )
        self.assertEqual(defaults["move_ids"], invoice)
        self.assertTrue(defaults["year"])
        self.assertEqual(
            defaults["cfdi_use_id"],
            self.env.ref("l10n_mx_catalogs.c_uso_cfdi_S01").id,
        )

    def test_validate_invoice_not_posted(self):
        invoice = self._create_cfdi_invoice()
        with self.assertRaises(ValidationError):
            self.env["l10n_mx_cfdi_account.generic_invoice_create"]._validate_invoice(
                invoice
            )

    def test_validate_invoice_items_error(self):
        product = self.env["product.product"].create(
            {"name": "No CFDI Codes", "list_price": 10.0}
        )
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                invoice_line_ids=[
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "quantity": 1,
                            "price_unit": 10.0,
                        },
                    )
                ]
            )
        )
        with self.assertRaises(ValidationError) as err:
            self.env["l10n_mx_cfdi_account.generic_invoice_create"]._validate_invoice(
                invoice
            )
        self.assertIn("No CFDI Codes", str(err.exception))

    def test_validate_invoice_with_published_cfdi(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        self._create_published_invoice_cfdi(invoice)
        with self.assertRaises(ValidationError):
            self.env["l10n_mx_cfdi_account.generic_invoice_create"]._validate_invoice(
                invoice
            )

    def test_compute_fiscal_regime_bimestral(self):
        wizard = self.env["l10n_mx_cfdi_account.generic_invoice_create"].new(
            {
                "periodicity_id": self.env.ref("l10n_mx_catalogs.c_periodicidad_05").id,
            }
        )
        wizard._compute_fiscal_regime_id()
        self.assertEqual(
            wizard.fiscal_regime_id,
            self.env.ref("l10n_mx_catalogs.c_regimen_fiscal_621"),
        )

    def test_compute_folio_periodicities(self):
        wizard_model = self.env["l10n_mx_cfdi_account.generic_invoice_create"]
        test_date = date(2026, 6, 20)
        cases = [
            ("c_periodicidad_01", test_date.strftime("%Y%m%d")),
            ("c_periodicidad_02", test_date.strftime("%Y%W")),
            ("c_periodicidad_03", test_date.strftime("%Y%m") + "2"),
            ("c_periodicidad_04", test_date.strftime("%Y%m")),
            ("c_periodicidad_05", test_date.strftime("%Y") + "3"),
        ]
        # Quincenal first half of month (day <= 15)
        wizard_q1 = wizard_model.new(
            {
                "periodicity_id": self.env.ref("l10n_mx_catalogs.c_periodicidad_03").id,
                "date": date(2026, 6, 10),
            }
        )
        self.assertEqual(wizard_q1._compute_folio(), "2026061")
        for periodicity_xmlid, expected in cases:
            wizard = wizard_model.new(
                {
                    "periodicity_id": self.env.ref(
                        f"l10n_mx_catalogs.{periodicity_xmlid}"
                    ).id,
                    "date": test_date,
                }
            )
            self.assertEqual(wizard._compute_folio(), expected)

    def test_create_cfdi(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        wizard = self._create_wizard(invoice)
        with self._mock_cfdi_publish():
            wizard.create_cfdi()
        self.assertTrue(invoice.related_cert_ids)

    def test_compute_fiscal_regime_default(self):
        wizard = self.env["l10n_mx_cfdi_account.generic_invoice_create"].new(
            {
                "periodicity_id": self.env.ref("l10n_mx_catalogs.c_periodicidad_01").id,
            }
        )
        wizard._compute_fiscal_regime_id()
        self.assertEqual(
            wizard.fiscal_regime_id,
            self.env.ref("l10n_mx_catalogs.c_regimen_fiscal_616"),
        )

    def test_validate_included_invoices_constraint(self):
        invoice = self._create_cfdi_invoice()
        with self.assertRaises(ValidationError):
            self._create_wizard(invoice)

    def test_create_cfdi_failure_unlinks_document(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        wizard = self._create_wizard(invoice)
        with (
            patch.object(
                type(self.service),
                "create_cfdi",
                side_effect=UserError("publish failed"),
            ),
            self.assertRaises(UserError),
        ):
            wizard.create_cfdi()
        self.assertFalse(invoice.related_cert_ids)


class TestAccountPaymentRegisterWizard(CFDIAccountTestCommon):
    def test_create_payments_sets_payment_form(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        payment_form = self.env.ref("l10n_mx_catalogs.c_forma_pago_03")
        register = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "amount": invoice.amount_residual,
                    "payment_form_id": payment_form.id,
                }
            )
        )
        payments = register._create_payments()
        self.assertEqual(payments.payment_form_id, payment_form)

    def test_partial_payment_blocked_for_pue_cfdi(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        register = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "amount": invoice.amount_residual / 2,
                    "payment_form_id": self.env.ref(
                        "l10n_mx_catalogs.c_forma_pago_03"
                    ).id,
                }
            )
        )
        with self.assertRaises(UserError):
            register._create_payments()
