from datetime import datetime
from decimal import Decimal

from satcfdi.create.cfd import pago20

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import json_float_round

from odoo.addons.l10n_mx_cfdi.services import cfdi_builder


class AccountPayment(models.Model):
    _inherit = "account.payment"

    cfdi_document_id = fields.Many2one(
        "l10n_mx_cfdi.document",
        string="CFDI",
        readonly=True,
        copy=False,
        compute="_compute_cfdi_document_id",
        store=True,
    )
    cfdi_document_state = fields.Selection(
        string="CFDI Status", readonly=True, related="cfdi_document_id.state"
    )

    related_cert_ids = fields.Many2many(
        "l10n_mx_cfdi.document", string="Documentos", readonly=True, copy=False
    )
    cfdi_use_id = fields.Many2one("l10n_mx_catalogs.c_uso_cfdi", string="Uso de CFDI")
    payment_form_id = fields.Many2one(
        "l10n_mx_catalogs.c_forma_pago", string="Forma de pago"
    )
    l10n_mx_cfdi_auto = fields.Boolean(
        string="CFDI Automatico", related="company_id.l10n_mx_cfdi_auto", readonly=True
    )

    l10n_mx_cfdi_enabled = fields.Boolean(
        string="CFDI Habilitado",
        related="company_id.l10n_mx_cfdi_enabled",
        readonly=True,
    )

    @api.depends("related_cert_ids")
    def _compute_cfdi_document_id(self):
        for payment in self:
            payment.cfdi_document_id = False
            payment.cfdi_document_id = payment.related_cert_ids.filtered(
                lambda x: x.type == "P" and x.state == "published"
            )

    def action_generate_cfdi(self):
        self.ensure_one()

        if self.cfdi_document_id:
            raise ValidationError(self.env._("The payment already has a related CFDI."))

        if not self.is_reconciled:
            raise ValidationError(self.env._("The payment is not fully reconciled."))

        if self.payment_type == "inbound":
            self.create_payment_cfdi()

    def create_payment_cfdi(self):
        """Create payment-type ('P') CFDI matching invoice payments if needed."""

        self.ensure_one()

        if self.payment_type != "inbound":
            raise ValidationError(self.env._("You can only create customer payments."))

        if not self.is_reconciled:
            raise ValidationError(self.env._("The payment is not fully reconciled."))

        payment_complement = self.prepare_payment_cfdi()

        issuer = self.reconciled_invoice_ids.issuer_id
        issuer.ensure_one()

        receiver = self.reconciled_invoice_ids.receiver_id
        if not receiver:
            receiver = self.reconciled_invoice_ids.related_cert_ids.filtered_domain(
                [("type", "=", "I"), ("state", "=", "published")]
            ).mapped("receiver_id")[0]

        receiver.ensure_one()

        payment_cfdi = self.env["l10n_mx_cfdi.document"].create(
            {
                "type": "P",
                "issuer_id": issuer.id,
                "receiver_id": receiver.id,
                "related_payment_id": self.id,
            }
        )

        self.cfdi_use_id = self.env.ref("l10n_mx_catalogs.c_uso_cfdi_CP01").id

        try:
            # CFDI type P uses a single zero-amount concepto plus pagos complement
            conceptos = [
                {
                    "ProductCode": "84111506",
                    "UnitCode": "ACT",
                    "Description": "Pago",
                    "Quantity": 1,
                    "UnitPrice": 0,
                    "Subtotal": 0,
                    "Total": 0,
                    "TaxObject": "01",
                }
            ]
            receiver_data = {
                "Name": receiver.name,
                "Rfc": receiver.vat,
                "CfdiUse": self.cfdi_use_id.code,
                "FiscalRegime": receiver.tax_regime.code,
                "TaxZipCode": receiver.zip,
            }
            global_information = None
            if receiver.vat == "XAXX010101000":
                currentDateTime = datetime.now()
                global_information = {
                    "Periodicity": "01",
                    "Months": str(currentDateTime.month).rjust(2, "0"),
                    "Year": currentDateTime.year,
                }
                receiver_data["TaxZipCode"] = issuer.zip
                receiver_data["FiscalRegime"] = "616"

            # Keep Exportacion=01 (CFDI 4.0 / Facturama Multiemisor). Stripping
            # it made Multiemisor return ASP.NET "La solicitud no es válida."
            cfdi = cfdi_builder.build_comprobante(
                issuer=issuer,
                receiver=receiver_data,
                conceptos=conceptos,
                tipo_de_comprobante="P",
                lugar_expedicion=issuer.zip,
                moneda="XXX",
                serie=payment_cfdi.serie,
                folio=payment_cfdi.folio,
                fecha=self.move_id._format_cfdi_date_str(self.date),
                informacion_global=global_information,
                complemento=payment_complement,
                exportacion="01",
            )

            payment_cfdi.publish(cfdi)

            self.update(
                {
                    "related_cert_ids": [(4, payment_cfdi.id)],
                    "cfdi_document_id": payment_cfdi.id,
                }
            )

            for invoice in self.reconciled_invoice_ids:
                invoice.related_cert_ids |= payment_cfdi

            if self.move_id:
                self.move_id._l10n_mx_cfdi_post_document_attachments(payment_cfdi)

        except Exception as e:
            payment_cfdi.unlink()
            raise e

    def prepare_payment_cfdi(self):
        self.ensure_one()

        related_documents = []

        for invoice in self.reconciled_invoice_ids:
            if not invoice.cfdi_document_id:
                raise ValidationError(
                    self.env._(
                        "Error al emitir CFDI tipo Comprobante de Pago. "
                        "La factura %s no tiene CFDI",
                        invoice.name,
                    )
                )

            existent_invoice_cfdi = invoice.related_cert_ids.filtered_domain(
                [("type", "=", "I"), ("state", "=", "published")]
            )
            existent_invoice_cfdi.ensure_one()

            existent_payments_cfdi = invoice.related_cert_ids.filtered_domain(
                [("type", "=", "P"), ("state", "=", "published")]
            )

            previous_balance, amount_paid = self._cfdi_docto_imp_amounts(invoice)

            tax_data = self._compute_taxes(amount_paid, invoice)
            impuestos_dr = None
            if tax_data:
                objeto_imp = "02"
                traslados = []
                retenciones = []
                for tax in tax_data:
                    payload = {
                        "base_dr": Decimal(str(tax["Base"])),
                        "impuesto_dr": cfdi_builder.tax_code_from_name(tax["Name"]),
                        "tipo_factor_dr": "Tasa",
                        "tasa_o_cuota_dr": cfdi_builder._dec_tasa(tax["Rate"]),
                        "importe_dr": Decimal(str(tax["Total"])),
                    }
                    if tax["IsRetention"]:
                        retenciones.append(pago20.RetencionDR(**payload))
                    else:
                        traslados.append(pago20.TrasladoDR(**payload))
                impuestos_dr = pago20.ImpuestosDR(
                    traslados_dr=traslados or None,
                    retenciones_dr=retenciones or None,
                )
            else:
                objeto_imp = "01"

            equivalencia = self._cfdi_docto_equivalencia_dr(invoice)

            docto = pago20.DoctoRelacionado(
                id_documento=existent_invoice_cfdi.uuid,
                moneda_dr=invoice.currency_id.name,
                num_parcialidad=len(existent_payments_cfdi) + 1,
                imp_saldo_ant=Decimal(str(previous_balance)),
                imp_pagado=Decimal(str(amount_paid)),
                objeto_imp_dr=objeto_imp,
                serie=existent_invoice_cfdi.serie or None,
                folio=existent_invoice_cfdi.folio or None,
                equivalencia_dr=equivalencia,
                impuestos_dr=impuestos_dr,
            )
            # Facturama Multiemisor expects MetodoDePagoDR (PUE/PPD) on each
            # related document; defaulting to PPD mismatches paid PUE invoices.
            metodo_dr = (
                invoice.payment_method_id.code if invoice.payment_method_id else None
            )
            if not metodo_dr and existent_invoice_cfdi.related_invoice_id:
                related_invoice = existent_invoice_cfdi.related_invoice_id
                if related_invoice.payment_method_id:
                    metodo_dr = related_invoice.payment_method_id.code
            if metodo_dr:
                docto["MetodoDePagoDR"] = metodo_dr
            related_documents.append(docto)

        payment_date = self.move_id._format_cfdi_date_str(self.date)
        if isinstance(payment_date, str):
            payment_date = datetime.strptime(payment_date, "%Y-%m-%dT%H:%M:%S")

        forma_pago = self._cfdi_payment_form_code()
        # Monto is recomputed by satcfdi Pagos as sum(ImpPagado/EquivalenciaDR);
        # pass the payment amount as a seed for same-currency consistency.
        pago = pago20.Pago(
            fecha_pago=payment_date,
            forma_de_pago_p=forma_pago,
            moneda_p=self.currency_id.name,
            monto=Decimal(str(json_float_round(self.amount, 2))),
            # satcfdi make_pago_totales does monto * TipoCambioP; None is stored
            # when omitted incorrectly, so always pass 1 for MXN.
            tipo_cambio_p=self._cfdi_tipo_cambio_p(),
            docto_relacionado=related_documents,
        )
        pagos = pago20.Pagos(pago=[pago])
        self._cfdi_align_pago_monto(pagos)
        return pagos

    def _cfdi_docto_imp_amounts(self, invoice):
        """Return ``(ImpSaldoAnt, ImpPagado)`` in invoice (MonedaDR) currency.

        ``account.partial.reconcile.amount`` is company currency; ImpPagado must
        use the debit/invoice currency amount so sum(ImpPagado/EquivalenciaDR)
        matches Monto (payment currency) within SAT/Facturama limits.
        """
        self.ensure_one()
        amount_paid = 0.0
        previous_balance = invoice.amount_residual
        for partial in invoice.line_ids.matched_credit_ids:
            if partial.credit_move_id.move_id != self.move_id:
                continue
            # Prefer invoice-currency amount; fall back to company amount.
            paid = partial.debit_amount_currency or partial.amount
            amount_paid += paid
            previous_balance += paid
        return (
            json_float_round(previous_balance, 2),
            json_float_round(amount_paid, 2),
        )

    def _cfdi_align_pago_monto(self, pagos):
        """Ensure Pago.Monto matches payment amount when currencies align.

        satcfdi overwrites Monto from ImpPagado/EquivalenciaDR. When the
        payment and all related documents share a currency, force Monto to the
        registered payment amount (2 dp) and scale the single ImpPagado if the
        reconcile residual drifted by a cent.
        """
        self.ensure_one()
        pago_nodes = pagos.get("Pago") or []
        if not pago_nodes:
            return
        pago = pago_nodes[0]
        payment_amount = Decimal(str(json_float_round(self.amount, 2)))
        doctos = list(pago.get("DoctoRelacionado") or [])
        if not doctos:
            return
        same_currency = all(
            str(d.get("MonedaDR") or self.currency_id.name) == self.currency_id.name
            for d in doctos
        )
        if not same_currency:
            return
        paid_sum = sum(Decimal(str(d.get("ImpPagado") or 0)) for d in doctos)
        if paid_sum == payment_amount:
            pago["Monto"] = payment_amount
            return
        if len(doctos) == 1 and paid_sum:
            # Absorb 1-cent reconcile drift into ImpPagado / balances.
            docto = doctos[0]
            delta = payment_amount - Decimal(str(docto.get("ImpPagado") or 0))
            docto["ImpPagado"] = payment_amount
            if docto.get("ImpSaldoAnt") is not None:
                docto["ImpSaldoAnt"] = Decimal(str(docto["ImpSaldoAnt"])) + delta
            if docto.get("ImpSaldoInsoluto") is not None:
                docto["ImpSaldoInsoluto"] = (
                    Decimal(str(docto["ImpSaldoAnt"])) - payment_amount
                )
        pago["Monto"] = payment_amount

    def _cfdi_payment_form_code(self):
        """SAT FormaDePagoP from the payment (not the journal entry).

        ``account.payment.register`` stores ``payment_form_id`` on the payment.
        The related ``move_id`` often has no Forma de pago, which previously
        sent ``PaymentForm: "False"`` to Facturama ("Forma de pago inválida").
        """
        self.ensure_one()
        form = self.payment_form_id or self.move_id.payment_form_id
        if not form:
            invoices = self.reconciled_invoice_ids
            form = invoices[:1].payment_form_id if invoices else form
        code = form.code if form else False
        if not code:
            raise ValidationError(
                self.env._(
                    "Payment form (Forma de pago) is required to generate a "
                    "payment CFDI (complemento de pago)."
                )
            )
        return code

    def _cfdi_tipo_cambio_p(self):
        """MXN pesos per 1 unit of payment currency (TipoCambioP)."""
        self.ensure_one()
        if self.currency_id.name == "MXN":
            return Decimal("1")
        return Decimal(
            str(
                self.currency_id._convert(
                    1.0,
                    self.company_id.currency_id,
                    self.company_id,
                    self.date,
                )
                or 1.0
            )
        )

    def _cfdi_docto_equivalencia_dr(self, invoice):
        """Units of document currency per 1 unit of payment currency."""
        self.ensure_one()
        if invoice.currency_id == self.currency_id:
            return Decimal("1")
        rate = (
            self.currency_id._convert(
                1.0,
                invoice.currency_id,
                self.company_id,
                self.date,
            )
            or 1.0
        )
        # SAT allows up to 10 decimal places for EquivalenciaDR.
        return Decimal(str(rate)).quantize(Decimal("0.0000000001"))

    def _compute_taxes(self, amount_paid, invoice):
        total_taxes = invoice.prepare_invoice_cfdi_total_taxes()
        payment_taxes = []

        if not total_taxes:
            return payment_taxes

        total_rate = sum(float(tax["Rate"] + 1) for tax in total_taxes)
        base = amount_paid / total_rate
        for tax in total_taxes:
            payment_taxes.append(
                {
                    "Name": tax["Name"],
                    "Rate": tax["Rate"],
                    "IsRetention": tax["IsRetention"],
                    "Base": json_float_round(base, 2),
                    "Total": json_float_round(base * float(tax["Rate"]), 2),
                }
            )

        return payment_taxes

    def cancel_payment_cfdi(self):
        self.ensure_one()

        for cfdi in self.related_cert_ids:
            if cfdi.state == "published":
                cfdi.cancel("02")
