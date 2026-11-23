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

    @patch.object(cefidia.time, "sleep")
    def test_stamp_rejected_after_polling(self, _mock_sleep):
        rejection = {"code": "CFDI40999", "message": "Sello inválido", "path": None}
        self.client.session.request.side_effect = [
            _response(payload=_stamped_doc(state="stamping", uuid=None, links=None)),
            _response(
                payload=_stamped_doc(
                    state="rejected", uuid=None, links=None, rejection=rejection
                )
            ),
        ]
        with self.assertRaises(cefidia.CefidiaRejection) as ctx:
            self.client.stamp("<x/>")
        self.assertEqual(ctx.exception.response["code"], "CFDI40999")
        self.assertNotIn("fields", ctx.exception.response)

    def test_stamp_accepts_xml_bytes(self):
        self.client.session.request.return_value = _response(payload=_stamped_doc())
        self.client.session.get.return_value = _response(content=b"<xml/>")
        self.client.stamp(b"<signed/>", accept=Accept.XML)
        self.assertEqual(
            self.client.session.request.call_args.kwargs["json"], {"xml": "<signed/>"}
        )

    def test_empty_response_body_is_empty_dict(self):
        self.client.session.request.return_value = _response(content=b"")
        self.assertEqual(self.client._request("post", "v1/anything"), {})

    def test_download_error_raises_response_error(self):
        self.client.session.request.return_value = _response(payload=_stamped_doc())
        self.client.session.get.return_value = _response(status=403)
        with self.assertRaises(ResponseError):
            self.client.recover(DOC_ID, accept=Accept.XML)

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

    def test_status_unknown_state_is_not_found(self):
        self.client.session.request.return_value = _response(
            payload={"state": "draft", "sat_state": None}
        )
        self.assertEqual(self.client.status(_cfdi())["Status"], "No Encontrado")

    def test_status_other_http_error_raises(self):
        self.client.session.request.return_value = _response(
            status=500, payload={"code": "internal", "detail": "x"}
        )
        with self.assertRaises(ResponseError):
            self.client.status(_cfdi())

    def test_cancel_without_uuid_uses_document_id(self):
        self.client.session.request.return_value = _response(
            payload={"state": "canceled", "message": "Cancelado"}
        )
        ack = self.client.cancel(
            {"Emisor": {"Rfc": "EKU9003173C9"}},
            CancelReason.COMPROBANTE_EMITIDO_CON_ERRORES_SIN_RELACION,
            document_id=DOC_ID,
        )
        _method, url = self.client.session.request.call_args.args
        self.assertEqual(url, f"https://cefidia.com/v1/documents/{DOC_ID}/cancel")
        self.assertEqual(ack.code, {"Status": "canceled", "Message": "Cancelado"})

    def test_cancel_without_uuid_or_document_id_raises(self):
        with self.assertRaises(ValueError):
            self.client.cancel({"Emisor": {"Rfc": "EKU9003173C9"}}, "02")
        self.client.session.request.assert_not_called()


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
        self.assertTrue(provider.supports_issue)
        self.assertTrue(provider.issue_with_local_seal)
        self.assertFalse(provider.requires_registration)
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

    def test_new_service_defaults_to_cefidia(self):
        service = self.env["l10n_mx_cfdi.cfdi_service"].create({"name": "New"})
        self.assertEqual(service.provider, "cefidia")
        selection = pac_registry.provider_selection()
        self.assertEqual(selection[0][0], "cefidia")

    def test_capabilities(self):
        self.assertTrue(self.service.supports_issue)
        self.assertTrue(self.service.supports_cancel)

    def test_issuer_with_csd_is_registered_without_register(self):
        self.assertFalse(self.issuer.pac_requires_registration)
        self.assertTrue(self.issuer.registered)

    def test_issuer_without_full_csd_is_not_registered(self):
        self.issuer.key_password = False
        self.assertFalse(self.issuer.registered)
        self.issuer.key_password = "password"
        self.assertTrue(self.issuer.registered)

    def test_cefidia_issuer_usable_in_issuer_domains(self):
        found = self.env["l10n_mx_cfdi.issuer"].search(
            [("id", "=", self.issuer.id), ("registered", "=", True)]
        )
        self.assertEqual(found, self.issuer)

    def test_upload_csd_does_not_call_cefidia(self):
        pac = MagicMock()
        with patch.object(type(self.service), "_get_pac", return_value=pac):
            self.assertIsNone(self.service.upload_issuer_csd(self.issuer))
        pac.assert_not_called()
        self.assertFalse(pac.method_calls)

    def test_other_pac_keeps_manual_registration(self):
        finkok = self.env["l10n_mx_cfdi.cfdi_service"].create(
            {"name": "Finkok", "provider": "finkok"}
        )
        issuer = self.issuer.copy({"service_id": finkok.id, "registered": False})
        issuer.certificate_file = b"Y2VydA=="
        self.assertTrue(issuer.pac_requires_registration)
        self.assertFalse(issuer.registered)
        issuer.registered = True
        issuer.key_file = b"bmV3"
        self.assertTrue(issuer.registered)

    def test_create_cfdi_seals_locally_and_stamps(self):
        pac = MagicMock()
        cfdi_obj = MagicMock()
        service_cls = type(self.service)
        with (
            patch.object(service_cls, "_get_pac", return_value=pac),
            patch.object(service_cls, "_get_csd_signer", return_value=MagicMock()),
            patch(
                "odoo.addons.l10n_mx_cfdi.models.cfdi_service.cfdi_normalize"
                ".normalize_pac_document",
                return_value={},
            ),
        ):
            self.service.create_cfdi(cfdi_obj, issuer=self.issuer)
        cfdi_obj.sign.assert_called_once()
        pac.stamp.assert_called_once()
        pac.issue.assert_not_called()

    def test_problem_json_error_message(self):
        exc = cefidia.CefidiaRejection(
            {"code": "CFDI40108", "message": "Tipo inválido", "path": "Comprobante"}
        )
        text = self.service._format_pac_error(exc)
        self.assertIn("CFDI40108: Tipo inválido", text)
        self.assertIn("- Comprobante: Tipo inválido", text)

    def test_format_pac_problem(self):
        fmt = self.service._format_pac_problem
        # Not a problem document: no detail, or detail without problem keys.
        self.assertIsNone(fmt({"message": "x"}))
        self.assertIsNone(fmt({"detail": "  "}))
        self.assertIsNone(fmt({"detail": "Plain error"}))
        # Code already in the detail is not repeated.
        self.assertEqual(
            fmt({"detail": "CFDI40108: bad", "code": "CFDI40108"}), "CFDI40108: bad"
        )
        self.assertEqual(
            fmt(
                {
                    "detail": "Invalid request",
                    "code": "validation",
                    "fields": [
                        "not a field",
                        {},
                        {"path": "rfc", "message": "required"},
                        {"path": "xml"},
                    ],
                }
            ),
            "Invalid request [validation]\n- rfc: required\n- xml",
        )

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
