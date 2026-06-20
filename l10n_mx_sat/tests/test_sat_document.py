# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from unittest.mock import MagicMock, patch

from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from odoo.addons.l10n_mx_sat.services.sat_helpers import SAFE_XML_PARSER

_PATCH_GET_CLIENT = (
    "odoo.addons.l10n_mx_sat.models.res_company.ResCompany." "l10n_mx_sat_get_client"
)


@tagged("post_install", "-at_install")
class TestSatDocument(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.company.write(
            {
                "vat": "EKU9003173C9",
                "country_id": cls.env.ref("base.mx").id,
                "l10n_mx_sat_fiel_cer": b"ZmFrZQ==",
                "l10n_mx_sat_fiel_key": b"ZmFrZQ==",
                "l10n_mx_sat_fiel_password": "test",
            }
        )
        cls.Document = cls.env["l10n_mx_sat.document"]
        cls.Request = cls.env["l10n_mx_sat.download.request"]

    def _parse_xml(self, xml_bytes):
        return etree.fromstring(xml_bytes, SAFE_XML_PARSER)

    def _create_request(self, **kwargs):
        vals = {
            "company_id": self.company.id,
            "document_kind": "cfdi",
            "direction": "received",
            "request_type": "xml",
            "date_from": "2026-02-01 00:00:00",
            "date_to": "2026-02-28 23:59:59",
            "state": "done",
        }
        vals.update(kwargs)
        return self.Request.create(vals)

    def test_find_by_local_name_with_namespace(self):
        xml = (
            b'<root xmlns:ret="http://www.sat.gob.mx/esquemas/retencion/2">'
            b'<ret:Emisor RfcEmisor="EKU9003173C9"/>'
            b"</root>"
        )
        tree = self._parse_xml(xml)
        nodes = self.Document._find_by_local_name(tree, "Emisor")
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].get("RfcEmisor"), "EKU9003173C9")

    def test_first_attr_returns_first_non_empty(self):
        xml = b'<node Rfc="" RfcEmisor="EKU9003173C9"/>'
        tree = self._parse_xml(xml)
        self.assertEqual(
            self.Document._first_attr(tree, "Rfc", "RfcEmisor"),
            "EKU9003173C9",
        )
        self.assertFalse(self.Document._first_attr(None, "Rfc"))

    def test_get_retention_emisor_rfc_variants(self):
        for attr, value in (
            ("Rfc", "EKU9003173C9"),
            ("RfcEmisor", "EKU9003173C9"),
            ("RFCEmisor", "EKU9003173C9"),
        ):
            xml = f'<root><Emisor {attr}="{value}"/></root>'.encode()
            tree = self._parse_xml(xml)
            self.assertEqual(
                self.Document._get_retention_emisor_rfc(tree),
                "EKU9003173C9",
            )

    def test_get_retention_receptor_rfc_direct_and_nacional(self):
        xml_direct = b'<root><Receptor RfcReceptor="EKU9003173C9"/></root>'
        self.assertEqual(
            self.Document._get_retention_receptor_rfc(self._parse_xml(xml_direct)),
            "EKU9003173C9",
        )
        xml_nacional = (
            b"<root><Receptor><Nacional RfcR='EKU9003173C9'/></Receptor></root>"
        )
        self.assertEqual(
            self.Document._get_retention_receptor_rfc(self._parse_xml(xml_nacional)),
            "EKU9003173C9",
        )

    def test_get_retention_receptor_rfc_extranjero(self):
        xml = (
            b"<root><Receptor><Extranjero "
            b'NumRegIdTrib="EXT123456789"/></Receptor></root>'
        )
        self.assertEqual(
            self.Document._get_retention_receptor_rfc(self._parse_xml(xml)),
            "EXT123456789",
        )

    def test_get_retention_emisor_and_receptor_names(self):
        xml = (
            b"<root>"
            b'<Emisor NomDenRazSocE="Emisor SA"/>'
            b'<Receptor><Nacional NomDenRazSocR="Receptor SA"/></Receptor>'
            b"</root>"
        )
        tree = self._parse_xml(xml)
        self.assertEqual(
            self.Document._get_retention_emisor_name(tree),
            "Emisor SA",
        )
        self.assertEqual(
            self.Document._get_retention_receptor_name(tree),
            "Receptor SA",
        )

    def test_get_retention_total_from_totales_and_root(self):
        xml_totales = b'<root><Totales MontoTotOperacion="250.50"/></root>'
        self.assertEqual(
            self.Document._get_retention_total(self._parse_xml(xml_totales)),
            250.50,
        )
        xml_root = b'<root MontoTotRet="invalid" Total="99.00"/>'
        self.assertEqual(
            self.Document._get_retention_total(self._parse_xml(xml_root)),
            99.0,
        )

    def test_parse_xml_values_retention_stamp_date(self):
        xml = (
            b"<Retenciones FechaExp='2026-01-10T08:00:00'>"
            b'<Emisor Rfc="EKU9003173C9"/>'
            b'<Receptor RfcReceptor="AAA010101AAA"/>'
            b"<Complemento><TimbreFiscalDigital "
            b'FechaTimbrado="2026-01-10T08:05:00"/></Complemento>'
            b"</Retenciones>"
        )
        tree = self._parse_xml(xml)
        vals = self.Document._parse_xml_values(tree, "retention")
        self.assertEqual(vals["issuer_rfc"], "EKU9003173C9")
        self.assertTrue(vals["stamp_date"])

    def test_validate_xml_company_cfdi_received_valid_and_invalid(self):
        request = self._create_request(document_kind="cfdi", direction="received")
        valid = self._parse_xml(
            b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4">'
            b'<cfdi:Receptor Rfc="EKU9003173C9"/>'
            b"</cfdi:Comprobante>"
        )
        invalid = self._parse_xml(
            b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4">'
            b'<cfdi:Receptor Rfc="AAA010101AAA"/>'
            b"</cfdi:Comprobante>"
        )
        self.assertTrue(
            self.Document._validate_xml_company(valid, self.company, request)
        )
        self.assertFalse(
            self.Document._validate_xml_company(invalid, self.company, request)
        )

    def test_validate_xml_company_cfdi_issued(self):
        request = self._create_request(document_kind="cfdi", direction="issued")
        valid = self._parse_xml(
            b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4">'
            b'<cfdi:Emisor Rfc="EKU9003173C9"/>'
            b"</cfdi:Comprobante>"
        )
        self.assertTrue(
            self.Document._validate_xml_company(valid, self.company, request)
        )

    def test_validate_xml_company_retention_issued_and_received(self):
        issued_req = self._create_request(document_kind="retention", direction="issued")
        received_req = self._create_request(
            document_kind="retention", direction="received"
        )
        issued_xml = self._parse_xml(b"<root><Emisor Rfc='EKU9003173C9'/></root>")
        received_xml = self._parse_xml(
            b"<root><Receptor RfcReceptor='EKU9003173C9'/></root>"
        )
        self.assertTrue(
            self.Document._validate_xml_company(issued_xml, self.company, issued_req)
        )
        self.assertTrue(
            self.Document._validate_xml_company(
                received_xml, self.company, received_req
            )
        )

    def test_get_company_rfc_falls_back_to_fiel(self):
        self.company.vat = False
        client = MagicMock()
        client.rfc = "RFCFIEL123"
        with patch(_PATCH_GET_CLIENT, return_value=client):
            self.assertEqual(
                self.Document._get_company_rfc(self.company),
                "RFCFIEL123",
            )

    def test_validate_xml_company_retention_without_company_rfc(self):
        self.company.write(
            {
                "vat": False,
                "l10n_mx_sat_fiel_cer": False,
                "l10n_mx_sat_fiel_key": False,
                "l10n_mx_sat_fiel_password": False,
            }
        )
        request = self._create_request(document_kind="retention", direction="issued")
        tree = self._parse_xml(b"<root><Emisor Rfc='AAA010101AAA'/></root>")
        self.assertTrue(
            self.Document._validate_xml_company(tree, self.company, request)
        )

    @mute_logger("odoo.addons.l10n_mx_sat.models.l10n_mx_sat_document")
    def test_upsert_from_xml_skips_wrong_company(self):
        request = self._create_request(document_kind="cfdi", direction="received")
        xml_bytes = (
            b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4">'
            b'<cfdi:Receptor Rfc="AAA010101AAA"/>'
            b"<cfdi:Complemento>"
            b"<tfd:TimbreFiscalDigital "
            b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
            b'UUID="SKIP-UUID-1234"/>'
            b"</cfdi:Complemento></cfdi:Comprobante>"
        )
        tree = self._parse_xml(xml_bytes)
        doc = self.Document._upsert_from_xml(tree, xml_bytes, self.company, request)
        self.assertFalse(doc)

    def test_action_download_xml_without_attachment(self):
        doc = self.Document._sat_create(
            [
                {
                    "company_id": self.company.id,
                    "uuid": "NO-ATTACH-UUID",
                    "document_kind": "cfdi",
                    "direction": "received",
                }
            ]
        )
        self.assertFalse(doc.action_download_xml())

    def test_upsert_from_xml_creates_attachment(self):
        request = self._create_request(document_kind="cfdi", direction="received")
        uuid = "UPSERT-UUID-12345678901234567890123456789012"
        xml_bytes = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" '
            b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" Total="50.00">'
            b'<cfdi:Emisor Rfc="AAA010101AAA" Nombre="Emisor"/>'
            b'<cfdi:Receptor Rfc="EKU9003173C9" Nombre="Receptor"/>'
            b"<cfdi:Complemento>"
            b'<tfd:TimbreFiscalDigital UUID="' + uuid.encode() + b'"/>'
            b"</cfdi:Complemento></cfdi:Comprobante>"
        )
        tree = self._parse_xml(xml_bytes)
        doc = self.Document._upsert_from_xml(tree, xml_bytes, self.company, request)
        self.assertTrue(doc)
        self.assertTrue(doc.attachment_id)
        action = doc.action_download_xml()
        self.assertIn("/web/content/", action["url"])

    def test_extract_uuid_from_folio_fiscal(self):
        xml = b'<root FolioFiscal="folio-uuid-123"/>'
        tree = self._parse_xml(xml)
        self.assertEqual(
            self.Document._extract_uuid(tree),
            "FOLIO-UUID-123",
        )
