from unittest.mock import MagicMock, PropertyMock, patch

from satcfdi.pacs import Accept, CancelReason, Document, Environment

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, mute_logger

from odoo.addons.l10n_mx_cfdi.services import pac_registry


class TestCFDIService(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cfdi_service = cls.env["l10n_mx_cfdi.cfdi_service"].create(
            {
                "name": "Test Service",
                "provider": "finkok",
                "user": "test_user",
                "password": "test_password",
                "sandbox_mode": True,
            }
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
                "service_id": cls.cfdi_service.id,
            }
        )

    def test_provider_registry_contains_all_pacs(self):
        codes = set(pac_registry.PAC_PROVIDERS)
        self.assertEqual(
            codes,
            {
                "finkok",
                "diverza",
                "prodigia",
                "comerciodigital",
                "swsapien",
                "mysuite",
                "facturama",
            },
        )

    def test_pac_capabilities(self):
        self.assertTrue(self.cfdi_service.supports_issue)
        self.assertTrue(self.cfdi_service.supports_cancel)
        self.cfdi_service.provider = "prodigia"
        self.cfdi_service.invalidate_recordset()
        self.assertFalse(self.cfdi_service.supports_issue)
        self.assertFalse(self.cfdi_service.supports_cancel)

    def test_get_pac_sandbox(self):
        with patch(
            "odoo.addons.l10n_mx_cfdi.services.pac_registry.build_pac"
        ) as mock_build:
            mock_build.return_value = MagicMock()
            pac = self.cfdi_service._get_pac()
            self.assertTrue(pac)
            mock_build.assert_called_once()

    def test_create_cfdi_uses_issue_when_supported(self):
        mock_pac = MagicMock()
        mock_pac.issue.return_value = Document(
            document_id="doc-1",
            xml=(
                b'<?xml version="1.0"?><cfdi:Comprobante '
                b'xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Total="10" '
                b'Fecha="2024-01-01T12:00:00" NoCertificado="1" Sello="ABC">'
                b"<cfdi:Complemento><tfd:TimbreFiscalDigital "
                b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
                b'UUID="11111111-1111-1111-1111-111111111111" '
                b'SelloSAT="s" NoCertificadoSAT="2" RfcProvCertif="RFC" '
                b'FechaTimbrado="2024-01-01T13:00:00"/>'
                b"</cfdi:Complemento></cfdi:Comprobante>"
            ),
        )
        cfdi = MagicMock()
        with patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac):
            result = self.cfdi_service.create_cfdi(cfdi, issuer=self.issuer)
        mock_pac.issue.assert_called_once()
        mock_pac.stamp.assert_not_called()
        self.assertEqual(result["status"], "published")
        self.assertEqual(result["uuid"], "11111111-1111-1111-1111-111111111111")
        self.assertEqual(mock_pac.issue.call_args.kwargs.get("accept"), Accept.XML_PDF)

    def test_create_cfdi_uses_stamp_when_issue_unsupported(self):
        self.cfdi_service.provider = "prodigia"
        self.cfdi_service.pac_contrato = "1234"
        mock_pac = MagicMock()
        mock_pac.stamp.return_value = Document(
            document_id="uuid-1",
            xml=(
                b'<?xml version="1.0"?><cfdi:Comprobante '
                b'xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Total="10" '
                b'Fecha="2024-01-01T12:00:00" NoCertificado="1" Sello="ABC">'
                b"<cfdi:Complemento><tfd:TimbreFiscalDigital "
                b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
                b'UUID="22222222-2222-2222-2222-222222222222" '
                b'SelloSAT="s" NoCertificadoSAT="2" RfcProvCertif="RFC" '
                b'FechaTimbrado="2024-01-01T13:00:00"/>'
                b"</cfdi:Complemento></cfdi:Comprobante>"
            ),
        )
        cfdi = MagicMock()
        cfdi.get.return_value = None
        with (
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
            patch.object(
                type(self.cfdi_service),
                "_get_csd_signer",
                return_value=MagicMock(),
            ),
        ):
            result = self.cfdi_service.create_cfdi(cfdi, issuer=self.issuer)
        mock_pac.stamp.assert_called_once()
        self.assertEqual(result["uuid"], "22222222-2222-2222-2222-222222222222")

    @mute_logger("odoo.addons.l10n_mx_cfdi.models.cfdi_service")
    def test_create_cfdi_error(self):
        mock_pac = MagicMock()
        mock_pac.issue.side_effect = RuntimeError("PAC down")
        with patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac):
            with self.assertRaises(UserError):
                self.cfdi_service.create_cfdi(MagicMock(), issuer=self.issuer)

    def test_cancel_unsupported_provider(self):
        self.cfdi_service.provider = "mysuite"
        with self.assertRaises(UserError):
            self.cfdi_service.cancel_cfdi(b"<xml/>", "02", issuer=self.issuer)

    def test_cancel_cfdi_success(self):
        mock_pac = MagicMock()
        mock_pac.cancel.return_value = MagicMock(code="201", acuse=b"<acuse/>")
        xml = (
            b'<?xml version="1.0"?><cfdi:Comprobante '
            b'xmlns:cfdi="http://www.sat.gob.mx/cfd/4">'
            b"<cfdi:Complemento><tfd:TimbreFiscalDigital "
            b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
            b'UUID="33333333-3333-3333-3333-333333333333"/>'
            b"</cfdi:Complemento></cfdi:Comprobante>"
        )
        with (
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
            patch.object(
                type(self.cfdi_service),
                "_get_cancel_signer",
                return_value=MagicMock(),
            ),
        ):
            result = self.cfdi_service.cancel_cfdi(xml, "02", issuer=self.issuer)
        self.assertIn(result["Status"], ("canceled", "pending"))
        mock_pac.cancel.assert_called_once()
        args, kwargs = mock_pac.cancel.call_args
        self.assertEqual(
            kwargs.get("reason") or args[1],
            CancelReason.COMPROBANTE_EMITIDO_CON_ERRORES_SIN_RELACION,
        )

    def test_finkok_kwargs(self):
        provider = pac_registry.get_provider("finkok")
        kwargs = provider.kwargs_builder(self.cfdi_service, Environment.TEST)
        self.assertEqual(kwargs["username"], "test_user")
        self.assertEqual(kwargs["environment"], Environment.TEST)

    def test_map_cancel_reason(self):
        reason = self.cfdi_service._map_cancel_reason("01")
        self.assertEqual(
            reason, CancelReason.COMPROBANTE_EMITIDO_CON_ERRORES_CON_RELACION
        )

    @mute_logger("odoo.addons.l10n_mx_cfdi.models.cfdi_service")
    def test_check_cfdi_status_unknown_on_error(self):
        mock_pac = MagicMock()
        mock_pac.status.side_effect = NotImplementedError()
        with patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac):
            status = self.cfdi_service.check_cfdi_status("u", "a", "b", 1)
        self.assertEqual(status, "unknown")

    def test_get_cfdi_pdf_success_and_empty(self):
        mock_pac = MagicMock()
        mock_pac.recover.return_value = MagicMock(pdf=b"%PDF-1.4")
        with patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac):
            result = self.cfdi_service.get_cfdi_pdf("track-1")
        self.assertIn("Content", result)
        self.assertTrue(result["Content"])

        mock_pac.recover.return_value = MagicMock(pdf=None)
        with (
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
            self.assertRaises(UserError),
        ):
            self.cfdi_service.get_cfdi_pdf("track-1")

        mock_pac.recover.side_effect = NotImplementedError()
        with (
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
            self.assertRaises(UserError) as err,
        ):
            self.cfdi_service.get_cfdi_pdf("track-1")
        self.assertIn("does not provide PDF recovery", str(err.exception))

    def test_get_cfdi_pdf_from_sw_dict_payload(self):
        """SW Sapien recover() may return a raw dict instead of Document."""
        import base64

        mock_pac = MagicMock()
        mock_pac.recover.return_value = {
            "status": "success",
            "data": {"contentB64": base64.b64encode(b"%PDF-sw").decode()},
        }
        with patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac):
            result = self.cfdi_service.get_cfdi_pdf("track-sw")
        self.assertEqual(base64.b64decode(result["Content"]), b"%PDF-sw")

        mock_pac.recover.return_value = {"status": "success", "data": {}}
        with (
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
            self.assertRaises(UserError),
        ):
            self.cfdi_service.get_cfdi_pdf("track-sw")

    def test_create_cfdi_facturama_cartaporte_message(self):
        self.cfdi_service.provider = "facturama"
        mock_pac = MagicMock()
        mock_pac.issue.side_effect = NotImplementedError(
            "Unsupported Complemento: CartaPorte"
        )
        with (
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
            self.assertRaises(UserError) as err,
        ):
            self.cfdi_service.create_cfdi(MagicMock(), issuer=self.issuer)
        self.assertIn("Carta Porte", str(err.exception))

    def test_get_cfdi_xml_success_and_not_implemented(self):
        mock_pac = MagicMock()
        mock_pac.recover.return_value = MagicMock(xml=b"<xml/>")
        with patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac):
            result = self.cfdi_service.get_cfdi_xml("track-1")
        self.assertEqual(result["Content"], b"<xml/>")

        mock_pac.recover.side_effect = NotImplementedError()
        with (
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
            self.assertRaises(UserError),
        ):
            self.cfdi_service.get_cfdi_xml("track-1")

    def test_check_cfdi_status_maps_vigente_and_cancelado(self):
        mock_pac = MagicMock()
        mock_pac.status.return_value = {"Status": "Vigente"}
        with patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac):
            self.assertEqual(
                self.cfdi_service.check_cfdi_status("u", "a", "b", 1), "published"
            )
        mock_pac.status.return_value = {"estado": "Cancelado"}
        with patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac):
            self.assertEqual(
                self.cfdi_service.check_cfdi_status("u", "a", "b", 1), "canceled"
            )

    def test_map_cancel_status_variants(self):
        self.assertEqual(self.cfdi_service._map_cancel_status(None), "canceled")
        self.assertEqual(self.cfdi_service._map_cancel_status("201"), "pending")
        self.assertEqual(self.cfdi_service._map_cancel_status("pending"), "pending")
        self.assertEqual(self.cfdi_service._map_cancel_status("205"), "rejected")
        self.assertEqual(self.cfdi_service._map_cancel_status("rejected"), "rejected")
        self.assertEqual(self.cfdi_service._map_cancel_status("202"), "pending")
        self.assertEqual(self.cfdi_service._map_cancel_status("ok"), "canceled")
        self.assertEqual(self.cfdi_service._map_cancel_status("active"), "active")
        self.assertEqual(
            self.cfdi_service._map_cancel_status(
                {"Status": "canceled", "Message": "Cancelado sin Aceptacion"}
            ),
            "canceled",
        )

    def test_split_cancel_ack_facturama_dict(self):
        status, message = self.cfdi_service._split_cancel_ack(
            {"Status": "pending", "Message": "En proceso"}
        )
        self.assertEqual(status, "pending")
        self.assertEqual(message, "En proceso")

    def test_split_cancel_ack_non_string_message(self):
        status, message = self.cfdi_service._split_cancel_ack(
            {"Status": "canceled", "Message": 404}
        )
        self.assertEqual(status, "canceled")
        self.assertEqual(message, "404")
        status, message = self.cfdi_service._split_cancel_ack(
            {"Status": "canceled", "Message": None}
        )
        self.assertEqual(message, "")

    def test_cancel_cfdi_facturama_status_message_and_acuse(self):
        mock_pac = MagicMock()
        mock_pac.cancel.return_value = MagicMock(
            code={"Status": "canceled", "Message": "Cancelado sin Aceptacion"},
            acuse=b"<acuse/>",
        )
        xml = (
            b'<?xml version="1.0"?><cfdi:Comprobante '
            b'xmlns:cfdi="http://www.sat.gob.mx/cfd/4">'
            b"<cfdi:Complemento><tfd:TimbreFiscalDigital "
            b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
            b'UUID="33333333-3333-3333-3333-333333333333"/>'
            b"</cfdi:Complemento></cfdi:Comprobante>"
        )
        self.cfdi_service.provider = "facturama"
        with patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac):
            result = self.cfdi_service.cancel_cfdi(
                xml, "02", issuer=self.issuer, document_id="doc-1"
            )
        self.assertEqual(result["Status"], "canceled")
        self.assertEqual(result["Message"], "Cancelado sin Aceptacion")
        self.assertEqual(result["Acuse"], b"<acuse/>")

    def test_as_cfdi_bytes_str_and_uuid_stub(self):
        from satcfdi.cfdi import CFDI

        stub = CFDI({"Complemento": {"TimbreFiscalDigital": {"UUID": "u"}}})
        self.assertIs(self.cfdi_service._as_cfdi(stub), stub)

        xml = (
            b'<?xml version="1.0"?><cfdi:Comprobante '
            b'xmlns:cfdi="http://www.sat.gob.mx/cfd/4">'
            b"<cfdi:Complemento><tfd:TimbreFiscalDigital "
            b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
            b'UUID="33333333-3333-3333-3333-333333333333"/>'
            b"</cfdi:Complemento></cfdi:Comprobante>"
        )
        cfdi = self.cfdi_service._as_cfdi(xml)
        self.assertEqual(
            cfdi["Complemento"]["TimbreFiscalDigital"]["UUID"],
            "33333333-3333-3333-3333-333333333333",
        )
        cfdi_str = self.cfdi_service._as_cfdi(xml.decode())
        self.assertEqual(
            cfdi_str["Complemento"]["TimbreFiscalDigital"]["UUID"],
            "33333333-3333-3333-3333-333333333333",
        )
        with self.assertRaises(UserError):
            self.cfdi_service._as_cfdi(b"<cfdi:Comprobante/>")

    def test_get_csd_signer_missing_certificate(self):
        self.issuer.certificate_file = False
        with self.assertRaises(UserError):
            self.cfdi_service._get_csd_signer(self.issuer)

    def test_get_csd_signer_rfc_mismatch(self):
        fake_signer = MagicMock(rfc="AAAA010101AAA")
        with (
            patch(
                "odoo.addons.l10n_mx_cfdi.models.cfdi_service.Signer.load",
                return_value=fake_signer,
            ),
            self.assertRaises(UserError),
        ):
            self.cfdi_service._get_csd_signer(self.issuer)

    def test_get_cancel_signer_fiel_then_fallback(self):
        from types import SimpleNamespace

        fiel_signer = MagicMock(name="fiel")
        csd_signer = MagicMock(name="csd")
        fiel_company = SimpleNamespace(
            l10n_mx_sat_fiel_cer=b"Y2Vy",
            l10n_mx_sat_fiel_key=b"a2V5",
            l10n_mx_sat_fiel_password="secret",
        )
        with (
            patch.object(
                type(self.issuer),
                "company_id",
                new_callable=PropertyMock,
                return_value=fiel_company,
            ),
            patch(
                "odoo.addons.l10n_mx_cfdi.models.cfdi_service.Signer.load",
                return_value=fiel_signer,
            ),
        ):
            result = self.cfdi_service._get_cancel_signer(self.issuer)
        self.assertIs(result, fiel_signer)

        with (
            patch.object(
                type(self.issuer),
                "company_id",
                new_callable=PropertyMock,
                return_value=fiel_company,
            ),
            patch(
                "odoo.addons.l10n_mx_cfdi.models.cfdi_service.Signer.load",
                side_effect=ValueError("bad fiel"),
            ),
            patch.object(
                type(self.cfdi_service),
                "_get_csd_signer",
                return_value=csd_signer,
            ) as mock_csd,
            mute_logger("odoo.addons.l10n_mx_cfdi.models.cfdi_service"),
        ):
            result = self.cfdi_service._get_cancel_signer(self.issuer)
        self.assertIs(result, csd_signer)
        mock_csd.assert_called_once()

    def test_cancel_cfdi_requires_issuer_for_finkok(self):
        xml = (
            b'<?xml version="1.0"?><cfdi:Comprobante '
            b'xmlns:cfdi="http://www.sat.gob.mx/cfd/4">'
            b"<cfdi:Complemento><tfd:TimbreFiscalDigital "
            b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
            b'UUID="33333333-3333-3333-3333-333333333333"/>'
            b"</cfdi:Complemento></cfdi:Comprobante>"
        )
        with self.assertRaises(UserError):
            self.cfdi_service.cancel_cfdi(xml, "02", issuer=None)

    def test_cancel_cfdi_with_uuid_replacement(self):
        mock_pac = MagicMock()
        mock_pac.cancel.return_value = MagicMock(code="201", acuse=b"<acuse/>")
        xml = (
            b'<?xml version="1.0"?><cfdi:Comprobante '
            b'xmlns:cfdi="http://www.sat.gob.mx/cfd/4">'
            b"<cfdi:Complemento><tfd:TimbreFiscalDigital "
            b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
            b'UUID="33333333-3333-3333-3333-333333333333"/>'
            b"</cfdi:Complemento></cfdi:Comprobante>"
        )
        with (
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
            patch.object(
                type(self.cfdi_service),
                "_get_cancel_signer",
                return_value=MagicMock(),
            ),
        ):
            result = self.cfdi_service.cancel_cfdi(
                xml,
                "01",
                uuid_replacement="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                issuer=self.issuer,
            )
        self.assertEqual(result["Status"], "pending")
        self.assertEqual(
            mock_pac.cancel.call_args.kwargs.get("substitution_id"),
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        )

    def test_get_cancellation_request_proof_raises(self):
        with self.assertRaises(UserError):
            self.cfdi_service.get_cancellation_request_proof("track")

    def test_map_cancel_reason_invalid(self):
        with self.assertRaises(UserError):
            self.cfdi_service._map_cancel_reason("99")

    def test_get_pac_missing_provider(self):
        service = self.env["l10n_mx_cfdi.cfdi_service"].new({"provider": False})
        with self.assertRaises(UserError):
            service._get_pac()

    def test_get_pac_build_failure(self):
        with (
            patch(
                "odoo.addons.l10n_mx_cfdi.models.cfdi_service.pac_registry.build_pac",
                side_effect=RuntimeError("boom"),
            ),
            mute_logger("odoo.addons.l10n_mx_cfdi.models.cfdi_service"),
            self.assertRaises(UserError),
        ):
            self.cfdi_service._get_pac()

    def test_create_cfdi_requires_issuer(self):
        with self.assertRaises(UserError):
            self.cfdi_service.create_cfdi(MagicMock(), issuer=None)

    def test_create_cfdi_not_implemented(self):
        mock_pac = MagicMock()
        mock_pac.issue.side_effect = NotImplementedError("no issue")
        with (
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
            self.assertRaises(UserError),
        ):
            self.cfdi_service.create_cfdi(MagicMock(), issuer=self.issuer)

    def test_get_cfdi_pdf_generic_error(self):
        mock_pac = MagicMock()
        mock_pac.recover.side_effect = RuntimeError("pdf fail")
        with (
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
            self.assertRaises(UserError),
        ):
            self.cfdi_service.get_cfdi_pdf("track")

    def test_get_cfdi_xml_generic_error(self):
        mock_pac = MagicMock()
        mock_pac.recover.side_effect = RuntimeError("xml fail")
        with (
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
            self.assertRaises(UserError),
        ):
            self.cfdi_service.get_cfdi_xml("track")

    def test_cancel_cfdi_pac_exception(self):
        mock_pac = MagicMock()
        mock_pac.cancel.side_effect = RuntimeError("cancel fail")
        xml = (
            b'<?xml version="1.0"?><cfdi:Comprobante '
            b'xmlns:cfdi="http://www.sat.gob.mx/cfd/4">'
            b"<cfdi:Complemento><tfd:TimbreFiscalDigital "
            b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
            b'UUID="33333333-3333-3333-3333-333333333333"/>'
            b"</cfdi:Complemento></cfdi:Comprobante>"
        )
        with (
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
            patch.object(
                type(self.cfdi_service),
                "_get_cancel_signer",
                return_value=MagicMock(),
            ),
            mute_logger("odoo.addons.l10n_mx_cfdi.models.cfdi_service"),
            self.assertRaises(UserError),
        ):
            self.cfdi_service.cancel_cfdi(xml, "02", issuer=self.issuer)

    def test_cancel_cfdi_uuid_replacement_object(self):
        from types import SimpleNamespace

        mock_pac = MagicMock()
        mock_pac.cancel.return_value = MagicMock(code=None, acuse=None)
        xml = (
            b'<?xml version="1.0"?><cfdi:Comprobante '
            b'xmlns:cfdi="http://www.sat.gob.mx/cfd/4">'
            b"<cfdi:Complemento><tfd:TimbreFiscalDigital "
            b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
            b'UUID="33333333-3333-3333-3333-333333333333"/>'
            b"</cfdi:Complemento></cfdi:Comprobante>"
        )
        replacement = SimpleNamespace(uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        with (
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
            patch.object(
                type(self.cfdi_service),
                "_get_cancel_signer",
                return_value=MagicMock(),
            ),
        ):
            result = self.cfdi_service.cancel_cfdi(
                xml, "01", uuid_replacement=replacement, issuer=self.issuer
            )
        self.assertEqual(result["Status"], "canceled")
        self.assertEqual(
            mock_pac.cancel.call_args.kwargs.get("substitution_id"),
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        )

    def test_cancel_cfdi_passes_document_id_when_supported(self):
        mock_pac = MagicMock()
        mock_pac.cancel.return_value = MagicMock(code=None, acuse=None)
        xml = (
            b'<?xml version="1.0"?><cfdi:Comprobante '
            b'xmlns:cfdi="http://www.sat.gob.mx/cfd/4">'
            b"<cfdi:Complemento><tfd:TimbreFiscalDigital "
            b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
            b'UUID="33333333-3333-3333-3333-333333333333"/>'
            b"</cfdi:Complemento></cfdi:Comprobante>"
        )
        self.cfdi_service.provider = "facturama"
        with patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac):
            self.cfdi_service.cancel_cfdi(
                xml, "02", issuer=self.issuer, document_id="facturama-doc-id"
            )
        self.assertEqual(
            mock_pac.cancel.call_args.kwargs.get("document_id"),
            "facturama-doc-id",
        )

    def test_upload_issuer_csd_facturama_only(self):
        mock_pac = MagicMock()
        mock_pac.upload_csd.return_value = {"Rfc": "EKU9003173C9"}
        with (
            patch.object(
                type(self.cfdi_service),
                "_get_csd_signer",
                return_value=MagicMock(rfc="EKU9003173C9"),
            ),
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
        ):
            self.assertIsNone(self.cfdi_service.upload_issuer_csd(self.issuer))
            mock_pac.upload_csd.assert_not_called()

            self.cfdi_service.provider = "facturama"
            self.cfdi_service.upload_issuer_csd(self.issuer)
            mock_pac.upload_csd.assert_called_once()
            self.assertEqual(
                mock_pac.upload_csd.call_args.kwargs["rfc"], "EKU9003173C9"
            )

    @mute_logger("odoo.addons.l10n_mx_cfdi.models.cfdi_service")
    def test_upload_issuer_csd_raises_user_error(self):
        mock_pac = MagicMock()
        mock_pac.upload_csd.side_effect = RuntimeError("PAC reject")
        self.cfdi_service.provider = "facturama"
        with (
            patch.object(
                type(self.cfdi_service),
                "_get_csd_signer",
                return_value=MagicMock(rfc="EKU9003173C9"),
            ),
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
            self.assertRaises(UserError) as err,
        ):
            self.cfdi_service.upload_issuer_csd(self.issuer)
        self.assertIn("Cannot upload the CSD to Facturama", str(err.exception))

    def test_upload_issuer_csd_falls_back_to_signer_rfc(self):
        mock_pac = MagicMock()
        mock_pac.upload_csd.return_value = {}
        self.cfdi_service.provider = "facturama"
        self.issuer.vat = False
        with (
            patch.object(
                type(self.cfdi_service),
                "_get_csd_signer",
                return_value=MagicMock(rfc="EKU9003173C9"),
            ),
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
        ):
            self.cfdi_service.upload_issuer_csd(self.issuer)
        self.assertEqual(mock_pac.upload_csd.call_args.kwargs["rfc"], "EKU9003173C9")

    def test_delete_issuer_csd_facturama_success(self):
        mock_pac = MagicMock()
        self.cfdi_service.provider = "facturama"
        with patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac):
            self.cfdi_service.delete_issuer_csd(self.issuer)
        mock_pac.delete_csd.assert_called_once_with(self.issuer.vat)

    def test_delete_issuer_csd_skips_non_facturama_and_missing_vat(self):
        mock_pac = MagicMock()
        with patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac):
            self.cfdi_service.delete_issuer_csd(self.issuer)
            self.cfdi_service.provider = "facturama"
            self.issuer.vat = False
            self.cfdi_service.delete_issuer_csd(self.issuer)
        mock_pac.delete_csd.assert_not_called()

    @mute_logger("odoo.addons.l10n_mx_cfdi.models.cfdi_service")
    def test_delete_issuer_csd_swallows_errors(self):
        mock_pac = MagicMock()
        mock_pac.delete_csd.side_effect = RuntimeError("gone")
        self.cfdi_service.provider = "facturama"
        with patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac):
            self.cfdi_service.delete_issuer_csd(self.issuer)

    def test_cancel_cfdi_ignores_document_id_for_non_facturama(self):
        mock_pac = MagicMock()
        mock_pac.cancel.return_value = MagicMock(code=None, acuse=None)
        xml = (
            b'<?xml version="1.0"?><cfdi:Comprobante '
            b'xmlns:cfdi="http://www.sat.gob.mx/cfd/4">'
            b"<cfdi:Complemento><tfd:TimbreFiscalDigital "
            b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
            b'UUID="33333333-3333-3333-3333-333333333333"/>'
            b"</cfdi:Complemento></cfdi:Comprobante>"
        )
        with (
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
            patch.object(
                type(self.cfdi_service),
                "_get_cancel_signer",
                return_value=MagicMock(),
            ),
        ):
            self.cfdi_service.cancel_cfdi(
                xml, "02", issuer=self.issuer, document_id="ignored-id"
            )
        self.assertNotIn("document_id", mock_pac.cancel.call_args.kwargs)

    def test_check_cfdi_status_status_variants(self):
        mock_pac = MagicMock()
        with patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac):
            mock_pac.status.return_value = {"Status": "Active"}
            self.assertEqual(
                self.cfdi_service.check_cfdi_status("u", "a", "b", 1), "published"
            )
            mock_pac.status.return_value = {"estado": "cancelled"}
            self.assertEqual(
                self.cfdi_service.check_cfdi_status("u", "a", "b", 1), "canceled"
            )
            mock_pac.status.return_value = {"Estado": "No Encontrado"}
            self.assertEqual(
                self.cfdi_service.check_cfdi_status("u", "a", "b", 1), "unknown"
            )
            mock_pac.status.return_value = {"Status": "weird"}
            self.assertEqual(
                self.cfdi_service.check_cfdi_status("u", "a", "b", 1), "unknown"
            )

    @mute_logger("odoo.addons.l10n_mx_cfdi.models.cfdi_service")
    def test_check_cfdi_status_generic_exception(self):
        mock_pac = MagicMock()
        mock_pac.status.side_effect = RuntimeError("status fail")
        with patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac):
            self.assertEqual(
                self.cfdi_service.check_cfdi_status("u", "a", "b", 1), "unknown"
            )

    def test_map_cancel_reason_passthrough_enum(self):
        reason = CancelReason.NO_SE_LLEVO_A_CABO_LA_OPERACION
        self.assertIs(self.cfdi_service._map_cancel_reason(reason), reason)

    def test_as_cfdi_invalid_payload(self):
        with self.assertRaises(UserError):
            self.cfdi_service._as_cfdi(12345)

    def test_as_cfdi_xml_syntax_error(self):
        with self.assertRaises(UserError) as err:
            self.cfdi_service._as_cfdi(b"<<<not-xml")
        self.assertIn("invalid or missing UUID", str(err.exception))

    def test_get_csd_signer_invalid_certificate(self):
        with (
            patch(
                "odoo.addons.l10n_mx_cfdi.models.cfdi_service.Signer.load",
                side_effect=ValueError("bad DER"),
            ),
            self.assertRaises(UserError) as err,
        ):
            self.cfdi_service._get_csd_signer(self.issuer)
        self.assertIn("Invalid digital certificate", str(err.exception))

    def test_get_csd_signer_missing_password(self):
        self.issuer.key_password = False
        with self.assertRaises(UserError):
            self.cfdi_service._get_csd_signer(self.issuer)

    def test_get_csd_signer_skips_rfc_check_without_issuer_vat(self):
        self.issuer.vat = False
        fake = MagicMock(rfc="AAAA010101AAA")
        with patch(
            "odoo.addons.l10n_mx_cfdi.models.cfdi_service.Signer.load",
            return_value=fake,
        ):
            self.assertIs(self.cfdi_service._get_csd_signer(self.issuer), fake)

    def test_create_cfdi_reraises_user_error(self):
        self.cfdi_service.provider = "prodigia"
        self.cfdi_service.pac_contrato = "1"
        with (
            patch.object(type(self.cfdi_service), "_get_pac", return_value=MagicMock()),
            patch.object(
                type(self.cfdi_service),
                "_get_csd_signer",
                side_effect=UserError("CSD boom"),
            ),
            self.assertRaises(UserError) as err,
        ):
            self.cfdi_service.create_cfdi(MagicMock(), issuer=self.issuer)
        self.assertEqual(str(err.exception), "CSD boom")

    def test_create_cfdi_stamp_sign_without_process(self):
        self.cfdi_service.provider = "prodigia"
        self.cfdi_service.pac_contrato = "1"
        mock_pac = MagicMock()
        mock_pac.stamp.return_value = Document(
            document_id="uuid-1",
            xml=(
                b'<?xml version="1.0"?><cfdi:Comprobante '
                b'xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Total="10" '
                b'Fecha="2024-01-01T12:00:00" NoCertificado="1" Sello="ABC">'
                b"<cfdi:Complemento><tfd:TimbreFiscalDigital "
                b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
                b'UUID="22222222-2222-2222-2222-222222222222" '
                b'SelloSAT="s" NoCertificadoSAT="2" RfcProvCertif="RFC" '
                b'FechaTimbrado="2024-01-01T13:00:00"/>'
                b"</cfdi:Complemento></cfdi:Comprobante>"
            ),
        )
        cfdi = MagicMock(spec=["sign", "get"])
        cfdi.get.return_value = None
        with (
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
            patch.object(
                type(self.cfdi_service), "_get_csd_signer", return_value=MagicMock()
            ),
        ):
            self.cfdi_service.create_cfdi(cfdi, issuer=self.issuer)
        cfdi.sign.assert_called_once()
        mock_pac.stamp.assert_called_once()

    def test_create_cfdi_stamp_signs_cfdi_without_sign_attr(self):
        """Cover the elif branch when hasattr(cfdi, 'sign') is false."""
        from satcfdi.cfdi import CFDI

        self.cfdi_service.provider = "prodigia"
        self.cfdi_service.pac_contrato = "1"
        mock_pac = MagicMock()
        mock_pac.stamp.return_value = Document(
            document_id="uuid-elif",
            xml=(
                b'<?xml version="1.0"?><cfdi:Comprobante '
                b'xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Total="10" '
                b'Fecha="2024-01-01T12:00:00" NoCertificado="1" Sello="ABC">'
                b"<cfdi:Complemento><tfd:TimbreFiscalDigital "
                b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
                b'UUID="33333333-3333-3333-3333-333333333333" '
                b'SelloSAT="s" NoCertificadoSAT="2" RfcProvCertif="RFC" '
                b'FechaTimbrado="2024-01-01T13:00:00"/>'
                b"</cfdi:Complemento></cfdi:Comprobante>"
            ),
        )
        cfdi = CFDI({"TipoDeComprobante": "I", "Conceptos": []})
        signer = MagicMock()
        real_hasattr = hasattr

        def _hasattr(obj, name):
            if obj is cfdi and name == "sign":
                return False
            return real_hasattr(obj, name)

        with (
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
            patch.object(
                type(self.cfdi_service), "_get_csd_signer", return_value=signer
            ),
            patch("builtins.hasattr", side_effect=_hasattr),
            patch.object(type(cfdi), "sign") as mock_sign,
        ):
            self.cfdi_service.create_cfdi(cfdi, issuer=self.issuer)
        mock_sign.assert_called_once_with(signer)
        mock_pac.stamp.assert_called_once()

    def test_compute_pac_capabilities_without_provider(self):
        service = self.env["l10n_mx_cfdi.cfdi_service"].new({"provider": False})
        service._compute_pac_capabilities()
        self.assertFalse(service.supports_issue)
        self.assertFalse(service.supports_cancel)

    def test_check_cfdi_status_non_dict_response(self):
        mock_pac = MagicMock()
        mock_pac.status.return_value = "Vigente"
        with patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac):
            self.assertEqual(
                self.cfdi_service.check_cfdi_status("u", "a", "b", 1), "unknown"
            )

    def test_get_cfdi_xml_none_content(self):
        mock_pac = MagicMock()
        mock_pac.recover.return_value = MagicMock(xml=None)
        with patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac):
            self.assertEqual(self.cfdi_service.get_cfdi_xml("t")["Content"], b"")

    def test_format_pac_error_prodigia_dict(self):
        from satcfdi.exceptions import ResponseError

        payload = {
            "servicioTimbrado": {
                "codigo": 2,
                "contrato": "1fca4f82-c815-4be1-b405-fcc7d7cf9bd6",
                "timbradoOk": False,
                "mensaje": (
                    "El contrato con código 1fca4f82-c815-4be1-b405-fcc7d7cf9bd6 "
                    "no fue encontrado"
                ),
            }
        }
        detail = self.cfdi_service._format_pac_error(ResponseError(payload))
        self.assertIn("no fue encontrado", detail)

    def test_format_pac_error_sw_response(self):
        from satcfdi.exceptions import ResponseError

        response = MagicMock()
        response.json.return_value = {
            "status": "error",
            "message": "CFDI40101 - El campo Fecha no cumple",
            "messageDetail": "Detalle SW",
        }
        response.text = '{"status":"error"}'
        response.status_code = 400
        detail = self.cfdi_service._format_pac_error(ResponseError(response))
        self.assertIn("CFDI40101", detail)
        self.assertIn("Detalle SW", detail)
        self.assertNotIn("<Response", detail)

    def test_format_pac_error_sw_generic_solicitud_includes_message_detail(self):
        """Cristhian/SW: generic message must not hide messageDetail (CFDI40…)."""
        from satcfdi.exceptions import ResponseError

        response = MagicMock()
        response.json.return_value = {
            "status": "error",
            "message": "La solicitud no es válida.",
            "messageDetail": (
                "CFDI40145 - El campo TasaOCuota del nodo Traslado no "
                "contiene un valor del catálogo c_TasaOCuota."
            ),
            "data": None,
        }
        response.text = '{"status":"error"}'
        response.status_code = 400
        detail = self.cfdi_service._format_pac_error(ResponseError(response))
        self.assertIn("CFDI40145", detail)
        self.assertIn("TasaOCuota", detail)
        # Keep the wrapper too so logs stay searchable
        self.assertIn("solicitud no es válida", detail.lower())

    def test_format_pac_error_opaque_error_no_clasificado_dumps_payload(self):
        """Facturama 'Error no clasificado' must surface the full JSON body."""
        from satcfdi.exceptions import ResponseError

        payload = {
            "Message": "Error no clasificado",
            "ModelState": {
                "cfdiToCreate.Complemento.ForeignTrade": ["Missing Addresses"]
            },
        }
        detail = self.cfdi_service._format_pac_error(ResponseError(payload))
        self.assertIn("Error no clasificado", detail)
        self.assertIn("ForeignTrade", detail)
        self.assertIn("Addresses", detail)

    def test_format_pac_error_opaque_cfdi40999_prefix_dumps_payload(self):
        """CFDI40999-prefixed opaque messages must still dump PAC JSON."""
        from satcfdi.exceptions import ResponseError

        payload = {
            "Message": "CFDI40999 - Error no clasificado",
            "Items": [{"NumerosPedimento": ["bad"]}],
        }
        detail = self.cfdi_service._format_pac_error(ResponseError(payload))
        self.assertIn("Error no clasificado", detail)
        self.assertIn("NumerosPedimento", detail)

    @mute_logger("odoo.addons.l10n_mx_cfdi.models.cfdi_service")
    def test_create_cfdi_surfaces_sw_message_detail(self):
        """create_cfdi UserError must include messageDetail, not only the wrapper."""
        from satcfdi.exceptions import ResponseError

        response = MagicMock()
        response.json.return_value = {
            "status": "error",
            "message": "La solicitud no es válida.",
            "messageDetail": "CFDI40143 - El campo Nombre del emisor no coincide",
        }
        response.text = ""
        response.status_code = 400
        mock_pac = MagicMock()
        mock_pac.issue.side_effect = ResponseError(response)
        with (
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
            self.assertRaises(UserError) as err,
        ):
            self.cfdi_service.create_cfdi(MagicMock(spec=[]), issuer=self.issuer)
        self.assertIn("CFDI40143", str(err.exception))
        self.assertIn("Nombre del emisor", str(err.exception))

    def test_format_pac_error_http_fallback(self):
        from satcfdi.exceptions import ResponseError

        response = MagicMock()
        response.json.side_effect = ValueError("not json")
        response.text = ""
        response.status_code = 400
        response.reason = "Bad Request"
        detail = self.cfdi_service._format_pac_error(ResponseError(response))
        self.assertIn("HTTP 400", detail)

    def test_format_pac_error_plain_text_body(self):
        from satcfdi.exceptions import ResponseError

        response = MagicMock()
        response.json.side_effect = ValueError("not json")
        response.text = "plain PAC error body"
        response.status_code = 500
        detail = self.cfdi_service._format_pac_error(ResponseError(response))
        self.assertEqual(detail, "plain PAC error body")

    def test_detail_from_pac_mapping_nested_data_string(self):
        detail = self.cfdi_service._detail_from_pac_mapping(
            {"data": "nested string error"}
        )
        self.assertEqual(detail, "nested string error")

    def test_detail_from_pac_mapping_facturama_model_state(self):
        """Facturama ASP.NET ModelState must not be hidden behind the wrapper."""
        detail = self.cfdi_service._detail_from_pac_mapping(
            {
                "Message": "La solicitud no es válida.",
                "ModelState": {
                    "cfdi.Exportation": ["The Exportation field is required."],
                    "cfdi.Relations": ["The Relations field is required."],
                },
            }
        )
        self.assertIn("solicitud no es válida", detail.lower())
        self.assertIn("Exportation", detail)
        self.assertIn("Relations", detail)

    def test_detail_from_pac_mapping_edge_cases(self):
        svc = self.cfdi_service
        self.assertIsNone(svc._detail_from_pac_mapping("not-a-dict"))
        self.assertIsNone(svc._detail_from_pac_mapping({}))
        self.assertEqual(
            svc._detail_from_pac_mapping({"message": {"mensaje": "inner msg"}}),
            "inner msg",
        )
        self.assertEqual(
            svc._detail_from_pac_mapping({"data": {"mensaje": "from nested data"}}),
            "from nested data",
        )
        self.assertIsNone(
            svc._detail_from_pac_mapping({"message": {"codigo": 1}, "data": {"x": 1}})
        )
        self.assertIsNone(svc._pac_mapping_text("not-a-dict", ("message",)))
        # Prefer the longer string when one side contains the other.
        self.assertEqual(
            svc._detail_from_pac_mapping(
                {
                    "message": "CFDI40145 detail already in summary",
                    "messageDetail": "detail already in summary",
                }
            ),
            "CFDI40145 detail already in summary",
        )
        self.assertEqual(
            svc._detail_from_pac_mapping(
                {
                    "message": "La solicitud no es válida.",
                    "messageDetail": (
                        "La solicitud no es válida. CFDI40145 - TasaOCuota"
                    ),
                }
            ),
            "La solicitud no es válida. CFDI40145 - TasaOCuota",
        )

    def test_extract_pac_response_detail_returns_none(self):
        class EmptyResponse:
            pass

        self.assertIsNone(
            self.cfdi_service._extract_pac_response_detail(EmptyResponse())
        )

    def test_pac_recover_file_variants(self):
        svc = self.cfdi_service
        self.assertIsNone(svc._pac_recover_file(None, "pdf"))
        self.assertEqual(
            svc._pac_recover_file({"pdf": b"%PDF-bytes"}, "pdf"),
            b"%PDF-bytes",
        )
        # Invalid base64 for XML falls back to UTF-8 encoding of the string.
        self.assertEqual(
            svc._pac_recover_file({"content": "not!!b64"}, "xml"),
            b"not!!b64",
        )
        self.assertIsNone(svc._pac_recover_file({"content": "not!!b64"}, "pdf"))
        self.assertIsNone(svc._pac_recover_file(object(), "pdf"))

    def test_validate_csd_returns_signer(self):
        fake = MagicMock(rfc="EKU9003173C9")
        with patch.object(
            type(self.cfdi_service), "_get_csd_signer", return_value=fake
        ) as mock_get:
            self.assertIs(self.cfdi_service.validate_csd(self.issuer), fake)
        mock_get.assert_called_once_with(self.issuer)

    def test_as_cfdi_valid_xml_without_uuid(self):
        # Parseable XML that CFDI.from_string rejects, with no Timbre UUID.
        xml = (
            b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4">'
            b"<cfdi:Complemento>"
            b'<tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"/>'
            b"</cfdi:Complemento></cfdi:Comprobante>"
        )
        with (
            patch(
                "odoo.addons.l10n_mx_cfdi.models.cfdi_service.CFDI.from_string",
                side_effect=ValueError("incomplete"),
            ),
            self.assertRaises(UserError) as err,
        ):
            self.cfdi_service._as_cfdi(xml)
        self.assertIn("missing UUID", str(err.exception))

    def test_create_cfdi_surfaces_pac_message(self):
        from satcfdi.exceptions import ResponseError

        mock_pac = MagicMock()
        mock_pac.issue.side_effect = ResponseError(
            {
                "status": "error",
                "message": "Token inválido para ambiente de pruebas",
            }
        )
        with (
            patch.object(type(self.cfdi_service), "_get_pac", return_value=mock_pac),
            mute_logger("odoo.addons.l10n_mx_cfdi.models.cfdi_service"),
            self.assertRaises(UserError) as err,
        ):
            self.cfdi_service.create_cfdi(MagicMock(), issuer=self.issuer)
        self.assertIn("Token inválido", str(err.exception))
        self.assertNotIn("<Response", str(err.exception))

    def test_dump_pac_payload_and_model_state_fallbacks(self):
        svc = self.cfdi_service
        self.assertIsNone(svc._dump_pac_payload(None))
        self.assertIsNone(svc._dump_pac_payload("x"))
        self.assertIsNone(svc._dump_pac_payload({}))
        dumped = svc._dump_pac_payload({"a": 1})
        self.assertIn('"a"', dumped)
        # Circular refs / non-serializable → str() fallback.
        circular = {}
        circular["self"] = circular
        self.assertIn("self", svc._dump_pac_payload(circular))
        self.assertIsNone(svc._format_pac_model_state(None))
        self.assertIsNone(svc._format_pac_model_state({}))
        formatted = svc._format_pac_model_state({"field": ["err"]})
        self.assertIn("field", formatted)
        self.assertIn("self", svc._format_pac_model_state(circular))
