import base64
import json
import re
from io import BytesIO

import qrcode
from dateutil import parser

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class Document(models.Model):
    _name = "l10n_mx_cfdi.document"
    _description = "CFDI document"

    ###
    # Certificate fields
    ###
    type = fields.Selection(
        [
            ("I", "Ingreso"),
            ("E", "Egreso"),
            ("P", "Pago"),
            ("T", "Traslado"),
        ],
        readonly=True,
    )

    version = fields.Char(default="4.0")
    serie = fields.Char()
    folio = fields.Char()
    name = fields.Char(
        string="Nombre", readonly=True, compute="_compute_name", store=True
    )

    uuid = fields.Char(string="UUID", readonly=True, help="UUID asignado por el SAT")

    issuer_id = fields.Many2one(
        "l10n_mx_cfdi.issuer",
        string="Emisor",
        required=True,
        domain=[("registered", "=", True)],
    )

    receiver_id = fields.Many2one("res.partner", string="Receptor", required=True)

    tracking_id = fields.Char(string="ID del documento en el API", readonly=True)

    pdf_file = fields.Binary(string="Archivo PDF", attachment=True, readonly=True)
    xml_file = fields.Binary(string="Archivo XML", attachment=True, readonly=True)

    is_global_note = fields.Boolean(string="Nota global", readonly=True, default=False)

    ###
    # Auxiliary fields
    ###
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("pending", "Pendiente"),
            ("published", "Publicada"),
            ("pending_cancel", "Cancelación pendiente"),
            ("canceled", "Cancelada"),
            ("unknown", "Desconocido"),
        ],
        default="draft",
        string="Estado",
        readonly=True,
    )

    pdf_filename = fields.Char(string="Nombre del archivo PDF", readonly=True)
    xml_filename = fields.Char(string="Nombre del archivo XML", readonly=True)

    cert_data_json = fields.Char(readonly=True)

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )

    standalone = fields.Boolean(
        string="Independiente",
        compute="_compute_standalone",
        store=True,
        help="Si está marcado, el certificado no esta relacionado "
        "a otros documentos del sistema",
    )

    cancellation_request_proof_file = fields.Binary(
        string="Acuse de solicitud de cancelación", attachment=True, readonly=True
    )
    cancellation_request_proof_filename = fields.Char(
        string="Nombre del archivo de acuse de solicitud de cancelación", readonly=True
    )

    # used to download the files on demand
    files_in_cache = fields.Boolean(
        readonly=True, compute="_compute_download_files_if_needed", store=False
    )

    issuing_datetime = fields.Datetime(
        string="Fecha de emisión", readonly=True, compute="_compute_load_json_data"
    )
    cert_number = fields.Char(
        string="Número de certificado", readonly=True, compute="_compute_load_json_data"
    )
    original_string = fields.Char(
        string="Cadena original", readonly=True, compute="_compute_load_json_data"
    )
    cfdi_signature = fields.Char(
        string="Firma del CFDI", readonly=True, compute="_compute_load_json_data"
    )
    sat_signature = fields.Char(
        string="Firma del SAT", readonly=True, compute="_compute_load_json_data"
    )
    sat_cert_number = fields.Char(
        string="Número de certificado del SAT",
        readonly=True,
        compute="_compute_load_json_data",
    )
    rfc_prov_certif = fields.Char(
        string="RFC del proveedor de certificación",
        readonly=True,
        compute="_compute_load_json_data",
    )
    signing_date = fields.Datetime(
        string="Fecha de timbrado", readonly=True, compute="_compute_load_json_data"
    )
    related_document_ids = fields.One2many(
        "l10n_mx_cfdi.document_relation", "source_id", string="Documentos relacionados"
    )
    tax_codes = fields.Char(
        string="Código de impuesto", readonly=True, compute="_compute_load_json_data"
    )

    verification_url = fields.Char(
        string="URL de verificación", readonly=True, compute="_compute_load_json_data"
    )
    verification_qr_code = fields.Binary(
        string="Código QR de Verificación",
        readonly=True,
        compute="_compute_load_json_data",
    )

    # utility fields
    l10n_mx_cfdi_auto = fields.Boolean(
        string="CFDI Automatico", related="company_id.l10n_mx_cfdi_auto", readonly=True
    )

    l10n_mx_cfdi_enabled = fields.Boolean(
        string="CFDI Habilitado",
        related="company_id.l10n_mx_cfdi_enabled",
        readonly=True,
    )

    @api.depends("cert_data_json")
    def _compute_load_json_data(self):
        for rec in self:
            if rec.cert_data_json:
                data = json.loads(rec.cert_data_json)
                rec.issuing_datetime = parser.parse(data["Date"])
                rec.cert_number = data["CertNumber"]
                rec.original_string = data["OriginalString"]
                rec.cfdi_signature = data["Complement"]["TaxStamp"]["CfdiSign"]
                rec.sat_signature = data["Complement"]["TaxStamp"]["SatSign"]
                rec.sat_cert_number = data["Complement"]["TaxStamp"]["SatCertNumber"]
                rec.rfc_prov_certif = data["Complement"]["TaxStamp"]["RfcProvCertif"]
                rec.signing_date = parser.parse(data["Complement"]["TaxStamp"]["Date"])
                rec.verification_url = self._generate_verification_url(
                    rec.uuid,
                    rec.issuer_id.vat,
                    rec.receiver_id.vat,
                    data["Total"],
                    rec.cfdi_signature[-8:],
                )
                rec.verification_qr_code = self._generate_qr_code(
                    rec.verification_url.encode("utf-8")
                )
                rec.tax_codes = self._load_tax_code_from_json_data(data)

    @api.model
    def _load_tax_code_from_json_data(self, data):
        taxes = set()
        if "Taxes" in data:
            for tax in data["Taxes"]:
                if tax["Name"] == "ISR":
                    taxes.add("001")
                if tax["Name"] == "IVA":
                    taxes.add("002")
                if tax["Name"] == "IEPS":
                    taxes.add("003")

        return ",".join(taxes)

    @api.depends("pdf_file", "xml_file")
    def _generate_verification_url(
        self, uuid, issuer_cfdi, receiver_cfdi, total, sign_extract
    ):
        url = (
            f"https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx?"
            f"id={uuid}&"
            f"re={issuer_cfdi}&"
            f"rr={receiver_cfdi}&"
            f"tt={total}&"
            f"fe={sign_extract}"
        )
        return url

    def _generate_qr_code(self, data):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_Q,
            box_size=4,
            border=0,
        )

        qr.add_data(data)
        img = qr.make_image(fit=True)
        temp = BytesIO()
        img.save(temp, format="PNG")
        qr_image = base64.b64encode(temp.getvalue())
        return qr_image

    ###
    # Computed fields generation functions
    ###

    @api.depends("tracking_id")
    def _compute_download_files_if_needed(self):
        for entry in self:
            if entry.tracking_id:
                # if not entry.pdf_file:
                #     report, resource_ids = self._resolve_report()
                #
                #     if report:
                #         # force the report to be rendered to work around a bug
                #         # in _render_qweb_pdf
                #         report = report.with_context(**{"force_report_rendering": True})
                #         doc_data, doc_format = report._render_qweb_pdf(resource_ids)
                #         # in some scenarios, the report is not generated,
                #         # so we need to check if the file is empty
                #         if doc_data:
                #             result = base64.b64encode(doc_data)
                #             entry.pdf_file = result
                #
                #     if not entry.pdf_file:
                #         # fallback to the provider's PDF
                #         res = entry.issuer_id.service_id.sudo().get_cfdi_pdf(
                #             entry.tracking_id
                #         )
                #         entry.pdf_file = res["Content"]
                #
                #     # set filename
                #     entry.pdf_filename = "%s.pdf" % entry.name

                if not entry.xml_file:
                    res = entry.issuer_id.service_id.sudo().get_cfdi_xml(
                        entry.tracking_id
                    )
                    entry.xml_file = res["Content"].encode("utf-8")
                    entry.xml_filename = "%s.xml" % entry.name

                entry.files_in_cache = True
            else:
                entry.files_in_cache = False

    # def _resolve_report(self):
    #     """Returns the report and resource IDs for generating the PDF file."""
    #     report = None
    #     resource_ids = []
    #
    #     if self.type in ("I", "E") and self.related_invoice_id:
    #         report = self.env.ref("account.account_invoices")
    #         resource_ids = [self.related_invoice_id.id]
    #
    #     if self.type == "P" and self.related_payment_id:
    #         report = self.env.ref("account.action_report_payment_receipt")
    #         resource_ids = [self.related_payment_id.id]
    #
    #     return report, resource_ids

    @api.depends("serie", "folio")
    def _compute_name(self):
        for entry in self:
            if entry.serie:
                entry.name = f"{entry.serie}-{entry.folio}"
            else:
                entry.name = "%s" % entry.folio

    @api.depends("type")
    def _compute_standalone(self):
        # only documents of type 'T' are considered standalone
        for entry in self:
            entry.standalone = entry.type == "T"

    ###
    # Model methods
    ###

    def create(self, vals_list):
        # Set values to serie and folio from sequence if not provided

        # check if vals_list is a list of dictionaries
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        # for vals in vals_list:
        #     if "serie" not in vals or "folio" not in vals:
        #         issuer = self._resolve_issuer_on_create(vals)
        #         if (
        #             issuer.use_origin_document_sequence
        #             and vals.get("type", False) != "T"
        #             and vals.get("is_global_note", False) is False
        #         ):
        #             self._set_serie_and_folio_from_document_sequence(vals)
        #         else:
        #             self._set_serie_and_folio_from_cfdi_sequence(vals)

        # Create certificate
        return super().create(vals_list)

    def _resolve_issuer_on_create(self, vals):
        issuer_id = vals.get("issuer_id", False)
        if not issuer_id:
            raise UserError(_("Issuer is required to generate a new document."))

        return self.env["l10n_mx_cfdi.issuer"].browse(issuer_id)

    def _set_serie_and_folio_from_cfdi_sequence(self, vals):
        sequence_id = self.get_sequence_for_cfdi_type(vals)

        vals["serie"] = sequence_id.prefix
        vals["folio"] = sequence_id.number_next

        sequence_id.next_by_id(sequence_id.id)

    # def _set_serie_and_folio_from_document_sequence(self, vals):
    #     serie = ""
    #     folio = ""
    #     document_name = ""
    #
    #     if "related_invoice_id" in vals:
    #         invoice = self.env["account.move"].browse(vals["related_invoice_id"])
    #         document_name = invoice.name
    #
    #     if "related_payment_id" in vals:
    #         payment = self.env["account.payment"].browse(vals["related_payment_id"])
    #         document_name = payment.name
    #
    #     if not document_name:
    #         raise UserError(_("Unable to determine the origin document name."))
    #
    #     # extract numeric postfix from invoice name using regex
    #     match = re.search(r"\d+$", document_name)
    #     if match:
    #         folio = match.group()
    #         serie = document_name[: -len(match.group())]
    #     else:
    #         raise UserError(_("Invoice name does not contain a numeric postfix."))
    #
    #     # remove non-alphanumeric characters from serie
    #     serie = re.sub(r"\W+", "", serie)
    #
    #     vals["serie"] = serie
    #     vals["folio"] = folio

    @api.model
    def get_sequence_for_cfdi_type(self, vals_list):
        issuer_id = self.env["l10n_mx_cfdi.issuer"].browse(vals_list["issuer_id"])

        if vals_list["type"] == "I":
            return issuer_id.invoice_sequence_id
        elif vals_list["type"] == "E":
            return issuer_id.refund_sequence_id
        elif vals_list["type"] == "P":
            return issuer_id.payment_sequence_id
        elif vals_list["type"] == "T":
            return issuer_id.transfer_sequence_id
        else:
            raise UserError(_("Type of certificate unknown."))

    def cancel(self, reason: str, replacement=None, simulate=False):
        self.ensure_one()

        if self.state != "published":
            return

        if not simulate:
            res = self.issuer_id.service_id.sudo().cancel_cfdi(
                self.tracking_id, reason, replacement
            )
            if (
                res["Status"] == "canceled"
                or res["Status"] == "acepted"
                or res["Status"] == "expired"
            ):
                self.state = "canceled"
                self.pdf_file = False
                self.xml_file = False
            elif res["Status"] == "pending":
                self.state = "pending_cancel"
            elif res["Status"] == "rejected":
                self.state = "published"
            else:
                raise UserError(
                    _("Error when cancelling the certificate: %s") % res["Message"]
                )
        else:
            self.state = "canceled"

    def publish(self, cfdi_data):
        self.ensure_one()

        if "Serie" not in cfdi_data:
            cfdi_data["Serie"] = self.serie

        if "Folio" not in cfdi_data:
            cfdi_data["Folio"] = self.folio

        if "CfdiType" not in cfdi_data:
            cfdi_data["CfdiType"] = self.type

        if "Issuer" not in cfdi_data:
            cfdi_data["Issuer"] = {
                "Name": (
                    self.issuer_id.fiscal_name
                    if hasattr(self.issuer_id, "fiscal_name")
                    else self.issuer_id.name
                ),
                "Rfc": self.issuer_id.vat,
                "FiscalRegime": self.issuer_id.tax_regime.code,
            }

        if "LogoUrl" not in cfdi_data and self.issuer_id.logo_url:
            cfdi_data["LogoUrl"] = self.issuer_id.logo_url

        for entry in self:
            if entry.state != "draft":
                raise UserError(_("The certificate is not in draft."))

            # Ensure no other published certificates share the same series and folio.
            similar_certificates_count = self.search(
                [
                    ("serie", "=", entry.serie),
                    ("folio", "=", entry.folio),
                    ("state", "=", "published"),
                ],
                count=True,
            )

            if similar_certificates_count > 0:
                raise UserError(
                    _(
                        "A certificate is already published with this serie "
                        "and number."
                    )
                )

            # use sudo to allow users to publish certificates
            res = entry.issuer_id.service_id.sudo().create_cfdi(cfdi_data)

            # store result for later usage
            self.cert_data_json = json.dumps(res)

            if res["Status"] == "active":
                self.uuid = res["Complement"]["TaxStamp"]["Uuid"]
                self.tracking_id = res["Id"]
                self.state = "published"
            else:
                raise UserError(
                    _("Error when publishing the certificate: %s") % res["Message"]
                )

    def action_cancel(self):
        self.ensure_one()

        return {
            "name": "Cancel certificate",
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "l10n_mx_cfdi.document_cancel",
            "target": "new",
            "context": {"default_certificate_ids": [(6, 0, [self.id])]},
        }

    def action_check_status(self):
        self.ensure_one()

        service = self.issuer_id.service_id.sudo()
        amount_total = 0
        # if self.related_invoice_id:
        #     amount_total = self.related_invoice_id.amount_total
        #
        # if self.related_payment_id:
        #     amount_total = self.related_payment_id.amount

        status = service.check_cfdi_status(
            self.uuid, self.issuer_id.vat, self.receiver_id.vat, amount_total
        )

        if self.state != status:
            self.state = status

    def action_get_cancellation_request_proof(self):
        self.ensure_one()

        # check that the certificate is canceled
        if self.state != "canceled":
            raise UserError(_("The certificate is not cancelled."))

        service = self.issuer_id.service_id.sudo()

        file = service.get_cancellation_request_proof(self.tracking_id)
        self.cancellation_request_proof_file = file
        self.cancellation_request_proof_filename = (
            "Solicitud de cancelación %s.pdf" % self.name
        )


class DocumentRelation(models.Model):
    _name = "l10n_mx_cfdi.document_relation"
    _description = "Describe a relation between two CFDIs"

    relation_type_id = fields.Many2one(
        "l10n_mx_catalogs.c_tipo_relacion", required=True
    )
    source_id = fields.Many2one(
        "l10n_mx_cfdi.document", required=True, ondelete="cascade"
    )
    target_id = fields.Many2one(
        "l10n_mx_cfdi.document", required=True, ondelete="cascade"
    )
