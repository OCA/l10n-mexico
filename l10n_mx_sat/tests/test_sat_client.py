# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services import SatClient

_SVC = "odoo.addons.l10n_mx_sat.services.sat_client"


@tagged("post_install", "-at_install")
class TestSatClient(TransactionCase):
    """Tests for the SatClient adapter (pure Python class)."""

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_init_creates_signer_and_sat(self, mock_signer_load, mock_sat_cls):
        SatClient(b"cer", b"key", "pwd")
        mock_signer_load.assert_called_once_with(
            certificate=b"cer", key=b"key", password="pwd"
        )
        mock_sat_cls.assert_called_once()

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_authenticate_returns_token(self, mock_signer_load, mock_sat_cls):
        mock_sat_cls.return_value._autentica_comprobante.return_value = {
            "AutenticaResult": "tok-123"
        }
        client = SatClient(b"cer", b"key", "pwd")
        self.assertEqual(client.authenticate(), "tok-123")

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_request_download_received_cfdi(self, mock_signer_load, mock_sat_cls):
        mock_sat_cls.return_value.recover_comprobante_received_request.return_value = {
            "CodEstatus": "5000",
            "IdSolicitud": "SOL-1",
            "Mensaje": "Accepted",
        }
        client = SatClient(b"cer", b"key", "pwd")
        result = client.request_download(
            "tok", "RFC1", "2026-01-01", "2026-01-31", direction="received"
        )
        self.assertEqual(result["sat_request_id"], "SOL-1")
        mock_method = mock_sat_cls.return_value.recover_comprobante_received_request
        mock_method.assert_called_once()

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_request_download_emitted_cfdi_passes_issuer_rfc(
        self, mock_signer_load, mock_sat_cls
    ):
        mock_sat_cls.return_value.recover_comprobante_emitted_request.return_value = {
            "CodEstatus": "5000",
            "IdSolicitud": "SOL-E",
            "Mensaje": "Accepted",
        }
        client = SatClient(b"cer", b"key", "pwd")
        client.request_download(
            "tok",
            "RFC1",
            "2026-01-01",
            "2026-01-31",
            direction="issued",
        )
        mock_method = mock_sat_cls.return_value.recover_comprobante_emitted_request
        call_kwargs = mock_method.call_args.kwargs
        self.assertEqual(call_kwargs.get("rfc_emisor"), "RFC1")
        self.assertNotIn("tipo_comprobante", call_kwargs)

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_request_download_emitted_retention(self, mock_signer_load, mock_sat_cls):
        mock_sat_cls.return_value.recover_retencion_emitted_request.return_value = {
            "CodEstatus": "5000",
            "IdSolicitud": "SOL-R",
            "Mensaje": "Accepted",
        }
        client = SatClient(b"cer", b"key", "pwd")
        client.request_download(
            "tok",
            "RFC1",
            "2026-01-01",
            "2026-01-31",
            document_kind="retention",
            direction="issued",
        )
        mock_sat_cls.return_value.recover_retencion_emitted_request.assert_called_once()

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_request_download_metadata(self, mock_signer_load, mock_sat_cls):
        mock_sat_cls.return_value.recover_comprobante_received_request.return_value = {}
        client = SatClient(b"cer", b"key", "pwd")
        client.request_download(
            "tok",
            "RFC1",
            "2026-01-01",
            "2026-01-31",
            request_type="metadata",
        )
        mock_method = mock_sat_cls.return_value.recover_comprobante_received_request
        call_kwargs = mock_method.call_args.kwargs
        tipo = call_kwargs.get("tipo_solicitud")
        tipo_value = getattr(tipo, "value", tipo)
        self.assertEqual(tipo_value, "Metadata")

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_verify_retention_status(self, mock_signer_load, mock_sat_cls):
        mock_sat_cls.return_value.recover_retencion_status.return_value = {
            "CodEstatus": "5000",
            "EstadoSolicitud": 3,
            "CodigoEstadoSolicitud": "5000",
            "NumeroCFDIs": 1,
            "IdsPaquetes": ["PKG-1"],
            "Mensaje": "Completed",
        }
        client = SatClient(b"cer", b"key", "pwd")
        result = client.verify_download(
            "tok", "RFC1", "SOL-1", document_kind="retention"
        )
        self.assertEqual(result["request_status"], 3)
        mock_sat_cls.return_value.recover_retencion_status.assert_called_once()

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_verify_retention_no_info_response(self, mock_signer_load, mock_sat_cls):
        mock_sat_cls.return_value.recover_retencion_status.return_value = {
            "CodEstatus": "5000",
            "EstadoSolicitud": 5,
            "CodigoEstadoSolicitud": "5004",
            "NumeroCFDIs": 0,
            "IdsPaquetes": [],
            "Mensaje": "Solicitud Accepted",
        }
        client = SatClient(b"cer", b"key", "pwd")
        result = client.verify_download(
            "tok", "RFC1", "SOL-1", document_kind="retention"
        )
        self.assertEqual(result["cod_estatus"], "5000")
        self.assertEqual(result["request_status"], 5)
        self.assertEqual(result["request_status_code"], "5004")
        self.assertEqual(result["packages"], [])

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_download_retention_package(self, mock_signer_load, mock_sat_cls):
        mock_sat_cls.return_value.recover_retencion_download.return_value = (
            {"CodEstatus": "5000", "Mensaje": "OK"},
            "b64data",
        )
        client = SatClient(b"cer", b"key", "pwd")
        result = client.download_package(
            "tok", "RFC1", "PKG-1", document_kind="retention"
        )
        self.assertEqual(result["package_b64"], "b64data")

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_request_download_defaults_estado_comprobante(
        self, mock_signer_load, mock_sat_cls
    ):
        mock_sat_cls.return_value.recover_comprobante_received_request.return_value = {}
        client = SatClient(b"cer", b"key", "pwd")
        client.request_download("tok", "RFC1", "2026-01-01", "2026-01-31")
        mock_method = mock_sat_cls.return_value.recover_comprobante_received_request
        call_kwargs = mock_method.call_args.kwargs
        self.assertEqual(call_kwargs.get("estado_comprobante"), "Vigente")
