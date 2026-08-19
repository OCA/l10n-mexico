import base64
import json
from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests.common import TransactionCase, mute_logger

from odoo.addons.l10n_mx_cfdi.services import cfdi_normalize

SAMPLE_STAMPED_XML = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" '
    b'Version="4.0" Total="100.00" NoCertificado="CERT123" '
    b'Fecha="2024-01-01T12:00:00" Sello="ABC">'
    b"<cfdi:Complemento>"
    b"<tfd:TimbreFiscalDigital "
    b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
    b'UUID="11111111-1111-1111-1111-111111111111" '
    b'SelloSAT="sat-sign" NoCertificadoSAT="SATCERT" '
    b'RfcProvCertif="RFC123456" FechaTimbrado="2024-01-01T13:00:00"/>'
    b"</cfdi:Complemento></cfdi:Comprobante>"
)


class TestCFDINormalize(TransactionCase):
    def test_extract_stamp_meta_from_xml_bytes(self):
        meta = cfdi_normalize._extract_stamp_meta_from_xml_bytes(SAMPLE_STAMPED_XML)
        self.assertEqual(
            meta["Complement"]["TaxStamp"]["Uuid"],
            "11111111-1111-1111-1111-111111111111",
        )
        self.assertEqual(meta["Total"], "100.00")
        self.assertEqual(meta["CertNumber"], "CERT123")

    def test_extract_stamp_meta_taxes(self):
        cfdi = {
            "Fecha": "2024-01-01T12:00:00",
            "NoCertificado": "1",
            "Total": "116",
            "Sello": "ABC",
            "Impuestos": {
                "Traslados": [
                    {
                        "Impuesto": "002",
                        "TasaOCuota": "0.160000",
                        "Base": "100",
                        "Importe": "16",
                    }
                ],
                "Retenciones": [
                    {
                        "Impuesto": "001",
                        "TasaOCuota": "0.100000",
                        "Base": "100",
                        "Importe": "10",
                    }
                ],
            },
            "Complemento": {
                "TimbreFiscalDigital": {
                    "UUID": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "SelloSAT": "sat",
                    "NoCertificadoSAT": "2",
                    "RfcProvCertif": "RFC",
                    "FechaTimbrado": "2024-01-01T13:00:00",
                }
            },
        }
        meta = cfdi_normalize.extract_stamp_meta(cfdi)
        self.assertEqual(len(meta["Taxes"]), 2)
        self.assertFalse(meta["Taxes"][0]["IsRetention"])
        self.assertTrue(meta["Taxes"][1]["IsRetention"])
        self.assertEqual(meta["Taxes"][0]["Name"], "IVA")
        self.assertEqual(meta["Taxes"][1]["Name"], "ISR")

    def test_resolve_cadena_original_calls_method(self):
        class FakeCFDI(dict):
            def cadena_original(self):
                return "||1.1|cadena||"

        cfdi = FakeCFDI(
            {
                "Fecha": "2024-01-01T12:00:00",
                "NoCertificado": "1",
                "Total": "100",
                "Sello": "ABC",
                "Complemento": {
                    "TimbreFiscalDigital": {
                        "UUID": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                        "SelloSAT": "sat",
                        "NoCertificadoSAT": "2",
                        "RfcProvCertif": "RFC",
                        "FechaTimbrado": "2024-01-01T13:00:00",
                    }
                },
            }
        )
        meta = cfdi_normalize.extract_stamp_meta(cfdi)
        self.assertEqual(meta["OriginalString"], "||1.1|cadena||")
        # Must remain JSON-serializable (regression: method objects broke publish)
        json.dumps(meta)

    def test_resolve_cadena_original_method_raises(self):
        class BoomCFDI(dict):
            def cadena_original(self):
                raise RuntimeError("cannot build cadena")

        cfdi = BoomCFDI(
            {
                "Fecha": "2024-01-01T12:00:00",
                "NoCertificado": "1",
                "Total": "10",
                "Sello": "ABC",
                "Complemento": {"TimbreFiscalDigital": {"UUID": "u"}},
            }
        )
        meta = cfdi_normalize.extract_stamp_meta(cfdi)
        self.assertEqual(meta["OriginalString"], "")

    def test_tax_name_mapping(self):
        self.assertEqual(cfdi_normalize._tax_name("001"), "ISR")
        self.assertEqual(cfdi_normalize._tax_name("002"), "IVA")
        self.assertEqual(cfdi_normalize._tax_name("003"), "IEPS")
        self.assertEqual(cfdi_normalize._tax_name("999"), "999")
        self.assertEqual(cfdi_normalize._tax_name(None), "")

    def test_normalize_pac_document_happy_path(self):
        document = SimpleNamespace(
            xml=SAMPLE_STAMPED_XML,
            document_id="doc-1",
            pdf=None,
        )
        result = cfdi_normalize.normalize_pac_document(document)
        self.assertEqual(result["status"], "published")
        self.assertEqual(result["uuid"], "11111111-1111-1111-1111-111111111111")
        self.assertEqual(result["xml"], SAMPLE_STAMPED_XML)

    def test_normalize_pac_document_calls_extract_stamp_meta(self):
        document = SimpleNamespace(
            xml=SAMPLE_STAMPED_XML,
            document_id="doc-meta",
            pdf=None,
        )
        fake_cfdi = SimpleNamespace()
        stamp_meta = {
            "Complement": {"TaxStamp": {"Uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}}
        }
        with (
            patch.object(
                cfdi_normalize.CFDI, "from_string", return_value=fake_cfdi
            ) as mock_from,
            patch.object(
                cfdi_normalize, "extract_stamp_meta", return_value=stamp_meta
            ) as mock_extract,
        ):
            result = cfdi_normalize.normalize_pac_document(document)
        mock_from.assert_called_once_with(SAMPLE_STAMPED_XML)
        mock_extract.assert_called_once_with(fake_cfdi)
        self.assertEqual(result["uuid"], "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

    @mute_logger("odoo.addons.l10n_mx_cfdi.services.cfdi_normalize")
    def test_normalize_pac_document_falls_back_to_lxml(self):
        document = SimpleNamespace(
            xml=SAMPLE_STAMPED_XML,
            document_id="doc-fallback",
            pdf=None,
        )
        with patch.object(
            cfdi_normalize.CFDI, "from_string", side_effect=ValueError("bad")
        ):
            result = cfdi_normalize.normalize_pac_document(document)
        self.assertEqual(result["uuid"], "11111111-1111-1111-1111-111111111111")
        self.assertTrue(result["stamp_meta"])

    def test_normalize_pac_document_empty_xml_uses_document_id(self):
        document = SimpleNamespace(xml=b"", document_id="fallback-uuid", pdf=None)
        result = cfdi_normalize.normalize_pac_document(document)
        self.assertEqual(result["uuid"], "fallback-uuid")
        self.assertEqual(result["tracking_id"], "fallback-uuid")

    @mute_logger("odoo.addons.l10n_mx_cfdi.services.cfdi_normalize")
    def test_normalize_pac_document_unparseable_xml(self):
        document = SimpleNamespace(
            xml=b"<not-valid", document_id="broken-doc", pdf=None
        )
        with patch.object(
            cfdi_normalize.CFDI, "from_string", side_effect=ValueError("bad")
        ):
            result = cfdi_normalize.normalize_pac_document(document)
        self.assertEqual(result["uuid"], "broken-doc")
        self.assertEqual(result["stamp_meta"], {})

    def test_decode_binary_field_variants(self):
        self.assertEqual(cfdi_normalize.decode_binary_field(None), b"")
        raw = b"hello"
        encoded = base64.b64encode(raw)
        self.assertEqual(cfdi_normalize.decode_binary_field(encoded), raw)
        self.assertEqual(cfdi_normalize.decode_binary_field(encoded.decode()), raw)
        self.assertEqual(
            cfdi_normalize.decode_binary_field(b"not-b64!!!"), b"not-b64!!!"
        )
        self.assertEqual(cfdi_normalize.decode_binary_field(bytearray(b"abc")), b"abc")

    def test_extract_stamp_meta_without_timbre(self):
        xml = (
            b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" '
            b'Total="1" Fecha="2024-01-01T00:00:00" NoCertificado="1"/>'
        )
        meta = cfdi_normalize._extract_stamp_meta_from_xml_bytes(xml)
        self.assertEqual(meta["Complement"]["TaxStamp"]["Uuid"], "")
        self.assertEqual(meta["Total"], "1")
