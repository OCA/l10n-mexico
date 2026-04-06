# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
import logging
import zipfile
from datetime import datetime, timedelta
from io import BytesIO

from lxml import etree

from odoo import _, Command, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.l10n_mx_sat.services import (
    MX_TZ,
    SAFE_XML_PARSER,
    SAT_CODE_NO_INFO,
    SAT_CODE_SUCCESS,
    SAT_REJECT_CODES,
    sat_int,
    sat_str,
)

_logger = logging.getLogger(__name__)

# SAT VerificaSolicitudDescarga - additional response codes (V1.5)
SAT_CODE_MAX_ELEMENTS = "5003"
SAT_CODE_DAILY_LIMIT = "5011"

# SAT DescargaMasiva - package-level error codes (V1.5)
SAT_DOWNLOAD_EXPIRED = "5007"
SAT_DOWNLOAD_MAX_REACHED = "5008"

# SAT EstadoSolicitud values (VerificaSolicitudDescarga)
SAT_ESTADO_ACCEPTED = 1
SAT_ESTADO_PROCESSING = 2
SAT_ESTADO_READY = 3
SAT_ESTADO_ERROR = 4
SAT_ESTADO_REJECTED = 5
SAT_ESTADO_EXPIRED = 6
SAT_ESTADO_LABELS = {
    SAT_ESTADO_ERROR: "Error",
    SAT_ESTADO_REJECTED: "Rejected",
    SAT_ESTADO_EXPIRED: "Expired",
}


