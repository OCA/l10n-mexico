import base64
import json
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from .common import ACTIVE_CFDI_RESPONSE, CFDITestMixin


class TestCFDIDocument(CFDITestMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls._create_cfdi_service()
        cls.issuer = cls._create_cfdi_issuer(cls.service)
        cls.partner = cls._create_cfdi_partner()

    def test_create_document(self):
        document = self._create_document()
        self.assertEqual(document.state, "draft")

    def test_compute_name_with_serie(self):
        document = self._create_document(serie="INV", folio="42")
        self.assertEqual(document.name, "INV-42")

    def test_compute_name_without_serie(self):
        document = self._create_document(serie=False, folio="42")
        self.assertEqual(document.name, "42")

    def test_compute_standalone(self):
        transfer = self._create_document(type="T")
        invoice = self._create_document(type="I", serie="B", folio="2")
        self.assertTrue(transfer.standalone)
        self.assertFalse(invoice.standalone)

    def test_load_tax_code_from_json_data(self):
        document_model = self.env["l10n_mx_cfdi.document"]
        tax_codes = document_model._load_tax_code_from_json_data(
            {"Taxes": [{"Name": "ISR"}, {"Name": "IVA"}, {"Name": "IEPS"}]}
        )
        self.assertEqual(set(tax_codes.split(",")), {"001", "002", "003"})

    def test_generate_verification_url_and_qr_code(self):
        document = self._create_document(
            uuid="11111111-1111-1111-1111-111111111111",
        )
        url = document._generate_verification_url(
            document.uuid,
            self.issuer.vat,
            self.partner.vat,
            "100.00",
            "12345678",
        )
        self.assertIn(document.uuid, url)
        qr_code = document._generate_qr_code(url.encode("utf-8"))
        self.assertTrue(qr_code)

    def test_compute_load_json_data(self):
        document = self._create_document(
            uuid="11111111-1111-1111-1111-111111111111",
            cert_data_json=json.dumps(ACTIVE_CFDI_RESPONSE),
        )
        self.assertEqual(document.cert_number, "CERT123")
        self.assertTrue(document.verification_url)
        self.assertTrue(document.verification_qr_code)
        self.assertIn("002", document.tax_codes)

    def test_files_in_cache_without_tracking_id(self):
        document = self._create_document()
        self.assertFalse(document.files_in_cache)

    def test_download_files_if_needed(self):
        pdf_content = base64.b64encode(b"%PDF-1.4")
        xml_content = "<cfdi/>"

        with (
            patch.object(
                type(self.service),
                "get_cfdi_pdf",
                return_value={"Content": pdf_content},
            ),
            patch.object(
                type(self.service),
                "get_cfdi_xml",
                return_value={"Content": xml_content},
            ),
        ):
            document = self._create_document(tracking_id="tracking-123")
            self.assertTrue(document.files_in_cache)
            self.assertEqual(document.pdf_file, pdf_content)
            self.assertEqual(document.xml_file, base64.b64encode(b"<cfdi/>"))

    def test_publish_document(self):
        with patch.object(
            type(self.service),
            "create_cfdi",
            return_value=ACTIVE_CFDI_RESPONSE,
        ):
            document = self._create_document()
            document.publish({})

        self.assertEqual(document.state, "published")
        self.assertEqual(document.tracking_id, "tracking-123")
        self.assertTrue(document.cert_data_json)

    def test_publish_document_not_draft(self):
        document = self._create_document(state="published")
        with self.assertRaises(UserError):
            document.publish({})

    def test_publish_document_duplicate_serie_folio(self):
        with patch.object(
            type(self.service),
            "create_cfdi",
            return_value=ACTIVE_CFDI_RESPONSE,
        ):
            first = self._create_document()
            first.publish({})
            second = self._create_document()
            with self.assertRaises(UserError):
                second.publish({})

    def test_publish_document_error_status(self):
        with patch.object(
            type(self.service),
            "create_cfdi",
            return_value={"Status": "error", "Message": "Invalid CFDI"},
        ):
            document = self._create_document()
            with self.assertRaises(UserError):
                document.publish({})

    def test_cancel_document_simulate(self):
        document = self._create_document(state="published")
        document.cancel(reason="01", simulate=True)
        self.assertEqual(document.state, "canceled")

    def test_cancel_document_not_published(self):
        document = self._create_document(state="draft")
        document.cancel(reason="01")
        self.assertEqual(document.state, "draft")

    def test_cancel_document_success(self):
        document = self._create_document(
            state="published",
            tracking_id="tracking-123",
            pdf_file=base64.b64encode(b"pdf"),
            xml_file=base64.b64encode(b"xml"),
        )
        with patch.object(
            type(self.service),
            "cancel_cfdi",
            return_value={"Status": "canceled"},
        ):
            document.cancel(reason="01")
        self.assertEqual(document.state, "canceled")
        self.assertFalse(document.pdf_file)

    def test_cancel_document_pending(self):
        document = self._create_document(state="published", tracking_id="tracking-123")
        with patch.object(
            type(self.service),
            "cancel_cfdi",
            return_value={"Status": "pending"},
        ):
            document.cancel(reason="01")
        self.assertEqual(document.state, "pending_cancel")

    def test_cancel_document_rejected(self):
        document = self._create_document(state="published", tracking_id="tracking-123")
        with patch.object(
            type(self.service),
            "cancel_cfdi",
            return_value={"Status": "rejected"},
        ):
            document.cancel(reason="01")
        self.assertEqual(document.state, "published")

    def test_cancel_document_accepted(self):
        document = self._create_document(state="published", tracking_id="tracking-123")
        with patch.object(
            type(self.service),
            "cancel_cfdi",
            return_value={"Status": "acepted"},
        ):
            document.cancel(reason="01")
        self.assertEqual(document.state, "canceled")

    def test_cancel_document_expired(self):
        document = self._create_document(state="published", tracking_id="tracking-123")
        with patch.object(
            type(self.service),
            "cancel_cfdi",
            return_value={"Status": "expired"},
        ):
            document.cancel(reason="01")
        self.assertEqual(document.state, "canceled")

    def test_download_files_with_report(self):
        document = self._create_document(tracking_id="tracking-report")
        report = MagicMock()
        report.with_context.return_value = report
        report._render_qweb_pdf.return_value = (b"%PDF-1.4 report", "pdf")
        xml_content = "<cfdi/>"

        with (
            patch.object(
                type(document),
                "_resolve_report",
                return_value=(report, [1]),
            ),
            patch.object(
                type(self.service),
                "get_cfdi_xml",
                return_value={"Content": xml_content},
            ),
        ):
            self.assertTrue(document.files_in_cache)
        self.assertEqual(document.pdf_file, base64.b64encode(b"%PDF-1.4 report"))

    def test_publish_passes_logo_url(self):
        captured = {}

        def _create_cfdi(cfdi_data):
            captured.update(cfdi_data)
            return ACTIVE_CFDI_RESPONSE

        with patch.object(type(self.service), "create_cfdi", side_effect=_create_cfdi):
            document = self._create_document()
            document.publish({})
        self.assertEqual(captured["LogoUrl"], self.issuer.logo_url)

    def test_cancel_document_error(self):
        document = self._create_document(state="published", tracking_id="tracking-123")
        with patch.object(
            type(self.service),
            "cancel_cfdi",
            return_value={"Status": "unknown", "Message": "Rejected by SAT"},
        ):
            with self.assertRaises(UserError):
                document.cancel(reason="01")

    def test_action_cancel(self):
        document = self._create_document()
        action = document.action_cancel()
        self.assertEqual(action["res_model"], "l10n_mx_cfdi.document_cancel")

    def test_action_check_status(self):
        document = self._create_document(
            state="published",
            uuid="11111111-1111-1111-1111-111111111111",
        )
        with patch.object(
            type(self.service),
            "check_cfdi_status",
            return_value="unknown",
        ):
            document.action_check_status()
        self.assertEqual(document.state, "unknown")

    def test_action_get_cancellation_request_proof(self):
        document = self._create_document(
            state="canceled",
            tracking_id="tracking-123",
            serie="A",
            folio="9",
        )
        with patch.object(
            type(self.service),
            "get_cancellation_request_proof",
            return_value=b"proof-pdf",
        ):
            document.action_get_cancellation_request_proof()
        self.assertTrue(document.cancellation_request_proof_file)
        self.assertTrue(document.cancellation_request_proof_filename)

    def test_action_get_cancellation_request_proof_not_canceled(self):
        document = self._create_document(state="published")
        with self.assertRaises(UserError):
            document.action_get_cancellation_request_proof()


class TestCFDIDocumentRelation(CFDITestMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls._create_cfdi_service()
        cls.issuer = cls._create_cfdi_issuer(cls.service)
        cls.partner = cls._create_cfdi_partner()
        cls.relation_type = cls.env.ref("l10n_mx_catalogs.c_tipo_relacion_4")

    def test_document_relation_creation(self):
        source = self._create_document(serie="S", folio="1")
        target = self._create_document(serie="T", folio="2")
        relation = self.env["l10n_mx_cfdi.document_relation"].create(
            {
                "relation_type_id": self.relation_type.id,
                "source_id": source.id,
                "target_id": target.id,
            }
        )
        self.assertEqual(relation.source_id, source)
        self.assertEqual(relation.target_id, target)
