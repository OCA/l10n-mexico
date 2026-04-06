# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services import SatClient

_SVC = "odoo.addons.l10n_mx_sat.services.sat_client"


@tagged("post_install", "-at_install")
class TestSatClient(TransactionCase):
    """Tests for the SatClient adapter (pure Python class)."""

    @patch(f"{_SVC}.Fiel")
    def test_init_creates_fiel(self, MockFiel):
        SatClient(b"cer", b"key", "pwd")
        MockFiel.assert_called_once_with(b"cer", b"key", "pwd")

    @patch(f"{_SVC}.Autenticacion")
    @patch(f"{_SVC}.Fiel")
    def test_authenticate_returns_token(self, MockFiel, MockAuth):
        MockAuth.return_value.obtener_token.return_value = "tok-123"
        client = SatClient(b"cer", b"key", "pwd")

        token = client.authenticate()

        self.assertEqual(token, "tok-123")
        MockAuth.assert_called_once_with(MockFiel.return_value)

    @patch(f"{_SVC}.Autenticacion")
    @patch(f"{_SVC}.Fiel")
    def test_authenticate_empty_token_raises(self, MockFiel, MockAuth):
        MockAuth.return_value.obtener_token.return_value = ""
        client = SatClient(b"cer", b"key", "pwd")

        with self.assertRaises(ValueError):
            client.authenticate()

    @patch(f"{_SVC}.SolicitaDescargaRecibidos")
    @patch(f"{_SVC}.Fiel")
    def test_request_download(self, MockFiel, MockSolicita):
        expected = {"cod_estatus": "5000", "id_solicitud": "SOL-1"}
        MockSolicita.return_value.solicitar_descarga.return_value = expected
        client = SatClient(b"cer", b"key", "pwd")

        result = client.request_download("tok", "RFC1", "2026-01-01", "2026-01-31")

        self.assertEqual(result, expected)

    @patch(f"{_SVC}.SolicitaDescargaRecibidos")
    @patch(f"{_SVC}.Fiel")
    def test_request_download_defaults_estado_comprobante(self, MockFiel, MockSolicita):
        """estado_comprobante defaults to 'Vigente' (cfdiclient bug workaround)."""
        MockSolicita.return_value.solicitar_descarga.return_value = {}
        client = SatClient(b"cer", b"key", "pwd")

        client.request_download("tok", "RFC1", "2026-01-01", "2026-01-31")

        call_kwargs = MockSolicita.return_value.solicitar_descarga.call_args
        self.assertEqual(call_kwargs.kwargs.get("estado_comprobante"), "Vigente")

    @patch(f"{_SVC}.SolicitaDescargaRecibidos")
    @patch(f"{_SVC}.Fiel")
    def test_request_download_allows_override_estado(self, MockFiel, MockSolicita):
        """Caller can still override estado_comprobante if needed."""
        MockSolicita.return_value.solicitar_descarga.return_value = {}
        client = SatClient(b"cer", b"key", "pwd")

        client.request_download(
            "tok",
            "RFC1",
            "2026-01-01",
            "2026-01-31",
            estado_comprobante="Cancelado",
        )

        call_kwargs = MockSolicita.return_value.solicitar_descarga.call_args
        self.assertEqual(call_kwargs.kwargs.get("estado_comprobante"), "Cancelado")

    @patch(f"{_SVC}.VerificaSolicitudDescarga")
    @patch(f"{_SVC}.Fiel")
    def test_verify_download(self, MockFiel, MockVerifica):
        expected = {"estado_solicitud": "3", "paquetes": ["PKG-1"]}
        MockVerifica.return_value.verificar_descarga.return_value = expected
        client = SatClient(b"cer", b"key", "pwd")

        result = client.verify_download("tok", "RFC1", "SOL-1")

        self.assertEqual(result, expected)

    @patch(f"{_SVC}.DescargaMasiva")
    @patch(f"{_SVC}.Fiel")
    def test_download_package(self, MockFiel, MockDescarga):
        expected = {"cod_estatus": "5000", "paquete_b64": "b64data"}
        MockDescarga.return_value.descargar_paquete.return_value = expected
        client = SatClient(b"cer", b"key", "pwd")

        result = client.download_package("tok", "RFC1", "PKG-1")

        self.assertEqual(result, expected)

    @patch(f"{_SVC}.Validacion")
    @patch(f"{_SVC}.Fiel")
    def test_validate_cfdi(self, MockFiel, MockValidacion):
        expected = {"estado": "Vigente"}
        MockValidacion.return_value.obtener_estado.return_value = expected
        client = SatClient(b"cer", b"key", "pwd")

        result = client.validate_cfdi("RFC1", "RFC2", "100.00", "uuid-1")

        self.assertEqual(result, expected)
