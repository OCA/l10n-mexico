import base64
from datetime import datetime, timedelta

from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero, float_round, json_float_round


class AccountMove(models.Model):
    """
    Integration with the Mexican CFDI 4.0 system for electronic invoices
    """

    _inherit = "account.move"

    cfdi_document_id = fields.Many2one(
        "l10n_mx_cfdi.document",
        string="CFDI",
        readonly=True,
        copy=False,
        compute="_compute_cfdi_document_id",
        store=True,
    )

    cfdi_document_name = fields.Char(
        string="Folio CFDI", readonly=True, related="cfdi_document_id.name", store=True
    )
    cfdi_document_state = fields.Selection(
        string="CFDI Status", readonly=True, related="cfdi_document_id.state"
    )

    related_cert_ids = fields.Many2many(
        "l10n_mx_cfdi.document", string="Documentos", readonly=True, copy=False
    )

    # Invoice CFDI required fields
    cfdi_required = fields.Boolean(string="Requiere CFDI", default=False)

    issuer_id = fields.Many2one(
        "l10n_mx_cfdi.issuer", string="Emisor", domain=[("registered", "=", True)]
    )
    receiver_id = fields.Many2one("res.partner", string="Receptor", readonly=True)

    cfdi_use_id = fields.Many2one("l10n_mx_catalogs.c_uso_cfdi", string="Uso de CFDI")
    payment_method_id = fields.Many2one(
        "l10n_mx_catalogs.c_metodo_pago", string="Método de pago"
    )
    payment_form_id = fields.Many2one(
        "l10n_mx_catalogs.c_forma_pago", string="Forma de pago"
    )

    cfdi_posted = fields.Boolean(
        string="Requiere CFDI", compute="_compute_cfdi_posted", store=True
    )
    cfdi_data_in_attachments = fields.Boolean(
        string="CFDI data in attachments", compute="_compute_cfdi_data_in_attachments"
    )

    l10n_mx_cfdi_auto = fields.Boolean(
        string="CFDI Automatico", related="company_id.l10n_mx_cfdi_auto", readonly=True
    )
    l10n_mx_cfdi_enabled = fields.Boolean(
        string="CFDI Habilitado",
        related="company_id.l10n_mx_cfdi_enabled",
        readonly=True,
    )

    @api.depends("cfdi_document_id")
    def _compute_cfdi_data_in_attachments(self):
        # remove 'bin_size' from the context to allow data to be read
        self = self.with_context(bin_size=False)
        for move in self:
            move.cfdi_data_in_attachments = False

            # get xml attachments
            xml_attachments = self.env["ir.attachment"].search(
                [
                    ("res_model", "=", "account.move"),
                    ("res_id", "=", self.id),
                    ("mimetype", "=", "application/xml"),
                ]
            )

            for attachment in xml_attachments:
                xml = base64.b64decode(attachment.datas)
                if b"cfdi:Comprobante" in xml:
                    move.cfdi_data_in_attachments = True

    @api.model
    def default_get(self, field_names):
        defaults_dict = super().default_get(field_names)
        defaults_dict["receiver_id"] = defaults_dict.get("partner_id")
        if self.partner_id and not self.receiver_id:
            self.receiver_id = self.partner_id
            self.cfdi_use_id = self.partner_id.cfdi_use_id
            self.payment_method_id = self.partner_id.payment_method_id
            self.payment_form_id = self.partner_id.payment_form_id

        # set issuer if there is only one choice
        issuers = self.env["l10n_mx_cfdi.issuer"].search([("registered", "=", True)])
        if len(issuers) == 1:
            defaults_dict["issuer_id"] = issuers[0].id

        return defaults_dict

    @api.onchange("partner_id")
    def _update_receiver(self):
        """
        Update the receiver_id field
        """
        for move in self:
            move.receiver_id = move.partner_id
            move._update_cfdi_data()

    @api.onchange("receiver_id")
    def _update_cfdi_data(self):
        """
        Update the CFDI data when the receiver_id changes
        """
        for move in self:
            if move.receiver_id:
                move.cfdi_use_id = move.receiver_id.cfdi_use_id
                move.payment_method_id = move.receiver_id.payment_method_id
                move.payment_form_id = move.receiver_id.payment_form_id

    @api.depends("related_cert_ids")
    def _compute_cfdi_document_id(self):
        for move in self:
            # remove current reference
            move.cfdi_document_id = False

            # get the last CFDI
            if move.move_type in ("in_invoice", "out_invoice"):
                move.cfdi_document_id = move.related_cert_ids.filtered(
                    lambda x: x.type == "I" and x.state == "published"
                )

            if move.move_type == "out_refund":
                move.cfdi_document_id = move.related_cert_ids.filtered(
                    lambda x: x.type == "E" and x.state == "published"
                )

            if move.move_type == "in_payment":
                move.cfdi_document_id = move.related_cert_ids.filtered(
                    lambda x: x.type == "P" and x.state == "published"
                )

    @api.depends("related_cert_ids")
    def _compute_cfdi_posted(self):
        for move in self:
            if move.cfdi_document_id and move.cfdi_document_id.state == "published":
                move.cfdi_posted = True
            else:
                move.cfdi_posted = False

    def action_post(self):
        """
        Override the action_post method to create the CFDI
        """

        res = super(AccountMove, self).action_post()

        if self.l10n_mx_cfdi_auto:
            # Create the CFDIs if required
            for move in self:
                if (
                    move.move_type == "out_invoice"
                    and move.cfdi_required
                    and move.cfdi_document_id.state != "published"
                ):
                    move.create_invoice_cfdi()

        return res

    def create_invoice_cfdi(self):
        """
        Create the CFDI
        """
        self.ensure_one()

        self._validate_invoice_cfdi_required_fields()

        cert = self.env["l10n_mx_cfdi.document"].create(
            {
                "type": "I",
                "issuer_id": self.issuer_id.id,
                "receiver_id": self.receiver_id.id,
                "related_invoice_id": self.id,
            }
        )

        try:
            cfdi_data = self._gather_invoice_cfdi_data()
            cert.publish(cfdi_data)

            self.update(
                {
                    "related_cert_ids": [(4, cert.id)],
                }
            )

        except Exception as e:
            cert.unlink()
            raise e

    def _validate_invoice_cfdi_required_fields(self):
        """
        Validate the CFDI required fields
        """
        self.ensure_one()
        err_msg = ""

        # validate issuer
        if not self.issuer_id:
            err_msg += "- No se ha definido el emisor\n"

        # validate partner data
        if not self.receiver_id.vat:
            err_msg += "- No se ha definido el RFC del receptor\n"

        if not self.receiver_id.tax_regime:
            err_msg += "- No se ha definido el régimen fiscal del receptor\n"

        if not self.receiver_id.zip and self.receiver_id.vat != "XAXX010101000":
            err_msg += "- No se ha definido el código postal del receptor\n"

        if not self.cfdi_use_id:
            err_msg += "- No se ha definido el uso del CFDI\n"

        if not self.payment_method_id:
            err_msg += "- No se ha definido el método de pago\n"

        if not self.payment_form_id:
            err_msg += "- No se ha definido la forma de pago\n"

        err_msg += self.validate_invoice_items_for_cfdi_generation()

        if err_msg:
            raise ValidationError(_("Cannot generate the CFDI:\n") + err_msg)

    def _gather_invoice_cfdi_data(self):
        cfdi_data = {
            "Currency": self.company_currency_id.name,
            "ExpeditionPlace": self.issuer_id.zip,
            "Date": self._format_cfdi_date_str(self.invoice_date),
            "CfdiType": "I",
            "PaymentForm": self.payment_form_id.code,
            "PaymentMethod": self.payment_method_id.code,
            "Receiver": {
                "Name": self.receiver_id.name,
                "Rfc": self.receiver_id.vat,
                "CfdiUse": self.cfdi_use_id.code,
                "FiscalRegime": self.receiver_id.tax_regime.code,
                "TaxZipCode": self.receiver_id.zip,
            },
            "Items": self.gather_invoice_cfdi_items_data(),
        }

        self._add_global_information_to_cfdi_if_required(cfdi_data)

        return cfdi_data

    def _format_cfdi_date_str(self, document_date):
        """
        Format the date to be used in the CFDI

        This method will add the time to the document_date to make it
        compatible with the CFDI format. Then will format the date to
        ISO 8601 format.

        """
        fixed_tz_recordset = self.with_context(**{"tz": self.env.user.tz})
        now_utc = fields.datetime.now()
        now_utc_tz = fields.Datetime.context_timestamp(fixed_tz_recordset, now_utc)

        # add 2h if there is a difference larger than 24h between
        # this is a workaround to avoid issues with the PAC when
        # signing a CFDI with a date in the past
        if (now_utc_tz.date() - document_date).days > 1:
            # add 2h to now_utc_tz
            now_utc_tz = now_utc_tz + timedelta(hours=2)

        # add time info to invoice_date
        document_date = datetime.combine(document_date, now_utc_tz.time())

        # invoice_date to ISO 8601 format
        document_date_str = document_date.strftime("%Y-%m-%dT%H:%M:%S")
        return document_date_str

    def gather_invoice_cfdi_items_data(self):
        """
        Gather the data for the CFDI items
        """
        self.ensure_one()

        cfdi_items_data = []
        for line in self.line_ids:
            if line.exclude_from_invoice_tab or not line.product_id:
                continue

            cfdi_item_data = line._gater_cfdi_item_data()
            cfdi_items_data.append(cfdi_item_data)

        return cfdi_items_data

    def gater_invoice_cfdi_item_data(self, line):
        """Gather the data for a CFDI item.
        :param line: The invoice line
        :return: The CFDI item data
        """

        cfdi_item_data = line._gater_cfdi_item_data()

        return cfdi_item_data

    def validate_invoice_items_for_cfdi_generation(self):
        err_msg = ""
        # validate invoice items
        for line in self.line_ids:
            if line.exclude_from_invoice_tab or not line.product_id:
                continue

            if not line.product_id.l10n_mx_cfdi_product_code_id:
                err_msg += (
                    "- No se ha definido el código de producto para el producto %s\n"
                    % line.product_id.name
                )

            if not line.product_id.l10n_mx_cfdi_product_measurement_unit_id:
                err_msg += (
                    "- No se ha definido la unidad de medida para el producto %s\n"
                    % line.product_id.name
                )

        return err_msg

    @api.model
    def _gather_invoice_cfdi_item_taxes_data(self, line, discount):
        """Gather the taxes data for a CFDI item."""

        price_unit_wo_discount = line.price_unit - discount

        taxes = []
        for tax_id in line.tax_ids:
            computed_tax = tax_id.compute_all(
                price_unit_wo_discount,
                quantity=line.quantity,
                currency=line.currency_id,
            )
            tax_rate = (
                tax_id.amount / 100
                if tax_id.amount_type == "percent"
                else tax_id.amount
            )
            tax_total = (
                computed_tax["taxes"][0]["amount"] if computed_tax["taxes"] else 0
            )
            taxes.append(
                {
                    "Name": tax_id.extract_l10n_mx_tax_code(),
                    "Rate": tax_rate,
                    "IsRetention": tax_id.extract_is_retention(),
                    "Base": computed_tax["total_excluded"],
                    "Total": tax_total,
                }
            )
        return taxes

    def prepare_invoice_cfdi_total_taxes(self):
        self.ensure_one()

        total_taxes = {}
        for line in self.line_ids:
            if line.tax_line_id:
                tax_id = line.tax_line_id
                tax_code = tax_id.extract_l10n_mx_tax_code()
                if not tax_code:
                    raise UserError(
                        _("The tax code for tax %s is not defined.")
                        % line.tax_ids[0].name
                    )

                tax_rate = (
                    tax_id.amount / 100
                    if tax_id.amount_type == "percent"
                    else tax_id.amount
                )

                if tax_code in total_taxes:
                    total_taxes[tax_code]["Base"] += line.tax_base_amount
                    total_taxes[tax_code]["Total"] += line.price_total
                else:
                    total_taxes[tax_code] = {
                        "Name": tax_code,
                        "Rate": tax_rate,
                        "IsRetention": tax_id.extract_is_retention(),
                        "Base": line.tax_base_amount,
                        "Total": line.price_total,
                    }

        # prepare float values to be serialized as JSON
        for _k, v in total_taxes.items():
            v["Base"] = json_float_round(v["Base"], 2)
            v["Total"] = json_float_round(v["Total"], 2)

        return list(total_taxes.values())

    def button_draft(self):
        for rec in self:
            if rec.l10n_mx_cfdi_auto:
                published_related_cfdi = rec.related_cert_ids.filtered_domain(
                    [("state", "=", "published")]
                )
                if len(published_related_cfdi) > 0 and rec.move_type != "in_invoice":
                    # show CFDI cancel dialog
                    return (
                        rec.env.ref("l10n_mx_cfdi.document_cancel_action")
                        .sudo()
                        .read()[0]
                    )

        return super(AccountMove, self).button_draft()

    def create_refund_cfdi(self):
        """
        Create CFDI of type 'E' (Egreso).
        """
        for refund in self:
            items_data = self.gather_invoice_cfdi_items_data()

            receivables = refund.line_ids.filtered(
                lambda l: l.account_id.user_type_id.type == "receivable"
            )
            partial_reconcile = self.env["account.partial.reconcile"].search(
                [("debit_move_id", "in", receivables.ids)]
            )
            partial_reconcile |= (
                receivables.matched_debit_ids + receivables.matched_credit_ids
            )

            move_lines = (
                partial_reconcile.credit_move_id + partial_reconcile.debit_move_id
            )

            related_cfdis = move_lines.move_id.related_cert_ids.filtered_domain(
                [
                    ("state", "=", "published"),
                    ("type", "=", "I"),
                ]
            )

            cfdi_data = {
                "NameId": "2",
                "ExpeditionPlace": refund.issuer_id.zip,
                "Date": self._format_cfdi_date_str(self.invoice_date),
                "PaymentForm": refund.payment_form_id.code,
                "PaymentMethod": refund.payment_method_id.code,
                "Receiver": {
                    "Name": refund.partner_id.name,
                    "Rfc": refund.partner_id.vat,
                    "CfdiUse": refund.cfdi_use_id.code,
                    "FiscalRegime": refund.partner_id.tax_regime.code,
                    "TaxZipCode": refund.partner_id.zip,
                },
                "Items": items_data,
                "Relations": {
                    "Type": "01",
                    "Cfdis": [
                        {"Uuid": related_cfdi.uuid} for related_cfdi in related_cfdis
                    ],
                },
            }

            refund_cfdi = self.env["l10n_mx_cfdi.document"].create(
                {
                    "type": "E",
                    "issuer_id": refund.issuer_id.id,
                    "receiver_id": refund.receiver_id.id,
                    "related_invoice_id": refund.id,
                }
            )

            self._add_global_information_to_cfdi_if_required(cfdi_data)

            # register relations
            refund_cfdi.update(
                {
                    "related_document_ids": [
                        (
                            0,
                            0,
                            {
                                "source_id": refund_cfdi.id,
                                "target_id": related_cfdi.id,
                                "relation_type_id": self.env.ref(
                                    "l10n_mx_catalogs.c_tipo_relacion_1"
                                ).id,
                            },
                        )
                        for related_cfdi in related_cfdis
                    ]
                }
            )

            try:
                refund_cfdi.publish(cfdi_data)

                refund.update(
                    {
                        "related_cert_ids": [(4, refund_cfdi.id)],
                    }
                )

                for cfdi in related_cfdis:
                    if cfdi.related_invoice_id:
                        cfdi.related_invoice_id.related_cert_ids |= refund_cfdi

            except Exception as e:
                refund_cfdi.unlink()
                raise e

    def _add_global_information_to_cfdi_if_required(self, cfdi_data):
        if self.receiver_id.vat == "XAXX010101000":
            currentDateTime = datetime.now()

            cfdi_data["GlobalInformation"] = {
                "Periodicity": "01",  # Daily periodicity
                "Months": str(currentDateTime.month).rjust(2, "0"),
                "Year": currentDateTime.year,
            }

            cfdi_data["Receiver"]["TaxZipCode"] = self.issuer_id.zip
            cfdi_data["Receiver"]["FiscalRegime"] = "616"

    @api.returns("self", lambda value: value.id)
    def copy(self, default=None):
        # avoid copying the related cfdis
        default = (default or {}).update(
            {
                "related_cert_ids": [(6, 0, [])],
            }
        )

        return super(AccountMove, self).copy(default)

    def _get_name_invoice_report(self):
        self.ensure_one()
        if self.company_id.account_fiscal_country_id.code == "MX":
            return "l10n_mx_cfdi.report_invoice_document"

        return super()._get_name_invoice_report()

    def action_load_from_attachment(self):
        self.ensure_one()

        # find xml attachment
        xml_attachment = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", self.id),
                ("mimetype", "=", "application/xml"),
            ],
            limit=1,
        )

        if not xml_attachment:
            raise UserError(_("No XML attachment found for this invoice."))

        # decode attachment
        xml = base64.b64decode(xml_attachment.datas)

        cfdi = self._parse_cfdi_xml(xml)
        cfdi.xml_file = xml

        self.related_cert_ids |= cfdi

    def _parse_cfdi_xml(self, xml):
        # parse CFDI XML
        root = etree.fromstring(xml)
        namespaces = root.nsmap

        # add tfd namespace
        namespaces["tfd"] = "http://www.sat.gob.mx/TimbreFiscalDigital"

        cfdi_data = {
            "type": root.attrib["TipoDeComprobante"],
            "serie": root.attrib.get("Serie", ""),
            "folio": root.attrib.get("Folio", ""),
            "state": "published",
            "related_invoice_id": self.id,
        }

        # get uuid
        timbre_fiscal = root.find(
            "./cfdi:Complemento/tfd:TimbreFiscalDigital", namespaces
        )
        cfdi_data["uuid"] = timbre_fiscal.attrib["UUID"]

        issuer_id = self._resolve_issuer_from_xml(namespaces, root)
        cfdi_data["issuer_id"] = issuer_id.id
        self.issuer_id = issuer_id

        receiver_id, cfdi_use = self._resolve_receiver_data_from_xml(namespaces, root)
        cfdi_data["receiver_id"] = receiver_id.id
        cfdi_use_model = self.env["l10n_mx_catalogs.c_uso_cfdi"]
        cfdi_use = cfdi_use_model.search([("code", "=", cfdi_use)], limit=1)

        self.receiver_id = receiver_id
        self.cfdi_use_id = cfdi_use

        # create or update cfdi document
        cfdi_document_model = self.env["l10n_mx_cfdi.document"]
        document = cfdi_document_model.search(
            [("uuid", "=", cfdi_data["uuid"])], limit=1
        )
        if document:
            document.write(cfdi_data)
        else:
            document = cfdi_document_model.create(cfdi_data)

        self.cfdi_document_id = document
        self.cfdi_required = True

        # resolve payment form
        payment_form_model = self.env["l10n_mx_catalogs.c_forma_pago"]
        payment_form_code = root.attrib["FormaPago"]
        self.payment_form_id = payment_form_model.search(
            [("code", "=", payment_form_code)], limit=1
        )

        # resolve payment method
        payment_method_model = self.env["l10n_mx_catalogs.c_metodo_pago"]
        payment_method_code = root.attrib["MetodoPago"]
        self.payment_method_id = payment_method_model.search(
            [("code", "=", payment_method_code)], limit=1
        )

        return document

    def _resolve_receiver_data_from_xml(self, namespaces, root):
        # get receiver
        receiver = root.find("cfdi:Receptor", namespaces)
        receiver_id = self.env["res.partner"].search(
            [("vat", "=", receiver.attrib["Rfc"])], limit=1
        )
        if not receiver_id:
            raise UserError(
                _("Cannot find the receptor of the certificate. RFC: %s")
                % receiver.attrib["Rfc"]
            )

        cfdi_use = receiver.attrib["UsoCFDI"]
        return receiver_id, cfdi_use

    def _resolve_issuer_from_xml(self, namespaces, root):
        # get issuer
        issuer = root.find("cfdi:Emisor", namespaces)
        issuer_id = self.env["l10n_mx_cfdi.issuer"].search(
            [("vat", "=", issuer.attrib["Rfc"])]
        )
        if not issuer_id:
            # find partner
            partner_id = self.env["res.partner"].search(
                [("vat", "=", issuer.attrib["Rfc"])]
            )
            if not partner_id:
                raise UserError(
                    _("Cannot find the partner who emitted the certificate. " "RFC: %s")
                    % issuer.attrib["Rfc"]
                )

            # create issuer
            issuer_id = self.env["l10n_mx_cfdi.issuer"].create(
                {
                    "partner_id": partner_id.id,
                }
            )
        return issuer_id

    def action_generate_cfdi(self):
        self.ensure_one()

        if self.cfdi_document_id.state == "published":
            raise UserError(_("The CFDI has been published."))

        if self.move_type == "out_invoice":
            self.create_invoice_cfdi()

        if self.move_type == "out_refund":
            # create credit note CFDI if required
            if self.amount_residual != 0:
                raise UserError(
                    _(
                        "You cannot generate a CFDI for a credit note with a "
                        "pending amount."
                    )
                )
            self.create_refund_cfdi()


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    cfdi_price_unit = fields.Monetary(
        compute="_compute_cfdi_fields",
        store=True,
    )

    cfdi_subtotal = fields.Monetary(
        compute="_compute_cfdi_fields",
        store=True,
    )

    cfdi_discount = fields.Monetary(
        compute="_compute_cfdi_fields",
        store=True,
    )

    @api.depends(
        "product_id",
        "price_unit",
        "quantity",
        "discount",
    )
    def _compute_cfdi_fields(self):
        for line in self:
            line._gater_cfdi_item_data()

    def _gater_cfdi_item_data(self):
        self.ensure_one()

        res = {}
        currency = self.currency_id.sudo()

        # use product price decimal precision to round the price calculations
        price_decimal_precision = self.env.ref("product.decimal_price").sudo().digits

        # Compute 'Subtotal'.
        line_discount_price_unit = self.price_unit

        if hasattr(self, "discount_fixed"):
            line_discount_price_unit -= self.discount_fixed

        line_discount_price_unit = line_discount_price_unit * (
            1 - self.discount / 100.0
        )
        # round the price unit to the currency precision to prevent
        # differences between the invoice totals and the CFDI total
        line_discount_price_unit = float_round(
            line_discount_price_unit, precision_digits=price_decimal_precision
        )

        subtotal = self.quantity * line_discount_price_unit

        # keep track of taxes included in price to subtract them later
        # from the unit price as the CFDI specification doesn't support
        # then
        taxes_included = 0

        cfdi_taxes = []
        if self.tax_ids:
            # Compute taxes and adjust 'Subtotal' and 'Total'
            taxes = self.tax_ids._origin.with_context(force_sign=1)
            taxes_res = taxes.compute_all(
                line_discount_price_unit,
                quantity=self.quantity,
                currency=self.currency_id,
                product=self.product_id,
                partner=self.partner_id,
                is_refund=self.move_id.move_type in ("out_refund", "in_refund"),
            )
            res["Subtotal"] = taxes_res["total_excluded"]
            res["Total"] = taxes_res["total_included"]

            for computed_tax in taxes_res["taxes"]:
                tax_id = self.env["account.tax"].browse(computed_tax["id"])
                tax_rate = (
                    tax_id.amount / 100
                    if tax_id.amount_type == "percent"
                    else tax_id.amount
                )
                is_retention = tax_id.extract_is_retention()
                tax_rate = json_float_round(tax_rate, precision_digits=6)
                tax_total = json_float_round(
                    computed_tax["amount"], precision_digits=currency.decimal_places
                )
                tax_base = json_float_round(
                    taxes_res["total_excluded"],
                    precision_digits=currency.decimal_places,
                )

                # sat expects retention taxes to be positive but odoo uses negative values
                if is_retention:
                    tax_rate *= -1
                    tax_total *= -1

                cfdi_taxes.append(
                    {
                        "Name": tax_id.extract_l10n_mx_tax_code(),
                        "Rate": tax_rate,
                        "IsRetention": is_retention,
                        "Base": tax_base,
                        "Total": tax_total,
                    }
                )

                if tax_id.price_include:
                    taxes_included += tax_total

        if cfdi_taxes:
            res.update(
                {
                    "Taxes": cfdi_taxes,
                    "TaxObject": "02",  # 'Si objeto de impuesto'
                }
            )
        else:
            res["Total"] = res["Subtotal"] = subtotal
            res["TaxObject"] = "01"

        if self.product_id.default_code:
            res["IdentificationNumber"] = self.product_id.default_code
        unit_included_taxes = taxes_included / (self.quantity or 1)
        line_discount_price_unit -= unit_included_taxes
        res.update(
            {
                "Quantity": self.quantity,
                "ProductCode": self.product_id.l10n_mx_cfdi_product_code_id.code,
                "Description": self.name,
                "UnitCode": self.product_id.l10n_mx_cfdi_product_measurement_unit_id.code,
            }
        )

        self._round_values_to_currency_precision(res)

        # compute discount
        expected_subtotal_wo_discount = line_discount_price_unit * self.quantity
        discount = (
            (self.price_unit * self.quantity)
            - expected_subtotal_wo_discount
            - taxes_included
        )
        if float_is_zero(discount, precision_digits=currency.decimal_places):
            # ignore a difference below the currency precision
            discount = 0

        res["Discount"] = discount
        res["Subtotal"] += discount

        # recompute the unit price from the subtotal to avoid rounding
        res["UnitPrice"] = res["Subtotal"] / (self.quantity or 1)

        self._round_values_to_currency_precision(res)

        # store the values to be used in the report
        self.cfdi_subtotal = res["Subtotal"]
        self.cfdi_discount = res["Discount"]
        self.cfdi_price_unit = res["UnitPrice"]

        return res

    def _round_values_to_currency_precision(self, res, skip=None):
        currency_decimal_places = self.currency_id.decimal_places

        # Round all values to the currency precision
        for k, v in res.items():
            if skip and k in skip:
                continue

            if isinstance(v, float):
                res[k] = json_float_round(v, precision_digits=currency_decimal_places)
            else:
                res[k] = v
