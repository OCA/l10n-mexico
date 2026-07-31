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
            cert_data_json=json.dumps(ACTIVE_CFDI_RESPONSE["stamp_meta"]),
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
            return_value={
                "Status": "canceled",
                "Message": "Cancelado sin Aceptacion",
                "Acuse": b"<acuse/>",
            },
        ):
            feedback = document.cancel(reason="01")
        self.assertEqual(document.state, "canceled")
        self.assertFalse(document.pdf_file)
        self.assertTrue(document.cancellation_request_proof_file)
        self.assertEqual(feedback["Status"], "canceled")
        self.assertTrue(feedback["HasAcuse"])
        summary = document._format_cancel_feedback(feedback)
        self.assertIn("canceled", summary)
        self.assertIn("Cancelado sin Aceptacion", summary)
        self.assertIn("acuse", summary.lower())

    def test_cancel_document_without_acuse_feedback(self):
        document = self._create_document(
            state="published",
            tracking_id="tracking-123",
            xml_file=base64.b64encode(b"xml"),
        )
        with patch.object(
            type(self.service),
            "cancel_cfdi",
            return_value={"Status": "canceled", "Message": "", "Acuse": None},
        ):
            feedback = document.cancel(reason="02")
        self.assertEqual(document.state, "canceled")
        self.assertFalse(feedback["HasAcuse"])
        summary = document._format_cancel_feedback(feedback)
        self.assertIn("did not return", summary)

    def test_cancel_document_active_raises(self):
        document = self._create_document(
            state="published",
            tracking_id="tracking-123",
            xml_file=base64.b64encode(b"xml"),
        )
        with (
            patch.object(
                type(self.service),
                "cancel_cfdi",
                return_value={
                    "Status": "active",
                    "Message": "Tiene documentos relacionados",
                },
            ),
            self.assertRaises(UserError),
        ):
            document.cancel(reason="02")
        self.assertEqual(document.state, "published")

    def test_cancel_document_pending(self):
        document = self._create_document(
            state="published",
            tracking_id="tracking-123",
            xml_file=base64.b64encode(b"xml"),
        )
        with patch.object(
            type(self.service),
            "cancel_cfdi",
            return_value={"Status": "pending"},
        ):
            document.cancel(reason="01")
        self.assertEqual(document.state, "pending_cancel")

    def test_cancel_document_rejected(self):
        document = self._create_document(
            state="published",
            tracking_id="tracking-123",
            xml_file=base64.b64encode(b"xml"),
        )
        with patch.object(
            type(self.service),
            "cancel_cfdi",
            return_value={"Status": "rejected"},
        ):
            document.cancel(reason="01")
        self.assertEqual(document.state, "published")

    def test_cancel_document_accepted(self):
        document = self._create_document(
            state="published",
            tracking_id="tracking-123",
            xml_file=base64.b64encode(b"xml"),
        )
        with patch.object(
            type(self.service),
            "cancel_cfdi",
            return_value={"Status": "acepted"},
        ):
            document.cancel(reason="01")
        self.assertEqual(document.state, "canceled")

    def test_cancel_document_expired(self):
        document = self._create_document(
            state="published",
            tracking_id="tracking-123",
            xml_file=base64.b64encode(b"xml"),
        )
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

    def test_publish_stores_stamp_meta(self):
        with patch.object(
            type(self.service),
            "create_cfdi",
            return_value=ACTIVE_CFDI_RESPONSE,
        ):
            document = self._create_document()
            document.publish({})
        self.assertEqual(document.state, "published")
        self.assertEqual(document.uuid, ACTIVE_CFDI_RESPONSE["uuid"])
        meta = json.loads(document.cert_data_json)
        self.assertEqual(meta["CertNumber"], "CERT123")

    def test_publish_tolerates_non_json_stamp_meta_values(self):
        """Regression: satcfdi methods in stamp_meta used to abort after PAC stamp."""
        response = dict(ACTIVE_CFDI_RESPONSE)
        response["stamp_meta"] = dict(ACTIVE_CFDI_RESPONSE["stamp_meta"])
        response["stamp_meta"]["OriginalString"] = str.upper
        with patch.object(
            type(self.service),
            "create_cfdi",
            return_value=response,
        ):
            document = self._create_document()
            document.publish({})
        self.assertEqual(document.state, "published")
        self.assertTrue(document.cert_data_json)
        json.loads(document.cert_data_json)

    def test_cancel_document_error(self):
        document = self._create_document(
            state="published",
            tracking_id="tracking-123",
            xml_file=base64.b64encode(b"xml"),
        )
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
            cancellation_request_proof_file=base64.b64encode(b"proof-pdf"),
            cancellation_request_proof_filename="Acuse.xml",
        )
        document.action_get_cancellation_request_proof()
        self.assertTrue(document.cancellation_request_proof_file)

    def test_action_get_cancellation_request_proof_missing(self):
        document = self._create_document(state="canceled")
        with self.assertRaises(UserError):
            document.action_get_cancellation_request_proof()

    def test_action_get_cancellation_request_proof_not_canceled(self):
        document = self._create_document(state="published")
        with self.assertRaises(UserError):
            document.action_get_cancellation_request_proof()

    def test_legacy_without_xml_blocks_cancel(self):
        document = self._create_document(
            state="published",
            tracking_id="facturama-old-id",
            xml_file=False,
        )
        self.assertTrue(document.legacy_without_xml)
        with self.assertRaises(UserError) as err:
            document.cancel(reason="02")
        self.assertIn("no stored stamped XML", str(err.exception))

    def test_cancel_blocked_when_pac_unsupported(self):
        self.service.provider = "prodigia"
        self.service.pac_contrato = "1234"
        document = self._create_document(
            state="published",
            tracking_id="tracking-123",
            xml_file=base64.b64encode(b"<xml/>"),
        )
        self.assertFalse(document.pac_supports_cancel)
        with self.assertRaises(UserError) as err:
            document.cancel(reason="02")
        self.assertIn("does not support CFDI cancellation", str(err.exception))

    def test_publish_stores_pac_provider(self):
        with patch.object(
            type(self.service),
            "create_cfdi",
            return_value=ACTIVE_CFDI_RESPONSE,
        ):
            document = self._create_document()
            document.publish({})
        self.assertEqual(document.pac_provider, self.service.provider)

    def test_publish_stores_pdf_and_injects_serie_folio(self):
        response = dict(ACTIVE_CFDI_RESPONSE)
        response["pdf"] = b"%PDF-fake"
        cfdi = {}
        with patch.object(
            type(self.service),
            "create_cfdi",
            return_value=response,
        ):
            document = self._create_document(serie="XYZ", folio="9")
            document.publish(cfdi)
        self.assertTrue(document.pdf_file)
        self.assertEqual(cfdi.get("Serie"), "XYZ")
        self.assertEqual(cfdi.get("Folio"), "9")

    def test_cancel_stores_acuse_on_document(self):
        document = self._create_document(
            state="published",
            uuid="11111111-1111-1111-1111-111111111111",
            xml_file=base64.b64encode(
                b'<?xml version="1.0"?><cfdi:Comprobante '
                b'xmlns:cfdi="http://www.sat.gob.mx/cfd/4">'
                b"<cfdi:Complemento><tfd:TimbreFiscalDigital "
                b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
                b'UUID="11111111-1111-1111-1111-111111111111"/>'
                b"</cfdi:Complemento></cfdi:Comprobante>"
            ),
        )
        with patch.object(
            type(self.service),
            "cancel_cfdi",
            return_value={
                "Status": "canceled",
                "Message": "",
                "Acuse": b"<acuse/>",
            },
        ):
            document.cancel("02")
        self.assertTrue(document.cancellation_request_proof_file)

    def test_cancel_without_xml_non_legacy(self):
        document = self._create_document(
            state="published",
            uuid="11111111-1111-1111-1111-111111111111",
            tracking_id=False,
            xml_file=False,
        )
        self.assertFalse(document.legacy_without_xml)
        with self.assertRaises(UserError):
            document.cancel("02")

    def test_publish_accepts_xml_as_str(self):
        response = dict(ACTIVE_CFDI_RESPONSE)
        response["xml"] = (
            '<?xml version="1.0"?><cfdi:Comprobante '
            'xmlns:cfdi="http://www.sat.gob.mx/cfd/4"/>'
        )
        response["pdf"] = False
        cfdi = {"Serie": "A", "Folio": "1"}
        with patch.object(
            type(self.service),
            "create_cfdi",
            return_value=response,
        ):
            document = self._create_document(serie="A", folio="1")
            document.publish(cfdi)
        self.assertTrue(document.xml_file)

    def test_action_check_status_unchanged(self):
        document = self._create_document(
            state="published",
            uuid="11111111-1111-1111-1111-111111111111",
        )
        with patch.object(
            type(self.service),
            "check_cfdi_status",
            return_value="published",
        ):
            document.action_check_status()
        self.assertEqual(document.state, "published")

    def test_download_files_falls_back_to_pac_when_report_empty(self):
        document = self._create_document(tracking_id="tracking-empty-report")
        report = MagicMock()
        report.with_context.return_value = report
        report._render_qweb_pdf.return_value = (b"", "pdf")
        pac_pdf = base64.b64encode(b"%PDF-pac")
        with (
            patch.object(
                type(document),
                "_resolve_report",
                return_value=(report, [1]),
            ),
            patch.object(
                type(self.service),
                "get_cfdi_pdf",
                return_value={"Content": pac_pdf},
            ),
            patch.object(
                type(self.service),
                "get_cfdi_xml",
                return_value={"Content": b"<xml/>"},
            ),
        ):
            self.assertTrue(document.files_in_cache)
        self.assertEqual(document.pdf_file, pac_pdf)

    def test_download_files_soft_fail_on_user_error(self):
        document = self._create_document(tracking_id="tracking-soft-fail")
        with (
            patch.object(
                type(self.service),
                "get_cfdi_pdf",
                side_effect=UserError("no pdf"),
            ),
            patch.object(
                type(self.service),
                "get_cfdi_xml",
                side_effect=UserError("no xml"),
            ),
        ):
            # tracking_id present still marks cache as attempted
            self.assertTrue(document.files_in_cache)
        self.assertFalse(document.pdf_file)
        self.assertFalse(document.xml_file)

    def test_publish_allows_second_document_when_folio_blank(self):
        """Empty serie/folio must not block E/P after the first ingreso."""
        first = self._create_document(serie="TMP", folio="1", type="I")
        second = self._create_document(serie="TMP", folio="2", type="E")
        # Simulate legacy/blank Multiemisor docs (no local serie/folio).
        first.write({"serie": False, "folio": False, "state": "published"})
        second.write({"serie": False, "folio": False})
        with patch.object(
            type(self.service), "create_cfdi", return_value=ACTIVE_CFDI_RESPONSE
        ):
            second.publish({})
        self.assertEqual(second.state, "published")

    def test_create_assigns_serie_folio_from_series(self):
        self.env["l10n_mx_cfdi.series"].create(
            {
                "name": "Payment series",
                "code": "PAG",
                "prefix": "P",
                "padding": 3,
                "implementation": "no_gap",
            }
        )
        document = self.env["l10n_mx_cfdi.document"].create(
            {
                "issuer_id": self.issuer.id,
                "receiver_id": self.partner.id,
                "type": "P",
            }
        )
        self.assertTrue(document.folio)
        self.assertEqual(document.serie, "P")

    def test_prepare_serie_folio_fallback_and_missing(self):
        Series = self.env["l10n_mx_cfdi.series"]
        Series.search([]).unlink()
        Document = self.env["l10n_mx_cfdi.document"]
        # No series at all: leave vals unchanged.
        vals = {"type": "I"}
        self.assertEqual(Document._prepare_serie_folio_vals(dict(vals)), vals)
        # Unmatched code falls back to any available series.
        Series.create(
            {
                "name": "Fallback series",
                "code": "ZZZ",
                "prefix": "Z",
                "padding": 3,
                "implementation": "no_gap",
            }
        )
        out = Document._prepare_serie_folio_vals({"type": "I"})
        self.assertEqual(out["serie"], "Z")
        self.assertTrue(out["folio"])


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
