from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from satcfdi.exceptions import ResponseError
from satcfdi.pacs import Accept, CancelReason, Environment

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, mute_logger

from odoo.addons.l10n_mx_cfdi.services import cefidia, pac_registry

UUID = "11111111-1111-1111-1111-111111111111"
DOC_ID = "aaaaaaaa-0000-0000-0000-000000000001"
XML_LINK = "https://cefidia.com/files/doc.xml?sig=1"
PDF_LINK = "https://storage.example.com/doc.pdf?sig=1"


def _response(status=200, payload=None, content=b""):
    response = MagicMock()
    response.status_code = status
    response.ok = 200 <= status < 300
    response.json.return_value = payload
    response.content = content if payload is None else b"{}"
    response.text = ""
    return response


def _stamped_doc(**extra):
    doc = {
        "id": DOC_ID,
        "state": "stamped",
        "uuid": UUID,
        "sat_state": None,
        "rejection": None,
        "links": {"xml": XML_LINK, "pdf": PDF_LINK},
    }
    doc.update(extra)
    return doc


def _cfdi():
    return {
        "Emisor": {"Rfc": "EKU9003173C9"},
        "Complemento": {"TimbreFiscalDigital": {"UUID": UUID}},
    }


class TestCefidiaClient(TransactionCase):
    def setUp(self):
        super().setUp()
        self.client = cefidia.Cefidia(token="cfd_test")
        self.client.session = MagicMock()

    def test_requires_token(self):
        with self.assertRaises(ValueError):
            cefidia.Cefidia(token="")

    def test_stamp_posts_signed_xml_and_downloads_files(self):
        self.client.session.request.return_value = _response(payload=_stamped_doc())
        self.client.session.get.side_effect = [
            _response(content=b"<xml/>"),
            _response(content=b"%PDF"),
        ]
        document = self.client.stamp("<cfdi:Comprobante/>", accept=Accept.XML_PDF)

        method, url = self.client.session.request.call_args.args
        kwargs = self.client.session.request.call_args.kwargs
        self.assertEqual(method, "post")
        self.assertEqual(url, "https://cefidia.com/v1/signed-documents")
        self.assertEqual(kwargs["json"], {"xml": "<cfdi:Comprobante/>"})
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer cfd_test")
        self.assertEqual(document.document_id, DOC_ID)
        self.assertEqual(document.xml, b"<xml/>")
        self.assertEqual(document.pdf, b"%PDF")
        # Token only goes to the API host, never to third-party storage.
        xml_call, pdf_call = self.client.session.get.call_args_list
        self.assertIn("Authorization", xml_call.kwargs["headers"])
        self.assertEqual(pdf_call.kwargs["headers"], {})

    def test_stamp_uses_cfdi_xml_bytes(self):
        cfdi_obj = MagicMock()
        cfdi_obj.xml_bytes.return_value = b"<signed/>"
        self.client.session.request.return_value = _response(payload=_stamped_doc())
        self.client.session.get.return_value = _response(content=b"<xml/>")
        self.client.stamp(cfdi_obj, accept=Accept.XML)
        self.assertEqual(
            self.client.session.request.call_args.kwargs["json"], {"xml": "<signed/>"}
        )

    def test_stamp_rejection_raises_with_sat_code(self):
        self.client.session.request.return_value = _response(
            payload={
                "rejection": {
                    "code": "CFDI40108",
                    "message": "El TipoDeComprobante no es válido",
                    "path": "Comprobante/@TipoDeComprobante",
                }
            }
        )
        with self.assertRaises(cefidia.CefidiaRejection) as ctx:
            self.client.stamp("<x/>")
        problem = ctx.exception.response
        self.assertEqual(problem["code"], "CFDI40108")
        self.assertIn("CFDI40108", problem["detail"])
        self.assertEqual(problem["fields"][0]["path"], "Comprobante/@TipoDeComprobante")

    @patch.object(cefidia.time, "sleep")
    def test_stamp_polls_while_stamping(self, mock_sleep):
        self.client.session.request.side_effect = [
            _response(payload=_stamped_doc(state="stamping", uuid=None, links=None)),
            _response(payload=_stamped_doc()),
        ]
        self.client.session.get.return_value = _response(content=b"<xml/>")
        document = self.client.stamp("<x/>", accept=Accept.XML)
        self.assertEqual(document.xml, b"<xml/>")
        self.assertEqual(mock_sleep.call_count, 1)
        method, url = self.client.session.request.call_args.args
        self.assertEqual(
            (method, url), ("get", f"https://cefidia.com/v1/documents/{DOC_ID}")
        )

    @patch.object(cefidia.time, "sleep")
    def test_stamp_still_stamping_raises(self, _mock_sleep):
        pending = _stamped_doc(state="stamping", uuid=None, links=None)
        self.client.session.request.return_value = _response(payload=pending)
        with self.assertRaises(ResponseError) as ctx:
            self.client.stamp("<x/>")
        self.assertEqual(ctx.exception.response["code"], "stamping")

    def test_http_error_raises_response_error(self):
        self.client.session.request.return_value = _response(
            status=404, payload={"code": "taxpayer_not_found", "detail": "x"}
        )
        with self.assertRaises(ResponseError):
            self.client.stamp("<x/>")

    def test_issue_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.client.issue("<x/>")

    def test_recover_pdf(self):
        self.client.session.request.return_value = _response(payload=_stamped_doc())
        self.client.session.get.return_value = _response(content=b"%PDF")
        document = self.client.recover(UUID, accept=Accept.PDF)
        self.assertEqual(document.pdf, b"%PDF")
        self.assertIsNone(document.xml)

    def test_recover_without_links_raises(self):
        self.client.session.request.return_value = _response(
            payload=_stamped_doc(state="prepared", links=None)
        )
        with self.assertRaises(ResponseError):
            self.client.recover(DOC_ID, accept=Accept.XML)

    def test_cancel_with_replacement(self):
        self.client.session.request.return_value = _response(
            payload={"state": "canceled", "document": _stamped_doc(state="canceled")}
        )
        ack = self.client.cancel(
            _cfdi(),
            CancelReason.COMPROBANTE_EMITIDO_CON_ERRORES_CON_RELACION,
            substitution_id="22222222-2222-2222-2222-222222222222",
        )
        _method, url = self.client.session.request.call_args.args
        self.assertEqual(url, f"https://cefidia.com/v1/documents/{UUID}/cancel")
        self.assertEqual(
            self.client.session.request.call_args.kwargs["json"],
            {
                "motivo": "01",
                "taxpayer": "EKU9003173C9",
                "replacement": "22222222-2222-2222-2222-222222222222",
            },
        )
        self.assertEqual(ack.code["Status"], "canceled")
        self.assertIsNone(ack.acuse)

    def test_cancel_waiting_acceptance_is_pending(self):
        self.client.session.request.return_value = _response(
            payload={"state": "waiting_acceptance", "document": _stamped_doc()}
        )
        ack = self.client.cancel(
            _cfdi(),
            CancelReason.NO_SE_LLEVO_A_CABO_LA_OPERACION,
            substitution_id="ignored-for-03",
        )
        payload = self.client.session.request.call_args.kwargs["json"]
        self.assertNotIn("replacement", payload)
        self.assertEqual(ack.code["Status"], "pending")
        self.assertTrue(ack.code["Message"])

    def test_status_mapping(self):
        cases = [
            ({"state": "stamped"}, "Vigente"),
            ({"state": "cancel_pending"}, "Vigente"),
            ({"state": "canceled"}, "Cancelado"),
            ({"state": "stamped", "sat_state": "Cancelado"}, "Cancelado"),
        ]
        for doc, expected in cases:
            self.client.session.request.return_value = _response(payload=doc)
            self.assertEqual(self.client.status(_cfdi())["Status"], expected)

    def test_status_not_found(self):
        self.client.session.request.return_value = _response(
            status=404, payload={"code": "not_found", "detail": "x"}
        )
        self.assertEqual(self.client.status(_cfdi())["Status"], "No Encontrado")


