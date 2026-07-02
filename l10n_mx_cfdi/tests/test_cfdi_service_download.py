from unittest.mock import MagicMock, patch

import facturama

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestCFDIServiceDownload(TransactionCase):
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

    def _mock_facturama_error(self, error_json):
        return facturama.FacturamaError(error_json)

    def test_format_facturama_error_message(self):
        error = self._mock_facturama_error({"Message": "File not found"})
        self.assertEqual(
            self.cfdi_service._format_facturama_error(error),
            "File not found",
        )

    def test_format_facturama_error_response(self):
        error = self._mock_facturama_error({"response": "Service unavailable"})
        self.assertEqual(
            self.cfdi_service._format_facturama_error(error),
            "Service unavailable",
        )

    def test_format_facturama_error_fallback(self):
        error = MagicMock()
        error.error_json = "raw error"
        self.assertEqual(
            self.cfdi_service._format_facturama_error(error),
            "raw error",
        )

    def test_get_cfdi_file_success(self):
        mock_client = MagicMock()
        mock_client.CfdiMultiEmisor.get_by_file.return_value = {
            "Content": b"file-content"
        }

        with patch.object(
            type(self.cfdi_service),
            "_get_client",
            return_value=mock_client,
        ):
            result = self.cfdi_service._get_cfdi_file("pdf", "cfdi-id")

        mock_client.CfdiMultiEmisor.get_by_file.assert_called_once_with(
            "pdf", "IssuedLite", "cfdi-id"
        )
        self.assertEqual(result, {"Content": b"file-content"})

    def test_get_cfdi_file_facturama_error(self):
        mock_client = MagicMock()
        mock_client.CfdiMultiEmisor.get_by_file.side_effect = (
            self._mock_facturama_error({"Message": "Not found"})
        )

        with patch.object(
            type(self.cfdi_service),
            "_get_client",
            return_value=mock_client,
        ):
            with self.assertRaises(UserError) as error:
                self.cfdi_service.get_cfdi_pdf("cfdi-id")

        self.assertIn("Error downloading the CFDI PDF", str(error.exception))
        self.assertIn("Not found", str(error.exception))

    def test_get_cfdi_file_unexpected_error(self):
        mock_client = MagicMock()
        mock_client.CfdiMultiEmisor.get_by_file.side_effect = RuntimeError(
            "network down"
        )

        with patch.object(
            type(self.cfdi_service),
            "_get_client",
            return_value=mock_client,
        ):
            with self.assertRaises(UserError) as error:
                self.cfdi_service.get_cfdi_xml("cfdi-id")

        self.assertIn(
            "An error occurred while downloading the CFDI XML",
            str(error.exception),
        )
