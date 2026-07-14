# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
import logging
import zipfile
from datetime import datetime, timedelta
from io import BytesIO

from lxml import etree

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services import (
    MX_TZ,
    SAFE_XML_PARSER,
    SAT_CODE_DAILY_LIMIT,
    SAT_CODE_DUPLICATE_LIFETIME,
    SAT_CODE_MAX_ELEMENTS,
    SAT_CODE_NO_INFO,
    SAT_CODE_SUCCESS,
    SAT_DEFAULT_SYNC_DAYS,
    SAT_DOWNLOAD_EXPIRED,
    SAT_DOWNLOAD_MAX_REACHED,
    SAT_METADATA_DEFAULT_WINDOW_DAYS,
    SAT_METADATA_MIN_WINDOW_HOURS,
    SAT_REJECT_CODES,
    SAT_REQUEST_STATUS_ACCEPTED,
    SAT_REQUEST_STATUS_ERROR,
    SAT_REQUEST_STATUS_EXPIRED,
    SAT_REQUEST_STATUS_LABELS,
    SAT_REQUEST_STATUS_PROCESSING,
    SAT_REQUEST_STATUS_READY,
    SAT_REQUEST_STATUS_REJECTED,
    SAT_STATUS_CODE_LABELS,
    sat_int,
    sat_str,
)
from ..services.sat_metadata import (
    build_request_fingerprint,
    parse_metadata_content,
)

_logger = logging.getLogger(__name__)

# Active states: do not recreate identical fingerprint while one is open.
_ACTIVE_REQUEST_STATES = ("draft", "requested", "processing", "ready", "downloading")
_IMMEDIATE_PROCESS_STATES = ("draft", "ready", "downloading")
_WAITING_SAT_STATES = ("requested", "processing")
_VERIFY_RETRY_MINUTES = 15

_SYNC_PENDING_PARAM = "l10n_mx_sat.sync_pending_company_ids"
_QUEUED_REQUESTS_PARAM = "l10n_mx_sat.queued_request_ids"
_CRON_BATCH_SIZE = 4  # 0 = unlimited (tests)


