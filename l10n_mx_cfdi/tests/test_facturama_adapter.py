from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase

from odoo.addons.l10n_mx_cfdi.services import facturama_adapter


class TestFacturamaAdapter(TransactionCase):
    def test_enrich_sets_nameid_for_egreso_and_pago(self):
        cfdi = MagicMock()
        cfdi.get.return_value = None
        egreso = facturama_adapter.enrich_facturama_payload(cfdi, {"CfdiType": "E"})
        self.assertEqual(egreso["NameId"], "2")
        pago = facturama_adapter.enrich_facturama_payload(cfdi, {"CfdiType": "P"})
        self.assertEqual(pago["NameId"], "14")

    def test_enrich_preserves_existing_nameid(self):
        cfdi = MagicMock()
        cfdi.get.return_value = None
        payload = {"CfdiType": "T", "NameId": "36"}
        facturama_adapter.enrich_facturama_payload(cfdi, payload)
        self.assertEqual(payload["NameId"], "36")

    def test_enrich_pago_adds_exportation_and_nameid(self):
        cfdi = MagicMock()
        payload = {"CfdiType": "P", "Complemento": {"Payments": []}}
        facturama_adapter.enrich_facturama_payload(cfdi, payload)
        self.assertEqual(payload["NameId"], "14")
        self.assertEqual(payload["Exportation"], "01")

    def test_enrich_pago_strips_mxn_exchange_rate_and_normalizes_form(self):
        cfdi = MagicMock()
        cfdi.get.return_value = None
        payload = {
            "CfdiType": "P",
            "Date": "2026-07-31 12:00:00",
            "Complemento": {
                "Payments": [
                    {
                        "PaymentForm": "03 - Transferencia electrónica de fondos",
                        "Currency": "MXN",
                        "ExchangeRate": 1.0,
                        "Amount": 100.0,
                        "RelatedDocuments": [
                            {
                                "Uuid": "A" * 36,
                                "Currency": "MXN",
                                "AmountPaid": 100.0,
                                "PreviousBalanceAmount": 100.0,
                                "EquivalenceDocRel": 1.0,
                                "ImpSaldoInsoluto": 0.0,
                            }
                        ],
                    },
                    {
                        "PaymentForm": "False",
                        "Currency": "USD",
                        "ExchangeRate": 17.5,
                        "Amount": 10.0,
                    },
                ]
            },
        }
        facturama_adapter.enrich_facturama_payload(cfdi, payload)
        mxn = payload["Complemento"]["Payments"][0]
        usd = payload["Complemento"]["Payments"][1]
        self.assertEqual(mxn["PaymentForm"], "03")
        self.assertNotIn("ExchangeRate", mxn)
        self.assertEqual(usd["ExchangeRate"], 17.5)
        self.assertEqual(usd["PaymentForm"], "False")
        # Same-currency: drop EquivalenceDocRel / ImpSaldoInsoluto; Amount==Paid.
        doc = mxn["RelatedDocuments"][0]
        self.assertNotIn("EquivalenceDocRel", doc)
        self.assertNotIn("ImpSaldoInsoluto", doc)
        self.assertEqual(mxn["Amount"], 100.0)
        self.assertEqual(doc["AmountPaid"], 100.0)

    def test_enrich_pago_aligns_amount_with_imp_pagado_fx(self):
        """sum(AmountPaid/EquivalenceDocRel) must match Amount (SAT limits)."""
        cfdi = MagicMock()
        cfdi.get.return_value = None
        payload = {
            "CfdiType": "P",
            "Date": "2026-08-10 12:00:00",
            "Complemento": {
                "Payments": [
                    {
                        "PaymentForm": "03",
                        "Currency": "USD",
                        "ExchangeRate": 20.0,
                        "Amount": 999.0,  # wrong on purpose; enrich realigns
                        "RelatedDocuments": [
                            {
                                "Uuid": "B" * 36,
                                "Currency": "MXN",
                                "AmountPaid": 2000.0,
                                "PreviousBalanceAmount": 2000.0,
                                "EquivalenceDocRel": 20.0,
                            }
                        ],
                    }
                ]
            },
        }
        facturama_adapter.enrich_facturama_payload(cfdi, payload)
        payment = payload["Complemento"]["Payments"][0]
        self.assertEqual(payment["Amount"], 100.0)
        self.assertEqual(payment["RelatedDocuments"][0]["EquivalenceDocRel"], 20.0)

    def test_enrich_foreign_trade_renames_recipient_addresses(self):
        cfdi = MagicMock()
        cfdi.get.return_value = None
        addr = {
            "Street": "Main",
            "State": "CA",
            "Country": "USA",
            "ZipCode": "90210",
        }
        payload = {
            "CfdiType": "I",
            "Date": "2026-07-31 12:00:00",
            "Complemento": {
                "ForeignTrade": {
                    "Recipient": [
                        {"Name": "Warehouse", "Address": [addr]},
                    ]
                }
            },
        }
        facturama_adapter.enrich_facturama_payload(cfdi, payload)
        recipient = payload["Complemento"]["ForeignTrade"]["Recipient"][0]
        self.assertIn("Addresses", recipient)
        self.assertNotIn("Address", recipient)
        self.assertEqual(recipient["Addresses"][0]["Street"], "Main")

    def test_enrich_foreign_trade_builds_recipient_from_receiver(self):
        cfdi = MagicMock()
        cfdi.get.return_value = None
        addr = {"Street": "Dock", "Country": "USA", "State": "TX", "ZipCode": "75001"}
        payload = {
            "CfdiType": "I",
            "Date": "2026-07-31 12:00:00",
            "Complemento": {
                "ForeignTrade": {"Receiver": {"Address": addr, "NumRegIdTrib": "1"}}
            },
        }
        facturama_adapter.enrich_facturama_payload(cfdi, payload)
        recipients = payload["Complemento"]["ForeignTrade"]["Recipient"]
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0]["Addresses"][0]["Street"], "Dock")
        self.assertEqual(recipients[0]["NumRegIdTrib"], "1")

    def test_enrich_cartaporte_omits_date_for_facturama(self):
        """Carta Porte: null Date lets Facturama assign local now from CP."""
        cfdi = MagicMock()
        cfdi.get.return_value = "26015"
        payload = {
            "CfdiType": "T",
            "Date": "2020-01-01 00:00:00",
            "Complemento": {"CartaPorte31": {"TranspInternac": "No"}},
        }
        facturama_adapter.enrich_facturama_payload(cfdi, payload)
        self.assertIsNone(payload["Date"])

    def test_enrich_refreshes_future_date(self):
        cfdi = MagicMock()
        cfdi.get.return_value = "26015"
        payload = {
            "CfdiType": "I",
            "Date": "2099-01-01 00:00:00",
            "Items": [],
        }
        facturama_adapter.enrich_facturama_payload(cfdi, payload)
        self.assertNotEqual(payload["Date"], "2099-01-01 00:00:00")
        self.assertTrue(payload["Date"].startswith("2026-"))

    def test_enrich_refreshes_stale_date(self):
        cfdi = MagicMock()
        cfdi.get.return_value = "26015"
        payload = {
            "CfdiType": "I",
            "Date": "2020-01-01 00:00:00",
            "Items": [],
        }
        facturama_adapter.enrich_facturama_payload(cfdi, payload)
        self.assertNotEqual(payload["Date"], "2020-01-01 00:00:00")
        self.assertTrue(payload["Date"].startswith("2026-"))

    def test_enrich_traslado_cartaporte_forces_nameid_36(self):
        cfdi = MagicMock()
        payload = {
            "CfdiType": "T",
            "NameId": "1",
            "Complemento": {"CartaPorte31": {"TranspInternac": "No"}},
        }
        facturama_adapter.enrich_facturama_payload(cfdi, payload)
        self.assertEqual(payload["NameId"], "36")

    def test_enrich_injects_numeros_pedimento_from_informacion_aduanera(self):
        from satcfdi.cfdi import CFDI

        # Minimal CFDI-like mapping with InformacionAduanera on the concept
        concepto = {
            "ClaveProdServ": "01010101",
            # Single spaces (Odoo pedimento storage) → SAT double spaces.
            "InformacionAduanera": ["24 48 3807 0001234"],
        }
        cfdi = CFDI(
            {
                "TipoDeComprobante": "I",
                "Conceptos": [concepto],
            }
        )
        payload = {
            "CfdiType": "I",
            "Items": [{"ProductCode": "01010101", "Description": "x"}],
        }
        facturama_adapter.enrich_facturama_payload(cfdi, payload)
        self.assertEqual(
            payload["Items"][0]["NumerosPedimento"],
            ["24  48  3807  0001234"],
        )

    def test_enrich_drops_pedimentos_when_foreign_trade_present(self):
        """CFDI40195: no concept pedimentos together with ComercioExterior."""
        from satcfdi.cfdi import CFDI

        cfdi = CFDI(
            {
                "TipoDeComprobante": "I",
                "Conceptos": [
                    {
                        "ClaveProdServ": "01010101",
                        "InformacionAduanera": ["24  48  3807  0001234"],
                    }
                ],
            }
        )
        payload = {
            "CfdiType": "I",
            "Items": [
                {
                    "ProductCode": "01010101",
                    "Description": "x",
                    "NumerosPedimento": ["24  48  3807  0001234"],
                }
            ],
            "Complemento": {
                "ForeignTrade": {
                    "Recipient": [{"Addresses": [{"Street": "A", "Country": "USA"}]}]
                }
            },
        }
        facturama_adapter.enrich_facturama_payload(cfdi, payload)
        self.assertNotIn("NumerosPedimento", payload["Items"][0])
        self.assertEqual(payload["NameId"], "26")

    def test_bind_enriched_issue_posts_enriched_payload(self):
        pac = SimpleNamespace(
            _allow_foreign_trade=False,
            _issue_path="api-lite/3/cfdis",
            _request=MagicMock(return_value={"Id": "doc-1"}),
            _download_file=MagicMock(return_value=b"<xml/>"),
        )
        cfdi = MagicMock()
        with patch(
            "satcfdi.pacs.facturama.cfdi_to_facturama_payload",
            return_value={"CfdiType": "E", "Items": []},
        ) as mock_map:
            facturama_adapter.bind_enriched_issue(pac)
            from satcfdi.pacs import Accept

            doc = pac.issue(cfdi, accept=Accept.XML)
        mock_map.assert_called_once()
        posted = pac._request.call_args.kwargs["json"]
        self.assertEqual(posted["NameId"], "2")
        self.assertEqual(doc.document_id, "doc-1")

    def test_bind_enriched_cancel_preserves_status_and_message(self):
        import base64

        acuse_xml = b"<Acuse/>"
        pac = SimpleNamespace(
            _cancel_path_prefix="api-lite/cfdis",
            _request=MagicMock(
                return_value={
                    "Status": "canceled",
                    "Message": "Cancelado sin Aceptacion",
                    "AcuseXmlBase64": base64.b64encode(acuse_xml).decode(),
                }
            ),
            find_id_by_uuid=MagicMock(return_value="fallback-id"),
        )
        cfdi = MagicMock()
        facturama_adapter.bind_enriched_cancel(pac)
        from satcfdi.pacs import CancelReason

        ack = pac.cancel(
            cfdi,
            CancelReason.COMPROBANTE_EMITIDO_CON_ERRORES_SIN_RELACION,
            document_id="facturama-doc",
        )
        self.assertEqual(
            ack.code,
            {"Status": "canceled", "Message": "Cancelado sin Aceptacion"},
        )
        self.assertEqual(ack.acuse, acuse_xml)
        self.assertEqual(
            pac._request.call_args.args[:2],
            ("delete", "api-lite/cfdis/facturama-doc"),
        )

    def test_bind_enriched_cancel_empty_body(self):
        pac = SimpleNamespace(
            _cancel_path_prefix="api-lite/cfdis",
            _download_type="issuedLite",
            _request=MagicMock(return_value=None),
            find_id_by_uuid=MagicMock(return_value="id-1"),
        )
        facturama_adapter.bind_enriched_cancel(pac)
        from satcfdi.pacs import CancelReason

        ack = pac.cancel(
            MagicMock(),
            CancelReason.COMPROBANTE_EMITIDO_CON_ERRORES_SIN_RELACION,
            document_id="id-1",
        )
        self.assertEqual(ack.code, "cancelled")
        self.assertIsNone(ack.acuse)

    def test_bind_enriched_cancel_fetches_acuse_when_missing(self):
        import base64

        acuse_xml = b"<AcuseCancelacion/>"
        pac = SimpleNamespace(
            _cancel_path_prefix="api-lite/cfdis",
            _download_type="issuedLite",
            _request=MagicMock(
                side_effect=[
                    {
                        "Status": "canceled",
                        "Message": "Cancelado sin Aceptacion",
                        "AcuseXmlBase64": None,
                    },
                    {
                        "ContentEncoding": "base64",
                        "ContentType": "xml",
                        "Content": base64.urlsafe_b64encode(acuse_xml).decode(),
                    },
                ]
            ),
            find_id_by_uuid=MagicMock(return_value="id-acuse"),
        )
        facturama_adapter.bind_enriched_cancel(pac)
        from satcfdi.pacs import CancelReason

        ack = pac.cancel(
            MagicMock(),
            CancelReason.COMPROBANTE_EMITIDO_CON_ERRORES_SIN_RELACION,
            document_id="id-acuse",
        )
        self.assertEqual(ack.acuse, acuse_xml)
        self.assertEqual(pac._request.call_count, 2)
        self.assertEqual(
            pac._request.call_args_list[1].args[:2],
            ("get", "acuse/xml/issuedLite/id-acuse"),
        )

    def test_enrich_returns_non_dict_payload_unchanged(self):
        self.assertEqual(
            facturama_adapter.enrich_facturama_payload(MagicMock(), "raw"),
            "raw",
        )

    def test_enrich_skips_items_that_already_have_pedimentos(self):
        from satcfdi.cfdi import CFDI

        cfdi = CFDI(
            {
                "TipoDeComprobante": "I",
                "Conceptos": [
                    {"InformacionAduanera": ["24  48  3807  0009999"]},
                    {"InformacionAduanera": ["24  48  3807  0001111"]},
                ],
            }
        )
        payload = {
            "CfdiType": "I",
            "Items": [
                "not-a-dict",
                {"NumerosPedimento": ["kept"], "Description": "x"},
            ],
        }
        facturama_adapter.enrich_facturama_payload(cfdi, payload)
        self.assertEqual(payload["Items"][1]["NumerosPedimento"], ["kept"])

    def test_pedimentos_from_dict_and_other_nodes(self):
        self.assertEqual(
            facturama_adapter._pedimentos_from_concepto({}),
            [],
        )
        self.assertEqual(
            facturama_adapter._pedimentos_from_concepto(
                {
                    "InformacionAduanera": [
                        {"NumeroPedimento": "24  48  3807  0002222"},
                        12345,
                    ]
                }
            ),
            ["24  48  3807  0002222", "12345"],
        )

    def test_bind_enriched_issue_downloads_pdf(self):
        pac = SimpleNamespace(
            _allow_foreign_trade=False,
            _issue_path="api-lite/3/cfdis",
            _request=MagicMock(return_value={"Id": "doc-pdf"}),
            _download_file=MagicMock(side_effect=[b"<xml/>", b"%PDF"]),
        )
        with patch(
            "satcfdi.pacs.facturama.cfdi_to_facturama_payload",
            return_value={"CfdiType": "I", "Items": []},
        ):
            facturama_adapter.bind_enriched_issue(pac)
            from satcfdi.pacs import Accept

            doc = pac.issue(MagicMock(), accept=Accept.XML | Accept.PDF)
        self.assertEqual(doc.pdf, b"%PDF")
        self.assertEqual(
            [c.args for c in pac._download_file.call_args_list],
            [("doc-pdf", "xml"), ("doc-pdf", "pdf")],
        )

    def test_bind_enriched_cancel_uuid_lookup_replacement_and_acuse_variants(self):
        from satcfdi.pacs import CancelReason

        cfdi = {
            "Complemento": {
                "TimbreFiscalDigital": {"UUID": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}
            }
        }

        # Resolve Facturama id from UUID, send replacement + issued type,
        # and accept raw bytes acuse.
        pac = SimpleNamespace(
            _cancel_path_prefix="api/Cfdi",
            _request=MagicMock(
                return_value={
                    "Status": "canceled",
                    "Message": "ok",
                    "Acuse": b"<AcuseBytes/>",
                }
            ),
            find_id_by_uuid=MagicMock(return_value="from-uuid"),
        )
        facturama_adapter.bind_enriched_cancel(pac)
        ack = pac.cancel(
            cfdi,
            CancelReason.COMPROBANTE_EMITIDO_CON_ERRORES_CON_RELACION,
            substitution_id="repl-uuid",
        )
        pac.find_id_by_uuid.assert_called_once_with(
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        )
        params = pac._request.call_args.kwargs["params"]
        self.assertEqual(params["uuidReplacement"], "repl-uuid")
        self.assertEqual(params["type"], "issued")
        self.assertIn("motive", params)
        self.assertEqual(ack.acuse, b"<AcuseBytes/>")

        # Invalid base64 falls back to encoding the raw string.
        pac._request.return_value = {
            "Status": "canceled",
            "Message": "ok",
            "AcuseXmlBase64": "A",  # Incorrect padding -> binascii.Error
        }
        ack = pac.cancel(
            cfdi,
            CancelReason.COMPROBANTE_EMITIDO_CON_ERRORES_SIN_RELACION,
            document_id="id-2",
        )
        self.assertEqual(ack.acuse, b"A")

        # Dict without Status/Message still reports cancelled.
        pac._request.return_value = {"AcuseXmlBase64": None}
        ack = pac.cancel(
            cfdi,
            CancelReason.COMPROBANTE_EMITIDO_CON_ERRORES_SIN_RELACION,
            document_id="id-3",
        )
        self.assertEqual(ack.code, "cancelled")

    def test_cfdi_has_comercio_exterior_detects_complement(self):
        from satcfdi.cfdi import CFDI

        plain = CFDI({"TipoDeComprobante": "I"})
        self.assertFalse(facturama_adapter.cfdi_has_comercio_exterior(plain))
        self.assertFalse(facturama_adapter.cfdi_has_comercio_exterior(MagicMock()))

        with_cce = CFDI(
            {
                "TipoDeComprobante": "I",
                "Complemento": {
                    "ComercioExterior": {
                        "Version": "2.0",
                        "ClaveDePedimento": "A1",
                    }
                },
            }
        )
        self.assertTrue(facturama_adapter.cfdi_has_comercio_exterior(with_cce))

    def test_multiemisor_issue_raises_on_cce_without_web(self):
        from satcfdi.cfdi import CFDI
        from satcfdi.pacs import Accept

        pac = SimpleNamespace(
            _allow_foreign_trade=False,
            _issue_path="api-lite/3/cfdis",
            _request=MagicMock(return_value={"Id": "doc-1"}),
            _download_file=MagicMock(return_value=b"<xml/>"),
        )
        cfdi = CFDI(
            {
                "TipoDeComprobante": "I",
                "Complemento": {"ComercioExterior": {"Version": "2.0"}},
            }
        )
        facturama_adapter.bind_enriched_issue(pac)
        with self.assertRaises(NotImplementedError) as err:
            pac.issue(cfdi, accept=Accept.XML)
        self.assertIn("Comercio Exterior", str(err.exception))

    def test_ensure_facturama_switches_to_web_for_cce(self):
        from satcfdi.cfdi import CFDI

        multi = SimpleNamespace(_allow_foreign_trade=False)
        service = SimpleNamespace(
            user="u",
            password="p",
            sandbox_mode=True,
        )
        cfdi = CFDI(
            {
                "TipoDeComprobante": "I",
                "Complemento": {"ComercioExterior": {"Version": "2.0"}},
            }
        )
        with patch.object(
            facturama_adapter,
            "build_facturama_web",
            return_value=SimpleNamespace(_allow_foreign_trade=True, web=True),
        ) as mock_web:
            pac = facturama_adapter.ensure_facturama_pac_for_cfdi(multi, service, cfdi)
        mock_web.assert_called_once_with(service)
        self.assertTrue(getattr(pac, "web", False))

        # Non-CCE keeps Multiemisor
        plain = CFDI({"TipoDeComprobante": "I"})
        same = facturama_adapter.ensure_facturama_pac_for_cfdi(multi, service, plain)
        self.assertIs(same, multi)

        # Already Web keeps same pac
        web = SimpleNamespace(_allow_foreign_trade=True)
        self.assertIs(
            facturama_adapter.ensure_facturama_pac_for_cfdi(web, service, cfdi),
            web,
        )

    def test_cfdi_has_comercio_exterior_tag_and_type_name(self):
        class ComercioExteriorNode(dict):
            tag = "{http://www.sat.gob.mx/ComercioExterior20}ComercioExterior"

        class TaggedOnly(dict):
            """Name does not include ComercioExterior; detection uses .tag."""

            tag = "{http://www.sat.gob.mx/ComercioExterior20}ComercioExterior"

        class WeirdComplement(list):
            pass

        class BoomGet(dict):
            def get(self, key, default=None):
                raise RuntimeError("boom get")

        self.assertFalse(facturama_adapter.cfdi_has_comercio_exterior(None))

        class Boom:
            def get(self, key):
                raise RuntimeError("boom")

        self.assertFalse(facturama_adapter.cfdi_has_comercio_exterior(Boom()))

        tagged = SimpleNamespace(get=lambda key: TaggedOnly())
        self.assertTrue(facturama_adapter.cfdi_has_comercio_exterior(tagged))

        named = SimpleNamespace(
            get=lambda key: ComercioExteriorNode({"Version": "2.0"})
        )
        self.assertTrue(facturama_adapter.cfdi_has_comercio_exterior(named))

        # Complemento.get raises → fall through to iterate (empty)
        boom_comp = SimpleNamespace(get=lambda key: BoomGet())
        self.assertFalse(facturama_adapter.cfdi_has_comercio_exterior(boom_comp))

        iterable = SimpleNamespace(
            get=lambda key: WeirdComplement(
                [SimpleNamespace(tag="{ns}ComercioExterior")]
            )
        )
        self.assertTrue(facturama_adapter.cfdi_has_comercio_exterior(iterable))

        # iterate skips mocks, then hits type-name match
        class ComercioExteriorItem:
            pass

        mixed = SimpleNamespace(
            get=lambda key: WeirdComplement([MagicMock(), ComercioExteriorItem()])
        )
        self.assertTrue(facturama_adapter.cfdi_has_comercio_exterior(mixed))

        # Plain empty complement → False
        empty = SimpleNamespace(get=lambda key: WeirdComplement())
        self.assertFalse(facturama_adapter.cfdi_has_comercio_exterior(empty))

        mock_comp = MagicMock()
        holder = SimpleNamespace(get=lambda key: mock_comp)
        self.assertFalse(facturama_adapter.cfdi_has_comercio_exterior(holder))

    def test_build_facturama_web_binds_issue_and_cancel(self):
        service = SimpleNamespace(user="u", password="p", sandbox_mode=False)
        fake_pac = SimpleNamespace(
            _allow_foreign_trade=True,
            _issue_path="api/3/cfdis",
            _cancel_path_prefix="api/Cfdi",
        )
        with patch("satcfdi.pacs.facturama.FacturamaWeb", return_value=fake_pac):
            pac = facturama_adapter.build_facturama_web(service)
        self.assertTrue(callable(pac.issue))
        self.assertTrue(callable(pac.cancel))

    def test_web_issue_allows_comercio_exterior(self):
        from satcfdi.cfdi import CFDI
        from satcfdi.pacs import Accept

        pac = SimpleNamespace(
            _allow_foreign_trade=True,
            _issue_path="api/3/cfdis",
            _request=MagicMock(return_value={"Id": "web-1"}),
            _download_file=MagicMock(return_value=b"<xml/>"),
        )
        cfdi = CFDI(
            {
                "TipoDeComprobante": "I",
                "Complemento": {"ComercioExterior": {"Version": "2.0"}},
            }
        )
        with patch(
            "satcfdi.pacs.facturama.cfdi_to_facturama_payload",
            return_value={"CfdiType": "I", "Items": []},
        ) as mock_map:
            facturama_adapter.bind_enriched_issue(pac)
            doc = pac.issue(cfdi, accept=Accept.XML_PDF)
        self.assertEqual(doc.document_id, "web-1")
        self.assertTrue(mock_map.call_args.kwargs.get("allow_foreign_trade"))
        self.assertEqual(pac._download_file.call_count, 2)

    def test_normalize_payment_form_and_as_decimal_edges(self):
        self.assertIsNone(facturama_adapter._normalize_payment_form(None))
        self.assertIsNone(facturama_adapter._normalize_payment_form(False))
        self.assertIsNone(facturama_adapter._normalize_payment_form("false"))
        self.assertEqual(facturama_adapter._as_decimal(None), Decimal("0"))
        self.assertEqual(facturama_adapter._as_decimal(False), Decimal("0"))
        self.assertEqual(facturama_adapter._as_decimal("12.5"), Decimal("12.5"))

    def test_enrich_payment_skips_non_dicts_and_zero_equivalence(self):
        cfdi = MagicMock()
        cfdi.get.return_value = None
        payload = {
            "CfdiType": "P",
            "Date": "2026-08-10 12:00:00",
            "Complemento": {
                "Payments": [
                    "skip-me",
                    {
                        "PaymentForm": "03",
                        "Currency": "USD",
                        "Amount": 50.0,
                        "RelatedDocuments": [
                            "skip-doc",
                            {
                                "Uuid": "C" * 36,
                                "Currency": "MXN",
                                "AmountPaid": 100.0,
                                "EquivalenceDocRel": 0,
                            },
                        ],
                    },
                ]
            },
        }
        facturama_adapter.enrich_facturama_payload(cfdi, payload)
        payment = payload["Complemento"]["Payments"][1]
        doc = payment["RelatedDocuments"][1]
        # Zero EquivalenceDocRel is treated as 1 (avoid division by zero).
        self.assertEqual(doc["EquivalenceDocRel"], 1.0)
        self.assertEqual(payment["Amount"], 100.0)

    def test_enrich_foreign_trade_recipient_fallbacks(self):
        facturama_adapter._enrich_foreign_trade("not-a-dict")
        # Non-dict recipient entries are skipped; missing Addresses fall back.
        ft = {
            "Receiver": {"Addresses": [{"Street": "A", "Country": "USA"}]},
            "Recipient": [
                "skip",
                {"Name": "Dest"},
                {"Name": "HasAddr", "Address": {"Street": "B", "Country": "USA"}},
            ],
        }
        facturama_adapter._enrich_foreign_trade(ft)
        self.assertEqual(ft["Recipient"][1]["Addresses"][0]["Street"], "A")
        self.assertEqual(ft["Recipient"][2]["Addresses"][0]["Street"], "B")
        # Recipient with no domicilio and no receiver address → leave empty.
        bare = {"Recipient": [{"Name": "X"}]}
        facturama_adapter._enrich_foreign_trade(bare)
        self.assertNotIn("Addresses", bare["Recipient"][0])

    def test_parse_payload_date_and_mexico_now_fallbacks(self):
        aware = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(
            facturama_adapter._parse_payload_date(aware),
            datetime(2026, 8, 10, 12, 0, 0),
        )
        self.assertIsNone(facturama_adapter._parse_payload_date(None))
        self.assertIsNone(facturama_adapter._parse_payload_date("not-a-date"))
        self.assertEqual(
            facturama_adapter._parse_payload_date("2026-08-10"),
            datetime(2026, 8, 10, 0, 0, 0),
        )
        with patch(
            "zoneinfo.ZoneInfo",
            side_effect=Exception("tz missing"),
        ):
            fallback = facturama_adapter._mexico_city_now_naive()
        self.assertIsInstance(fallback, datetime)

        class BoomCfdi:
            def get(self, key):
                raise RuntimeError("boom")

        now = facturama_adapter._mexico_now_naive(BoomCfdi())
        self.assertIsInstance(now, datetime)

    def test_decode_acuse_and_fetch_acuse_fallbacks(self):
        import base64

        self.assertIsNone(facturama_adapter._decode_acuse_content(None))
        self.assertIsNone(facturama_adapter._decode_acuse_content(""))
        self.assertIsNone(facturama_adapter._decode_acuse_content("   "))
        self.assertIsNone(facturama_adapter._decode_acuse_content(12345))
        self.assertEqual(facturama_adapter._decode_acuse_content(b""), None)
        self.assertEqual(facturama_adapter._decode_acuse_content(b"x"), b"x")

        # GET failures then raw bytes success.
        pac = SimpleNamespace(
            _download_type="issuedLite",
            _request=MagicMock(
                side_effect=[
                    RuntimeError("404"),
                    RuntimeError("404"),
                    RuntimeError("404"),
                    b"<AcuseRaw/>",
                ]
            ),
        )
        acuse = facturama_adapter._fetch_facturama_acuse(pac, "id-1")
        self.assertEqual(acuse, b"<AcuseRaw/>")

        # Content present but urlsafe decode fails → keep std decode.
        bad_urlsafe = base64.b64encode(b"<Acuse/>").decode()
        pac._request = MagicMock(
            return_value={"Content": bad_urlsafe, "ContentEncoding": "base64"}
        )
        with patch(
            "base64.urlsafe_b64decode",
            side_effect=Exception("bad urlsafe"),
        ):
            acuse = facturama_adapter._fetch_facturama_acuse(pac, "id-2")
        self.assertEqual(acuse, b"<Acuse/>")

        # Cancel pending: no acuse after GET → surface explanatory Message.
        pac = SimpleNamespace(
            _cancel_path_prefix="api-lite/cfdis",
            _download_type="issuedLite",
            _request=MagicMock(
                side_effect=[
                    {"Status": "canceled", "AcuseXmlBase64": None},
                    RuntimeError("404"),
                    RuntimeError("404"),
                    RuntimeError("404"),
                    RuntimeError("404"),
                ]
            ),
            find_id_by_uuid=MagicMock(return_value="id-pending"),
        )
        facturama_adapter.bind_enriched_cancel(pac)
        from satcfdi.pacs import CancelReason

        ack = pac.cancel(
            MagicMock(),
            CancelReason.COMPROBANTE_EMITIDO_CON_ERRORES_SIN_RELACION,
            document_id="id-pending",
        )
        self.assertIsNone(ack.acuse)
        self.assertEqual(ack.code["Status"], "canceled")
        self.assertIn("no acuse XML", ack.code["Message"])
