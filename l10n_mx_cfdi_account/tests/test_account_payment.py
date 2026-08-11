from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch

from odoo import fields
from odoo.exceptions import ValidationError

from .common import ACTIVE_CFDI_RESPONSE, CFDIAccountTestCommon


class TestAccountPayment(CFDIAccountTestCommon):
    def _first_docto_relacionado(self, pagos):
        return pagos["Pago"][0]["DoctoRelacionado"][0]

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
        captured = {}

        def _capture(cfdi, issuer=None):
            captured["cfdi"] = cfdi
            return ACTIVE_CFDI_RESPONSE

        with patch.object(type(self.service), "create_cfdi", side_effect=_capture):
            payment.create_payment_cfdi()
        self.assertTrue(payment.related_cert_ids)
        self.assertEqual(payment.cfdi_use_id.code, "CP01")
        self.assertEqual(captured["cfdi"]["TipoDeComprobante"], "P")
        self.assertEqual(captured["cfdi"]["Moneda"], "XXX")
        # CFDI 4.0 / Facturama Multiemisor expect Exportacion=01 on tipo P.
        self.assertEqual(captured["cfdi"].get("Exportacion"), "01")
        docto = captured["cfdi"]["Complemento"]["Pago"][0]["DoctoRelacionado"][0]
        self.assertEqual(docto.get("MetodoDePagoDR"), "PPD")

    def test_create_payment_cfdi_receiver_from_related_cert(self):
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        self._create_published_invoice_cfdi(invoice)
        invoice.with_context(check_move_validity=False).write({"receiver_id": False})
        payment = self._register_invoice_payment(invoice)
        with patch.object(
            type(self.service),
            "create_cfdi",
            return_value=ACTIVE_CFDI_RESPONSE,
        ):
            payment.create_payment_cfdi()
        self.assertTrue(payment.related_cert_ids)

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
        captured = {}

        def _capture(cfdi, issuer=None):
            captured["cfdi"] = cfdi
            return ACTIVE_CFDI_RESPONSE

        with patch.object(type(self.service), "create_cfdi", side_effect=_capture):
            payment.create_payment_cfdi()
        self.assertTrue(payment.related_cert_ids)
        self.assertTrue(captured["cfdi"].get("InformacionGlobal"))
        self.assertEqual(captured["cfdi"]["Receptor"]["RegimenFiscalReceptor"], "616")

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

    def test_prepare_payment_cfdi_objeto_imp_01_without_taxes(self):
        self.cfdi_product.taxes_id = [(5, 0, 0)]
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        self._create_published_invoice_cfdi(invoice)
        payment = self._register_invoice_payment(invoice)
        pagos = payment.prepare_payment_cfdi()
        docto = self._first_docto_relacionado(pagos)
        self.assertEqual(docto["ObjetoImpDR"], "01")
        self.assertFalse(docto.get("ImpuestosDR"))

    def test_prepare_payment_cfdi_with_retention_tax(self):
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        self._create_published_invoice_cfdi(invoice)
        payment = self._register_invoice_payment(invoice)
        with patch.object(
            type(payment),
            "_compute_taxes",
            return_value=[
                {
                    "Name": "IVA",
                    "Rate": 0.04,
                    "IsRetention": True,
                    "Base": 100.0,
                    "Total": 4.0,
                }
            ],
        ):
            pagos = payment.prepare_payment_cfdi()
        impuestos = self._first_docto_relacionado(pagos)["ImpuestosDR"]
        self.assertTrue(
            impuestos.get("RetencionesDR") or impuestos.get("retenciones_dr")
        )

    def test_prepare_payment_cfdi_with_traslado_tax(self):
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        self._create_published_invoice_cfdi(invoice)
        payment = self._register_invoice_payment(invoice)
        with patch.object(
            type(payment),
            "_compute_taxes",
            return_value=[
                {
                    "Name": "IVA",
                    "Rate": 0.16,
                    "IsRetention": False,
                    "Base": 100.0,
                    "Total": 16.0,
                }
            ],
        ):
            pagos = payment.prepare_payment_cfdi()
        impuestos = self._first_docto_relacionado(pagos)["ImpuestosDR"]
        self.assertTrue(impuestos.get("TrasladosDR") or impuestos.get("traslados_dr"))

    def test_prepare_payment_cfdi_metodo_dr_from_related_invoice(self):
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        document = self._create_published_invoice_cfdi(invoice)
        metodo_source = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        document.related_invoice_id = metodo_source
        invoice.payment_method_id = False
        payment = self._register_invoice_payment(invoice)
        pagos = payment.prepare_payment_cfdi()
        docto = self._first_docto_relacionado(pagos)
        self.assertEqual(docto.get("MetodoDePagoDR"), "PPD")

    def test_prepare_payment_cfdi_foreign_currency(self):
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        self._create_published_invoice_cfdi(invoice)
        payment = self._register_invoice_payment(invoice)
        with patch.object(
            type(payment),
            "_cfdi_docto_equivalencia_dr",
            return_value=Decimal("20"),
        ):
            pagos = payment.prepare_payment_cfdi()
        docto = self._first_docto_relacionado(pagos)
        self.assertEqual(float(docto.get("EquivalenciaDR")), 20.0)
        self.assertEqual(float(pagos.get("Pago")[0].get("TipoCambioP")), 1.0)

    def test_prepare_payment_cfdi_imp_pagado_matches_payment_amount(self):
        """Golden: same-currency ImpPagado sum equals Pago.Monto (Facturama)."""
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        self._create_published_invoice_cfdi(invoice)
        payment = self._register_invoice_payment(invoice)
        pagos = payment.prepare_payment_cfdi()
        pago = pagos["Pago"][0]
        docto = self._first_docto_relacionado(pagos)
        self.assertEqual(float(docto["ImpPagado"]), float(pago["Monto"]))
        self.assertEqual(float(pago["Monto"]), float(payment.amount))
        self.assertEqual(float(docto.get("EquivalenciaDR") or 1), 1.0)

    def test_cfdi_docto_imp_amounts_uses_debit_currency(self):
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        self._create_published_invoice_cfdi(invoice)
        payment = self._register_invoice_payment(invoice)
        saldo_ant, imp_pagado = payment._cfdi_docto_imp_amounts(invoice)
        self.assertGreater(imp_pagado, 0)
        self.assertGreaterEqual(saldo_ant, imp_pagado)
        self.assertEqual(imp_pagado, float(payment.amount))

    def test_cfdi_docto_imp_amounts_skips_foreign_partials(self):
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        payment_move = self.env["account.move"].new({})
        other_move = self.env["account.move"].new({})
        payment = self.env["account.payment"].new(
            {
                "amount": 10.0,
                "currency_id": self.company.currency_id.id,
            }
        )
        payment.move_id = payment_move
        foreign_partial = SimpleNamespace(
            credit_move_id=SimpleNamespace(move_id=other_move),
            debit_amount_currency=50.0,
            amount=50.0,
        )
        fake_lines = SimpleNamespace(matched_credit_ids=[foreign_partial])
        with patch.object(
            type(invoice),
            "line_ids",
            new_callable=PropertyMock,
            return_value=fake_lines,
        ):
            saldo_ant, imp_pagado = payment._cfdi_docto_imp_amounts(invoice)
        self.assertEqual(imp_pagado, 0.0)
        self.assertEqual(saldo_ant, float(invoice.amount_residual))

    def test_cfdi_align_pago_monto_early_returns_and_drift(self):
        payment = self.env["account.payment"].new(
            {
                "amount": 100.0,
                "currency_id": self.company.currency_id.id,
            }
        )
        # No Pago nodes / no doctos / different currency → early return.
        payment._cfdi_align_pago_monto({})
        payment._cfdi_align_pago_monto({"Pago": []})
        payment._cfdi_align_pago_monto({"Pago": [{"DoctoRelacionado": []}]})
        payment._cfdi_align_pago_monto(
            {
                "Pago": [
                    {
                        "DoctoRelacionado": [
                            {"MonedaDR": "USD", "ImpPagado": Decimal("100")}
                        ]
                    }
                ]
            }
        )
        # Exact match: only set Monto.
        pagos = {
            "Pago": [
                {
                    "DoctoRelacionado": [
                        {
                            "MonedaDR": payment.currency_id.name,
                            "ImpPagado": Decimal("100.00"),
                        }
                    ]
                }
            ]
        }
        payment._cfdi_align_pago_monto(pagos)
        self.assertEqual(pagos["Pago"][0]["Monto"], Decimal("100.00"))
        # Single docto with 1-cent drift → absorb into ImpPagado / balances.
        pagos = {
            "Pago": [
                {
                    "DoctoRelacionado": [
                        {
                            "MonedaDR": payment.currency_id.name,
                            "ImpPagado": Decimal("99.99"),
                            "ImpSaldoAnt": Decimal("99.99"),
                            "ImpSaldoInsoluto": Decimal("0"),
                        }
                    ]
                }
            ]
        }
        payment._cfdi_align_pago_monto(pagos)
        docto = pagos["Pago"][0]["DoctoRelacionado"][0]
        self.assertEqual(docto["ImpPagado"], Decimal("100.00"))
        self.assertEqual(docto["ImpSaldoAnt"], Decimal("100.00"))
        self.assertEqual(docto["ImpSaldoInsoluto"], Decimal("0.00"))
        self.assertEqual(pagos["Pago"][0]["Monto"], Decimal("100.00"))

    def test_prepare_payment_cfdi_uses_payment_form_not_move(self):
        """FormaDePagoP must come from payment.payment_form_id (register wizard)."""
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        self._create_published_invoice_cfdi(invoice)
        forma = self.env.ref("l10n_mx_catalogs.c_forma_pago_01")
        payment = self._register_invoice_payment(invoice, payment_form=forma)
        # Journal entry often has no payment_form_id; that previously yielded
        # Facturama PaymentForm "False" / "Forma de pago inválida".
        payment.move_id.payment_form_id = False
        self.assertTrue(payment.payment_form_id)
        pagos = payment.prepare_payment_cfdi()
        self.assertEqual(str(pagos["Pago"][0]["FormaDePagoP"]), "01")

    def test_cfdi_payment_form_code_requires_form(self):
        payment = self.env["account.payment"].new({})
        with self.assertRaises(ValidationError):
            payment._cfdi_payment_form_code()

    def test_cfdi_docto_equivalencia_dr_same_currency(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        payment = self._register_invoice_payment(invoice)
        self.assertEqual(
            payment._cfdi_docto_equivalencia_dr(invoice),
            Decimal("1"),
        )

    def test_cfdi_docto_equivalencia_dr_converts(self):
        mxn = self.env.ref("base.MXN")
        mxn.active = True
        usd = self.env.ref("base.USD")
        payment = self.env["account.payment"].new(
            {
                "currency_id": mxn.id,
                "company_id": self.company.id,
                "date": fields.Date.today(),
            }
        )
        invoice = self.env["account.move"].new(
            {
                "currency_id": usd.id,
                "company_id": self.company.id,
            }
        )
        with patch.object(type(mxn), "_convert", return_value=20.0):
            self.assertEqual(
                payment._cfdi_docto_equivalencia_dr(invoice),
                Decimal("20"),
            )

    def test_cfdi_docto_equivalencia_dr_falsy_convert(self):
        mxn = self.env.ref("base.MXN")
        mxn.active = True
        usd = self.env.ref("base.USD")
        payment = self.env["account.payment"].new(
            {
                "currency_id": mxn.id,
                "company_id": self.company.id,
                "date": fields.Date.today(),
            }
        )
        invoice = self.env["account.move"].new(
            {
                "currency_id": usd.id,
                "company_id": self.company.id,
            }
        )
        with patch.object(type(mxn), "_convert", return_value=0):
            self.assertEqual(
                payment._cfdi_docto_equivalencia_dr(invoice),
                Decimal("1"),
            )

    def test_cfdi_tipo_cambio_p_mxn(self):
        mxn = self.env.ref("base.MXN")
        mxn.active = True
        payment = self.env["account.payment"].new(
            {
                "currency_id": mxn.id,
                "company_id": self.company.id,
                "date": fields.Date.today(),
            }
        )
        self.assertEqual(payment._cfdi_tipo_cambio_p(), Decimal("1"))

    def test_cfdi_tipo_cambio_p_non_mxn(self):
        usd = self.env.ref("base.USD")
        payment = self.env["account.payment"].new(
            {
                "currency_id": usd.id,
                "company_id": self.company.id,
                "date": fields.Date.today(),
            }
        )
        with patch.object(type(usd), "_convert", return_value=17.5):
            self.assertEqual(payment._cfdi_tipo_cambio_p(), Decimal("17.5"))
        with patch.object(type(usd), "_convert", return_value=0):
            self.assertEqual(payment._cfdi_tipo_cambio_p(), Decimal("1"))

    def test_prepare_payment_cfdi_second_partialidad(self):
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        self._create_published_invoice_cfdi(invoice)
        prior_payment_cfdi = self._create_document(
            type="P",
            state="published",
            related_invoice_id=invoice.id,
            receiver_id=self.customer.id,
        )
        invoice.related_cert_ids = [(4, prior_payment_cfdi.id)]
        payment = self._register_invoice_payment(invoice)
        pagos = payment.prepare_payment_cfdi()
        docto = self._first_docto_relacionado(pagos)
        self.assertEqual(int(docto.get("NumParcialidad")), 2)

    def test_action_generate_cfdi_outbound_noop(self):
        payment = self.env["account.payment"].new(
            {
                "payment_type": "outbound",
                "is_reconciled": True,
            }
        )
        with patch.object(
            type(payment),
            "cfdi_document_id",
            new_callable=PropertyMock,
            return_value=False,
        ):
            self.assertIsNone(payment.action_generate_cfdi())

    def test_create_payment_cfdi_not_reconciled(self):
        payment = self.env["account.payment"].new(
            {
                "payment_type": "inbound",
                "is_reconciled": False,
            }
        )
        with self.assertRaises(ValidationError):
            payment.create_payment_cfdi()

    def test_cancel_payment_cfdi_skips_non_published(self):
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(
                payment_method_id=self.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD").id
            )
        )
        payment = self._register_invoice_payment(invoice)
        draft = self._create_document(
            type="P",
            state="draft",
            related_payment_id=payment.id,
            receiver_id=self.customer.id,
        )
        published = self._create_document(
            type="P",
            state="published",
            related_payment_id=payment.id,
            receiver_id=self.customer.id,
        )
        payment.related_cert_ids = [(6, 0, [draft.id, published.id])]
        cancelled_ids = []

        def _cancel(doc, reason, replacement=None, simulate=False):
            cancelled_ids.append(doc.id)

        with patch.object(type(published), "cancel", _cancel):
            payment.cancel_payment_cfdi()
        self.assertEqual(cancelled_ids, [published.id])
