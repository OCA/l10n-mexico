import base64
import zipfile
from io import BytesIO
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestDownloadCFDIFilesWizard(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cfdi_service = cls.env["l10n_mx_cfdi.cfdi_service"].create(
            {
                "name": "Test service",
                "user": "test_user",
                "password": "test_password",
            }
        )
        cls.issuer = cls.env["l10n_mx_cfdi.issuer"].create(
            {
                "name": "Test Issuer",
                "vat": "RFC123456",
                "service_id": cls.cfdi_service.id,
            }
        )

    def test_create_zip_file_downloads_missing_cfdi_files(self):
        invoice = self.init_invoice("out_invoice", products=self.product_a)
        pdf_bytes = b"%PDF-1.4"
        xml_bytes = b"<cfdi/>"
        pdf_content = base64.b64encode(pdf_bytes)
        xml_content = base64.b64encode(xml_bytes)
        document = self.env["l10n_mx_cfdi.document"].create(
            {
                "issuer_id": self.issuer.id,
                "receiver_id": invoice.partner_id.id,
                "type": "I",
                "serie": "INV",
                "folio": "0001",
                "related_invoice_id": invoice.id,
                "tracking_id": "tracking-zip",
                "state": "published",
            }
        )
        invoice.write({"related_cert_ids": [(4, document.id)]})

        with patch.object(
            type(self.cfdi_service),
            "get_cfdi_pdf",
            return_value={"Content": pdf_content},
        ), patch.object(
            type(self.cfdi_service),
            "get_cfdi_xml",
            return_value={"Content": xml_content},
        ), patch.object(
            type(document),
            "_resolve_report",
            return_value=(None, []),
        ):
            wizard = self.env["l10n_mx_cfdi_account.dl_cfdi_files_wizard"].create(
                {
                    "invoice_ids": [(6, 0, invoice.ids)],
                    "cfdi_document_ids": [(6, 0, document.ids)],
                }
            )
            wizard._create_zip_file()

        zip_data = base64.b64decode(wizard.zip_file.datas)
        with zipfile.ZipFile(BytesIO(zip_data)) as archive:
            self.assertEqual(
                sorted(archive.namelist()),
                sorted([document.pdf_filename, document.xml_filename]),
            )
            self.assertEqual(archive.read(document.pdf_filename), pdf_bytes)
            self.assertEqual(archive.read(document.xml_filename), xml_bytes)
