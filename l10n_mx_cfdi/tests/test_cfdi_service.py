from unittest.mock import MagicMock, patch

import facturama

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, mute_logger


class TestCFDIService(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cfdi_service = cls.env["l10n_mx_cfdi.cfdi_service"].create(
            {
                "name": "Test Service",
                "user": "test_user",
                "password": "test_password",
                "sandbox_mode": True,
            }
        )

    def _mock_client(self):
        return MagicMock()

    def test_get_client_sandbox(self):
        with patch(
            "odoo.addons.l10n_mx_cfdi.models.cfdi_service.facturama"
        ) as mock_facturama:
            self.cfdi_service._get_client()
            self.assertTrue(mock_facturama.sandbox)
            self.assertEqual(
                mock_facturama._credentials, ("test_user", "test_password")
            )

    def test_get_client_production(self):
        self.cfdi_service.sandbox_mode = False
        with patch(
            "odoo.addons.l10n_mx_cfdi.models.cfdi_service.facturama"
        ) as mock_facturama:
            self.cfdi_service._get_client()
            self.assertFalse(mock_facturama.sandbox)

    def test_register_csd_success(self):
        mock_client = self._mock_client()
        with patch.object(
            type(self.cfdi_service),
            "_get_client",
            return_value=mock_client,
        ):
            self.cfdi_service.register_csd("rfc123", b"cert", b"key", "password")
        mock_client.csdsMultiEmisor.build_http_request.assert_called_once()

    def test_register_csd_malformed_request(self):
        mock_client = self._mock_client()
        mock_client.csdsMultiEmisor.build_http_request.side_effect = (
            facturama.MalformedRequestError({"Message": "Invalid certificate"})
        )
        with patch.object(
            type(self.cfdi_service),
            "_get_client",
            return_value=mock_client,
        ):
            with self.assertRaises(UserError):
                self.cfdi_service.register_csd("rfc123", b"cert", b"key", "password")

    def test_register_csd_malformed_request_with_model_state(self):
        mock_client = self._mock_client()
        mock_client.csdsMultiEmisor.build_http_request.side_effect = (
            facturama.MalformedRequestError(
                {
                    "Message": "Invalid certificate",
                    "ModelState": {"Certificate": ["Invalid format"]},
                }
            )
        )
        with patch.object(
            type(self.cfdi_service),
            "_get_client",
            return_value=mock_client,
        ):
            with self.assertRaises(UserError) as error:
                self.cfdi_service.register_csd("rfc123", b"cert", b"key", "password")
        self.assertIn("Invalid format", str(error.exception))

    def test_unregister_csd(self):
        mock_client = self._mock_client()
        with patch.object(
            type(self.cfdi_service),
            "_get_client",
            return_value=mock_client,
        ):
            self.cfdi_service.unregister_csd("RFC123")
        mock_client.csdsMultiEmisor.delete.assert_called_once_with("RFC123")

    def test_get_csd_status(self):
        mock_client = self._mock_client()
        mock_client.csdsMultiEmisor.get_by_rfc.return_value = {"Status": "active"}
        with patch.object(
            type(self.cfdi_service),
            "_get_client",
            return_value=mock_client,
        ):
            status = self.cfdi_service.get_csd_status("RFC123")
        self.assertEqual(status, {"Status": "active"})

    def test_create_cfdi_success(self):
        mock_client = self._mock_client()
        mock_client.CfdiMultiEmisor.build_http_request.return_value = {"Id": "cfdi-1"}
        with patch.object(
            type(self.cfdi_service),
            "_get_client",
            return_value=mock_client,
        ):
            result = self.cfdi_service.create_cfdi({"NameId": "1"})
        self.assertEqual(result["Id"], "cfdi-1")

    def test_create_cfdi_malformed_request(self):
        mock_client = self._mock_client()
        mock_client.CfdiMultiEmisor.build_http_request.side_effect = (
            facturama.MalformedRequestError(
                {"Message": "Invalid", "ModelState": {"Items": ["Missing"]}}
            )
        )
        with patch.object(
            type(self.cfdi_service),
            "_get_client",
            return_value=mock_client,
        ):
            with self.assertRaises(UserError) as error:
                self.cfdi_service.create_cfdi({})
        self.assertIn("Invalid", str(error.exception))
        self.assertIn("Missing", str(error.exception))

    @mute_logger("odoo.addons.l10n_mx_cfdi.models.cfdi_service")
    def test_create_cfdi_api_error(self):
        mock_client = self._mock_client()
        mock_client.CfdiMultiEmisor.build_http_request.side_effect = facturama.ApiError(
            "Service unavailable"
        )
        with patch.object(
            type(self.cfdi_service),
            "_get_client",
            return_value=mock_client,
        ):
            with self.assertRaises(UserError):
                self.cfdi_service.create_cfdi({})

    def test_get_cfdi_pdf(self):
        mock_client = self._mock_client()
        mock_client.CfdiMultiEmisor.get_by_file.return_value = {"Content": b"pdf"}
        with patch.object(
            type(self.cfdi_service),
            "_get_client",
            return_value=mock_client,
        ):
            result = self.cfdi_service.get_cfdi_pdf("cfdi-id")
        self.assertEqual(result, {"Content": b"pdf"})

    def test_get_cfdi_xml(self):
        mock_client = self._mock_client()
        mock_client.CfdiMultiEmisor.get_by_file.return_value = {"Content": "<xml/>"}
        with patch.object(
            type(self.cfdi_service),
            "_get_client",
            return_value=mock_client,
        ):
            result = self.cfdi_service.get_cfdi_xml("cfdi-id")
        self.assertEqual(result, {"Content": "<xml/>"})

    def test_cancel_cfdi(self):
        mock_client = self._mock_client()
        mock_client.CfdiMultiEmisor.delete.return_value = {"Status": "canceled"}
        with patch.object(
            type(self.cfdi_service),
            "_get_client",
            return_value=mock_client,
        ):
            result = self.cfdi_service.cancel_cfdi("cfdi-id", "01", None)
        self.assertEqual(result["Status"], "canceled")

    def test_get_cancellation_request_proof(self):
        mock_client = self._mock_client()
        mock_client.CfdiMultiEmisor.build_http_request.return_value = {
            "Content": b"proof"
        }
        with patch.object(
            type(self.cfdi_service),
            "_get_client",
            return_value=mock_client,
        ):
            result = self.cfdi_service.get_cancellation_request_proof("cfdi-id")
        self.assertEqual(result, b"proof")

    def test_check_cfdi_status_published(self):
        self._assert_status_mapping("Vigente", "published")

    def test_check_cfdi_status_cancelled(self):
        self._assert_status_mapping("Cancelado", "cancelled")

    def test_check_cfdi_status_unknown(self):
        self._assert_status_mapping("No Encontrado", "unknown")

    def _assert_status_mapping(self, api_status, expected):
        mock_client = self._mock_client()
        mock_client.CfdiMultiEmisor.build_http_request.return_value = {
            "Status": api_status
        }
        with patch.object(
            type(self.cfdi_service),
            "_get_client",
            return_value=mock_client,
        ):
            status = self.cfdi_service.check_cfdi_status(
                "uuid", "issuer", "receiver", 100.0
            )
        self.assertEqual(status, expected)
