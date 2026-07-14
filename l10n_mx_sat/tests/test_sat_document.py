# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from unittest.mock import MagicMock, patch

from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from odoo.addons.l10n_mx_sat.services.sat_helpers import SAFE_XML_PARSER

_PATCH_GET_CLIENT = (
    "odoo.addons.l10n_mx_sat.models.res_company.ResCompany.l10n_mx_sat_get_client"
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
        empty_ext = b"<root><Receptor><Extranjero/></Receptor></root>"
        self.assertFalse(
            self.Document._get_retention_receptor_rfc(self._parse_xml(empty_ext))
        )
        no_ext = b"<root><Receptor/></root>"
        self.assertFalse(
            self.Document._get_retention_receptor_rfc(self._parse_xml(no_ext))
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
        tree_direct = self._parse_xml(
            b"<root>"
            b'<Emisor Nombre="Emisor Direct"/>'
            b'<Receptor Nombre="Receptor Direct"/>'
            b"</root>"
        )
        self.assertEqual(
            self.Document._get_retention_emisor_name(tree_direct), "Emisor Direct"
        )
        self.assertEqual(
            self.Document._get_retention_receptor_name(tree_direct), "Receptor Direct"
        )
        tree_ext = self._parse_xml(
            b'<root><Emisor NomDenRazSocE="Ext Emisor"/><Receptor>'
            b'<Extranjero NomDenRazSocR="Ext Receptor"/>'
            b"</Receptor></root>"
        )
        self.assertEqual(
            self.Document._get_retention_emisor_name(tree_ext), "Ext Emisor"
        )
        self.assertEqual(
            self.Document._get_retention_receptor_name(tree_ext), "Ext Receptor"
        )
        empty = self._parse_xml(b"<root/>")
        self.assertFalse(self.Document._get_retention_emisor_name(empty))
        self.assertFalse(self.Document._get_retention_receptor_name(empty))
        self.assertFalse(self.Document._get_retention_emisor_rfc(empty))
        self.assertFalse(
            self.Document._get_retention_emisor_rfc(
                self._parse_xml(b"<root><Emisor/></root>")
            )
        )
        self.assertFalse(self.Document._get_retention_receptor_rfc(empty))

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
        bad = self._parse_xml(b'<root><Totales MontoTotOperacion="x"/></root>')
        self.assertEqual(self.Document._get_retention_total(bad), 0.0)
        root_attr = self._parse_xml(b'<root MontoTotRet="12.5"/>')
        self.assertEqual(self.Document._get_retention_total(root_attr), 12.5)

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

    def test_update_status_from_validate(self):
        doc = self.Document._sat_create(
            [
                {
                    "company_id": self.company.id,
                    "uuid": "VALIDATE-STATUS-UUID",
                    "document_kind": "cfdi",
                    "direction": "received",
                    "sat_status": "valid",
                }
            ]
        )
        self.Document._update_status_from_validate(doc, {"estado": "Cancelado"})
        self.assertEqual(doc.sat_status, "cancelled")
        self.Document._update_status_from_validate(doc, {"estado": ""})
        self.assertEqual(doc.sat_status, "cancelled")
        self.Document._update_status_from_validate(doc, {"estado": "En Proceso"})
        self.assertEqual(doc.sat_status, "in_progress")
        self.Document._update_status_from_validate(doc, {"estado": "Vigente"})
        self.assertEqual(doc.sat_status, "valid")

    def test_unlink_manual_blocked(self):
        doc = self.Document._sat_create(
            [
                {
                    "company_id": self.company.id,
                    "uuid": "UNLINK-BLOCK-UUID",
                    "document_kind": "cfdi",
                    "direction": "received",
                }
            ]
        )
        with self.assertRaises(AccessError):
            doc.unlink()

    def test_display_name_includes_labels(self):
        doc = self.Document._sat_create(
            [
                {
                    "company_id": self.company.id,
                    "uuid": "DISPLAY-UUID-123",
                    "document_kind": "cfdi",
                    "direction": "received",
                }
            ]
        )
        self.assertIn("DISPLAY-UUID-123", doc.display_name)
        self.assertIn("/", doc.display_name)

    def test_parse_sat_datetime_formats(self):
        self.assertEqual(
            self.Document._parse_sat_datetime("2026-01-01T10:00:00").isoformat(),
            "2026-01-01T10:00:00",
        )
        self.assertEqual(
            self.Document._parse_sat_datetime("2026-01-01 10:00:00").isoformat(),
            "2026-01-01T10:00:00",
        )
        self.assertEqual(
            self.Document._parse_sat_datetime("2026-01-01").isoformat(),
            "2026-01-01T00:00:00",
        )
        self.assertFalse(self.Document._parse_sat_datetime(""))
        self.assertFalse(self.Document._parse_sat_datetime("not-a-date"))

    @mute_logger("odoo.addons.l10n_mx_sat.models.l10n_mx_sat_document")
    def test_upsert_from_xml_without_uuid(self):
        request = self._create_request(document_kind="cfdi", direction="received")
        xml_bytes = (
            b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4">'
            b'<cfdi:Receptor Rfc="EKU9003173C9"/>'
            b"</cfdi:Comprobante>"
        )
        tree = self._parse_xml(xml_bytes)
        self.assertFalse(
            self.Document._upsert_from_xml(tree, xml_bytes, self.company, request)
        )

    def test_upsert_from_xml_updates_existing_attachment(self):
        request = self._create_request(document_kind="cfdi", direction="received")
        uuid = "UPSERT-UPDATE-UUID-1234567890123456789012"

        def _xml(total):
            return (
                b'<?xml version="1.0" encoding="UTF-8"?>'
                b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" '
                b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
                b'Total="' + total + b'">'
                b'<cfdi:Emisor Rfc="AAA010101AAA" Nombre="Emisor"/>'
                b'<cfdi:Receptor Rfc="EKU9003173C9" Nombre="Receptor"/>'
                b"<cfdi:Complemento>"
                b'<tfd:TimbreFiscalDigital UUID="' + uuid.encode() + b'"/>'
                b"</cfdi:Complemento></cfdi:Comprobante>"
            )

        first = _xml(b"10.00")
        doc1 = self.Document._upsert_from_xml(
            self._parse_xml(first), first, self.company, request
        )
        second = _xml(b"99.50")
        doc2 = self.Document._upsert_from_xml(
            self._parse_xml(second), second, self.company, request
        )
        self.assertEqual(doc1.id, doc2.id)
        self.assertEqual(doc2.attachment_id.raw, second)

    def test_parse_xml_values_cfdi_fields(self):
        xml_bytes = (
            b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" '
            b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
            b'Serie="A" Folio="1" Moneda="MXN" TipoDeComprobante="I" '
            b'Fecha="2026-02-01T12:00:00" Total="bad-total">'
            b'<cfdi:Emisor Rfc="AAA010101AAA" Nombre="Emisor SA"/>'
            b'<cfdi:Receptor Rfc="EKU9003173C9" Nombre="Receptor SA"/>'
            b"<cfdi:Complemento>"
            b'<tfd:TimbreFiscalDigital UUID="PARSE-CFDI-UUID" '
            b'FechaTimbrado="2026-02-01T12:05:00"/>'
            b"</cfdi:Complemento></cfdi:Comprobante>"
        )
        values = self.Document._parse_xml_values(
            self._parse_xml(xml_bytes),
            document_kind="cfdi",
        )
        self.assertEqual(values["series"], "A")
        self.assertEqual(values["folio_number"], "1")
        self.assertEqual(values["currency_code"], "MXN")
        self.assertEqual(values["voucher_type"], "I")
        self.assertEqual(values["issuer_rfc"], "AAA010101AAA")
        self.assertEqual(values["receiver_rfc"], "EKU9003173C9")
        self.assertEqual(values["sat_status"], "valid")
        self.assertNotIn("total", values)
        self.assertTrue(values["issue_date"])
        self.assertTrue(values["stamp_date"])

    def test_validate_xml_company_missing_partner_nodes(self):
        request = self._create_request(document_kind="cfdi", direction="received")
        tree = self._parse_xml(
            b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"/>'
        )
        self.assertFalse(
            self.Document._validate_xml_company(tree, self.company, request)
        )
        request_issued = self._create_request(document_kind="cfdi", direction="issued")
        self.assertFalse(
            self.Document._validate_xml_company(tree, self.company, request_issued)
        )

    def test_get_company_rfc_returns_false_on_exception(self):
        self.company.vat = False
        with patch(_PATCH_GET_CLIENT, side_effect=Exception("boom")):
            self.assertFalse(self.Document._get_company_rfc(self.company))

    def test_upsert_from_metadata_empty_uuid(self):
        request = self._create_request(request_type="metadata")
        doc = self.Document._upsert_from_metadata_row(
            {"uuid": "", "sat_status": "valid"},
            self.company,
            request,
        )
        self.assertFalse(doc)

    def test_upsert_from_metadata_invalid_total_and_preserve_blanks(self):
        request = self._create_request(request_type="metadata")
        doc = self.Document._upsert_from_metadata_row(
            {
                "uuid": "META-PRESERVE-UUID-123456789012345678",
                "issuer_rfc": "AAA010101AAA",
                "issuer_name": "Issuer",
                "receiver_rfc": "EKU9003173C9",
                "receiver_name": "Receiver",
                "voucher_type": "I",
                "sat_status": "valid",
                "total": "100.50",
                "issue_date": "2026-02-01T10:00:00",
            },
            self.company,
            request,
        )
        self.assertEqual(doc.total, 100.50)
        self.Document._upsert_from_metadata_row(
            {
                "uuid": "META-PRESERVE-UUID-123456789012345678",
                "issuer_rfc": "",
                "issuer_name": "",
                "total": "not-a-float",
                "sat_status": "cancelled",
            },
            self.company,
            request,
        )
        self.assertEqual(doc.issuer_rfc, "AAA010101AAA")
        self.assertEqual(doc.issuer_name, "Issuer")
        self.assertEqual(doc.total, 100.50)
        self.assertEqual(doc.sat_status, "cancelled")

    def test_display_name_without_kind_or_direction(self):
        doc = self.Document.new(
            {
                "uuid": "DISP-NAME-UUID-12345678901234567890",
                "document_kind": False,
                "direction": False,
            }
        )
        doc._compute_display_name()
        self.assertEqual(doc.display_name, "DISP-NAME-UUID-12345678901234567890")

    def test_manual_api_returns_after_check_patched(self):
        with patch.object(
            type(self.Document), "_check_not_manual_update", lambda self: None
        ):
            doc = self.Document.create(
                {
                    "company_id": self.company.id,
                    "uuid": "MANUAL-API-UUID-123456789012345678901",
                    "document_kind": "cfdi",
                    "direction": "received",
                }
            )
            doc.write({"issuer_name": "Patched"})
            self.assertEqual(doc.issuer_name, "Patched")
            self.assertTrue(doc.unlink())