class TestCefidiaService(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["l10n_mx_cfdi.cfdi_service"].create(
            {"name": "Cefidia", "provider": "cefidia", "pac_token": "cfd_test"}
        )
        cls.issuer = cls.env["l10n_mx_cfdi.issuer"].create(
            {
                "name": "Issuer",
                "vat": "EKU9003173C9",
                "fiscal_name": "Issuer SA",
                "tax_regime": cls.env.ref("l10n_mx_catalogs.c_regimen_fiscal_601").id,
                "certificate_file": b"Y2VydA==",
                "key_file": b"a2V5",
                "key_password": "password",
                "service_id": cls.service.id,
            }
        )

    def test_registry_entry(self):
        provider = pac_registry.get_provider("cefidia")
        self.assertFalse(provider.supports_issue)
        self.assertTrue(provider.supports_cancel)
        self.assertFalse(provider.requires_signer_for_cancel)
        kwargs = provider.kwargs_builder(
            SimpleNamespace(pac_token="cfd_x"), Environment.PRODUCTION
        )
        self.assertEqual(kwargs["token"], "cfd_x")

    def test_build_pac_instantiates_client(self):
        pac = pac_registry.build_pac(self.service)
        self.assertIsInstance(pac, cefidia.Cefidia)
        self.assertEqual(pac.token, "cfd_test")

    def test_capabilities(self):
        self.assertFalse(self.service.supports_issue)
        self.assertTrue(self.service.supports_cancel)

    def _account(self, missing=None, rfc="EKU9003173C9"):
        return {
            "stamping_available": True,
            "add_taxpayer_url": "https://cefidia.com/add",
            "taxpayers": [
                {
                    "rfc": rfc,
                    "name": "Issuer",
                    "is_test": True,
                    "can_stamp": not missing,
                    "missing": missing or [],
                }
            ],
        }

    def test_register_checks_taxpayer_ready(self):
        pac = MagicMock()
        pac.account_status.return_value = self._account()
        with patch.object(type(self.service), "_get_pac", return_value=pac):
            taxpayer = self.service.upload_issuer_csd(self.issuer)
        self.assertEqual(taxpayer["rfc"], "EKU9003173C9")

    def test_register_unknown_taxpayer(self):
        pac = MagicMock()
        pac.account_status.return_value = self._account(rfc="XAXX010101000")
        with (
            patch.object(type(self.service), "_get_pac", return_value=pac),
            self.assertRaisesRegex(UserError, "https://cefidia.com/add"),
        ):
            self.service.upload_issuer_csd(self.issuer)

    def test_register_missing_csd(self):
        pac = MagicMock()
        pac.account_status.return_value = self._account(
            missing=[
                {
                    "code": "csd_missing",
                    "message": "Falta el CSD",
                    "url": "https://cefidia.com/tp/1",
                }
            ]
        )
        with (
            patch.object(type(self.service), "_get_pac", return_value=pac),
            self.assertRaisesRegex(UserError, "Falta el CSD"),
        ):
            self.service.upload_issuer_csd(self.issuer)

    def test_register_ignores_expiring_warning(self):
        pac = MagicMock()
        pac.account_status.return_value = self._account(
            missing=[{"code": "csd_expiring", "message": "Vence", "url": "u"}]
        )
        with patch.object(type(self.service), "_get_pac", return_value=pac):
            self.assertTrue(self.service.upload_issuer_csd(self.issuer))

    def test_problem_json_error_message(self):
        exc = cefidia.CefidiaRejection(
            {"code": "CFDI40108", "message": "Tipo inválido", "path": "Comprobante"}
        )
        text = self.service._format_pac_error(exc)
        self.assertIn("CFDI40108: Tipo inválido", text)
        self.assertIn("- Comprobante: Tipo inválido", text)

    @mute_logger("odoo.addons.l10n_mx_cfdi.models.cfdi_service")
    def test_create_cfdi_rejection_becomes_user_error(self):
        pac = MagicMock()
        pac.stamp.side_effect = cefidia.CefidiaRejection(
            {"code": "CFDI40999", "message": "Sello inválido", "path": None}
        )
        cfdi_obj = MagicMock()
        service_cls = type(self.service)
        with (
            patch.object(service_cls, "_get_pac", return_value=pac),
            patch.object(service_cls, "_get_csd_signer", return_value=MagicMock()),
            self.assertRaisesRegex(UserError, "CFDI40999"),
        ):
            self.service.create_cfdi(cfdi_obj, issuer=self.issuer)
        cfdi_obj.sign.assert_called_once()
        pac.stamp.assert_called_once()

    def test_cancel_cfdi_pending(self):
        pac = MagicMock()
        pac.cancel.return_value = MagicMock(
            code={"Status": "pending", "Message": "Esperando aceptación"}, acuse=None
        )
        with (
            patch.object(type(self.service), "_get_pac", return_value=pac),
            patch.object(type(self.service), "_as_cfdi", return_value=_cfdi()),
        ):
            res = self.service.cancel_cfdi(b"<x/>", "02", issuer=self.issuer)
        self.assertEqual(res["Status"], "pending")
        self.assertEqual(res["Message"], "Esperando aceptación")
        self.assertIsNone(pac.cancel.call_args.kwargs["signer"])
