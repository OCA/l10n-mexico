import base64
from unittest.mock import patch

from odoo.exceptions import UserError

from odoo.addons.l10n_mx_cfdi.tests.common import ACTIVE_CFDI_RESPONSE

from .common import CFDIAccountTestCommon


class TestCFDIDocumentAccount(CFDIAccountTestCommon):
    def test_create_document_sets_serie_folio_from_invoice(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        document = self.env["l10n_mx_cfdi.document"].create(
            {
                "type": "I",
                "issuer_id": self.issuer.id,
                "receiver_id": self.customer.id,
                "related_invoice_id": invoice.id,
            }
        )
        self.assertTrue(document.serie)
        self.assertTrue(document.folio)

    def test_create_document_sets_serie_folio_from_payment(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        payment = self._register_invoice_payment(invoice)
        document = self.env["l10n_mx_cfdi.document"].create(
            {
                "type": "P",
                "issuer_id": self.issuer.id,
                "receiver_id": self.customer.id,
                "related_payment_id": payment.id,
            }
        )
        self.assertTrue(document.serie)
        self.assertTrue(document.folio)

    def test_set_serie_and_folio_missing_origin(self):
        with self.assertRaises(UserError):
            self.env[
                "l10n_mx_cfdi.document"
            ]._set_serie_and_folio_from_document_sequence({})

    def test_set_serie_and_folio_missing_numeric_postfix(self):
        invoice = self._create_cfdi_invoice()
        invoice.name = "NO-NUMBERS"
        with self.assertRaises(UserError):
            self.env[
                "l10n_mx_cfdi.document"
            ]._set_serie_and_folio_from_document_sequence(
                {"related_invoice_id": invoice.id}
            )

    def test_resolve_report_invoice(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        document = self.env["l10n_mx_cfdi.document"].create(
            {
                "type": "I",
                "issuer_id": self.issuer.id,
                "receiver_id": self.customer.id,
                "related_invoice_id": invoice.id,
                "serie": "INV",
                "folio": "1",
            }
        )
        report_type, report, resource_ids = document._resolve_report()
        self.assertEqual(report_type, "account.account_invoices")
        self.assertTrue(report)
        self.assertEqual(resource_ids, [invoice.id])

    def test_resolve_report_payment(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        payment = self._register_invoice_payment(invoice)
        document = self.env["l10n_mx_cfdi.document"].create(
            {
                "type": "P",
                "issuer_id": self.issuer.id,
                "receiver_id": self.customer.id,
                "related_payment_id": payment.id,
                "serie": "PAY",
                "folio": "1",
            }
        )
        report_type, report, resource_ids = document._resolve_report()
        self.assertEqual(report_type, "account.action_report_payment_receipt")
        self.assertEqual(resource_ids, [payment.id])

    def test_download_files_if_needed_wrapper(self):
        document = self._create_document(tracking_id="tracking-123")
        with patch.object(
            type(document),
            "_compute_download_files_if_needed",
            return_value=None,
        ) as mocked:
            document.download_files_if_needed()
        mocked.assert_called_once()

    def test_action_check_status_from_invoice(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        document = self._create_document(
            type="I",
            state="published",
            related_invoice_id=invoice.id,
            uuid="11111111-1111-1111-1111-111111111111",
        )
        with patch.object(
            type(self.service),
            "check_cfdi_status",
            return_value="canceled",
        ):
            document.action_check_status()
        self.assertEqual(document.state, "canceled")

    def test_action_check_status_from_payment(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        payment = self._register_invoice_payment(invoice)
        document = self._create_document(
            type="P",
            state="published",
            related_payment_id=payment.id,
            uuid="11111111-1111-1111-1111-111111111111",
        )
        with patch.object(
            type(self.service),
            "check_cfdi_status",
            return_value="published",
        ):
            document.action_check_status()
        self.assertEqual(document.state, "published")

    def test_download_files_with_invoice_report(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        document = self._create_document(
            type="I",
            tracking_id="tracking-report",
            related_invoice_id=invoice.id,
        )
        with (
            patch.object(
                type(self.env["ir.actions.report"]),
                "_render_qweb_pdf",
                return_value=(b"%PDF-1.4 report", "pdf"),
            ),
            patch.object(
                type(self.service),
                "get_cfdi_xml",
                return_value={"Content": base64.b64encode(b"<cfdi/>").decode("ascii")},
            ),
        ):
            document._compute_download_files_if_needed()
        self.assertTrue(document.files_in_cache)
        self.assertEqual(document.pdf_file, base64.b64encode(b"%PDF-1.4 report"))

    def test_publish_document_from_account_module(self):
        with patch.object(
            type(self.service),
            "create_cfdi",
            return_value=ACTIVE_CFDI_RESPONSE,
        ):
            document = self._create_document(serie="A", folio="99")
            document.publish({})
        self.assertEqual(document.state, "published")

    def test_download_files_fallback_to_provider_pdf(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        document = self._create_document(
            type="I",
            tracking_id="tracking-fallback",
            related_invoice_id=invoice.id,
        )
        with (
            patch.object(
                type(self.env["ir.actions.report"]),
                "_render_qweb_pdf",
                return_value=(b"", "pdf"),
            ),
            patch.object(
                type(self.service),
                "get_cfdi_pdf",
                return_value={"Content": base64.b64encode(b"%PDF-provider")},
            ),
            patch.object(
                type(self.service),
                "get_cfdi_xml",
                return_value={"Content": base64.b64encode(b"<cfdi/>").decode("ascii")},
            ),
        ):
            document._compute_download_files_if_needed()
        self.assertEqual(document.pdf_file, base64.b64encode(b"%PDF-provider"))

    def test_download_files_without_tracking(self):
        document = self._create_document(tracking_id=False)
        document._compute_download_files_if_needed()
        self.assertFalse(document.files_in_cache)
