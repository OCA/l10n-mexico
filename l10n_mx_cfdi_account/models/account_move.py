import base64
import logging
from datetime import datetime

from lxml import etree
from satcfdi.create.cfd import cfdi40

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import json_float_round

from odoo.addons.l10n_mx_cfdi.services import cfdi_builder

_logger = logging.getLogger(__name__)


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
    cfdi_document_relations = fields.Many2many(
        "l10n_mx_cfdi.document",
        relation="account_move_cfdi_document_relations",
        column1="move_id",
        column2="cfdi_document_id",
        string="Related CFDIs",
        copy=False,
        help="Existing CFDIs to relate when issuing this invoice CFDI "
        "(e.g. substitution after cancellation).",
    )
    cfdi_document_relation_type = fields.Many2one(
        "l10n_mx_catalogs.c_tipo_relacion",
        string="Relation Type",
        copy=False,
        help="SAT catalog c_TipoRelacion for CfdiRelacionados.",
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
        string="CFDI Posted", compute="_compute_cfdi_posted", store=True
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

        res = super().action_post()

        for move in self:
            # Create the CFDIs if required
            if (
                move.l10n_mx_cfdi_auto
                and move.move_type == "out_invoice"
                and move.cfdi_required
                and move.cfdi_document_id.state != "published"
            ):
                move.create_invoice_cfdi()

        return res

    def _l10n_mx_edi_cfdi_invoice_append_addenda(self, cfdi, addenda):
        """Append an addenda block to a signed CFDI (Enterprise-compatible).

        :param cfdi: The stamped CFDI as bytes or str.
        :param addenda: ``ir.ui.view`` QWeb template marked as addenda.
        :return: CFDI bytes including the addenda.
        """
        self.ensure_one()
        if isinstance(cfdi, str):
            cfdi = cfdi.encode("utf-8")

        addenda_values = {"record": self, "cfdi": cfdi}
        rendered = (
            self.env["ir.qweb"]._render(addenda.id, values=addenda_values).strip()
        )
        if not rendered:
            return cfdi

        cfdi_node = etree.fromstring(cfdi)
        addenda_node = etree.fromstring(rendered)
        version = cfdi_node.get("Version") or "4.0"
        ns = f"http://www.sat.gob.mx/cfd/{version[0]}"

        # Add a root node Addenda if not specified explicitly by the user.
        if addenda_node.tag != f"{{{ns}}}Addenda":
            node = etree.Element(etree.QName(ns, "Addenda"))
            node.append(addenda_node)
            addenda_node = node

        cfdi_node.append(addenda_node)
        return etree.tostring(
            cfdi_node, pretty_print=True, xml_declaration=True, encoding="UTF-8"
        )

    def _l10n_mx_edi_cfdi_apply_partner_addenda(self, document):
        """Rewrite document XML with partner addenda after a successful stamp."""
        self.ensure_one()
        addenda = (
            self.partner_id.l10n_mx_edi_addenda
            or self.commercial_partner_id.l10n_mx_edi_addenda
        )
        if not addenda or not document.xml_file:
            return
        cfdi_bytes = base64.b64decode(document.xml_file)
        new_cfdi = self._l10n_mx_edi_cfdi_invoice_append_addenda(cfdi_bytes, addenda)
        if new_cfdi:
            document.xml_file = base64.b64encode(new_cfdi)

    def _l10n_mx_cfdi_post_document_attachments(self, document):
        """Post stamped XML/PDF on this record's chatter.

        Prefer files already stored on the document. If the PAC returned XML but
        no PDF, try PAC recover only (skip QWeb report rendering here — that is
        handled by ``_compute_download_files_if_needed`` on demand).
        """
        self.ensure_one()
        if not document.pdf_file and document.tracking_id:
            try:
                res = document.issuer_id.service_id.sudo().get_cfdi_pdf(
                    document.tracking_id
                )
                if res.get("Content"):
                    document.pdf_file = res["Content"]
                    document.pdf_filename = (
                        document.pdf_filename
                        or f"{document.name or document.uuid or document.id}.pdf"
                    )
            except Exception:
                _logger.debug(
                    "Could not recover PDF for chatter on %s",
                    document.display_name,
                    exc_info=True,
                )
        if not document.xml_file and document.tracking_id:
            try:
                res = document.issuer_id.service_id.sudo().get_cfdi_xml(
                    document.tracking_id
                )
                content = res.get("Content") or b""
                if content:
                    if isinstance(content, str):
                        content = content.encode("utf-8")
                    document.xml_file = base64.b64encode(content)
                    document.xml_filename = (
                        document.xml_filename
                        or f"{document.name or document.uuid or document.id}.xml"
                    )
            except Exception:
                _logger.debug(
                    "Could not recover XML for chatter on %s",
                    document.display_name,
                    exc_info=True,
                )

        attachment_vals = []
        if document.xml_file:
            attachment_vals.append(
                {
                    "name": document.xml_filename
                    or f"{document.uuid or document.id}.xml",
                    "datas": document.xml_file,
                    "res_model": self._name,
                    "res_id": self.id,
                    "type": "binary",
                    "mimetype": "application/xml",
                }
            )
        if document.pdf_file:
            attachment_vals.append(
                {
                    "name": document.pdf_filename
                    or f"{document.uuid or document.id}.pdf",
                    "datas": document.pdf_file,
                    "res_model": self._name,
                    "res_id": self.id,
                    "type": "binary",
                    "mimetype": "application/pdf",
                }
            )
        if not attachment_vals:
            return
        attachments = self.env["ir.attachment"].create(attachment_vals)
        self.message_post(
            body=self.env._("CFDI published"),
            attachment_ids=attachments.ids,
        )

    def create_invoice_cfdi(self):
        """
        Create the CFDI
        """
        self.ensure_one()

        self._validate_invoice_cfdi_required_fields()
        self._validate_cfdi_relation_fields()

        cert = self.env["l10n_mx_cfdi.document"].create(
            {
                "type": "I",
                "issuer_id": self.issuer_id.id,
                "receiver_id": self.receiver_id.id,
                "related_invoice_id": self.id,
            }
        )

        try:
            cfdi = self._gather_invoice_cfdi_data()
            cert.publish(cfdi)
            self._l10n_mx_edi_cfdi_apply_partner_addenda(cert)
            self._register_cfdi_document_relations(
                cert,
                self.cfdi_document_relations,
                self.cfdi_document_relation_type,
            )

            self.update(
                {
                    "related_cert_ids": [(4, cert.id)],
                }
            )
            self._l10n_mx_cfdi_post_document_attachments(cert)

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
            raise ValidationError(self.env._("Cannot generate the CFDI:\n") + err_msg)

    def _l10n_mx_cfdi_invoice_exportacion_complemento(self):
        """Return ``(exportacion, complemento)`` for the invoice CFDI.

        Extensions (e.g. Comercio Exterior) may override this hook.
        """
        return "01", None

    def _gather_invoice_cfdi_data(self):
        receiver = {
            "Name": self.receiver_id.name,
            "Rfc": self.receiver_id.vat,
            "CfdiUse": self.cfdi_use_id.code,
            "FiscalRegime": self.receiver_id.tax_regime.code,
            "TaxZipCode": self.receiver_id.zip,
        }
        global_information = None
        if self.receiver_id.vat == "XAXX010101000":
            currentDateTime = datetime.now()
            global_information = {
                "Periodicity": "01",
                "Months": str(currentDateTime.month).rjust(2, "0"),
                "Year": currentDateTime.year,
            }
            receiver["TaxZipCode"] = self.issuer_id.zip
            receiver["FiscalRegime"] = "616"

        exportacion, complemento = self._l10n_mx_cfdi_invoice_exportacion_complemento()
        return cfdi_builder.build_comprobante(
            issuer=self.issuer_id,
            receiver=receiver,
            conceptos=self.gather_invoice_cfdi_items_data(),
            tipo_de_comprobante="I",
            lugar_expedicion=self.issuer_id.zip,
            moneda=self.company_currency_id.name,
            forma_pago=self.payment_form_id.code,
            metodo_pago=self.payment_method_id.code,
            fecha=self._format_cfdi_date_str(self.invoice_date),
            informacion_global=global_information,
            cfdi_relacionados=self._get_cfdi_relacionados(),
            exportacion=exportacion,
            complemento=complemento,
        )

    def _validate_cfdi_relation_fields(self):
        """Ensure relation type and related CFDIs are set together."""
        self.ensure_one()
        if self.cfdi_document_relations and not self.cfdi_document_relation_type:
            raise ValidationError(
                self.env._(
                    "You must set a relation type when related CFDIs are selected."
                )
            )
        if self.cfdi_document_relation_type and not self.cfdi_document_relations:
            raise ValidationError(
                self.env._(
                    "You must add at least one related CFDI when a relation "
                    "type is set."
                )
            )

    def _get_cfdi_relacionados(self):
        """Build satcfdi CfdiRelacionados from manual invoice relation fields."""
        self.ensure_one()
        if not self.cfdi_document_relation_type:
            return None
        if not self.cfdi_document_relations:
            raise ValidationError(
                self.env._(
                    "You must add at least one related CFDI when a relation "
                    "type is set."
                )
            )
        missing_uuid = self.cfdi_document_relations.filtered(lambda d: not d.uuid)
        if missing_uuid:
            raise ValidationError(
                self.env._(
                    "Related CFDIs must be published and have a UUID: %s",
                    ", ".join(missing_uuid.mapped("display_name")),
                )
            )
        return cfdi40.CfdiRelacionados(
            tipo_relacion=self.cfdi_document_relation_type.code,
            cfdi_relacionado=list(self.cfdi_document_relations.mapped("uuid")),
        )

    def _register_cfdi_document_relations(self, cert, related_docs, relation_type):
        """Persist Odoo CFDI document relations after a successful stamp."""
        if not related_docs or not relation_type:
            return
        cert.write(
            {
                "related_document_ids": [
                    (
                        0,
                        0,
                        {
                            "source_id": cert.id,
                            "target_id": related_cfdi.id,
                            "relation_type_id": relation_type.id,
                        },
                    )
                    for related_cfdi in related_docs
                ]
            }
        )

    def _add_related_cfdis_data_if_needed(self, cfdi_data):
        """Compatibility helper used by tests; mutates a dict payload."""
        related = self._get_cfdi_relacionados()
        if related is None:
            return
        cfdi_data["Relations"] = {
            "Type": self.cfdi_document_relation_type.code,
            "Cfdis": [
                {"Uuid": related_cfdi.uuid}
                for related_cfdi in self.cfdi_document_relations
            ],
        }

    def _format_cfdi_date_str(self, document_date):
        """
        Format the date to be used in the CFDI

        This method will add the time to the document_date to make it
        compatible with the CFDI format. Then will format the date to
        ISO 8601 format.

        SAT/PAC reject Fecha older than 72 hours at stamp time, so when the
        document date is more than two days in the past we use "now" in the
        user timezone instead of keeping the stale calendar day.
        """
        fixed_tz_recordset = self.with_context(**{"tz": self.env.user.tz})
        now_utc = fields.Datetime.now()
        now_utc_tz = fields.Datetime.context_timestamp(fixed_tz_recordset, now_utc)

        if document_date and (now_utc_tz.date() - document_date).days > 2:
            # Outside the 72h stamp window — use current stamp time.
            document_dt = now_utc_tz.replace(tzinfo=None)
        else:
            document_dt = datetime.combine(document_date, now_utc_tz.time())

        return document_dt.strftime("%Y-%m-%dT%H:%M:%S")

    def gather_invoice_cfdi_items_data(self):
        """
        Gather the data for the CFDI items
        """
        self.ensure_one()

        cfdi_items_data = []
        for line in self.line_ids:
            if not line.product_id:
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
            if not line.product_id:
                continue

            if not line.product_id.l10n_mx_cfdi_product_code_id:
                err_msg += self.env._(
                    "- The product code has not been defined for the product %s\n",
                    line.product_id.name,
                )

            if not line.product_id.l10n_mx_cfdi_product_measurement_unit_id:
                err_msg += self.env._(
                    "- The unit of measure has not been defined for the product %s\n",
                    line.product_id.name,
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
                        self.env._(
                            "The tax code for tax %s is not defined.",
                            tax_id.name,
                        )
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
                        rec.env.ref("l10n_mx_cfdi_account.document_cancel_action")
                        .sudo()
                        .read()[0]
                    )

        return super().button_draft()

    def create_refund_cfdi(self):
        """
        Create CFDI of type 'E' (Egreso).

        Manual CFDI relations on the refund (PR #77 style) take precedence.
        Otherwise, related income CFDIs are inferred from reconciliations
        with TipoRelacion 01 (credit note).
        """
        for refund in self:
            refund._validate_cfdi_relation_fields()
            items_data = refund.gather_invoice_cfdi_items_data()

            relation_type = refund.cfdi_document_relation_type
            related_cfdis = refund.cfdi_document_relations
            cfdi_relacionados = refund._get_cfdi_relacionados()

            if cfdi_relacionados is None:
                related_domain = [
                    ("state", "=", "published"),
                    ("type", "=", "I"),
                    ("uuid", "!=", False),
                ]
                receivables = refund.line_ids.filtered(
                    lambda L: L.account_id.account_type == "asset_receivable"
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
                    related_domain
                )
                # Credit notes created via reverse often keep reversed_entry_id
                # even before receivable reconciliation finds the income CFDI.
                if not related_cfdis:
                    origin = refund.reversed_entry_id
                    if origin:
                        related_cfdis = origin.related_cert_ids.filtered_domain(
                            related_domain
                        )
                relation_type = self.env.ref("l10n_mx_catalogs.c_tipo_relacion_1")
                if related_cfdis:
                    cfdi_relacionados = cfdi40.CfdiRelacionados(
                        tipo_relacion=relation_type.code,
                        cfdi_relacionado=list(related_cfdis.mapped("uuid")),
                    )

            if not cfdi_relacionados:
                raise UserError(
                    self.env._(
                        "Cannot generate a credit note CFDI without related "
                        "income CFDIs. Reconcile the credit note with the "
                        "original invoice, or set Relation Type and Related "
                        "CFDIs on the CFDI tab."
                    )
                )

            receiver_partner = refund.receiver_id or refund.partner_id
            receiver = {
                "Name": receiver_partner.name,
                "Rfc": receiver_partner.vat,
                "CfdiUse": refund.cfdi_use_id.code,
                "FiscalRegime": receiver_partner.tax_regime.code,
                "TaxZipCode": receiver_partner.zip,
            }
            global_information = None
            if receiver_partner.vat == "XAXX010101000":
                currentDateTime = datetime.now()
                global_information = {
                    "Periodicity": "01",
                    "Months": str(currentDateTime.month).rjust(2, "0"),
                    "Year": currentDateTime.year,
                }
                receiver["TaxZipCode"] = refund.issuer_id.zip
                receiver["FiscalRegime"] = "616"

            cfdi = cfdi_builder.build_comprobante(
                issuer=refund.issuer_id,
                receiver=receiver,
                conceptos=items_data,
                tipo_de_comprobante="E",
                lugar_expedicion=refund.issuer_id.zip,
                moneda=(
                    refund.currency_id.name
                    if refund.currency_id
                    else refund.company_currency_id.name
                ),
                forma_pago=refund.payment_form_id.code,
                metodo_pago=refund.payment_method_id.code,
                fecha=refund._format_cfdi_date_str(refund.invoice_date),
                informacion_global=global_information,
                cfdi_relacionados=cfdi_relacionados,
            )

            refund_cfdi = self.env["l10n_mx_cfdi.document"].create(
                {
                    "type": "E",
                    "issuer_id": refund.issuer_id.id,
                    "receiver_id": refund.receiver_id.id,
                    "related_invoice_id": refund.id,
                }
            )

            try:
                refund_cfdi.publish(cfdi)
                refund._l10n_mx_edi_cfdi_apply_partner_addenda(refund_cfdi)
                refund._register_cfdi_document_relations(
                    refund_cfdi, related_cfdis, relation_type
                )

                refund.update(
                    {
                        "related_cert_ids": [(4, refund_cfdi.id)],
                    }
                )
                refund._l10n_mx_cfdi_post_document_attachments(refund_cfdi)

                for cfdi_doc in related_cfdis:
                    if cfdi_doc.related_invoice_id:
                        cfdi_doc.related_invoice_id.related_cert_ids |= refund_cfdi

            except Exception as e:
                refund_cfdi.unlink()
                raise e

    def _add_global_information_to_cfdi_if_required(self, cfdi_data):
        """Legacy helper kept for callers that still edit dict payloads."""
        if self.receiver_id.vat == "XAXX010101000":
            currentDateTime = datetime.now()

            cfdi_data["GlobalInformation"] = {
                "Periodicity": "01",  # Daily periodicity
                "Months": str(currentDateTime.month).rjust(2, "0"),
                "Year": currentDateTime.year,
            }

            cfdi_data["Receiver"]["TaxZipCode"] = self.issuer_id.zip
            cfdi_data["Receiver"]["FiscalRegime"] = "616"

    def _get_name_invoice_report(self):
        self.ensure_one()
        if self.company_id.account_fiscal_country_id.code == "MX":
            return "l10n_mx_cfdi_account.report_invoice_document"

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
            raise UserError(self.env._("No XML attachment found for this invoice."))

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
                self.env._(
                    "Cannot find the receptor of the certificate. RFC: %s",
                    receiver.attrib["Rfc"],
                )
            )

        cfdi_use = receiver.attrib["UsoCFDI"]
        return receiver_id, cfdi_use

    def _resolve_issuer_from_xml(self, namespaces, root):
        # get issuer
        issuer = root.find("cfdi:Emisor", namespaces)
        issuer_id = self.env["l10n_mx_cfdi.issuer"].search(
            [("vat", "=", issuer.attrib["Rfc"])],
            limit=1,
        )
        if not issuer_id:
            # find partner
            partner_id = self.env["res.partner"].search(
                [("vat", "=", issuer.attrib["Rfc"])],
                limit=1,
            )
            if not partner_id:
                raise UserError(
                    self.env._(
                        "Cannot find the partner who emitted the certificate. RFC: %s",
                        issuer.attrib["Rfc"],
                    )
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
            raise UserError(self.env._("The CFDI has been published."))

        if self.move_type == "out_invoice":
            self.create_invoice_cfdi()

        if self.move_type == "out_refund":
            if self.state != "posted":
                raise UserError(
                    self.env._("Confirm the credit note before generating its CFDI.")
                )
            # create credit note CFDI if required
            if self.amount_residual != 0:
                raise UserError(
                    self.env._(
                        "You cannot generate a CFDI for a credit note with a "
                        "pending amount."
                    )
                )
            self.create_refund_cfdi()
