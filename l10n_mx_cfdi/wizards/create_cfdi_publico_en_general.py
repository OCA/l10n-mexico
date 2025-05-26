from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import datetime


class CFDIGenericInvoiceCreate(models.TransientModel):
    _name = "l10n_mx_cfdi.generic_invoice_create"
    _description = "Create a generic CFDI invoice"

    periodicity_id = fields.Many2one(
        "l10n_mx_catalogs.c_periodicidad", string="Periodicity", required=True
    )

    meses_id = fields.Many2one("l10n_mx_catalogs.c_meses", string="Mes", required=True)

    year = fields.Text(string="Año", required=True)

    issuer_id = fields.Many2one(
        "l10n_mx_cfdi.issuer",
        string="Emisor",
        domain=[("registered", "=", True)],
        required=True,
    )

    payment_method_id = fields.Many2one(
        "l10n_mx_catalogs.c_metodo_pago", string="Metodo de Pago", readonly=True
    )
    payment_form_id = fields.Many2one(
        "l10n_mx_catalogs.c_forma_pago", string="Forma de Pago"
    )

    fiscal_regime_id = fields.Many2one(
        "l10n_mx_catalogs.c_regimen_fiscal",
        string="Régimen Fiscal",
        required=True,
        compute="_compute_fiscal_regime_id",
        readonly=True,
    )

    cfdi_use_id = fields.Many2one(
        "l10n_mx_catalogs.c_uso_cfdi",
        string="Uso de CFDI",
        required=True,
        readonly=True,
    )
    move_ids = fields.Many2many("account.move", string="Facturas", required=True)

    date = fields.Date(string="Fecha", required=True, default=fields.Date.context_today)

    @api.depends("periodicity_id")
    def _compute_fiscal_regime_id(self):
        for record in self:
            if record.periodicity_id.code == "05":
                record.fiscal_regime_id = self.env.ref(
                    "l10n_mx_catalogs.c_regimen_fiscal_621"
                )
            else:
                record.fiscal_regime_id = self.env.ref(
                    "l10n_mx_catalogs.c_regimen_fiscal_616"
                )

    @api.model
    def default_get(self, field_names):
        defaults_dict = super().default_get(field_names)
        context = self.env.context

        if context["active_model"] == "account.move":
            related_invoice_objs = self.env["account.move"].browse(
                context["active_ids"]
            )
            for invoice in related_invoice_objs:
                self._validate_invoice(invoice)

            defaults_dict.update({"move_ids": related_invoice_objs})

        currentDateTime = datetime.datetime.now()
        defaults_dict.update(
            {
                "year": currentDateTime.strftime("%Y"),
                "cfdi_use_id": self.env.ref("l10n_mx_catalogs.c_uso_cfdi_S01").id,
                "payment_method_id": self.env.ref(
                    "l10n_mx_catalogs.c_metodo_pago_PUE"
                ).id,
                "payment_form_id": self.env.ref("l10n_mx_catalogs.c_forma_pago_01").id,
            }
        )
        return defaults_dict

    @api.constrains("move_ids")
    def _validate_included_invoices(self):
        for record in self:
            for invoice in record.move_ids:
                self._validate_invoice(invoice)

    @api.model
    def _validate_invoice(self, invoice):
        invoice.ensure_one()

        if invoice.state != "posted":
            raise ValidationError(_("Invoice %s is not posted.") % invoice.name)

        related_cfdi = invoice.related_cert_ids.filtered_domain(
            [("state", "=", "published")]
        )
        if related_cfdi:
            raise ValidationError(
                _("Invoice %s already has a published CFDI.") % invoice.name
            )

        err_msg = invoice.validate_invoice_items_for_cfdi_generation()
        if err_msg:
            raise ValidationError(err_msg)

    def create_cfdi(self):
        """Emit CFDI 'Al Público en General'"""

        self.ensure_one()
        receiver = self.env.ref(
            "l10n_mx_cfdi.l10n_mx_cfdi_res_partner_publico_en_general"
        )
        cert = self.env["l10n_mx_cfdi.document"].create(
            {
                "type": "I",
                "issuer_id": self.issuer_id.id,
                "receiver_id": receiver.id,
                "is_global_note": True,
            }
        )

        try:
            all_items_data = []
            for invoice in self.move_ids:
                items_data = invoice.gather_invoice_cfdi_items_data()
                all_items_data.extend(items_data)
            currency = self.move_ids[0].currency_id

            cfdi_data = {
                "Currency": currency[0].name,
                "ExpeditionPlace": self.issuer_id.zip,
                "CfdiType": "I",
                "Date": self.move_ids._format_cfdi_date_str(self.date),
                "PaymentForm": self.payment_form_id.code,
                "PaymentMethod": self.payment_method_id.code,
                "GlobalInformation": {
                    "Periodicity": self.periodicity_id.code,
                    "Months": self.meses_id.code,
                    "Year": self.year,
                },
                "Receiver": {
                    "Name": receiver.name,
                    "Rfc": receiver.vat,
                    "CfdiUse": self.cfdi_use_id.code,
                    "FiscalRegime": receiver.tax_regime.code,
                    "TaxZipCode": self.issuer_id.zip,
                },
                "Items": all_items_data,
            }

            cert.publish(cfdi_data)

            for invoice in self.move_ids:
                invoice.related_cert_ids = [(4, cert.id)]

        except Exception as e:
            cert.unlink()
            raise e
