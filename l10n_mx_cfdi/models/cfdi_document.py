import base64
import json
import logging
from io import BytesIO

import qrcode
from dateutil import parser

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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
    pac_provider = fields.Char(
        string="PAC Provider",
        readonly=True,
        help="satcfdi PAC code used when the CFDI was stamped.",
    )
    legacy_without_xml = fields.Boolean(
        string="Legacy without XML",
        compute="_compute_legacy_without_xml",
        help="Published CFDI without stored stamped XML (typically Facturama-era). "
        "Cancel/download via satcfdi is not available for these documents.",
    )

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
    pac_supports_cancel = fields.Boolean(
        related="issuer_id.service_id.supports_cancel",
        readonly=True,
    )

    @api.depends("xml_file", "state", "tracking_id")
    def _compute_legacy_without_xml(self):
        for rec in self:
            rec.legacy_without_xml = bool(
                rec.state in ("published", "pending_cancel", "canceled")
                and rec.tracking_id
                and not rec.xml_file
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
            if not entry.tracking_id:
                entry.files_in_cache = False
                continue

            if not entry.pdf_file:
                report, resource_ids = self._resolve_report()
                if report:
                    report = report.with_context(**{"force_report_rendering": True})
                    doc_data, _doc_format = report._render_qweb_pdf(resource_ids)
                    if doc_data:
                        entry.pdf_file = base64.b64encode(doc_data)
                if not entry.pdf_file:
                    try:
                        res = entry.issuer_id.service_id.sudo().get_cfdi_pdf(
                            entry.tracking_id
                        )
                        entry.pdf_file = res["Content"]
                    except UserError:
                        _logger.debug(
                            "Could not recover PDF for CFDI %s", entry.display_name
                        )
                if entry.pdf_file:
                    entry.pdf_filename = f"{entry.name}.pdf"

            if not entry.xml_file:
                try:
                    res = entry.issuer_id.service_id.sudo().get_cfdi_xml(
                        entry.tracking_id
                    )
                    content = res["Content"]
                    if isinstance(content, str):
                        content = content.encode("utf-8")
                    entry.xml_file = base64.b64encode(content)
                    entry.xml_filename = f"{entry.name}.xml"
                except UserError:
                    _logger.debug(
                        "Could not recover XML for CFDI %s", entry.display_name
                    )

            entry.files_in_cache = True

    @api.depends("serie", "folio")
    def _compute_name(self):
        for entry in self:
            if entry.serie:
                entry.name = f"{entry.serie}-{entry.folio}"
            else:
                entry.name = f"{entry.folio}"

    @api.depends("type")
    def _compute_standalone(self):
        # only documents of type 'T' are considered standalone
        for entry in self:
            entry.standalone = entry.type == "T"

    ###
    # Model methods
    ###

    def _resolve_report(self):
        """Return report and resource ids for PDF generation (extended in account)."""
        return None, []

    def cancel(self, reason: str, replacement=None, simulate=False):
        """Cancel the CFDI through the PAC.

        Returns a feedback dict with keys ``Status``, ``Message``,
        ``HasAcuse`` so wizards can show clear post-cancel feedback.
        """
        self.ensure_one()

        if self.state != "published":
            return {
                "Status": self.state,
                "Message": self.env._("Document is not published."),
                "HasAcuse": bool(self.cancellation_request_proof_file),
            }

        if not simulate:
            service = self.issuer_id.service_id.sudo()
            if self.legacy_without_xml:
                raise UserError(
                    self.env._(
                        "This CFDI has no stored stamped XML (legacy Facturama "
                        "document). Cancel it manually at the SAT / previous PAC "
                        "or attach the CFDI XML before retrying."
                    )
                )
            if not service.supports_cancel:
                raise UserError(
                    self.env._("The configured PAC does not support CFDI cancellation.")
                )
            xml_bytes = None
            if self.xml_file:
                xml_bytes = base64.b64decode(self.xml_file)
            if not xml_bytes:
                raise UserError(
                    self.env._(
                        "Cannot cancel CFDI without the stamped XML stored on "
                        "the document."
                    )
                )
            res = service.cancel_cfdi(
                xml_bytes,
                reason,
                uuid_replacement=replacement,
                issuer=self.issuer_id,
                document_id=self.tracking_id,
            )
            if res["Status"] in ("canceled", "acepted", "expired"):
                self.state = "canceled"
                self.pdf_file = False
                # keep xml_file for audit; optional clear not required
            elif res["Status"] == "pending":
                self.state = "pending_cancel"
            elif res["Status"] == "rejected":
                self.state = "published"
            elif res["Status"] == "active":
                raise UserError(
                    self.env._(
                        "The PAC could not cancel CFDI %(cfdi)s: it is still "
                        "active (often because related documents block "
                        "cancellation). PAC message: %(message)s",
                        cfdi=self.name or self.uuid or self.id,
                        message=res.get("Message") or res["Status"],
                    )
                )
            else:
                raise UserError(
                    self.env._(
                        "Error when cancelling the certificate: %s", res["Message"]
                    )
                )
            if res.get("Acuse"):
                self.cancellation_request_proof_file = base64.b64encode(res["Acuse"])
                self.cancellation_request_proof_filename = (
                    f"Acuse de cancelación {self.name}.xml"
                )
            return {
                "Status": res["Status"],
                "Message": res.get("Message") or "",
                "HasAcuse": bool(res.get("Acuse")),
            }

        self.state = "canceled"
        return {
            "Status": "canceled",
            "Message": self.env._("Simulated cancellation (PAC not called)."),
            "HasAcuse": False,
        }

    def _format_cancel_feedback(self, feedback):
        """Build a user-facing summary after a cancel attempt."""
        self.ensure_one()
        feedback = feedback or {}
        status = feedback.get("Status") or self.state
        message = (feedback.get("Message") or "").strip()
        has_acuse = bool(feedback.get("HasAcuse"))
        state_label = dict(self._fields["state"].selection).get(self.state, self.state)
        parts = [
            self.env._(
                "CFDI %(name)s: cancellation status %(status)s "
                "(document state: %(state)s).",
                name=self.name or self.uuid or self.id,
                status=status,
                state=state_label,
            )
        ]
        if message:
            parts.append(self.env._("PAC message: %s", message))
        if has_acuse:
            parts.append(self.env._("Cancellation acknowledgment (acuse) was stored."))
        else:
            parts.append(
                self.env._(
                    "The PAC did not return a cancellation acknowledgment (acuse)."
                )
            )
        return " ".join(parts)

    @api.model
    def _series_codes_for_type(self, doc_type):
        return {
            "I": ["INV", "I"],
            "E": ["EGR", "NC", "E"],
            "P": ["PAG", "P"],
            "T": ["TRA", "CP", "T"],
        }.get(doc_type, [])

    @api.model
    def _prepare_serie_folio_vals(self, vals):
        """Assign serie/folio from l10n_mx_cfdi.series when missing.

        Facturama Multiemisor requires Folio. Empty serie+folio also made the
        uniqueness check in ``publish`` treat every subsequent CFDI as a
        duplicate of the first published blank-folio document.
        """
        if vals.get("folio"):
            return vals
        Series = self.env["l10n_mx_cfdi.series"]
        codes = self._series_codes_for_type(vals.get("type"))
        series = Series.search([("code", "in", codes)], limit=1) if codes else Series
        if not series:
            series = Series.search([], limit=1)
        if not series:
            return vals
        vals.setdefault("serie", series.prefix or series.code or False)
        full = series.next_by_id()
        prefix = series.prefix or ""
        folio = full[len(prefix) :] if prefix and str(full).startswith(prefix) else full
        vals["folio"] = str(folio).lstrip("0") or str(folio) or str(full)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._prepare_serie_folio_vals(vals)
        return super().create(vals_list)

    def publish(self, cfdi):
        self.ensure_one()

        for entry in self:
            if entry.state != "draft":
                raise UserError(self.env._("The certificate is not in draft."))

            # Only enforce uniqueness when serie/folio are actually set.
            # Blank+blank matched every published CFDI and blocked E/P/T after I.
            if entry.serie or entry.folio:
                similar_certificates_count = self.search_count(
                    [
                        ("serie", "=", entry.serie),
                        ("folio", "=", entry.folio),
                        ("state", "=", "published"),
                        ("id", "!=", entry.id),
                    ],
                )

                if similar_certificates_count > 0:
                    raise UserError(
                        self.env._(
                            "A certificate is already published with this "
                            "serie and number."
                        )
                    )

            # Fill serie/folio on satcfdi Comprobante when missing
            if hasattr(cfdi, "get"):
                if entry.serie and not cfdi.get("Serie"):
                    cfdi["Serie"] = entry.serie
                if entry.folio and not cfdi.get("Folio"):
                    cfdi["Folio"] = entry.folio

            res = entry.issuer_id.service_id.sudo().create_cfdi(
                cfdi, issuer=entry.issuer_id
            )

            if res.get("status") != "published":
                raise UserError(
                    self.env._(
                        "Error when publishing the certificate: %s",
                        res.get("Message") or res.get("status"),
                    )
                )

            stamp_meta = res.get("stamp_meta") or {}
            # PAC helpers may leave callables in meta; never let that roll back a stamp
            entry.cert_data_json = json.dumps(stamp_meta, default=str)
            entry.uuid = res.get("uuid")
            entry.tracking_id = res.get("tracking_id")
            entry.pac_provider = entry.issuer_id.service_id.provider
            if res.get("xml"):
                xml = res["xml"]
                if isinstance(xml, str):
                    xml = xml.encode("utf-8")
                entry.xml_file = base64.b64encode(xml)
                entry.xml_filename = f"{entry.name or entry.uuid}.xml"
            if res.get("pdf"):
                entry.pdf_file = base64.b64encode(res["pdf"])
                entry.pdf_filename = f"{entry.name or entry.uuid}.pdf"
            entry.state = "published"

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
        if "related_invoice_id" in self._fields and self.related_invoice_id:
            amount_total = self.related_invoice_id.amount_total
        elif "related_payment_id" in self._fields and self.related_payment_id:
            amount_total = self.related_payment_id.amount

        status = service.check_cfdi_status(
            self.uuid, self.issuer_id.vat, self.receiver_id.vat, amount_total
        )

        if self.state != status:
            self.state = status

    def action_get_cancellation_request_proof(self):
        self.ensure_one()

        if self.state != "canceled":
            raise UserError(self.env._("The certificate is not cancelled."))

        if self.cancellation_request_proof_file:
            return

        raise UserError(
            self.env._(
                "No cancellation acknowledgment is stored for this document. "
                "Re-canceling with a PAC that returns an acuse is required."
            )
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
