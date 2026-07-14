# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from odoo.addons.l10n_mx_sat.services import (
    SAT_CODE_DAILY_LIMIT,
    SAT_CODE_DUPLICATE_LIFETIME,
    SAT_CODE_MAX_ELEMENTS,
    SAT_CODE_NO_INFO,
    SAT_CODE_SUCCESS,
    SAT_DOWNLOAD_EXPIRED,
    SAT_DOWNLOAD_MAX_REACHED,
    SAT_REQUEST_STATUS_ACCEPTED,
    SAT_REQUEST_STATUS_ERROR,
    SAT_REQUEST_STATUS_EXPIRED,
    SAT_REQUEST_STATUS_PROCESSING,
    SAT_REQUEST_STATUS_READY,
    SAT_REQUEST_STATUS_REJECTED,
    SAT_STATUS_CODE_LABELS,
)
from odoo.addons.l10n_mx_sat.services.sat_metadata import (
    build_request_fingerprint,
    normalize_sat_status,
    parse_metadata_content,
)

_PATCH_GET_CLIENT = (
    "odoo.addons.l10n_mx_sat.models.res_company.ResCompany.l10n_mx_sat_get_client"
)
_SVC = "odoo.addons.l10n_mx_sat.services.sat_client"
_DEFAULT_CFDI_UUID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


@tagged("post_install", "-at_install")
class TestSatMetadata(TransactionCase):
    def test_normalize_sat_status(self):
        self.assertEqual(normalize_sat_status("Valid"), "valid")
        self.assertEqual(normalize_sat_status("Cancelled"), "cancelled")
        self.assertEqual(normalize_sat_status("In progress"), "in_progress")
        self.assertEqual(normalize_sat_status("Vigente"), "valid")
        self.assertEqual(normalize_sat_status("Cancelado"), "cancelled")
        self.assertEqual(normalize_sat_status("En Proceso"), "in_progress")
        self.assertEqual(normalize_sat_status("enproceso"), "in_progress")
        self.assertFalse(normalize_sat_status(""))
        self.assertFalse(normalize_sat_status(None))
        self.assertEqual(normalize_sat_status("Weird Status"), "weird_status")

    def test_parse_metadata_content(self):
        content = (
            b"Uuid|RfcEmisor|NombreEmisor|RfcReceptor|NombreReceptor|"
            b"FechaEmision|FechaCertificacion|Total|EfectoComprobante|Estado\n"
            b"AAA-BBB|EKU9003173C9|EMPRESA|AAA010101AAA|CLIENTE|"
            b"2026-01-01 10:00:00|2026-01-01 10:01:00|100.00|I|Cancelled\n"
        )
        rows = parse_metadata_content(content)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["uuid"], "AAA-BBB")
        self.assertEqual(rows[0]["sat_status"], "cancelled")

    def test_parse_metadata_content_empty_and_csv(self):
        self.assertEqual(parse_metadata_content(b""), [])
        self.assertEqual(parse_metadata_content(b"   \n"), [])
        content = (
            b"\xef\xbb\xbfFolioFiscal,RfcEmisor,NombreEmisor,RfcReceptor,"
            b"NombreReceptor,FechaEmision,FechaCertificacion,Total,"
            b"EfectoComprobante,Estado\n"
            b"abc-def,EKU9003173C9,EMPRESA,AAA010101AAA,CLIENTE,"
            b"2026-01-01,2026-01-01,10.00,I,Vigente\n"
            b",EKU9003173C9,EMPRESA,AAA010101AAA,CLIENTE,"
            b"2026-01-01,2026-01-01,10.00,I,Vigente\n"
        )
        rows = parse_metadata_content(content)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["uuid"], "ABC-DEF")
        self.assertEqual(rows[0]["sat_status"], "valid")

    def test_build_request_fingerprint_stable(self):
        fi = datetime(2026, 1, 1)
        ff = datetime(2026, 1, 31)
        fp1 = build_request_fingerprint(1, "cfdi", "received", "metadata", fi, ff)
        fp2 = build_request_fingerprint(1, "cfdi", "received", "metadata", fi, ff)
        self.assertEqual(fp1, fp2)
        fp_other_company = build_request_fingerprint(
            2, "cfdi", "received", "metadata", fi, ff
        )
        self.assertNotEqual(fp1, fp_other_company)
        fp_none_dates = build_request_fingerprint(
            1, "cfdi", "received", "metadata", None, None
        )
        self.assertTrue(fp_none_dates)
        self.assertNotEqual(fp1, fp_none_dates)