class L10nMxSatDownloadRequest(models.Model):
    _name = "l10n_mx_sat.download.request"
    _description = "SAT Download Request"
    _order = "create_date desc"

    name = fields.Char(string="Description", compute="_compute_name", store=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    document_kind = fields.Selection(
        selection=[
            ("cfdi", "CFDI"),
            ("retention", "Retention"),
        ],
        string="Document kind",
        required=True,
        default="cfdi",
        index=True,
    )
    direction = fields.Selection(
        selection=[
            ("issued", "Issued"),
            ("received", "Received"),
        ],
        required=True,
        default="received",
        index=True,
    )
    request_type = fields.Selection(
        selection=[
            ("xml", "XML"),
            ("metadata", "Metadata"),
        ],
        string="Request type",
        required=True,
        default="xml",
        index=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("requested", "Requested"),
            ("processing", "Processing"),
            ("ready", "Ready"),
            ("downloading", "Downloading"),
            ("done", "Completed"),
            ("error", "Error"),
        ],
        default="draft",
        required=True,
        readonly=True,
        index=True,
    )
    date_from = fields.Datetime(string="From", required=True)
    date_to = fields.Datetime(string="To", required=True)
    sat_request_id = fields.Char(string="SAT request ID", readonly=True)
    request_fingerprint = fields.Char(
        string="Request fingerprint",
        readonly=True,
        index=True,
    )
    package_ids = fields.One2many(
        comodel_name="l10n_mx_sat.download.package",
        inverse_name="request_id",
        string="Packages",
        readonly=True,
    )
    document_ids = fields.One2many(
        comodel_name="l10n_mx_sat.document",
        inverse_name="download_request_id",
        string="Documents",
        readonly=True,
    )
    error_message = fields.Text(string="Error message", readonly=True)
    next_process_at = fields.Datetime(
        string="Next process at",
        readonly=True,
        index=True,
        help="Earliest datetime when the cron should verify this request again "
        "after the SAT accepted it but has not finished processing.",
    )
    document_count = fields.Integer(string="Processed documents", readonly=True)
    reported_cfdi_count = fields.Integer(string="SAT reported CFDIs", readonly=True)
    can_retry = fields.Boolean(
        string="Can retry",
        compute="_compute_can_retry",
    )

    _request_fingerprint_uniq = models.Constraint(
        "UNIQUE(request_fingerprint)",
        "A SAT download request with the same company and date range already exists.",
    )

    @api.depends(
        "company_id.vat",
        "company_id.l10n_mx_sat_fiel_cer",
        "company_id.l10n_mx_sat_fiel_key",
        "company_id.l10n_mx_sat_fiel_password",
        "document_kind",
        "direction",
        "request_type",
        "date_from",
        "date_to",
    )
    def _compute_name(self):
        fields_info = self.fields_get(["document_kind", "direction", "request_type"])
        kind_labels = dict(fields_info["document_kind"]["selection"])
        direction_labels = dict(fields_info["direction"]["selection"])
        type_labels = dict(fields_info["request_type"]["selection"])
        for rec in self:
            rfc = rec._get_display_rfc(rec.company_id)
            kind = kind_labels.get(rec.document_kind, "?")
            direction = direction_labels.get(rec.direction, "?")
            req_type = type_labels.get(rec.request_type, "?")
            fi = rec.date_from.strftime("%Y-%m-%d") if rec.date_from else "?"
            ff = rec.date_to.strftime("%Y-%m-%d") if rec.date_to else "?"
            rec.name = f"{rfc} / {kind} / {direction} / {req_type} / {fi} - {ff}"

    @api.model
    def _get_display_rfc(self, company):
        """Resolve RFC for labels, falling back to FIEL when VAT is empty."""
        rfc = company.vat.strip().upper() if company.vat else False
        if not rfc and company.l10n_mx_sat_has_credentials():
            try:
                rfc = company.l10n_mx_sat_get_rfc()
            except Exception:
                rfc = False
        return rfc or company.name or "?"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("request_fingerprint"):
                vals["request_fingerprint"] = self._build_fingerprint_from_vals(vals)
            if self.search(
                [("request_fingerprint", "=", vals["request_fingerprint"])], limit=1
            ):
                raise ValidationError(
                    self.env._(
                        "A SAT download request with the same parameters "
                        "already exists."
                    )
                )
        return super().create(vals_list)

    @api.model
    def _build_fingerprint_from_vals(self, vals):
        company_id = vals.get("company_id") or self.env.company.id
        date_from = vals.get("date_from")
        date_to = vals.get("date_to")
        if isinstance(date_from, str):
            date_from = fields.Datetime.to_datetime(date_from)
        if isinstance(date_to, str):
            date_to = fields.Datetime.to_datetime(date_to)
        return build_request_fingerprint(
            company_id,
            vals.get("document_kind"),
            vals.get("direction"),
            vals.get("request_type"),
            date_from,
            date_to,
        )

    @api.depends("state", "error_message")
    def _compute_can_retry(self):
        non_retryable = (SAT_CODE_DUPLICATE_LIFETIME, SAT_CODE_DAILY_LIMIT)
        for rec in self:
            if rec.state != "error":
                rec.can_retry = False
                continue
            msg = rec.error_message or ""
            rec.can_retry = not any(code in msg for code in non_retryable)

    def _sat_request_status_label(self, status):
        label = SAT_REQUEST_STATUS_LABELS.get(status)
        return self.env._(label) if label else str(status)

    def _sat_status_code_label(self, code):
        if not code:
            return self.env._("(empty)")
        label = SAT_STATUS_CODE_LABELS.get(code)
        return self.env._(label) if label else code

    def _selection_label(self, field_name, value):
        if not value:
            return value
        selection = dict(self.fields_get([field_name])[field_name]["selection"])
        return selection.get(value, value)

    def _write_request_error(self, cod_estatus, message):
        code_label = self._sat_status_code_label(cod_estatus)
        self.write(
            {
                "state": "error",
                "error_message": self.env._(
                    "SAT rejected the download request. "
                    "CodEstatus=%(code)s (%(label)s). SAT message: %(message)s",
                    code=cod_estatus or self.env._("(empty)"),
                    label=code_label,
                    message=message or self.env._("(no message)"),
                ),
            }
        )

    def _complete_verify_no_info(self):
        """Mark verification as successful with zero documents in the range."""
        self.ensure_one()
        self.write(
            {
                "state": "done",
                "document_count": 0,
                "reported_cfdi_count": 0,
                "error_message": False,
                "next_process_at": False,
            }
        )
        self._update_company_last_sync()

    def _schedule_sat_verification_retry(self, minutes=None):
        """Defer the next SAT status check for accepted/processing requests."""
        self.ensure_one()
        delay = timedelta(minutes=minutes or _VERIFY_RETRY_MINUTES)
        self.write({"next_process_at": fields.Datetime.now() + delay})

    def _format_verify_error(self, status, request_status_code, cod_estatus, message):
        status_label = self._sat_request_status_label(status)
        ces_label = self._sat_status_code_label(request_status_code)
        ce_label = self._sat_status_code_label(cod_estatus)
        if status == SAT_REQUEST_STATUS_ERROR:
            return self.env._(
                "SAT reported an error on the request (EstadoSolicitud=4, %(status)s). "
                "CodigoEstadoSolicitud=%(ces)s (%(ces_label)s). "
                "Verification was accepted (CodEstatus=%(ce)s). "
                "SAT message: %(msg)s. Review the date range or retry.",
                status=status_label,
                ces=request_status_code or self.env._("(empty)"),
                ces_label=ces_label,
                ce=cod_estatus or self.env._("(empty)"),
                msg=message or self.env._("(no message)"),
            )
        if status == SAT_REQUEST_STATUS_REJECTED:
            return self.env._(
                "SAT rejected the request (EstadoSolicitud=5, %(status)s). "
                "CodigoEstadoSolicitud=%(ces)s (%(ces_label)s). "
                "Verification was accepted (CodEstatus=%(ce)s, %(ce_label)s). "
                "SAT message: %(msg)s. Review type, direction, and date range.",
                status=status_label,
                ces=request_status_code or self.env._("(empty)"),
                ces_label=ces_label,
                ce=cod_estatus or self.env._("(empty)"),
                ce_label=ce_label,
                msg=message or self.env._("(no message)"),
            )
        if status == SAT_REQUEST_STATUS_EXPIRED:
            return self.env._(
                "SAT marked the request as expired (EstadoSolicitud=6, %(status)s). "
                "CodigoEstadoSolicitud=%(ces)s (%(ces_label)s). "
                "Use Retry to request the same range again.",
                status=status_label,
                ces=request_status_code or self.env._("(empty)"),
                ces_label=ces_label,
            )
        return self.env._(
            "SAT returned an unrecognized request status "
            "(EstadoSolicitud=%(status)s, %(status_label)s). "
            "CodigoEstadoSolicitud=%(ces)s (%(ces_label)s). "
            "CodEstatus=%(ce)s (%(ce_label)s). SAT message: %(msg)s",
            status=status,
            status_label=status_label,
            ces=request_status_code or self.env._("(empty)"),
            ces_label=ces_label,
            ce=cod_estatus or self.env._("(empty)"),
            ce_label=ce_label,
            msg=message or self.env._("(no message)"),
        )

    def _action_request(self):
        self.ensure_one()
        company = self.company_id
        client = company.l10n_mx_sat_get_client()
        token = client.authenticate()
        rfc = company.l10n_mx_sat_get_rfc(client)

        result = client.request_download(
            token,
            rfc,
            self.date_from.replace(tzinfo=None),
            self.date_to.replace(tzinfo=None),
            document_kind=self.document_kind,
            direction=self.direction,
            request_type=self.request_type,
        )

        cod_estatus = sat_str(result.get("cod_estatus"))
        sat_request_id = sat_str(result.get("sat_request_id"))
        message = sat_str(result.get("message"))

        if cod_estatus == SAT_CODE_DUPLICATE_LIFETIME:
            self.write(
                {
                    "state": "error",
                    "error_message": self.env._(
                        "SAT: duplicate request (5002). Will not retry "
                        "automatically with the same parameters."
                    ),
                }
            )
            return

        if sat_request_id and cod_estatus in (SAT_CODE_SUCCESS, SAT_CODE_NO_INFO):
            self.write(
                {
                    "state": "requested",
                    "sat_request_id": sat_request_id,
                    "error_message": False,
                    "next_process_at": False,
                }
            )
            return

        if cod_estatus == SAT_CODE_NO_INFO and not sat_request_id:
            self.write(
                {
                    "state": "done",
                    "document_count": 0,
                    "error_message": False,
                    "next_process_at": False,
                }
            )
            self._update_company_last_sync()
            return

        if cod_estatus == SAT_CODE_MAX_ELEMENTS:
            self._handle_max_elements_exceeded()
            return

        if cod_estatus in SAT_REJECT_CODES:
            self._write_request_error(cod_estatus, message)
            return

        if sat_request_id and "aceptada" in message.lower():
            self.write(
                {
                    "state": "requested",
                    "sat_request_id": sat_request_id,
                    "error_message": False,
                    "next_process_at": False,
                }
            )
            return

        self._write_request_error(cod_estatus, message)

    def _handle_max_elements_exceeded(self):
        """Split request window on SAT 5003 (metadata/XML volume limit)."""
        self.ensure_one()
        delta = self.date_to - self.date_from
        min_delta = timedelta(hours=SAT_METADATA_MIN_WINDOW_HOURS)
        if delta <= min_delta:
            self.write(
                {
                    "state": "error",
                    "error_message": self.env._(
                        "SAT: maximum number of records exceeded even with "
                        "ventana minima. Revise manualmente."
                    ),
                }
            )
            return

        original_date_to = self.date_to
        mid = self.date_from + (delta / 2)
        # Current request covers first half; create second half if not duplicate.
        self.write(
            {
                "date_to": mid,
                "state": "draft",
                "request_fingerprint": build_request_fingerprint(
                    self.company_id.id,
                    self.document_kind,
                    self.direction,
                    self.request_type,
                    self.date_from,
                    mid,
                ),
                "error_message": self.env._(
                    "Window automatically reduced due to SAT 5003."
                ),
            }
        )
        second_half = self.search(
            [
                (
                    "request_fingerprint",
                    "=",
                    build_request_fingerprint(
                        self.company_id.id,
                        self.document_kind,
                        self.direction,
                        self.request_type,
                        mid + timedelta(seconds=1),
                        original_date_to,
                    ),
                )
            ],
            limit=1,
        )
        if not second_half:
            self.create(
                {
                    "company_id": self.company_id.id,
                    "document_kind": self.document_kind,
                    "direction": self.direction,
                    "request_type": self.request_type,
                    "date_from": mid + timedelta(seconds=1),
                    "date_to": original_date_to,
                    "state": "draft",
                }
            )

    def _action_verify(self):
        self.ensure_one()
        company = self.company_id
        client = company.l10n_mx_sat_get_client()
        token = client.authenticate()
        rfc = company.l10n_mx_sat_get_rfc(client)

        result = client.verify_download(
            token, rfc, self.sat_request_id, document_kind=self.document_kind
        )

        cod_estatus = sat_str(result.get("cod_estatus"))
        estado = sat_int(result.get("request_status"), 0)
        request_status_code = sat_str(result.get("request_status_code"))
        packages = result.get("packages") or []
        reported_cfdi_count = sat_int(result.get("reported_cfdi_count"), 0)
        message = sat_str(result.get("message"))

        if cod_estatus == SAT_CODE_MAX_ELEMENTS:
            self._handle_max_elements_exceeded()
            return

        if cod_estatus == SAT_CODE_DAILY_LIMIT:
            self.write(
                {
                    "state": "error",
                    "error_message": self.env._(
                        "SAT: daily download limit reached (5011). Retry tomorrow."
                    ),
                }
            )
            return

        if cod_estatus == SAT_CODE_DUPLICATE_LIFETIME:
            self.write(
                {
                    "state": "error",
                    "error_message": self.env._(
                        "SAT: duplicate request limit reached (5002)."
                    ),
                }
            )
            return

        if request_status_code == SAT_CODE_NO_INFO or cod_estatus == SAT_CODE_NO_INFO:
            self._complete_verify_no_info()
            return

        if estado in (SAT_REQUEST_STATUS_ACCEPTED, SAT_REQUEST_STATUS_PROCESSING):
            self.write(
                {
                    "state": "processing",
                    "reported_cfdi_count": reported_cfdi_count,
                    "next_process_at": False,
                }
            )
            self._schedule_sat_verification_retry()
        elif estado == SAT_REQUEST_STATUS_READY:
            existing_ids = set(self.package_ids.mapped("sat_package_id"))
            for package_id in packages:
                if package_id in existing_ids:
                    continue
                self.env["l10n_mx_sat.download.package"].create(
                    {
                        "request_id": self.id,
                        "sat_package_id": package_id,
                        "state": "pending",
                    }
                )
            self.write(
                {
                    "state": "ready",
                    "reported_cfdi_count": reported_cfdi_count,
                    "error_message": False,
                    "next_process_at": False,
                }
            )
        elif estado == 0:
            self.write(
                {
                    "state": "error",
                    "error_message": self.env._(
                        "SAT returned an invalid EstadoSolicitud (0). "
                        "CodEstatus=%(ce)s (%(ce_label)s). "
                        "CodigoEstadoSolicitud=%(ces)s. SAT message: %(msg)s",
                        ce=cod_estatus or self.env._("(empty)"),
                        ce_label=self._sat_status_code_label(cod_estatus),
                        ces=request_status_code or self.env._("(empty)"),
                        msg=message or self.env._("(no message)"),
                    ),
                }
            )
        else:
            self.write(
                {
                    "state": "error",
                    "error_message": self._format_verify_error(
                        estado, request_status_code, cod_estatus, message
                    ),
                }
            )

    def _get_retry_target_state(self):
        """Return the pipeline state to resume after a failed request."""
        self.ensure_one()
        if not self.sat_request_id:
            return "draft"
        retry_packages = self.package_ids.filtered(
            lambda p: p.state in ("pending", "error")
        )
        if retry_packages:
            retry_packages.filtered(lambda p: p.state == "error").write(
                {"state": "pending"}
            )
            return "ready"
        return "requested"

    def _process_request_pipeline(self):
        """Run the SAT download pipeline for the current request state."""
        self.ensure_one()
        if self.state == "draft":
            self._action_request()
        if self.state in ("requested", "processing"):
            self._action_verify()
        if self.state == "ready":
            self._action_download()

    def action_retry(self):
        """Retry a failed SAT download request from the appropriate step."""
        self.ensure_one()
        if self.state != "error":
            raise UserError(self.env._("Only requests in error state can be retried."))
        if not self.can_retry:
            raise UserError(
                self.env._(
                    "Esta solicitud no puede reintentarse automatically. "
                    "Revise el message de error."
                )
            )

        target_state = self._get_retry_target_state()
        self.write({"state": target_state, "error_message": False})

        try:
            with self.env.cr.savepoint():
                self._process_request_pipeline()
        except Exception as e:
            self.write({"state": "error", "error_message": str(e)})
            raise UserError(self.env._("Failed to retry SAT request: %s", e)) from e

        if self.state == "done":
            message = self.env._(
                "Solicitud completada. Processed documents: %(count)s.",
                count=self.document_count,
            )
            notif_type = "success"
        elif self.state == "error":
            message = self.error_message or self.env._("The request failed again.")
            notif_type = "danger"
        else:
            message = self.env._(
                "Retry started. Current state: %(state)s.",
                state=self._selection_label("state", self.state),
            )
            notif_type = "info"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("SAT retry"),
                "message": message,
                "type": notif_type,
                "sticky": self.state == "error",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _action_download(self):
        self.ensure_one()
        company = self.company_id
        client = company.l10n_mx_sat_get_client()
        token = client.authenticate()
        rfc = company.l10n_mx_sat_get_rfc(client)

        self.write({"state": "downloading"})

        documents = self.env["l10n_mx_sat.document"]
        document_count = 0

        for package in self.package_ids.filtered(lambda p: p.state == "pending"):
            try:
                result = client.download_package(
                    token,
                    rfc,
                    package.sat_package_id,
                    document_kind=self.document_kind,
                )
                cod_estatus = sat_str(result.get("cod_estatus"))
                package_b64 = result.get("package_b64", "")

                if cod_estatus in (SAT_DOWNLOAD_EXPIRED, SAT_DOWNLOAD_MAX_REACHED):
                    package.write({"state": "error"})
                    continue
                if cod_estatus != SAT_CODE_SUCCESS or not package_b64:
                    package.write({"state": "error"})
                    continue

                proc = self._process_package(package_b64, company)
                documents |= proc["documents"]
                document_count += proc["processed"]
                package.write({"state": "processed"})
            except Exception:
                package.write({"state": "error"})
                _logger.exception("Error processing package %s", package.sat_package_id)

        all_error = self.package_ids and all(
            p.state == "error" for p in self.package_ids
        )
        if all_error:
            self.write(
                {
                    "state": "error",
                    "document_count": document_count,
                    "error_message": self.env._("All packages failed."),
                    "next_process_at": False,
                }
            )
        else:
            self.write(
                {
                    "state": "done",
                    "document_count": document_count,
                    "error_message": False,
                    "next_process_at": False,
                }
            )
            self._update_company_last_sync()

    def _update_company_last_sync(self):
        self.ensure_one()
        field_name = (
            "l10n_mx_sat_last_metadata_sync"
            if self.request_type == "metadata"
            else "l10n_mx_sat_last_sync"
        )
        self.company_id.sudo().write({field_name: fields.Datetime.now()})

    _ZIP_MAX_SIZE = 500 * 1024 * 1024
    _ZIP_MAX_FILES = 10_000

    def _process_package(self, package_b64, company):
        """Extract ZIP and process XML or metadata files."""
        documents = self.env["l10n_mx_sat.document"]
        processed = 0

        zip_data = base64.b64decode(package_b64)
        with zipfile.ZipFile(BytesIO(zip_data)) as zf:
            total_size = sum(info.file_size for info in zf.infolist())
            file_count = len(zf.namelist())
            if total_size > self._ZIP_MAX_SIZE or file_count > self._ZIP_MAX_FILES:
                _logger.warning("ZIP bomb guard triggered")
                return {"documents": documents, "processed": 0}

            for filename in zf.namelist():
                lower = filename.lower()
                content = zf.read(filename)
                if self.request_type == "metadata":
                    if not lower.endswith((".txt", ".csv")):
                        continue
                    rows = parse_metadata_content(content)
                    for row in rows:
                        doc = self.env[
                            "l10n_mx_sat.document"
                        ]._upsert_from_metadata_row(row, company, self)
                        if doc:
                            documents |= doc
                            processed += 1
                elif lower.endswith(".xml"):
                    try:
                        tree = etree.fromstring(content, SAFE_XML_PARSER)
                    except etree.XMLSyntaxError:
                        continue
                    doc = self.env["l10n_mx_sat.document"]._upsert_from_xml(
                        tree, content, company, self
                    )
                    if doc:
                        documents |= doc
                        processed += 1

        return {"documents": documents, "processed": processed}

    @api.model
    def _parse_param_ids(self, param_name):
        """Read a comma-separated list of integer IDs from ir.config_parameter."""
        raw = self.env["ir.config_parameter"].sudo().get_param(param_name, "")
        if not raw:
            return []
        return [int(item) for item in raw.split(",") if item.strip().isdigit()]

    @api.model
    def _write_param_ids(self, param_name, ids):
        """Persist a list of integer IDs as a comma-separated config parameter."""
        icp = self.env["ir.config_parameter"].sudo()
        unique_ids = list(dict.fromkeys(ids))
        icp.set_param(
            param_name,
            ",".join(str(item) for item in unique_ids) if unique_ids else "",
        )

    @api.model
    def _add_param_ids(self, param_name, new_ids):
        """Append unique IDs to a config parameter list, preserving order."""
        existing = self._parse_param_ids(param_name)
        combined = list(dict.fromkeys(existing + list(new_ids)))
        self._write_param_ids(param_name, combined)

    @api.model
    def _remove_param_ids(self, param_name, remove_ids):
        """Remove IDs from a config parameter list."""
        remove_set = set(remove_ids)
        remaining = [
            item for item in self._parse_param_ids(param_name) if item not in remove_set
        ]
        self._write_param_ids(param_name, remaining)

    @api.model
    def _mark_company_sync_pending(self, companies):
        """Register companies whose SAT sync should be processed by the cron."""
        companies = companies.exists()
        if not companies:
            return
        self._add_param_ids(_SYNC_PENDING_PARAM, companies.ids)

    @api.model
    def _is_request_executable(self, request, now=None):
        """Return True when a request can be processed by the cron now."""
        now = now or fields.Datetime.now()
        if request.state in _IMMEDIATE_PROCESS_STATES:
            return True
        if request.state in _WAITING_SAT_STATES:
            return not request.next_process_at or request.next_process_at <= now
        return False

    @api.model
    def _build_executable_work_domain(self, company_ids=None):
        """Domain for SAT requests that the cron can process immediately."""
        now = fields.Datetime.now()
        domain = [
            "|",
            ("state", "in", _IMMEDIATE_PROCESS_STATES),
            "&",
            ("state", "in", _WAITING_SAT_STATES),
            "|",
            ("next_process_at", "=", False),
            ("next_process_at", "<=", now),
        ]
        if company_ids:
            domain = [("company_id", "in", list(company_ids))] + domain
        return domain

    @api.model
    def _cron_trigger(self, at=None):
        """Schedule a run of the SAT download cron."""
        cron = self.env.ref(
            "l10n_mx_sat.ir_cron_sat_download", raise_if_not_found=False
        )
        if cron:
            if at:
                cron._trigger(at=at)
            else:
                cron._trigger()

    @api.model
    def _cron_has_immediate_work(self, pending_company_ids):
        """Return True when the cron has executable work without waiting."""
        queued_ids = self._parse_param_ids(_QUEUED_REQUESTS_PARAM)
        if queued_ids:
            now = fields.Datetime.now()
            queued_requests = self.browse(queued_ids).exists()
            if any(
                self._is_request_executable(request, now) for request in queued_requests
            ):
                return True
        if not pending_company_ids:
            return False
        return bool(
            self.search_count(
                self._build_executable_work_domain(pending_company_ids),
                limit=1,
            )
        )

    @api.model
    def _cron_get_next_deferred_at(self, pending_company_ids):
        """Return the earliest future verification datetime, if any."""
        now = fields.Datetime.now()
        domain = [
            ("state", "in", _WAITING_SAT_STATES),
            ("next_process_at", ">", now),
        ]
        if pending_company_ids:
            domain = [("company_id", "in", list(pending_company_ids))] + domain
        request = self.search(domain, order="next_process_at asc", limit=1)
        return request.next_process_at if request else None

    @api.model
    def _cron_schedule_follow_up(self, pending_company_ids):
        """Relaunch the cron immediately or defer SAT verification checks."""
        if self._cron_has_immediate_work(pending_company_ids):
            self._cron_trigger()
            return
        deferred_at = self._cron_get_next_deferred_at(pending_company_ids)
        if deferred_at:
            self._cron_trigger(at=deferred_at)

    def action_queue(self):
        """Enqueue draft requests for background processing."""
        drafts = self.filtered(lambda rec: rec.state == "draft")
        if not drafts:
            raise UserError(
                self.env._("Only draft SAT download requests can be queued.")
            )
        self._add_param_ids(_QUEUED_REQUESTS_PARAM, drafts.ids)
        self._cron_trigger()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("SAT queue"),
                "message": self.env._("Request(s) queued for background processing."),
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def _collect_pending_work(self, pending_companies):
        """Build ordered request list: queued first, then company pending rows."""
        requests_to_process = self.browse()
        now = fields.Datetime.now()
        queued_ids = self._parse_param_ids(_QUEUED_REQUESTS_PARAM)
        if queued_ids:
            queued_requests = (
                self.browse(queued_ids)
                .exists()
                .filtered(lambda rec: self._is_request_executable(rec, now))
            )
            requests_to_process |= queued_requests
            self._write_param_ids(_QUEUED_REQUESTS_PARAM, queued_requests.ids)

        selected_ids = set(requests_to_process.ids)
        if pending_companies:
            company_requests = self.search(
                self._build_executable_work_domain(pending_companies.ids),
                order="create_date asc",
            )
            for request in company_requests:
                if request.id not in selected_ids:
                    requests_to_process |= request
                    selected_ids.add(request.id)
        return requests_to_process

    @api.model
    def _refresh_pending_companies(self, pending_companies):
        """Keep companies in the pending list while they still have work."""
        still_pending = []
        for company in pending_companies:
            active_count = self.search_count(
                [
                    ("company_id", "=", company.id),
                    ("state", "in", _ACTIVE_REQUEST_STATES),
                ]
            )
            if active_count:
                still_pending.append(company.id)
                continue
            if not (
                company.l10n_mx_sat_auto_download
                and company.l10n_mx_sat_has_credentials()
            ):
                continue
            before = active_count
            self._ensure_scheduled_requests(company)
            after = self.search_count(
                [
                    ("company_id", "=", company.id),
                    ("state", "in", _ACTIVE_REQUEST_STATES),
                ]
            )
            if after > before:
                still_pending.append(company.id)
        self._write_param_ids(_SYNC_PENDING_PARAM, still_pending)
        return still_pending

    @api.model
    def _cron_process_requests(self, companies=None):
        """Main cron entry point: queue-backed, one request per invocation."""
        if companies is not None:
            self._mark_company_sync_pending(companies)
        else:
            auto_companies = self.env["res.company"].search(
                [
                    ("l10n_mx_sat_auto_download", "=", True),
                    ("l10n_mx_sat_fiel_cer", "!=", False),
                    ("l10n_mx_sat_fiel_key", "!=", False),
                    ("l10n_mx_sat_fiel_password", "!=", False),
                ]
            )
            self._mark_company_sync_pending(auto_companies)

        pending_company_ids = self._parse_param_ids(_SYNC_PENDING_PARAM)
        pending_companies = self.env["res.company"].browse(pending_company_ids).exists()

        for company in pending_companies:
            if company.l10n_mx_sat_has_credentials():
                self._ensure_scheduled_requests(company)

        requests_to_process = self._collect_pending_work(pending_companies)
        batch_size = (
            len(requests_to_process) if not _CRON_BATCH_SIZE else _CRON_BATCH_SIZE
        )
        batch = requests_to_process[:batch_size]

        successful_requests = self.browse()
        for request in batch:
            try:
                with self.env.cr.savepoint():
                    request._process_request_pipeline()
                    if request.state == "done":
                        successful_requests |= request
            except Exception as exc:
                request_safe = request.exists()
                if request_safe:
                    request_safe.write({"state": "error", "error_message": str(exc)})
                _logger.exception("Error processing SAT request id=%s", request.id)

        self._remove_param_ids(_QUEUED_REQUESTS_PARAM, batch.ids)

        for request in successful_requests:
            company = request.company_id
            if company.l10n_mx_sat_auto_download:
                self._ensure_scheduled_requests(company, after_success=True)

        still_pending = self._refresh_pending_companies(pending_companies)
        self._cron_schedule_follow_up(still_pending)

    @api.model
    def _ensure_scheduled_requests(self, company, after_success=False):
        """Create missing XML download requests for enabled company flows."""
        flows = company.l10n_mx_sat_get_xml_download_flows()
        if not flows:
            return
        for document_kind, direction, request_type in flows:
            pending = self.search_count(
                [
                    ("company_id", "=", company.id),
                    ("document_kind", "=", document_kind),
                    ("direction", "=", direction),
                    ("request_type", "=", request_type),
                    ("state", "in", _ACTIVE_REQUEST_STATES),
                ]
            )
            if pending:
                continue
            last_error = self.search(
                [
                    ("company_id", "=", company.id),
                    ("document_kind", "=", document_kind),
                    ("direction", "=", direction),
                    ("request_type", "=", request_type),
                    ("state", "=", "error"),
                ],
                order="write_date desc",
                limit=1,
            )
            if last_error and SAT_CODE_DUPLICATE_LIFETIME in (
                last_error.error_message or ""
            ):
                continue
            req = self._create_next_request(
                company, document_kind, direction, request_type
            )
            if req and after_success:
                _logger.info(
                    "Chained SAT request %s for company %s",
                    req.name,
                    company.name,
                )

    @api.model
    def _create_next_request(self, company, document_kind, direction, request_type):
        """Create incremental request for the next date window."""
        last_done = self.search(
            [
                ("company_id", "=", company.id),
                ("document_kind", "=", document_kind),
                ("direction", "=", direction),
                ("request_type", "=", request_type),
                ("state", "=", "done"),
            ],
            order="date_to desc",
            limit=1,
        )

        sync_from = self._get_sync_from_date(company, request_type)
        if last_done:
            date_from = last_done.date_to + timedelta(seconds=1)
        elif sync_from:
            date_from = datetime.combine(sync_from, datetime.min.time())
        else:
            mx_now = datetime.now(MX_TZ)
            days = (
                SAT_METADATA_DEFAULT_WINDOW_DAYS
                if request_type == "metadata"
                else SAT_DEFAULT_SYNC_DAYS
            )
            date_from = (mx_now - timedelta(days=days)).replace(
                hour=0, minute=0, second=0, tzinfo=None
            )

        mx_now = datetime.now(MX_TZ)
        date_to = (mx_now - timedelta(days=1)).replace(
            hour=23, minute=59, second=59, tzinfo=None
        )

        if hasattr(date_from, "tzinfo") and date_from.tzinfo:
            date_from = date_from.replace(tzinfo=None)

        if request_type == "metadata" and not last_done:
            window_end = date_from + timedelta(days=SAT_METADATA_DEFAULT_WINDOW_DAYS)
            if window_end < date_to:
                date_to = window_end.replace(hour=23, minute=59, second=59)

        if date_from >= date_to:
            return self.browse()

        fingerprint = build_request_fingerprint(
            company.id,
            document_kind,
            direction,
            request_type,
            date_from,
            date_to,
        )
        if self.search([("request_fingerprint", "=", fingerprint)], limit=1):
            return self.browse()

        return self.create(
            {
                "company_id": company.id,
                "document_kind": document_kind,
                "direction": direction,
                "request_type": request_type,
                "date_from": date_from,
                "date_to": date_to,
                "state": "draft",
                "request_fingerprint": fingerprint,
            }
        )

    @api.model
    def _get_sync_from_date(self, company, request_type):
        if request_type == "metadata":
            return (
                company.l10n_mx_sat_metadata_sync_from or company.l10n_mx_sat_sync_from
            )
        return company.l10n_mx_sat_sync_from


class L10nMxSatDownloadPackage(models.Model):
    _name = "l10n_mx_sat.download.package"
    _description = "SAT Download Package"

    request_id = fields.Many2one(
        comodel_name="l10n_mx_sat.download.request",
        string="SAT request",
        required=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        related="request_id.company_id",
        store=True,
        index=True,
    )
    sat_package_id = fields.Char(string="Package ID", required=True, readonly=True)
    state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("processed", "Processed"),
            ("error", "Error"),
        ],
        default="pending",
        required=True,
        readonly=True,
    )