class L10nMxSatDownloadRequest(models.Model):
    _name = "l10n_mx_sat.download.request"
    _description = "SAT Download Request"
    _order = "create_date desc"

    name = fields.Char(compute="_compute_name", store=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("requested", "Requested"),
            ("processing", "Processing"),
            ("ready", "Ready"),
            ("downloading", "Downloading"),
            ("done", "Done"),
            ("error", "Error"),
        ],
        default="draft",
        required=True,
        readonly=True,
    )
    fecha_inicial = fields.Datetime(string="From", required=True)
    fecha_final = fields.Datetime(string="To", required=True)
    id_solicitud = fields.Char(string="SAT Request ID", readonly=True)
    package_ids = fields.One2many(
        comodel_name="l10n_mx_sat.download.package",
        inverse_name="request_id",
        string="Packages",
        readonly=True,
    )
    error_message = fields.Text(readonly=True)
    cfdi_count = fields.Integer(string="CFDIs Processed", readonly=True)
    numero_cfdis = fields.Integer(string="CFDIs Reported by SAT", readonly=True)
    move_ids = fields.Many2many(
        comodel_name="account.move",
        string="Created Bills",
        readonly=True,
    )

    @api.depends("company_id.vat", "fecha_inicial", "fecha_final")
    def _compute_name(self):
        for rec in self:
            vat = rec.company_id.vat or "?"
            fi = rec.fecha_inicial.strftime("%Y-%m-%d") if rec.fecha_inicial else "?"
            ff = rec.fecha_final.strftime("%Y-%m-%d") if rec.fecha_final else "?"
            rec.name = "%s / %s - %s" % (vat, fi, ff)

    # ------------------------------------------------------------------
    # State machine actions
    # ------------------------------------------------------------------

    def _write_request_error(self, cod_estatus, mensaje):
        """Write error state with standardized SAT rejection message."""
        self.write(
            {
                "state": "error",
                "error_message": _(
                    "SAT rejected request. Code: %(code)s, "
                    "Message: %(message)s",
                    code=cod_estatus or _("(empty)"),
                    message=mensaje,
                ),
            }
        )
        _logger.warning(
            "SAT request rejected for %s: %s - %s",
            self.company_id.vat,
            cod_estatus,
            mensaje,
        )

    def _action_request(self):
        """draft -> requested: Send download request to SAT."""
        self.ensure_one()
        company = self.company_id
        client = company.l10n_mx_sat_get_client()
        token = client.authenticate()

        result = client.request_download(
            token,
            company.vat,
            self.fecha_inicial.replace(tzinfo=None),
            self.fecha_final.replace(tzinfo=None),
            rfc_receptor=company.vat,
            tipo_solicitud="CFDI",
        )

        cod_estatus = sat_str(result.get("cod_estatus"))
        id_solicitud = sat_str(result.get("id_solicitud"))
        mensaje = sat_str(result.get("mensaje"))

        # Success: got id_solicitud with accepted code.
        # NOTE: 5004 is NOT in the SAT spec for WS SolicitaDescargaRecibidos,
        # but the API returns it in practice. When it comes WITH an id_solicitud
        # we treat it as accepted; without id_solicitud -> no data found.
        if id_solicitud and cod_estatus in (SAT_CODE_SUCCESS, SAT_CODE_NO_INFO):
            self.write(
                {
                    "state": "requested",
                    "id_solicitud": id_solicitud,
                    "error_message": False,
                }
            )
            _logger.info(
                "SAT download requested for %s: %s", company.vat, id_solicitud
            )
            return

        # No data found (5004 without id_solicitud)
        if cod_estatus == SAT_CODE_NO_INFO and not id_solicitud:
            self.write({"state": "done", "cfdi_count": 0, "error_message": False})
            _logger.info("SAT returned no data for %s", company.vat)
            return

        # Explicit rejection
        if cod_estatus in SAT_REJECT_CODES:
            self._write_request_error(cod_estatus, mensaje)
            return

        # Fallback: accepted with non-standard code
        if id_solicitud and "aceptada" in mensaje.lower():
            self.write(
                {
                    "state": "requested",
                    "id_solicitud": id_solicitud,
                    "error_message": False,
                }
            )
            _logger.info(
                "SAT download accepted (fallback) for %s: %s code=%s",
                company.vat,
                id_solicitud,
                cod_estatus,
            )
            return

        # Unknown response -> error
        self._write_request_error(cod_estatus, mensaje)

    def _action_verify(self):
        """requested/processing -> processing/ready/error: Verify status."""
        self.ensure_one()
        company = self.company_id
        client = company.l10n_mx_sat_get_client()
        token = client.authenticate()

        result = client.verify_download(token, company.vat, self.id_solicitud)

        cod_estatus = sat_str(result.get("cod_estatus"))
        estado = sat_int(result.get("estado_solicitud"), 0)
        codigo_estado = sat_str(result.get("codigo_estado_solicitud"))
        paquetes = result.get("paquetes") or []
        numero_cfdis = sat_int(result.get("numero_cfdis"), 0)
        mensaje = sat_str(result.get("mensaje"))

        # VerificaSolicitudDescarga: 5003 = max elements exceeded for the query.
        if cod_estatus == SAT_CODE_MAX_ELEMENTS:
            self.write(
                {
                    "state": "error",
                    "error_message": _(
                        "SAT: maximum elements exceeded. Reduce the date range."
                    ),
                }
            )
            return

        # VerificaSolicitudDescarga: 5011 = daily download limit reached (V1.5).
        if cod_estatus == SAT_CODE_DAILY_LIMIT:
            self.write(
                {
                    "state": "error",
                    "error_message": _(
                        "SAT: daily download limit reached. Retry tomorrow."
                    ),
                }
            )
            return

        # VerificaSolicitudDescarga: 5004 = no info for this request yet (retry).
        if cod_estatus == SAT_CODE_NO_INFO:
            self.write(
                {
                    "state": "processing",
                    "numero_cfdis": numero_cfdis,
                    "error_message": False,
                }
            )
            _logger.info(
                "SAT verify returned 5004 for request %s; will retry later",
                self.id_solicitud,
            )
            return

        if estado in (SAT_ESTADO_ACCEPTED, SAT_ESTADO_PROCESSING):
            self.write({"state": "processing", "numero_cfdis": numero_cfdis})
            _logger.info(
                "SAT request %s still processing (estado=%s, cfdis=%s)",
                self.id_solicitud,
                estado,
                numero_cfdis,
            )
        elif estado == SAT_ESTADO_READY:
            # Create package records (idempotent on retry)
            existing_ids = set(self.package_ids.mapped("id_paquete"))
            for id_paquete in paquetes:
                if id_paquete in existing_ids:
                    continue
                self.env["l10n_mx_sat.download.package"].create(
                    {
                        "request_id": self.id,
                        "id_paquete": id_paquete,
                        "state": "pending",
                    }
                )
            self.write(
                {
                    "state": "ready",
                    "numero_cfdis": numero_cfdis,
                    "error_message": False,
                }
            )
            _logger.info(
                "SAT request %s ready with %d packages",
                self.id_solicitud,
                len(paquetes),
            )
        elif estado == 0:
            # EstadoSolicitud=0 is NOT in the SAT spec (valid: 1-6).
            # cfdiclient returns 0 when the token is invalid or the response
            # is empty. Treating it as error is the safe default.
            self.write(
                {
                    "state": "error",
                    "error_message": _(
                        "SAT verify: invalid or empty estado_solicitud (0). "
                        "CodEstatus: %(ce)s, Message: %(msg)s",
                        ce=cod_estatus,
                        msg=mensaje,
                    ),
                }
            )
        else:
            self.write(
                {
                    "state": "error",
                    "error_message": _(
                        "SAT verification: EstadoSolicitud=%(estado)s (%(label)s). "
                        "CodigoEstadoSolicitud=%(ces)s, CodEstatus=%(ce)s, "
                        "Message: %(msg)s",
                        estado=estado,
                        label=SAT_ESTADO_LABELS.get(estado, str(estado)),
                        ces=codigo_estado,
                        ce=cod_estatus,
                        msg=mensaje,
                    ),
                }
            )

    def _action_download(self):
        """ready -> downloading -> done: Download packages and process XMLs."""
        self.ensure_one()
        company = self.company_id
        client = company.l10n_mx_sat_get_client()
        token = client.authenticate()

        self.write({"state": "downloading"})

        created_moves = self.env["account.move"]
        cfdi_count = 0

        for package in self.package_ids.filtered(
            lambda p: p.state == "pending"
        ):
            try:
                result = client.download_package(
                    token, company.vat, package.id_paquete
                )
                cod_estatus = sat_str(result.get("cod_estatus"))
                paquete_b64 = result.get("paquete_b64", "")

                if cod_estatus == SAT_DOWNLOAD_EXPIRED:
                    package.write({"state": "error"})
                    _logger.warning(
                        "Package %s expired (72h TTL). "
                        "Must create a new SAT request.",
                        package.id_paquete,
                    )
                    continue
                if cod_estatus == SAT_DOWNLOAD_MAX_REACHED:
                    package.write({"state": "error"})
                    _logger.warning(
                        "Package %s reached max downloads (2). "
                        "Must create a new SAT request.",
                        package.id_paquete,
                    )
                    continue
                if cod_estatus != SAT_CODE_SUCCESS or not paquete_b64:
                    package.write({"state": "error"})
                    _logger.warning(
                        "Failed to download package %s: %s",
                        package.id_paquete,
                        result.get("mensaje", ""),
                    )
                    continue

                # Process the ZIP package
                moves, count = self._process_package(paquete_b64, company)
                created_moves |= moves
                cfdi_count += count
                package.write({"state": "processed"})

            except Exception:
                package.write({"state": "error"})
                _logger.exception(
                    "Error processing package %s", package.id_paquete
                )

        all_error = self.package_ids and all(
            p.state == "error" for p in self.package_ids
        )
        if all_error:
            self.write(
                {
                    "state": "error",
                    "cfdi_count": cfdi_count,
                    "move_ids": [Command.set(created_moves.ids)],
                    "error_message": _("All packages failed to download."),
                }
            )
        else:
            self.write(
                {
                    "state": "done",
                    "cfdi_count": cfdi_count,
                    "move_ids": [Command.set(created_moves.ids)],
                    "error_message": False,
                }
            )
            company.sudo().write(
                {"l10n_mx_sat_vendor_bill_last_sync": fields.Datetime.now()}
            )

        _logger.info(
            "SAT download complete for %s: %d CFDIs processed, %d bills created",
            company.vat,
            cfdi_count,
            len(created_moves),
        )

    # Maximum decompressed size (500 MB) and file count (10 000) to prevent
    # ZIP bombs from exhausting server memory.
    _ZIP_MAX_SIZE = 500 * 1024 * 1024
    _ZIP_MAX_FILES = 10_000

    def _process_package(self, paquete_b64, company):
        """Extract ZIP from base64 and process each XML file.

        :return: tuple (created_moves recordset, xml_count int)
        """
        created_moves = self.env["account.move"]
        xml_count = 0

        zip_data = base64.b64decode(paquete_b64)
        with zipfile.ZipFile(BytesIO(zip_data)) as zf:
            total_size = sum(info.file_size for info in zf.infolist())
            file_count = len(zf.namelist())
            if total_size > self._ZIP_MAX_SIZE or file_count > self._ZIP_MAX_FILES:
                _logger.warning(
                    "ZIP bomb guard: package exceeds limits "
                    "(size=%s, files=%s), skipping",
                    total_size,
                    file_count,
                )
                return created_moves, 0

            for xml_filename in zf.namelist():
                if not xml_filename.lower().endswith(".xml"):
                    continue
                xml_bytes = zf.read(xml_filename)
                xml_count += 1

                try:
                    tree = etree.fromstring(xml_bytes, SAFE_XML_PARSER)
                except etree.XMLSyntaxError:
                    _logger.warning("Invalid XML in package: %s", xml_filename)
                    continue

                # Verify receptor matches our company
                receptor = tree.find("{*}Receptor")
                if receptor is None:
                    _logger.warning(
                        "CFDI without Receptor element, skipping: %s",
                        xml_filename,
                    )
                    continue
                receptor_rfc = receptor.get("Rfc", "")
                if receptor_rfc != company.vat:
                    _logger.warning(
                        "SAT package XML skipped (receptor RFC mismatch): file=%s "
                        "receptor_rfc=%s company_vat=%s",
                        xml_filename,
                        receptor_rfc,
                        company.vat,
                    )
                    continue

                move = self.env[
                    "account.move"
                ]._l10n_mx_sat_create_bill_from_cfdi(tree, xml_bytes, self)
                if move:
                    created_moves |= move

        return created_moves, xml_count

    # ------------------------------------------------------------------
    # Cron entry point
    # ------------------------------------------------------------------

    @api.model
    def _cron_process_requests(self, companies=None):
        """Main cron entry point. Process requests through their state machine.

        :param companies: optional recordset to limit processing
        """
        if companies is None:
            companies = self.env["res.company"].search(
                [
                    ("l10n_mx_sat_fiel_cer", "!=", False),
                    ("l10n_mx_sat_fiel_key", "!=", False),
                    ("l10n_mx_sat_fiel_password", "!=", False),
                ]
            )

        manual_sync = self.env.context.get("l10n_mx_sat_vendor_bill_manual_sync")

        for company in companies:
            # Process existing requests (advance state machine). If none exist,
            # create one and process it in this same cycle so manual "Sync Now"
            # does not stop at draft.
            pending_requests = self.search(
                [
                    ("company_id", "=", company.id),
                    ("state", "not in", ("done", "error")),
                ],
                order="create_date asc",
            )
            if not pending_requests:
                new_request = self._create_next_request(company)
                pending_requests = new_request or self.browse()

            successful_requests = self.browse()
            for req in pending_requests:
                try:
                    # Sequential if (NOT elif) is intentional: each action may
                    # advance the state, allowing a request to traverse multiple
                    # states in a single cron tick (e.g. draft -> requested ->
                    # processing -> ready -> done).
                    if req.state == "draft":
                        req._action_request()
                    if req.state in ("requested", "processing"):
                        req._action_verify()
                    if req.state == "ready":
                        req._action_download()
                    if req.state == "done":
                        successful_requests |= req
                    # Commit after each request to avoid losing progress
                    if not self.env.context.get("test_queue_job_no_delay"):
                        self.env.cr.commit()  # pylint: disable=invalid-commit
                except Exception as e:
                    if not self.env.context.get("test_queue_job_no_delay"):
                        self.env.cr.rollback()  # pylint: disable=invalid-commit
                        self.env.invalidate_all()
                    req_safe = req.exists()
                    if req_safe:
                        req_safe.write({"state": "error", "error_message": str(e)})
                    if not self.env.context.get("test_queue_job_no_delay"):
                        self.env.cr.commit()  # pylint: disable=invalid-commit
                    _logger.exception(
                        "Error processing SAT request id=%s", req.id
                    )

            # Encadenar siguiente rango solo tras al menos un request en "done"
            # en esta corrida (evita un draft extra cuando lo último fue error).
            pending_count = self.search_count(
                [
                    ("company_id", "=", company.id),
                    ("state", "not in", ("done", "error")),
                ]
            )
            if (
                not manual_sync
                and not pending_count
                and successful_requests
            ):
                self._create_next_request(company)

    @api.model
    def _create_next_request(self, company):
        """Create a new download request for the next date range.

        Precedence for *fecha_inicial*:
        1. If there is at least one completed request, start the instant **after**
           its ``fecha_final`` (avoids overlapping the same second the SAT already
           covered and reduces duplicate/rejected solicitations).
        2. Else if ``l10n_mx_sat_vendor_bill_sync_from`` is set on the company,
           use that date at 00:00:00 (first sync / backfill start).
        3. Else default to 30 days ago (Mexico timezone) at 00:00:00.

        ``Sync from date`` in settings does **not** override (1): once incremental
        sync has completed ranges, the next chunk always continues from the last
        successful period. To re-download from an earlier date, remove or adjust
        completed ``SAT Download Request`` records or change company data with care.
        """
        # Determine fecha_inicial
        last_done = self.search(
            [
                ("company_id", "=", company.id),
                ("state", "=", "done"),
            ],
            order="fecha_final desc",
            limit=1,
        )

        if last_done:
            # Avoid inclusive overlap with the previous completed window
            fecha_inicial = last_done.fecha_final + timedelta(seconds=1)
        elif company.l10n_mx_sat_vendor_bill_sync_from:
            fecha_inicial = datetime.combine(
                company.l10n_mx_sat_vendor_bill_sync_from, datetime.min.time()
            )
        else:
            # Default: 30 days ago in Mexico timezone
            mx_now = datetime.now(MX_TZ)
            fecha_inicial = (mx_now - timedelta(days=30)).replace(
                hour=0, minute=0, second=0, tzinfo=None
            )

        # fecha_final = yesterday 23:59:59 in Mexico timezone (SAT rejects
        # today or future)
        mx_now = datetime.now(MX_TZ)
        fecha_final = (mx_now - timedelta(days=1)).replace(
            hour=23, minute=59, second=59, tzinfo=None
        )

        # Ensure fecha_inicial is a naive datetime
        if hasattr(fecha_inicial, "tzinfo") and fecha_inicial.tzinfo:
            fecha_inicial = fecha_inicial.replace(tzinfo=None)

        if fecha_inicial >= fecha_final:
            return  # Nothing to sync

        return self.create(
            {
                "company_id": company.id,
                "fecha_inicial": fecha_inicial,
                "fecha_final": fecha_final,
                "state": "draft",
            }
        )


class L10nMxSatDownloadPackage(models.Model):
    _name = "l10n_mx_sat.download.package"
    _description = "SAT Download Package"

    request_id = fields.Many2one(
        comodel_name="l10n_mx_sat.download.request",
        required=True,
        ondelete="cascade",
    )
    id_paquete = fields.Char(string="Package ID", required=True, readonly=True)
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
