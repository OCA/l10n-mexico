from base64 import b64encode
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestCFDIDocumentAccount(AccountTestInvoicingCommon):
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
                "certificate_file": b64encode(b"certificate"),
                "key_file": b64encode(b"key"),
                "key_password": "password",
                "service_id": cls.cfdi_service.id,
            }
        )

    def _create_document(self, **extra):
        vals = {
            "issuer_id": self.issuer.id,
            "receiver_id": self.partner_a.id,
            "serie": "INV",
            "folio": "0001",
        }
        vals.update(extra)
        return self.env["l10n_mx_cfdi.document"].create(vals)

    def test_resolve_report_invoice(self):
        invoice = self.init_invoice("out_invoice", products=self.product_a)
        document = self._create_document(
            type="I",
            related_invoice_id=invoice.id,
        )
        report, resource_ids = document._resolve_report()
        self.assertEqual(report, self.env.ref("account.account_invoices"))
        self.assertEqual(resource_ids, [invoice.id])

    def test_resolve_report_credit_note(self):
        invoice = self.init_invoice("out_refund", products=self.product_a)
        document = self._create_document(
            type="E",
            related_invoice_id=invoice.id,
        )
        report, resource_ids = document._resolve_report()
        self.assertEqual(report, self.env.ref("account.account_invoices"))
        self.assertEqual(resource_ids, [invoice.id])

    def test_resolve_report_payment(self):
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner_a.id,
                "amount": 50.0,
                "journal_id": self.company_data["default_journal_bank"].id,
            }
        )
        document = self._create_document(
            type="P",
            related_payment_id=payment.id,
        )
        report, resource_ids = document._resolve_report()
        self.assertEqual(report, self.env.ref("account.action_report_payment_receipt"))
        self.assertEqual(resource_ids, [payment.id])

    def test_resolve_report_without_related_document(self):
        document = self._create_document(type="T")
        report, resource_ids = document._resolve_report()
        self.assertFalse(report)
        self.assertEqual(resource_ids, [])

    def test_download_pdf_uses_invoice_report(self):
        invoice = self.init_invoice("out_invoice", products=self.product_a)
        report = self.env.ref("account.account_invoices")
        xml_content = b64encode(b"<cfdi/>")

        with patch.object(
            type(report),
            "_render_qweb_pdf",
            return_value=(b"%PDF-1.4 invoice", "pdf"),
        ), patch.object(
            type(self.cfdi_service),
            "get_cfdi_xml",
            return_value={"Content": xml_content},
        ):
            document = self._create_document(
                type="I",
                related_invoice_id=invoice.id,
                tracking_id="tracking-invoice",
            )
            document._download_pdf_file_if_needed()

        self.assertEqual(document.pdf_file, b64encode(b"%PDF-1.4 invoice"))

    def test_download_xml_still_runs_when_pdf_download_fails(self):
        invoice = self.init_invoice("out_invoice", products=self.product_a)
        xml_content = b64encode(b"<cfdi/>")

        with patch.object(
            type(self.env["l10n_mx_cfdi.document"]),
            "_resolve_report",
            return_value=(None, []),
        ), patch.object(
            type(self.cfdi_service),
            "get_cfdi_pdf",
            side_effect=UserError("PDF unavailable"),
        ), patch.object(
            type(self.cfdi_service),
            "get_cfdi_xml",
            return_value={"Content": xml_content},
        ):
            document = self._create_document(
                type="I",
                related_invoice_id=invoice.id,
                tracking_id="tracking-xml-only",
            )
            document.download_files_if_needed()

        self.assertFalse(document.pdf_file)
        self.assertEqual(document.xml_file, xml_content)
        self.assertTrue(document.files_in_cache)
