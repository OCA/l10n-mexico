from base64 import b64encode
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestCFDIDocumentDownload(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["l10n_mx_cfdi.cfdi_service"].create(
            {
                "name": "Test service",
                "user": "Test user",
                "password": "12345",
            }
        )
        cls.issuer = cls.env["l10n_mx_cfdi.issuer"].create(
            {
                "name": "Test Issuer",
                "vat": "RFC123456",
                "certificate_file": b64encode(b"certificate"),
                "key_file": b64encode(b"key"),
                "key_password": "password",
                "service_id": cls.service.id,
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "vat": "TESTVAT",
                "zip": "12345",
            }
        )

    def _create_document(self, **extra):
        vals = {
            "issuer_id": self.issuer.id,
            "receiver_id": self.partner.id,
            "type": "I",
            "serie": "INV",
            "folio": "0001",
        }
        vals.update(extra)
        return self.env["l10n_mx_cfdi.document"].create(vals)

    def test_files_in_cache_without_tracking_id(self):
        document = self._create_document()
        self.assertFalse(document.files_in_cache)

    def test_download_pdf_skips_when_cached(self):
        pdf_data = b64encode(b"%PDF-1.4 cached")
        document = self._create_document(
            tracking_id="tracking-123",
            pdf_file=pdf_data,
        )
        with patch.object(
            type(self.service),
            "get_cfdi_pdf",
            autospec=True,
        ) as mock_get_pdf:
            document._download_pdf_file_if_needed()
            mock_get_pdf.assert_not_called()
        self.assertEqual(document.pdf_file, pdf_data)

    def test_download_pdf_from_report(self):
        document = self._create_document(tracking_id="tracking-123")
        report = MagicMock()
        report.with_context.return_value = report
        report._render_qweb_pdf.return_value = (b"%PDF-1.4 report", "pdf")

        with patch.object(
            type(document),
            "_resolve_report",
            return_value=(report, [1]),
        ):
            document._download_pdf_file_if_needed()

        self.assertEqual(document.pdf_file, b64encode(b"%PDF-1.4 report"))
        self.assertEqual(document.pdf_filename, f"{document.name}.pdf")

    def test_download_pdf_fallback_to_service(self):
        document = self._create_document(tracking_id="tracking-123")
        pdf_content = b64encode(b"%PDF-1.4 provider")

        with patch.object(
            type(document),
            "_resolve_report",
            return_value=(None, []),
        ), patch.object(
            type(self.service),
            "get_cfdi_pdf",
            return_value={"Content": pdf_content},
        ):
            document._download_pdf_file_if_needed()

        self.assertEqual(document.pdf_file, pdf_content)
        self.assertEqual(document.pdf_filename, f"{document.name}.pdf")

    def test_download_pdf_service_error_is_swallowed(self):
        document = self._create_document(tracking_id="tracking-123")

        with patch.object(
            type(document),
            "_resolve_report",
            return_value=(None, []),
        ), patch.object(
            type(self.service),
            "get_cfdi_pdf",
            side_effect=UserError("PDF unavailable"),
        ):
            document._download_pdf_file_if_needed()

        self.assertFalse(document.pdf_file)
        self.assertFalse(document.pdf_filename)

    def test_download_xml_from_service(self):
        document = self._create_document(tracking_id="tracking-123")
        xml_content = b64encode(b"<cfdi/>")

        with patch.object(
            type(self.service),
            "get_cfdi_xml",
            return_value={"Content": xml_content},
        ):
            document._download_xml_file_if_needed()

        self.assertEqual(document.xml_file, xml_content)
        self.assertEqual(document.xml_filename, f"{document.name}.xml")

    def test_download_xml_skips_when_cached(self):
        xml_data = b64encode(b"<cfdi cached/>")
        document = self._create_document(
            tracking_id="tracking-123",
            xml_file=xml_data,
        )
        with patch.object(
            type(self.service),
            "get_cfdi_xml",
            autospec=True,
        ) as mock_get_xml:
            document._download_xml_file_if_needed()
            mock_get_xml.assert_not_called()
        self.assertEqual(document.xml_file, xml_data)

    def test_download_files_if_needed_triggers_download(self):
        xml_content = b64encode(b"<cfdi/>")
        pdf_content = b64encode(b"%PDF-1.4 provider")

        with patch.object(
            type(self.service),
            "get_cfdi_pdf",
            return_value={"Content": pdf_content},
        ), patch.object(
            type(self.service),
            "get_cfdi_xml",
            return_value={"Content": xml_content},
        ), patch.object(
            type(self.env["l10n_mx_cfdi.document"]),
            "_resolve_report",
            return_value=(None, []),
        ):
            document = self._create_document(tracking_id="tracking-456")
            document.download_files_if_needed()

        self.assertTrue(document.files_in_cache)
        self.assertEqual(document.pdf_file, pdf_content)
        self.assertEqual(document.xml_file, xml_content)

    def test_load_tax_code_from_json_data(self):
        document_model = self.env["l10n_mx_cfdi.document"]
        tax_codes = document_model._load_tax_code_from_json_data(
            {
                "Taxes": [
                    {"Name": "ISR"},
                    {"Name": "IVA"},
                    {"Name": "IEPS"},
                ]
            }
        )
        self.assertEqual(set(tax_codes.split(",")), {"001", "002", "003"})

    def test_compute_name_with_serie(self):
        document = self._create_document(serie="A", folio="42")
        self.assertEqual(document.name, "A-42")

    def test_compute_name_without_serie(self):
        document = self._create_document(serie=False, folio="42")
        self.assertEqual(document.name, "42")
