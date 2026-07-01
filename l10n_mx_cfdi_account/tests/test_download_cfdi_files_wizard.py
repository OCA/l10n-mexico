import base64
from unittest.mock import patch

from .common import CFDIAccountTestCommon


class TestDownloadCFDIFilesWizard(CFDIAccountTestCommon):
    def test_default_get_from_invoices(self):
        invoice = self._create_cfdi_invoice()
        document = self._create_published_invoice_cfdi(invoice)
        wizard_model = self.env["l10n_mx_cfdi_account.dl_cfdi_files_wizard"]
        defaults = wizard_model.with_context(
            active_model="account.move",
            active_ids=invoice.ids,
        ).default_get(["invoice_ids", "cfdi_document_ids"])
        self.assertEqual(defaults["invoice_ids"], invoice)
        self.assertEqual(defaults["cfdi_document_ids"], document)

    def test_action_download_zip(self):
        invoice = self._create_cfdi_invoice()
        document = self._create_published_invoice_cfdi(invoice)
        document.write(
            {
                "pdf_file": base64.b64encode(b"%PDF-1.4"),
                "pdf_filename": "invoice.pdf",
                "xml_file": base64.b64encode(b"<cfdi/>"),
                "xml_filename": "invoice.xml",
            }
        )
        wizard = self.env["l10n_mx_cfdi_account.dl_cfdi_files_wizard"].create(
            {
                "invoice_ids": [(6, 0, invoice.ids)],
                "cfdi_document_ids": [(6, 0, document.ids)],
            }
        )
        with patch.object(
            type(document),
            "download_files_if_needed",
            return_value=None,
        ):
            action = wizard.action_download_zip()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertTrue(wizard.zip_file)
