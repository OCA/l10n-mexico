from datetime import datetime

from odoo import _, models
from odoo.exceptions import ValidationError
from odoo.tools import json_float_round


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def action_generate_cfdi(self):
        self.ensure_one()

        if self.cfdi_document_id:
            raise ValidationError(_("The payment already has a related CFDI."))

        if not self.is_reconciled:
            raise ValidationError(_("The payment is not fully reconciled."))

        if self.payment_type == "inbound":
            self.create_payment_cfdi()

    def create_payment_cfdi(self):
        """
        Create CFDI of type payment ('P') matching the invoice payments if they are required.
        """

        self.ensure_one()

        # assert move type is inbound payment
        if self.move_type != "entry" or self.payment_type != "inbound":
            raise ValidationError(_("You can only create customer payments."))

        # check if the payment is fully reconciled
        if not self.is_reconciled:
            raise ValidationError(_("The payment is not fully reconciled."))

        payment_data = self.prepare_payment_cfdi()

        # get invoices issuer
        issuer = self.reconciled_invoice_ids.issuer_id
        issuer.ensure_one()

        # get invoices receiver
        receiver = self.reconciled_invoice_ids.receiver_id
        if not receiver:
            # resolve receiver from the invoice CFDI for legacy invoices
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

        # establecer uso de CFDI a Pagos (CP01)
        self.cfdi_use_id = self.env.ref("l10n_mx_catalogs.c_uso_cfdi_CP01").id

        try:
            cfdi_data = {
                "ExpeditionPlace": issuer.zip,
                "Receiver": {
                    "Name": receiver.name,
                    "Rfc": receiver.vat,
                    "CfdiUse": self.cfdi_use_id.code,
                    "FiscalRegime": receiver.tax_regime.code,
                    "TaxZipCode": receiver.zip,
                },
                "Complemento": {"Payments": [payment_data]},
            }

            if receiver.vat == "XAXX010101000":
                currentDateTime = datetime.now()

                cfdi_data["GlobalInformation"] = {
                    "Periodicity": "01",  # Daily periodicity
                    "Months": str(currentDateTime.month).rjust(2, "0"),
                    "Year": currentDateTime.year,
                }

                cfdi_data["Receiver"]["TaxZipCode"] = issuer.zip
                cfdi_data["Receiver"]["FiscalRegime"] = "616"

            payment_cfdi.publish(cfdi_data)

            self.update(
                {
                    "related_cert_ids": [(4, payment_cfdi.id)],
                    "cfdi_document_id": payment_cfdi.id,
                }
            )

            for invoice in self.reconciled_invoice_ids:
                invoice.related_cert_ids |= payment_cfdi

        except Exception as e:
            payment_cfdi.unlink()
            raise e

    def prepare_payment_cfdi(self):
        self.ensure_one()

        related_documents_data = []

        for invoice in self.reconciled_invoice_ids:
            if not invoice.cfdi_document_id:
                raise ValidationError(
                    _(
                        "Error al emitir CFDI tipo Comprobante de Pago. "
                        "La factura %s no tiene CFDI"
                    )
                    % invoice.name
                )

            # get related cfdi of type 'Ingreso'
            existent_invoice_cfdi = invoice.related_cert_ids.filtered_domain(
                [("type", "=", "I"), ("state", "=", "published")]
            )
            existent_invoice_cfdi.ensure_one()

            # get related CFDIs of type 'Pago'
            existent_payments_cfdi = invoice.related_cert_ids.filtered_domain(
                [("type", "=", "P"), ("state", "=", "published")]
            )

            # initialize related document data
            related_document_data = {
                "Uuid": existent_invoice_cfdi.uuid,
                "Folio": existent_invoice_cfdi.name,
                "PartialityNumber": len(existent_payments_cfdi) + 1,
                "PaymentMethod": "PUE",
                "AmountPaid": 0,
                "PreviousBalanceAmount": invoice.amount_residual,
            }

            # add amounts from matched credit lines
            for credit in invoice.line_ids.matched_credit_ids:
                # add line amount if it comes from the current payment
                if credit.credit_move_id.move_id == self.move_id:
                    related_document_data["AmountPaid"] += credit.amount
                    related_document_data["PreviousBalanceAmount"] += credit.amount

            # add tax data
            tax_data = self._compute_taxes(related_document_data["AmountPaid"], invoice)
            if tax_data:
                related_document_data["TaxObject"] = "02"
                related_document_data["Taxes"] = tax_data
            else:
                related_document_data["TaxObject"] = "01"

            # round monetary fields
            for field in ["AmountPaid", "PreviousBalanceAmount"]:
                related_document_data[field] = json_float_round(
                    related_document_data[field], 2
                )

            # add related document data to the list
            related_documents_data.append(related_document_data)

        payment_date = self.move_id._format_cfdi_date_str(self.date)
        payment_data = {
            "Date": payment_date,
            "PaymentForm": self.move_id.payment_form_id.code,
            "Amount": json_float_round(self.amount, 2),
            "RelatedDocuments": related_documents_data,
        }
        return payment_data

    def _compute_taxes(self, amount_paid, invoice):
        total_taxes = invoice.prepare_invoice_cfdi_total_taxes()
        payment_taxes = []

        # skip if there are no taxes
        if not total_taxes:
            return payment_taxes

        # compute taxes base (amount_paid = rate * base) so ( base = amount_paid / rate )
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
                cfdi.cancel(
                    "02"
                )  # cancel reason: 'Comprobantes emitidos con errores sin relación'