@tagged("post_install", "-at_install")
class TestDownloadRequest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.company.write(
            {
                "vat": "EKU9003173C9",
                "country_id": cls.env.ref("base.mx").id,
                "l10n_mx_sat_fiel_cer": b"ZmFrZQ==",
                "l10n_mx_sat_fiel_key": b"ZmFrZQ==",
                "l10n_mx_sat_fiel_password": "test",
            }
        )
        cls.env.user.group_ids |= cls.env.ref("l10n_mx_sat.group_sat_manager")

    def setUp(self):
        super().setUp()
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("l10n_mx_sat.sync_pending_company_ids", "")
        icp.set_param("l10n_mx_sat.queued_request_ids", "")

    def _create_request(self, **kwargs):
        vals = {
            "company_id": self.company.id,
            "document_kind": "cfdi",
            "direction": "received",
            "request_type": "xml",
            "date_from": "2026-02-01 00:00:00",
            "date_to": "2026-02-28 23:59:59",
            "state": "draft",
        }
        vals.update(kwargs)
        return self.env["l10n_mx_sat.download.request"].create(vals)

    def _mock_client(self, **overrides):
        client = MagicMock()
        client.authenticate.return_value = "fake-token"
        client.rfc = self.company.vat
        for attr, val in overrides.items():
            setattr(client, attr, val)
        return client

    def test_mock_client_applies_overrides(self):
        client = self._mock_client(rfc="OVERRIDE", authenticate=lambda: "tok")
        self.assertEqual(client.rfc, "OVERRIDE")
        self.assertEqual(client.authenticate(), "tok")

    def _patch_factory(self, mock_client):
        return patch(_PATCH_GET_CLIENT, return_value=mock_client)

    def _build_zip_b64(self, files):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            for name, content in files.items():
                zf.writestr(name, content)
        return base64.b64encode(buffer.getvalue()).decode()

    def _minimal_cfdi_xml(
        self,
        receiver_rfc="EKU9003173C9",
        uuid=_DEFAULT_CFDI_UUID,
    ):
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" '
            f'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
            f'Fecha="2026-01-15T10:00:00" Total="100.00">'
            f'<cfdi:Emisor Rfc="AAA010101AAA" Nombre="Emisor"/>'
            f'<cfdi:Receptor Rfc="{receiver_rfc}" Nombre="Receptor"/>'
            f"<cfdi:Complemento>"
            f'<tfd:TimbreFiscalDigital UUID="{uuid}" '
            f'FechaTimbrado="2026-01-15T10:01:00"/>'
            f"</cfdi:Complemento></cfdi:Comprobante>"
        ).encode()

    def _create_package(self, request, sat_package_id="PKG-1", state="pending"):
        return self.env["l10n_mx_sat.download.package"].create(
            {
                "request_id": request.id,
                "sat_package_id": sat_package_id,
                "state": state,
            }
        )

    def test_action_request_success(self):
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "sat_request_id": "SOL-12345",
            "message": "Solicitud aceptada",
        }
        req = self._create_request()
        with self._patch_factory(client):
            req._action_request()
        self.assertEqual(req.state, "requested")
        self.assertEqual(req.sat_request_id, "SOL-12345")

    def test_action_request_duplicate_5002(self):
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": SAT_CODE_DUPLICATE_LIFETIME,
            "sat_request_id": "",
            "message": "Se agotaron las solicitudes",
        }
        req = self._create_request()
        with self._patch_factory(client):
            req._action_request()
        self.assertEqual(req.state, "error")
        self.assertIn("5002", req.error_message)

    def test_action_request_max_elements_splits(self):
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": SAT_CODE_MAX_ELEMENTS,
            "sat_request_id": "",
            "message": "Tope maximo",
        }
        req = self._create_request(
            date_from="2026-03-01 00:00:00",
            date_to="2026-03-31 23:59:59",
        )
        original_date_to = req.date_to
        with self._patch_factory(client):
            req._action_request()
        self.assertEqual(req.state, "draft")
        mid = req.date_to
        second = self.env["l10n_mx_sat.download.request"].search(
            [
                ("company_id", "=", self.company.id),
                ("date_from", "=", mid + timedelta(seconds=1)),
                ("date_to", "=", original_date_to),
            ]
        )
        self.assertEqual(len(second), 1)

    def test_fingerprint_prevents_duplicate_request(self):
        req = self._create_request()
        with self.assertRaises(ValidationError):
            self._create_request(
                date_from=req.date_from,
                date_to=req.date_to,
                document_kind=req.document_kind,
                direction=req.direction,
                request_type=req.request_type,
            )

    def test_metadata_upsert_updates_estado(self):
        request = self._create_request(request_type="metadata", state="done")
        row = {
            "uuid": "11111111-2222-3333-4444-555555555555",
            "issuer_rfc": "EKU9003173C9",
            "receiver_rfc": "AAA010101AAA",
            "sat_status": "cancelled",
            "total": "150.00",
        }
        doc = self.env["l10n_mx_sat.document"]._upsert_from_metadata_row(
            row, self.company, request
        )
        self.assertEqual(doc.sat_status, "cancelled")
        row["sat_status"] = "in_progress"
        doc2 = self.env["l10n_mx_sat.document"]._upsert_from_metadata_row(
            row, self.company, request
        )
        self.assertEqual(doc2.id, doc.id)
        self.assertEqual(doc2.sat_status, "in_progress")

    def test_document_manual_write_is_blocked(self):
        request = self._create_request(request_type="metadata", state="done")
        row = {
            "uuid": "22222222-3333-4444-5555-666666666666",
            "sat_status": "valid",
            "total": "100.00",
        }
        doc = self.env["l10n_mx_sat.document"]._upsert_from_metadata_row(
            row, self.company, request
        )
        with self.assertRaises(AccessError):
            doc.write({"total": 999.99})

    def test_document_manual_write_with_context_is_blocked(self):
        request = self._create_request(request_type="metadata", state="done")
        doc = self.env["l10n_mx_sat.document"]._upsert_from_metadata_row(
            {
                "uuid": "55555555-6666-7777-8888-999999999999",
                "sat_status": "valid",
            },
            self.company,
            request,
        )
        with self.assertRaises(AccessError):
            doc.with_context(l10n_mx_sat_internal_update=True).write(
                {"sat_status": "cancelled"}
            )

    def test_document_manual_create_is_blocked(self):
        Document = self.env["l10n_mx_sat.document"]
        with self.assertRaises(AccessError):
            Document.create(
                {
                    "company_id": self.company.id,
                    "uuid": "33333333-4444-5555-6666-777777777777",
                    "document_kind": "cfdi",
                    "direction": "received",
                }
            )

    def test_document_form_action_is_readonly(self):
        request = self._create_request(request_type="metadata", state="done")
        doc = self.env["l10n_mx_sat.document"]._upsert_from_metadata_row(
            {
                "uuid": "44444444-5555-6666-7777-888888888888",
                "sat_status": "valid",
            },
            self.company,
            request,
        )
        action = doc.get_formview_action()
        self.assertFalse(action["context"].get("edit"))
        self.assertEqual(action["flags"].get("mode"), "readonly")

    def test_create_next_request_respects_metadata_window(self):
        self.env["l10n_mx_sat.download.request"].search(
            [("company_id", "=", self.company.id)]
        ).unlink()
        self.company.write(
            {
                "l10n_mx_sat_metadata_sync_from": "2025-01-01",
                "l10n_mx_sat_sync_from": False,
            }
        )
        req = self.env["l10n_mx_sat.download.request"]._create_next_request(
            self.company, "cfdi", "received", "metadata"
        )
        self.assertTrue(req)
        delta = req.date_to - req.date_from
        self.assertLessEqual(delta.days, 7)
        self.assertEqual(req.date_from.date().isoformat(), "2025-01-01")

    def test_manual_sync_creates_requests(self):
        """Manual sync must create and chain XML requests for enabled flows."""
        Request = self.env["l10n_mx_sat.download.request"]
        Request.search([("company_id", "=", self.company.id)]).unlink()

        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "sat_request_id": "SOL-MANUAL",
            "message": "Solicitud aceptada",
        }
        with self._patch_factory(client):
            Request.with_context(
                l10n_mx_sat_manual_sync=True,
                test_queue_job_no_delay=True,
            )._cron_process_requests(companies=self.company)

        requests = Request.search([("company_id", "=", self.company.id)])
        self.assertEqual(len(requests), 8)
        self.assertTrue(all(req.request_type == "xml" for req in requests))
        self.assertEqual(
            Request.search_count(
                [("company_id", "=", self.company.id), ("request_type", "=", "xml")]
            ),
            8,
        )

    def test_manual_sync_respects_download_flags(self):
        Request = self.env["l10n_mx_sat.download.request"]
        Request.search([("company_id", "=", self.company.id)]).unlink()
        self.company.write(
            {
                "l10n_mx_sat_download_cfdi_issued": True,
                "l10n_mx_sat_download_cfdi_received": False,
                "l10n_mx_sat_download_retention_issued": False,
                "l10n_mx_sat_download_retention_received": False,
            }
        )

        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "sat_request_id": "SOL-FLAG",
            "message": "Solicitud aceptada",
        }
        with self._patch_factory(client):
            Request.with_context(
                l10n_mx_sat_manual_sync=True,
                test_queue_job_no_delay=True,
            )._cron_process_requests(companies=self.company)

        requests = Request.search([("company_id", "=", self.company.id)])
        self.assertEqual(len(requests), 2)
        self.assertEqual(set(requests.mapped("document_kind")), {"cfdi"})
        self.assertEqual(set(requests.mapped("direction")), {"issued"})
        self.assertEqual(set(requests.mapped("request_type")), {"xml"})

    def test_manual_sync_with_all_flags_disabled_creates_nothing(self):
        Request = self.env["l10n_mx_sat.download.request"]
        Request.search([("company_id", "=", self.company.id)]).unlink()
        self.company.write(
            {
                "l10n_mx_sat_download_cfdi_issued": False,
                "l10n_mx_sat_download_cfdi_received": False,
                "l10n_mx_sat_download_retention_issued": False,
                "l10n_mx_sat_download_retention_received": False,
            }
        )

        Request.with_context(
            l10n_mx_sat_manual_sync=True,
            test_queue_job_no_delay=True,
        )._cron_process_requests(companies=self.company)

        self.assertEqual(
            Request.search_count([("company_id", "=", self.company.id)]),
            0,
        )

    def test_action_request_issued_uses_fiel_rfc_without_vat(self):
        self.company.vat = False
        client = self._mock_client()
        client.rfc = "RFCFIEL123"
        client.request_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "sat_request_id": "SOL-ISSUED",
            "message": "Solicitud aceptada",
        }
        req = self._create_request(document_kind="cfdi", direction="issued")
        with self._patch_factory(client):
            req._action_request()
        client.request_download.assert_called_once()
        self.assertEqual(client.request_download.call_args.args[1], "RFCFIEL123")
        self.assertEqual(req.state, "requested")

    def test_get_display_rfc_uses_fiel_when_vat_missing(self):
        self.company.write({"vat": False})
        self.env.invalidate_all()
        client = self._mock_client()
        client.rfc = "RFCFIEL123"
        Request = self.env["l10n_mx_sat.download.request"]
        with self._patch_factory(client):
            rfc = Request._get_display_rfc(self.company)
        self.assertEqual(rfc, "RFCFIEL123")

    def test_action_verify_no_info_rejected_5004(self):
        """Real SAT pattern: verify OK but no packages in range."""
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "request_status": SAT_REQUEST_STATUS_REJECTED,
            "request_status_code": SAT_CODE_NO_INFO,
            "reported_cfdi_count": 0,
            "packages": [],
            "message": "Solicitud Accepted",
        }
        req = self._create_request(
            document_kind="retention",
            direction="issued",
            state="requested",
            sat_request_id="012f356d-7d28-41a1-9c46-08c514aa5ed2",
        )
        with self._patch_factory(client):
            req._action_verify()
        self.assertEqual(req.state, "done")
        self.assertEqual(req.document_count, 0)
        self.assertEqual(req.reported_cfdi_count, 0)
        self.assertFalse(req.error_message)

    def test_action_verify_rejected_without_no_info_is_error(self):
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "request_status": SAT_REQUEST_STATUS_REJECTED,
            "request_status_code": "5001",
            "reported_cfdi_count": 0,
            "packages": [],
            "message": "Rejected",
        }
        req = self._create_request(
            state="requested",
            sat_request_id="SOL-REJECT",
        )
        with self._patch_factory(client):
            req._action_verify()
        self.assertEqual(req.state, "error")
        self.assertIn("EstadoSolicitud=5", req.error_message)
        self.assertIn("5001", req.error_message)

    def test_action_retry_from_error_without_sat_request_id(self):
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "sat_request_id": "SOL-RETRY",
            "message": "Solicitud aceptada",
        }
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "request_status": SAT_REQUEST_STATUS_REJECTED,
            "request_status_code": SAT_CODE_NO_INFO,
            "reported_cfdi_count": 0,
            "packages": [],
            "message": "Solicitud Accepted",
        }
        req = self._create_request(state="error", error_message="Fallo inicial")
        count_before = self.env["l10n_mx_sat.download.request"].search_count(
            [("company_id", "=", self.company.id)]
        )
        with self._patch_factory(client):
            req.action_retry()
        self.assertEqual(req.state, "done")
        self.assertFalse(req.error_message)
        self.assertEqual(
            self.env["l10n_mx_sat.download.request"].search_count(
                [("company_id", "=", self.company.id)]
            ),
            count_before,
        )

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_action_retry_retention_legacy_satcfdi_re_requests(
        self, mock_signer_load, mock_sat_cls
    ):
        """Retry without sat_request_id uses legacy recover_retencion_request."""
        legacy_sat = type(
            "LegacySat",
            (),
            {
                "_autentica_comprobante": lambda self: {
                    "AutenticaResult": "fake-token"
                },
                "recover_retencion_request": lambda self, **kwargs: {
                    "CodEstatus": SAT_CODE_SUCCESS,
                    "IdSolicitud": "SOL-RETRY-L",
                    "Mensaje": "Solicitud aceptada",
                },
                "recover_retencion_status": lambda self, sat_request_id: {
                    "CodEstatus": SAT_CODE_SUCCESS,
                    "EstadoSolicitud": SAT_REQUEST_STATUS_REJECTED,
                    "CodigoEstadoSolicitud": SAT_CODE_NO_INFO,
                    "NumeroCFDIs": 0,
                    "IdsPaquetes": [],
                    "Mensaje": "Solicitud Accepted",
                },
            },
        )()
        mock_sat_cls.return_value = legacy_sat
        mock_signer_load.return_value.rfc = self.company.vat
        req = self._create_request(
            document_kind="retention",
            direction="issued",
            state="error",
            error_message="Fallo inicial",
        )
        req.action_retry()
        self.assertEqual(req.state, "done")
        self.assertEqual(req.sat_request_id, "SOL-RETRY-L")
        self.assertFalse(req.error_message)

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_action_retry_retention_legacy_satcfdi_verify_only(
        self, mock_signer_load, mock_sat_cls
    ):
        """Retry with sat_request_id verifies via legacy recover_retencion_status."""
        legacy_sat = type(
            "LegacySat",
            (),
            {
                "_autentica_comprobante": lambda self: {
                    "AutenticaResult": "fake-token"
                },
                "recover_retencion_status": lambda self, sat_request_id: {
                    "CodEstatus": SAT_CODE_SUCCESS,
                    "EstadoSolicitud": SAT_REQUEST_STATUS_REJECTED,
                    "CodigoEstadoSolicitud": SAT_CODE_NO_INFO,
                    "NumeroCFDIs": 0,
                    "IdsPaquetes": [],
                    "Mensaje": "Solicitud Accepted",
                },
            },
        )()
        mock_sat_cls.return_value = legacy_sat
        mock_signer_load.return_value.rfc = self.company.vat
        req = self._create_request(
            document_kind="retention",
            direction="received",
            state="error",
            sat_request_id="SOL-EXISTING-L",
            error_message="Error de verificacion previo",
        )
        req.action_retry()
        self.assertEqual(req.state, "done")
        self.assertFalse(req.error_message)

    def test_action_retry_from_error_with_sat_request_id(self):
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "request_status": SAT_REQUEST_STATUS_REJECTED,
            "request_status_code": SAT_CODE_NO_INFO,
            "reported_cfdi_count": 0,
            "packages": [],
            "message": "Solicitud Accepted",
        }
        req = self._create_request(
            state="error",
            sat_request_id="SOL-EXISTING",
            error_message="Error de verificacion previo",
        )
        with self._patch_factory(client):
            req.action_retry()
        self.assertEqual(req.state, "done")
        self.assertFalse(req.error_message)
        client.request_download.assert_not_called()

    def test_can_retry_false_for_duplicate_5002(self):
        req = self._create_request(
            state="error",
            error_message="SAT: solicitud duplicada (5002).",
        )
        self.assertFalse(req.can_retry)

    def test_can_retry_false_for_daily_limit_5011(self):
        req = self._create_request(
            state="error",
            error_message="SAT: daily download limit reached (5011).",
        )
        self.assertFalse(req.can_retry)

    def test_action_verify_daily_limit(self):
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_DAILY_LIMIT,
            "request_status": 0,
            "request_status_code": "",
            "reported_cfdi_count": 0,
            "packages": [],
            "message": "Limit",
        }
        req = self._create_request(state="requested", sat_request_id="SOL-DAILY")
        with self._patch_factory(client):
            req._action_verify()
        self.assertEqual(req.state, "error")
        self.assertIn("5011", req.error_message)

    def test_action_verify_duplicate_5002(self):
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_DUPLICATE_LIFETIME,
            "request_status": 0,
            "request_status_code": "",
            "reported_cfdi_count": 0,
            "packages": [],
            "message": "Duplicate",
        }
        req = self._create_request(state="requested", sat_request_id="SOL-DUP")
        with self._patch_factory(client):
            req._action_verify()
        self.assertEqual(req.state, "error")
        self.assertIn("5002", req.error_message)

    def test_action_verify_accepted_sets_processing(self):
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "request_status": SAT_REQUEST_STATUS_ACCEPTED,
            "request_status_code": SAT_CODE_SUCCESS,
            "reported_cfdi_count": 5,
            "packages": [],
            "message": "Accepted",
        }
        req = self._create_request(state="requested", sat_request_id="SOL-ACC")
        with self._patch_factory(client):
            req._action_verify()
        self.assertEqual(req.state, "processing")
        self.assertEqual(req.reported_cfdi_count, 5)
        self.assertTrue(req.next_process_at)
        self.assertGreater(req.next_process_at, fields.Datetime.now())

    def test_action_verify_processing_sets_processing(self):
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "request_status": SAT_REQUEST_STATUS_PROCESSING,
            "request_status_code": SAT_CODE_SUCCESS,
            "reported_cfdi_count": 3,
            "packages": [],
            "message": "Processing",
        }
        req = self._create_request(state="requested", sat_request_id="SOL-PROC")
        with self._patch_factory(client):
            req._action_verify()
        self.assertEqual(req.state, "processing")
        self.assertEqual(req.reported_cfdi_count, 3)

    def test_action_verify_ready_creates_packages(self):
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "request_status": SAT_REQUEST_STATUS_READY,
            "request_status_code": SAT_CODE_SUCCESS,
            "reported_cfdi_count": 2,
            "packages": ["PKG-A", "PKG-B", "PKG-A"],
            "message": "Ready",
        }
        req = self._create_request(state="requested", sat_request_id="SOL-READY")
        self._create_package(req, "PKG-A")
        with self._patch_factory(client):
            req._action_verify()
        self.assertEqual(req.state, "ready")
        package_ids = req.package_ids.mapped("sat_package_id")
        self.assertEqual(sorted(package_ids), ["PKG-A", "PKG-B"])

    def test_action_verify_invalid_estado_zero(self):
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "request_status": 0,
            "request_status_code": "5000",
            "reported_cfdi_count": 0,
            "packages": [],
            "message": "Invalid",
        }
        req = self._create_request(state="requested", sat_request_id="SOL-ZERO")
        with self._patch_factory(client):
            req._action_verify()
        self.assertEqual(req.state, "error")
        self.assertIn("EstadoSolicitud (0)", req.error_message)

    def test_action_verify_error_status(self):
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "request_status": SAT_REQUEST_STATUS_ERROR,
            "request_status_code": "5001",
            "reported_cfdi_count": 0,
            "packages": [],
            "message": "SAT error",
        }
        req = self._create_request(state="requested", sat_request_id="SOL-ERR")
        with self._patch_factory(client):
            req._action_verify()
        self.assertEqual(req.state, "error")
        self.assertIn("EstadoSolicitud=4", req.error_message)

    def test_action_verify_expired_status(self):
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "request_status": SAT_REQUEST_STATUS_EXPIRED,
            "request_status_code": "5000",
            "reported_cfdi_count": 0,
            "packages": [],
            "message": "Expired",
        }
        req = self._create_request(state="requested", sat_request_id="SOL-EXP")
        with self._patch_factory(client):
            req._action_verify()
        self.assertEqual(req.state, "error")
        self.assertIn("EstadoSolicitud=6", req.error_message)

    def test_action_verify_unknown_status(self):
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "request_status": 99,
            "request_status_code": "5000",
            "reported_cfdi_count": 0,
            "packages": [],
            "message": "Unknown",
        }
        req = self._create_request(state="requested", sat_request_id="SOL-UNK")
        with self._patch_factory(client):
            req._action_verify()
        self.assertEqual(req.state, "error")
        self.assertIn("unrecognized request status", req.error_message)

    def test_action_download_xml_success(self):
        uuid = "11111111-2222-3333-4444-555555555555"
        xml_bytes = self._minimal_cfdi_xml(uuid=uuid)
        package_b64 = self._build_zip_b64({"cfdi.xml": xml_bytes})
        client = self._mock_client()
        client.download_package.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "package_b64": package_b64,
        }
        req = self._create_request(state="ready", sat_request_id="SOL-DL")
        self._create_package(req)
        self.company.l10n_mx_sat_last_sync = False
        with self._patch_factory(client):
            req._action_download()
        self.assertEqual(req.state, "done")
        self.assertEqual(req.document_count, 1)
        self.assertTrue(self.company.l10n_mx_sat_last_sync)
        doc = self.env["l10n_mx_sat.document"].search(
            [("uuid", "=", uuid), ("company_id", "=", self.company.id)]
        )
        self.assertTrue(doc.has_xml)
        self.assertTrue(doc.attachment_id)

    def test_action_download_metadata_success(self):
        metadata = (
            b"Uuid|RfcEmisor|RfcReceptor|Total|Estado\n"
            b"AAA-BBB|EKU9003173C9|AAA010101AAA|100.00|Valid\n"
        )
        package_b64 = self._build_zip_b64({"metadata.txt": metadata})
        client = self._mock_client()
        client.download_package.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "package_b64": package_b64,
        }
        req = self._create_request(
            request_type="metadata", state="ready", sat_request_id="SOL-META"
        )
        self._create_package(req)
        self.company.l10n_mx_sat_last_metadata_sync = False
        with self._patch_factory(client):
            req._action_download()
        self.assertEqual(req.state, "done")
        self.assertEqual(req.document_count, 1)
        self.assertTrue(self.company.l10n_mx_sat_last_metadata_sync)

    def test_action_download_skips_unsupported_and_invalid_files(self):
        package_b64 = self._build_zip_b64(
            {
                "readme.pdf": b"ignored",
                "bad.xml": b"<not-valid-xml",
            }
        )
        client = self._mock_client()
        client.download_package.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "package_b64": package_b64,
        }
        req = self._create_request(state="ready", sat_request_id="SOL-SKIP")
        self._create_package(req)
        with self._patch_factory(client):
            req._action_download()
        self.assertEqual(req.state, "done")
        self.assertEqual(req.document_count, 0)

    def test_action_download_package_expired(self):
        client = self._mock_client()
        client.download_package.return_value = {
            "cod_estatus": SAT_DOWNLOAD_EXPIRED,
            "package_b64": "",
        }
        req = self._create_request(state="ready", sat_request_id="SOL-PEXP")
        pkg = self._create_package(req)
        with self._patch_factory(client):
            req._action_download()
        self.assertEqual(pkg.state, "error")
        self.assertEqual(req.state, "error")
        self.assertIn("All packages failed", req.error_message)

    def test_action_download_package_max_reached(self):
        client = self._mock_client()
        client.download_package.return_value = {
            "cod_estatus": SAT_DOWNLOAD_MAX_REACHED,
            "package_b64": "",
        }
        req = self._create_request(state="ready", sat_request_id="SOL-PMAX")
        pkg = self._create_package(req)
        with self._patch_factory(client):
            req._action_download()
        self.assertEqual(pkg.state, "error")
        self.assertEqual(req.state, "error")

    @mute_logger("odoo.addons.l10n_mx_sat.models.l10n_mx_sat_download_request")
    def test_process_package_zip_bomb_guard(self):
        req = self._create_request()
        package_b64 = self._build_zip_b64({"cfdi.xml": b"<root/>"})
        with patch.object(
            type(req),
            "_ZIP_MAX_FILES",
            0,
        ):
            result = req._process_package(package_b64, self.company)
        self.assertEqual(result["processed"], 0)

    def test_get_retry_target_state_with_error_packages(self):
        req = self._create_request(state="error", sat_request_id="SOL-RPKG")
        pkg = self._create_package(req, state="error")
        Request = self.env["l10n_mx_sat.download.request"]
        target = Request.browse(req.id)._get_retry_target_state()
        self.assertEqual(target, "ready")
        self.assertEqual(pkg.state, "pending")

    def test_action_retry_returns_info_when_still_processing(self):
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "request_status": SAT_REQUEST_STATUS_PROCESSING,
            "request_status_code": SAT_CODE_SUCCESS,
            "reported_cfdi_count": 1,
            "packages": [],
            "message": "Processing",
        }
        req = self._create_request(
            state="error",
            sat_request_id="SOL-RINFO",
            error_message="Temporary failure",
        )
        with self._patch_factory(client):
            result = req.action_retry()
        self.assertEqual(req.state, "processing")
        self.assertEqual(result["params"]["type"], "info")

    def test_action_retry_pipeline_exception_raises_user_error(self):
        client = self._mock_client()
        client.request_download.side_effect = Exception("SAT down")
        req = self._create_request(state="error", error_message="Previous error")
        with self._patch_factory(client):
            with self.assertRaises(UserError) as err:
                req.action_retry()
        self.assertEqual(req.state, "error")
        self.assertIn("SAT down", str(err.exception))

    def test_parse_param_ids_filters_invalid(self):
        Request = self.env["l10n_mx_sat.download.request"]
        param = "l10n_mx_sat.test_param_ids"
        Request._write_param_ids(param, [1, 2])
        Request._add_param_ids(param, [2, 3, "x"])
        self.assertEqual(Request._parse_param_ids(param), [1, 2, 3])
        Request._remove_param_ids(param, [2])
        self.assertEqual(Request._parse_param_ids(param), [1, 3])
        Request._write_param_ids(param, [])
        self.assertEqual(Request._parse_param_ids(param), [])

    def test_action_queue_draft_requests(self):
        req = self._create_request()
        Request = self.env["l10n_mx_sat.download.request"]
        with patch.object(type(Request), "_cron_trigger") as mock_trigger:
            result = req.action_queue()
        queued = Request._parse_param_ids("l10n_mx_sat.queued_request_ids")
        self.assertIn(req.id, queued)
        mock_trigger.assert_called_once()
        self.assertEqual(result["params"]["type"], "success")

    def test_action_queue_non_draft_raises(self):
        req = self._create_request(state="requested", sat_request_id="SOL-Q")
        with self.assertRaises(UserError):
            req.action_queue()

    def test_collect_pending_work_prioritizes_queue(self):
        Request = self.env["l10n_mx_sat.download.request"]
        req1 = self._create_request(
            date_from="2026-03-01 00:00:00",
            date_to="2026-03-15 23:59:59",
        )
        req2 = self._create_request(
            date_from="2026-04-01 00:00:00",
            date_to="2026-04-15 23:59:59",
        )
        Request._write_param_ids("l10n_mx_sat.queued_request_ids", [req2.id, 999999])
        work = Request._collect_pending_work(self.company)
        self.assertEqual(work.ids[0], req2.id)
        self.assertIn(req1.id, work.ids)

    def test_cron_has_immediate_work(self):
        Request = self.env["l10n_mx_sat.download.request"]
        self.assertFalse(Request._cron_has_immediate_work([]))
        req = self._create_request()
        Request._write_param_ids("l10n_mx_sat.queued_request_ids", [req.id])
        self.assertTrue(Request._cron_has_immediate_work([]))
        Request._write_param_ids("l10n_mx_sat.queued_request_ids", [])
        self.assertTrue(Request._cron_has_immediate_work([self.company.id]))
        req.write(
            {
                "state": "processing",
                "sat_request_id": "SOL-WAIT",
                "next_process_at": fields.Datetime.now() + timedelta(hours=1),
            }
        )
        self.assertFalse(Request._cron_has_immediate_work([self.company.id]))

    def test_refresh_pending_companies_keeps_active(self):
        Request = self.env["l10n_mx_sat.download.request"]
        self._create_request()
        still = Request._refresh_pending_companies(self.company)
        self.assertIn(self.company.id, still)

    def test_refresh_pending_skips_when_auto_download_disabled(self):
        Request = self.env["l10n_mx_sat.download.request"]
        Request.search([("company_id", "=", self.company.id)]).unlink()
        self.company.l10n_mx_sat_auto_download = False
        still = Request._refresh_pending_companies(self.company)
        self.assertNotIn(self.company.id, still)

    def test_cron_process_requests_batch_size_one(self):
        Request = self.env["l10n_mx_sat.download.request"]
        Request.search([("company_id", "=", self.company.id)]).unlink()
        self._create_request(
            date_from="2026-05-01 00:00:00",
            date_to="2026-05-15 23:59:59",
        )
        self._create_request(
            date_from="2026-06-01 00:00:00",
            date_to="2026-06-15 23:59:59",
        )
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "sat_request_id": "SOL-BATCH",
            "message": "Solicitud aceptada",
        }
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "request_status": SAT_REQUEST_STATUS_REJECTED,
            "request_status_code": SAT_CODE_NO_INFO,
            "reported_cfdi_count": 0,
            "packages": [],
            "message": "Solicitud Accepted",
        }
        with (
            self._patch_factory(client),
            patch.object(type(Request), "_cron_trigger") as mock_trigger,
        ):
            Request._cron_process_requests(companies=self.company)
        processed = Request.search(
            [("company_id", "=", self.company.id), ("state", "!=", "draft")]
        )
        self.assertEqual(len(processed), 4)
        mock_trigger.assert_called_once_with()

    def test_cron_processing_defers_trigger(self):
        Request = self.env["l10n_mx_sat.download.request"]
        Request.search([("company_id", "=", self.company.id)]).unlink()
        self.company.write(
            {
                "l10n_mx_sat_download_cfdi_issued": False,
                "l10n_mx_sat_download_cfdi_received": True,
                "l10n_mx_sat_download_retention_issued": False,
                "l10n_mx_sat_download_retention_received": False,
                "l10n_mx_sat_auto_download": False,
            }
        )
        deferred_at = fields.Datetime.now() + timedelta(hours=1)
        self._create_request(
            state="processing",
            sat_request_id="SOL-DEFER",
            next_process_at=deferred_at,
        )
        Request._mark_company_sync_pending(self.company)
        with patch.object(type(Request), "_cron_trigger") as mock_trigger:
            Request._cron_process_requests(companies=self.company)
        mock_trigger.assert_called_once_with(at=deferred_at)

    def test_cron_draft_remaining_defers_when_waiting(self):
        Request = self.env["l10n_mx_sat.download.request"]
        Request.search([("company_id", "=", self.company.id)]).unlink()
        self.company.write(
            {
                "l10n_mx_sat_download_cfdi_issued": False,
                "l10n_mx_sat_download_cfdi_received": True,
                "l10n_mx_sat_download_retention_issued": False,
                "l10n_mx_sat_download_retention_received": False,
            }
        )
        deferred_at = fields.Datetime.now() + timedelta(hours=1)
        self._create_request(
            state="processing",
            sat_request_id="SOL-WAIT",
            date_from="2026-07-01 00:00:00",
            date_to="2026-07-15 23:59:59",
            next_process_at=deferred_at,
        )
        self._create_request(
            date_from="2026-08-01 00:00:00",
            date_to="2026-08-15 23:59:59",
        )
        self._create_request(
            date_from="2026-09-01 00:00:00",
            date_to="2026-09-15 23:59:59",
        )
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "sat_request_id": "SOL-DRAFT",
            "message": "Solicitud aceptada",
        }
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "request_status": SAT_REQUEST_STATUS_REJECTED,
            "request_status_code": SAT_CODE_NO_INFO,
            "reported_cfdi_count": 0,
            "packages": [],
            "message": "Solicitud Accepted",
        }
        with (
            self._patch_factory(client),
            patch.object(type(Request), "_cron_trigger") as mock_trigger,
        ):
            Request._cron_process_requests(companies=self.company)
        call_kwargs = mock_trigger.call_args.kwargs
        self.assertIn("at", call_kwargs)
        self.assertGreaterEqual(call_kwargs["at"], deferred_at)

    @mute_logger("odoo.addons.l10n_mx_sat.models.l10n_mx_sat_download_request")
    def test_cron_process_requests_handles_exception(self):
        Request = self.env["l10n_mx_sat.download.request"]
        req = self._create_request()
        client = self._mock_client()
        client.authenticate.side_effect = Exception("Auth failed")
        with self._patch_factory(client), patch.object(type(Request), "_cron_trigger"):
            Request._cron_process_requests(companies=self.company)
        self.assertEqual(req.state, "error")
        self.assertIn("Auth failed", req.error_message)

    def test_action_request_no_info_without_id_completes(self):
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": SAT_CODE_NO_INFO,
            "sat_request_id": "",
            "message": "No info",
        }
        req = self._create_request()
        self.company.l10n_mx_sat_last_sync = False
        with self._patch_factory(client):
            req._action_request()
        self.assertEqual(req.state, "done")
        self.assertTrue(self.company.l10n_mx_sat_last_sync)

    def test_action_request_reject_code(self):
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": "5001",
            "sat_request_id": "",
            "message": "Rejected",
        }
        req = self._create_request()
        with self._patch_factory(client):
            req._action_request()
        self.assertEqual(req.state, "error")
        self.assertIn("5001", req.error_message)

    def test_action_request_aceptada_fallback(self):
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": "9999",
            "sat_request_id": "SOL-ACEP",
            "message": "Solicitud aceptada por SAT",
        }
        req = self._create_request()
        with self._patch_factory(client):
            req._action_request()
        self.assertEqual(req.state, "requested")
        self.assertEqual(req.sat_request_id, "SOL-ACEP")

    def test_handle_max_elements_min_window_error(self):
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": SAT_CODE_MAX_ELEMENTS,
            "sat_request_id": "",
            "message": "Too many",
        }
        req = self._create_request(
            date_from="2026-02-01 00:00:00",
            date_to="2026-02-01 00:30:00",
        )
        with self._patch_factory(client):
            req._action_request()
        self.assertEqual(req.state, "error")
        self.assertIn("ventana minima", req.error_message)

    def test_build_fingerprint_from_string_dates(self):
        Request = self.env["l10n_mx_sat.download.request"]
        fp = Request._build_fingerprint_from_vals(
            {
                "company_id": self.company.id,
                "document_kind": "cfdi",
                "direction": "received",
                "request_type": "xml",
                "date_from": "2026-07-01 00:00:00",
                "date_to": "2026-07-31 23:59:59",
            }
        )
        self.assertTrue(fp)

    def test_action_verify_cod_estatus_no_info(self):
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_NO_INFO,
            "request_status": SAT_REQUEST_STATUS_REJECTED,
            "request_status_code": SAT_CODE_SUCCESS,
            "reported_cfdi_count": 0,
            "packages": [],
            "message": "No info",
        }
        req = self._create_request(state="requested", sat_request_id="SOL-NI")
        with self._patch_factory(client):
            req._action_verify()
        self.assertEqual(req.state, "done")
        self.assertEqual(req.document_count, 0)

    def test_get_sync_from_date_metadata_fallback(self):
        Request = self.env["l10n_mx_sat.download.request"]
        self.company.write(
            {
                "l10n_mx_sat_sync_from": "2025-01-01",
                "l10n_mx_sat_metadata_sync_from": False,
            }
        )
        sync_from = Request._get_sync_from_date(self.company, "metadata")
        self.assertEqual(str(sync_from), "2025-01-01")

    def test_mark_company_sync_pending_empty(self):
        Request = self.env["l10n_mx_sat.download.request"]
        Request._mark_company_sync_pending(self.env["res.company"].browse())
        self.assertEqual(
            Request._parse_param_ids("l10n_mx_sat.sync_pending_company_ids"),
            [],
        )

    def test_action_retry_wrong_state_raises(self):
        req = self._create_request(state="draft")
        with self.assertRaises(UserError):
            req.action_retry()

    def test_action_retry_non_retryable_raises(self):
        req = self._create_request(
            state="error",
            error_message="SAT: duplicate request (5002).",
        )
        with self.assertRaises(UserError):
            req.action_retry()

    def test_compute_can_retry_false_when_not_error(self):
        req = self._create_request(state="done")
        self.assertFalse(req.can_retry)

    def test_action_verify_max_elements_5003_splits(self):
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_MAX_ELEMENTS,
            "request_status": 0,
            "request_status_code": "",
            "reported_cfdi_count": 0,
            "packages": [],
            "message": "Tope maximo",
        }
        req = self._create_request(
            state="requested",
            sat_request_id="SOL-5003",
            date_from="2026-03-01 00:00:00",
            date_to="2026-03-31 23:59:59",
        )
        original_date_to = req.date_to
        with self._patch_factory(client):
            req._action_verify()
        self.assertEqual(req.state, "draft")
        self.assertIn("5003", req.error_message or "")
        mid = req.date_to
        second = self.env["l10n_mx_sat.download.request"].search(
            [
                ("company_id", "=", self.company.id),
                ("date_from", "=", mid + timedelta(seconds=1)),
                ("date_to", "=", original_date_to),
            ]
        )
        self.assertEqual(len(second), 1)
        self.assertEqual(second.state, "draft")

    def test_action_verify_max_elements_skips_existing_second_half(self):
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_MAX_ELEMENTS,
            "request_status": 0,
            "request_status_code": "",
            "reported_cfdi_count": 0,
            "packages": [],
            "message": "Tope maximo",
        }
        req = self._create_request(
            state="requested",
            sat_request_id="SOL-5003B",
            date_from="2026-03-01 00:00:00",
            date_to="2026-03-31 23:59:59",
        )
        mid = req.date_from + (req.date_to - req.date_from) / 2
        self._create_request(
            date_from=mid + timedelta(seconds=1),
            date_to=req.date_to,
            state="draft",
        )
        before = self.env["l10n_mx_sat.download.request"].search_count(
            [("company_id", "=", self.company.id)]
        )
        with self._patch_factory(client):
            req._action_verify()
        after = self.env["l10n_mx_sat.download.request"].search_count(
            [("company_id", "=", self.company.id)]
        )
        self.assertEqual(req.state, "draft")
        self.assertEqual(after, before)

    def test_action_download_partial_package_success(self):
        uuid = "33333333-4444-5555-6666-777777777777"
        package_ok = self._build_zip_b64(
            {"cfdi.xml": self._minimal_cfdi_xml(uuid=uuid)}
        )
        client = self._mock_client()

        def _download(_token, _rfc, package_id, document_kind="cfdi"):
            if package_id == "PKG-OK":
                return {"cod_estatus": SAT_CODE_SUCCESS, "package_b64": package_ok}
            return {"cod_estatus": SAT_CODE_SUCCESS, "package_b64": ""}

        client.download_package.side_effect = _download
        req = self._create_request(state="ready", sat_request_id="SOL-PART")
        pkg_ok = self._create_package(req, "PKG-OK")
        pkg_bad = self._create_package(req, "PKG-BAD")
        with self._patch_factory(client):
            req._action_download()
        self.assertEqual(pkg_ok.state, "processed")
        self.assertEqual(pkg_bad.state, "error")
        self.assertEqual(req.state, "done")
        self.assertGreaterEqual(req.document_count, 1)

    def test_action_download_empty_package_b64_marks_error(self):
        client = self._mock_client()
        client.download_package.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "package_b64": "",
        }
        req = self._create_request(state="ready", sat_request_id="SOL-EMPTY")
        pkg = self._create_package(req)
        with self._patch_factory(client):
            req._action_download()
        self.assertEqual(pkg.state, "error")
        self.assertEqual(req.state, "error")
        self.assertIn("All packages failed", req.error_message)

    @mute_logger("odoo.addons.l10n_mx_sat.models.l10n_mx_sat_download_request")
    def test_action_download_package_exception_marks_error(self):
        client = self._mock_client()
        client.download_package.side_effect = Exception("boom")
        req = self._create_request(state="ready", sat_request_id="SOL-EXC")
        pkg = self._create_package(req)
        with self._patch_factory(client):
            req._action_download()
        self.assertEqual(pkg.state, "error")
        self.assertEqual(req.state, "error")
        self.assertIn("All packages failed", req.error_message)

    def test_is_request_executable_states(self):
        Request = self.env["l10n_mx_sat.download.request"]
        now = fields.Datetime.now()
        draft = self._create_request(state="draft")
        ready = self._create_request(
            state="ready",
            date_from="2026-04-01 00:00:00",
            date_to="2026-04-15 23:59:59",
        )
        waiting_now = self._create_request(
            state="requested",
            sat_request_id="SOL-W1",
            date_from="2026-04-16 00:00:00",
            date_to="2026-04-20 23:59:59",
            next_process_at=False,
        )
        waiting_past = self._create_request(
            state="processing",
            sat_request_id="SOL-W2",
            date_from="2026-04-21 00:00:00",
            date_to="2026-04-25 23:59:59",
            next_process_at=now - timedelta(hours=1),
        )
        waiting_future = self._create_request(
            state="processing",
            sat_request_id="SOL-W3",
            date_from="2026-04-26 00:00:00",
            date_to="2026-04-30 23:59:59",
            next_process_at=now + timedelta(hours=1),
        )
        done = self._create_request(
            state="done",
            date_from="2026-05-01 00:00:00",
            date_to="2026-05-05 23:59:59",
        )
        self.assertTrue(Request._is_request_executable(draft, now=now))
        self.assertTrue(Request._is_request_executable(ready, now=now))
        self.assertTrue(Request._is_request_executable(waiting_now, now=now))
        self.assertTrue(Request._is_request_executable(waiting_past, now=now))
        self.assertFalse(Request._is_request_executable(waiting_future, now=now))
        self.assertFalse(Request._is_request_executable(done, now=now))

    def test_ensure_scheduled_skips_last_error_5002(self):
        Request = self.env["l10n_mx_sat.download.request"]
        Request.search([("company_id", "=", self.company.id)]).unlink()
        self.company.write(
            {
                "l10n_mx_sat_download_cfdi_issued": False,
                "l10n_mx_sat_download_cfdi_received": True,
                "l10n_mx_sat_download_retention_issued": False,
                "l10n_mx_sat_download_retention_received": False,
            }
        )
        self._create_request(
            state="error",
            error_message="SAT: duplicate request limit reached (5002).",
            date_from="2026-06-01 00:00:00",
            date_to="2026-06-15 23:59:59",
        )
        Request._ensure_scheduled_requests(self.company)
        drafts = Request.search(
            [
                ("company_id", "=", self.company.id),
                ("state", "=", "draft"),
                ("document_kind", "=", "cfdi"),
                ("direction", "=", "received"),
            ]
        )
        self.assertFalse(drafts)

    def test_create_next_request_returns_empty_when_caught_up(self):
        Request = self.env["l10n_mx_sat.download.request"]
        yesterday_eod = (fields.Datetime.now() - timedelta(days=1)).replace(
            hour=23, minute=59, second=59, microsecond=0
        )
        self._create_request(
            state="done",
            date_from=yesterday_eod - timedelta(days=7),
            date_to=yesterday_eod,
        )
        nxt = Request._create_next_request(self.company, "cfdi", "received", "xml")
        self.assertFalse(nxt)

    def test_get_display_rfc_exception_falls_back_to_name(self):
        self.company.write({"vat": False, "name": "Fallback Co"})
        self.env.invalidate_all()
        Request = self.env["l10n_mx_sat.download.request"]
        with patch(
            "odoo.addons.l10n_mx_sat.models.res_company.ResCompany.l10n_mx_sat_get_rfc",
            side_effect=UserError("no rfc"),
        ):
            rfc = Request._get_display_rfc(self.company)
        self.assertEqual(rfc, "Fallback Co")

    def test_action_retry_success_notification(self):
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "request_status": SAT_REQUEST_STATUS_REJECTED,
            "request_status_code": SAT_CODE_NO_INFO,
            "reported_cfdi_count": 0,
            "packages": [],
            "message": "Solicitud Accepted",
        }
        req = self._create_request(
            state="error",
            sat_request_id="SOL-OK-RETRY",
            error_message="temporary verify error",
            date_from="2026-07-01 00:00:00",
            date_to="2026-07-07 23:59:59",
        )
        with self._patch_factory(client):
            action = req.action_retry()
        self.assertEqual(req.state, "done")
        self.assertEqual(action["params"]["type"], "success")
        self.assertIn("Processed", action["params"]["message"])

    def test_action_retry_danger_notification(self):
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "request_status": SAT_REQUEST_STATUS_REJECTED,
            "request_status_code": "5005",
            "reported_cfdi_count": 0,
            "packages": [],
            "message": "Rejected again",
        }
        req = self._create_request(
            state="error",
            sat_request_id="SOL-BAD-RETRY",
            error_message="temporary verify error",
            date_from="2026-07-08 00:00:00",
            date_to="2026-07-10 23:59:59",
        )
        with self._patch_factory(client):
            action = req.action_retry()
        self.assertEqual(req.state, "error")
        self.assertEqual(action["params"]["type"], "danger")
        self.assertTrue(action["params"]["sticky"])

    def test_cron_trigger_with_and_without_at(self):
        Request = self.env["l10n_mx_sat.download.request"]
        cron = self.env.ref("l10n_mx_sat.ir_cron_sat_download")
        with patch.object(type(cron), "_trigger") as mock_trigger:
            Request._cron_trigger()
            mock_trigger.assert_called_once_with()
            mock_trigger.reset_mock()
            at = fields.Datetime.now() + timedelta(minutes=5)
            Request._cron_trigger(at=at)
            mock_trigger.assert_called_once_with(at=at)

    def test_sat_label_helpers(self):
        Request = self.env["l10n_mx_sat.download.request"]
        self.assertTrue(Request._sat_request_status_label(SAT_REQUEST_STATUS_READY))
        self.assertEqual(Request._sat_status_code_label(""), "(empty)")
        self.assertEqual(
            Request._sat_status_code_label(SAT_CODE_SUCCESS),
            SAT_STATUS_CODE_LABELS[SAT_CODE_SUCCESS],
        )
        self.assertEqual(
            Request._sat_status_code_label("9999"),
            "9999",
        )
        self.assertEqual(Request._selection_label("state", "draft"), "Draft")
        self.assertFalse(Request._selection_label("state", False))

    def test_create_next_request_empty_on_fingerprint_collision(self):
        Request = self.env["l10n_mx_sat.download.request"]
        fake_done = MagicMock()
        fake_done.date_to = datetime(2026, 1, 15, 23, 59, 59)
        with patch.object(
            type(Request),
            "search",
            side_effect=[fake_done, Request.browse([1])],
        ):
            nxt = Request._create_next_request(self.company, "cfdi", "received", "xml")
        self.assertFalse(nxt)

    def test_get_display_rfc_falls_back_to_question_mark(self):
        Request = self.env["l10n_mx_sat.download.request"]
        company = self.company.new(
            {
                "vat": False,
                "name": False,
                "l10n_mx_sat_fiel_cer": False,
                "l10n_mx_sat_fiel_key": False,
                "l10n_mx_sat_fiel_password": False,
            }
        )
        self.assertEqual(Request._get_display_rfc(company), "?")

    def test_action_request_unknown_response_writes_error(self):
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": "8888",
            "sat_request_id": "",
            "message": "Weird SAT reply",
        }
        req = self._create_request(
            date_from="2026-08-01 00:00:00",
            date_to="2026-08-05 23:59:59",
        )
        with self._patch_factory(client):
            req._action_request()
        self.assertEqual(req.state, "error")
        self.assertIn("8888", req.error_message)

    def test_process_pipeline_downloads_when_ready(self):
        uuid = "PIPE-READY-UUID-1234567890123456789012"
        package_b64 = self._build_zip_b64(
            {"cfdi.xml": self._minimal_cfdi_xml(uuid=uuid)}
        )
        client = self._mock_client()
        client.download_package.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "package_b64": package_b64,
        }
        req = self._create_request(
            state="ready",
            sat_request_id="SOL-PIPE",
            date_from="2026-08-06 00:00:00",
            date_to="2026-08-10 23:59:59",
        )
        self._create_package(req)
        with self._patch_factory(client):
            req._process_request_pipeline()
        self.assertEqual(req.state, "done")

    def test_action_download_metadata_skips_non_text_files(self):
        metadata = (
            b"Uuid|RfcEmisor|RfcReceptor|Total|Estado\n"
            b"META-SKIP|EKU9003173C9|AAA010101AAA|10.00|Valid\n"
        )
        package_b64 = self._build_zip_b64(
            {"notes.pdf": b"ignored", "metadata.txt": metadata}
        )
        client = self._mock_client()
        client.download_package.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "package_b64": package_b64,
        }
        req = self._create_request(
            request_type="metadata",
            state="ready",
            sat_request_id="SOL-META-SKIP",
            date_from="2026-08-11 00:00:00",
            date_to="2026-08-15 23:59:59",
        )
        self._create_package(req)
        with self._patch_factory(client):
            req._action_download()
        self.assertEqual(req.state, "done")
        self.assertEqual(req.document_count, 1)

    def test_refresh_pending_schedules_when_idle_with_auto_download(self):
        Request = self.env["l10n_mx_sat.download.request"]
        Request.search([("company_id", "=", self.company.id)]).unlink()
        self.company.write(
            {
                "l10n_mx_sat_auto_download": True,
                "l10n_mx_sat_download_cfdi_issued": False,
                "l10n_mx_sat_download_cfdi_received": True,
                "l10n_mx_sat_download_retention_issued": False,
                "l10n_mx_sat_download_retention_received": False,
                "l10n_mx_sat_sync_from": "2026-01-01",
            }
        )
        still = Request._refresh_pending_companies(self.company)
        self.assertIn(self.company.id, still)
        self.assertTrue(
            Request.search(
                [
                    ("company_id", "=", self.company.id),
                    ("state", "=", "draft"),
                    ("direction", "=", "received"),
                ]
            )
        )

    def test_cron_process_requests_without_companies_arg(self):
        Request = self.env["l10n_mx_sat.download.request"]
        Request.search([("company_id", "=", self.company.id)]).unlink()
        self.company.write(
            {
                "l10n_mx_sat_auto_download": True,
                "l10n_mx_sat_download_cfdi_issued": False,
                "l10n_mx_sat_download_cfdi_received": True,
                "l10n_mx_sat_download_retention_issued": False,
                "l10n_mx_sat_download_retention_received": False,
                "l10n_mx_sat_sync_from": "2026-01-10",
            }
        )
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "sat_request_id": "SOL-AUTO",
            "message": "Solicitud aceptada",
        }
        client.verify_download.return_value = {
            "cod_estatus": SAT_CODE_SUCCESS,
            "request_status": SAT_REQUEST_STATUS_REJECTED,
            "request_status_code": SAT_CODE_NO_INFO,
            "reported_cfdi_count": 0,
            "packages": [],
            "message": "Accepted",
        }
        with (
            self._patch_factory(client),
            patch.object(type(Request), "_cron_trigger"),
        ):
            Request._cron_process_requests()
        self.assertTrue(
            Request.search(
                [("company_id", "=", self.company.id), ("state", "!=", "draft")]
            )
        )

    def test_create_next_request_uses_sync_from_without_last_done(self):
        Request = self.env["l10n_mx_sat.download.request"]
        Request.search([("company_id", "=", self.company.id)]).unlink()
        self.company.write({"l10n_mx_sat_sync_from": "2026-02-01"})
        req = Request._create_next_request(self.company, "cfdi", "received", "xml")
        self.assertTrue(req)
        self.assertEqual(req.date_from.date().isoformat(), "2026-02-01")

    def test_create_next_request_strips_timezone_from_date_from(self):
        from datetime import timezone

        Request = self.env["l10n_mx_sat.download.request"]
        Request.search([("company_id", "=", self.company.id)]).unlink()
        aware = datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
        empty = Request.browse()
        fake_done = MagicMock()
        fake_done.date_to = aware
        with patch.object(
            type(Request),
            "search",
            side_effect=[fake_done, empty, empty, empty],
        ):
            req = Request._create_next_request(self.company, "cfdi", "received", "xml")
        self.assertTrue(req)
        self.assertIsNone(req.date_from.tzinfo)


