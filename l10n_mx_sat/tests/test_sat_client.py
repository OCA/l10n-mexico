# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from unittest.mock import MagicMock, patch

from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services import SatClient
from ..services.sat_client import EstadoComprobante

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
    def test_request_download_retention_legacy_satcfdi(
        self, mock_signer_load, mock_sat_cls
    ):
        legacy_sat = type(
            "LegacySat",
            (),
            {
                "recover_retencion_request": lambda self, **kwargs: {
                    "CodEstatus": "5000",
                    "IdSolicitud": "SOL-L",
                    "Mensaje": "Accepted",
                }
            },
        )()
        mock_sat_cls.return_value = legacy_sat
        client = SatClient(b"cer", b"key", "pwd")
        result = client.request_download(
            "tok",
            "RFC1",
            "2026-01-01",
            "2026-01-31",
            document_kind="retention",
            direction="issued",
        )
        self.assertEqual(result["sat_request_id"], "SOL-L")

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_request_download_retention_received_legacy_satcfdi(
        self, mock_signer_load, mock_sat_cls
    ):
        legacy_sat = type(
            "LegacySat",
            (),
            {
                "recover_retencion_request": lambda self, **kwargs: {
                    "CodEstatus": "5000",
                    "IdSolicitud": "SOL-L-R",
                    "Mensaje": "Accepted",
                }
            },
        )()
        mock_sat_cls.return_value = legacy_sat
        client = SatClient(b"cer", b"key", "pwd")
        result = client.request_download(
            "tok",
            "RFC1",
            "2026-01-01",
            "2026-01-31",
            document_kind="retention",
            direction="received",
        )
        self.assertEqual(result["sat_request_id"], "SOL-L-R")

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_verify_retention_status_legacy_satcfdi(
        self, mock_signer_load, mock_sat_cls
    ):
        legacy_sat = type(
            "LegacySat",
            (),
            {
                "recover_retencion_request": lambda self, **kwargs: {},
                "recover_retencion_status": lambda self, sat_request_id: {
                    "CodEstatus": "5000",
                    "EstadoSolicitud": 3,
                    "CodigoEstadoSolicitud": "5000",
                    "NumeroCFDIs": 1,
                    "IdsPaquetes": ["PKG-L"],
                    "Mensaje": "Completed",
                },
            },
        )()
        mock_sat_cls.return_value = legacy_sat
        client = SatClient(b"cer", b"key", "pwd")
        result = client.verify_download(
            "tok", "RFC1", "SOL-L", document_kind="retention"
        )
        self.assertEqual(result["request_status"], 3)
        self.assertEqual(result["packages"], ["PKG-L"])

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
        self.assertEqual(
            call_kwargs.get("estado_comprobante"), EstadoComprobante.VIGENTE
        )

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_authenticate_empty_token_raises(self, mock_signer_load, mock_sat_cls):
        mock_sat_cls.return_value._autentica_comprobante.return_value = {}
        client = SatClient(b"cer", b"key", "pwd")
        with self.assertRaisesRegex(ValueError, "empty token"):
            client.authenticate()

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_ensure_token_empty_raises(self, mock_signer_load, mock_sat_cls):
        client = SatClient(b"cer", b"key", "pwd")
        with self.assertRaisesRegex(ValueError, "SAT token is required"):
            client.request_download("", "RFC1", "2026-01-01", "2026-01-31")

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_get_sat_method_missing_retention_raises(
        self, mock_signer_load, mock_sat_cls
    ):
        mock_sat_cls.return_value = type("BareSat", (), {})()
        client = SatClient(b"cer", b"key", "pwd")
        with self.assertRaisesRegex(
            AttributeError, "recover_retencion_emitted_request"
        ):
            client.request_download(
                "tok",
                "RFC1",
                "2026-01-01",
                "2026-01-31",
                document_kind="retention",
                direction="issued",
            )

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_validate_cfdi_parses_response(self, mock_signer_load, mock_sat_cls):
        result_xml = etree.fromstring(
            b'<Envelope xmlns="http://schemas.xmlsoap.org/soap/envelope/">'
            b"<Body><ConsultaResponse><ConsultaResult>"
            b"<CodigoEstatus>S - Comprobante obtenido satisfactoriamente."
            b"</CodigoEstatus>"
            b"<EsCancelable>No cancelable</EsCancelable>"
            b"<Estado>Vigente</Estado>"
            b"</ConsultaResult></ConsultaResponse></Body></Envelope>"
        )
        mock_sat_cls.return_value._request.return_value = result_xml
        client = SatClient(b"cer", b"key", "pwd")
        result = client.validate_cfdi("EMI123", "REC456", "100.00", "uuid-1")
        self.assertEqual(result["estado"], "Vigente")
        self.assertIn("Comprobante obtenido", result["codigo_estatus"])

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_verify_status_enum_estado_value(self, mock_signer_load, mock_sat_cls):
        estado = MagicMock()
        estado.value = 3
        mock_sat_cls.return_value.recover_comprobante_status.return_value = {
            "CodEstatus": "5000",
            "EstadoSolicitud": estado,
            "CodigoEstadoSolicitud": "5000",
            "NumeroCFDIs": 0,
            "IdsPaquetes": [],
            "Mensaje": "Completed",
        }
        client = SatClient(b"cer", b"key", "pwd")
        result = client.verify_download("tok", "RFC1", "SOL-1")
        self.assertEqual(result["request_status"], 3)

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_request_download_cfdi_with_optional_filters(
        self, mock_signer_load, mock_sat_cls
    ):
        mock_sat_cls.return_value.recover_comprobante_received_request.return_value = {
            "CodEstatus": "5000",
            "IdSolicitud": "SOL-F",
            "Mensaje": "Accepted",
        }
        client = SatClient(b"cer", b"key", "pwd")
        client.request_download(
            "tok",
            "RFC1",
            "2026-01-01",
            "2026-01-31",
            direction="received",
            tipo_comprobante="I",
            rfc_a_cuenta_terceros="RFC3",
            complemento="nomina",
        )
        mock_method = mock_sat_cls.return_value.recover_comprobante_received_request
        call_kwargs = mock_method.call_args.kwargs
        self.assertEqual(call_kwargs["tipo_comprobante"], "I")
        self.assertEqual(call_kwargs["rfc_a_cuenta_terceros"], "RFC3")
        self.assertEqual(call_kwargs["complemento"], "nomina")

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_request_download_retention_with_complemento(
        self, mock_signer_load, mock_sat_cls
    ):
        mock_sat_cls.return_value.recover_retencion_received_request.return_value = {
            "CodEstatus": "5000",
            "IdSolicitud": "SOL-RC",
            "Mensaje": "Accepted",
        }
        client = SatClient(b"cer", b"key", "pwd")
        client.request_download(
            "tok",
            "RFC1",
            "2026-01-01",
            "2026-01-31",
            document_kind="retention",
            direction="received",
            complemento="dividendos",
        )
        mock_method = mock_sat_cls.return_value.recover_retencion_received_request
        call_kwargs = mock_method.call_args.kwargs
        self.assertEqual(call_kwargs["complemento"], "dividendos")
        self.assertEqual(call_kwargs["rfc_receptor"], "RFC1")

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_download_cfdi_package(self, mock_signer_load, mock_sat_cls):
        mock_sat_cls.return_value.recover_comprobante_download.return_value = (
            {"CodEstatus": "5000", "Mensaje": "OK"},
            "cfdi-b64",
        )
        client = SatClient(b"cer", b"key", "pwd")
        result = client.download_package("tok", "RFC1", "PKG-1")
        self.assertEqual(result["package_b64"], "cfdi-b64")
        self.assertEqual(result["cod_estatus"], "5000")

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_download_package_empty_payload(self, mock_signer_load, mock_sat_cls):
        mock_sat_cls.return_value.recover_comprobante_download.return_value = (
            {"CodEstatus": "5000", "Mensaje": "OK"},
            None,
        )
        client = SatClient(b"cer", b"key", "pwd")
        result = client.download_package("tok", "RFC1", "PKG-E")
        self.assertEqual(result["package_b64"], "")

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_normalize_status_response_defaults(self, mock_signer_load, mock_sat_cls):
        client = SatClient(b"cer", b"key", "pwd")
        result = client._normalize_status_response({})
        self.assertEqual(result["request_status"], 0)
        self.assertEqual(result["packages"], [])
        self.assertEqual(result["cod_estatus"], "")
        self.assertEqual(result["message"], "")

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_request_download_metadata_omits_estado(
        self, mock_signer_load, mock_sat_cls
    ):
        mock_sat_cls.return_value.recover_comprobante_received_request.return_value = {
            "CodEstatus": "5000",
            "IdSolicitud": "SOL-M",
            "Mensaje": "Accepted",
        }
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
        self.assertNotIn("estado_comprobante", call_kwargs)

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_request_download_filters_falsey_kwargs(
        self, mock_signer_load, mock_sat_cls
    ):
        mock_sat_cls.return_value.recover_comprobante_received_request.return_value = {
            "CodEstatus": "5000",
            "IdSolicitud": "SOL-F2",
            "Mensaje": "Accepted",
        }
        client = SatClient(b"cer", b"key", "pwd")
        client.request_download(
            "tok",
            "RFC1",
            "2026-01-01",
            "2026-01-31",
            tipo_comprobante=False,
            complemento=None,
        )
        mock_method = mock_sat_cls.return_value.recover_comprobante_received_request
        call_kwargs = mock_method.call_args.kwargs
        self.assertNotIn("tipo_comprobante", call_kwargs)
        self.assertNotIn("complemento", call_kwargs)
        self.assertEqual(call_kwargs["estado_comprobante"], EstadoComprobante.VIGENTE)

    def test_missing_satcfdi_import_placeholders(self):
        """Cover ImportError fallbacks without polluting the live sat_client module."""
        import importlib.util
        import sys
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / "services" / "sat_client.py"
        name = "l10n_mx_sat_sat_client_missing_satcfdi"
        blocked = {
            "satcfdi": None,
            "satcfdi.models": None,
            "satcfdi.pacs": None,
            "satcfdi.pacs.sat": None,
        }
        saved = {
            key: sys.modules.pop(key)
            for key in list(sys.modules)
            if key == "satcfdi" or key.startswith("satcfdi.")
        }
        try:
            with patch.dict(sys.modules, blocked):
                spec = importlib.util.spec_from_file_location(name, path)
                mod = importlib.util.module_from_spec(spec)
                sys.modules[name] = mod
                spec.loader.exec_module(mod)
                self.assertEqual(mod.EstadoComprobante.VIGENTE, "Vigente")
                self.assertEqual(
                    mod.TipoDescargaMasivaTerceros.METADATA.value, "Metadata"
                )
                self.assertEqual(mod.TipoDescargaMasivaTerceros.CFDI.value, "CFDI")
                with self.assertRaises(ImportError) as err:
                    mod.Signer.load(certificate=b"c", key=b"k", password="p")
                self.assertIn("satcfdi", str(err.exception))
                self.assertIs(mod.SAT, mod.Signer)
        finally:
            sys.modules.pop(name, None)
            sys.modules["satcfdi"] = None
            for key in list(sys.modules):
                if key == "satcfdi" or key.startswith("satcfdi."):
                    sys.modules.pop(key, None)
            sys.modules.update(saved)