@tagged("post_install", "-at_install")
class TestMultiCompanySAT(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref("l10n_mx_sat.group_sat_manager")
        cls.company_a = cls.env.ref("base.main_company")
        cls.company_a.write(
            {
                "vat": "EKU9003173C9",
                "country_id": cls.env.ref("base.mx").id,
                "l10n_mx_sat_fiel_cer": b"ZmFrZQ==",
                "l10n_mx_sat_fiel_key": b"ZmFrZQ==",
                "l10n_mx_sat_fiel_password": "test-a",
            }
        )
        cls.company_b = cls.env["res.company"].create(
            {
                "name": "Empresa B SAT",
                "vat": "AAA010101AAA",
                "country_id": cls.env.ref("base.mx").id,
                "l10n_mx_sat_fiel_cer": b"ZmFrZQ==",
                "l10n_mx_sat_fiel_key": b"ZmFrZQ==",
                "l10n_mx_sat_fiel_password": "test-b",
            }
        )

    def test_documents_isolated_by_company(self):
        req_a = self.env["l10n_mx_sat.download.request"].create(
            {
                "company_id": self.company_a.id,
                "document_kind": "cfdi",
                "direction": "received",
                "request_type": "metadata",
                "date_from": "2026-01-01 00:00:00",
                "date_to": "2026-01-31 23:59:59",
                "state": "done",
            }
        )
        req_b = self.env["l10n_mx_sat.download.request"].create(
            {
                "company_id": self.company_b.id,
                "document_kind": "cfdi",
                "direction": "received",
                "request_type": "metadata",
                "date_from": "2026-01-01 00:00:00",
                "date_to": "2026-01-31 23:59:59",
                "state": "done",
            }
        )
        uuid = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
        self.env["l10n_mx_sat.document"]._upsert_from_metadata_row(
            {"uuid": uuid, "sat_status": "valid"},
            self.company_a,
            req_a,
        )
        self.env["l10n_mx_sat.document"]._upsert_from_metadata_row(
            {"uuid": uuid, "sat_status": "cancelled"},
            self.company_b,
            req_b,
        )
        docs_a = (
            self.env["l10n_mx_sat.document"]
            .with_company(self.company_a)
            .search(
                [
                    ("uuid", "=", uuid),
                    ("company_id", "=", self.company_a.id),
                ]
            )
        )
        docs_b = (
            self.env["l10n_mx_sat.document"]
            .with_company(self.company_b)
            .search(
                [
                    ("uuid", "=", uuid),
                    ("company_id", "=", self.company_b.id),
                ]
            )
        )
        self.assertEqual(len(docs_a), 1)
        self.assertEqual(len(docs_b), 1)
        self.assertEqual(docs_a.sat_status, "valid")
        self.assertEqual(docs_b.sat_status, "cancelled")
